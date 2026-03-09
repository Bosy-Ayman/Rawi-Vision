from wsdiscovery import WSDiscovery
import subprocess
import re

wsd = WSDiscovery()  # IPv4 enabled by default
wsd.start()
services = wsd.searchServices(timeout=10)

# is there a way to get the mac address?
for service in services:
    print("Device name:", service.getXAddrs())
    print("Types:", service.getTypes())
    print("Scopes:", service.getScopes())
    print("EPR:", service.getEPR())

wsd.stop()

def get_mac(ip):
    try:
        # Ping the device to ensure it's in the ARP table
        subprocess.run(["ping", "-c", "1", ip], stdout=subprocess.DEVNULL)

        # Read ARP table, this command will fail if not on a linux system
        arp_output = subprocess.check_output(["arp", "-n"]).decode()

        for line in arp_output.split("\n"):
            if ip in line:
                mac = re.search(r"([0-9a-f]{2}(:[0-9a-f]{2}){5})", line.lower())
                if mac:
                    return mac.group(0)

        return None
    except Exception as e:
        print(e)

ip = "192.168.1.5"
mac = get_mac(ip)

print("MAC Address:", mac)