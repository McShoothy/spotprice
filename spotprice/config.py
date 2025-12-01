"""
Configuration constants for SpotPrice Display.
"""

# API
API_URL = "https://api.porssisahko.net/v2/latest-prices.json"
RETRY_INTERVAL = 30  # 30 seconds on error

# Access Point
AP_SSID = "SpotPrice"
AP_IP = "192.168.4.1"

# Display
GRAPH_SLOTS_8H = 32  # Number of 15-min slots for 8-hour view (32 = 8 hours)
GRAPH_SLOTS_24H = 96  # Number of 15-min slots for 24-hour view (96 = 24 hours)
DISPLAY_REFRESH = 120  # Check for price changes (prices update every 15 min)
DISPLAY_BRIGHTNESS = 0.5  # 0.0-1.0 (lower = less power, longer battery life)

# Fetch schedule (hours in UTC)
FETCH_HOURS = [0, 7, 15]  # Fetch at 00:01, 07:59, 15:59

# Price thresholds (cents/kWh)
PRICE_LOW = 1.0
PRICE_MED = 3.0
PRICE_HIGH = 8.0
PRICE_MAX = 13.0

# Display colors
BLACK = 0x000000
WHITE = 0xFFFFFF
GREEN = 0x00FF00
LIGHT_GREEN = 0x66FF66
YELLOW = 0xFFFF00
RED = 0xFF0000
BLUE = 0x0000FF
ACCENT = 0x00FF88
GRAY = 0x888888
