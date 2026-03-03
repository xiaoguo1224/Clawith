"""Tool management API — CRUD for tools and per-agent assignments."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database import get_db
from app.models.tool import Tool, AgentTool
from app.models.user import User

router = APIRouter(prefix="/tools", tags=["tools"])


# ─── Schemas ────────────────────────────────────────────────
class ToolCreate(BaseModel):
    name: str
    display_name: str
    description: str = ""
    type: str = "mcp"
    category: str = "custom"
    icon: str = "🔧"
    parameters_schema: dict = {}
    mcp_server_url: str | None = None
    mcp_server_name: str | None = None
    mcp_tool_name: str | None = None
    is_default: bool = False


class ToolUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    icon: str | None = None
    enabled: bool | None = None
    mcp_server_url: str | None = None
    mcp_server_name: str | None = None
    parameters_schema: dict | None = None
    is_default: bool | None = None
    config: dict | None = None


class AgentToolUpdate(BaseModel):
    tool_id: str
    enabled: bool


# ─── Global Tool CRUD ──────────────────────────────────────
@router.get("")
async def list_tools(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all available tools."""
    result = await db.execute(select(Tool).order_by(Tool.category, Tool.name))
    tools = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "name": t.name,
            "display_name": t.display_name,
            "description": t.description,
            "type": t.type,
            "category": t.category,
            "icon": t.icon,
            "parameters_schema": t.parameters_schema,
            "mcp_server_url": t.mcp_server_url,
            "mcp_server_name": t.mcp_server_name,
            "mcp_tool_name": t.mcp_tool_name,
            "enabled": t.enabled,
            "is_default": t.is_default,
            "config": t.config or {},
            "config_schema": t.config_schema or {},
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tools
    ]


@router.post("")
async def create_tool(
    data: ToolCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new tool (typically MCP)."""
    # Check unique name
    existing = await db.execute(select(Tool).where(Tool.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Tool '{data.name}' already exists")

    tool = Tool(
        name=data.name,
        display_name=data.display_name,
        description=data.description,
        type=data.type,
        category=data.category,
        icon=data.icon,
        parameters_schema=data.parameters_schema,
        mcp_server_url=data.mcp_server_url,
        mcp_server_name=data.mcp_server_name,
        mcp_tool_name=data.mcp_tool_name,
        is_default=data.is_default,
    )
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return {"id": str(tool.id), "name": tool.name}


@router.put("/{tool_id}")
async def update_tool(
    tool_id: uuid.UUID,
    data: ToolUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a tool."""
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(tool, field, value)
    await db.commit()
    return {"ok": True}


@router.delete("/{tool_id}")
async def delete_tool(
    tool_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a tool (only non-builtin)."""
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    if tool.type == "builtin":
        raise HTTPException(status_code=400, detail="Cannot delete builtin tools")

    await db.execute(delete(AgentTool).where(AgentTool.tool_id == tool_id))
    await db.delete(tool)
    await db.commit()
    return {"ok": True}


# ─── Per-Agent Tool Assignment ─────────────────────────────
@router.get("/agents/{agent_id}")
async def get_agent_tools(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get tools for a specific agent with their enabled status."""
    # All available tools
    all_tools_r = await db.execute(select(Tool).where(Tool.enabled == True).order_by(Tool.category, Tool.name))
    all_tools = all_tools_r.scalars().all()

    # Agent-specific assignments
    agent_tools_r = await db.execute(select(AgentTool).where(AgentTool.agent_id == agent_id))
    assignments = {str(at.tool_id): at for at in agent_tools_r.scalars().all()}

    result = []
    for t in all_tools:
        tid = str(t.id)
        at = assignments.get(tid)
        # If no explicit assignment, use is_default
        enabled = at.enabled if at else t.is_default
        result.append({
            "id": tid,
            "name": t.name,
            "display_name": t.display_name,
            "description": t.description,
            "type": t.type,
            "category": t.category,
            "icon": t.icon,
            "enabled": enabled,
            "is_default": t.is_default,
            "mcp_server_name": t.mcp_server_name,
        })
    return result


@router.put("/agents/{agent_id}")
async def update_agent_tools(
    agent_id: uuid.UUID,
    updates: list[AgentToolUpdate],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update tool assignments for an agent."""
    for u in updates:
        tool_id = uuid.UUID(u.tool_id)
        # Upsert
        result = await db.execute(
            select(AgentTool).where(AgentTool.agent_id == agent_id, AgentTool.tool_id == tool_id)
        )
        at = result.scalar_one_or_none()
        if at:
            at.enabled = u.enabled
        else:
            db.add(AgentTool(agent_id=agent_id, tool_id=tool_id, enabled=u.enabled))
    await db.commit()
    return {"ok": True}


# ─── MCP Server Testing ────────────────────────────────────
class MCPTestRequest(BaseModel):
    server_url: str


@router.post("/test-mcp")
async def test_mcp_connection(
    data: MCPTestRequest,
    current_user: User = Depends(get_current_user),
):
    """Test connection to an MCP server and list available tools."""
    from app.services.mcp_client import MCPClient

    try:
        client = MCPClient(data.server_url)
        tools = await client.list_tools()
        return {"ok": True, "tools": tools}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}
