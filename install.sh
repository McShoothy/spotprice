#!/bin/bash
#
# SpotPrice Display - Installation Script
# ========================================
# Installs dependencies and copies files to CircuitPython device.
#
# Usage: ./install.sh
#

set -e

echo "╔═══════════════════════╗"
echo "║  SpotPrice Installer  ║"
echo "╚═══════════════════════╝"
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Find CircuitPython device
find_device() {
    # Common mount points for CircuitPython
    local paths=(
        "/Volumes/CIRCUITPY"
        "/media/$USER/CIRCUITPY"
        "/run/media/$USER/CIRCUITPY"
        "/mnt/CIRCUITPY"
    )
    
    for path in "${paths[@]}"; do
        if [ -d "$path" ]; then
            echo "$path"
            return 0
        fi
    done
    
    # Try to find any volume with boot_out.txt (CircuitPython marker)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        for vol in /Volumes/*; do
            if [ -f "$vol/boot_out.txt" ]; then
                echo "$vol"
                return 0
            fi
        done
    fi
    
    return 1
}

# Step 1: Create virtual environment
echo -e "${YELLOW}[1/4]${NC} Setting up Python virtual environment..."
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    python3 -m venv "$SCRIPT_DIR/venv"
    echo -e "  ${GREEN}✓${NC} Created venv"
else
    echo -e "  ${GREEN}✓${NC} venv already exists"
fi

# Step 2: Install circup
echo -e "${YELLOW}[2/4]${NC} Installing circup..."
source "$SCRIPT_DIR/venv/bin/activate"
pip install --quiet --upgrade circup
echo -e "  ${GREEN}✓${NC} circup installed"

# Step 3: Find device
echo -e "${YELLOW}[3/4]${NC} Looking for CircuitPython device..."
DEVICE_PATH=$(find_device)

if [ -z "$DEVICE_PATH" ]; then
    echo -e "  ${RED}✗${NC} No CircuitPython device found!"
    echo
    echo "Please ensure your device is:"
    echo "  1. Connected via USB"
    echo "  2. Running CircuitPython (not in bootloader mode)"
    echo "  3. Mounted as a drive (usually named CIRCUITPY)"
    echo
    echo "If using development mode (D0 held during boot), the drive should be writable."
    exit 1
fi

echo -e "  ${GREEN}✓${NC} Found device at: $DEVICE_PATH"

# Step 4: Copy project files
echo -e "${YELLOW}[4/4]${NC} Copying files to device..."

# Copy main files
cp "$SCRIPT_DIR/boot.py" "$DEVICE_PATH/"
echo -e "  ${GREEN}✓${NC} boot.py"

cp "$SCRIPT_DIR/main.py" "$DEVICE_PATH/"
echo -e "  ${GREEN}✓${NC} main.py"

# Copy spotprice module
if [ -d "$SCRIPT_DIR/spotprice" ]; then
    rm -rf "$DEVICE_PATH/spotprice" 2>/dev/null || true
    cp -r "$SCRIPT_DIR/spotprice" "$DEVICE_PATH/"
    echo -e "  ${GREEN}✓${NC} spotprice/"
fi

# Copy font if exists
if [ -f "$SCRIPT_DIR/font.bdf" ]; then
    cp "$SCRIPT_DIR/font.bdf" "$DEVICE_PATH/"
    echo -e "  ${GREEN}✓${NC} font.bdf"
fi

# Copy settings.toml template if no settings exist
if [ ! -f "$DEVICE_PATH/settings.toml" ]; then
    if [ -f "$SCRIPT_DIR/settings.toml" ]; then
        cp "$SCRIPT_DIR/settings.toml" "$DEVICE_PATH/"
        echo -e "  ${GREEN}✓${NC} settings.toml (template)"
    fi
fi

# Step 5: Install CircuitPython libraries
echo
echo -e "${YELLOW}[5/5]${NC} Installing CircuitPython libraries with circup..."
circup install --auto
echo -e "  ${GREEN}✓${NC} Libraries installed"

# Done!
echo
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}   Installation complete!${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo
echo "Next steps:"
echo "  1. Reset the device (press reset button or unplug/replug)"
echo "  2. If WiFi not configured, scan the QR code on screen to set up"
echo "  3. Press D0 to cycle through views: Price → 8H → 24H"
echo
echo "Development mode:"
echo "  Hold D0 during boot to enable USB drive write access"
echo

# Deactivate venv
deactivate
