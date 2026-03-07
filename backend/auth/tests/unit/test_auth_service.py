import pytest
from unittest.mock import AsyncMock, patch
from auth.service.auth import AuthService
from auth.models.system_user import SystemUser, SystemRole
import uuid

@pytest.fixture
def auth_service():
    mock_repo = AsyncMock()
    mock_repo.db = AsyncMock()
    return AuthService(repository=mock_repo)

@pytest.mark.asyncio
async def test_google_login_unregistered_user(auth_service):
    """Test that login fails if the user is not found in the database by email."""
    # 1. Arrange
    auth_service.repository.get_by_email.return_value = None
    
    # We mock Google's verification to return a fake email and sub
    with patch("auth.service.auth.id_token.verify_oauth2_token") as mock_google:
        mock_google.return_value = {"email": "unregistered@test.com", "sub": "google-sub-123"}
        
        # 2. Act & Assert
        with pytest.raises(PermissionError) as exc:
            await auth_service.google_login("fake_google_token")
        
        assert "not registered" in str(exc.value)
        auth_service.repository.get_by_email.assert_called_once_with("unregistered@test.com")

@pytest.mark.asyncio
async def test_google_login_success_first_time(auth_service):
    """Test successful login and linking of Google ID on first login."""
    # 1. Arrange
    mock_user = SystemUser(
        id=uuid.uuid4(),
        email="admin@test.com",
        full_name="Admin Admin",
        role=SystemRole.HR,
        google_id=None # Simulating first time login
    )
    auth_service.repository.get_by_email.return_value = mock_user
    
    with patch("auth.service.auth.id_token.verify_oauth2_token") as mock_google:
        mock_google.return_value = {"email": "admin@test.com", "sub": "google-sub-123"}
        
        # 2. Act
        result = await auth_service.google_login("valid_google_token")
        
        # 3. Assert
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"
        assert result["role"] == SystemRole.HR
        
        # Verify it linked the google ID and committed!
        auth_service.repository.link_google_id.assert_called_once_with(mock_user, "google-sub-123")
        auth_service.repository.db.commit.assert_called_once()
        auth_service.repository.db.refresh.assert_called_once_with(mock_user)

@pytest.mark.asyncio
async def test_refresh_token_expired(auth_service):
    """Test refresh token fails if the token is expired/invalid according to python-jose."""
    from jose import jwt
    with patch("auth.service.auth.jwt.decode") as mock_decode:
        # Mock jose throwing an error on decode
        mock_decode.side_effect = jwt.JWTError("Expired")
        
        with pytest.raises(ValueError) as exc:
            await auth_service.refresh_access_token("expired_refresh_token")
            
        assert "expired" in str(exc.value).lower()

@pytest.mark.asyncio
async def test_refresh_token_success(auth_service):
    """Test a valid refresh token generates a new access token for a valid user."""
    mock_user = SystemUser(id=uuid.uuid4(), email="admin@test.com", full_name="Admin", role=SystemRole.HR)
    auth_service.repository.get_by_email.return_value = mock_user
    
    with patch("auth.service.auth.jwt.decode") as mock_decode:
        mock_decode.return_value = {"email": "admin@test.com"}
        
        result = await auth_service.refresh_access_token("valid_refresh_token")
        
        assert "access_token" in result
        assert result["token_type"] == "bearer"
