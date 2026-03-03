"""Messages API — inbox, unread count, mark as read."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database import get_db
from app.models.message import Message
from app.models.agent import Agent
from app.models.user import User

router = APIRouter(tags=["messages"])


@router.get("/messages/inbox")
async def get_inbox(
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get messages sent TO the current user (from agents or other agents they manage).

    Returns messages where receiver is the current user,
    plus messages to agents the user created.
    """
    # Messages directly to this user
    user_msgs_q = select(Message).where(
        Message.receiver_type == "user",
        Message.receiver_id == current_user.id,
    )

    # Messages to agents this user created
    agent_ids_q = select(Agent.id).where(Agent.creator_id == current_user.id)
    agent_ids_result = await db.execute(agent_ids_q)
    my_agent_ids = [r[0] for r in agent_ids_result.fetchall()]

    if my_agent_ids:
        agent_msgs_q = select(Message).where(
            Message.receiver_type == "agent",
            Message.receiver_id.in_(my_agent_ids),
        )
        from sqlalchemy import union_all
        combined = union_all(user_msgs_q, agent_msgs_q).subquery()
        result = await db.execute(
            select(Message)
            .where(Message.id.in_(select(combined.c.id)))
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
    else:
        result = await db.execute(
            user_msgs_q.order_by(Message.created_at.desc()).limit(limit)
        )

    messages = result.scalars().all()

    # Enrich with sender names
    sender_cache: dict[str, str] = {}

    async def get_sender_name(s_type: str, s_id: uuid.UUID) -> str:
        key = f"{s_type}:{s_id}"
        if key not in sender_cache:
            if s_type == "agent":
                r = await db.execute(select(Agent.name).where(Agent.id == s_id))
                name = r.scalar_one_or_none() or "未知员工"
            else:
                r = await db.execute(select(User.display_name).where(User.id == s_id))
                name = r.scalar_one_or_none() or "未知用户"
            sender_cache[key] = name
        return sender_cache[key]

    async def get_receiver_name(r_type: str, r_id: uuid.UUID) -> str:
        key = f"{r_type}:{r_id}"
        if key not in sender_cache:
            if r_type == "agent":
                r = await db.execute(select(Agent.name).where(Agent.id == r_id))
                name = r.scalar_one_or_none() or "未知员工"
            else:
                r = await db.execute(select(User.display_name).where(User.id == r_id))
                name = r.scalar_one_or_none() or "未知用户"
            sender_cache[key] = name
        return sender_cache[key]

    result_list = []
    for msg in messages:
        result_list.append({
            "id": str(msg.id),
            "sender_type": msg.sender_type,
            "sender_id": str(msg.sender_id),
            "sender_name": await get_sender_name(msg.sender_type, msg.sender_id),
            "receiver_type": msg.receiver_type,
            "receiver_id": str(msg.receiver_id),
            "receiver_name": await get_receiver_name(msg.receiver_type, msg.receiver_id),
            "content": msg.content,
            "msg_type": msg.msg_type,
            "read_at": msg.read_at.isoformat() if msg.read_at else None,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        })

    return result_list


@router.get("/messages/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get count of unread messages for the current user."""
    # Direct messages to user
    user_count_q = select(func.count(Message.id)).where(
        Message.receiver_type == "user",
        Message.receiver_id == current_user.id,
        Message.read_at.is_(None),
    )

    # Messages to user's agents
    agent_ids_q = select(Agent.id).where(Agent.creator_id == current_user.id)
    agent_ids_result = await db.execute(agent_ids_q)
    my_agent_ids = [r[0] for r in agent_ids_result.fetchall()]

    user_count_result = await db.execute(user_count_q)
    total = user_count_result.scalar() or 0

    if my_agent_ids:
        agent_count_q = select(func.count(Message.id)).where(
            Message.receiver_type == "agent",
            Message.receiver_id.in_(my_agent_ids),
            Message.read_at.is_(None),
        )
        agent_count_result = await db.execute(agent_count_q)
        total += agent_count_result.scalar() or 0

    return {"unread_count": total}


@router.put("/messages/{message_id}/read")
async def mark_message_read(
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a message as read."""
    result = await db.execute(select(Message).where(Message.id == message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    msg.read_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "ok"}


@router.put("/messages/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all messages as read for the current user."""
    from sqlalchemy import update

    now = datetime.now(timezone.utc)

    # Direct messages
    await db.execute(
        update(Message)
        .where(
            Message.receiver_type == "user",
            Message.receiver_id == current_user.id,
            Message.read_at.is_(None),
        )
        .values(read_at=now)
    )

    # Messages to user's agents
    agent_ids_q = select(Agent.id).where(Agent.creator_id == current_user.id)
    agent_ids_result = await db.execute(agent_ids_q)
    my_agent_ids = [r[0] for r in agent_ids_result.fetchall()]

    if my_agent_ids:
        await db.execute(
            update(Message)
            .where(
                Message.receiver_type == "agent",
                Message.receiver_id.in_(my_agent_ids),
                Message.read_at.is_(None),
            )
            .values(read_at=now)
        )

    await db.commit()
    return {"status": "ok"}
