from datetime import timedelta
from fastapi import APIRouter, HTTPException, status, Response, Depends
from pydantic import BaseModel, EmailStr, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.user import User
from app.auth.security import verify_password, create_access_token, get_password_hash
from app.auth.dependencies import get_current_user
from app.auth.authorization import get_team_memberships

router = APIRouter(prefix="/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    memberships: list[dict]

    model_config = ConfigDict(from_attributes=True)


@router.post("/login")
async def login(
    request: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db)
):
    """Login with email and password, set httpOnly JWT cookie."""
    # Find user by email
    result = await session.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalar_one_or_none()

    # Verify user exists and password is correct
    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Create access token
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=60 * 24 * 7)  # 7 days
    )

    # Set httpOnly cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=60 * 60 * 24 * 7  # 7 days
    )

    return {"message": "Login successful"}


@router.post("/logout")
async def logout(response: Response):
    """Logout by clearing the JWT cookie."""
    response.delete_cookie(key="access_token")
    return {"message": "Logout successful"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Get current user info with team memberships."""
    memberships = await get_team_memberships(session, str(current_user.id))

    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        memberships=memberships
    )
