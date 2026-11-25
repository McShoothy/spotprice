"""
SpotPrice Display
=================
Real-time Finnish electricity spot price monitor for ESP32-S3 TFT Feather.

Displays current prices with color-coded background and 8h/24h forecast graphs.
Includes WiFi captive portal for easy configuration.

Hardware: Adafruit ESP32-S3 TFT Feather
    - D0: Mode button (cycle price / 8h graph / 24h graph)
    - D0 held during boot: Enable USB drive for development

Author: Sam
License: CC BY-NC 4.0 (non-commercial use only)
Repository: https://github.com/McShoothy/spotprice
"""

import gc
import time
import random
import ssl
import os
import rtc
import board
import wifi
import socketpool
import digitalio
import adafruit_requests
import adafruit_ntp

try:
    import adafruit_connection_manager
except ImportError:
    adafruit_connection_manager = None

from spotprice import (
    display,
    init_display,
    show_price,
    show_graph,
    show_status,
    show_message,
    set_title,
    parse_prices,
    find_current_price,
    get_prices_with_history,
    needs_wifi_setup,
    run_setup_portal,
    plan_next_fetch,
    parse_http_date,
    API_URL,
    RETRY_INTERVAL,
    RETRY_MAX,
    PUBLISH_LOCAL,
    FETCH_JITTER,
    FAST_UNTIL_LOCAL,
    GIVE_UP_LOCAL,
    RETRY_FAST,
    RETRY_SLOW,
    GRAPH_SLOTS_8H,
    GRAPH_SLOTS_24H,
    GRAPH_PAST_8H,
    GRAPH_PAST_24H,
)

SLOT_SECONDS = 15 * 60
CLOCK_VALID_AFTER = 1700000000  # RTC is still near 2000-01-01 until NTP works
NUM_VIEWS = 3  # 0 = price, 1 = 8h graph, 2 = 24h graph
BOOT_CONNECT_TRIES = 5  # WiFi attempts at boot before opening the setup portal
PORTAL_TIMEOUT = 10 * 60  # Reboot from the portal to retry saved WiFi after this

# Hardware
btn_mode = digitalio.DigitalInOut(board.D0)
btn_mode.direction = digitalio.Direction.INPUT
btn_mode.pull = digitalio.Pull.UP


def log_memory(label=""):
    """Log current memory usage for debugging."""
    gc.collect()
    free = gc.mem_free()
    alloc = gc.mem_alloc()
    total = free + alloc
    print(f"[MEM {label}] Free: {free//1024}KB / {total//1024}KB ({100*free//total}%)")


def main():
    """Main application entry point."""

    if needs_wifi_setup():
        run_setup_portal(display)
        return

    init_display()
    show_message("Connecting...")

    ssid = os.getenv("CIRCUITPY_WIFI_SSID")
    password = os.getenv("CIRCUITPY_WIFI_PASSWORD")
    # Retry a few times: after a power cut the router may still be booting
    for attempt in range(1, BOOT_CONNECT_TRIES + 1):
        try:
            wifi.radio.connect(ssid, password)
            show_message("WiFi connected")
            break
        except Exception as e:
            print(f"WiFi connection failed ({attempt}/{BOOT_CONNECT_TRIES}): {e}")
            show_message("Connecting...", f"retry {attempt}/{BOOT_CONNECT_TRIES}")
            time.sleep(min(5 * attempt, 20))
    else:
        show_message("WiFi failed", "opening setup")
        time.sleep(2)
        # Saved credentials exist, so time out and retry them later
        run_setup_portal(display, timeout=PORTAL_TIMEOUT)
        return

    pool = socketpool.SocketPool(wifi.radio)
    http = adafruit_requests.Session(pool, ssl.create_default_context())

    def wifi_on():
        """Enable WiFi (reconnect if needed)."""
        if not wifi.radio.enabled:
            wifi.radio.enabled = True
            time.sleep(0.5)
        if not wifi.radio.connected:
            wifi.radio.connect(ssid, password)

    def wifi_off():
        """Disable WiFi to save power.

        Close pooled (keep-alive) sockets first; otherwise the next fetch
        reuses a dead TLS socket and can hang until the request times out.
        """
        if adafruit_connection_manager:
            try:
                adafruit_connection_manager.connection_manager_close_all(pool)
            except Exception as e:
                print(f"Socket cleanup failed: {e}")
        wifi.radio.enabled = False

    def sync_time():
        """Set the RTC from NTP (UTC). Re-run on every fetch to correct drift."""
        try:
            rtc.RTC().datetime = adafruit_ntp.NTP(pool, tz_offset=0).datetime
            return True
        except Exception as e:
            print(f"NTP sync failed: {e}")
            return False

    def time_from_http(response):
        """Fallback when NTP is blocked: set the RTC from the HTTP Date header."""
        headers = response.headers
        ts = parse_http_date(headers.get("date") or headers.get("Date") or "")
        if ts > CLOCK_VALID_AFTER:
            rtc.RTC().datetime = time.localtime(ts)
            print("Clock set from HTTP Date header")

    def fetch_prices():
        """Sync time and fetch prices. Returns parsed slots or None."""
        response = None
        try:
            wifi_on()
            ntp_ok = sync_time()
            response = http.get(API_URL)
            if response.status_code != 200:  # e.g. 429 rate limit
                raise OSError(f"HTTP {response.status_code}")
            if not ntp_ok and time.time() < CLOCK_VALID_AFTER:
                time_from_http(response)
            data = response.json()
            slots = parse_prices(data["prices"])
            data = None
            return slots
        except Exception as e:
            print(f"Fetch error: {e}")
            return None
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
            wifi_off()
            gc.collect()

    # Per-device random offset so many devices don't all fetch at 14:05:00
    jitter = random.randint(0, FETCH_JITTER)

    # Application state
    view_mode = 0
    slots = None
    next_fetch = 0  # fetch immediately
    retry_delay = RETRY_INTERVAL
    next_slot_boundary = 0
    btn_was_pressed = False

    def refresh_display():
        """Update the display based on current mode and data."""
        if not slots:
            return
        if view_mode == 0:
            price = find_current_price(slots)
            set_title("Hinta nyt:")
            show_price(price)  # None shows a full-screen message
            return

        if view_mode == 1:
            set_title("8H")
            total, past = GRAPH_SLOTS_8H, GRAPH_PAST_8H
        else:
            set_title("24H")
            total, past = GRAPH_SLOTS_24H, GRAPH_PAST_24H
        price_list, now_idx, first_start = get_prices_with_history(
            slots, future_slots=total - past, past_slots=past
        )
        show_graph(price_list, now_idx, first_start)

    while True:
        now = time.time()

        # Mode button: act on press edge only, so holding it doesn't spin views
        pressed = not btn_mode.value
        if pressed and not btn_was_pressed:
            view_mode = (view_mode + 1) % NUM_VIEWS
            refresh_display()
        btn_was_pressed = pressed

        if now >= next_fetch:
            if slots:
                show_status("Updating...")  # keep showing current prices
            else:
                show_message("Fetching prices...")
            new_slots = fetch_prices()
            now = time.time()  # clock may have jumped after NTP sync
            if new_slots:
                slots = None
                gc.collect()
                slots = new_slots
                if now < CLOCK_VALID_AFTER:
                    # No valid clock (NTP and HTTP Date both failed): can't
                    # tell which prices are current. Back off, don't hammer.
                    next_fetch = now + retry_delay
                    retry_delay = min(retry_delay * 2, RETRY_MAX)
                else:
                    retry_delay = RETRY_INTERVAL
                    next_fetch = plan_next_fetch(
                        now,
                        slots[-1][1],
                        PUBLISH_LOCAL,
                        FAST_UNTIL_LOCAL,
                        GIVE_UP_LOCAL,
                        RETRY_FAST,
                        RETRY_SLOW,
                        jitter,
                    )
                print(
                    f"Cached {len(slots)} slots, next fetch in {(next_fetch - now) // 60} min"
                )
                log_memory("after fetch")
                show_status("")
                refresh_display()
                next_slot_boundary = now - now % SLOT_SECONDS + SLOT_SECONDS
            else:
                if slots:
                    show_status("Update failed")
                else:
                    show_message("Fetch failed", f"retrying in {retry_delay} s")
                next_fetch = now + retry_delay
                retry_delay = min(retry_delay * 2, RETRY_MAX)

        elif slots and now >= next_slot_boundary:
            # New 15-minute price slot started
            next_slot_boundary = now - now % SLOT_SECONDS + SLOT_SECONDS
            refresh_display()

        time.sleep(0.05)


if __name__ == "__main__":
    main()
