"""
Boot configuration for SpotPrice Display.

This script runs before code.py and configures the filesystem.

HOLD D0 BUTTON during boot to keep USB drive writable (for development).
Otherwise, USB drive becomes read-only so CircuitPython can save WiFi credentials.
"""

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
    print("Boot: USB drive disabled, filesystem writable by code")
else:
    # Development mode: keep USB drive writable
    print("Boot: D0 held - USB drive enabled for development")

btn.deinit()  # Release the pin for use in code.py