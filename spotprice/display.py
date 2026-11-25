"""
Display management for SpotPrice Display.
"""

import board
import displayio
import bitmaptools

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
from .fonts import FONT, PRICE_FONT, PRICE_AA, HAS_DISPLAY_TEXT, label
from .prices import SLOT_SECONDS, local_time

# Hardware display
display = getattr(board, "DISPLAY", None)

# Graph geometry (relative to the 240x135 TFT; recomputed from display size)
GRAPH_MARGIN_X = 8
GRAPH_TOP = 28
GRAPH_BOTTOM_PAD = 22
MAX_PRICE_SCALE = 5

# Graph palette indices (0 = transparent)
_C_MIN_LINE = 1
_C_MAX_LINE = 2
_C_FILL_GREEN = 3
_C_FILL_YELLOW = 4
_C_FILL_RED = 5
_C_LINE_GREEN = 6
_C_LINE_YELLOW = 7
_C_LINE_RED = 8
_C_MARKER = 9
_C_NOW_LINE = 10
_C_TICK = 11

# Display state
main_group = None
price_group = None
graph_group = None
graph_labels = None
price_label = None
price_aa = None  # anti-aliased price (AAText), if /price.aa exists
status_label = None
title_label = None
unit_label = None
message_label = None  # full-screen message (boot, fetching, errors)
detail_label = None
bg_palette = None

# One bitmap for the whole graph, allocated once and redrawn in place.
# Far cheaper than hundreds of vectorio objects per redraw.
_graph_bitmap = None
_graph_palette = None


def _init_graph_bitmap(width, height):
    global _graph_bitmap, _graph_palette
    if _graph_bitmap is not None:
        return
    _graph_palette = displayio.Palette(12)
    _graph_palette.make_transparent(0)
    _graph_palette[_C_MIN_LINE] = 0x004400
    _graph_palette[_C_MAX_LINE] = 0x440000
    _graph_palette[_C_FILL_GREEN] = 0x003322
    _graph_palette[_C_FILL_YELLOW] = 0x332200
    _graph_palette[_C_FILL_RED] = 0x330000
    _graph_palette[_C_LINE_GREEN] = GREEN
    _graph_palette[_C_LINE_YELLOW] = YELLOW
    _graph_palette[_C_LINE_RED] = RED
    _graph_palette[_C_MARKER] = WHITE
    _graph_palette[_C_NOW_LINE] = ACCENT
    _graph_palette[_C_TICK] = GRAY
    _graph_bitmap = displayio.Bitmap(width, height, 12)


def init_display():
    """Set up the main display groups and labels."""
    global main_group, price_group, graph_group, graph_labels
    global price_label, status_label, title_label, unit_label, price_aa
    global message_label, detail_label
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

    price_label = label.Label(PRICE_FONT or FONT, text="--.-", color=WHITE, scale=1)
    price_label.anchor_point = (0.5, 0.5)
    price_label.anchored_position = (display.width // 2, display.height // 2 - 5)
    price_group.append(price_label)

    if PRICE_AA is not None:
        from .aatext import AAText

        price_aa = AAText(PRICE_AA, display.width, display.height // 2 - 5)
        price_group.append(price_aa.tilegrid)
        price_label.hidden = True

    unit_label = label.Label(FONT, text="c/kWh", color=WHITE, scale=1)
    unit_label.anchor_point = (0.5, 0.0)
    unit_label.anchored_position = (display.width // 2, display.height // 2 + 40)
    price_group.append(unit_label)

    # Graph view (hidden by default)
    graph_group = displayio.Group()
    graph_group.hidden = True
    main_group.append(graph_group)

    gw = display.width - 2 * GRAPH_MARGIN_X
    gh = display.height - GRAPH_BOTTOM_PAD - GRAPH_TOP + 4  # +4 for tick marks
    _init_graph_bitmap(gw, gh)
    graph_group.append(
        displayio.TileGrid(
            _graph_bitmap, pixel_shader=_graph_palette, x=GRAPH_MARGIN_X, y=GRAPH_TOP
        )
    )
    graph_labels = displayio.Group()
    graph_group.append(graph_labels)

    # Status bar
    status_label = label.Label(FONT, text="Booting...", color=WHITE, scale=1)
    status_label.anchor_point = (0.5, 1.0)
    status_label.anchored_position = (display.width // 2, display.height - 2)
    main_group.append(status_label)

    # Full-screen message, shown while there's no price to display yet
    message_label = label.Label(FONT, text="", color=WHITE, scale=1)
    message_label.anchor_point = (0.5, 0.5)
    message_label.anchored_position = (display.width // 2, display.height // 2 - 8)
    main_group.append(message_label)
    detail_label = label.Label(FONT, text="", color=GRAY, scale=1)
    detail_label.anchor_point = (0.5, 0.0)
    detail_label.anchored_position = (display.width // 2, display.height // 2 + 8)
    main_group.append(detail_label)

    show_message("Starting...")


def show_message(text, detail=""):
    """Fill the screen with just a message (and optional gray detail line).

    Used while there are no prices to show, instead of a "--.-" placeholder.
    """
    if not display or not HAS_DISPLAY_TEXT:
        return
    price_group.hidden = True
    graph_group.hidden = True
    title_label.hidden = True
    status_label.hidden = True
    bg_palette[0] = BLACK
    message_label.text = text
    detail_label.text = detail
    message_label.hidden = False
    detail_label.hidden = not detail


def _leave_message():
    message_label.hidden = True
    detail_label.hidden = True
    title_label.hidden = False
    status_label.hidden = False


_GRAD_GREEN = (0x66, 0xFF, 0x66)  # LIGHT_GREEN, matches the PRICE_MED band
_GRAD_YELLOW = (0xFF, 0xE0, 0x00)
_GRAD_RED = (0xFF, 0x00, 0x00)


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

    # Two-step gradient: light green -> yellow at PRICE_HIGH -> red at PRICE_MAX.
    # (A straight green->red blend passes through olive/brown, never yellow.)
    if price < PRICE_HIGH:
        t = (price - PRICE_MED) / (PRICE_HIGH - PRICE_MED)
        start, end = _GRAD_GREEN, _GRAD_YELLOW
    else:
        t = (price - PRICE_HIGH) / (PRICE_MAX - PRICE_HIGH)
        start, end = _GRAD_YELLOW, _GRAD_RED
    r, g, b = (int(s + (e - s) * t) for s, e in zip(start, end))
    bg_color = (r << 16) | (g << 8) | b
    # White text once the background gets dark enough (deep orange/red)
    text_color = WHITE if g < 90 else BLACK
    return bg_color, text_color


def format_price(price):
    """Format a c/kWh price in at most 4 significant characters.

    0.05, -0.50, 8.8, 12.5, 123, -12. Keeps the big price digits within
    the 240 px screen width.
    """
    if abs(price) < 0.995:  # rounds to below 1.00
        return f"{price:.2f}"
    tenths = round(price, 1)  # decide on the rounded value: 99.96 -> "100"
    if tenths >= 100 or tenths <= -10:
        return f"{price:.0f}"
    return f"{price:.1f}"


def _fit_price_scale():
    """Fallback when /price.pcf is missing: scale up the small font to fit.

    Integer scaling of a bitmap font looks blocky; the native price font
    is always preferred.
    """
    if PRICE_FONT is not None:
        return
    _, _, w, h = price_label.bounding_box
    if not w or not h:
        return
    max_w = display.width - 8
    max_h = display.height - 50  # leave room for title and unit labels
    scale = max(1, min(MAX_PRICE_SCALE, max_w // w, max_h // h))
    if price_label.scale != scale:
        price_label.scale = scale


def show_price(price):
    """Display the current price with color-coded background.

    price=None (no data for the current time) shows a full-screen message.
    """
    if not display or not HAS_DISPLAY_TEXT:
        return

    if price is None:
        show_message("No current price", "waiting for data")
        return

    _leave_message()
    price_group.hidden = False
    graph_group.hidden = True

    text = format_price(price)
    bg_color, text_color = get_price_color(price)
    if price_aa is not None and PRICE_AA.can_render(text):
        price_aa.set_colors(text_color, bg_color)
        price_aa.set_text(text)
        price_aa.tilegrid.hidden = False
        price_label.hidden = True
    else:
        if price_aa is not None:
            price_aa.tilegrid.hidden = True
        price_label.hidden = False
        price_label.text = text
        _fit_price_scale()

    bg_palette[0] = bg_color
    price_label.color = text_color
    title_label.color = text_color
    unit_label.color = text_color
    status_label.color = text_color


def _slot_colors(price):
    if price < PRICE_MED:
        return _C_FILL_GREEN, _C_LINE_GREEN
    if price < PRICE_HIGH:
        return _C_FILL_YELLOW, _C_LINE_YELLOW
    return _C_FILL_RED, _C_LINE_RED


AXIS_LABEL_GAP = 4  # min px between neighbouring x-axis labels


def _add_label(text, color, anchor, pos):
    lbl = label.Label(FONT, text=text, color=color, scale=1)
    lbl.anchor_point = anchor
    lbl.anchored_position = pos
    graph_labels.append(lbl)
    return lbl


def _place_axis_label(text, color, center_x, y, taken, clamp=False):
    """Add a label centred on center_x below the graph, unless it would collide.

    taken: list of (left, right) spans already used on the axis; updated.
    clamp: shift the label to stay on screen instead of skipping it.
    Returns True if the label was placed.
    """
    lbl = label.Label(FONT, text=text, color=color, scale=1)
    w = lbl.bounding_box[2]
    left = center_x - w // 2
    if clamp:
        left = max(1, min(display.width - w - 1, left))
    elif left < 0 or left + w > display.width:
        return False
    right = left + w
    for t_left, t_right in taken:
        if left < t_right + AXIS_LABEL_GAP and right > t_left - AXIS_LABEL_GAP:
            return False
    lbl.anchor_point = (0.0, 0.0)
    lbl.anchored_position = (left, y)
    graph_labels.append(lbl)
    taken.append((left, right))
    return True


def show_graph(prices, now_index=0, first_start=0):
    """Draw a price graph.

    Args:
        prices: list of slot prices (15 min each)
        now_index: index of the current slot in `prices`
        first_start: UTC epoch of prices[0], used for local-time hour labels
    """
    if not display or not HAS_DISPLAY_TEXT:
        return

    _leave_message()
    price_group.hidden = True
    graph_group.hidden = False

    bg_palette[0] = BLACK
    title_label.color = WHITE
    status_label.color = WHITE

    bmp = _graph_bitmap
    bmp.fill(0)
    while len(graph_labels) > 0:
        graph_labels.pop()

    if not prices or len(prices) < 2:
        return

    gw = bmp.width
    gh = display.height - GRAPH_BOTTOM_PAD - GRAPH_TOP  # plot height (excl. ticks)
    bottom = gh  # y of the baseline inside the bitmap

    min_price = min(prices)
    max_price = max(prices)

    _add_label(format_price(min_price), GREEN, (0.0, 0.0), (4, 2))
    _add_label(format_price(max_price), RED, (1.0, 0.0), (display.width - 4, 2))

    # Vertical scale with 10% headroom. Allow negative prices to go below 0.
    price_range = max(max_price - min_price, 1.0)
    padding = price_range * 0.1
    lo = min_price - padding if min_price < 0 else max(0, min_price - padding)
    hi = max_price + padding
    span = hi - lo

    def y_of(p):
        y = int(bottom - (p - lo) / span * gh)
        return max(0, min(bottom - 1, y))

    n = len(prices)
    x_step = (gw - 1) / (n - 1)
    xs = [int(i * x_step) for i in range(n)]
    ys = [y_of(p) for p in prices]

    # Dashed min/max reference lines
    for ref_y, color in (
        (y_of(min_price), _C_MIN_LINE),
        (y_of(max_price), _C_MAX_LINE),
    ):
        for x in range(0, gw, 4):
            bmp[x, ref_y] = color
            if x + 1 < gw:
                bmp[x + 1, ref_y] = color

    # Filled area under the curve, one column at a time
    for i in range(n - 1):
        fill_c, _ = _slot_colors((prices[i] + prices[i + 1]) / 2)
        x1, y1, x2, y2 = xs[i], ys[i], xs[i + 1], ys[i + 1]
        dx = x2 - x1
        for x in range(x1, x2 + 1):
            y = y1 + (y2 - y1) * (x - x1) // dx if dx else y1
            if y < bottom:
                bitmaptools.fill_region(bmp, x, y, x + 1, bottom, fill_c)

    # Curve on top, 2 px thick
    for i in range(n - 1):
        _, line_c = _slot_colors((prices[i] + prices[i + 1]) / 2)
        x1, y1, x2, y2 = xs[i], ys[i], xs[i + 1], ys[i + 1]
        bitmaptools.draw_line(bmp, x1, y1, x2, y2, line_c)
        bitmaptools.draw_line(bmp, x1, max(0, y1 - 1), x2, max(0, y2 - 1), line_c)

    # "Now" marker and dotted vertical line
    axis_y = GRAPH_TOP + bottom + 4
    taken = []  # x-spans used by axis labels, so they never overlap
    if 0 <= now_index < n:
        now_x = xs[now_index]
        for y in range(0, bottom, 3):
            bmp[now_x, y] = _C_NOW_LINE
            if y + 1 < bottom:
                bmp[now_x, y + 1] = _C_NOW_LINE
        mx = max(0, min(gw - 4, now_x - 2))
        my = max(0, min(bottom - 4, ys[now_index] - 2))
        bitmaptools.fill_region(bmp, mx, my, mx + 4, my + 4, _C_MARKER)
        # Kept on screen even when "now" is at the very edge of the graph
        _place_axis_label(
            "now", ACCENT, GRAPH_MARGIN_X + now_x, axis_y, taken, clamp=True
        )

    # Hour labels at whole local hours (2h apart on short graphs, 6h on long ones)
    if first_start:
        interval = 2 if n * SLOT_SECONDS <= 10 * 3600 else 6
        for i in range(n):
            t = local_time(first_start + i * SLOT_SECONDS)
            if t.tm_min != 0 or t.tm_hour % interval:
                continue
            x = xs[i]
            bitmaptools.fill_region(bmp, x, bottom, x + 1, bottom + 4, _C_TICK)
            # Skipped if it would overlap "now" or run off the screen
            _place_axis_label(
                f"{t.tm_hour:02d}", GRAY, GRAPH_MARGIN_X + x, axis_y, taken
            )


def show_status(message):
    """Update the status bar text."""
    if status_label:
        status_label.text = message


def set_title(text):
    """Update the title text."""
    if title_label:
        title_label.text = text
