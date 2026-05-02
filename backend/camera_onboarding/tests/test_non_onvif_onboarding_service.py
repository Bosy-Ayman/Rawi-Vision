import pytest
from unittest.mock import MagicMock, patch, call
from concurrent.futures import Future
import sys
import types

# Stub: onboarding_interface
onboarding_pkg = types.ModuleType("onboarding_interface")
class OnboardingInterface: pass
onboarding_pkg.OnboardingInterface = OnboardingInterface
sys.modules.setdefault("onboarding_interface", onboarding_pkg)

# Stub: config
config_mod = types.ModuleType("config")
class Config:
    RTSP_URLS = ["live/ch0", "stream1", "h264/ch1/main/av_stream"]
config_mod.Config = Config
sys.modules.setdefault("config", config_mod)

# Stub: nmap
nmap_mod = types.ModuleType("nmap")
nmap_mod.PortScanner = MagicMock()
sys.modules.setdefault("nmap", nmap_mod)

# Stub: cv2
cv2_mod = types.ModuleType("cv2")
cv2_mod.VideoCapture = MagicMock()
sys.modules.setdefault("cv2", cv2_mod)


from camera_onboarding.service.non_onvif_onboarding import NonOnvifOnboarding  


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_cap(opened: bool, frame_read: bool):
    """Return a mock cv2.VideoCapture with configurable behaviour."""
    cap = MagicMock()
    cap.isOpened.return_value = opened
    cap.read.return_value = (frame_read, MagicMock() if frame_read else None)
    return cap


# ---------------------------------------------------------------------------
# _try_rtsp_urls
# ---------------------------------------------------------------------------

class TestTryRtspUrls:

    def test_returns_true_when_stream_opens_and_frame_reads(self):
        onboarding = NonOnvifOnboarding()
        with patch("cv2.VideoCapture", return_value=make_cap(True, True)):
            assert onboarding._try_rtsp_urls("192.168.1.10", "admin", "pass", "stream1") is True

    def test_returns_false_when_cap_not_opened(self):
        onboarding = NonOnvifOnboarding()
        with patch("cv2.VideoCapture", return_value=make_cap(False, False)):
            assert onboarding._try_rtsp_urls("192.168.1.10", "admin", "pass", "stream1") is False

    def test_returns_false_when_frame_not_readable(self):
        onboarding = NonOnvifOnboarding()
        with patch("cv2.VideoCapture", return_value=make_cap(True, False)):
            assert onboarding._try_rtsp_urls("192.168.1.10", "admin", "pass", "stream1") is False

    def test_constructs_correct_rtsp_url(self):
        onboarding = NonOnvifOnboarding()
        cap = make_cap(True, True)
        with patch("cv2.VideoCapture", return_value=cap) as mock_vc:
            onboarding._try_rtsp_urls("10.0.0.1", "user", "secret", "live/ch0")
            mock_vc.assert_called_once_with("rtsp://user:secret@10.0.0.1:554/live/ch0")

    def test_releases_cap_on_success(self):
        onboarding = NonOnvifOnboarding()
        cap = make_cap(True, True)
        with patch("cv2.VideoCapture", return_value=cap):
            onboarding._try_rtsp_urls("10.0.0.1", "u", "p", "stream")
        cap.release.assert_called_once()

    def test_releases_cap_on_failed_read(self):
        onboarding = NonOnvifOnboarding()
        cap = make_cap(True, False)
        with patch("cv2.VideoCapture", return_value=cap):
            onboarding._try_rtsp_urls("10.0.0.1", "u", "p", "stream")
        cap.release.assert_called_once()


# ---------------------------------------------------------------------------
# is_camera
# ---------------------------------------------------------------------------

class TestIsCamera:

    def test_returns_false_when_all_paths_fail(self):
        onboarding = NonOnvifOnboarding()
        with patch.object(onboarding, "_try_rtsp_urls", return_value=False):
            assert onboarding.is_camera("192.168.1.5", "admin", "pass") is False

    def test_returns_true_when_first_path_succeeds(self):
        onboarding = NonOnvifOnboarding()
        with patch.object(onboarding, "_try_rtsp_urls", return_value=True):
            assert onboarding.is_camera("192.168.1.5", "admin", "pass") is True


# ---------------------------------------------------------------------------
# get_camera_ip_addresses
# ---------------------------------------------------------------------------

class TestGetCameraIpAddresses:

    def _make_nm_scanner(self, hosts_data: dict):
        """
        hosts_data: { "192.168.1.x": { "tcp": { 554: ..., 80: ... } } }
        """
        nm = MagicMock()
        nm.all_hosts.return_value = list(hosts_data.keys())
        nm.__getitem__ = lambda self_, key: hosts_data[key]
        return nm

    def test_camera_with_rtsp_port_is_discovered(self):
        onboarding = NonOnvifOnboarding()
        hosts = {
            "192.168.1.10": {"tcp": {554: {}, 80: {}}},
        }
        nm = self._make_nm_scanner(hosts)
        with patch("nmap.PortScanner", return_value=nm):
            with patch.object(onboarding, "is_camera", return_value=True):
                result = onboarding.get_camera_ip_addresses("admin", "pass")
        assert "192.168.1.10" in result

    def test_host_without_rtsp_or_http_is_excluded(self):
        onboarding = NonOnvifOnboarding()
        hosts = {
            "192.168.1.20": {"tcp": {22: {}}},  # only SSH
        }
        nm = self._make_nm_scanner(hosts)
        with patch("nmap.PortScanner", return_value=nm):
            with patch.object(onboarding, "is_camera", return_value=True):
                result = onboarding.get_camera_ip_addresses("admin", "pass")
        assert "192.168.1.20" not in result

    def test_host_without_tcp_key_is_excluded(self):
        onboarding = NonOnvifOnboarding()
        hosts = {
            "192.168.1.30": {},  # no 'tcp' key
        }
        nm = self._make_nm_scanner(hosts)
        with patch("nmap.PortScanner", return_value=nm):
            with patch.object(onboarding, "is_camera", return_value=True):
                result = onboarding.get_camera_ip_addresses("admin", "pass")
        assert "192.168.1.30" not in result

    def test_non_camera_host_excluded_even_with_rtsp_port(self):
        onboarding = NonOnvifOnboarding()
        hosts = {
            "192.168.1.40": {"tcp": {554: {}}},
        }
        nm = self._make_nm_scanner(hosts)
        with patch("nmap.PortScanner", return_value=nm):
            with patch.object(onboarding, "is_camera", return_value=False):
                result = onboarding.get_camera_ip_addresses("admin", "pass")
        assert result == []

    def test_multiple_cameras_all_returned(self):
        onboarding = NonOnvifOnboarding()
        hosts = {
            "192.168.1.10": {"tcp": {554: {}}},
            "192.168.1.11": {"tcp": {8554: {}}},
            "192.168.1.12": {"tcp": {80: {}}},
        }
        nm = self._make_nm_scanner(hosts)
        with patch("nmap.PortScanner", return_value=nm):
            with patch.object(onboarding, "is_camera", return_value=True):
                result = onboarding.get_camera_ip_addresses("admin", "pass")
        assert set(result) == {"192.168.1.10", "192.168.1.11", "192.168.1.12"}


# ---------------------------------------------------------------------------
# discover_camera_mac_address
# ---------------------------------------------------------------------------

class TestDiscoverCameraMacAddress:

    ARP_OUTPUT = (
        "Address                  HWtype  HWaddress           Flags Mask\n"
        "192.168.1.10             ether   aa:bb:cc:dd:ee:ff   C\n"
        "192.168.1.20             ether   11:22:33:44:55:66   C\n"
    )

    def test_returns_correct_mac_for_ip(self):
        onboarding = NonOnvifOnboarding()
        with patch("subprocess.run"), \
             patch("subprocess.check_output", return_value=self.ARP_OUTPUT.encode()):
            mac = onboarding.discover_camera_mac_address("192.168.1.10", "admin", "pass")
        assert mac == "aa:bb:cc:dd:ee:ff"

    def test_pings_ip_before_reading_arp(self):
        onboarding = NonOnvifOnboarding()
        with patch("subprocess.run") as mock_run, \
             patch("subprocess.check_output", return_value=self.ARP_OUTPUT.encode()):
            onboarding.discover_camera_mac_address("192.168.1.10", "admin", "pass")
        mock_run.assert_called_once_with(
            ["ping", "-c", "1", "192.168.1.10"], stdout=pytest.approx(subprocess.DEVNULL, abs=0)
        )

    def test_raises_on_subprocess_error(self):
        onboarding = NonOnvifOnboarding()
        with patch("subprocess.run", side_effect=OSError("ping failed")):
            with pytest.raises(OSError):
                onboarding.discover_camera_mac_address("192.168.1.99", "admin", "pass")


import subprocess  # needed by the ping assertion above


# ---------------------------------------------------------------------------
# get_rtsp_url
# ---------------------------------------------------------------------------

class TestGetRtspUrl:

    def test_returns_empty_list_when_no_paths_work(self):
        onboarding = NonOnvifOnboarding()
        with patch("cv2.VideoCapture", return_value=make_cap(False, False)):
            urls = onboarding.get_rtsp_url("192.168.1.10", "admin", "pass")
        assert urls == []

    def test_url_format_is_correct(self):
        onboarding = NonOnvifOnboarding()
        with patch("cv2.VideoCapture", return_value=make_cap(True, True)):
            urls = onboarding.get_rtsp_url("10.0.0.5", "user", "pw")
        for url in urls:
            assert url.startswith("rtsp://user:pw@10.0.0.5:554")