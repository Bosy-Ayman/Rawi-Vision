from .onboarding_interface import OnboardingInterface
import socket
import nmap
import cv2
import subprocess
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

class NonOnvifOnboarding(OnboardingInterface):
    def __init__(self):
        self.camera_ips=[]
        self.RTSP_PATHS = [
            "/Streaming/Channels/101",
            "/Streaming/Channels/102",
            "/Streaming/Channels/201",
            "/Streaming/Channels/301",
            "/Streaming/Channels/401",
            "/h264/ch1/main/av_stream",
            "/h264/ch1/sub/av_stream",
            "/live",
            "/live.sdp",
            "/stream1",
            "/stream2",
            "/cam/realmonitor?channel=1&subtype=0"]
    
    def _try_rtsp_urls(self, ip, username, password, path):
        url = f"rtsp://{username}:{password}@{ip}:554/{path}"
        cap = cv2.VideoCapture(url)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                cap.release()
                return True
            cap.release()
        return False

    def is_camera(self, ip, username, password):
        with ThreadPoolExecutor(max_workers=len(self.RTSP_PATHS)) as executor:
            futures= {
                executor.submit(self._try_rtsp_urls, ip, username, password, path): path
                for path in self.RTSP_PATHS
            }
            for future in as_completed(futures):
                if future.result():
                    for f in futures:
                        f.cancel()
                    return True
        return False

    def get_camera_ip_addresses(self, username, password):
        network_range = "192.168.1.0/24"
        nm = nmap.PortScanner()
        nm.scan(hosts=network_range, ports='80,443,554,8080,8554', arguments='-T5 --open')
        candidate_hosts=[]
        for host in nm.all_hosts():
            if 'tcp' not in nm[host]:
                continue
            ports = nm[host]['tcp']
            has_rtsp = 554 in ports or 8554 in ports
            has_http = 80 in ports or 8080 in ports
            if (has_rtsp or has_http) and self.is_camera(host, username=username, password=password):
                candidate_hosts.append(host)
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures={
                executor.submit(self.is_camera, host, username, password): host
                for host in candidate_hosts
            }
            for future in as_completed(futures):
                if future.result():
                    self.camera_ips.append(futures[future])
        return self.camera_ips

    def discover_camera_mac_address(self, ip, username, password):
        try:
            subprocess.run(["ping", "-c", "1",ip], stdout=subprocess.DEVNULL)
            arp_output = subprocess.check_output(["arp", "-n"]).decode()
            for line in arp_output.split("\n"):
                if ip in line:
                    mac = re.search(r"([0-9a-f]{2}(:[0-9a-f]{2}){5})", line.lower())
                    if mac:
                        mac_address= mac.group(0)
            return mac_address
        except Exception as error:
            raise error
    
    def get_rtsp_url(self, ip, username, password):
        urls = []
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