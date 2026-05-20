import sys
import os
import json

# Setup Config Path to read settings before loading Qt
CONFIG_PATH = os.path.expanduser("~/.config/camo/config.json")

def force_high_performance_gpu():
    """
    Exports Prime offloading environment variables to force the usage
    of high performance discrete GPUs on Linux Optimus/hybrid laptops.
    """
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
                settings = config.get("settings", {})
                if settings.get("force_gpu", False):
                    print("CAMO: Forcing high-performance discrete GPU offload...")
                    os.environ["__NV_PRIME_RENDER_OFFLOAD"] = "1"
                    os.environ["__GLX_VENDOR_LIBRARY_NAME"] = "nvidia"
                    os.environ["DRI_PRIME"] = "1"
        except Exception as e:
            print(f"CAMO Startup: Could not read config for GPU setup: {e}")

# Apply GPU offload settings before any GUI or graphics libraries are loaded
force_high_performance_gpu()

# Now import PySide6 components
from PySide6.QtWidgets import QApplication
from camo_app.gui import CAMOMainWindow

def main():
    # Setup high DPI scaling for crisp premium aesthetics on modern monitors
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    app = QApplication(sys.argv)
    app.setApplicationName("CAMO")
    app.setApplicationDisplayName("CAMO - Low Latency RTSP Router")
    
    # Create the main window
    window = CAMOMainWindow()
    
    # Run loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
