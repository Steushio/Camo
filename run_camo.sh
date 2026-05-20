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

# Execute application, passing through any command line arguments (e.g. --minimized)
python3 -m camo_app.main "$@"
