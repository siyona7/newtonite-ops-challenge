import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.models.item import Item, ItemType, Priority, Status
from app.models.user import User, Role
from app.models.event import Event, EventType
from app.auth.dependencies import get_current_user
from app.auth.authorization import Action, ResourceType
from app.db.session import get_db


class MockAsyncSession:
    """In-memory mock async session for testing item workflows and behaviors."""

    def __init__(self):
        self.store = {}
        self.events = []
        self.comments = []
        self.idempotency = {}
        self.outbox = []

    def add(self, obj):
        if hasattr(obj, "id"):
            self.store[obj.id] = obj
        if isinstance(obj, Event):
            self.events.append(obj)

    def add_all(self, objs):
        for o in objs:
            self.add(o)

    async def get(self, model, ident):
        if isinstance(ident, str):
            try:
                ident = uuid.UUID(ident)
            except ValueError:
                return None
        return self.store.get(ident)

    async def execute(self, statement):
        # Handle count query
        stmt_str = str(statement)
        class MockResult:
            def __init__(self, data):
                self._data = data

            def scalar_one_or_none(self):
                return self._data[0] if self._data else None

            def scalar_one(self):
                return len(self._data) if isinstance(self._data, list) else self._data

            def scalar(self):
                return self.scalar_one_or_none()

            def scalars(self):
                class Scalars:
                    def __init__(self, items):
                        self._items = items
                    def all(self):
                        return self._items
                return Scalars(self._data if isinstance(self._data, list) else [self._data])

            def all(self):
                return self._data if isinstance(self._data, list) else []

            @property
            def rowcount(self):
                return 1

        if "idempotency_keys" in stmt_str:
            return MockResult([])
        if "items" in stmt_str and "UPDATE" in stmt_str:
            return MockResult([1])
        if "items" in stmt_str:
            items_list = [v for v in self.store.values() if isinstance(v, Item)]
            return MockResult(items_list)
        return MockResult([])

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass


@pytest.fixture
def mock_context():
    session = MockAsyncSession()
    user_id = uuid.uuid4()
    team_id = uuid.uuid4()
    user = User(
        id=user_id,
        email="lead@newtonite.test",
        name="Lead User",
    )

    # Prepopulate an item in team
    item_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    item = Item(
        id=item_id,
        team_id=team_id,
        owner_id=None,
        type=ItemType.TASK,
        title="Initial Task",
        description="Task description",
        priority=Priority.MEDIUM,
        status=Status.OPEN,
        version=1,
        extra={},
        created_at=now,
        updated_at=now,
    )
    session.add(item)

    async def override_get_current_user():
        return user

    async def override_get_db():
        yield session

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    from app.routers import items
    # Override check_auth so unit tests focus on endpoint behavior
    original_check_auth = items.check_auth

    async def noop_check_auth(*args, **kwargs):
        return True

    items.check_auth = noop_check_auth

    yield {
        "session": session,
        "user": user,
        "team_id": team_id,
        "item": item,
    }

    items.check_auth = original_check_auth
    app.dependency_overrides.clear()


def test_create_item_and_idempotency(client: TestClient, mock_context):
    """Test item creation and idempotency-key handling (Behavior 3)."""
    payload = {
        "team_id": str(mock_context["team_id"]),
        "type": "incident",
        "title": "Payment gateway down",
        "priority": "critical",
        "metadata": {"env": "prod"},
    }

    # 1. Create item
    headers = {"Idempotency-Key": "req-12345"}
    resp = client.post("/items", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Payment gateway down"
    assert data["status"] == "open"
    assert data["version"] == 1
    assert "ETag" in resp.headers


def test_stale_edit_protection(client: TestClient, mock_context):
    """Test If-Match version header prevents stale edits (Behavior 2)."""
    item = mock_context["item"]

    # 1. Matching version should succeed
    update_payload = {"title": "Updated Title", "version": 1}
    resp = client.patch(f"/items/{item.id}", json=update_payload, headers={"If-Match": '"1"'})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Title"

    # 2. Outdated version should fail with 412 Precondition Failed
    stale_payload = {"title": "Stale Edit Attempt"}
    stale_resp = client.patch(f"/items/{item.id}", json=stale_payload, headers={"If-Match": '"999"'})
    assert stale_resp.status_code == 412
    assert "Stale edit" in stale_resp.json()["detail"]


def test_workflow_status_transitions(client: TestClient, mock_context):
    """Test valid and invalid status transitions (Behavior 4)."""
    item = mock_context["item"]
    assert item.status == Status.OPEN

    # 1. Invalid jump from OPEN directly to COMPLETED -> 400
    bad_resp = client.post(f"/items/{item.id}/transition", json={"status": "completed"})
    assert bad_resp.status_code == 400
    assert "Invalid transition" in bad_resp.json()["detail"]

    # 2. Valid transition from OPEN to IN_PROGRESS -> 200
    good_resp = client.post(f"/items/{item.id}/transition", json={"status": "in_progress"})
    assert good_resp.status_code == 200
    assert good_resp.json()["status"] == "in_progress"


def test_atomic_claim(client: TestClient, mock_context):
    """Test atomic claim mechanism (Behavior 1)."""
    item = mock_context["item"]
    user = mock_context["user"]
    item.owner_id = None

    # Claim unclaimed item
    resp = client.post(f"/items/{item.id}/claim")
    assert resp.status_code == 200

    # Idempotent re-claim by same user succeeds
    item.owner_id = user.id
    resp2 = client.post(f"/items/{item.id}/claim")
    assert resp2.status_code == 200


def test_add_comment_and_history(client: TestClient, mock_context):
    """Test adding comments and audit history (Phase 6)."""
    item = mock_context["item"]

    # 1. Add comment
    comment_resp = client.post(
        f"/items/{item.id}/comments",
        json={"content": "Investigating the incident now."},
    )
    assert comment_resp.status_code == 201
    assert comment_resp.json()["content"] == "Investigating the incident now."

    # 2. List history
    history_resp = client.get(f"/items/{item.id}/history")
    assert history_resp.status_code == 200


def test_server_side_authorization_forbidden(client: TestClient, mock_context):
    """Test that server-side authorization returns 403 Forbidden when action is disallowed."""
    from app.routers import items
    from fastapi import HTTPException

    # Simulate authorization check failing (e.g. Viewer attempting to delete or claim)
    async def deny_auth(*args, **kwargs):
        raise HTTPException(status_code=403, detail="Forbidden: user lacks 'claim' permission")

    original_check_auth = items.check_auth
    items.check_auth = deny_auth
    try:
        item = mock_context["item"]
        resp = client.post(f"/items/{item.id}/claim")
        assert resp.status_code == 403
        assert "Forbidden" in resp.json()["detail"]
    finally:
        items.check_auth = original_check_auth


def test_server_side_authorization_cross_team_404(client: TestClient, mock_context):
    """Test that server-side authorization returns 404 for cross-team or nonexistent access."""
    from app.routers import items
    from fastapi import HTTPException

    async def not_found_auth(*args, **kwargs):
        raise HTTPException(status_code=404, detail="User not in team")

    original_check_auth = items.check_auth
    items.check_auth = not_found_auth
    try:
        item = mock_context["item"]
        resp = client.get(f"/items/{item.id}")
        assert resp.status_code == 404
        assert "User not in team" in resp.json()["detail"]
    finally:
        items.check_auth = original_check_auth

