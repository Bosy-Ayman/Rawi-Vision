import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from camera_onboarding.service.metadata import CameraMetadataService 
from camera_onboarding.utils.exceptions import CameraNotFound


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """Async mock for the SQLAlchemy session attached to the repository."""
    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def mock_repository(mock_db):
    """Mock CameraMetadataRepository with all async methods pre-wired."""
    repo = MagicMock()
    repo.db = mock_db
    repo.create_camera_metadata_instance = AsyncMock()
    repo.get_camera_metadata_by_ip = AsyncMock()
    repo.get_camera_metadata_by_mac_address = AsyncMock()
    repo.get_all_camera_metadata = AsyncMock()
    repo.delete_camera = AsyncMock()
    return repo


@pytest.fixture
def service(mock_repository):
    return CameraMetadataService(repository=mock_repository)


# ---------------------------------------------------------------------------
# Helpers / shared test data
# ---------------------------------------------------------------------------

def make_camera(ip="192.168.1.1", mac="AA:BB:CC:DD:EE:FF"):
    camera = MagicMock()
    camera.ip = ip
    camera.mac_address = mac
    return camera


# ---------------------------------------------------------------------------
# create_camera_metadata_instance
# ---------------------------------------------------------------------------

class TestCreateCameraMetadataInstance:
    @pytest.mark.asyncio
    async def test_creates_and_returns_instance(self, service, mock_repository, mock_db):
        camera_input = MagicMock()
        new_camera = make_camera()
        mock_repository.create_camera_metadata_instance.return_value = new_camera

        result = await service.create_camera_metadata_instance(camera_input)

        mock_repository.create_camera_metadata_instance.assert_awaited_once_with(camera=camera_input)
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once_with(new_camera)
        assert result is new_camera

    @pytest.mark.asyncio
    async def test_rolls_back_and_re_raises_on_error(self, service, mock_repository, mock_db):
        mock_repository.create_camera_metadata_instance.side_effect = SQLAlchemyError("db error")

        with pytest.raises(SQLAlchemyError):
            await service.create_camera_metadata_instance(MagicMock())

        mock_db.rollback.assert_awaited_once()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rolls_back_when_commit_fails(self, service, mock_repository, mock_db):
        mock_repository.create_camera_metadata_instance.return_value = make_camera()
        mock_db.commit.side_effect = SQLAlchemyError("commit failed")

        with pytest.raises(SQLAlchemyError):
            await service.create_camera_metadata_instance(MagicMock())

        mock_db.rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_camera_metadata_by_ip
# ---------------------------------------------------------------------------

class TestGetCameraMetadataByIp:
    @pytest.mark.asyncio
    async def test_returns_camera_when_found(self, service, mock_repository):
        camera = make_camera(ip="10.0.0.5")
        mock_repository.get_camera_metadata_by_ip.return_value = camera

        result = await service.get_camera_metadata_by_ip("10.0.0.5")

        mock_repository.get_camera_metadata_by_ip.assert_awaited_once_with(ip="10.0.0.5")
        assert result is camera

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, service, mock_repository):
        mock_repository.get_camera_metadata_by_ip.return_value = None

        result = await service.get_camera_metadata_by_ip("10.0.0.99")

        assert result is None

    @pytest.mark.asyncio
    async def test_re_raises_repository_exception(self, service, mock_repository):
        mock_repository.get_camera_metadata_by_ip.side_effect = RuntimeError("connection error")

        with pytest.raises(RuntimeError, match="connection error"):
            await service.get_camera_metadata_by_ip("10.0.0.5")


# ---------------------------------------------------------------------------
# get_camera_metadata_by_mac_address
# ---------------------------------------------------------------------------

class TestGetCameraMetadataByMacAddress:
    @pytest.mark.asyncio
    async def test_returns_camera_when_found(self, service, mock_repository):
        camera = make_camera(mac="11:22:33:44:55:66")
        mock_repository.get_camera_metadata_by_mac_address.return_value = camera

        result = await service.get_camera_metadata_by_mac_address("11:22:33:44:55:66")

        mock_repository.get_camera_metadata_by_mac_address.assert_awaited_once_with(
            mac_address="11:22:33:44:55:66"
        )
        assert result is camera

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, service, mock_repository):
        mock_repository.get_camera_metadata_by_mac_address.return_value = None

        result = await service.get_camera_metadata_by_mac_address("FF:FF:FF:FF:FF:FF")

        assert result is None

    @pytest.mark.asyncio
    async def test_re_raises_repository_exception(self, service, mock_repository):
        mock_repository.get_camera_metadata_by_mac_address.side_effect = ValueError("bad mac")

        with pytest.raises(ValueError, match="bad mac"):
            await service.get_camera_metadata_by_mac_address("ZZ:ZZ")


# ---------------------------------------------------------------------------
# get_all_camera_metadata
# ---------------------------------------------------------------------------

class TestGetAllCameraMetadata:
    @pytest.mark.asyncio
    async def test_returns_list_of_cameras(self, service, mock_repository):
        cameras = [make_camera("192.168.1.1"), make_camera("192.168.1.2")]
        mock_repository.get_all_camera_metadata.return_value = cameras

        result = await service.get_all_camera_metadata()

        mock_repository.get_all_camera_metadata.assert_awaited_once()
        assert result == cameras

    @pytest.mark.asyncio
    async def test_returns_empty_list(self, service, mock_repository):
        mock_repository.get_all_camera_metadata.return_value = []

        result = await service.get_all_camera_metadata()

        assert result == []

    @pytest.mark.asyncio
    async def test_re_raises_repository_exception(self, service, mock_repository):
        mock_repository.get_all_camera_metadata.side_effect = SQLAlchemyError("timeout")

        with pytest.raises(SQLAlchemyError):
            await service.get_all_camera_metadata()


# ---------------------------------------------------------------------------
# delete_camera_metadata_by_ip
# ---------------------------------------------------------------------------

class TestDeleteCameraMetadataByIp:
    @pytest.mark.asyncio
    async def test_deletes_existing_camera(self, service, mock_repository, mock_db):
        camera = make_camera(ip="192.168.1.10")
        mock_repository.get_camera_metadata_by_ip.return_value = camera

        await service.delete_camera_metadata_by_ip("192.168.1.10")

        mock_repository.get_camera_metadata_by_ip.assert_awaited_once_with(ip="192.168.1.10")
        mock_repository.delete_camera.assert_awaited_once_with(camera=camera)
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_camera_not_found_when_missing(self, service, mock_repository, mock_db):
        mock_repository.get_camera_metadata_by_ip.return_value = None

        with pytest.raises(CameraNotFound):
            await service.delete_camera_metadata_by_ip("0.0.0.0")

        mock_repository.delete_camera.assert_not_awaited()
        mock_db.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rolls_back_and_re_raises_when_delete_fails(self, service, mock_repository, mock_db):
        camera = make_camera()
        mock_repository.get_camera_metadata_by_ip.return_value = camera
        mock_repository.delete_camera.side_effect = SQLAlchemyError("delete failed")

        with pytest.raises(SQLAlchemyError):
            await service.delete_camera_metadata_by_ip(camera.ip)

        mock_db.rollback.assert_awaited_once()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rolls_back_when_commit_fails(self, service, mock_repository, mock_db):
        camera = make_camera()
        mock_repository.get_camera_metadata_by_ip.return_value = camera
        mock_db.commit.side_effect = SQLAlchemyError("commit failed")

        with pytest.raises(SQLAlchemyError):
            await service.delete_camera_metadata_by_ip(camera.ip)

        mock_db.rollback.assert_awaited_once()