#!/usr/bin/env bash
# ==============================================================================
# CAMO Setup Script
# Installs GStreamer, PipeWire, V4L2 loopback modules, and sets up Python venv.
# ==============================================================================

set -e

echo "====================================================="
echo " Installing System Dependencies for CAMO"
echo "====================================================="

# Update package lists
sudo apt-get update

# Install GStreamer core and plugins (essential for low-latency RTSP and HW decoders)
sudo apt-get install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev

# Install GStreamer PipeWire and V4L2 sinks
sudo apt-get install -y \
    gstreamer1.0-pipewire \
    v4l2loopback-dkms \
    v4l2loopback-utils

# Install Python and PyGObject system packages
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gst-rtsp-server-1.0 \
    policykit-1

# Add current user to video group to access webcam devices without sudo
echo "Configuring webcam device permissions..."
sudo usermod -aG video "$USER"

echo "====================================================="
echo " Creating Virtual Environment"
echo "====================================================="

# Create venv with system site packages enabled
# This allows the virtual environment to import system-compiled 'gi' (PyGObject) 
# and GStreamer wrappers, which prevents compilation issues during pip install.
python3 -m venv .venv --system-site-packages

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install PySide6
pip install PySide6

echo "====================================================="
echo " CAMO Installation Complete!"
echo "====================================================="
echo "1. To load the virtual camera kernel module, run:"
echo "   sudo modprobe v4l2loopback exclusive_caps=1"
echo "2. Run CAMO using:"
echo "   ./run_camo.sh"
echo "====================================================="
