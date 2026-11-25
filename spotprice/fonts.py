"""
Shared font loading for SpotPrice Display.

Fonts are loaded once and shared by the display and setup portal.

FONT        small UI font (/font.pcf or /font.bdf), used at scale 1
PRICE_FONT  large price digits (/price.pcf), rendered natively at full size.
            Scaling a small bitmap font up instead makes the digits blocky.
            None if missing; the display then falls back to scaling FONT.

Generate both with tools/make_font.py.
"""

try:
    from adafruit_display_text import label  # noqa: F401  (re-exported)
    import terminalio

    HAS_DISPLAY_TEXT = True
except ImportError as e:
    print(f"Display text import error: {e}")
    label = None
    terminalio = None
    HAS_DISPLAY_TEXT = False


def _load_font(paths, glyphs, fallback):
    if not HAS_DISPLAY_TEXT:
        return None
    try:
        from adafruit_bitmap_font import bitmap_font
    except ImportError:
        return fallback

    # PCF loads much faster than BDF
    for path in paths:
        try:
            font = bitmap_font.load_font(path)
        except OSError:
            continue
        except Exception as e:
            print(f"Font load error ({path}): {e}")
            continue
        # Pre-load the glyphs we use so labels don't hit the filesystem later
        try:
            font.load_glyphs(glyphs)
        except Exception:
            pass
        print(f"Loaded font: {path}")
        return font

    return fallback


FONT = _load_font(
    ("/font.pcf", "/font.bdf"),
    "0123456789.,-+:/ ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!",
    terminalio.FONT if HAS_DISPLAY_TEXT else None,
)
PRICE_FONT = _load_font(("/price.pcf", "/price.bdf"), "0123456789.-", None)

# Anti-aliased price digits (/price.aa). Preferred over PRICE_FONT when present.
try:
    from . import aatext

    PRICE_AA = aatext.load("/price.aa") if HAS_DISPLAY_TEXT else None
except ImportError:
    PRICE_AA = None
