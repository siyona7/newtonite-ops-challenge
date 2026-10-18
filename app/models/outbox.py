import enum
from datetime import datetime
from sqlalchemy import String, DateTime, func, Text, JSONB, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db.base import Base


class OutboxStatus(str, enum.Enum):
    """Status of outbox messages for background job processing."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class OutboxMessage(Base):
    """Outbox pattern table for reliable background job processing."""
    __tablename__ = "outbox_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # Aggregate type (e.g., "item", "team")
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Aggregate ID (e.g., item UUID)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    # Event type (e.g., "item_created", "item_approved")
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # Event payload
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Processing status
    status: Mapped[OutboxStatus] = mapped_column(
        String,
        nullable=False,
        default=OutboxStatus.PENDING,
        index=True,
    )
    # Retry count for failed messages
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Error message if failed
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    # Processing timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    # Time when message moved to dead letter queue
    dead_letter_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
