"""
Boot configuration for SpotPrice Display.

This script runs before main.py and configures the filesystem.

HOLD D0 BUTTON during boot to keep USB drive writable (for development).
Otherwise, the USB drive is hidden and the filesystem is writable by code
(so the setup portal can save WiFi credentials to settings.toml).
"""

import os
import board
import digitalio
import storage

# Check if D0 button is held during boot
btn = digitalio.DigitalInOut(board.D0)
btn.direction = digitalio.Direction.INPUT
btn.pull = digitalio.Pull.UP

if btn.value:  # Button NOT pressed (pulled high)
    # Normal mode: disable USB drive so CircuitPython can write to filesystem
    storage.disable_usb_drive()
    storage.remount("/", readonly=False)
    print("Boot: USB drive disabled, filesystem writable by code")

    # Finish a WiFi-settings save that a power cut interrupted
    files = os.listdir("/")
    if "settings.toml" not in files and "settings.toml.tmp" in files:
        os.rename("/settings.toml.tmp", "/settings.toml")
        print("Boot: restored settings.toml from interrupted save")
else:
    # Development mode: keep USB drive writable
    print("Boot: D0 held - USB drive enabled for development")

btn.deinit()  # Release the pin for use in main.py
