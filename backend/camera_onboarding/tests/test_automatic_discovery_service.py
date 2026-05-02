import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from dataclasses import dataclass
from typing import List, Optional

# ---------------------------------------------------------------------------
# Minimal stubs so the module can be imported without the real dependencies
# ---------------------------------------------------------------------------

@dataclass
class FakeCamera:
    mac_address: str
    username: str
    password: str
    room: str = "room1"
    building: str = "building1"

@dataclass
class FakeCameraMetadata:
    mac_address: str
    ip_address: str
    rtsp_urls: List[str]
    username: str
    password: str
    room: str = "room1"
    building: str = "building1"

@dataclass
class CameraMetadataCreate:
    mac_address: str
    ip_address: str
    rtsp_urls: List[str]
    username: str
    password: str
    room: str
    building: str


# ---------------------------------------------------------------------------
# Import the class under test, patching heavy third-party imports
# ---------------------------------------------------------------------------

import sys
import types

# Stub out cv2 so OpenCV is not required in the test environment
cv2_stub = types.ModuleType("cv2")
cv2_stub.VideoCapture = MagicMock
cv2_stub.CAP_PROP_OPEN_TIMEOUT_MSEC = 0
cv2_stub.CAP_PROP_READ_TIMEOUT_MSEC = 1
cv2_stub.CAP_FFMPEG = 0
sys.modules.setdefault("cv2", cv2_stub)

# Now import the class directly (adjust the import path to your project layout)
# We recreate it here so the tests are self-contained.
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio


# ---------------------------------------------------------------------------
# Inline copy of the class under test (avoids import-path issues in CI)
# ---------------------------------------------------------------------------

import cv2  # will resolve to the stub above

class AutomaticDiscovery:
    def __init__(self, onvif_onboarding, non_onvif_onboarding, repo, metadata_service):
        self.onvif_onboarding = onvif_onboarding
        self.non_onvif_onboarding = non_onvif_onboarding
        self.repo = repo
        self.metadata_service = metadata_service

    async def discover_camera_ips(self):
        camera_ips = []
        onvif_ips = self.onvif_onboarding.get_camera_ip_addresses()
        db_cameras = await self.repo.get_all_cameras()
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(
                None,
                lambda c=camera: self.non_onvif_onboarding.get_camera_ip_addresses(
                    username=c.username, password=c.password
                ),
            )
            for camera in db_cameras
        ]
        results = await asyncio.gather(*tasks)
        for non_onvif_ips in results:
            camera_ips.extend(non_onvif_ips)
        camera_ips.extend(onvif_ips)
        return camera_ips

    def check_path(self, username, password, ip, path):
        url = f"rtsp://{username}:{password}@{ip}:554{path}"
        cap = cv2.VideoCapture()
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
        cap.open(url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            return False
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None or frame.size == 0:
            return False
        return True

    async def check_saved_camera_metadata_validity(self, ip):
        camera_metadata = await self.metadata_service.get_camera_metadata_by_ip(ip=ip)
        if self.check_path(
            username=camera_metadata.username,
            password=camera_metadata.password,
            ip=camera_metadata.ip_address,
            path=camera_metadata.rtsp_urls[0],
        ):
            return True
        return False

    async def discover_mac_address_and_rtsp_url(self, ip_address):
        mac_address = self.onvif_onboarding.discover_mac_address(ip=ip_address)
        if not mac_address:
            return [None, None]
        cameras = await self.repo.get_all_cameras()
        for camera in cameras:
            if camera.mac_address == mac_address:
                result_camera = camera
                rtsp_urls = self.onvif_onboarding.get_rtsp_url(
                    ip=ip_address,
                    username=result_camera.username,
                    password=result_camera.password,
                )
                return [mac_address, rtsp_urls]
        return [mac_address, None]

    async def sync_camera_metadata(self):
        camera_ips = await self.discover_camera_ips()
        cameras_metadata = await self.metadata_service.get_all_camera_metadata()
        saved_camera_metadata_ips = {camera.ip_address: camera for camera in cameras_metadata}
        for ip, camera in saved_camera_metadata_ips.items():
            if not await self.check_saved_camera_metadata_validity(ip=camera.ip_address):
                await self.metadata_service.delete_camera_metadata_by_ip(ip_address=camera.ip_address)
        for ip in camera_ips:
            if ip in saved_camera_metadata_ips:
                if await self.check_saved_camera_metadata_validity(ip=ip):
                    continue
                else:
                    await self.metadata_service.delete_camera_metadata_by_ip(ip_address=ip)
                    continue
            [mac_address, rtsp_urls] = await self.discover_mac_address_and_rtsp_url(ip_address=ip)
            if mac_address is None or rtsp_urls is None:
                continue
            existing = await self.metadata_service.get_camera_metadata_by_mac_address(mac_address=mac_address)
            if existing:
                continue
            camera_metadata = await self.repo.get_camera_by_mac_address(mac_address=mac_address)
            camera_metadata_instance = CameraMetadataCreate(
                mac_address=mac_address,
                ip_address=ip,
                rtsp_urls=rtsp_urls,
                username=camera_metadata.username,
                password=camera_metadata.password,
                room=camera_metadata.room,
                building=camera_metadata.building,
            )
            await self.metadata_service.create_camera_metadata_instance(camera_metadata_instance)
        return await self.metadata_service.get_all_camera_metadata()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_service(
    onvif_ips=None,
    db_cameras=None,
    non_onvif_ips=None,
    cameras_metadata=None,
):
    """Return an AutomaticDiscovery instance wired with configurable mocks."""
    onvif = MagicMock()
    onvif.get_camera_ip_addresses.return_value = onvif_ips or []

    non_onvif = MagicMock()
    non_onvif.get_camera_ip_addresses.return_value = non_onvif_ips or []

    repo = AsyncMock()
    repo.get_all_cameras.return_value = db_cameras or []

    metadata_svc = AsyncMock()
    metadata_svc.get_all_camera_metadata.return_value = cameras_metadata or []

    svc = AutomaticDiscovery(
        onvif_onboarding=onvif,
        non_onvif_onboarding=non_onvif,
        repo=repo,
        metadata_service=metadata_svc,
    )
    return svc, onvif, non_onvif, repo, metadata_svc


def make_camera(mac="AA:BB:CC:DD:EE:FF", username="admin", password="pass"):
    return FakeCamera(mac_address=mac, username=username, password=password)


def make_metadata(ip="192.168.1.10", mac="AA:BB:CC:DD:EE:FF", rtsp_urls=None):
    return FakeCameraMetadata(
        mac_address=mac,
        ip_address=ip,
        rtsp_urls=rtsp_urls or ["/stream1"],
        username="admin",
        password="pass",
    )


# ---------------------------------------------------------------------------
# Tests: discover_camera_ips
# ---------------------------------------------------------------------------

class TestDiscoverCameraIps:
    @pytest.mark.asyncio
    async def test_returns_onvif_and_non_onvif_ips(self):
        camera = make_camera()
        svc, onvif, non_onvif, repo, _ = make_service(
            onvif_ips=["10.0.0.1"],
            db_cameras=[camera],
            non_onvif_ips=["10.0.0.2"],
        )
        result = await svc.discover_camera_ips()
        assert "10.0.0.1" in result
        assert "10.0.0.2" in result

    @pytest.mark.asyncio
    async def test_non_onvif_called_per_db_camera_credentials(self):
        cam1 = make_camera(mac="AA:AA:AA:AA:AA:AA", username="user1", password="p1")
        cam2 = make_camera(mac="BB:BB:BB:BB:BB:BB", username="user2", password="p2")
        svc, _, non_onvif, repo, _ = make_service(db_cameras=[cam1, cam2])
        await svc.discover_camera_ips()
        calls = non_onvif.get_camera_ip_addresses.call_args_list
        assert len(calls) == 2
        called_creds = {(c.kwargs["username"], c.kwargs["password"]) for c in calls}
        assert called_creds == {("user1", "p1"), ("user2", "p2")}

    @pytest.mark.asyncio
    async def test_empty_when_no_cameras_or_ips(self):
        svc, _, _, _, _ = make_service()
        result = await svc.discover_camera_ips()
        assert result == []

    @pytest.mark.asyncio
    async def test_deduplication_not_applied_raw_list_returned(self):
        """discover_camera_ips returns raw combined list (no dedup logic)."""
        svc, _, _, _, _ = make_service(onvif_ips=["10.0.0.1"], non_onvif_ips=["10.0.0.1"])
        # One db camera to trigger non-onvif lookup
        svc.repo.get_all_cameras.return_value = [make_camera()]
        result = await svc.discover_camera_ips()
        assert result.count("10.0.0.1") == 2


# ---------------------------------------------------------------------------
# Tests: check_path
# ---------------------------------------------------------------------------

class TestCheckPath:
    def _make_cap(self, is_opened=True, read_ret=True, frame_size=1000):
        cap = MagicMock()
        cap.isOpened.return_value = is_opened
        frame = MagicMock()
        frame.size = frame_size
        cap.read.return_value = (read_ret, frame if read_ret else None)
        return cap

    def test_returns_true_when_stream_valid(self):
        svc, _, _, _, _ = make_service()
        with patch("cv2.VideoCapture", return_value=self._make_cap()):
            assert svc.check_path("admin", "pass", "10.0.0.1", "/stream1") is True

    def test_returns_false_when_cap_not_opened(self):
        svc, _, _, _, _ = make_service()
        with patch("cv2.VideoCapture", return_value=self._make_cap(is_opened=False)):
            assert svc.check_path("admin", "pass", "10.0.0.1", "/stream1") is False

    def test_returns_false_when_read_fails(self):
        svc, _, _, _, _ = make_service()
        with patch("cv2.VideoCapture", return_value=self._make_cap(read_ret=False)):
            assert svc.check_path("admin", "pass", "10.0.0.1", "/stream1") is False

    def test_returns_false_when_frame_empty(self):
        svc, _, _, _, _ = make_service()
        with patch("cv2.VideoCapture", return_value=self._make_cap(frame_size=0)):
            assert svc.check_path("admin", "pass", "10.0.0.1", "/stream1") is False

    def test_builds_correct_rtsp_url(self):
        svc, _, _, _, _ = make_service()
        cap = self._make_cap()
        with patch("cv2.VideoCapture", return_value=cap) as mock_vc:
            svc.check_path("user", "secret", "192.168.1.5", "/cam/stream")
            # The URL is passed to cap.open
            cap.open.assert_called_once()
            url_arg = cap.open.call_args[0][0]
            assert url_arg == "rtsp://user:secret@192.168.1.5:554/cam/stream"


# ---------------------------------------------------------------------------
# Tests: check_saved_camera_metadata_validity
# ---------------------------------------------------------------------------

class TestCheckSavedCameraMetadataValidity:
    @pytest.mark.asyncio
    async def test_returns_true_when_path_valid(self):
        svc, _, _, _, metadata_svc = make_service()
        metadata_svc.get_camera_metadata_by_ip.return_value = make_metadata()
        svc.check_path = MagicMock(return_value=True)
        result = await svc.check_saved_camera_metadata_validity(ip="192.168.1.10")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_path_invalid(self):
        svc, _, _, _, metadata_svc = make_service()
        metadata_svc.get_camera_metadata_by_ip.return_value = make_metadata()
        svc.check_path = MagicMock(return_value=False)
        result = await svc.check_saved_camera_metadata_validity(ip="192.168.1.10")
        assert result is False

    @pytest.mark.asyncio
    async def test_passes_correct_args_to_check_path(self):
        svc, _, _, _, metadata_svc = make_service()
        meta = make_metadata(ip="10.10.10.10", rtsp_urls=["/live"])
        metadata_svc.get_camera_metadata_by_ip.return_value = meta
        svc.check_path = MagicMock(return_value=True)
        await svc.check_saved_camera_metadata_validity(ip="10.10.10.10")
        svc.check_path.assert_called_once_with(
            username=meta.username,
            password=meta.password,
            ip=meta.ip_address,
            path="/live",
        )


# ---------------------------------------------------------------------------
# Tests: discover_mac_address_and_rtsp_url
# ---------------------------------------------------------------------------

class TestDiscoverMacAddressAndRtspUrl:
    @pytest.mark.asyncio
    async def test_returns_none_none_when_no_mac(self):
        svc, onvif, _, repo, _ = make_service()
        onvif.discover_mac_address.return_value = None
        result = await svc.discover_mac_address_and_rtsp_url("10.0.0.1")
        assert result == [None, None]

    @pytest.mark.asyncio
    async def test_returns_mac_and_rtsp_when_camera_found(self):
        camera = make_camera(mac="AA:BB:CC:DD:EE:FF")
        svc, onvif, _, repo, _ = make_service(db_cameras=[camera])
        onvif.discover_mac_address.return_value = "AA:BB:CC:DD:EE:FF"
        onvif.get_rtsp_url.return_value = ["/stream1"]
        result = await svc.discover_mac_address_and_rtsp_url("10.0.0.1")
        assert result == ["AA:BB:CC:DD:EE:FF", ["/stream1"]]

    @pytest.mark.asyncio
    async def test_returns_mac_and_none_when_no_matching_camera(self):
        camera = make_camera(mac="FF:FF:FF:FF:FF:FF")
        svc, onvif, _, repo, _ = make_service(db_cameras=[camera])
        onvif.discover_mac_address.return_value = "AA:BB:CC:DD:EE:FF"
        result = await svc.discover_mac_address_and_rtsp_url("10.0.0.1")
        assert result == ["AA:BB:CC:DD:EE:FF", None]

    @pytest.mark.asyncio
    async def test_rtsp_url_fetched_with_correct_credentials(self):
        camera = make_camera(mac="AA:BB:CC:DD:EE:FF", username="admin", password="1234")
        svc, onvif, _, repo, _ = make_service(db_cameras=[camera])
        onvif.discover_mac_address.return_value = "AA:BB:CC:DD:EE:FF"
        onvif.get_rtsp_url.return_value = ["/stream1"]
        await svc.discover_mac_address_and_rtsp_url("10.0.0.5")
        onvif.get_rtsp_url.assert_called_once_with(
            ip="10.0.0.5", username="admin", password="1234"
        )


# ---------------------------------------------------------------------------
# Tests: sync_camera_metadata
# ---------------------------------------------------------------------------

class TestSyncCameraMetadata:
    @pytest.mark.asyncio
    async def test_creates_metadata_for_new_valid_ip(self):
        """A freshly discovered IP with a resolvable MAC creates a metadata record."""
        camera = make_camera(mac="AA:BB:CC:DD:EE:FF")
        svc, onvif, _, repo, metadata_svc = make_service(
            onvif_ips=["10.0.0.1"],
            db_cameras=[camera],
            cameras_metadata=[],
        )
        onvif.discover_mac_address.return_value = "AA:BB:CC:DD:EE:FF"
        onvif.get_rtsp_url.return_value = ["/stream1"]
        metadata_svc.get_camera_metadata_by_mac_address.return_value = None
        repo.get_camera_by_mac_address.return_value = camera
        metadata_svc.get_all_camera_metadata.return_value = []

        # non_onvif returns nothing; only onvif IP matters
        svc.non_onvif_onboarding.get_camera_ip_addresses.return_value = []

        await svc.sync_camera_metadata()

        metadata_svc.create_camera_metadata_instance.assert_called_once()
        created = metadata_svc.create_camera_metadata_instance.call_args[0][0]
        assert created.ip_address == "10.0.0.1"
        assert created.mac_address == "AA:BB:CC:DD:EE:FF"
        assert created.rtsp_urls == ["/stream1"]

    @pytest.mark.asyncio
    async def test_skips_ip_when_mac_is_none(self):
        svc, onvif, _, repo, metadata_svc = make_service(
            onvif_ips=["10.0.0.1"],
            cameras_metadata=[],
        )
        onvif.discover_mac_address.return_value = None
        svc.non_onvif_onboarding.get_camera_ip_addresses.return_value = []

        await svc.sync_camera_metadata()
        metadata_svc.create_camera_metadata_instance.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_ip_when_rtsp_urls_are_none(self):
        camera = make_camera(mac="AA:BB:CC:DD:EE:FF")
        svc, onvif, _, repo, metadata_svc = make_service(
            onvif_ips=["10.0.0.1"],
            db_cameras=[camera],
            cameras_metadata=[],
        )
        onvif.discover_mac_address.return_value = "AA:BB:CC:DD:EE:FF"
        # No matching camera in repo → rtsp_urls will be None
        repo.get_all_cameras.return_value = []
        svc.non_onvif_onboarding.get_camera_ip_addresses.return_value = []

        await svc.sync_camera_metadata()
        metadata_svc.create_camera_metadata_instance.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_ip_when_metadata_already_exists_for_mac(self):
        camera = make_camera(mac="AA:BB:CC:DD:EE:FF")
        svc, onvif, _, repo, metadata_svc = make_service(
            onvif_ips=["10.0.0.1"],
            db_cameras=[camera],
            cameras_metadata=[],
        )
        onvif.discover_mac_address.return_value = "AA:BB:CC:DD:EE:FF"
        onvif.get_rtsp_url.return_value = ["/stream1"]
        # Simulate pre-existing metadata for this MAC
        metadata_svc.get_camera_metadata_by_mac_address.return_value = make_metadata()
        svc.non_onvif_onboarding.get_camera_ip_addresses.return_value = []

        await svc.sync_camera_metadata()
        metadata_svc.create_camera_metadata_instance.assert_not_called()

    @pytest.mark.asyncio
    async def test_deletes_invalid_saved_metadata(self):
        """Saved metadata entries whose stream is no longer reachable get deleted."""
        stale = make_metadata(ip="10.0.0.99")
        svc, _, _, _, metadata_svc = make_service(
            onvif_ips=[],
            cameras_metadata=[stale],
        )
        svc.check_path = MagicMock(return_value=False)
        metadata_svc.get_camera_metadata_by_ip.return_value = stale
        svc.non_onvif_onboarding.get_camera_ip_addresses.return_value = []

        await svc.sync_camera_metadata()
        metadata_svc.delete_camera_metadata_by_ip.assert_called_with(ip_address="10.0.0.99")

    @pytest.mark.asyncio
    async def test_keeps_valid_saved_metadata(self):
        """Saved metadata entries with a live stream are not deleted."""
        valid_meta = make_metadata(ip="10.0.0.50")
        svc, onvif, _, repo, metadata_svc = make_service(
            onvif_ips=["10.0.0.50"],
            cameras_metadata=[valid_meta],
        )
        svc.check_path = MagicMock(return_value=True)
        metadata_svc.get_camera_metadata_by_ip.return_value = valid_meta
        svc.non_onvif_onboarding.get_camera_ip_addresses.return_value = []

        await svc.sync_camera_metadata()
        metadata_svc.delete_camera_metadata_by_ip.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_final_metadata_list(self):
        final = [make_metadata()]
        svc, _, _, _, metadata_svc = make_service(cameras_metadata=[])
        metadata_svc.get_all_camera_metadata.return_value = final
        svc.non_onvif_onboarding.get_camera_ip_addresses.return_value = []
        # No saved metadata → no validity checks needed; just confirm return value
        svc.check_path = MagicMock(return_value=True)

        result = await svc.sync_camera_metadata()
        assert result == final

    @pytest.mark.asyncio
    async def test_deletes_then_skips_discovered_ip_with_invalid_saved_stream(self):
        """
        If a discovered IP is already in saved metadata but the stream is dead,
        the entry is deleted and no new record is created (the IP is skipped).
        """
        stale = make_metadata(ip="10.0.0.1")
        svc, onvif, _, repo, metadata_svc = make_service(
            onvif_ips=["10.0.0.1"],
            cameras_metadata=[stale],
        )
        svc.check_path = MagicMock(return_value=False)
        metadata_svc.get_camera_metadata_by_ip.return_value = stale
        svc.non_onvif_onboarding.get_camera_ip_addresses.return_value = []

        await svc.sync_camera_metadata()

        # Should have been deleted (called at least once for this IP)
        delete_calls = [
            c for c in metadata_svc.delete_camera_metadata_by_ip.call_args_list
            if c.kwargs.get("ip_address") == "10.0.0.1"
        ]
        assert delete_calls
        metadata_svc.create_camera_metadata_instance.assert_not_called()