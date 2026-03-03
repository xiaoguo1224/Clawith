"""Activity log API — view agent work history."""

import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.core.permissions import check_agent_access
from app.database import get_db
from app.models.activity_log import AgentActivityLog
from app.models.user import User

router = APIRouter(tags=["activity"])


@router.get("/agents/{agent_id}/activity")
async def get_agent_activity(
    agent_id: uuid.UUID,
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get recent activity logs for an agent."""
    await check_agent_access(db, current_user, agent_id)

    result = await db.execute(
        select(AgentActivityLog)
        .where(AgentActivityLog.agent_id == agent_id)
        .order_by(AgentActivityLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()

    return [
        {
            "id": str(log.id),
            "action_type": log.action_type,
            "summary": log.summary,
            "detail": log.detail_json,
            "related_id": str(log.related_id) if log.related_id else None,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


# ─── Chat History (per-agent) ─────────────────────────────────

@router.get("/agents/{agent_id}/chat-history/conversations")
async def list_conversations(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all conversation partners for this agent (web users + other agents)."""
    await check_agent_access(db, current_user, agent_id)

    from app.models.audit import ChatMessage
    from app.models.message import Message
    from app.models.agent import Agent

    conversations = []

    # 1. Web chat conversations (from ChatMessage table, grouped by user)
    web_users_q = await db.execute(
        select(ChatMessage.user_id, func.max(ChatMessage.created_at).label("last_at"), func.count(ChatMessage.id).label("cnt"))
        .where(ChatMessage.agent_id == agent_id, ChatMessage.conversation_id.like("web_%"))
        .group_by(ChatMessage.user_id)
    )
    for row in web_users_q.fetchall():
        user_id, last_at, cnt = row
        user_r = await db.execute(select(User.display_name).where(User.id == user_id))
        name = user_r.scalar_one_or_none() or "未知用户"
        # Get last message
        last_msg_r = await db.execute(
            select(ChatMessage.content)
            .where(ChatMessage.agent_id == agent_id, ChatMessage.user_id == user_id)
            .order_by(ChatMessage.created_at.desc()).limit(1)
        )
        last_content = last_msg_r.scalar_one_or_none() or ""
        conversations.append({
            "conv_id": f"web_{user_id}",
            "partner_type": "user",
            "partner_id": str(user_id),
            "partner_name": f"👤 {name}",
            "last_message": last_content[:80],
            "message_count": cnt,
            "last_at": last_at.isoformat() if last_at else None,
        })

    # 1b. Feishu conversations (P2P and group)
    feishu_convs_q = await db.execute(
        select(
            ChatMessage.conversation_id,
            func.max(ChatMessage.created_at).label("last_at"),
            func.count(ChatMessage.id).label("cnt"),
        )
        .where(
            ChatMessage.agent_id == agent_id,
            ChatMessage.conversation_id.like("feishu_%"),
        )
        .group_by(ChatMessage.conversation_id)
    )
    for row in feishu_convs_q.fetchall():
        conv_id, last_at, cnt = row
        # Get last message
        last_msg_r = await db.execute(
            select(ChatMessage.content)
            .where(ChatMessage.agent_id == agent_id, ChatMessage.conversation_id == conv_id)
            .order_by(ChatMessage.created_at.desc()).limit(1)
        )
        last_content = last_msg_r.scalar_one_or_none() or ""

        # Determine display name
        if conv_id.startswith("feishu_p2p_"):
            # Try to get sender name from first user message
            name_r = await db.execute(
                select(ChatMessage.content)
                .where(
                    ChatMessage.agent_id == agent_id,
                    ChatMessage.conversation_id == conv_id,
                    ChatMessage.role == "user",
                )
                .order_by(ChatMessage.created_at.asc()).limit(1)
            )
            first_msg = name_r.scalar_one_or_none() or ""
            # Extract sender name from [发送者: xxx] prefix
            import re
            sender_match = re.search(r'\[发送者:\s*([^\]]+?)(?:\s*\(ID:.*?\))?\]', first_msg)
            display_name = f"📱 {sender_match.group(1)}" if sender_match else f"📱 飞书用户"
        else:
            display_name = "👥 飞书群聊"

        conversations.append({
            "conv_id": conv_id,
            "partner_type": "feishu",
            "partner_id": conv_id,
            "partner_name": display_name,
            "last_message": last_content[:80],
            "message_count": cnt,
            "last_at": last_at.isoformat() if last_at else None,
        })

    # 2. Agent-to-agent conversations (from Message table)
    # Messages where this agent is sender OR receiver
    agent_partners = set()
    sent_q = await db.execute(
        select(Message.receiver_id)
        .where(Message.sender_type == "agent", Message.sender_id == agent_id, Message.receiver_type == "agent")
        .distinct()
    )
    for r in sent_q.fetchall():
        agent_partners.add(r[0])

    recv_q = await db.execute(
        select(Message.sender_id)
        .where(Message.receiver_type == "agent", Message.receiver_id == agent_id, Message.sender_type == "agent")
        .distinct()
    )
    for r in recv_q.fetchall():
        agent_partners.add(r[0])

    for partner_id in agent_partners:
        agent_r = await db.execute(select(Agent.name).where(Agent.id == partner_id))
        partner_name = agent_r.scalar_one_or_none() or "未知数字员工"

        stats_q = await db.execute(
            select(func.count(Message.id), func.max(Message.created_at))
            .where(
                ((Message.sender_id == agent_id) & (Message.receiver_id == partner_id)) |
                ((Message.sender_id == partner_id) & (Message.receiver_id == agent_id))
            )
        )
        stats = stats_q.fetchone()
        cnt = stats[0] if stats else 0
        last_at = stats[1] if stats else None

        last_msg_r = await db.execute(
            select(Message.content)
            .where(
                ((Message.sender_id == agent_id) & (Message.receiver_id == partner_id)) |
                ((Message.sender_id == partner_id) & (Message.receiver_id == agent_id))
            )
            .order_by(Message.created_at.desc()).limit(1)
        )
        last_content = last_msg_r.scalar_one_or_none() or ""

        conversations.append({
            "conv_id": f"agent_{min(str(agent_id), str(partner_id))}_{max(str(agent_id), str(partner_id))}",
            "partner_type": "agent",
            "partner_id": str(partner_id),
            "partner_name": f"🤖 {partner_name}",
            "last_message": last_content[:80],
            "message_count": cnt,
            "last_at": last_at.isoformat() if last_at else None,
        })

    # Sort by last_at desc
    conversations.sort(key=lambda c: c["last_at"] or "", reverse=True)
    return conversations


@router.get("/agents/{agent_id}/chat-history/{conv_id:path}")
async def get_conversation_messages(
    agent_id: uuid.UUID,
    conv_id: str,
    limit: int = Query(100, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get messages for a specific conversation."""
    await check_agent_access(db, current_user, agent_id)

    messages = []

    if conv_id.startswith("web_") or conv_id.startswith("feishu_"):
        from app.models.audit import ChatMessage
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.agent_id == agent_id, ChatMessage.conversation_id == conv_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        for m in result.scalars().all():
            content = m.content
            # Strip [发送者: xxx] prefix for display (identity shown in UI)
            if content.startswith("[发送者:"):
                import re
                content = re.sub(r'^\[发送者:[^\]]*\]\s*', '', content)
            messages.append({
                "id": str(m.id),
                "role": m.role,
                "content": content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            })
    elif conv_id.startswith("agent_"):
        from app.models.message import Message as Msg
        from app.models.agent import Agent
        # Extract partner from conv_id
        parts = conv_id.split("_")
        # conv_id format: agent_{uuid1}_{uuid2}
        id1 = uuid.UUID(parts[1])
        id2 = uuid.UUID("_".join(parts[2:]))  # uuid may contain underscores... no, UUIDs use hyphens
        partner_id = id2 if id1 == agent_id else id1

        result = await db.execute(
            select(Msg)
            .where(
                ((Msg.sender_id == agent_id) & (Msg.receiver_id == partner_id)) |
                ((Msg.sender_id == partner_id) & (Msg.receiver_id == agent_id))
            )
            .order_by(Msg.created_at.asc())
            .limit(limit)
        )
        # Get agent names
        name_cache = {}
        for m in result.scalars().all():
            if str(m.sender_id) not in name_cache:
                r = await db.execute(select(Agent.name).where(Agent.id == m.sender_id))
                name_cache[str(m.sender_id)] = r.scalar_one_or_none() or "未知"
            role = "assistant" if m.sender_id == agent_id else "user"
            messages.append({
                "id": str(m.id),
                "role": role,
                "sender_name": name_cache.get(str(m.sender_id), "未知"),
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            })

    return messages
