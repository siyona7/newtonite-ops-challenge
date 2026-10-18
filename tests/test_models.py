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


def test_base_metadata():
    """Test that Base metadata includes all model tables."""
    table_names = {table.name for table in Base.metadata.tables.values()}
    expected_tables = {"users", "teams", "team_members", "items", "events", "outbox_messages"}
    assert table_names == expected_tables
