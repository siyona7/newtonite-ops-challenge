import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Any
from fastapi import APIRouter, HTTPException, status, Depends, Header, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, desc, or_
from app.db.session import get_db
from app.models.item import Item, ItemType, Priority, Status
from app.models.event import Event, EventType
from app.models.comment import Comment
from app.models.idempotency import IdempotencyKey
from app.models.notification import Notification, NotificationType
from app.models.outbox import OutboxMessage, OutboxStatus
from app.models.user import User, Role
from app.auth.dependencies import get_current_user
from app.auth.authorization import authorize, Action, ResourceType, _to_uuid

router = APIRouter(prefix="/items", tags=["items"])

# Allowed workflow transitions
VALID_TRANSITIONS = {
    Status.OPEN: {Status.IN_PROGRESS, Status.CLOSED},
    Status.IN_PROGRESS: {Status.IN_REVIEW, Status.OPEN, Status.CLOSED},
    Status.IN_REVIEW: {Status.APPROVED, Status.REJECTED, Status.IN_PROGRESS},
    Status.APPROVED: {Status.COMPLETED, Status.IN_PROGRESS},
    Status.REJECTED: {Status.IN_PROGRESS, Status.CLOSED},
    Status.COMPLETED: {Status.CLOSED, Status.OPEN},
    Status.CLOSED: {Status.OPEN},
}


# --- Schemas ---

class ItemCreate(BaseModel):
    team_id: uuid.UUID
    type: ItemType = ItemType.TASK
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    priority: Priority = Priority.MEDIUM
    metadata: Optional[dict] = Field(default_factory=dict)


class ItemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    priority: Optional[Priority] = None
    type: Optional[ItemType] = None
    metadata: Optional[dict] = None
    version: Optional[int] = None


class StatusTransitionRequest(BaseModel):
    status: Status
    reason: Optional[str] = None


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1)


class CommentResponse(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    author_id: Optional[uuid.UUID]
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EventResponse(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    event_type: str
    actor_id: Optional[uuid.UUID]
    old_values: Optional[dict]
    new_values: Optional[dict]
    description: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ItemResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    owner_id: Optional[uuid.UUID]
    type: ItemType
    title: str
    description: Optional[str]
    priority: Priority
    status: Status
    version: int
    metadata: Optional[dict] = Field(default=None, alias="extra")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PaginatedItemsResponse(BaseModel):
    items: list[ItemResponse]
    total: int
    limit: int
    offset: int


# --- Helper for Auth Check ---

async def check_auth(
    session: AsyncSession,
    user: User,
    action: Action,
    resource_type: ResourceType,
    resource_id: Optional[Any] = None,
):
    try:
        allowed = await authorize(session, user, action, resource_type, resource_id)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: user lacks '{action.value}' permission for this resource",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# --- Endpoints ---

@router.post("", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    request: ItemCreate,
    response: Response,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Create a new operational work item with optional idempotency and append-only event logging.
    Requires CREATE permission in the target team.
    """
    # 1. Check idempotency if key provided
    if idempotency_key:
        result = await session.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.key == idempotency_key,
                IdempotencyKey.endpoint == "/items",
            )
        )
        existing = result.scalar_one_or_none()
        if existing and existing.response_params:
            cached_data = json.loads(existing.response_params)
            return JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content=cached_data,
                headers={"X-Idempotent-Replayed": "true"},
            )

    # 2. Check team authorization
    await check_auth(session, current_user, Action.CREATE, ResourceType.TEAM, request.team_id)

    # 3. Create the item
    item_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    item = Item(
        id=item_id,
        team_id=request.team_id,
        owner_id=None,
        type=request.type,
        title=request.title,
        description=request.description,
        priority=request.priority,
        status=Status.OPEN,
        version=1,
        extra=request.metadata or {},
        created_at=now,
        updated_at=now,
    )
    session.add(item)

    # 4. Create CREATED event for append-only audit trail
    event = Event(
        id=uuid.uuid4(),
        item_id=item_id,
        event_type=EventType.CREATED,
        actor_id=current_user.id,
        old_values=None,
        new_values={
            "title": request.title,
            "type": request.type.value,
            "priority": request.priority.value,
            "status": Status.OPEN.value,
        },
        description=f"Item created by {current_user.name}",
        created_at=now,
    )
    session.add(event)

    # 5. Outbox message for reliable async processing
    outbox = OutboxMessage(
        id=uuid.uuid4(),
        aggregate_type="item",
        aggregate_id=item_id,
        event_type="item_created",
        payload={
            "item_id": str(item_id),
            "team_id": str(request.team_id),
            "title": request.title,
            "created_by": str(current_user.id),
        },
        status=OutboxStatus.PENDING,
        created_at=now,
    )
    session.add(outbox)

    # 6. Store idempotency key if requested
    item_response_data = {
        "id": str(item.id),
        "team_id": str(item.team_id),
        "owner_id": None,
        "type": item.type.value,
        "title": item.title,
        "description": item.description,
        "priority": item.priority.value,
        "status": item.status.value,
        "version": item.version,
        "metadata": item.extra,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }

    if idempotency_key:
        idem = IdempotencyKey(
            id=uuid.uuid4(),
            key=idempotency_key,
            endpoint="/items",
            response_params=json.dumps(item_response_data),
            created_at=now,
        )
        session.add(idem)

    await session.commit()
    await session.refresh(item)

    response.headers["ETag"] = f'"{item.version}"'
    return item


@router.get("", response_model=PaginatedItemsResponse)
async def list_items(
    team_id: Optional[uuid.UUID] = None,
    status: Optional[Status] = None,
    priority: Optional[Priority] = None,
    type: Optional[ItemType] = None,
    owner_id: Optional[uuid.UUID] = None,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    List items with filtering, search, and pagination.
    """
    limit = min(max(1, limit), 100)
    query = select(Item)

    if team_id:
        await check_auth(session, current_user, Action.READ, ResourceType.TEAM, team_id)
        query = query.where(Item.team_id == team_id)

    if status:
        query = query.where(Item.status == status)
    if priority:
        query = query.where(Item.priority == priority)
    if type:
        query = query.where(Item.type == type)
    if owner_id:
        query = query.where(Item.owner_id == owner_id)
    if q:
        search_filter = or_(
            Item.title.ilike(f"%{q}%"),
            Item.description.ilike(f"%{q}%"),
        )
        query = query.where(search_filter)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    # Paginated results
    query = query.order_by(desc(Item.created_at)).limit(limit).offset(offset)
    result = await session.execute(query)
    items = result.scalars().all()

    return PaginatedItemsResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: uuid.UUID,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get a single item by ID. Validates team membership.
    """
    await check_auth(session, current_user, Action.READ, ResourceType.ITEM, item_id)
    item = await session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    response.headers["ETag"] = f'"{item.version}"'
    return item


@router.patch("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: uuid.UUID,
    request: ItemUpdate,
    response: Response,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Update item fields with optimistic concurrency protection (stale edit detection via If-Match or version).
    """
    await check_auth(session, current_user, Action.UPDATE, ResourceType.ITEM, item_id)
    item = await session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Stale edit check
    expected_version = None
    if if_match:
        try:
            expected_version = int(if_match.strip('"').strip())
        except ValueError:
            pass
    elif request.version is not None:
        expected_version = request.version

    if expected_version is not None and item.version != expected_version:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=f"Stale edit: current version is {item.version}, but client specified {expected_version}",
        )

    # Track changes for event log
    old_values = {}
    new_values = {}

    if request.title is not None and request.title != item.title:
        old_values["title"] = item.title
        new_values["title"] = request.title
        item.title = request.title

    if request.description is not None and request.description != item.description:
        old_values["description"] = item.description
        new_values["description"] = request.description
        item.description = request.description

    if request.priority is not None and request.priority != item.priority:
        old_values["priority"] = item.priority.value
        new_values["priority"] = request.priority.value
        item.priority = request.priority

    if request.type is not None and request.type != item.type:
        old_values["type"] = item.type.value
        new_values["type"] = request.type.value
        item.type = request.type

    if request.metadata is not None:
        old_values["metadata"] = item.extra
        new_values["metadata"] = request.metadata
        item.extra = request.metadata

    if new_values:
        item.version += 1
        item.updated_at = datetime.now(timezone.utc)

        event = Event(
            id=uuid.uuid4(),
            item_id=item.id,
            event_type=EventType.UPDATED,
            actor_id=current_user.id,
            old_values=old_values,
            new_values=new_values,
            description=f"Item updated by {current_user.name}",
            created_at=datetime.now(timezone.utc),
        )
        session.add(event)

    await session.commit()
    await session.refresh(item)

    response.headers["ETag"] = f'"{item.version}"'
    return item


@router.post("/{item_id}/claim", response_model=ItemResponse)
async def claim_item(
    item_id: uuid.UUID,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Atomic claim of an item. Uses conditional update to guarantee race-free ownership assignment.
    """
    await check_auth(session, current_user, Action.CLAIM, ResourceType.ITEM, item_id)
    item = await session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # If already claimed by current user, return success idempotently
    if item.owner_id == current_user.id:
        response.headers["ETag"] = f'"{item.version}"'
        return item

    # Atomic conditional update: only claim if owner_id IS NULL
    now = datetime.now(timezone.utc)
    stmt = (
        update(Item)
        .where(Item.id == item_id, Item.owner_id.is_(None))
        .values(
            owner_id=current_user.id,
            version=Item.version + 1,
            updated_at=now,
        )
    )
    result = await session.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Item is already claimed by another user",
        )

    # Record event
    event = Event(
        id=uuid.uuid4(),
        item_id=item_id,
        event_type=EventType.CLAIMED,
        actor_id=current_user.id,
        old_values={"owner_id": None},
        new_values={"owner_id": str(current_user.id)},
        description=f"Item claimed by {current_user.name}",
        created_at=now,
    )
    session.add(event)

    # Outbox message
    outbox = OutboxMessage(
        id=uuid.uuid4(),
        aggregate_type="item",
        aggregate_id=item_id,
        event_type="item_claimed",
        payload={"item_id": str(item_id), "owner_id": str(current_user.id)},
        status=OutboxStatus.PENDING,
        created_at=now,
    )
    session.add(outbox)

    await session.commit()
    await session.refresh(item)

    response.headers["ETag"] = f'"{item.version}"'
    return item


@router.post("/{item_id}/transition", response_model=ItemResponse)
async def transition_item_status(
    item_id: uuid.UUID,
    request: StatusTransitionRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Validate and execute a workflow status transition.
    Transitions to APPROVED require APPROVE permission (LEAD or ADMIN).
    """
    item = await session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Workflow validation
    allowed_next_states = VALID_TRANSITIONS.get(item.status, set())
    if request.status not in allowed_next_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid transition from {item.status.value} to {request.status.value}",
        )

    # Role check: Approvals require APPROVE permission
    if request.status == Status.APPROVED:
        await check_auth(session, current_user, Action.APPROVE, ResourceType.ITEM, item_id)
    else:
        await check_auth(session, current_user, Action.UPDATE, ResourceType.ITEM, item_id)

    old_status = item.status
    now = datetime.now(timezone.utc)
    item.status = request.status
    item.version += 1
    item.updated_at = now

    event_type = EventType.APPROVED if request.status == Status.APPROVED else EventType.STATUS_CHANGED
    event = Event(
        id=uuid.uuid4(),
        item_id=item.id,
        event_type=event_type,
        actor_id=current_user.id,
        old_values={"status": old_status.value},
        new_values={"status": request.status.value, "reason": request.reason},
        description=f"Status changed from {old_status.value} to {request.status.value} by {current_user.name}",
        created_at=now,
    )
    session.add(event)

    # Notification for item owner if someone else changed status
    if item.owner_id and item.owner_id != current_user.id:
        notif = Notification(
            id=uuid.uuid4(),
            user_id=item.owner_id,
            notification_type=NotificationType.ITEM_STATUS_CHANGED,
            title=f"Item status changed to {request.status.value}",
            message=request.reason or f"Changed by {current_user.name}",
            item_id=item.id,
            is_read=False,
            created_at=now,
        )
        session.add(notif)

    await session.commit()
    await session.refresh(item)

    response.headers["ETag"] = f'"{item.version}"'
    return item


@router.post("/{item_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(
    item_id: uuid.UUID,
    request: CommentCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Add a comment to an item and notify the item owner. Requires COMMENT permission.
    """
    await check_auth(session, current_user, Action.COMMENT, ResourceType.ITEM, item_id)
    item = await session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    now = datetime.now(timezone.utc)
    comment = Comment(
        id=uuid.uuid4(),
        item_id=item.id,
        author_id=current_user.id,
        content=request.content,
        created_at=now,
    )
    session.add(comment)

    # Event for comment
    event = Event(
        id=uuid.uuid4(),
        item_id=item.id,
        event_type=EventType.COMMENT_ADDED,
        actor_id=current_user.id,
        old_values=None,
        new_values={"content_preview": request.content[:100]},
        description=f"Comment added by {current_user.name}",
        created_at=now,
    )
    session.add(event)

    # Notify owner if someone else comments
    if item.owner_id and item.owner_id != current_user.id:
        notif = Notification(
            id=uuid.uuid4(),
            user_id=item.owner_id,
            notification_type=NotificationType.COMMENT_ADDED,
            title="New comment on your item",
            message=request.content[:200],
            item_id=item.id,
            is_read=False,
            created_at=now,
        )
        session.add(notif)

    await session.commit()
    await session.refresh(comment)
    return comment


@router.get("/{item_id}/comments", response_model=list[CommentResponse])
async def list_comments(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    List all comments on an item. Requires READ permission.
    """
    await check_auth(session, current_user, Action.READ, ResourceType.ITEM, item_id)
    result = await session.execute(
        select(Comment).where(Comment.item_id == item_id).order_by(Comment.created_at.asc())
    )
    return result.scalars().all()


@router.get("/{item_id}/history", response_model=list[EventResponse])
async def get_item_history(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Get append-only audit trail events for an item. Requires READ permission.
    """
    await check_auth(session, current_user, Action.READ, ResourceType.ITEM, item_id)
    result = await session.execute(
        select(Event).where(Event.item_id == item_id).order_by(desc(Event.created_at))
    )
    return result.scalars().all()
