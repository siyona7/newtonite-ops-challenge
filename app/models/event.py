import enum
from datetime import datetime
from sqlalchemy import String, DateTime, func, ForeignKey, Text, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db.base import Base


class EventType(str, enum.Enum):
    """Types of events that can occur on items."""
    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    CLAIMED = "claimed"
    UNCLAIMED = "unclaimed"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMMENT_ADDED = "comment_added"


class Event(Base):
    """Append-only event log for all item changes."""
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[EventType] = mapped_column(String, nullable=False, index=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Previous state snapshot for audit trail
    old_values: Mapped[dict] = mapped_column(JSONB, nullable=True)
    # New state snapshot
    new_values: Mapped[dict] = mapped_column(JSONB, nullable=True)
    # Human-readable description
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
