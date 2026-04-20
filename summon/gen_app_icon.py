"""Generate a .icns app icon for Summon.app from a scaled-up radar design.

Creates a rounded-square dark background with a white radar pulse centered
on it, renders at every size macOS expects (16/32/128/256/512 @1x & @2x),
writes them into Summon.iconset/, then `iconutil` converts that folder to
icon.icns. Run this once before bundling the app.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from PIL import Image, ImageDraw

SUMMON = os.path.expanduser("~/.claude/summon")
ICONSET = os.path.join(SUMMON, "Summon.iconset")
OUT_ICNS = os.path.join(SUMMON, "icon.icns")


def make_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Rounded-square background (macOS squircle-ish)
    radius = int(size * 0.22)
    d.rounded_rectangle([0, 0, size, size], radius=radius,
                        fill=(18, 22, 34, 255))

    cx = cy = size / 2
    # Center dot — bright, slightly larger than a strict dot for app-icon presence
    dot_r = size * 0.055
    d.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r],
              fill=(240, 248, 255, 255))

    # Three expanding rings — soft glow feel via decreasing alpha
    ring_specs = [(0.16, 255), (0.26, 200), (0.36, 140)]
    stroke = max(2, int(round(size * 0.014)))
    for frac, alpha in ring_specs:
        r = size * frac
        d.ellipse([cx - r, cy - r, cx + r, cy + r],
                  outline=(200, 220, 255, alpha), width=stroke)

    return img


def main() -> None:
    if os.path.exists(ICONSET):
        shutil.rmtree(ICONSET)
    os.makedirs(ICONSET)

    # macOS iconutil expects these exact filenames
    specs = [
        (16, "icon_16x16.png"),
        (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"),
        (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"),
        (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"),
        (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    ]
    for size, name in specs:
        make_icon(size).save(os.path.join(ICONSET, name))

    subprocess.check_call(["iconutil", "-c", "icns", "-o", OUT_ICNS, ICONSET])
    print("Wrote", OUT_ICNS)


if __name__ == "__main__":
    main()
