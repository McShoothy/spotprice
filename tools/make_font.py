#!/usr/bin/env python3
"""
Render a TTF/OTF into a crisp 1-bit bitmap font (BDF, optionally PCF) at an
exact pixel size, for adafruit_bitmap_font.

Bitmap fonts can only be enlarged by integer pixel multiples (Label scale=N),
which makes large text blocky. Generating each size natively from the vector
font keeps the curves smooth.

Requires: pip install freetype-py ; bdftopcf for .pcf output (XQuartz or
`brew install bdftopcf`).

Usage:
    python tools/make_font.py FONT.ttf SIZE_PX OUT.(bdf|pcf) [--chars CHARS] [--weight 700]

Examples:
    # UI font: printable ASCII at 20 px
    python tools/make_font.py "tools/fonts/LeagueSpartan[wght].ttf" 20 font.pcf
    # Big price digits only
    python tools/make_font.py "tools/fonts/LeagueSpartan[wght].ttf" 84 price.pcf --chars "0123456789.-"
"""

import argparse
import os
import shutil
import subprocess
import tempfile

import freetype

ASCII = "".join(chr(c) for c in range(32, 127))


def render_bdf(font_path, size_px, chars, weight=None):
    face = freetype.Face(font_path)
    if weight is not None:
        try:
            face.set_var_design_coords((weight,))
        except Exception as e:  # static (non-variable) font
            print(f"note: could not set weight ({e}); using default instance")
    face.set_pixel_sizes(0, size_px)
    flags = freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO

    glyphs = []
    for ch in sorted(set(chars), key=ord):
        if face.get_char_index(ch) == 0 and ch != " ":
            print(f"skip {ch!r}: not in font")
            continue
        face.load_char(ch, flags)
        g = face.glyph
        bm = g.bitmap
        rows = []
        for r in range(bm.rows):
            row = bytes(bm.buffer[r * bm.pitch : r * bm.pitch + (bm.width + 7) // 8])
            rows.append(row.hex().upper())
        glyphs.append(
            {
                "ch": ch,
                "adv": g.advance.x >> 6,
                "w": bm.width,
                "h": bm.rows,
                "x": g.bitmap_left,
                "y": g.bitmap_top - bm.rows,
                "rows": rows,
            }
        )

    ascent = (face.size.ascender + 63) >> 6
    descent = (-face.size.descender + 63) >> 6
    inked = [g for g in glyphs if g["w"]]
    min_x = min(g["x"] for g in inked)
    min_y = min(g["y"] for g in inked)
    max_x = max(g["x"] + g["w"] for g in inked)
    max_y = max(g["y"] + g["h"] for g in inked)

    family = face.family_name.decode(errors="replace")
    out = [
        "STARTFONT 2.1",
        f"FONT -{family.replace(' ', '')}-{size_px}px",
        f"SIZE {size_px} 72 72",
        f"FONTBOUNDINGBOX {max_x - min_x} {max_y - min_y} {min_x} {min_y}",
        "STARTPROPERTIES 4",
        f"FONT_ASCENT {ascent}",
        f"FONT_DESCENT {descent}",
        f"PIXEL_SIZE {size_px}",
        f"DEFAULT_CHAR {ord(glyphs[0]['ch'])}",
        "ENDPROPERTIES",
        f"CHARS {len(glyphs)}",
    ]
    for g in glyphs:
        out += [
            f"STARTCHAR U+{ord(g['ch']):04X}",
            f"ENCODING {ord(g['ch'])}",
            f"SWIDTH {g['adv'] * 1000 // size_px} 0",
            f"DWIDTH {g['adv']} 0",
            f"BBX {g['w']} {g['h']} {g['x']} {g['y']}",
            "BITMAP",
            *g["rows"],
            "ENDCHAR",
        ]
    out.append("ENDFONT")
    return "\n".join(out) + "\n", glyphs


def render_aa(font_path, size_px, chars, weight=None, levels=4):
    """Render greyscale (anti-aliased) glyphs into the SpotPrice .aa format.

    bitmap_font/Label only support 1-bit glyphs, so smooth edges need a
    custom format (read by spotprice/aatext.py). Coverage is rounded to
    `levels` shades; 4 = transparent, 2 edge shades, solid: a subtle AA.

    Layout, little-endian:
        b"AAF1", u8 levels, u8 count, u8 ascent, u8 descent
        count x 8-byte records: u8 char, u8 w, u8 h, i8 left, i8 top,
                                u8 advance, u16 reserved
        pixel data for each glyph in record order: w*h bytes, 0..levels-1
    """
    import struct

    face = freetype.Face(font_path)
    if weight is not None:
        try:
            face.set_var_design_coords((weight,))
        except Exception as e:
            print(f"note: could not set weight ({e}); using default instance")
    face.set_pixel_sizes(0, size_px)
    flags = freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_LIGHT

    records, data, glyphs = [], [], []
    for ch in sorted(set(chars), key=ord):
        if ord(ch) > 255 or (face.get_char_index(ch) == 0 and ch != " "):
            print(f"skip {ch!r}")
            continue
        face.load_char(ch, flags)
        g = face.glyph
        bm = g.bitmap
        px = bytearray()
        for r in range(bm.rows):
            row = bm.buffer[r * bm.pitch : r * bm.pitch + bm.width]
            px += bytes(min(levels - 1, (v * (levels - 1) + 127) // 255) for v in row)
        records.append(
            (ord(ch), bm.width, bm.rows, g.bitmap_left, g.bitmap_top, g.advance.x >> 6)
        )
        data.append(bytes(px))
        glyphs.append({"ch": ch, "w": bm.width, "h": bm.rows, "adv": g.advance.x >> 6})

    inked = [r for r in records if r[1] and r[2]]
    ascent = max(r[4] for r in inked)
    descent = max(0, max(r[2] - r[4] for r in inked))
    out = b"AAF1" + struct.pack("<BBBB", levels, len(records), ascent, descent)
    for code, w, h, left, top, adv in records:
        out += struct.pack("<BBBbbBH", code, w, h, left, top, adv, 0)
    out += b"".join(data)
    return out, glyphs


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("font")
    ap.add_argument("size", type=int, help="pixel size (em height)")
    ap.add_argument("output", help=".bdf, .pcf, or .aa (anti-aliased, price only)")
    ap.add_argument("--chars", default=ASCII, help="characters to include")
    ap.add_argument("--weight", type=float, default=700, help="variable-font weight")
    ap.add_argument(
        "--levels", type=int, default=4, help="shades for .aa output (2-16)"
    )
    args = ap.parse_args()

    if args.output.endswith(".aa"):
        blob, glyphs = render_aa(
            args.font, args.size, args.chars, args.weight, args.levels
        )
        with open(args.output, "wb") as f:
            f.write(blob)
        print(f"Wrote {args.output} ({len(blob)} bytes, {len(glyphs)} glyphs)")
        return

    bdf, glyphs = render_bdf(args.font, args.size, args.chars, args.weight)
    digit = next((g for g in glyphs if g["ch"] == "8"), None)
    if digit:
        print(f"'8' is {digit['w']}x{digit['h']} px, advance {digit['adv']}")

    if args.output.endswith(".pcf"):
        if not shutil.which("bdftopcf"):
            raise SystemExit("bdftopcf not found; install it or write a .bdf instead")
        with tempfile.NamedTemporaryFile("w", suffix=".bdf", delete=False) as f:
            f.write(bdf)
        try:
            subprocess.run(["bdftopcf", "-o", args.output, f.name], check=True)
        finally:
            os.remove(f.name)
    else:
        with open(args.output, "w") as f:
            f.write(bdf)
    print(
        f"Wrote {args.output} ({os.path.getsize(args.output)} bytes, {len(glyphs)} glyphs)"
    )


if __name__ == "__main__":
    main()
