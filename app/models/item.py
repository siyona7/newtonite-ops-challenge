import enum
from datetime import datetime
from sqlalchemy import String, DateTime, func, ForeignKey, Text, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from app.db.base import Base


class ItemType(str, enum.Enum):
    """Types of operational work items."""
    INCIDENT = "incident"
    PAYMENT = "payment"
    CUSTOMER_ISSUE = "customer_issue"
    COMPLIANCE = "compliance"
    TASK = "task"


class Priority(str, enum.Enum):
    """Priority levels for items."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Status(str, enum.Enum):
    """Status states for items with workflow transitions."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    CLOSED = "closed"


class Item(Base):
    """Operational work item with version control for stale edit detection."""
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    type: Mapped[ItemType] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    priority: Mapped[Priority] = mapped_column(String, nullable=False, default=Priority.MEDIUM)
    status: Mapped[Status] = mapped_column(String, nullable=False, default=Status.OPEN, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Metadata for filtering and search
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=True, default=dict)
    # Full-text search vector will be added via migration
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_items_team_status", "team_id", "status"),
        Index("ix_items_priority_status", "priority", "status"),
    )
