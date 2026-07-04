import unittest
from unittest.mock import patch, MagicMock
import os
import json
import tempfile
import shutil

# Mock GStreamer before importing modules that depend on it
import sys
sys.modules['gi'] = MagicMock()
sys.modules['gi.repository'] = MagicMock()
sys.modules['gi.repository.Gst'] = MagicMock()
sys.modules['gi.repository.GstVideo'] = MagicMock()
sys.modules['gi.repository.GLib'] = MagicMock()

from camo_app.network_utils import get_network_interfaces
from camo_app.camera_manager import CameraPipeline

class TestCAMONetworkUtils(unittest.TestCase):
    @patch('subprocess.run')
    @patch('os.name', 'posix')
    def test_get_network_interfaces_linux(self, mock_run):
        # Mock successful Linux 'ip -o addr show' output
        mock_output = (
            "1: lo    inet 127.0.0.1/8 scope host lo\\       valid_lft forever preferred_lft forever\n"
            "2: eth0    inet 192.168.1.5/24 brd 192.168.1.255 scope global eth0\\       valid_lft forever preferred_lft forever\n"
            "2: eth0    inet6 fe80::a00:27ff:fe8e:e8d2/64 scope link \\       valid_lft forever preferred_lft forever\n"
            "3: wlan0    inet 192.168.1.50/24 brd 192.168.1.255 scope global wlan0\\       valid_lft forever preferred_lft forever\n"
        )
        mock_run.return_value = MagicMock(stdout=mock_output, returncode=0)

        interfaces = get_network_interfaces()
        
        # Should have 3 interfaces (excluding loopback)
        self.assertEqual(len(interfaces), 3)
        
        # Verify first interface (eth0 IPv4)
        self.assertEqual(interfaces[0]["raw_name"], "eth0")
        self.assertEqual(interfaces[0]["family"], "IPv4")
        self.assertEqual(interfaces[0]["ip"], "192.168.1.5")
        self.assertEqual(interfaces[0]["name"], "[Ethernet] eth0")

        # Verify second interface (eth0 IPv6)
        self.assertEqual(interfaces[1]["raw_name"], "eth0")
        self.assertEqual(interfaces[1]["family"], "IPv6")
        
        # Verify third interface (wlan0 IPv4)
        self.assertEqual(interfaces[2]["raw_name"], "wlan0")
        self.assertEqual(interfaces[2]["name"], "[Wi-Fi] wlan0")
        self.assertEqual(interfaces[2]["ip"], "192.168.1.50")


class TestCAMOPipelineBuilder(unittest.TestCase):
    def test_pipeline_generation_basic(self):
        config = {
            "name": "Standard Cam",
            "rtsp_url": "rtsp://192.168.1.100/stream",
            "device": "/dev/video10",
            "network_bind": "default",
            "enable_pipewire": True,
            "enable_v4l2": True,
            "enable_preview": True
        }
        
        # Construct pipeline and inspect generated string
        cam_pipeline = CameraPipeline("test_standard", config)
        pipe_str = cam_pipeline.get_pipeline_string()
        
        # Verify GStreamer elements and optimized properties
        self.assertIn("avdec_h264 max-threads=1", pipe_str)
        self.assertIn("rtspsrc location=\"rtsp://192.168.1.100/stream\"", pipe_str)
        self.assertIn("latency=100", pipe_str)
        self.assertIn("protocols=tcp", pipe_str)
        self.assertIn("timeout=5000000", pipe_str)
        self.assertIn("rtph264depay request-keyframe=true", pipe_str)
        self.assertIn("videoscale method=0", pipe_str)
        self.assertIn("leaky=downstream", pipe_str)
        
        # PipeWire sink must be populated with camera name
        self.assertIn("pipewiresink", pipe_str)
        self.assertIn('client-name="Standard Cam"', pipe_str)
        
        # Linux V4L2 appsink feeder must be present
        self.assertIn("appsink name=v4l2_feeder", pipe_str)

    def test_pipeline_generation_disabled_v4l2(self):
        config = {
            "name": "VAAPI Cam",
            "rtsp_url": "rtsp://192.168.1.100/stream",
            "device": "/dev/video11",
            "network_bind": "default",
            "enable_pipewire": True,
            "enable_v4l2": False,
            "enable_preview": True
        }
        
        cam_pipeline = CameraPipeline("test_no_v4l2", config)
        pipe_str = cam_pipeline.get_pipeline_string()
        
        self.assertIn("pipewiresink", pipe_str)
        self.assertNotIn("appsink name=v4l2_feeder", pipe_str)


if __name__ == '__main__':
    unittest.main()
