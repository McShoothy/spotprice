"""
SpotPrice Display - Finnish electricity spot price monitor.
"""

from .config import *
from .display import display, init_display, show_price, show_graph, show_status, set_title
from .prices import find_current_price, get_upcoming_prices, get_prices_with_history
from .wifi_portal import needs_wifi_setup, run_setup_portal
