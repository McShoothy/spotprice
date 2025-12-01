"""
SpotPrice Display
=================
Real-time Finnish electricity spot price monitor for ESP32-S3 TFT Feather.

Displays current prices with color-coded background and a 24-hour forecast graph.
Includes WiFi captive portal for easy configuration.

Hardware: Adafruit ESP32-S3 TFT Feather
    - D0: Mode button (toggle price/graph view)
    - D0 held during boot: Enable USB drive for development

Author: Sam
License: CC BY-NC 4.0 (non-commercial use only)
Repository: https://github.com/McShoothy/spotprice
"""

import time
import ssl
import os
import rtc
import board
import wifi
import socketpool
import digitalio
import adafruit_requests
import adafruit_ntp

# Import from spotprice module
from spotprice import (
    display, init_display, show_price, show_graph, show_status, set_title,
    find_current_price, get_upcoming_prices, get_prices_with_history,
    needs_wifi_setup, run_setup_portal,
    API_URL, RETRY_INTERVAL, GRAPH_SLOTS_8H, GRAPH_SLOTS_24H, DISPLAY_REFRESH, FETCH_HOURS
)

# Hardware
btn_mode = digitalio.DigitalInOut(board.D0)
btn_mode.direction = digitalio.Direction.INPUT
btn_mode.pull = digitalio.Pull.UP


def main():
    """Main application entry point."""
    
    # Check if WiFi setup is needed
    if needs_wifi_setup():
        run_setup_portal(display)
        return
    
    # Normal operation
    init_display()
    show_status("Connecting...")
    
    # Connect to WiFi
    ssid = os.getenv("CIRCUITPY_WIFI_SSID")
    try:
        wifi.radio.connect(ssid, os.getenv("CIRCUITPY_WIFI_PASSWORD"))
        show_status("WiFi OK")
    except Exception as e:
        print(f"WiFi connection failed: {e}")
        show_status("WiFi failed")
        time.sleep(2)
        run_setup_portal(display)
        return
    
    # Initialize network session
    pool = socketpool.SocketPool(wifi.radio)
    ssl_context = ssl.create_default_context()
    http = adafruit_requests.Session(pool, ssl_context)
    
    def wifi_on():
        """Enable WiFi (reconnect if needed)."""
        if not wifi.radio.enabled:
            wifi.radio.enabled = True
            time.sleep(0.5)
        if not wifi.radio.connected:
            try:
                wifi.radio.connect(ssid, os.getenv("CIRCUITPY_WIFI_PASSWORD"))
            except Exception as e:
                print(f"WiFi reconnect failed: {e}")
    
    def wifi_off():
        """Disable WiFi to save power."""
        wifi.radio.enabled = False
    
    # Synchronize time via NTP
    show_status("Syncing time...")
    try:
        ntp = adafruit_ntp.NTP(pool, tz_offset=0)
        rtc.RTC().datetime = ntp.datetime
        show_status("Time OK")
    except Exception as e:
        print(f"NTP sync failed: {e}")
        show_status("Time error")
    
    # Application state
    view_mode = 0  # 0 = price, 1 = 8h graph, 2 = 24h graph
    price_data = None
    last_fetch_time = 0
    last_display_refresh = 0
    last_price_shown = None
    
    def refresh_display():
        """Update the display based on current mode and data."""
        nonlocal last_price_shown
        
        if not price_data or "prices" not in price_data:
            return
        
        prices = price_data["prices"]
        
        if view_mode == 0:
            # Current price view
            current_price = find_current_price(prices)
            if current_price is not None:
                set_title("Hinta nyt:")
                show_price(current_price)
                last_price_shown = current_price
        elif view_mode == 1:
            # 8-hour graph (30min past + 7.5h future = 8h total)
            set_title("8H")
            price_list, now_idx = get_prices_with_history(prices, future_slots=30, past_slots=2)
            show_graph(price_list, now_idx)
        else:
            # 24-hour graph (1h past + 23h future = 24h total)
            set_title("24H")
            price_list, now_idx = get_prices_with_history(prices, future_slots=92, past_slots=4)
            show_graph(price_list, now_idx)
    
    # Main loop
    while True:
        current_time = time.time()
        
        # Handle mode button
        if not btn_mode.value:
            view_mode = (view_mode + 1) % 3
            refresh_display()
            time.sleep(0.2)
        
        # Check if it's time to fetch
        now_struct = time.localtime(current_time)
        current_hour = now_struct.tm_hour
        current_min = now_struct.tm_min
        
        should_fetch = price_data is None
        if not should_fetch and last_fetch_time > 0:
            hours_since_fetch = (current_time - last_fetch_time) / 3600
            if hours_since_fetch >= 1:
                for fetch_hour in FETCH_HOURS:
                    if current_hour == fetch_hour and current_min <= 5:
                        should_fetch = True
                        break
                    if current_hour == fetch_hour and current_min >= 55:
                        should_fetch = True
                        break
        
        if should_fetch:
            try:
                show_status("Fetching prices...")
                wifi_on()
                response = http.get(API_URL)
                price_data = response.json()
                response.close()
                wifi_off()
                last_fetch_time = current_time
                last_display_refresh = current_time
                
                if "prices" in price_data:
                    count = len(price_data["prices"])
                    print(f"Cached {count} price entries at {current_hour:02d}:{current_min:02d}")
                
                refresh_display()
                show_status("")
            except Exception as e:
                print(f"Fetch error: {e}")
                show_status("Error")
                wifi_off()
                last_fetch_time = current_time - 3600 + RETRY_INTERVAL
        
        elif (current_time - last_display_refresh) > DISPLAY_REFRESH:
            last_display_refresh = current_time
            
            if price_data and "prices" in price_data:
                current_price = find_current_price(price_data["prices"])
                if current_price != last_price_shown:
                    refresh_display()
        
        time.sleep(0.1)


if __name__ == "__main__":
    main()