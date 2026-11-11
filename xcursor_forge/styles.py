"""Cursor styles. Each style turns the frames of one base cursor into new frames.

Adding a style: write a function ``(name, frames, intensity) -> list[Frame]``
and register it in ``STYLES``. ``frames`` is the base cursor in file order;
cursors that are already animated have several frames per nominal size.
"""

from __future__ import annotations

import random
import zlib
from dataclasses import dataclass
from typing import Callable

import numpy as np

from .xcursor import Frame


# ---------------------------------------------------------------- helpers ---

def _shift(x: np.ndarray, dx: int) -> np.ndarray:
    """Shift an array horizontally, filling with zeros (transparent)."""
    out = np.zeros_like(x)
    if dx > 0:
        out[:, dx:] = x[:, :-dx]
    elif dx < 0:
        out[:, :dx] = x[:, -dx:]
    else:
        out[:] = x
    return out


def _by_size(frames: list[Frame]) -> dict[int, list[Frame]]:
    groups: dict[int, list[Frame]] = {}
    for f in frames:
        groups.setdefault(f.size, []).append(f)
    return groups


def _rng(name: str) -> random.Random:
    """Deterministic per-cursor randomness, so rebuilds are reproducible."""
    return random.Random(zlib.crc32(name.encode()))


# ----------------------------------------------------------------- glitch ---

Band = tuple[float, float, float]  # (top as fraction of height, height fraction, shift in units)

REST_BANDS: tuple[Band, ...] = ((0.45, 0.12, 2.0),)


def glitch(rgba: np.ndarray, size: int, split: float = 2.0,
           bands: tuple[Band, ...] = REST_BANDS, scan: float = 0.10) -> np.ndarray:
    """RGB split + displaced horizontal bands + scanlines.

    Distances are in "units" of size/24 px, so the look stays consistent
    across nominal sizes (2 units = 2 px at 24 px, 4 px at 48 px).
    """
    h, _w, _ = rgba.shape
    unit = size / 24
    a = rgba[..., 3]
    pm = rgba[..., :3] * a[..., None]  # premultiply so shifted channels blend cleanly

    torn, torn_a = pm.copy(), a.copy()
    for top, height, shift in bands:
        y0, bh = int(h * top), max(1, int(h * height))
        d = int(round(unit * shift)) or (1 if shift >= 0 else -1)
        torn[y0:y0 + bh] = _shift(pm[y0:y0 + bh], d)
        torn_a[y0:y0 + bh] = _shift(a[y0:y0 + bh], d)

    s = max(1, round(unit * split))
    r = _shift(torn[..., 0], s)
    g = torn[..., 1]
    b = _shift(torn[..., 2], -s)
    alpha = np.clip(np.maximum.reduce([_shift(torn_a, s), torn_a, _shift(torn_a, -s)]), 0, 1)

    rows = (np.arange(h) // max(1, size // 24)) % 2
    shade = (1.0 - scan * rows)[:, None]
    rgb = np.stack([r, g, b], -1) * shade[..., None]
    rgb = np.minimum(rgb, alpha[..., None])

    straight = np.where(alpha[..., None] > 0, rgb / np.maximum(alpha, 1e-6)[..., None], 0.0)
    return np.concatenate([straight, alpha[..., None]], -1).astype(np.float32)


def _scaled(bands: tuple[Band, ...], k: float) -> tuple[Band, ...]:
    return tuple((t, h, s * k) for t, h, s in bands)


STATIC_BANDS: tuple[Band, ...] = ((0.45, 0.12, 4.0),)


def style_glitch(name: str, frames: list[Frame], intensity: float) -> list[Frame]:
    """Static glitch. Already-animated cursors keep their frames and timing."""
    return [
        Frame(f.size, f.xhot, f.yhot, f.delay,
              glitch(f.rgba, f.size, 2.0 * intensity, _scaled(STATIC_BANDS, intensity)))
        for f in frames
    ]


REST_MS = 1200
BURST_MS = (60, 50, 70, 50, 60, 50)


def _bursts(name: str, intensity: float) -> list[tuple[float, tuple[Band, ...]]]:
    rng = _rng(name)
    out = []
    for _ in BURST_MS:
        split = rng.choice([2.0, 3.0, 3.5, 4.0]) * intensity
        bands = tuple(
            (rng.uniform(0.05, 0.85), rng.uniform(0.08, 0.22),
             rng.choice([-1, 1]) * rng.uniform(2.5, 6.0) * intensity)
            for _ in range(rng.choice([1, 2, 3]))
        )
        out.append((split, bands))
    return out


def style_glitch_anim(name: str, frames: list[Frame], intensity: float) -> list[Frame]:
    """Long resting glitch frame followed by a short burst of heavier glitches.

    Cursors that are already animated (e.g. ``wait``) keep their frames and
    delays, with a band that travels down the cursor from frame to frame.
    """
    groups = _by_size(frames)
    out: list[Frame] = []
    if all(len(g) == 1 for g in groups.values()):
        bursts = _bursts(name, intensity)
        for f in frames:
            out.append(Frame(f.size, f.xhot, f.yhot, REST_MS,
                             glitch(f.rgba, f.size, 2.0 * intensity, _scaled(REST_BANDS, intensity))))
            for (split, bands), ms in zip(bursts, BURST_MS):
                out.append(Frame(f.size, f.xhot, f.yhot, ms, glitch(f.rgba, f.size, split, bands)))
        return out

    index: dict[int, int] = {}
    for f in frames:
        i = index.get(f.size, 0)
        index[f.size] = i + 1
        split = (2.0, 2.0, 3.0, 2.0)[i % 4] * intensity
        bands = (((0.1 + 0.07 * i) % 0.8, 0.12, (2.5 if i % 2 else -2.5) * intensity),)
        out.append(Frame(f.size, f.xhot, f.yhot, f.delay, glitch(f.rgba, f.size, split, bands)))
    return out


# --------------------------------------------------------------- registry ---

@dataclass(frozen=True)
class Style:
    name: str
    description: str
    render: Callable[[str, list[Frame], float], list[Frame]]


STYLES: dict[str, Style] = {
    s.name: s
    for s in (
        Style("glitch", "Static RGB split, torn band and scanlines.", style_glitch),
        Style("glitch-anim", "Glitch at rest with short random bursts (~every 1.5 s).",
              style_glitch_anim),
    )
}
