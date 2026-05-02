import pytest
from fastapi import HTTPException
from auth.dependencies import require_hr, require_manager
from auth.models.system_user import SystemUser, SystemRole

@pytest.mark.asyncio
async def test_require_hr_privilege_escalation_blocked():
    """Manager trying to hit an HR-only endpoint should be blocked."""
    mock_manager = SystemUser(email="manager@test.com", role=SystemRole.MANAGER)
    
    with pytest.raises(HTTPException) as exc_info:
        await require_hr(current_user=mock_manager)

    assert exc_info.value.status_code == 403
    assert "HR personnel only" in str(exc_info.value.detail)

@pytest.mark.asyncio
async def test_require_hr_success():
    """HR role should pass perfectly."""
    mock_hr = SystemUser(email="hr@test.com", role=SystemRole.HR)
    result = await require_hr(current_user=mock_hr)
    
    assert result == mock_hr

@pytest.mark.asyncio
async def test_require_manager_success():
    """Manager should be able to hit a Manager endpoint."""
    mock_manager = SystemUser(email="manager@test.com", role=SystemRole.MANAGER)
    result = await require_manager(current_user=mock_manager)
    
    assert result == mock_manager

@pytest.mark.asyncio
async def test_require_manager_allows_hr():
    """HR should also be able to hit Manager endpoints (since HR > Manager)."""
    mock_hr = SystemUser(email="hr@test.com", role=SystemRole.HR)
    result = await require_manager(current_user=mock_hr)
    
    assert result == mock_hr
