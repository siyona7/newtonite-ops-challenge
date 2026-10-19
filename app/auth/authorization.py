import uuid
from enum import Enum
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User, TeamMember, Role
from app.models.team import Team
from app.models.item import Item


def _to_uuid(val: Any) -> Optional[uuid.UUID]:
    if val is None:
        return None
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError, AttributeError):
        return None


class Action(str, Enum):
    """Actions that can be performed on resources."""
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    CLAIM = "claim"
    APPROVE = "approve"
    COMMENT = "comment"


class ResourceType(str, Enum):
    """Types of resources."""
    TEAM = "team"
    ITEM = "item"
    EVENT = "event"
    COMMENT = "comment"


# Permission matrix: role -> allowed actions
ROLE_PERMISSIONS = {
    Role.VIEWER: {Action.READ, Action.COMMENT},
    Role.MEMBER: {Action.READ, Action.CREATE, Action.UPDATE, Action.CLAIM, Action.COMMENT},
    Role.LEAD: {Action.READ, Action.CREATE, Action.UPDATE, Action.DELETE, Action.CLAIM, Action.APPROVE, Action.COMMENT},
    Role.ADMIN: {Action.READ, Action.CREATE, Action.UPDATE, Action.DELETE, Action.CLAIM, Action.APPROVE, Action.COMMENT},
}


async def get_user_role_in_team(session: AsyncSession, user_id: Any, team_id: Any) -> Optional[Role]:
    """Get a user's role in a specific team."""
    u_uuid = _to_uuid(user_id)
    t_uuid = _to_uuid(team_id)
    if not u_uuid or not t_uuid:
        return None
    result = await session.execute(
        select(TeamMember.role).where(
            TeamMember.user_id == u_uuid,
            TeamMember.team_id == t_uuid
        )
    )
    return result.scalar_one_or_none()


async def authorize(
    session: AsyncSession,
    user: User,
    action: Action,
    resource_type: ResourceType,
    resource_id: Optional[Any] = None,
) -> bool:
    """
    Central authorization function.

    Args:
        session: Database session
        user: The user attempting the action
        action: The action being attempted
        resource_type: The type of resource
        resource_id: The ID of the resource (optional)

    Returns:
        True if authorized, False otherwise

    Raises:
        ValueError: If resource not found or user not in team (404 case)
    """
    # Get the team_id for the resource
    team_id = None
    res_uuid = _to_uuid(resource_id)

    if resource_type == ResourceType.TEAM:
        if not res_uuid:
            raise ValueError("Team not found")
        team = await session.get(Team, res_uuid)
        if not team:
            raise ValueError("Team not found")
        team_id = team.id

    elif resource_type == ResourceType.ITEM:
        if not res_uuid:
            raise ValueError("Item not found")
        item = await session.get(Item, res_uuid)
        if not item:
            raise ValueError("Item not found")
        team_id = item.team_id

    elif resource_type == ResourceType.EVENT:
        if not res_uuid:
            raise ValueError("Event not found")
        from app.models.event import Event
        event = await session.get(Event, res_uuid)
        if not event:
            raise ValueError("Event not found")
        item = await session.get(Item, event.item_id)
        if not item:
            raise ValueError("Item not found")
        team_id = item.team_id

    elif resource_type == ResourceType.COMMENT:
        if not res_uuid:
            raise ValueError("Comment not found")
        from app.models.comment import Comment
        comment = await session.get(Comment, res_uuid)
        if not comment:
            raise ValueError("Comment not found")
        item = await session.get(Item, comment.item_id)
        if not item:
            raise ValueError("Item not found")
        team_id = item.team_id

    if not team_id:
        return False

    # Get user's role in the team
    role = await get_user_role_in_team(session, user.id, team_id)

    if role is None:
        # User is not in the team - return 404 (resource not found for this user)
        raise ValueError("User not in team")

    # Check if the role has permission for the action
    allowed_actions = ROLE_PERMISSIONS.get(role, set())
    return action in allowed_actions


async def get_team_memberships(session: AsyncSession, user_id: Any) -> list[dict]:
    """Get all team memberships for a user."""
    u_uuid = _to_uuid(user_id)
    if not u_uuid:
        return []
    result = await session.execute(
        select(TeamMember, Team)
        .join(Team, TeamMember.team_id == Team.id)
        .where(TeamMember.user_id == u_uuid)
    )
    memberships = []
    for member, team in result.all():
        memberships.append({
            "team_id": str(team.id),
            "team_name": team.name,
            "role": member.role,
        })
    return memberships
