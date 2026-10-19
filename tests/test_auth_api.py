import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.user import User, Role
from app.auth.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
)
from app.auth.dependencies import get_current_user
from jose import jwt


def test_password_hashing():
    """Verify password hashing with argon2 works properly."""
    raw = "MySecurePassword123!"
    hashed = get_password_hash(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_token_creation_and_tampering():
    """Verify JWT token creation, decoding, and rejection of tampered tokens."""
    data = {"sub": str(uuid.uuid4())}
    token = create_access_token(data)
    assert token is not None

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == data["sub"]

    # Tampered token with wrong secret
    tampered = jwt.encode(data, "wrong-secret-key", algorithm="HS256")
    assert decode_access_token(tampered) is None

    # Invalid token string
    assert decode_access_token("completely-invalid-jwt") is None


def test_unauthenticated_me_route(client: TestClient):
    """Test that /auth/me returns 401 when no token is provided."""
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_unauthenticated_me_alias(client: TestClient):
    """Test that /me returns 401 when no token is provided."""
    response = client.get("/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_invalid_token_header(client: TestClient):
    """Test that invalid token in Authorization header returns 401."""
    response = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.payload"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


def test_invalid_token_cookie(client: TestClient):
    """Test that invalid token in cookie returns 401."""
    client.cookies.set("access_token", "invalid.token.here")
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


def test_login_invalid_email_format(client: TestClient):
    """Test that login validates email format with 422."""
    response = client.post("/auth/login", json={"email": "not-an-email", "password": "password"})
    assert response.status_code == 422


def test_logout(client: TestClient):
    """Test that logout succeeds and clears the cookie."""
    client.cookies.set("access_token", "test-token")
    response = client.post("/auth/logout")
    assert response.status_code == 200
    assert response.json() == {"message": "Logout successful"}
    # Verify cookie deleted or expired
    cookie = response.cookies.get("access_token")
    assert cookie is None or cookie == "" or response.headers.get("set-cookie", "").find("Max-Age=0") != -1


def test_authenticated_me_endpoint_with_override(client: TestClient):
    """Test /auth/me and /me endpoints with an authenticated user via dependency override."""
    test_user_id = uuid.uuid4()
    mock_user = User(
        id=test_user_id,
        email="testuser@example.com",
        name="Test User",
        password_hash=get_password_hash("password123"),
    )

    async def mock_get_current_user():
        return mock_user

    async def mock_get_db():
        # Empty dummy async generator for session
        class DummySession:
            async def execute(self, *args, **kwargs):
                class DummyResult:
                    def all(self):
                        return []
                return DummyResult()
        yield DummySession()

    from app.db.session import get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_db] = mock_get_db

    try:
        response = client.get("/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_user_id)
        assert data["email"] == "testuser@example.com"
        assert data["name"] == "Test User"
        assert data["memberships"] == []

        # Also test /me alias
        alias_response = client.get("/me")
        assert alias_response.status_code == 200
        assert alias_response.json()["email"] == "testuser@example.com"
    finally:
        app.dependency_overrides.clear()
