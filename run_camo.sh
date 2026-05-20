#!/usr/bin/env bash
# ==============================================================================
# CAMO Launcher Script
# Activates the Python virtual environment and executes the main app entrypoint.
# ==============================================================================

# Find script directory path
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment (.venv) not found. Running setup..."
    ./setup_camo.sh
fi

# Activate virtual environment
source .venv/bin/activate

# Compile bind_shim.so if gcc is available
USE_PRELOAD=0
if command -v gcc >/dev/null 2>&1; then
    if [ ! -f "camo_app/bind_shim.so" ] || [ "camo_app/bind_shim.c" -nt "camo_app/bind_shim.so" ]; then
        echo "Compiling socket binder shim..."
        gcc -fPIC -shared -o camo_app/bind_shim.so camo_app/bind_shim.c -ldl
    fi
    if [ -f "camo_app/bind_shim.so" ]; then
        USE_PRELOAD=1
    fi
fi

# Execute application, passing through any command line arguments (e.g. --minimized)
if [ "$USE_PRELOAD" -eq 1 ]; then
    export CAMO_PRELOAD_ACTIVE=1
    LD_PRELOAD="$DIR/camo_app/bind_shim.so" python3 -m camo_app.main "$@"
else
    python3 -m camo_app.main "$@"
fi
