import os
import sys

def get_autostart_path():
    """
    Returns the path to the autostart desktop file for CAMO on Linux.
    """
    if os.name == 'nt':
        return None
    home = os.path.expanduser("~")
    autostart_dir = os.path.join(home, ".config", "autostart")
    if not os.path.exists(autostart_dir):
        try:
            os.makedirs(autostart_dir, exist_ok=True)
        except Exception:
            return None
    return os.path.join(autostart_dir, "camo.desktop")

def is_autostart_enabled():
    """
    Checks if CAMO's autostart file exists.
    """
    path = get_autostart_path()
    if not path:
        return False
    return os.path.exists(path)

def set_autostart(enable=True):
    """
    Enables or disables CAMO's autostart by writing or removing the .desktop file.
    """
    path = get_autostart_path()
    if not path:
        return False
        
    if not enable:
        if os.path.exists(path):
            try:
                os.remove(path)
                return True
            except Exception:
                return False
        return True
        
    # Enable: Write .desktop file
    try:
        app_dir = os.path.abspath(os.path.dirname(os.path.dirname(sys.argv[0])))
        run_script = os.path.join(app_dir, "run_camo.sh")
        logo_path = os.path.join(app_dir, "camo_app", "assets", "logo.png")
        
        # Fallback if run_camo.sh is missing
        if not os.path.exists(run_script):
            run_script = f"python3 -m camo_app.main"
            
        desktop_content = f"""[Desktop Entry]
Type=Application
Name=CAMO
Comment=Ultra Low Latency Virtual Camera Router
Exec={run_script} --minimized
Icon={logo_path if os.path.exists(logo_path) else "video-x-generic"}
Terminal=false
Categories=AudioVideo;Video;
X-GNOME-Autostart-enabled=true
"""
        with open(path, 'w') as f:
            f.write(desktop_content)
        return True
    except Exception as e:
        print(f"Error setting autostart: {e}")
        return False
