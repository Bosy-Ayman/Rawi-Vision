from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from ..repository.system_user import SystemUserRepository
from ..service.auth import AuthService
from ..schemas.system_user import (
    GoogleLoginRequest,
    TokenResponse,
    SystemUserCreate,
    SystemUserResponse,
)
from ..models.system_user import SystemUser
from ..dependencies import require_hr, get_current_user


auth_router = APIRouter(prefix="/auth", tags=["auth"])

# ── Dependency chain ──────────────────────────────────────────────────────────

async def get_auth_repository(db: AsyncSession = Depends(get_db)) -> SystemUserRepository:
    return SystemUserRepository(db=db)

async def get_auth_service(
    repo: SystemUserRepository = Depends(get_auth_repository),
) -> AuthService:
    return AuthService(repository=repo)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@auth_router.post("/google", response_model=TokenResponse)
async def google_login(
    body: GoogleLoginRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    """
    Frontend sends the Google id_token.
    Backend verifies it, returns a short-lived access_token in JSON,
    and sets a long-lived refresh_token in an HttpOnly cookie.
    """
    try:
        result = await service.google_login(body.id_token)
        
        # Extract the refresh token to put in a cookie, remove it from the JSON body
        refresh_token = result.pop("refresh_token")
        
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False, # Set to True in Production with HTTPS
            samesite="lax",
            max_age=7 * 24 * 60 * 60, # 7 days in seconds
        )
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    """
    Reads the HttpOnly refresh_token cookie and issues a new access_token.
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")
        
    try:
        result = await service.refresh_access_token(refresh_token)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    """Clears the HttpOnly refresh_token cookie."""
    response.delete_cookie(key="refresh_token", samesite="lax", secure=False)
    return None


@auth_router.post("/users", response_model=SystemUserResponse, status_code=status.HTTP_201_CREATED)
async def create_system_user(
    data: SystemUserCreate,
    service: AuthService = Depends(get_auth_service),
):
    """SuperAdmin whitelists a new HR or Manager (email + full_name + role)."""
    try:
        user = await service.create_system_user(data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@auth_router.get("/users", response_model=list[SystemUserResponse])
async def list_system_users(
    service: AuthService = Depends(get_auth_service),
):
    """List all whitelisted system users."""
    return await service.get_all_system_users()


@auth_router.delete("/users/{email}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_system_user(
    email: str,
    service: AuthService = Depends(get_auth_service),
):
    """Remove a user from the whitelist by email."""
    try:
        await service.delete_system_user(email)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
