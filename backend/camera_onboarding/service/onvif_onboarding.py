from wsdiscovery import WSDiscovery # for onvif-compaitable cameras
import subprocess
import re
from urllib.parse import urlparse
from .onboarding_interface import OnboardingInterface
import cv2
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import Config  

class OnvifOnboarding(OnboardingInterface):
    def __init__(self):
        self.camera_ips = []
        self.RTSP_PATHS = Config.RTSP_URLS
        
    def is_camera(self, types):
        if 'networkvideotransmitter' in str(types).lower(): # i think i need to add more strings, not sure tho
            return True
        return False

    def discover_cameras(self):
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

