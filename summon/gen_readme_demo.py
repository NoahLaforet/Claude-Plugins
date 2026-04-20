"""Generate an animated GIF showing Summon's menu-bar icon states.

Produces summon/docs/demo.gif — cycles through radar (double-clap),
mic (dictate), super (both), and disabled, tinted white for a dark
menu-bar mock. Used in the README so the icon work is visible at a glance.
"""
from __future__ import annotations

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
ICONS = ROOT / "icons"
OUT_DIR = ROOT / "docs"
OUT_DIR.mkdir(exist_ok=True)
OUT = OUT_DIR / "demo.gif"

# Frame geometry
BAR_W, BAR_H = 520, 110
ICON_PX = 44
SCALE = 2                        # menu-bar is 22px; 2x scale reads clearly
BG = (28, 28, 30, 255)           # macOS dark menu bar
FG = (240, 240, 240, 255)
LABEL_FG = (200, 200, 205, 255)
CAPTION_FG = (150, 150, 155, 255)

FRAME_MS = 220                   # per-frame duration
HOLD_FRAMES = 2                  # extra copies of the last frame per mode


def load_white(name: str) -> Image.Image:
    """Load a template icon and recolor it white on transparent."""
    src = Image.open(ICONS / f"{name}.png").convert("RGBA")
    alpha = src.split()[3]
    white = Image.new("RGBA", src.size, FG)
    white.putalpha(alpha)
    return white.resize((ICON_PX * SCALE, ICON_PX * SCALE), Image.LANCZOS)


def font(size: int) -> ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def render_frame(icon: Image.Image, label: str, caption: str) -> Image.Image:
    frame = Image.new("RGBA", (BAR_W, BAR_H), BG)
    d = ImageDraw.Draw(frame)

    icon_x = 28
    icon_y = (BAR_H - icon.height) // 2
    frame.alpha_composite(icon, (icon_x, icon_y))

    text_x = icon_x + icon.width + 24
    d.text((text_x, 28), label, fill=LABEL_FG, font=font(22))
    d.text((text_x, 62), caption, fill=CAPTION_FG, font=font(15))

    return frame


MODES = [
    ("Double-clap listening", "Clap twice → new Claude session",
     ["radar_01", "radar_02", "radar_03", "radar_04"]),
    ("Dictate armed", "Caps Lock to start / stop",
     ["mic_01", "mic_02", "mic_03", "mic_04"]),
    ("Both active", "Clap + voice working together",
     ["super_01", "super_02", "super_03", "super_04"]),
    ("Off", "Everything disabled from the menu",
     ["radar_disabled"]),
]


def main() -> None:
    frames: list[Image.Image] = []
    durations: list[int] = []

    for label, caption, names in MODES:
        for name in names:
            icon = load_white(name)
            frames.append(render_frame(icon, label, caption))
            durations.append(FRAME_MS)
        # Hold the last frame of each mode a touch longer so the eye catches it.
        for _ in range(HOLD_FRAMES):
            frames.append(frames[-1])
            durations.append(FRAME_MS)

    # PIL's GIF writer wants palette ("P") frames for best quality.
    palette_frames = [f.convert("P", palette=Image.ADAPTIVE, colors=64) for f in frames]
    palette_frames[0].save(
        OUT,
        save_all=True,
        append_images=palette_frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"wrote {OUT} ({len(frames)} frames, {sum(durations)}ms loop)")


if __name__ == "__main__":
    main()
