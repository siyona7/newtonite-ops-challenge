"""Test the authorization module with permission matrix."""
import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User, TeamMember, Role
from app.models.team import Team
from app.models.item import Item, ItemType, Priority, Status
from app.auth.authorization import authorize, Action, ResourceType, get_team_memberships
from app.auth.security import get_password_hash


@pytest.mark.asyncio
async def test_permission_matrix(db_session: AsyncSession):
    """Test that each role has the correct permissions."""
    # Create a team
    team = Team(name="TestTeam")
    db_session.add(team)
    await db_session.flush()

    # Create users with different roles
    users = {}
    for role in Role:
        user = User(
            email=f"{role.value}@test.com",
            name=f"{role.value} User",
            password_hash=get_password_hash("password")
        )
        db_session.add(user)
        await db_session.flush()

        # Add user to team with specific role
        member = TeamMember(
            user_id=user.id,
            team_id=team.id,
            role=role
        )
        db_session.add(member)
        users[role] = user

    # Create an item in the team
    item = Item(
        team_id=team.id,
        type=ItemType.TASK,
        title="Test Item",
        priority=Priority.MEDIUM,
        status=Status.OPEN
    )
    db_session.add(item)
    await db_session.commit()

    # Define expected permissions for each role
    expected_permissions = {
        Role.VIEWER: {Action.READ, Action.COMMENT},
        Role.MEMBER: {Action.READ, Action.CREATE, Action.UPDATE, Action.CLAIM, Action.COMMENT},
        Role.LEAD: {Action.READ, Action.CREATE, Action.UPDATE, Action.DELETE, Action.CLAIM, Action.APPROVE, Action.COMMENT},
        Role.ADMIN: {Action.READ, Action.CREATE, Action.UPDATE, Action.DELETE, Action.CLAIM, Action.APPROVE, Action.COMMENT},
    }

    # Test each role's permissions
    for role, user in users.items():
        expected = expected_permissions[role]

        for action in Action:
            result = await authorize(
                db_session,
                user,
                action,
                ResourceType.ITEM,
                str(item.id)
            )
            if action in expected:
                assert result is True, f"{role} should be able to {action}"
            else:
                assert result is False, f"{role} should NOT be able to {action}"


@pytest.mark.asyncio
async def test_cross_team_access_returns_404(db_session: AsyncSession):
    """Test that users from one team cannot access resources from another team."""
    # Create two teams
    team1 = Team(name="Team1")
    team2 = Team(name="Team2")
    db_session.add_all([team1, team2])
    await db_session.flush()

    # Create user in team1
    user = User(
        email="user1@test.com",
        name="User1",
        password_hash=get_password_hash("password")
    )
    db_session.add(user)
    await db_session.flush()

    member = TeamMember(
        user_id=user.id,
        team_id=team1.id,
        role=Role.ADMIN
    )
    db_session.add(member)

    # Create item in team2
    item = Item(
        team_id=team2.id,
        type=ItemType.TASK,
        title="Team2 Item",
        priority=Priority.MEDIUM,
        status=Status.OPEN
    )
    db_session.add(item)
    await db_session.commit()

    # User from team1 should not be able to access team2's item
    with pytest.raises(ValueError, match="User not in team"):
        await authorize(
            db_session,
            user,
            Action.READ,
            ResourceType.ITEM,
            str(item.id)
        )


@pytest.mark.asyncio
async def test_nonexistent_resource_returns_404(db_session: AsyncSession):
    """Test that accessing a nonexistent resource raises ValueError."""
    # Create a team and user
    team = Team(name="TestTeam")
    db_session.add(team)
    await db_session.flush()

    user = User(
        email="user@test.com",
        name="User",
        password_hash=get_password_hash("password")
    )
    db_session.add(user)
    await db_session.flush()

    member = TeamMember(
        user_id=user.id,
        team_id=team.id,
        role=Role.ADMIN
    )
    db_session.add(member)
    await db_session.commit()

    # Try to access a nonexistent item
    fake_item_id = str(uuid.uuid4())
    with pytest.raises(ValueError, match="Item not found"):
        await authorize(
            db_session,
            user,
            Action.READ,
            ResourceType.ITEM,
            fake_item_id
        )


@pytest.mark.asyncio
async def test_get_team_memberships(db_session: AsyncSession):
    """Test getting team memberships for a user."""
    # Create teams
    team1 = Team(name="Team1")
    team2 = Team(name="Team2")
    db_session.add_all([team1, team2])
    await db_session.flush()

    # Create user
    user = User(
        email="user@test.com",
        name="User",
        password_hash=get_password_hash("password")
    )
    db_session.add(user)
    await db_session.flush()

    # Add user to both teams with different roles
    member1 = TeamMember(
        user_id=user.id,
        team_id=team1.id,
        role=Role.ADMIN
    )
    member2 = TeamMember(
        user_id=user.id,
        team_id=team2.id,
        role=Role.MEMBER
    )
    db_session.add_all([member1, member2])
    await db_session.commit()

    # Get memberships
    memberships = await get_team_memberships(db_session, str(user.id))

    assert len(memberships) == 2
    team_names = {m["team_name"] for m in memberships}
    assert "Team1" in team_names
    assert "Team2" in team_names

    # Check roles
    for m in memberships:
        if m["team_name"] == "Team1":
            assert m["role"] == Role.ADMIN
        elif m["team_name"] == "Team2":
            assert m["role"] == Role.MEMBER


@pytest.mark.asyncio
async def test_viewer_cannot_delete(db_session: AsyncSession):
    """Test that viewers cannot delete items."""
    # Create team and viewer user
    team = Team(name="TestTeam")
    db_session.add(team)
    await db_session.flush()

    user = User(
        email="viewer@test.com",
        name="Viewer",
        password_hash=get_password_hash("password")
    )
    db_session.add(user)
    await db_session.flush()

    member = TeamMember(
        user_id=user.id,
        team_id=team.id,
        role=Role.VIEWER
    )
    db_session.add(member)

    # Create item
    item = Item(
        team_id=team.id,
        type=ItemType.TASK,
        title="Test Item",
        priority=Priority.MEDIUM,
        status=Status.OPEN
    )
    db_session.add(item)
    await db_session.commit()

    # Viewer should not be able to delete
    result = await authorize(
        db_session,
        user,
        Action.DELETE,
        ResourceType.ITEM,
        str(item.id)
    )
    assert result is False


@pytest.mark.asyncio
async def test_admin_can_approve(db_session: AsyncSession):
    """Test that admins can approve items."""
    # Create team and admin user
    team = Team(name="TestTeam")
    db_session.add(team)
    await db_session.flush()

    user = User(
        email="admin@test.com",
        name="Admin",
        password_hash=get_password_hash("password")
    )
    db_session.add(user)
    await db_session.flush()

    member = TeamMember(
        user_id=user.id,
        team_id=team.id,
        role=Role.ADMIN
    )
    db_session.add(member)

    # Create item
    item = Item(
        team_id=team.id,
        type=ItemType.TASK,
        title="Test Item",
        priority=Priority.MEDIUM,
        status=Status.OPEN
    )
    db_session.add(item)
    await db_session.commit()

    # Admin should be able to approve
    result = await authorize(
        db_session,
        user,
        Action.APPROVE,
        ResourceType.ITEM,
        str(item.id)
    )
    assert result is True
