#!/usr/bin/env bash
# ==============================================================================
# CAMO Desktop Installer Script
# ==============================================================================

# Ensure script halts on errors
set -e

# Find current script directory (absolute path)
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "====================================================="
echo " Installing CAMO Desktop Application"
echo "====================================================="

# Check virtual environment
if [ ! -d ".venv" ]; then
    echo "Virtual environment (.venv) not found. Running setup..."
    ./setup_camo.sh
fi

# Ensure bind_shim.so is compiled
echo "Ensuring socket binder shim is compiled..."
if command -v gcc >/dev/null 2>&1; then
    gcc -fPIC -shared -o camo_app/bind_shim.so camo_app/bind_shim.c -ldl
else
    echo "Warning: gcc is not available. User-space binding will not be precompiled."
fi

# Create user bin directory if it doesn't exist
mkdir -p "$HOME/.local/bin"

# Create launcher wrapper script
LAUNCHER_PATH="$HOME/.local/bin/camo"
echo "Creating launcher at $LAUNCHER_PATH..."
cat << EOF > "$LAUNCHER_PATH"
#!/usr/bin/env bash
cd "$DIR"
source .venv/bin/activate
if [ -f "camo_app/bind_shim.so" ]; then
    export CAMO_PRELOAD_ACTIVE=1
    LD_PRELOAD="$DIR/camo_app/bind_shim.so" python3 -m camo_app.main "\$@"
else
    python3 -m camo_app.main "\$@"
fi
EOF

chmod +x "$LAUNCHER_PATH"

# Create application desktop entry
mkdir -p "$HOME/.local/share/applications"
DESKTOP_ENTRY_PATH="$HOME/.local/share/applications/camo.desktop"
echo "Creating desktop entry at $DESKTOP_ENTRY_PATH..."
cat << EOF > "$DESKTOP_ENTRY_PATH"
[Desktop Entry]
Name=CAMO
Comment=Low Latency RTSP Router & Virtual Camera
Exec=$LAUNCHER_PATH
Icon=$DIR/camo_app/assets/logo.png
Terminal=false
Type=Application
Categories=AudioVideo;Video;Network;
StartupNotify=true
EOF

chmod +x "$DESKTOP_ENTRY_PATH"

# Update desktop database
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications"
fi

echo "====================================================="
echo " Installation Complete!"
echo "====================================================="
echo "You can now search and launch 'CAMO' directly from"
echo "your desktop application menu or launcher!"
echo "Or run it from terminal using:"
echo "  camo"
echo "====================================================="
