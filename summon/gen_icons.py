"""Generate menu-bar icons for Summon.

Three 4-frame animation sets + one disabled frame, all 44x44 template PNGs
(black-on-transparent) so macOS can auto-tint for light/dark mode.

  radar_01..04  — double-clap launcher only (ring pulse)
  mic_01..04    — dictate only (mic + pulse waves)
  super_01..04  — both features on (mic + expanding rings + sparkles)
  radar_disabled — both off (slashed radar)
"""
from __future__ import annotations

import math
import os
from PIL import Image, ImageDraw

ICONS_DIR = os.path.expanduser("~/.claude/summon/icons")
os.makedirs(ICONS_DIR, exist_ok=True)

SIZE = 44
CX = CY = SIZE / 2


def canvas() -> Image.Image:
    return Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))


def save(img: Image.Image, name: str) -> str:
    path = os.path.join(ICONS_DIR, name + ".png")
    img.save(path)
    return path


def ring(d: ImageDraw.ImageDraw, r: float, alpha: int, width: int = 2,
         cx: float = CX, cy: float = CY) -> None:
    d.ellipse([cx - r, cy - r, cx + r, cy + r],
              outline=(0, 0, 0, alpha), width=width)


def dot(d: ImageDraw.ImageDraw, r: float, alpha: int = 255,
        cx: float = CX, cy: float = CY) -> None:
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0, alpha))


# === radar_01..04 (double-clap) + disabled ===
def radar_frame(rings: list[tuple[float, int]]) -> Image.Image:
    img = canvas()
    d = ImageDraw.Draw(img)
    dot(d, 2.5)
    for r, alpha in rings:
        if alpha > 0:
            ring(d, r, alpha, width=2)
    return img


save(radar_frame([(7, 255), (0, 0), (0, 0)]),       "radar_01")
save(radar_frame([(9, 200), (14, 255), (0, 0)]),    "radar_02")
save(radar_frame([(9, 110), (15, 180), (20, 255)]), "radar_03")
save(radar_frame([(0, 0), (16, 90), (21, 150)]),    "radar_04")

# Disabled: slashed outer ring + center dot
img = canvas()
d = ImageDraw.Draw(img)
ring(d, 13, 255, width=1)
dot(d, 2.5, alpha=255)
d.line([CX - 12, CY - 12, CX + 12, CY + 12], fill=(0, 0, 0, 255), width=2)
save(img, "radar_disabled")


# === mic_01..04 (dictate) ===
# A vertical capsule mic (body) sitting on a U-shaped stand, with pulse arcs
# on either side that expand across 4 frames.

def mic_body(d: ImageDraw.ImageDraw) -> None:
    # Capsule body: rounded rectangle centered slightly high
    body_w = 10
    body_h = 18
    top_y = CY - 10
    left_x = CX - body_w / 2
    d.rounded_rectangle(
        [left_x, top_y, left_x + body_w, top_y + body_h],
        radius=5, fill=(0, 0, 0, 255),
    )
    # U-shaped stand (cradle) below body
    cradle_r = 9
    d.arc(
        [CX - cradle_r, CY - 1, CX + cradle_r, CY + cradle_r * 2 - 1],
        start=20, end=160, fill=(0, 0, 0, 255), width=2,
    )
    # Stem + base
    stem_top_y = CY + cradle_r
    stem_bot_y = stem_top_y + 4
    d.line([CX, stem_top_y, CX, stem_bot_y], fill=(0, 0, 0, 255), width=2)
    d.line(
        [CX - 4, stem_bot_y, CX + 4, stem_bot_y],
        fill=(0, 0, 0, 255), width=2,
    )


def mic_frame(wave_alphas: tuple[int, int, int]) -> Image.Image:
    """wave_alphas = (inner, middle, outer) opacity for the pulse arcs."""
    img = canvas()
    d = ImageDraw.Draw(img)
    mic_body(d)
    # Pulse arcs on both sides of the mic body — like WiFi arcs flipped vertical
    for side, sign in (("L", -1), ("R", 1)):
        for idx, (r, alpha) in enumerate(zip((6, 10, 14), wave_alphas)):
            if alpha <= 0:
                continue
            # Arc is a thin slice opening outward
            bbox = [
                CX - r + sign * 8, CY - 10 - r + 9,
                CX + r + sign * 8, CY - 10 + r + 9,
            ]
            if sign < 0:
                start, end = 110, 250
            else:
                start, end = -70, 70
            d.arc(bbox, start=start, end=end, fill=(0, 0, 0, alpha), width=2)
    return img


# 4-frame cycle: waves ripple outward
save(mic_frame((255,   0,   0)), "mic_01")
save(mic_frame((200, 255,   0)), "mic_02")
save(mic_frame((120, 200, 255)), "mic_03")
save(mic_frame((  0, 120, 180)), "mic_04")


# === super_01..04 (both on) ===
# Mic body + pulsing rings AROUND the whole glyph + sparkle at top-right corner.

def sparkle(d: ImageDraw.ImageDraw, x: float, y: float, r: float,
            alpha: int = 255) -> None:
    """Four-pointed sparkle (plus + diagonal)."""
    d.line([x - r, y, x + r, y], fill=(0, 0, 0, alpha), width=1)
    d.line([x, y - r, x, y + r], fill=(0, 0, 0, alpha), width=1)
    d.line([x - r * 0.6, y - r * 0.6, x + r * 0.6, y + r * 0.6],
           fill=(0, 0, 0, alpha), width=1)
    d.line([x - r * 0.6, y + r * 0.6, x + r * 0.6, y - r * 0.6],
           fill=(0, 0, 0, alpha), width=1)


def super_frame(ring_rings: list[tuple[float, int]],
                spark_alpha: int) -> Image.Image:
    img = canvas()
    d = ImageDraw.Draw(img)
    # Outer radar rings wrap the full icon
    for r, alpha in ring_rings:
        if alpha > 0:
            ring(d, r, alpha, width=1)
    # Mic body in center (slightly smaller so rings have room)
    body_w = 8
    body_h = 14
    top_y = CY - 9
    left_x = CX - body_w / 2
    d.rounded_rectangle(
        [left_x, top_y, left_x + body_w, top_y + body_h],
        radius=4, fill=(0, 0, 0, 255),
    )
    # U cradle
    cradle_r = 7
    d.arc(
        [CX - cradle_r, CY - 2, CX + cradle_r, CY + cradle_r * 2 - 2],
        start=20, end=160, fill=(0, 0, 0, 255), width=2,
    )
    # Sparkle in top-right corner
    if spark_alpha > 0:
        sparkle(d, SIZE - 8, 8, 3.5, spark_alpha)
    return img


# 4-frame cycle: expanding rings + sparkle pulse
save(super_frame([(10, 255), (0, 0), (0, 0)],          255), "super_01")
save(super_frame([(12, 200), (17, 255), (0, 0)],       200), "super_02")
save(super_frame([(12, 110), (18, 180), (21, 255)],    140), "super_03")
save(super_frame([(0, 0),   (19, 110), (22, 180)],      80), "super_04")


print("Icons written to:", ICONS_DIR)
for name in sorted(os.listdir(ICONS_DIR)):
    print(" ", name)
