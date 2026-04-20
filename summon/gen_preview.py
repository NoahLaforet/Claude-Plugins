"""Build a preview sheet of all candidate icons on light + dark backgrounds.

Each family gets a row. Within a row: 1x size, 3x size, 1x inverted, 3x inverted
so Noah can see how each icon reads at actual menu-bar size and how it looks
against both menu-bar themes.
"""
from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont

ICONS_DIR = os.path.expanduser("~/.claude/summon/icons")
OUT = os.path.expanduser("~/.claude/summon/preview.png")

FAMILIES = [
    ("Radar / Pulse (animated, 4 frames → disabled)",
     ["radar_01", "radar_02", "radar_03", "radar_04", "radar_disabled"]),
    ("Hexagon + dot (enabled → disabled)",
     ["hex_enabled", "hex_disabled"]),
    ("Waveform in ring (enabled → disabled)",
     ["wave_enabled", "wave_disabled"]),
    ("J monogram in rounded square (enabled → disabled)",
     ["mono_enabled", "mono_disabled"]),
    ("Broadcast / signal arcs (enabled → disabled)",
     ["cast_enabled", "cast_disabled"]),
]

ICON_PX = 44                 # source icon size
SMALL_PX = 22                # menu-bar actual size
LARGE_PX = 88                # 4x for visibility
CELL_PAD_X = 14
CELL_PAD_Y = 10
ROW_LABEL_H = 24
LIGHT_BG = (245, 245, 247, 255)
DARK_BG = (30, 30, 32, 255)
LABEL_COLOR = (50, 50, 55, 255)


def tinted(src: Image.Image, bg: tuple[int, int, int, int]) -> Image.Image:
    """Render a black template PNG against a given background color.

    Dark bg → pixels become white (like dark-mode menu bar).
    Light bg → pixels stay dark (like light-mode menu bar).
    """
    dark_mode = (bg[0] + bg[1] + bg[2]) / 3 < 128
    out = Image.new("RGBA", src.size, bg)
    if dark_mode:
        # Invert: alpha stays, color becomes white.
        white = Image.new("RGBA", src.size, (240, 240, 240, 0))
        alpha = src.split()[3]
        white.putalpha(alpha)
        out = Image.alpha_composite(out, white)
    else:
        out = Image.alpha_composite(out, src)
    return out


def render_icon(name: str, px: int, bg: tuple[int, int, int, int]) -> Image.Image:
    src = Image.open(os.path.join(ICONS_DIR, name + ".png")).convert("RGBA")
    if px != src.width:
        src = src.resize((px, px), Image.LANCZOS)
    return tinted(src, bg)


def build_row(label: str, names: list[str]) -> Image.Image:
    # Each entry shows: small_light, large_light, small_dark, large_dark
    cell_w = SMALL_PX + LARGE_PX + CELL_PAD_X * 3
    block_w = cell_w * 2  # light block + dark block
    entry_w = block_w + CELL_PAD_X * 2
    row_w = entry_w * len(names) + CELL_PAD_X
    row_h = LARGE_PX + CELL_PAD_Y * 2 + ROW_LABEL_H

    row = Image.new("RGBA", (row_w, row_h), (255, 255, 255, 255))
    d = ImageDraw.Draw(row)

    try:
        font = ImageFont.truetype(
            "/System/Library/Fonts/SFNSMono.ttf", 13)
        small_font = ImageFont.truetype(
            "/System/Library/Fonts/SFNSMono.ttf", 10)
    except Exception:
        font = ImageFont.load_default()
        small_font = font

    d.text((CELL_PAD_X, 4), label, fill=LABEL_COLOR, font=font)

    y0 = ROW_LABEL_H
    x = CELL_PAD_X
    for name in names:
        # Light half
        light_block = Image.new("RGBA", (cell_w, LARGE_PX + CELL_PAD_Y * 2),
                                LIGHT_BG)
        light_block.alpha_composite(
            render_icon(name, SMALL_PX, LIGHT_BG),
            (CELL_PAD_X,
             CELL_PAD_Y + (LARGE_PX - SMALL_PX) // 2))
        light_block.alpha_composite(
            render_icon(name, LARGE_PX, LIGHT_BG),
            (CELL_PAD_X + SMALL_PX + CELL_PAD_X, CELL_PAD_Y))
        # Dark half
        dark_block = Image.new("RGBA", (cell_w, LARGE_PX + CELL_PAD_Y * 2),
                               DARK_BG)
        dark_block.alpha_composite(
            render_icon(name, SMALL_PX, DARK_BG),
            (CELL_PAD_X,
             CELL_PAD_Y + (LARGE_PX - SMALL_PX) // 2))
        dark_block.alpha_composite(
            render_icon(name, LARGE_PX, DARK_BG),
            (CELL_PAD_X + SMALL_PX + CELL_PAD_X, CELL_PAD_Y))

        row.paste(light_block, (x, y0))
        row.paste(dark_block, (x + cell_w, y0))

        # per-frame label under the block
        ImageDraw.Draw(row).text(
            (x + CELL_PAD_X, y0 + LARGE_PX + CELL_PAD_Y + 2),
            name, fill=LABEL_COLOR, font=small_font)

        x += entry_w
    # Trim/resize height to include label line
    return row


def main() -> None:
    rows = [build_row(label, names) for label, names in FAMILIES]
    max_w = max(r.width for r in rows)
    total_h = sum(r.height for r in rows) + 20
    sheet = Image.new("RGBA", (max_w, total_h), (255, 255, 255, 255))
    y = 10
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height
    sheet.save(OUT)
    print("Preview sheet:", OUT)


if __name__ == "__main__":
    main()
