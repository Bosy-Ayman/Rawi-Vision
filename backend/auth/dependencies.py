from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db

from .service.auth import JWT_SECRET, JWT_ALGORITHM
from .repository.system_user import SystemUserRepository
from .models.system_user import SystemUser

# This scheme will automatically look for the "Authorization: Bearer <token>" header
token_auth_scheme = HTTPBearer()

async def get_system_user_repository(db: AsyncSession = Depends(get_db)) -> SystemUserRepository:
    return SystemUserRepository(db=db)

async def get_current_user(
    token: HTTPAuthorizationCredentials = Depends(token_auth_scheme),
    repo: SystemUserRepository = Depends(get_system_user_repository)
) -> SystemUser:
    """
    Validates the provided JWT, extracts the email, and verifies the user
    still exists in the database. Returns the full SystemUser model.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode the JWT
        payload = jwt.decode(token.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email: str = payload.get("email")
        if email is None:
            raise credentials_exception
            
    except JWTError:
        # Catch any expiry or signature errors
        raise credentials_exception

    # Verify user actually exists in the DB still
    user = await repo.get_by_email(email)
    if user is None:
        raise credentials_exception
        
    return user

async def require_hr(current_user: SystemUser = Depends(get_current_user)) -> SystemUser:
    """Dependency that ensures the current user has the 'HR' role."""
    if current_user.role.value != "HR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation restricted to HR personnel only."
        )
    return current_user

async def require_manager(current_user: SystemUser = Depends(get_current_user)) -> SystemUser:
    """
    Dependency that ensures the current user is at least a Manager.
    (Since both HR and Manager can exist, we allow both here, or restrict perfectly)
    """
    # If the endpoint is for managers, HR might be allowed too depending on the system config.
    # We will enforce simply that they have a valid role at all,
    # or strictly check for "Manager".
    if current_user.role.value not in ["Manager", "HR"]:
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation restricted to Managers."
        )
    return current_user
