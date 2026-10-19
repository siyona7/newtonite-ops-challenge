from typing import Optional
from datetime import datetime
from sqlalchemy import String, DateTime, func, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db.base import Base


class IdempotencyKey(Base):
    """Idempotency keys to prevent duplicate operations."""
    __tablename__ = "idempotency_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    # Store the endpoint that was called
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    # Store the response parameters to return on duplicate requests
    response_params: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
