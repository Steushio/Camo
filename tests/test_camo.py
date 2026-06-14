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
    def test_pipeline_generation_nvidia(self):
        config = {
            "name": "Nvidia Cam",
            "rtsp_url": "rtsp://192.168.1.100/stream",
            "device": "/dev/video10",
            "hw_mode": "nvidia",
            "network_bind": "default",
            "enable_pipewire": True,
            "enable_v4l2": True
        }
        
        # Construct pipeline and inspect generated string
        cam_pipeline = CameraPipeline("test_nvidia", config)
        pipe_str = cam_pipeline.get_pipeline_string()
        
        # avdec_h264 is strictly used
        self.assertIn("avdec_h264", pipe_str)
        # PipeWire sink must be populated with camera name
        self.assertIn("pipewiresink", pipe_str)
        self.assertIn('client-name="Nvidia Cam"', pipe_str)
        # V4L2 feeder appsink must be present on Linux instead of direct v4l2sink
        self.assertIn("appsink name=v4l2_feeder", pipe_str)

    def test_pipeline_generation_vaapi(self):
        config = {
            "name": "VAAPI Cam",
            "rtsp_url": "rtsp://192.168.1.100/stream",
            "device": "/dev/video11",
            "hw_mode": "vaapi",
            "network_bind": "default",
            "enable_pipewire": True,
            "enable_v4l2": False
        }
        
        cam_pipeline = CameraPipeline("test_vaapi", config)
        pipe_str = cam_pipeline.get_pipeline_string()
        
        self.assertIn("avdec_h264", pipe_str)
        self.assertIn("pipewiresink", pipe_str)
        self.assertNotIn("appsink name=v4l2_feeder", pipe_str) # V4L2 output disabled


if __name__ == '__main__':
    unittest.main()
