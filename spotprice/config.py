"""
Configuration constants for SpotPrice Display.
"""

# API
API_URL = "https://api.porssisahko.net/v2/latest-prices.json"
RETRY_INTERVAL = 30  # First retry after a failed request (doubles up to RETRY_MAX)
RETRY_MAX = 15 * 60

# Access Point
AP_SSID = "SpotPrice"
AP_IP = "192.168.4.1"

# Display
GRAPH_SLOTS_8H = 32  # Number of 15-min slots for 8-hour view (32 = 8 hours)
GRAPH_SLOTS_24H = 96  # Number of 15-min slots for 24-hour view (96 = 24 hours)
GRAPH_PAST_8H = 2  # Of those, how many slots are before "now"
GRAPH_PAST_24H = 4
DISPLAY_BRIGHTNESS = 0.5  # 0.0-1.0 (lower = less power, longer battery life)

# Fetch schedule, in Finnish local time (EET/EEST, DST handled).
# Nord Pool publishes tomorrow's prices ~14:00 Finnish time; porssisahko.net
# has them "from 14:00". So fetch once a day just after, plus at boot.
# If tomorrow's prices aren't in yet (Nord Pool delays happen), retry:
#   every RETRY_FAST until FAST_UNTIL, then every RETRY_SLOW until GIVE_UP.
# Today's data lasts until 01:00, so giving up for the evening is safe.
PUBLISH_LOCAL = (14, 5)  # first try (+ random 0-FETCH_JITTER s per device)
FETCH_JITTER = 10 * 60  # spread devices out instead of all hitting 14:05:00
FAST_UNTIL_LOCAL = (15, 30)  # covers normal SDAC delays (latest ~15:20)
GIVE_UP_LOCAL = (22, 0)  # covers the Nordic fallback auction (by 21:00)
RETRY_FAST = 15 * 60
RETRY_SLOW = 45 * 60

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
