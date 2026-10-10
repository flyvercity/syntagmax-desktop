"""Derive the Syntagmax Desktop application icon from the core logo.

Source: ``syntagmax/assets/images/syntagmax_800x800.png`` (the brand logomark on
the dark-green grid field). We take a centred square crop tightened around the
mark so it fills the icon frame at small sizes, keep the brand-green field, apply
a subtle rounded-corner mask, and emit:

* ``src/syntagmax_desktop/resources/app_icon.ico`` — multi-resolution Windows ICO
  (16/32/48/64/128/256) for the frozen executable, the MSI shortcuts, and the
  Windows taskbar.
* ``src/syntagmax_desktop/resources/app_icon.png`` — a 256x256 PNG for
  ``QApplication.setWindowIcon`` at runtime (cross-platform).

Run once to regenerate the committed assets::

    uv run python scripts/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

SRC = Path('syntagmax/assets/images/syntagmax_800x800.png')
OUT_DIR = Path('src/syntagmax_desktop/resources')
BG = (23, 74, 43)  # the logo's dark-green field (probed from the corners).

# A centred square crop around the mark. The logomark is horizontally centred in
# the 800x800 source and runs vertically from roughly y=110 to y=775; we frame it
# with a little breathing room and ignore the tiny corner sparkle.
CROP_SIZE = 660
CROP_CX = 400  # horizontal centre of the source
CROP_TOP = 92


def _rounded_mask(size: int, radius_frac: float = 0.18) -> Image.Image:
    """Return an L-mode rounded-rectangle mask of ``size`` square."""
    mask = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(mask)
    radius = int(size * radius_frac)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def build() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    src = Image.open(SRC).convert('RGB')

    left = CROP_CX - CROP_SIZE // 2
    box = (left, CROP_TOP, left + CROP_SIZE, CROP_TOP + CROP_SIZE)
    cropped = src.crop(box)

    # Work at 256 for the base master, on an opaque brand-green backing so the
    # rounded corners reveal nothing but transparency outside the badge.
    base = cropped.resize((256, 256), Image.LANCZOS).convert('RGBA')
    backing = Image.new('RGBA', (256, 256), (*BG, 255))
    badge = Image.alpha_composite(backing, base)
    badge.putalpha(_rounded_mask(256))

    png_path = OUT_DIR / 'app_icon.png'
    badge.save(png_path)

    ico_path = OUT_DIR / 'app_icon.ico'
    badge.save(ico_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    print('wrote', png_path, 'and', ico_path)


if __name__ == '__main__':
    build()
