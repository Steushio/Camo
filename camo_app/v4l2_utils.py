import os
import glob
import subprocess

def list_video_devices():
    """
    Scans the system for video devices and returns their paths and labels.
    Returns:
        list of dicts: [{"device": "/dev/video10", "name": "CAMO Cam 1", "is_loopback": True}, ...]
    """
    if os.name == 'nt':
        return [
            {"device": "OBS Virtual Camera", "name": "OBS Virtual Camera", "is_loopback": True},
            {"device": "Unity Capture", "name": "Unity Capture", "is_loopback": True}
        ]

    devices = []
    video_paths = glob.glob('/dev/video*')
    # Sort numerically (video0, video1, video10, etc.)
    video_paths.sort(key=lambda path: int(path.replace('/dev/video', '')) if path.replace('/dev/video', '').isdigit() else 999)
    
    for path in video_paths:
        dev_name = os.path.basename(path)
        sys_path = f"/sys/class/video4linux/{dev_name}/name"
        card_name = "Unknown Camera"
        is_loopback = False
        
        if os.path.exists(sys_path):
            try:
                with open(sys_path, 'r') as f:
                    card_name = f.read().strip()
            except Exception:
                pass
                
        # Check if v4l2loopback is the driver (typically indicates loopback device)
        driver_path = f"/sys/class/video4linux/{dev_name}/device/driver"
        if os.path.exists(driver_path):
            try:
                driver_link = os.readlink(driver_path)
                if 'v4l2loopback' in driver_link:
                    is_loopback = True
            except Exception:
                pass
        
        # Fallback check by card name
        if "loopback" in card_name.lower() or "camo" in card_name.lower():
            is_loopback = True
            
        devices.append({
            "device": path,
            "name": card_name,
            "is_loopback": is_loopback
        })
        
    return devices

def is_v4l2loopback_loaded():
    """
    Checks if the v4l2loopback module is loaded in the kernel.
    """
    if os.name == 'nt':
        return False
    try:
        result = subprocess.run(['lsmod'], capture_output=True, text=True)
        return 'v4l2loopback' in result.stdout
    except Exception:
        return False

def load_v4l2loopback(devices_count=4, start_nr=10):
    """
    Uses PolicyKit (pkexec) to load the v4l2loopback module with the correct parameters.
    """
    if os.name == 'nt':
        return False, "Not supported on Windows"
        
    video_nr_list = ",".join(str(start_nr + i) for i in range(devices_count))
    card_labels = ",".join(f'"CAMO Virtual Cam {i+1}"' for i in range(devices_count))
    
    exclusive_caps_list = ",".join("1" for _ in range(devices_count))
    cmd = [
        "pkexec", "modprobe", "v4l2loopback",
        f"devices={devices_count}",
        f"video_nr={video_nr_list}",
        f"card_label={card_labels}",
        f"exclusive_caps={exclusive_caps_list}"
    ]
    
    try:
        # Check if PolicyKit is available
        subprocess.run(["pkexec", "--version"], capture_output=True, check=True)
    except Exception:
        return False, "PolicyKit (pkexec) is not installed or available. Please run: sudo modprobe v4l2loopback exclusive_caps=1"
        
    try:
        # Load kernel module
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True, "v4l2loopback module loaded successfully"
        else:
            return False, f"Failed to load module: {result.stderr.strip()}"
    except Exception as e:
        return False, f"Failed to execute pkexec: {str(e)}"
        
def unload_v4l2loopback():
    """
    Unloads the v4l2loopback module.
    """
    if os.name == 'nt':
        return False
    cmd = ["pkexec", "rmmod", "v4l2loopback"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False
