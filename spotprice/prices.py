"""
Price data fetching and parsing for SpotPrice Display.
"""

import time


def parse_iso_timestamp(timestamp):
    """Parse an ISO 8601 timestamp to Unix epoch time."""
    try:
        return time.mktime(time.struct_time((
            int(timestamp[0:4]),
            int(timestamp[5:7]),
            int(timestamp[8:10]),
            int(timestamp[11:13]),
            int(timestamp[14:16]),
            int(timestamp[17:19]),
            -1, -1, 0
        )))
    except Exception:
        return 0


def find_current_price(prices):
    """Find the price for the current time slot."""
    now = time.time()
    for entry in prices:
        start = parse_iso_timestamp(entry["startDate"])
        end = parse_iso_timestamp(entry["endDate"])
        if start <= now < end:
            return entry["price"]
    return None


def get_upcoming_prices(prices, slots=24):
    """Get a list of prices for the next N 15-minute slots."""
    now = time.time()
    upcoming = []
    for entry in prices:
        if parse_iso_timestamp(entry["endDate"]) > now:
            upcoming.append((parse_iso_timestamp(entry["startDate"]), entry["price"]))
    upcoming.sort()
    return [price for _, price in upcoming[:slots]]


def get_prices_with_history(prices, future_slots=24, past_slots=4):
    """
    Get prices including some past slots for better graph visualization.
    
    Args:
        prices: List of price entries from API
        future_slots: Number of future 15-min slots to include
        past_slots: Number of past 15-min slots to include
    
    Returns:
        tuple: (price_list, now_index) where now_index is the position of current time
    """
    now = time.time()
    all_prices = []
    
    for entry in prices:
        start = parse_iso_timestamp(entry["startDate"])
        end = parse_iso_timestamp(entry["endDate"])
        all_prices.append((start, end, entry["price"]))
    
    all_prices.sort()
    
    # Find current slot index
    current_idx = 0
    for i, (start, end, price) in enumerate(all_prices):
        if start <= now < end:
            current_idx = i
            break
    
    # Get range: past_slots before current, future_slots after
    start_idx = max(0, current_idx - past_slots)
    end_idx = min(len(all_prices), current_idx + future_slots)
    
    result = [price for _, _, price in all_prices[start_idx:end_idx]]
    now_index = current_idx - start_idx  # Position of "now" in the result list
    
    return result, now_index
