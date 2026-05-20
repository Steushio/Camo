import os
import json
import socket
from urllib.parse import urlparse
import subprocess
from PySide6.QtCore import QObject, Signal, Slot, QTimer
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gst, GstVideo, GLib

CONFIG_PATH = os.path.expanduser("~/.config/camo/config.json")

class CameraPipeline(QObject):
    # Signals for communicating with GUI
    status_changed = Signal(str, str)  # cam_id, status_string
    stats_updated = Signal(str, float, float)  # cam_id, fps, bitrate_kbps
    error_occurred = Signal(str, str)  # cam_id, error_message

    def __init__(self, cam_id, config, parent=None):
        super().__init__(parent)
        self.cam_id = cam_id
        self.config = config  # Dict with name, rtsp_url, device (v4l2), hw_mode, network_bind, etc.
        self.pipeline = None
        self.win_id = None
        self.is_running = False
        
        # Connection status tracking
        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.setSingleShot(True)
        self.reconnect_timer.timeout.connect(self.reconnect_start)
        self.is_reconnecting = False
        
        # Bus polling timer
        self.bus_timer = QTimer(self)
        self.bus_timer.timeout.connect(self.poll_bus)

    def set_window_handle(self, win_id):
        self.win_id = win_id
        # If pipeline is already running, we might need to update the window handle
        if self.pipeline:
            # Note: Changing window handle on the fly is supported by GstVideoOverlay
            pass

    def get_pipeline_string(self):
        rtsp_url = self.config.get("rtsp_url", "")
        v4l2_device = self.config.get("device", "")
        hw_mode = self.config.get("hw_mode", "auto")
        enable_pipewire = self.config.get("enable_pipewire", True)
        enable_v4l2 = self.config.get("enable_v4l2", True)
        
        # Build decoder element based on hardware mode
        dec_element = "avdec_h264" # Default fallback
        if hw_mode == "nvidia":
            dec_element = "nvh264dec"
        elif hw_mode == "vaapi":
            dec_element = "vaapih264dec"
        elif hw_mode == "auto":
            # GStreamer decodebin automatically negotiates hw decoders
            dec_element = "decodebin"
            
        # Base RTSP stream ingestion
        # protocols=tcp prevents packet drops and reduces latency spikes
        pipeline_str = (
            f"rtspsrc location=\"{rtsp_url}\" latency=0 protocols=tcp ! "
            f"rtph264depay ! h264parse ! {dec_element} ! tee name=t "
        )
        
        # Preview output (autovideosink dynamically selects the best display sink)
        pipeline_str += "t. ! queue ! videoconvert ! autovideosink name=preview_sink "
        
        # PipeWire virtual camera output
        if enable_pipewire:
            cam_name = self.config.get("name", "CAMO Cam")
            pipeline_str += (
                f"t. ! queue ! videoconvert ! video/x-raw,format=I420 ! "
                f"pipewiresink mode=provide "
                f"stream-properties=\"properties,media.class=Video/Source,media.role=Camera\" "
                f"client-name=\"{cam_name}\" "
            )
            
        # V4L2 virtual camera output
        if enable_v4l2 and v4l2_device:
            pipeline_str += (
                f"t. ! queue ! videoconvert ! video/x-raw,format=YUY2 ! "
                f"v4l2sink device={v4l2_device} "
            )
            
        return pipeline_str

    def reconnect_start(self):
        self.is_reconnecting = True
        self.start()
        self.is_reconnecting = False

    def start(self):
        is_reconnecting = getattr(self, "is_reconnecting", False)
        self.stop(is_reconnecting=is_reconnecting)
        
        # Apply network interface routing if set and we are not reconnecting
        if not is_reconnecting:
            self.apply_network_routing()
        
        pipeline_str = self.get_pipeline_string()
        print(f"Starting GStreamer pipeline for {self.cam_id}:\n{pipeline_str}")
        
        try:
            self.pipeline = Gst.parse_launch(pipeline_str)
            
            # Setup sync handler to intercept "prepare-window-handle" for zero-copy rendering
            bus = self.pipeline.get_bus()
            bus.set_sync_handler(self.on_sync_message)
            
            # Start state
            self.pipeline.set_state(Gst.State.PLAYING)
            self.is_running = True
            
            # Start timers
            self.bus_timer.start(50)  # Check bus messages every 50ms
            self.status_changed.emit(self.cam_id, "Streaming")
            
        except Exception as e:
            self.is_running = False
            self.status_changed.emit(self.cam_id, "Error")
            self.error_occurred.emit(self.cam_id, f"Failed to initialize GStreamer: {str(e)}")

    def stop(self, is_reconnecting=False):
        self.bus_timer.stop()
        if not is_reconnecting:
            self.reconnect_timer.stop()
        
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
            
        self.is_running = False
        self.status_changed.emit(self.cam_id, "Stopped")
        
        # Tear down any temporary network routes if not reconnecting
        if not is_reconnecting:
            self.remove_network_routing()

    def on_sync_message(self, bus, message):
        struct = message.get_structure()
        if struct is None:
            return Gst.BusSyncReply.PASS
            
        message_name = struct.get_name()
        if message_name == "prepare-window-handle":
            imagesink = message.src
            imagesink.set_property("force-aspect-ratio", True)
            if self.win_id:
                # Tell GStreamer to draw directly onto our Qt widget handle
                imagesink.set_window_handle(self.win_id)
            return Gst.BusSyncReply.DROP
            
        return Gst.BusSyncReply.PASS

    def poll_bus(self):
        if not self.pipeline:
            return
            
        bus = self.pipeline.get_bus()
        while True:
            # Non-blocking poll of bus messages
            msg = bus.pop_filtered(Gst.MessageType.ANY)
            if not msg:
                break
                
            msg_type = msg.type
            if msg_type == Gst.MessageType.ERROR:
                err, debug_info = msg.parse_error()
                error_msg = err.message
                print(f"GStreamer Pipeline Error for {self.cam_id}: {error_msg}")
                if debug_info:
                    print(f"GStreamer Debug Info: {debug_info}")
                self.error_occurred.emit(self.cam_id, error_msg)
                self.status_changed.emit(self.cam_id, "Connection Lost")
                self.stop(is_reconnecting=True)
                # Attempt auto-reconnection in 5 seconds
                self.reconnect_timer.start(5000)
                break
            elif msg_type == Gst.MessageType.EOS:
                self.status_changed.emit(self.cam_id, "End of Stream")
                self.stop()
                break
            elif msg_type == Gst.MessageType.STATE_CHANGED:
                # Could track sub-state transitions if needed
                pass

    def apply_network_routing(self):
        """
        Forces traffic to the RTSP camera IP to route via the selected network interface.
        """
        bind_ip = self.config.get("network_bind", "default")
        if bind_ip == "default":
            manager = self.parent()
            if manager:
                bind_ip = manager.get_settings().get("global_network_bind", "default")

        # If user-space preload binding is active, use it (no sudo required)
        if os.environ.get("CAMO_PRELOAD_ACTIVE") == "1":
            if bind_ip and bind_ip != "default":
                os.environ["BIND_ADDR"] = bind_ip
                print(f"CAMO: Setting socket bind address to {bind_ip} via preload shim.")
            else:
                os.environ.pop("BIND_ADDR", None)
            return

        if bind_ip == "default":
            return
            
        rtsp_url = self.config.get("rtsp_url", "")
        try:
            url = rtsp_url.replace("rtsp://", "http://")
            parsed = urlparse(url)
            host = parsed.hostname
            if not host:
                return
                
            camera_ip = socket.gethostbyname(host)
            
            # Find the network interface name associated with the selected local IP
            # We import get_network_interfaces here to avoid circular imports
            from camo_app.network_utils import get_network_interfaces
            interfaces = get_network_interfaces()
            target_iface = None
            for iface in interfaces:
                if iface["ip"] == bind_ip:
                    target_iface = iface["raw_name"]
                    break
                    
            if target_iface:
                # Add temporary route using pkexec
                cmd = ["pkexec", "ip", "route", "replace", camera_ip, "dev", target_iface, "src", bind_ip]
                result = subprocess.run(cmd, capture_output=True)
                if result.returncode == 0:
                    self.config["_active_route_ip"] = camera_ip
                    print(f"CAMO: Successfully applied static route for {camera_ip} via {target_iface}")
                else:
                    print(f"CAMO: Network routing override failed (exit code {result.returncode}). Falling back to default route to prevent password spam.")
                    # Temporarily disable network bind for this camera session so we do not prompt again
                    self.config["network_bind"] = "default"
        except Exception as e:
            print(f"Failed to set static network route: {e}")

    def remove_network_routing(self):
        """
        Cleans up network routing/binding.
        """
        if os.environ.get("CAMO_PRELOAD_ACTIVE") == "1":
            manager = self.parent()
            if manager:
                global_bind = manager.get_settings().get("global_network_bind", "default")
                if global_bind and global_bind != "default":
                    os.environ["BIND_ADDR"] = global_bind
                    return
            os.environ.pop("BIND_ADDR", None)
            return

        active_route_ip = self.config.get("_active_route_ip")
        if active_route_ip:
            try:
                cmd = ["pkexec", "ip", "route", "del", active_route_ip]
                subprocess.run(cmd, capture_output=True)
                self.config.pop("_active_route_ip", None)
            except Exception:
                pass


class CameraManager(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        Gst.init(None)
        
        self.config = {
            "cameras": [],
            "settings": {
                "autostart": False,
                "start_minimized": False,
                "minimize_to_tray": True,
                "force_gpu": False,
                "hw_mode": "auto",
                "global_network_bind": "default",
                "preferred_ip_family": "both"
            }
        }
        self.active_pipelines = {}
        self.load_config()

    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r') as f:
                    self.config = json.load(f)
            except Exception as e:
                print(f"Error loading configuration: {e}")
        else:
            # Create config directory if not exists
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            self.save_config()

        # Initialize BIND_ADDR for the preloaded socket shim
        if os.environ.get("CAMO_PRELOAD_ACTIVE") == "1":
            global_bind = self.get_settings().get("global_network_bind", "default")
            if global_bind and global_bind != "default":
                os.environ["BIND_ADDR"] = global_bind
                print(f"CAMO Preload: Initialized BIND_ADDR to {global_bind}")
            else:
                os.environ.pop("BIND_ADDR", None)

    def save_config(self):
        try:
            with open(CONFIG_PATH, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving configuration: {e}")

    def get_cameras(self):
        return self.config.get("cameras", [])

    def get_settings(self):
        return self.config.get("settings", {})

    def update_settings(self, new_settings):
        self.config["settings"].update(new_settings)
        self.save_config()

        # Dynamically update BIND_ADDR if the global bind setting changed
        if "global_network_bind" in new_settings and os.environ.get("CAMO_PRELOAD_ACTIVE") == "1":
            global_bind = new_settings["global_network_bind"]
            if global_bind and global_bind != "default":
                os.environ["BIND_ADDR"] = global_bind
                print(f"CAMO Preload: Updated BIND_ADDR to {global_bind}")
            else:
                os.environ.pop("BIND_ADDR", None)

    def add_camera(self, name, rtsp_url, device, hw_mode="auto", network_bind="default", enable_pipewire=True, enable_v4l2=True, autostart=False):
        cam_id = f"cam_{int(QTimer.remainingTime(QTimer())) + len(self.config['cameras']) + 1}"
        camera = {
            "id": cam_id,
            "name": name,
            "rtsp_url": rtsp_url,
            "device": device,
            "hw_mode": hw_mode,
            "network_bind": network_bind,
            "autostart": autostart,
            "enable_pipewire": enable_pipewire,
            "enable_v4l2": enable_v4l2,
            "enabled": False
        }
        self.config["cameras"].append(camera)
        self.save_config()
        return cam_id

    def edit_camera(self, cam_id, name, rtsp_url, device, hw_mode, network_bind, enable_pipewire, enable_v4l2, autostart=False):
        for cam in self.config["cameras"]:
            if cam["id"] == cam_id:
                was_running = self.is_streaming(cam_id)
                if was_running:
                    self.stop_camera(cam_id)
                    
                cam.update({
                    "name": name,
                    "rtsp_url": rtsp_url,
                    "device": device,
                    "hw_mode": hw_mode,
                    "network_bind": network_bind,
                    "autostart": autostart,
                    "enable_pipewire": enable_pipewire,
                    "enable_v4l2": enable_v4l2
                })
                self.save_config()
                
                if was_running:
                    self.start_camera(cam_id)
                return True
        return False

    def remove_camera(self, cam_id):
        self.stop_camera(cam_id)
        self.config["cameras"] = [c for c in self.config["cameras"] if c["id"] != cam_id]
        self.save_config()

    def start_camera(self, cam_id, win_id=None):
        for cam in self.config["cameras"]:
            if cam["id"] == cam_id:
                if cam_id not in self.active_pipelines:
                    pipeline = CameraPipeline(cam_id, cam, self)
                    if win_id:
                        pipeline.set_window_handle(win_id)
                    self.active_pipelines[cam_id] = pipeline
                
                self.active_pipelines[cam_id].start()
                cam["enabled"] = True
                self.save_config()
                return self.active_pipelines[cam_id]
        return None

    def stop_camera(self, cam_id):
        if cam_id in self.active_pipelines:
            self.active_pipelines[cam_id].stop()
            self.active_pipelines.pop(cam_id)
            
        for cam in self.config["cameras"]:
            if cam["id"] == cam_id:
                cam["enabled"] = False
                break
        self.save_config()

    def is_streaming(self, cam_id):
        if cam_id in self.active_pipelines:
            return self.active_pipelines[cam_id].is_running
        return False
        
    def start_all(self):
        for cam in self.config["cameras"]:
            self.start_camera(cam["id"])
            
    def stop_all(self):
        # Must copy keys because stop_camera mutates self.active_pipelines
        for cam_id in list(self.active_pipelines.keys()):
            self.stop_camera(cam_id)
