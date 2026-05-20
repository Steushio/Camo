import sys
import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QStackedWidget, QLineEdit, QComboBox, QCheckBox, 
    QDialog, QFormLayout, QGridLayout, QFrame, QScrollArea, 
    QSystemTrayIcon, QMenu, QMessageBox, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QSize, Slot
from PySide6.QtGui import QIcon, QColor, QFont, QPalette, QCursor

from camo_app.network_utils import get_network_interfaces
from camo_app.v4l2_utils import list_video_devices, is_v4l2loopback_loaded, load_v4l2loopback
from camo_app.autostart import is_autostart_enabled, set_autostart
from camo_app.camera_manager import CameraManager

# Sleek Dark Palette CSS
STYLING = """
    QWidget {
        background-color: #12131C;
        color: #E2E4F0;
        font-family: 'Segoe UI', 'Inter', 'Roboto', Helvetica, Arial, sans-serif;
        font-size: 13px;
    }
    
    /* Header and Title Bar */
    QFrame#TitleBar {
        background-color: #1A1C29;
        border-bottom: 1px solid #23273A;
    }
    
    QLabel#TitleLabel {
        font-weight: bold;
        font-size: 15px;
        color: #00D2FF;
    }
    
    /* Left Sidebar */
    QFrame#Sidebar {
        background-color: #181924;
        border-right: 1px solid #23273A;
    }
    
    QPushButton.MenuButton {
        background-color: transparent;
        border: none;
        border-left: 3px solid transparent;
        color: #8E93B3;
        text-align: left;
        padding: 12px 20px;
        font-weight: 500;
    }
    
    QPushButton.MenuButton:hover {
        background-color: #202231;
        color: #E2E4F0;
    }
    
    QPushButton.MenuButton:checked {
        background-color: #1D1F2D;
        color: #ffffff;
        border-left: 3px solid #00D2FF;
    }
    
    /* Card Styles */
    QFrame.CameraCard {
        background-color: #1A1C29;
        border: 1px solid #2A2E44;
        border-radius: 8px;
    }
    
    QFrame.CameraCard:hover {
        border: 1px solid #00D2FF;
    }
    
    /* Buttons */
    QPushButton.PrimaryButton {
        background-color: #0078FF;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 8px 16px;
        font-weight: bold;
    }
    
    QPushButton.PrimaryButton:hover {
        background-color: #00D2FF;
    }
    
    QPushButton.DangerButton {
        background-color: #D32F2F;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 8px 16px;
    }
    
    QPushButton.DangerButton:hover {
        background-color: #F44336;
    }
    
    QPushButton.SecondaryButton {
        background-color: #23273A;
        border: 1px solid #323854;
        border-radius: 4px;
        padding: 8px 16px;
    }
    
    QPushButton.SecondaryButton:hover {
        background-color: #2E334D;
        border-color: #00D2FF;
    }
    
    /* Text Inputs */
    QLineEdit {
        background-color: #1B1D2B;
        border: 1px solid #2F344C;
        border-radius: 4px;
        padding: 6px 12px;
        color: white;
    }
    
    QLineEdit:focus {
        border: 1px solid #00D2FF;
    }
    
    /* ComboBoxes */
    QComboBox {
        background-color: #1B1D2B;
        border: 1px solid #2F344C;
        border-radius: 4px;
        padding: 6px 12px;
        color: white;
    }
    
    QComboBox::drop-down {
        border: none;
    }
    
    /* Scroll Areas */
    QScrollArea {
        border: none;
        background-color: transparent;
    }
    
    /* Checkbox */
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border: 1px solid #2F344C;
        border-radius: 3px;
        background-color: #1B1D2B;
    }
    
    QCheckBox::indicator:checked {
        background-color: #0078FF;
        border-color: #00D2FF;
    }
"""

class GstVideoOverlayWidget(QWidget):
    """
    Subclass of QWidget configured for native X11 window capabilities.
    Enables GStreamer's VideoOverlay to render directly to GPU VRAM with zero-copy.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DontCreateSandboxPack, True)
        self.setStyleSheet("background-color: #06070B; border: 1px solid #23273A; border-radius: 4px;")


class AddEditCameraDialog(QDialog):
    def __init__(self, camera_data=None, parent=None):
        super().__init__(parent)
        self.camera_data = camera_data
        self.setWindowTitle("Edit Camera" if camera_data else "Add Camera")
        self.setFixedSize(500, 420)
        self.setStyleSheet(STYLING)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("Edit Camera Configuration" if self.camera_data else "Register New RTSP Stream")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #00D2FF;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Office Front Gate")
        form.addRow("Camera Name:", self.name_input)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("rtsp://user:password@ip:port/path")
        form.addRow("RTSP Stream URL:", self.url_input)

        # Loopback video device selection
        self.device_combo = QComboBox()
        self.device_combo.addItem("None", "")
        devices = list_video_devices()
        for d in devices:
            if d["is_loopback"]:
                self.device_combo.addItem(f"{d['name']} ({d['device']})", d["device"])
        form.addRow("V4L2 Virtual Device:", self.device_combo)

        # GPU acceleration selection
        self.hw_combo = QComboBox()
        self.hw_combo.addItem("Auto Detect (Recommended)", "auto")
        self.hw_combo.addItem("NVIDIA (NVDEC)", "nvidia")
        self.hw_combo.addItem("Intel/AMD (VA-API)", "vaapi")
        self.hw_combo.addItem("Disable HW Acceleration", "cpu")
        form.addRow("GPU Decoding Mode:", self.hw_combo)

        # Local network bind selection
        self.bind_combo = QComboBox()
        self.bind_combo.addItem("Default Interface Route", "default")
        interfaces = get_network_interfaces()
        for iface in interfaces:
            self.bind_combo.addItem(f"{iface['name']} - {iface['ip']}", iface["ip"])
        form.addRow("Local Network Bind:", self.bind_combo)

        # Output options
        self.pw_check = QCheckBox("Expose as Native PipeWire Camera")
        self.pw_check.setChecked(True)
        form.addRow("", self.pw_check)

        self.v4l2_check = QCheckBox("Expose as Legacy V4L2 Webcam")
        self.v4l2_check.setChecked(True)
        form.addRow("", self.v4l2_check)

        layout.addLayout(form)

        # Pre-fill fields if editing
        if self.camera_data:
            self.name_input.setText(self.camera_data.get("name", ""))
            self.url_input.setText(self.camera_data.get("rtsp_url", ""))
            
            # Select V4L2 device
            idx = self.device_combo.findData(self.camera_data.get("device", ""))
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)
                
            # Select HW Mode
            idx = self.hw_combo.findData(self.camera_data.get("hw_mode", "auto"))
            if idx >= 0:
                self.hw_combo.setCurrentIndex(idx)
                
            # Select network bind IP
            idx = self.bind_combo.findData(self.camera_data.get("network_bind", "default"))
            if idx >= 0:
                self.bind_combo.setCurrentIndex(idx)
                
            self.pw_check.setChecked(self.camera_data.get("enable_pipewire", True))
            self.v4l2_check.setChecked(self.camera_data.get("enable_v4l2", True))

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "SecondaryButton")
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("Save Settings" if self.camera_data else "Add Camera")
        save_btn.setProperty("class", "PrimaryButton")
        save_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def get_data(self):
        return {
            "name": self.name_input.text().strip(),
            "rtsp_url": self.url_input.text().strip(),
            "device": self.device_combo.currentData(),
            "hw_mode": self.hw_combo.currentData(),
            "network_bind": self.bind_combo.currentData(),
            "enable_pipewire": self.pw_check.isChecked(),
            "enable_v4l2": self.v4l2_check.isChecked()
        }


class CameraCard(QFrame):
    """
    GUI card element representing a single camera instance.
    Includes connection stats, control toggles, and direct video render output.
    """
    def __init__(self, camera, manager, parent=None):
        super().__init__(parent)
        self.camera = camera
        self.manager = manager
        self.pipeline_ref = None
        self.setProperty("class", "CameraCard")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header Info (Name & Badges)
        header = QHBoxLayout()
        self.name_label = QLabel(self.camera.get("name", "Camera"))
        self.name_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #ffffff;")
        
        self.status_badge = QLabel("Stopped")
        self.status_badge.setStyleSheet("color: #8E93B3; font-weight: bold; background-color: #23273A; padding: 2px 6px; border-radius: 3px;")
        
        header.addWidget(self.name_label)
        header.addStretch()
        header.addWidget(self.status_badge)
        layout.addLayout(header)

        # Direct Video Overlay Widget (renders via GStreamer Sync Window Handle)
        self.video_overlay = GstVideoOverlayWidget()
        self.video_overlay.setMinimumHeight(180)
        layout.addWidget(self.video_overlay)

        # Control and Status Bottom Bar
        bottom = QHBoxLayout()
        
        # Stream parameters display
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #8E93B3; font-size: 11px;")
        bottom.addWidget(self.stats_label)
        
        bottom.addStretch()
        
        # Toggle Power Switch
        self.toggle_btn = QPushButton("Start Route")
        self.toggle_btn.setProperty("class", "PrimaryButton")
        self.toggle_btn.setFixedWidth(100)
        self.toggle_btn.clicked.connect(self.toggle_stream)
        bottom.addWidget(self.toggle_btn)
        
        layout.addLayout(bottom)

        # Sync GUI state on initialization
        if self.manager.is_streaming(self.camera["id"]):
            self.set_streaming_ui(True)
            self.bind_signals()
        else:
            self.set_streaming_ui(False)

    def toggle_stream(self):
        cam_id = self.camera["id"]
        if self.manager.is_streaming(cam_id):
            self.manager.stop_camera(cam_id)
            self.set_streaming_ui(False)
            self.pipeline_ref = None
        else:
            # Pass our native window handle to GStreamer
            win_id = self.video_overlay.winId()
            pipeline = self.manager.start_camera(cam_id, win_id)
            if pipeline:
                self.pipeline_ref = pipeline
                self.bind_signals()
                self.set_streaming_ui(True)

    def bind_signals(self):
        cam_id = self.camera["id"]
        if cam_id in self.manager.active_pipelines:
            pipe = self.manager.active_pipelines[cam_id]
            pipe.status_changed.connect(self.on_status_changed)
            pipe.stats_updated.connect(self.on_stats_updated)
            pipe.error_occurred.connect(self.on_error_occurred)

    def set_streaming_ui(self, is_streaming):
        if is_streaming:
            self.status_badge.setText("Streaming")
            self.status_badge.setStyleSheet("color: #ffffff; font-weight: bold; background-color: #0078FF; padding: 2px 6px; border-radius: 3px;")
            self.toggle_btn.setText("Stop Route")
            self.toggle_btn.setStyleSheet("background-color: #D32F2F;")
        else:
            self.status_badge.setText("Stopped")
            self.status_badge.setStyleSheet("color: #8E93B3; font-weight: bold; background-color: #23273A; padding: 2px 6px; border-radius: 3px;")
            self.toggle_btn.setText("Start Route")
            self.toggle_btn.setStyleSheet("")
            self.stats_label.setText("")

    @Slot(str, str)
    def on_status_changed(self, cam_id, status):
        if cam_id == self.camera["id"]:
            self.status_badge.setText(status)
            if status == "Streaming":
                self.set_streaming_ui(True)
            elif status == "Stopped":
                self.set_streaming_ui(False)
            elif status == "Connection Lost":
                self.status_badge.setStyleSheet("color: white; font-weight: bold; background-color: #E65100; padding: 2px 6px; border-radius: 3px;")

    @Slot(str, float, float)
    def on_stats_updated(self, cam_id, fps, bitrate):
        if cam_id == self.camera["id"]:
            self.stats_label.setText(f"{fps:.1f} fps  |  {bitrate:.0f} kbps")

    @Slot(str, str)
    def on_error_occurred(self, cam_id, error_msg):
        if cam_id == self.camera["id"]:
            self.stats_label.setText("Error: Stream Unavailable")


class CAMOMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.manager = CameraManager()
        self.setWindowTitle("CAMO - Low Latency RTSP Router")
        self.resize(1000, 680)
        self.setStyleSheet(STYLING)
        
        self.init_ui()
        self.setup_tray()
        
        # Check if started minimized
        if "--minimized" in sys.argv or self.manager.get_settings().get("start_minimized", False):
            self.hide()
        else:
            self.show()

    def init_ui(self):
        # Central Main Widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Left Sidebar Navigation
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 15, 0, 15)
        sidebar_layout.setSpacing(5)

        # App Logo & Branding
        brand_layout = QHBoxLayout()
        brand_layout.setContentsMargins(20, 10, 20, 20)
        logo_label = QLabel("CAMO")
        logo_label.setStyleSheet("font-size: 22px; font-weight: 800; color: #00D2FF; letter-spacing: 1px;")
        brand_layout.addWidget(logo_label)
        sidebar_layout.addLayout(brand_layout)

        # Menu Navigation Buttons
        self.menu_group = []
        self.dash_btn = QPushButton("  Dashboard")
        self.dash_btn.setCheckable(True)
        self.dash_btn.setChecked(True)
        self.dash_btn.setProperty("class", "MenuButton")
        self.dash_btn.clicked.connect(lambda: self.switch_tab(0))
        self.menu_group.append(self.dash_btn)
        sidebar_layout.addWidget(self.dash_btn)

        self.cams_btn = QPushButton("  Manage Cameras")
        self.cams_btn.setCheckable(True)
        self.cams_btn.setProperty("class", "MenuButton")
        self.cams_btn.clicked.connect(lambda: self.switch_tab(1))
        self.menu_group.append(self.cams_btn)
        sidebar_layout.addWidget(self.cams_btn)

        self.net_btn = QPushButton("  Network Selection")
        self.net_btn.setCheckable(True)
        self.net_btn.setProperty("class", "MenuButton")
        self.net_btn.clicked.connect(lambda: self.switch_tab(2))
        self.menu_group.append(self.net_btn)
        sidebar_layout.addWidget(self.net_btn)

        self.settings_btn = QPushButton("  System Settings")
        self.settings_btn.setCheckable(True)
        self.settings_btn.setProperty("class", "MenuButton")
        self.settings_btn.clicked.connect(lambda: self.switch_tab(3))
        self.menu_group.append(self.settings_btn)
        sidebar_layout.addWidget(self.settings_btn)

        sidebar_layout.addStretch()
        
        # System Tray indicator in sidebar
        v4l2_status = QLabel("v4l2loopback: LOADED" if is_v4l2loopback_loaded() else "v4l2loopback: MISSING")
        v4l2_status.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: bold; margin-left: 20px;" if is_v4l2loopback_loaded() else "color: #F44336; font-size: 11px; font-weight: bold; margin-left: 20px;")
        sidebar_layout.addWidget(v4l2_status)
        
        main_layout.addWidget(sidebar, stretch=1)

        # 2. Main Tabbed Content Area
        self.stack = QStackedWidget()
        
        # Build views
        self.create_dashboard_view()
        self.create_cameramanage_view()
        self.create_network_view()
        self.create_system_view()
        
        main_layout.addWidget(self.stack, stretch=4)

    def switch_tab(self, index):
        for i, btn in enumerate(self.menu_group):
            btn.setChecked(i == index)
        self.stack.setCurrentIndex(index)
        
        # Refresh camera lists or devices on switch
        if index == 0:
            self.refresh_dashboard()
        elif index == 1:
            self.refresh_camera_list()

    def create_dashboard_view(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)

        # Header section
        header = QHBoxLayout()
        title = QLabel("Dashboard Live Feeds")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #ffffff;")
        header.addWidget(title)
        
        header.addStretch()
        
        start_all = QPushButton("Start All Streams")
        start_all.setProperty("class", "PrimaryButton")
        start_all.clicked.connect(self.start_all_pipelines)
        
        stop_all = QPushButton("Stop All Streams")
        stop_all.setProperty("class", "DangerButton")
        stop_all.clicked.connect(self.stop_all_pipelines)
        
        header.addWidget(start_all)
        header.addWidget(stop_all)
        layout.addLayout(header)

        # Scroll Area for Camera Cards Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(20)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll.setWidget(self.grid_widget)
        layout.addWidget(scroll)
        
        self.refresh_dashboard()
        self.stack.addWidget(page)

    def refresh_dashboard(self):
        # Clear existing grid widgets
        for i in reversed(range(self.grid_layout.count())): 
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        cameras = self.manager.get_cameras()
        if not cameras:
            no_cam_label = QLabel("No registered cameras. Please visit 'Manage Cameras' tab to add streams.")
            no_cam_label.setStyleSheet("color: #8E93B3; font-size: 14px;")
            self.grid_layout.addWidget(no_cam_label, 0, 0)
            return

        row, col = 0, 0
        for cam in cameras:
            card = CameraCard(cam, self.manager, self)
            self.grid_layout.addWidget(card, row, col)
            col += 1
            if col > 1: # 2 columns grid
                col = 0
                row += 1

    def create_cameramanage_view(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)

        # Header
        header = QHBoxLayout()
        title = QLabel("Manage Cameras")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #ffffff;")
        header.addWidget(title)
        
        header.addStretch()
        
        add_btn = QPushButton("Add New Camera")
        add_btn.setProperty("class", "PrimaryButton")
        add_btn.clicked.connect(self.on_add_camera)
        header.addWidget(add_btn)
        layout.addLayout(header)

        # Camera list table/cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setSpacing(12)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll.setWidget(self.list_widget)
        layout.addWidget(scroll)
        
        self.refresh_camera_list()
        self.stack.addWidget(page)

    def refresh_camera_list(self):
        # Clear items
        for i in reversed(range(self.list_layout.count())):
            widget = self.list_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        cameras = self.manager.get_cameras()
        if not cameras:
            empty = QLabel("Click 'Add New Camera' to register a stream.")
            empty.setStyleSheet("color: #8E93B3; font-size: 14px;")
            self.list_layout.addWidget(empty)
            return

        for cam in cameras:
            item = QFrame()
            item.setStyleSheet("background-color: #1A1C29; border: 1px solid #23273A; border-radius: 6px;")
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(15, 12, 15, 12)
            
            desc = QVBoxLayout()
            name = QLabel(cam["name"])
            name.setStyleSheet("font-weight: bold; font-size: 14px; color: #ffffff; border: none;")
            url = QLabel(cam["rtsp_url"])
            url.setStyleSheet("color: #8E93B3; font-size: 12px; border: none;")
            desc.addWidget(name)
            desc.addWidget(url)
            item_layout.addLayout(desc)
            
            item_layout.addStretch()
            
            # Displays target mapping (PipeWire / V4L2 device)
            targets = []
            if cam.get("enable_pipewire", True):
                targets.append("PipeWire")
            if cam.get("enable_v4l2", True) and cam.get("device"):
                targets.append(cam["device"])
            target_lbl = QLabel(" → " + " | ".join(targets) if targets else " (Unrouted)")
            target_lbl.setStyleSheet("color: #00D2FF; font-weight: bold; border: none;")
            item_layout.addWidget(target_lbl)
            
            item_layout.addSpacing(20)
            
            # Action Buttons
            edit_btn = QPushButton("Edit")
            edit_btn.setProperty("class", "SecondaryButton")
            edit_btn.clicked.connect(lambda checked=False, c=cam: self.on_edit_camera(c))
            
            del_btn = QPushButton("Delete")
            del_btn.setProperty("class", "DangerButton")
            del_btn.clicked.connect(lambda checked=False, c_id=cam["id"]: self.on_delete_camera(c_id))
            
            item_layout.addWidget(edit_btn)
            item_layout.addWidget(del_btn)
            
            self.list_layout.addWidget(item)
            
        self.list_layout.addStretch()

    def create_network_view(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)

        title = QLabel("Network Select Configuration")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)

        desc = QLabel("Configure network interfaces to bind streams or restrict camera connections. Routes are implemented via policykit static routes to prevent GStreamer multi-interface leakage.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8E93B3; line-height: 18px;")
        layout.addWidget(desc)

        form = QFrame()
        form.setStyleSheet("background-color: #1A1C29; border: 1px solid #23273A; border-radius: 8px;")
        form_layout = QFormLayout(form)
        form_layout.setContentsMargins(20, 20, 20, 20)
        form_layout.setSpacing(15)

        self.ip_family_combo = QComboBox()
        self.ip_family_combo.addItem("IPv4 and IPv6 (Default)", "both")
        self.ip_family_combo.addItem("IPv4 Only", "ipv4")
        self.ip_family_combo.addItem("IPv6 Only", "ipv6")
        form_layout.addRow("Preferred IP Family:", self.ip_family_combo)

        # Show current detected local network interfaces
        interfaces_area = QVBoxLayout()
        interfaces = get_network_interfaces()
        if not interfaces:
            interfaces_area.addWidget(QLabel("No network interfaces detected."))
        else:
            for iface in interfaces:
                lbl = QLabel(f"• {iface['name']}: {iface['ip']} ({iface['family']})")
                lbl.setStyleSheet("color: #B0B5D0; font-size: 12px; border: none; background-color: transparent;")
                interfaces_area.addWidget(lbl)
                
        form_layout.addRow("Available Adapters:", interfaces_area)
        layout.addWidget(form)

        # Load kernel v4l2loopback loader helper inside Network page for visibility
        v4l2_panel = QFrame()
        v4l2_panel.setStyleSheet("background-color: #1A1C29; border: 1px solid #23273A; border-radius: 8px;")
        v4l2_layout = QVBoxLayout(v4l2_panel)
        v4l2_layout.setContentsMargins(20, 20, 20, 20)
        v4l2_layout.setSpacing(12)
        
        v4l2_title = QLabel("Virtual Camera Driver (V4L2)")
        v4l2_title.setStyleSheet("font-size: 14px; font-weight: bold; border: none; background-color: transparent;")
        v4l2_layout.addWidget(v4l2_title)
        
        self.v4l2_status_info = QLabel("Status: LOADED" if is_v4l2loopback_loaded() else "Status: MISSING (V4L2 legacy outputs will not be available)")
        self.v4l2_status_info.setStyleSheet("color: #4CAF50; border: none; background-color: transparent;" if is_v4l2loopback_loaded() else "color: #F44336; border: none; background-color: transparent;")
        v4l2_layout.addWidget(self.v4l2_status_info)
        
        self.v4l2_load_btn = QPushButton("Load v4l2loopback Driver (Requires authentication)")
        self.v4l2_load_btn.setProperty("class", "PrimaryButton")
        self.v4l2_load_btn.setEnabled(not is_v4l2loopback_loaded())
        self.v4l2_load_btn.clicked.connect(self.load_loopback_driver)
        v4l2_layout.addWidget(self.v4l2_load_btn)
        
        layout.addWidget(v4l2_panel)
        layout.addStretch()
        self.stack.addWidget(page)

    def load_loopback_driver(self):
        success, msg = load_v4l2loopback()
        if success:
            QMessageBox.information(self, "Success", "v4l2loopback loaded successfully.")
            self.v4l2_status_info.setText("Status: LOADED")
            self.v4l2_status_info.setStyleSheet("color: #4CAF50; border: none; background-color: transparent;")
            self.v4l2_load_btn.setEnabled(False)
        else:
            QMessageBox.critical(self, "Error", f"Could not load v4l2loopback:\n{msg}")

    def create_system_view(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)

        title = QLabel("System Configuration")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)

        form = QFrame()
        form.setStyleSheet("background-color: #1A1C29; border: 1px solid #23273A; border-radius: 8px;")
        form_layout = QFormLayout(form)
        form_layout.setContentsMargins(20, 20, 20, 20)
        form_layout.setSpacing(15)

        settings = self.manager.get_settings()

        self.startup_check = QCheckBox("Start CAMO automatically with Linux login")
        self.startup_check.setChecked(is_autostart_enabled())
        self.startup_check.stateChanged.connect(self.save_system_settings)
        form_layout.addRow("", self.startup_check)

        self.min_start_check = QCheckBox("Start application minimized to system tray")
        self.min_start_check.setChecked(settings.get("start_minimized", False))
        self.min_start_check.stateChanged.connect(self.save_system_settings)
        form_layout.addRow("", self.min_start_check)

        self.min_close_check = QCheckBox("Minimize window to system tray when closed")
        self.min_close_check.setChecked(settings.get("minimize_to_tray", True))
        self.min_close_check.stateChanged.connect(self.save_system_settings)
        form_layout.addRow("", self.min_close_check)

        self.gpu_check = QCheckBox("Force usage of high-performance discrete GPU")
        self.gpu_check.setChecked(settings.get("force_gpu", False))
        self.gpu_check.stateChanged.connect(self.save_system_settings)
        form_layout.addRow("", self.gpu_check)

        layout.addWidget(form)
        layout.addStretch()
        self.stack.addWidget(page)

    def save_system_settings(self):
        # Update autostart .desktop configuration
        set_autostart(self.startup_check.isChecked())
        
        # Save JSON settings
        self.manager.update_settings({
            "start_minimized": self.min_start_check.isChecked(),
            "minimize_to_tray": self.min_close_check.isChecked(),
            "force_gpu": self.gpu_check.isChecked()
        })

    def on_add_camera(self):
        dialog = AddEditCameraDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if data["name"] and data["rtsp_url"]:
                self.manager.add_camera(
                    name=data["name"],
                    rtsp_url=data["rtsp_url"],
                    device=data["device"],
                    hw_mode=data["hw_mode"],
                    network_bind=data["network_bind"],
                    enable_pipewire=data["enable_pipewire"],
                    enable_v4l2=data["enable_v4l2"]
                )
                self.refresh_camera_list()
                self.refresh_dashboard()

    def on_edit_camera(self, camera):
        dialog = AddEditCameraDialog(camera_data=camera, parent=self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            self.manager.edit_camera(
                cam_id=camera["id"],
                name=data["name"],
                rtsp_url=data["rtsp_url"],
                device=data["device"],
                hw_mode=data["hw_mode"],
                network_bind=data["network_bind"],
                enable_pipewire=data["enable_pipewire"],
                enable_v4l2=data["enable_v4l2"]
            )
            self.refresh_camera_list()
            self.refresh_dashboard()

    def on_delete_camera(self, cam_id):
        confirm = QMessageBox.question(self, "Confirm Delete", "Are you sure you want to remove this camera stream?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            self.manager.remove_camera(cam_id)
            self.refresh_camera_list()
            self.refresh_dashboard()

    def start_all_pipelines(self):
        self.manager.start_all()
        self.refresh_dashboard()

    def stop_all_pipelines(self):
        self.manager.stop_all()
        self.refresh_dashboard()

    # System Tray Integration
    def setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        
        # Create a simple default icon if assets/logo.png does not exist
        logo_path = os.path.join(os.path.dirname(sys.argv[0]), "assets", "logo.png")
        if os.path.exists(logo_path):
            self.tray.setIcon(QIcon(logo_path))
        else:
            # Standard Qt video system icon fallback
            self.tray.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
            
        self.tray_menu = QMenu()
        
        restore_action = self.tray_menu.addAction("Restore Window")
        restore_action.triggered.connect(self.show_normal)
        
        self.tray_menu.addSeparator()
        
        start_all_action = self.tray_menu.addAction("Start All Streams")
        start_all_action.triggered.connect(self.start_all_pipelines)
        
        stop_all_action = self.tray_menu.addAction("Stop All Streams")
        stop_all_action.triggered.connect(self.stop_all_pipelines)
        
        self.tray_menu.addSeparator()
        
        exit_action = self.tray_menu.addAction("Exit CAMO")
        exit_action.triggered.connect(self.exit_app)
        
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_normal()
                self.activateWindow()

    def closeEvent(self, event):
        if self.manager.get_settings().get("minimize_to_tray", True):
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "CAMO Router",
                "CAMO is running in the background minimized to the system tray.",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
        else:
            self.exit_app()

    def show_normal(self):
        self.show()
        self.setWindowState(Qt.WindowState.WindowNoState)

    def exit_app(self):
        # Stop all pipelines gracefully
        self.manager.stop_all()
        # Remove tray
        self.tray.hide()
        QApplication = sys.modules['PySide6.QtWidgets'].QApplication
        QApplication.quit()
