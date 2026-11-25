"""
Anti-aliased text for the big price digits.

CircuitPython bitmap fonts (and adafruit_display_text Labels) are 1-bit, so
edges are hard steps. This draws pre-rendered greyscale glyphs (.aa files
from tools/make_font.py) into one Bitmap whose palette blends the text
colour into the background, giving smooth edges with a few shades.
"""

import struct

import bitmaptools
import displayio


class AAFont:
    """Glyphs loaded from a .aa file: char -> (Bitmap or None, left, top, advance)."""

    def __init__(self, path):
        with open(path, "rb") as f:
            if f.read(4) != b"AAF1":
                raise ValueError(f"{path}: not an AAF1 font")
            self.levels, count, self.ascent, self.descent = struct.unpack(
                "<BBBB", f.read(4)
            )
            records = [struct.unpack("<BBBbbBH", f.read(8)) for _ in range(count)]
            self.glyphs = {}
            for code, w, h, left, top, adv, _ in records:
                bmp = None
                if w and h:
                    bmp = displayio.Bitmap(w, h, self.levels)
                    # Rows of w bytes, one shade index (0..levels-1) per pixel
                    bitmaptools.readinto(bmp, f, 8)
                self.glyphs[chr(code)] = (bmp, left, top, adv)

    def can_render(self, text):
        return all(c in self.glyphs for c in text)


def _blend(bg, fg, t):
    out = 0
    for shift in (16, 8, 0):
        b = (bg >> shift) & 0xFF
        f = (fg >> shift) & 0xFF
        out |= int(b + (f - b) * t + 0.5) << shift
    return out


class AAText:
    """A centred, anti-aliased text line. Add `.tilegrid` to a display Group."""

    def __init__(self, font, width, center_y):
        self.font = font
        height = font.ascent + font.descent
        self.bitmap = displayio.Bitmap(width, height, font.levels)
        self.palette = displayio.Palette(font.levels)
        self.palette.make_transparent(0)
        self.tilegrid = displayio.TileGrid(
            self.bitmap, pixel_shader=self.palette, x=0, y=center_y - height // 2
        )
        self.text = None
        self._colors = None

    def set_colors(self, fg, bg):
        """Text colour and the background it sits on (edge shades blend the two)."""
        if self._colors == (fg, bg):
            return
        self._colors = (fg, bg)
        top = self.font.levels - 1
        for i in range(1, self.font.levels):
            self.palette[i] = _blend(bg, fg, i / top)

    def set_text(self, text):
        if text == self.text:
            return
        self.text = text
        bmp = self.bitmap
        bmp.fill(0)

        # Centre on the actual ink, not advance widths
        glyphs = self.font.glyphs
        pen = 0
        ink_l, ink_r = None, 0
        for c in text:
            g_bmp, left, _, adv = glyphs[c]
            if g_bmp:
                gl = pen + left
                ink_l = gl if ink_l is None else min(ink_l, gl)
                ink_r = max(ink_r, gl + g_bmp.width)
            pen += adv
        if ink_l is None:
            return
        shift = (bmp.width - (ink_r - ink_l)) // 2 - ink_l

        pen = 0
        for c in text:
            g_bmp, left, top, adv = glyphs[c]
            if g_bmp:
                x = pen + left + shift
                y = self.font.ascent - top
                if 0 <= x and x + g_bmp.width <= bmp.width and y >= 0:
                    bitmaptools.blit(bmp, g_bmp, x, y, skip_source_index=0)
            pen += adv


def load(path):
    """Load an AAFont, or return None if the file is missing or invalid."""
    try:
        font = AAFont(path)
    except OSError:
        return None
    except Exception as e:
        print(f"AA font load error ({path}): {e}")
        return None
    print(f"Loaded AA font: {path}")
    return font
