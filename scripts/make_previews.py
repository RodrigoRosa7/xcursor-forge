#!/usr/bin/env python3
"""Regenerate the README previews in docs/ (needs ImageMagick for the GIFs).

Usage: python3 scripts/make_previews.py [BASE_THEME]   (default: capitaine-cursors)
"""

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from xcursor_forge import xcursor  # noqa: E402
from xcursor_forge.cli import find_theme  # noqa: E402
from xcursor_forge.png import write_png  # noqa: E402
from xcursor_forge.styles import STYLES  # noqa: E402

BG = np.array([0x1A, 0x1B, 0x26, 255], np.float32) / 255
CURSORS = ("default", "pointer", "text")
STATIC = ("glitch", "crt", "vhs")
ANIMATED = ("glitch-anim", "crt-anim", "vhs-anim")
SIZE, SCALE, PAD = 48, 4, 8


def tile(rgba: np.ndarray) -> np.ndarray:
    h, w, _ = rgba.shape
    out = np.tile(BG, (h + 2 * PAD, w + 2 * PAD, 1))
    a = rgba[..., 3:4]
    region = out[PAD:PAD + h, PAD:PAD + w]
    region[..., :3] = rgba[..., :3] * a + region[..., :3] * (1 - a)
    return out


def row(images: list[np.ndarray]) -> np.ndarray:
    h = max(i.shape[0] for i in images)
    padded = [np.concatenate([i, np.tile(BG, (h - i.shape[0], i.shape[1], 1))]) for i in images]
    return np.concatenate(padded, 1).repeat(SCALE, 0).repeat(SCALE, 1)


def frames_for(base: Path, style: str, cursor: str) -> list[xcursor.Frame]:
    src = xcursor.read(base / "cursors" / cursor)
    size = min({f.size for f in src}, key=lambda s: abs(s - SIZE))
    return [f for f in STYLES[style].apply(cursor, src, 1.0) if f.size == size], \
        [f for f in src if f.size == size][0]


def main() -> int:
    base = find_theme(sys.argv[1] if len(sys.argv) > 1 else "capitaine-cursors")
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)

    # static styles: original | styled, one row per cursor
    for style in STATIC:
        rows = []
        for c in CURSORS:
            styled, original = frames_for(base, style, c)
            rows.append(row([tile(original.rgba), tile(styled[0].rgba)]))
        width = max(r.shape[1] for r in rows)
        rows = [np.concatenate([r, np.tile(BG, (r.shape[0], width - r.shape[1], 1))], 1) for r in rows]
        write_png(docs / f"preview-{style}.png", np.concatenate(rows, 0))

    # animated styles: the three cursors side by side, frame by frame
    for style in ANIMATED:
        anims = [frames_for(base, style, c)[0] for c in CURSORS]
        with tempfile.TemporaryDirectory() as tmp:
            args = []
            for i in range(len(anims[0])):
                path = Path(tmp) / f"{i:03}.png"
                write_png(path, row([tile(a[i].rgba) for a in anims]))
                args += ["-delay", str(max(2, anims[0][i].delay // 10)), str(path)]
            subprocess.run(["magick", *args, "-loop", "0", str(docs / f"preview-{style}.gif")],
                           check=True, stdin=subprocess.DEVNULL)
    print("wrote docs/preview-{" + ",".join(STATIC) + "}.png and docs/preview-{"
          + ",".join(ANIMATED) + "}.gif")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
