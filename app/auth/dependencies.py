import uuid
from typing import Optional
from fastapi import Cookie, Header, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.user import User
from app.auth.security import decode_access_token


def extract_token(
    access_token: Optional[str] = None,
    authorization: Optional[str] = None,
) -> Optional[str]:
    """Extract JWT token from either cookie or Authorization header."""
    if access_token:
        return access_token
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
    return None


async def get_current_user(
    session: AsyncSession = Depends(get_db),
    access_token: Optional[str] = Cookie(None, name="access_token"),
    authorization: Optional[str] = Header(None),
) -> User:
    """Dependency to get the current user from JWT cookie or Authorization header."""
    token = extract_token(access_token, authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        user_uuid = uuid.UUID(str(user_id_raw))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = await session.get(User, user_uuid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


async def get_optional_user(
    session: AsyncSession = Depends(get_db),
    access_token: Optional[str] = Cookie(None, name="access_token"),
    authorization: Optional[str] = Header(None),
) -> Optional[User]:
    """Dependency to get the current user if authenticated, None otherwise."""
    token = extract_token(access_token, authorization)
    if not token:
        return None

    payload = decode_access_token(token)
    if payload is None:
        return None

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        return None

    try:
        user_uuid = uuid.UUID(str(user_id_raw))
        user = await session.get(User, user_uuid)
        return user
    except (ValueError, TypeError):
        return None
