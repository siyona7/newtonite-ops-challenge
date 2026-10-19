"""Test that all models can be imported and table metadata is accessible."""
import pytest
from app.db.base import Base
from app.models import (
    User,
    TeamMember,
    Team,
    Item,
    Event,
    OutboxMessage,
    IdempotencyKey,
    Comment,
    Notification,
)


def test_models_import():
    """Test that all models can be imported without errors."""
    # If this test passes, all imports worked
    assert User is not None
    assert TeamMember is not None
    assert Team is not None
    assert Item is not None
    assert Event is not None
    assert OutboxMessage is not None
    assert IdempotencyKey is not None
    assert Comment is not None
    assert Notification is not None


def test_table_metadata():
    """Test that all models have table metadata defined."""
    # Check that all models have a __tablename__ attribute
    assert hasattr(User, "__tablename__")
    assert User.__tablename__ == "users"

    assert hasattr(Team, "__tablename__")
    assert Team.__tablename__ == "teams"

    assert hasattr(TeamMember, "__tablename__")
    assert TeamMember.__tablename__ == "team_members"

    assert hasattr(Item, "__tablename__")
    assert Item.__tablename__ == "items"

    assert hasattr(Event, "__tablename__")
    assert Event.__tablename__ == "events"

    assert hasattr(OutboxMessage, "__tablename__")
    assert OutboxMessage.__tablename__ == "outbox_messages"

    assert hasattr(IdempotencyKey, "__tablename__")
    assert IdempotencyKey.__tablename__ == "idempotency_keys"

    assert hasattr(Comment, "__tablename__")
    assert Comment.__tablename__ == "comments"

    assert hasattr(Notification, "__tablename__")
    assert Notification.__tablename__ == "notifications"


def test_base_metadata():
    """Test that Base metadata includes all model tables."""
    table_names = {table.name for table in Base.metadata.tables.values()}
    expected_tables = {
        "users",
        "teams",
        "team_members",
        "items",
        "events",
        "outbox_messages",
        "idempotency_keys",
        "comments",
        "notifications",
    }
    assert table_names == expected_tables
