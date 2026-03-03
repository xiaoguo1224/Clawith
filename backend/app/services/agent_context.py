"""Build rich system prompt context for agents.

Loads soul, memory, skills summary, and relationships from the agent's
workspace files and composes a comprehensive system prompt.
"""

import uuid
from pathlib import Path

from app.config import get_settings

settings = get_settings()

# Two workspace roots exist — tool workspace and persistent data
TOOL_WORKSPACE = Path("/tmp/clawith_workspaces")
PERSISTENT_DATA = Path(settings.AGENT_DATA_DIR)


def _read_file_safe(path: Path, max_chars: int = 3000) -> str:
    """Read a file, return empty string if missing. Truncate if too long."""
    if not path.exists():
        return ""
    try:
        content = path.read_text(encoding="utf-8", errors="replace").strip()
        if len(content) > max_chars:
            content = content[:max_chars] + "\n...(truncated)"
        return content
    except Exception:
        return ""


def _parse_skill_frontmatter(content: str, filename: str) -> tuple[str, str]:
    """Parse YAML frontmatter from a skill .md file.

    Returns (name, description).
    If no frontmatter, falls back to filename-based name and first-line description.
    """
    name = filename.replace("_", " ").replace("-", " ")
    description = ""

    stripped = content.strip()
    if stripped.startswith("---"):
        end = stripped.find("---", 3)
        if end != -1:
            frontmatter = stripped[3:end].strip()
            for line in frontmatter.split("\n"):
                line = line.strip()
                if line.lower().startswith("name:"):
                    val = line[5:].strip().strip('"').strip("'")
                    if val:
                        name = val
                elif line.lower().startswith("description:"):
                    val = line[12:].strip().strip('"').strip("'")
                    if val:
                        description = val[:200]
            if description:
                return name, description

    # Fallback: use first non-empty, non-heading line as description
    for line in stripped.split("\n"):
        line = line.strip()
        # Skip frontmatter delimiters and YAML lines
        if line in ("---",) or line.startswith("name:") or line.startswith("description:"):
            continue
        if line and not line.startswith("#"):
            description = line[:200]
            break
    if not description:
        lines = stripped.split("\n")
        if lines:
            description = lines[0].strip().lstrip("# ")[:200]

    return name, description


def _load_skills_index(agent_id: uuid.UUID) -> str:
    """Load skill index (name + description) from skills/ directory.

    Supports two formats:
    - Flat file:   skills/my-skill.md
    - Folder:      skills/my-skill/SKILL.md  (Claude-style, with optional scripts/, references/)

    Uses progressive disclosure: only name+description go into the system
    prompt. The model is instructed to call read_file to load full content
    when a skill is relevant.
    """
    skills: list[tuple[str, str, str]] = []  # (name, description, path_relative_to_skills)
    for ws_root in [TOOL_WORKSPACE / str(agent_id), PERSISTENT_DATA / str(agent_id)]:
        skills_dir = ws_root / "skills"
        if not skills_dir.exists():
            continue
        for entry in sorted(skills_dir.iterdir()):
            if entry.name.startswith("."):
                continue

            # Case 1: Folder-based skill — skills/<folder>/SKILL.md
            if entry.is_dir():
                skill_md = entry / "SKILL.md"
                if not skill_md.exists():
                    # Also try lowercase skill.md
                    skill_md = entry / "skill.md"
                if skill_md.exists():
                    try:
                        content = skill_md.read_text(encoding="utf-8", errors="replace").strip()
                        name, desc = _parse_skill_frontmatter(content, entry.name)
                        skills.append((name, desc, f"{entry.name}/SKILL.md"))
                    except Exception:
                        skills.append((entry.name, "", f"{entry.name}/SKILL.md"))

            # Case 2: Flat file — skills/<name>.md
            elif entry.suffix == ".md" and entry.is_file():
                try:
                    content = entry.read_text(encoding="utf-8", errors="replace").strip()
                    name, desc = _parse_skill_frontmatter(content, entry.stem)
                    skills.append((name, desc, entry.name))
                except Exception:
                    skills.append((entry.stem, "", entry.name))

    # Deduplicate by name
    seen: set[str] = set()
    unique: list[tuple[str, str, str]] = []
    for s in skills:
        if s[0] not in seen:
            seen.add(s[0])
            unique.append(s)

    if not unique:
        return ""

    # Build index table
    lines = [
        "You have the following skills available. Each skill defines specific instructions for a task domain.",
        "",
        "| Skill | Description | File |",
        "|-------|-------------|------|",
    ]
    for name, desc, rel_path in unique:
        lines.append(f"| {name} | {desc} | skills/{rel_path} |")

    lines.append("")
    lines.append("⚠️ SKILL USAGE RULES:")
    lines.append("1. When a user request matches a skill, FIRST call `read_file` with the File path above to load the full instructions.")
    lines.append("2. Follow the loaded instructions to complete the task.")
    lines.append("3. Do NOT guess what the skill contains — always read it first.")
    lines.append("4. Folder-based skills may contain auxiliary files (scripts/, references/, examples/). Use `list_files` on the skill folder to discover them.")

    return "\n".join(lines)


async def build_agent_context(agent_id: uuid.UUID, agent_name: str, role_description: str = "") -> str:
    """Build a rich system prompt incorporating agent's full context.

    Reads from workspace files:
    - soul.md → personality
    - memory.md → long-term memory
    - skills/ → skill names + summaries
    - relationships.md → relationship descriptions
    """
    tool_ws = TOOL_WORKSPACE / str(agent_id)
    data_ws = PERSISTENT_DATA / str(agent_id)

    # --- Soul ---
    soul = _read_file_safe(tool_ws / "soul.md", 2000) or _read_file_safe(data_ws / "soul.md", 2000)
    # Strip markdown heading if present
    if soul.startswith("# "):
        soul = "\n".join(soul.split("\n")[1:]).strip()

    # --- Memory ---
    memory = _read_file_safe(tool_ws / "memory" / "memory.md", 2000) or _read_file_safe(tool_ws / "memory.md", 2000)
    if memory.startswith("# "):
        memory = "\n".join(memory.split("\n")[1:]).strip()

    # --- Skills index (progressive disclosure) ---
    skills_text = _load_skills_index(agent_id)

    # --- Relationships ---
    relationships = _read_file_safe(data_ws / "relationships.md", 2000)
    if relationships.startswith("# "):
        relationships = "\n".join(relationships.split("\n")[1:]).strip()

    # --- Compose system prompt ---
    from datetime import datetime, timezone, timedelta
    cst = timezone(timedelta(hours=8))
    now_str = datetime.now(cst).strftime("%Y-%m-%d %H:%M:%S (CST, UTC+8)")
    parts = [f"You are {agent_name}, an enterprise digital employee."]
    parts.append(f"\n## Current Time\n{now_str}")

    if role_description:
        parts.append(f"\n## Role\n{role_description}")

    if soul and soul not in ("_描述你的角色和职责。_", "_Describe your role and responsibilities._"):
        parts.append(f"\n## Personality\n{soul}")

    if memory and memory not in ("_这里记录重要的信息和学到的知识。_", "_Record important information and knowledge here._"):
        parts.append(f"\n## Memory\n{memory}")

    if skills_text:
        parts.append(f"\n## Skills\n{skills_text}")

    if relationships and "暂无" not in relationships and "None yet" not in relationships:
        parts.append(f"\n## Relationships\n{relationships}")

    parts.append("""
## Workspace & Tools

You have a dedicated workspace with this structure:
  - tasks.json     → Your real task list (read-only; use `manage_tasks` tool to manage)
  - soul.md        → Your personality definition
  - memory/memory.md → Your long-term memory and notes
  - skills/        → Your skill definition files (one .md per skill)
  - workspace/     → Your work files (reports, documents, etc.)
  - relationships.md → Your relationship list
  - enterprise_info/ → Shared company information

⚠️ CRITICAL RULES — YOU MUST FOLLOW THESE STRICTLY:

1. **ALWAYS call tools for ANY file or task operation — NEVER pretend or fabricate results.**
   - To list files → CALL `list_files`
   - To read a file → CALL `read_file` or `read_document`
   - To write a file → CALL `write_file`
   - To delete a file → CALL `delete_file`
   - To view tasks → CALL `read_file` with path `tasks.json`
   - To create/update/delete tasks → CALL `manage_tasks`

2. **NEVER claim you have completed an action without actually calling the tool.**
   If you say "I have deleted the file" without calling `delete_file`, that is a LIE.
   If you say "I have read the file" without calling `read_file`, that is a LIE.

3. **NEVER fabricate file contents or tool results from memory.**
   Even if you saw a file before, you MUST call the tool again to get current data.

4. **Use `write_file` to update memory/memory.md with important information.**

5. **Use `send_feishu_message` to message human colleagues in your relationships.**

6. **Reply in the same language the user uses.**

7. **Never assume a file exists — always verify with `list_files` first.**""")

    return "\n".join(parts)
