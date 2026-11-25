"""
SpotPrice Display - Finnish electricity spot price monitor.
"""

from .config import *
from .display import (
    display,
    init_display,
    show_price,
    show_graph,
    show_status,
    show_message,
    set_title,
)
from .prices import (
    parse_prices,
    find_current_price,
    current_slot_start,
    future_coverage,
    has_tomorrow,
    plan_next_fetch,
    parse_http_date,
    get_upcoming_prices,
    get_prices_with_history,
)
from .wifi_portal import needs_wifi_setup, run_setup_portal
