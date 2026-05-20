import os
import re
import socket
import subprocess

def get_network_interfaces():
    """
    Returns a list of dictionaries containing active network interfaces on Linux.
    Fallback to standard socket queries if 'ip' command is missing.
    Format:
    [
        {"name": "eth0", "family": "IPv4", "ip": "192.168.1.5"},
        {"name": "wlan0", "family": "IPv6", "ip": "fe80::1"}
    ]
    """
    interfaces = []
    
    # Primary logic: Parse 'ip -o addr show' on Linux
    if os.name != 'nt':
        try:
            result = subprocess.run(['ip', '-o', 'addr', 'show'], 
                                   capture_output=True, text=True, check=True)
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 4:
                    ifname = parts[1]
                    family = parts[2]  # 'inet' (IPv4) or 'inet6' (IPv6)
                    ip_cidr = parts[3] # e.g. '192.168.1.5/24' or 'fe80::a00/64'
                    ip = ip_cidr.split('/')[0]
                    
                    # Skip loopback interface
                    if ifname == 'lo' or ip == '::1' or ip.startswith('127.'):
                        continue
                        
                    friendly_family = 'IPv4' if family == 'inet' else 'IPv6'
                    
                    # Translate common interface names to friendly names
                    friendly_name = ifname
                    if ifname.startswith('wl') or 'wifi' in ifname.lower():
                        friendly_name = f"[Wi-Fi] {ifname}"
                    elif ifname.startswith('en') or ifname.startswith('eth'):
                        friendly_name = f"[Ethernet] {ifname}"
                    else:
                        friendly_name = f"[Network] {ifname}"
                        
                    interfaces.append({
                        "name": friendly_name,
                        "raw_name": ifname,
                        "family": friendly_family,
                        "ip": ip
                    })
            return interfaces
        except Exception:
            # Fall through to socket fallback if 'ip' fails
            pass

    # Fallback / cross-platform logic using standard socket library
    try:
        hostname = socket.gethostname()
        addr_infos = socket.getaddrinfo(hostname, None)
        seen_ips = set()
        for info in addr_infos:
            family_num = info[0]
            ip = info[4][0]
            
            # Skip loopbacks and duplicates
            if ip == '127.0.0.1' or ip == '::1' or ip in seen_ips:
                continue
                
            seen_ips.add(ip)
            
            if family_num == socket.AF_INET:
                family = 'IPv4'
            elif family_num == socket.AF_INET6:
                family = 'IPv6'
            else:
                continue
                
            interfaces.append({
                "name": f"[Default Interface] ({family})",
                "raw_name": "default",
                "family": family,
                "ip": ip
            })
    except Exception:
        pass
        
    return interfaces
