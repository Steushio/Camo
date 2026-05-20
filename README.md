# CAMO - Ultra Low Latency GStreamer & PipeWire Virtual Camera Router

CAMO is a high-performance, Linux-native realtime media routing layer designed to ingest multiple RTSP IP camera streams, decode them using hardware GPU acceleration, and route them with near-zero latency into modern PipeWire graphs and legacy V4L2 loopback devices. 

It is designed as a direct media injection tool for software like OBS Studio, Zoom, Discord, and Google Chrome, rather than a scene compositor.

---

## High-Level Architecture

```text
       [ RTSP Camera ]
              │
              ▼  (rtspsrc latency=0 protocols=tcp)
       [ RTP H.264 Depay ]
              │
              ▼
       [ H.264 Parser ]
              │
              ▼  (NVIDIA/VA-API Hardware Decoder)
       [ GPU HW Decoder ]
              │
              ▼  (DMA-BUF / GPU Memory)
            [ tee ]
         ┌────┴────┬──────────────┐
         ▼         ▼              ▼
    [ Video ]  [ PipeWire ]  [ V4L2 Loopback ]
    [Overlay]  [   Sink   ]  [    Sink       ]
     (Qt GUI)   (PipeWire    (/dev/video10)
    (0-copy)     Graph)     (compatibility)
```

---

## Key Features

1. **Ultra-Low Latency**: Utilizes GStreamer's `rtspsrc` with `latency=0` and TCP interleaving to ensure zero buffering delay.
2. **Zero-Copy Preview**: Uses `GstVideoOverlay` to render decoded H.264 frames directly onto PySide6 GUI window handles via GPU memory, bypassing CPU RAM copies.
3. **Dual Virtual Camera Sinks**:
   - **PipeWire Virtual Source**: Exposes streams natively to modern Wayland-compatible systems.
   - **V4L2 Webcam (`v4l2loopback`)**: Inserts frames into `/dev/video*` devices with `exclusive_caps=1` to guarantee compatibility with all legacy software (OBS, WebRTC browsers, Zoom).
4. **Interface Isolation**: Features a policykit-based IP routing mechanism to bind streams to specific physical network adapters (LAN/Wi-Fi/IPv4/IPv6).
5. **System Tray & Autostart**: Configurable minimize-to-tray behaviors and desktop startup entries to run headlessly upon boot.
6. **Discrete GPU Offloading**: Configurable PRIME offloading triggers (`__NV_PRIME_RENDER_OFFLOAD=1`, etc.) to run media tasks on discrete graphics chips.

---

## Installation

### Quick One-Line Install
To automatically download, compile dependencies, configure user-space socket bindings, and install CAMO into your desktop application menu, run the following command in your terminal:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/Steushio/Camo/master/install_camo.sh)"
```

---

### Manual Installation (From Git Clone)

#### 1. Clone the Repository
```bash
git clone https://github.com/Steushio/Camo.git
cd Camo
```

#### 2. Run Setup Script (Installs system dependencies & Python venv)
```bash
chmod +x setup_camo.sh install_camo.sh run_camo.sh
./setup_camo.sh
```

#### 3. Install Desktop Integration (Optional)
Run the desktop installer script to compile the user-space socket binder and register CAMO in your system launcher application menu:
```bash
./install_camo.sh
```
Once installed, you can launch CAMO directly from your desktop search/launcher, or simply type `camo` in any terminal!

---

## Execution

Launch the application:

```bash
./run_camo.sh
```

To run minimized in the system tray directly (e.g. for startup scripts):

```bash
./run_camo.sh --minimized
```

---

## Configuring `v4l2loopback`

CAMO requires `v4l2loopback` to expose V4L2 compatibility cameras. The GUI will prompt you for authorization to load it via PolicyKit (`pkexec`), but you can also load it manually or make it persistent.

### Manual Load
To load the module with 4 virtual devices starting at `/dev/video10` up to `/dev/video13`:

```bash
sudo modprobe v4l2loopback devices=4 video_nr=10,11,12,13 card_label="CAMO Cam 1","CAMO Cam 2","CAMO Cam 3","CAMO Cam 4" exclusive_caps=1
```

### Persistent Load (On Boot)
Create a modules load file:
```bash
echo "v4l2loopback" | sudo tee /etc/modules-load.d/v4l2loopback.conf
```

Configure module options:
```bash
echo "options v4l2loopback devices=4 video_nr=10,11,12,13 card_label=\"CAMO Cam 1\",\"CAMO Cam 2\",\"CAMO Cam 3\",\"CAMO Cam 4\" exclusive_caps=1" | sudo tee /etc/modprobe.d/v4l2loopback.conf
```

---

## Unit Testing

Run the test suite to verify configuration bindings, network parser, and pipeline construction:

```bash
source .venv/bin/activate
python -m unittest tests/test_camo.py
```
