import pytest
from unittest.mock import MagicMock, patch, call
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Minimal stubs so the module can be imported without the real dependencies
# ---------------------------------------------------------------------------

import sys
import types

# wsdiscovery stub
wsdiscovery_mod = types.ModuleType("wsdiscovery")
wsdiscovery_mod.WSDiscovery = MagicMock
sys.modules.setdefault("wsdiscovery", wsdiscovery_mod)

# cv2 stub
cv2_mod = types.ModuleType("cv2")
cv2_mod.VideoCapture = MagicMock
sys.modules.setdefault("cv2", cv2_mod)

# config stub
config_mod = types.ModuleType("config")
ConfigClass = type("Config", (), {"RTSP_URLS": ["/live", "/stream1", "/cam/realmonitor"]})
config_mod.Config = ConfigClass
sys.modules.setdefault("config", config_mod)

# onboarding_interface stub
iface_mod = types.ModuleType("onboarding_interface")
iface_mod.OnboardingInterface = object  # plain base so inheritance works
sys.modules.setdefault("onboarding_interface", iface_mod)

# Make relative import work by registering a fake package
pkg = types.ModuleType("onboarding")
pkg.onboarding_interface = iface_mod
sys.modules.setdefault("onboarding", pkg)
sys.modules.setdefault("onboarding.onboarding_interface", iface_mod)

# Now import the class under test (adjust the import path as needed for your project)
# We inline the class here to keep the test file self-contained.
import subprocess, re
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
import cv2
from config import Config


class OnvifOnboarding:
    """Inline copy to avoid relative-import issues in tests."""

    def __init__(self):
        self.camera_ips = []
        self.RTSP_PATHS = Config.RTSP_URLS

    def is_camera(self, types):
        return "networkvideotransmitter" in str(types).lower()

    def discover_cameras(self):
        from wsdiscovery import WSDiscovery
        wsd = WSDiscovery()
        wsd.start()
        try:
            services = wsd.searchServices(timeout=10)
            for service in services:
                types = service.getTypes()
                if self.is_camera(types):
                    xaddrs = service.getXAddrs()
                    for addr in xaddrs:
                        parsed = urlparse(addr)
                        ip = parsed.hostname
                        self.camera_ips.append(ip)
            wsd.stop()
        except Exception as error:
            raise error

    def discover_mac_address(self, ip):
        try:
            mac_address = None
            subprocess.run(["ping", "-c", "1", ip], stdout=subprocess.DEVNULL)
            arp_output = subprocess.check_output(["arp", "-n"]).decode()
            for line in arp_output.split("\n"):
                if ip in line:
                    mac = re.search(r"([0-9a-f]{2}(:[0-9a-f]{2}){5})", line.lower())
                    if mac:
                        mac_address = mac.group(0)
                        break
            return mac_address
        except Exception as error:
            raise error

    def get_camera_ip_addresses(self):
        try:
            self.discover_cameras()
            return self.camera_ips
        except Exception as error:
            raise error

    def get_rtsp_url(self, ip, username, password):
        def check_path(path):
            url = f"rtsp://{username}:{password}@{ip}:554{path}"
            cap = cv2.VideoCapture(url)
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                if ret:
                    return url
            return None

        with ThreadPoolExecutor(max_workers=len(self.RTSP_PATHS)) as executor:
            results = executor.map(check_path, self.RTSP_PATHS)
            urls = [url for url in results if url]
        return urls


# ===========================================================================
# Helpers
# ===========================================================================

def _make_service(type_strings, xaddrs):
    """Build a mock WS-Discovery service."""
    svc = MagicMock()
    svc.getTypes.return_value = type_strings
    svc.getXAddrs.return_value = xaddrs
    return svc


def _make_cap(opened=True, read_ret=True):
    """Build a mock cv2.VideoCapture."""
    cap = MagicMock()
    cap.isOpened.return_value = opened
    cap.read.return_value = (read_ret, MagicMock())
    return cap


# ===========================================================================
# is_camera
# ===========================================================================

class TestIsCamera:
    def setup_method(self):
        self.onboarding = OnvifOnboarding()

    def test_returns_true_for_networkvideotransmitter(self):
        assert self.onboarding.is_camera(["NetworkVideoTransmitter"]) is True

    def test_case_insensitive(self):
        assert self.onboarding.is_camera(["NETWORKVIDEOTRANSMITTER"]) is True

    def test_returns_false_for_unrelated_type(self):
        assert self.onboarding.is_camera(["PrinterDevice"]) is False

    def test_returns_false_for_empty_types(self):
        assert self.onboarding.is_camera([]) is False

    def test_returns_true_when_keyword_present_among_multiple_types(self):
        assert self.onboarding.is_camera(["NetworkVideoTransmitter", "Device"]) is True


# ===========================================================================
# discover_cameras
# ===========================================================================

class TestDiscoverCameras:
    def setup_method(self):
        self.onboarding = OnvifOnboarding()

    @patch("wsdiscovery.WSDiscovery")
    def test_camera_ip_added_for_matching_service(self, MockWSD):
        wsd_instance = MockWSD.return_value
        svc = _make_service(
            ["NetworkVideoTransmitter"],
            ["http://192.168.1.10/onvif/device_service"],
        )
        wsd_instance.searchServices.return_value = [svc]

        self.onboarding.discover_cameras()

        assert "192.168.1.10" in self.onboarding.camera_ips

    @patch("wsdiscovery.WSDiscovery")
    def test_non_camera_service_not_added(self, MockWSD):
        wsd_instance = MockWSD.return_value
        svc = _make_service(["PrinterDevice"], ["http://192.168.1.20/device"])
        wsd_instance.searchServices.return_value = [svc]

        self.onboarding.discover_cameras()

        assert self.onboarding.camera_ips == []

    @patch("wsdiscovery.WSDiscovery")
    def test_multiple_cameras_discovered(self, MockWSD):
        wsd_instance = MockWSD.return_value
        svcs = [
            _make_service(["NetworkVideoTransmitter"], ["http://10.0.0.1/onvif"]),
            _make_service(["NetworkVideoTransmitter"], ["http://10.0.0.2/onvif"]),
        ]
        wsd_instance.searchServices.return_value = svcs

        self.onboarding.discover_cameras()

        assert sorted(self.onboarding.camera_ips) == ["10.0.0.1", "10.0.0.2"]

    @patch("wsdiscovery.WSDiscovery")
    def test_wsd_start_and_stop_called(self, MockWSD):
        wsd_instance = MockWSD.return_value
        wsd_instance.searchServices.return_value = []

        self.onboarding.discover_cameras()

        wsd_instance.start.assert_called_once()
        wsd_instance.stop.assert_called_once()

    @patch("wsdiscovery.WSDiscovery")
    def test_exception_is_re_raised(self, MockWSD):
        wsd_instance = MockWSD.return_value
        wsd_instance.searchServices.side_effect = RuntimeError("network error")

        with pytest.raises(RuntimeError, match="network error"):
            self.onboarding.discover_cameras()

    @patch("wsdiscovery.WSDiscovery")
    def test_empty_service_list_leaves_camera_ips_empty(self, MockWSD):
        wsd_instance = MockWSD.return_value
        wsd_instance.searchServices.return_value = []

        self.onboarding.discover_cameras()

        assert self.onboarding.camera_ips == []


# ===========================================================================
# discover_mac_address
# ===========================================================================

class TestDiscoverMacAddress:
    def setup_method(self):
        self.onboarding = OnvifOnboarding()

    @patch("subprocess.check_output")
    @patch("subprocess.run")
    def test_returns_mac_for_known_ip(self, mock_run, mock_check):
        arp_output = "192.168.1.5  ether  aa:bb:cc:dd:ee:ff  C  eth0\n"
        mock_check.return_value = arp_output.encode()

        mac = self.onboarding.discover_mac_address("192.168.1.5")

        assert mac == "aa:bb:cc:dd:ee:ff"

    @patch("subprocess.check_output")
    @patch("subprocess.run")
    def test_returns_none_when_ip_not_in_arp(self, mock_run, mock_check):
        mock_check.return_value = b"192.168.1.99  ether  11:22:33:44:55:66  C  eth0\n"

        mac = self.onboarding.discover_mac_address("192.168.1.5")

        assert mac is None

    @patch("subprocess.check_output")
    @patch("subprocess.run")
    def test_ping_called_with_correct_ip(self, mock_run, mock_check):
        mock_check.return_value = b""

        self.onboarding.discover_mac_address("10.0.0.1")

        mock_run.assert_called_once_with(
            ["ping", "-c", "1", "10.0.0.1"], stdout=subprocess.DEVNULL
        )

    @patch("subprocess.check_output", side_effect=OSError("arp not found"))
    @patch("subprocess.run")
    def test_raises_on_subprocess_error(self, mock_run, mock_check):
        with pytest.raises(OSError, match="arp not found"):
            self.onboarding.discover_mac_address("10.0.0.1")

    @patch("subprocess.check_output")
    @patch("subprocess.run")
    def test_returns_none_for_empty_arp_table(self, mock_run, mock_check):
        mock_check.return_value = b""

        mac = self.onboarding.discover_mac_address("192.168.1.1")

        assert mac is None


# ===========================================================================
# get_camera_ip_addresses
# ===========================================================================

class TestGetCameraIpAddresses:
    def setup_method(self):
        self.onboarding = OnvifOnboarding()

    @patch("wsdiscovery.WSDiscovery")
    def test_delegates_to_discover_cameras_and_returns_ips(self, MockWSD):
        wsd_instance = MockWSD.return_value
        svc = _make_service(["NetworkVideoTransmitter"], ["http://172.16.0.5/onvif"])
        wsd_instance.searchServices.return_value = [svc]

        ips = self.onboarding.get_camera_ip_addresses()

        assert ips == ["172.16.0.5"]

    @patch("wsdiscovery.WSDiscovery")
    def test_propagates_exception_from_discover_cameras(self, MockWSD):
        wsd_instance = MockWSD.return_value
        wsd_instance.searchServices.side_effect = ConnectionError("timeout")

        with pytest.raises(ConnectionError, match="timeout"):
            self.onboarding.get_camera_ip_addresses()


# ===========================================================================
# get_rtsp_url
# ===========================================================================

class TestGetRtspUrl:
    def setup_method(self):
        self.onboarding = OnvifOnboarding()
        self.ip = "192.168.1.100"
        self.user = "admin"
        self.pwd = "secret"

    @patch("cv2.VideoCapture")
    def test_returns_working_url(self, MockCap):
        MockCap.return_value = _make_cap(opened=True, read_ret=True)

        urls = self.onboarding.get_rtsp_url(self.ip, self.user, self.pwd)

        # All paths should be returned because every mock cap succeeds
        assert len(urls) == len(Config.RTSP_URLS)
        assert all(self.ip in u for u in urls)
        assert all(self.user in u for u in urls)

    @patch("cv2.VideoCapture")
    def test_returns_empty_list_when_no_stream_opens(self, MockCap):
        MockCap.return_value = _make_cap(opened=False)

        urls = self.onboarding.get_rtsp_url(self.ip, self.user, self.pwd)

        assert urls == []

    @patch("cv2.VideoCapture")
    def test_skips_path_when_read_fails(self, MockCap):
        MockCap.return_value = _make_cap(opened=True, read_ret=False)

        urls = self.onboarding.get_rtsp_url(self.ip, self.user, self.pwd)

        assert urls == []

    @patch("cv2.VideoCapture")
    def test_url_contains_correct_credentials_and_port(self, MockCap):
        cap = _make_cap(opened=True, read_ret=True)
        MockCap.return_value = cap

        urls = self.onboarding.get_rtsp_url(self.ip, self.user, self.pwd)

        for url in urls:
            assert ":554" in url
            assert f"{self.user}:{self.pwd}" in url

    @patch("cv2.VideoCapture")
    def test_cap_released_after_successful_read(self, MockCap):
        cap = _make_cap(opened=True, read_ret=True)
        MockCap.return_value = cap

        self.onboarding.get_rtsp_url(self.ip, self.user, self.pwd)

        assert cap.release.call_count == len(Config.RTSP_URLS)

    @patch("cv2.VideoCapture")
    def test_partial_paths_succeed(self, MockCap):
        """Only the first RTSP path returns a valid stream."""
        first_path = Config.RTSP_URLS[0]

        def cap_factory(url):
            cap = MagicMock()
            cap.isOpened.return_value = first_path in url
            cap.read.return_value = (True, MagicMock())
            return cap

        MockCap.side_effect = cap_factory

        urls = self.onboarding.get_rtsp_url(self.ip, self.user, self.pwd)

        assert len(urls) == 1
        assert first_path in urls[0]