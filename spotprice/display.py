"""
Display management for SpotPrice Display.
"""

import time
import board
import displayio
import vectorio

from .config import (
    BLACK,
    WHITE,
    GREEN,
    LIGHT_GREEN,
    YELLOW,
    RED,
    BLUE,
    ACCENT,
    GRAY,
    PRICE_LOW,
    PRICE_MED,
    PRICE_HIGH,
    PRICE_MAX,
    DISPLAY_BRIGHTNESS,
)

# Optional dependencies
try:
    from adafruit_display_text import label
    import terminalio

    try:
        from adafruit_bitmap_font import bitmap_font

        FONT = bitmap_font.load_font("/font.bdf")
    except Exception:
        FONT = terminalio.FONT
    HAS_DISPLAY_TEXT = True
except ImportError:
    HAS_DISPLAY_TEXT = False
    FONT = None

# Hardware display
display = getattr(board, "DISPLAY", None)

# Display state
main_group = None
price_group = None
graph_group = None
price_label = None
status_label = None
title_label = None
unit_label = None
bg_palette = None


def init_display():
    """Set up the main display groups and labels."""
    global main_group, price_group, graph_group
    global price_label, status_label, title_label, unit_label
    global bg_palette

    if not display or not HAS_DISPLAY_TEXT:
        return

    display.brightness = DISPLAY_BRIGHTNESS

    main_group = displayio.Group()
    display.root_group = main_group

    # Background
    bg = displayio.Bitmap(display.width, display.height, 1)
    bg_palette = displayio.Palette(1)
    bg_palette[0] = BLACK
    main_group.append(displayio.TileGrid(bg, pixel_shader=bg_palette))

    # Title
    title_label = label.Label(FONT, text="Spot Price", color=WHITE, scale=1)
    title_label.anchor_point = (0.5, 0.0)
    title_label.anchored_position = (display.width // 2, 2)
    main_group.append(title_label)

    # Price view
    price_group = displayio.Group()
    main_group.append(price_group)

    price_label = label.Label(FONT, text="--.-", color=WHITE, scale=5)
    price_label.anchor_point = (0.5, 0.5)
    price_label.anchored_position = (display.width // 2, display.height // 2 - 5)
    price_group.append(price_label)

    unit_label = label.Label(FONT, text="c/kWh", color=WHITE, scale=1)
    unit_label.anchor_point = (0.5, 0.0)
    unit_label.anchored_position = (display.width // 2, display.height // 2 + 40)
    price_group.append(unit_label)

    # Graph view (hidden by default)
    graph_group = displayio.Group()
    graph_group.hidden = True
    main_group.append(graph_group)

    # Status bar
    status_label = label.Label(FONT, text="Booting...", color=WHITE, scale=1)
    status_label.anchor_point = (0.5, 1.0)
    status_label.anchored_position = (display.width // 2, display.height - 2)
    main_group.append(status_label)


def get_price_color(price):
    """Determine background and text colors based on electricity price."""
    if price < 0:
        return BLUE, WHITE
    if price < PRICE_LOW:
        return GREEN, BLACK
    if price < PRICE_MED:
        return LIGHT_GREEN, BLACK
    if price >= PRICE_MAX:
        return RED, WHITE

    ratio = (price - PRICE_MED) / (PRICE_MAX - PRICE_MED)
    r = int(102 + (255 - 102) * ratio)
    g = int(255 - 255 * ratio)
    b = int(102 - 102 * ratio)
    bg_color = (r << 16) | (g << 8) | b
    text_color = WHITE if price > 12 else BLACK
    return bg_color, text_color


def show_price(price):
    """Display the current price with color-coded background."""
    if not display or not HAS_DISPLAY_TEXT:
        return

    price_group.hidden = False
    graph_group.hidden = True

    price_label.text = f"{price:.1f}c" if price > 1 else f"{price:.2f}"

    bg_color, text_color = get_price_color(price)
    bg_palette[0] = bg_color
    price_label.color = text_color
    title_label.color = text_color
    unit_label.color = text_color
    status_label.color = text_color


def show_graph(prices, now_index=0):
    """Display a smooth curve graph of prices with optional now marker position."""
    if not display or not HAS_DISPLAY_TEXT:
        return

    price_group.hidden = True
    graph_group.hidden = False

    bg_palette[0] = BLACK
    title_label.color = WHITE
    status_label.color = WHITE

    while len(graph_group) > 0:
        graph_group.pop()

    if not prices or len(prices) < 2:
        return

    # Calculate min/max for title bar display
    min_price = min(prices)
    max_price = max(prices)

    # Add min/max labels to title bar (left and right of title)
    min_title_lbl = label.Label(FONT, text=f"{min_price:.1f}", color=GREEN, scale=1)
    min_title_lbl.anchor_point = (0.0, 0.0)
    min_title_lbl.anchored_position = (4, 2)
    graph_group.append(min_title_lbl)

    max_title_lbl = label.Label(FONT, text=f"{max_price:.1f}", color=RED, scale=1)
    max_title_lbl.anchor_point = (1.0, 0.0)
    max_title_lbl.anchored_position = (display.width - 4, 2)
    graph_group.append(max_title_lbl)

    # Graph dimensions
    graph_left = 8
    graph_right = display.width - 8
    graph_top = 28
    graph_bottom = display.height - 22
    graph_width = graph_right - graph_left
    graph_height = graph_bottom - graph_top

    # Calculate scale
    min_price = min(prices)
    max_price = max(prices)
    price_range = max(max_price - min_price, 1.0)
    padding = price_range * 0.1
    min_price_display = max(0, min_price - padding)
    max_price_display = max_price + padding
    price_range = max_price_display - min_price_display

    # Draw horizontal line at min price
    min_y = int(
        graph_bottom - ((min_price - min_price_display) / price_range) * graph_height
    )
    min_line_pal = displayio.Palette(1)
    min_line_pal[0] = 0x004400
    for x in range(graph_left, graph_right, 4):
        dash = vectorio.Rectangle(
            pixel_shader=min_line_pal, width=2, height=1, x=x, y=min_y
        )
        graph_group.append(dash)

    # Draw horizontal line at max price
    max_y = int(
        graph_bottom - ((max_price - min_price_display) / price_range) * graph_height
    )
    max_line_pal = displayio.Palette(1)
    max_line_pal[0] = 0x440000
    for x in range(graph_left, graph_right, 4):
        dash = vectorio.Rectangle(
            pixel_shader=max_line_pal, width=2, height=1, x=x, y=max_y
        )
        graph_group.append(dash)

    # Calculate x positions
    num_points = len(prices)
    x_step = graph_width / (num_points - 1) if num_points > 1 else graph_width

    # Convert prices to screen coordinates
    points = []
    for i, price in enumerate(prices):
        x = int(graph_left + i * x_step)
        y = int(
            graph_bottom - ((price - min_price_display) / price_range) * graph_height
        )
        y = max(graph_top, min(graph_bottom, y))
        points.append((x, y))

    # Draw filled area under curve
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]

        avg_price = (prices[i] + prices[i + 1]) / 2
        if avg_price < PRICE_MED:
            fill_color = 0x003322
        elif avg_price < PRICE_HIGH:
            fill_color = 0x332200
        else:
            fill_color = 0x330000

        for x in range(x1, x2 + 1):
            if x2 != x1:
                t = (x - x1) / (x2 - x1)
                y = int(y1 + t * (y2 - y1))
            else:
                y = y1

            if graph_bottom > y:
                fill_pal = displayio.Palette(1)
                fill_pal[0] = fill_color
                line = vectorio.Rectangle(
                    pixel_shader=fill_pal, width=1, height=graph_bottom - y, x=x, y=y
                )
                graph_group.append(line)

    # Draw the curve line on top
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]

        avg_price = (prices[i] + prices[i + 1]) / 2
        if avg_price < PRICE_MED:
            line_color = GREEN
        elif avg_price < PRICE_HIGH:
            line_color = YELLOW
        else:
            line_color = RED

        dx = x2 - x1
        dy = y2 - y1
        steps = max(abs(dx), abs(dy), 1)

        line_pal = displayio.Palette(1)
        line_pal[0] = line_color

        for step in range(steps + 1):
            t = step / steps if steps > 0 else 0
            x = int(x1 + t * dx)
            y = int(y1 + t * dy)
            dot = vectorio.Rectangle(
                pixel_shader=line_pal, width=2, height=2, x=x, y=y - 1
            )
            graph_group.append(dot)

    # Draw current price marker at now_index position
    if points and now_index < len(points):
        marker_pal = displayio.Palette(1)
        marker_pal[0] = WHITE
        now_x, now_y = points[now_index]
        marker = vectorio.Rectangle(
            pixel_shader=marker_pal, width=4, height=4, x=now_x - 2, y=now_y - 2
        )
        graph_group.append(marker)

        # Draw vertical "now" line
        now_line_pal = displayio.Palette(1)
        now_line_pal[0] = ACCENT
        for y_pos in range(graph_top, graph_bottom, 3):
            dot = vectorio.Rectangle(
                pixel_shader=now_line_pal, width=1, height=2, x=now_x, y=y_pos
            )
            graph_group.append(dot)

    # Time labels - dynamic interval based on graph duration
    total_hours = (len(prices) * 15) // 60
    now_struct = time.localtime()
    current_hour = now_struct.tm_hour

    # Calculate hours shown before "now"
    past_hours = (now_index * 15) // 60

    # Choose interval: 2h for <=8h graphs, 6h for longer
    if total_hours <= 10:
        hour_interval = 2
    else:
        hour_interval = 6

    # "now" label at the now_index position
    if now_index < len(points):
        now_x = points[now_index][0]
        now_lbl = label.Label(FONT, text="now", color=ACCENT, scale=1)
        now_lbl.anchor_point = (0.5, 0.0)
        now_lbl.anchored_position = (now_x, graph_bottom + 4)
        graph_group.append(now_lbl)

    # Hour markers relative to now position
    for h in range(-past_hours, total_hours - past_hours, hour_interval):
        if h == 0:  # Skip 0, we have "now" label
            continue
        slots_from_now = h * 4  # 4 slots per hour
        slot_index = now_index + slots_from_now
        if 0 <= slot_index < len(prices):
            x_pos = int(graph_left + slot_index * x_step)
            future_hour = (current_hour + h) % 24

            tick_pal = displayio.Palette(1)
            tick_pal[0] = GRAY
            tick = vectorio.Rectangle(
                pixel_shader=tick_pal, width=1, height=4, x=x_pos, y=graph_bottom
            )
            graph_group.append(tick)

            hour_lbl = label.Label(FONT, text=f"{future_hour:02d}", color=GRAY, scale=1)
            hour_lbl.anchor_point = (0.5, 0.0)
            hour_lbl.anchored_position = (x_pos, graph_bottom + 4)
            graph_group.append(hour_lbl)


def show_status(message):
    """Update the status bar text."""
    if status_label:
        status_label.text = message


def set_title(text):
    """Update the title text."""
    if title_label:
        title_label.text = text
