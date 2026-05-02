import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
from datetime import datetime

from camera_onboarding.service.camera import CameraService
from camera_onboarding.schemas.camera import CameraCreate, CameraResponse
from camera_onboarding.utils.exceptions import CameraNotFound


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def mock_repository(mock_db):
    repo = AsyncMock()
    repo.db = mock_db
    return repo


@pytest.fixture
def service(mock_repository):
    return CameraService(repository=mock_repository)


@pytest.fixture
def camera_id() -> UUID:
    return uuid4()


@pytest.fixture
def camera_create_payload() -> CameraCreate:
    return CameraCreate(
        room="Front Door",
        building="Main Building",
        mac_address="AA:BB:CC:DD:EE:FF",
        username="admin",
        password="password123"
    )

@pytest.fixture
def mock_camera_instance(camera_id):
    camera = MagicMock()
    camera.id = camera_id
    camera.room = "Front Door"
    camera.building = "Main Building"
    camera.mac_address = "AA:BB:CC:DD:EE:FF"
    camera.username = "admin"
    camera.password = "password123"
    camera.date_created = datetime.utcnow()
    return camera

# ---------------------------------------------------------------------------
# create_camera_instance
# ---------------------------------------------------------------------------

class TestCreateCameraInstance:
    async def test_creates_and_returns_camera(
        self, service, mock_repository, mock_db, camera_create_payload, mock_camera_instance
    ):
        mock_repository.create_camera_instance.return_value = mock_camera_instance

        result = await service.create_camera_instance(camera=camera_create_payload)

        mock_repository.create_camera_instance.assert_awaited_once_with(camera=camera_create_payload)
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once_with(mock_camera_instance)
        assert result == mock_camera_instance

    async def test_rolls_back_on_repository_error(
        self, service, mock_repository, mock_db, camera_create_payload
    ):
        mock_repository.create_camera_instance.side_effect = Exception("DB error")

        with pytest.raises(Exception, match="DB error"):
            await service.create_camera_instance(camera=camera_create_payload)

        mock_db.rollback.assert_awaited_once()
        mock_db.commit.assert_not_awaited()

    async def test_rolls_back_on_commit_error(
        self, service, mock_repository, mock_db, camera_create_payload, mock_camera_instance
    ):
        mock_repository.create_camera_instance.return_value = mock_camera_instance
        mock_db.commit.side_effect = Exception("Commit failed")

        with pytest.raises(Exception, match="Commit failed"):
            await service.create_camera_instance(camera=camera_create_payload)

        mock_db.rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_all_cameras
# ---------------------------------------------------------------------------

class TestGetAllCameras:
    async def test_returns_list_of_cameras(self, service, mock_repository, mock_camera_instance):
        mock_repository.get_all_cameras.return_value = [mock_camera_instance]

        result = await service.get_all_cameras()

        mock_repository.get_all_cameras.assert_awaited_once()
        assert result == [mock_camera_instance]

    async def test_returns_empty_list_when_no_cameras(self, service, mock_repository):
        mock_repository.get_all_cameras.return_value = []

        result = await service.get_all_cameras()

        assert result == []

    async def test_raises_on_repository_error(self, service, mock_repository):
        mock_repository.get_all_cameras.side_effect = Exception("DB error")

        with pytest.raises(Exception, match="DB error"):
            await service.get_all_cameras()


# ---------------------------------------------------------------------------
# delete_camera
# ---------------------------------------------------------------------------

class TestDeleteCamera:
    async def test_deletes_camera_successfully(
        self, service, mock_repository, mock_db, camera_id, mock_camera_instance
    ):
        mock_repository.get_camera_by_id.return_value = mock_camera_instance

        await service.delete_camera(id=camera_id)

        mock_repository.get_camera_by_id.assert_awaited_once_with(id=camera_id)
        mock_repository.delete_camera.assert_awaited_once_with(camera=mock_camera_instance)
        mock_db.commit.assert_awaited_once()

    async def test_raises_camera_not_found_when_missing(
        self, service, mock_repository, mock_db, camera_id
    ):
        mock_repository.get_camera_by_id.return_value = None

        with pytest.raises(CameraNotFound):
            await service.delete_camera(id=camera_id)

        mock_repository.delete_camera.assert_not_awaited()
        mock_db.rollback.assert_awaited_once()

    async def test_rolls_back_on_delete_error(
        self, service, mock_repository, mock_db, camera_id, mock_camera_instance
    ):
        mock_repository.get_camera_by_id.return_value = mock_camera_instance
        mock_repository.delete_camera.side_effect = Exception("Delete failed")

        with pytest.raises(Exception, match="Delete failed"):
            await service.delete_camera(id=camera_id)

        mock_db.rollback.assert_awaited_once()
        mock_db.commit.assert_not_awaited()

    async def test_rolls_back_on_commit_error(
        self, service, mock_repository, mock_db, camera_id, mock_camera_instance
    ):
        mock_repository.get_camera_by_id.return_value = mock_camera_instance
        mock_db.commit.side_effect = Exception("Commit failed")

        with pytest.raises(Exception, match="Commit failed"):
            await service.delete_camera(id=camera_id)

        mock_db.rollback.assert_awaited_once()