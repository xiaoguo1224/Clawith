"""Unified message model for agent↔user and agent↔agent communication."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Message(Base):
    """A message between any combination of agents and users."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sender_type: Mapped[str] = mapped_column(
        Enum("agent", "user", name="msg_participant_type_enum"),
        nullable=False,
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    receiver_type: Mapped[str] = mapped_column(
        Enum("agent", "user", name="msg_participant_type_enum", create_type=False),
        nullable=False,
    )
    receiver_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    msg_type: Mapped[str] = mapped_column(
        Enum("text", "task_delegate", "notify", "consult", name="msg_type_enum"),
        default="text",
        nullable=False,
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
