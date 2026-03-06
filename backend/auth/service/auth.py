import os
from datetime import datetime, timedelta
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from jose import jwt
from dotenv import load_dotenv
from ..repository.system_user import SystemUserRepository
from ..schemas.system_user import SystemUserCreate
from ..models.system_user import SystemUser


load_dotenv()
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "dummy_client_id_for_now")
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_temporary_key")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60
JWT_REFRESH_EXPIRE_DAYS = 7


def _create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def _create_refresh_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(days=JWT_REFRESH_EXPIRE_DAYS)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


class AuthService:
    def __init__(self, repository: SystemUserRepository):
        self.repository = repository

    async def google_login(self, token: str) -> dict:
        """
        1. Verify Google id_token → get email & google_id.
        2. Look up email in system_users.
        3. If found, link google_id on first login, then return a JWT.
        """
        try:
            info = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                GOOGLE_CLIENT_ID,
            )
        except ValueError:
            raise ValueError("Invalid or expired Google token.")

        email: str = info["email"]
        google_sub: str = info["sub"]

        user: SystemUser | None = await self.repository.get_by_email(email)
        if not user:
            raise PermissionError(
                "Access denied. Your email is not registered in this system. "
                "Contact your administrator."
            )

        # First-time login: link the Google account ID
        if user.google_id is None:
            await self.repository.link_google_id(user, google_sub)
            await self.repository.db.commit()
            await self.repository.db.refresh(user)

        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
        }
        
        access_token = _create_access_token(token_data)
        refresh_token = _create_refresh_token(token_data)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "role": user.role,
            "full_name": user.full_name,
        }
        
    async def refresh_access_token(self, refresh_token: str) -> dict:
        """Validates a refresh token and returns a new access token."""
        try:
            payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            email: str = payload.get("email")
            if email is None:
                raise ValueError("Invalid refresh token")
        except jwt.JWTError:
            raise ValueError("Refresh token expired or invalid")

        user: SystemUser | None = await self.repository.get_by_email(email)
        if not user:
            raise PermissionError("User no longer exists.")

        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
        }
        
        new_access_token = _create_access_token(token_data)
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "role": user.role,
            "full_name": user.full_name,
        }

    async def create_system_user(self, data: SystemUserCreate) -> SystemUser:
        """SuperAdmin whitelists a new HR or Manager by email."""
        existing = await self.repository.get_by_email(data.email)
        if existing:
            raise ValueError(f"System user with email '{data.email}' already exists.")
        
        user = await self.repository.create_system_user(
            email=data.email,
            full_name=data.full_name,
            role=data.role,
        )
        await self.repository.db.commit()
        await self.repository.db.refresh(user)
        return user

    async def get_all_system_users(self) -> list[SystemUser]:
        return await self.repository.get_all()

    async def delete_system_user(self, email: str) -> None:
        user = await self.repository.get_by_email(email)
        if not user:
            raise ValueError(f"No system user found with email '{email}'.")
        await self.repository.delete_system_user(user)
        await self.repository.db.commit()
