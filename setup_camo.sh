#!/usr/bin/env bash
# ==============================================================================
# CAMO Setup Script
# Installs GStreamer, PipeWire, V4L2 loopback modules, and sets up Python venv.
# ==============================================================================

set -e

echo "====================================================="
echo " Installing System Dependencies for CAMO"
echo "====================================================="

# Detect package manager and install dependencies
if command -v apt-get >/dev/null 2>&1; then
    echo "Detected Debian/Ubuntu-based distribution. Installing dependencies..."
    sudo apt-get update
    sudo apt-get install -y \
        gstreamer1.0-tools \
        gstreamer1.0-plugins-base \
        gstreamer1.0-plugins-good \
        gstreamer1.0-plugins-bad \
        gstreamer1.0-plugins-ugly \
        gstreamer1.0-libav \
        libgstreamer1.0-dev \
        libgstreamer-plugins-base1.0-dev \
        gstreamer1.0-pipewire \
        v4l2loopback-dkms \
        v4l2loopback-utils \
        python3-pip \
        python3-venv \
        python3-gi \
        python3-gi-cairo \
        gir1.2-gst-rtsp-server-1.0 \
        policykit-1
        
    # Add current user to video group to access webcam devices without sudo
    echo "Configuring webcam device permissions..."
    sudo usermod -aG video "$USER"

elif command -v dnf >/dev/null 2>&1; then
    echo "Detected RedHat/Fedora-based distribution. Installing dependencies..."
    sudo dnf install -y \
        gstreamer1 \
        gstreamer1-plugins-base \
        gstreamer1-plugins-good \
        gstreamer1-plugins-bad-free \
        gstreamer1-plugins-ugly-free \
        gstreamer1-libav \
        gstreamer1-devel \
        gstreamer1-plugins-base-devel \
        pipewire-gstreamer \
        v4l2loopback \
        python3-pip \
        python3-devel \
        python3-gobject \
        polkit
        
    # Add current user to video group to access webcam devices without sudo
    echo "Configuring webcam device permissions..."
    sudo usermod -aG video "$USER"

elif command -v pacman >/dev/null 2>&1; then
    echo "Detected Arch Linux-based distribution. Installing dependencies..."
    sudo pacman -Syu --needed --noconfirm \
        gstreamer \
        gst-plugins-base \
        gst-plugins-good \
        gst-plugins-bad \
        gst-plugins-ugly \
        gst-libav \
        pipewire \
        v4l2loopback-dkms \
        v4l2loopback-utils \
        python-pip \
        python-gobject \
        polkit
        
    # Add current user to video group if not already there
    echo "Configuring webcam device permissions..."
    sudo usermod -aG video "$USER" 2>/dev/null || true
else
    echo "Unsupported distribution package manager. Please install dependencies manually."
    exit 1
fi

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
echo " Configuring v4l2loopback Virtual Camera Driver"
echo "====================================================="

# 1. Configure module options
echo "Writing module options to /etc/modprobe.d/v4l2loopback.conf..."
sudo mkdir -p /etc/modprobe.d
echo 'options v4l2loopback devices=4 video_nr=10,11,12,13 card_label="CAMO Virtual Cam 1","CAMO Virtual Cam 2","CAMO Virtual Cam 3","CAMO Virtual Cam 4" exclusive_caps=1,1,1,1' | sudo tee /etc/modprobe.d/v4l2loopback.conf > /dev/null

# 2. Configure auto-load at boot
echo "Configuring automatic driver load at boot in /etc/modules-load.d/v4l2loopback.conf..."
sudo mkdir -p /etc/modules-load.d
echo "v4l2loopback" | sudo tee /etc/modules-load.d/v4l2loopback.conf > /dev/null

# 3. Configure passwordless sudoers rule for video group
echo "Writing passwordless sudo rule to /etc/sudoers.d/camo-v4l2..."
if [ -d "/etc/sudoers.d" ]; then
    echo "%video ALL=(ALL) NOPASSWD: /sbin/modprobe v4l2loopback *, /sbin/rmmod v4l2loopback, /usr/sbin/modprobe v4l2loopback *, /usr/sbin/rmmod v4l2loopback" | sudo tee /etc/sudoers.d/camo-v4l2 > /dev/null
    sudo chmod 0440 /etc/sudoers.d/camo-v4l2
else
    echo "Warning: /etc/sudoers.d does not exist on this system. Manual passwordless sudo loading will not be configured."
fi

# 4. Load the driver immediately so it's active right now
echo "Loading v4l2loopback module immediately..."
sudo modprobe -r v4l2loopback 2>/dev/null || true
if ! sudo modprobe v4l2loopback; then
    echo "Warning: Could not load v4l2loopback module immediately (Secure Boot or DKMS issue?). It will attempt to load at boot."
else
    echo "v4l2loopback module loaded successfully with CAMO options!"
fi

echo "====================================================="
echo " CAMO Installation Complete!"
echo "====================================================="
echo "1. The v4l2loopback driver has been loaded and configured to start at boot."
echo "2. Run CAMO using:"
echo "   ./run_camo.sh"
echo "====================================================="
