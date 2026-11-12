"""Cursor styles. Each style turns the frames of one base cursor into new frames.

Adding a style: write a function ``(name, frames, intensity, color) -> list[Frame]``
and register it in ``STYLES``. ``frames`` is the base cursor in file order;
cursors that are already animated have several frames per nominal size.
``color`` is an (r, g, b) tuple in 0..1, or None for styles without a color.
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


def _blur(x: np.ndarray, sigma: float, axes: tuple[int, ...] = (0, 1)) -> np.ndarray:
    """Gaussian blur along the given axes, treating the outside as zeros."""
    if sigma <= 0:
        return x
    radius = max(1, int(np.ceil(sigma * 2.5)))
    taps = np.exp(-0.5 * (np.arange(-radius, radius + 1) / sigma) ** 2)
    taps /= taps.sum()
    for axis in axes:
        moved = np.moveaxis(x, axis, 0)
        pad = np.zeros((radius, *moved.shape[1:]), moved.dtype)
        wide = np.concatenate([pad, moved, pad])
        acc = sum(k * wide[i:i + moved.shape[0]] for i, k in enumerate(taps))
        x = np.moveaxis(acc, 0, axis)
    return x


def _pad(rgba: np.ndarray, p: int) -> np.ndarray:
    """Add p transparent pixels on every side (room for glow)."""
    return np.pad(rgba, ((p, p), (p, p), (0, 0)))


def _luma(rgb: np.ndarray) -> np.ndarray:
    return rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)


def _straight(pm: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """Premultiplied RGB + alpha -> straight RGBA frame data."""
    alpha = np.clip(alpha, 0, 1)
    pm = np.minimum(np.clip(pm, 0, 1), alpha[..., None])
    rgb = np.where(alpha[..., None] > 0, pm / np.maximum(alpha, 1e-6)[..., None], 0.0)
    return np.concatenate([rgb, alpha[..., None]], -1).astype(np.float32)


def _each(frames: list[Frame], fn: Callable[[np.ndarray, int], np.ndarray], pad_units: float = 0.0
          ) -> list[Frame]:
    """Apply ``fn(rgba, size)`` to every frame, growing the canvas by
    ``pad_units`` (in units of size/24 px) and moving the hotspot with it."""
    out = []
    for f in frames:
        p = int(np.ceil(f.size / 24 * pad_units))
        out.append(Frame(f.size, f.xhot + p, f.yhot + p, f.delay, fn(_pad(f.rgba, p), f.size)))
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


def style_glitch(name: str, frames: list[Frame], intensity: float, color=None) -> list[Frame]:
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


def style_glitch_anim(name: str, frames: list[Frame], intensity: float, color=None) -> list[Frame]:
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


# -------------------------------------------------------------------- crt ---

RGB = tuple[float, float, float]

CRT_PAD = 3.0
CRT_ROLL_PERIOD = 4.0   # scanline spacing of the rolling variant, in units
CRT_ROLL_FRAMES = 4
CRT_ROLL_MS = 90


def crt(rgba: np.ndarray, size: int, color: RGB, intensity: float = 1.0,
        phase: float | None = None) -> np.ndarray:
    """Monochrome phosphor screen: tinted image, scanlines, smear and bloom.

    ``phase`` (0..1) switches to wider, soft scanlines displaced downwards by
    that fraction of their period, for the rolling animation.
    """
    h = rgba.shape[0]
    unit = size / 24
    c = np.array(color, np.float32)
    a = rgba[..., 3]
    v = 0.30 + 0.70 * _luma(rgba[..., :3])               # keep dark bodies visible
    phosphor = c * v[..., None] + (1 - c) * (v ** 4)[..., None] * 0.55

    pm = _blur(phosphor * a[..., None], unit * 0.45, axes=(1,))   # horizontal beam smear
    alpha = _blur(a, unit * 0.45, axes=(1,))

    if phase is None:
        line = max(1, round(unit))
        dark = ((np.arange(h) // line) % 2).astype(np.float32)[:, None]
    else:
        period = max(3.0, unit * CRT_ROLL_PERIOD)
        dark = (0.5 - 0.5 * np.cos(2 * np.pi * (np.arange(h) / period - phase)))
        dark = (dark.astype(np.float32) ** 1.5)[:, None]
    depth = min(0.9, 0.5 * intensity)
    pm = pm * (1 - depth * dark)[..., None]
    alpha_lines = alpha * (1 - 0.35 * depth * dark)

    bloom = _blur(phosphor * a[..., None], unit * 1.4) * 0.55 * intensity
    bloom_a = _luma(bloom) * 0.9
    return _straight(np.maximum(pm, bloom * 0.8), np.maximum(alpha_lines, bloom_a))


def style_crt(name: str, frames: list[Frame], intensity: float, color=None) -> list[Frame]:
    return _each(frames, lambda px, size: crt(px, size, color, intensity), CRT_PAD)


def style_crt_anim(name: str, frames: list[Frame], intensity: float, color=None) -> list[Frame]:
    """CRT with scanlines rolling down the cursor, like a filmed TV.

    Cursors that are already animated keep their frames and delays; the lines
    advance one step per frame.
    """
    groups = _by_size(frames)
    out: list[Frame] = []
    if all(len(g) == 1 for g in groups.values()):
        for f in frames:
            for i in range(CRT_ROLL_FRAMES):
                out += _each([Frame(f.size, f.xhot, f.yhot, CRT_ROLL_MS, f.rgba)],
                             lambda px, size: crt(px, size, color, intensity, i / CRT_ROLL_FRAMES),
                             CRT_PAD)
        return out

    index: dict[int, int] = {}
    for f in frames:
        i = index.get(f.size, 0)
        index[f.size] = i + 1
        out += _each([f], lambda px, size: crt(px, size, color, intensity,
                                               (i % CRT_ROLL_FRAMES) / CRT_ROLL_FRAMES), CRT_PAD)
    return out


# -------------------------------------------------------------------- vhs ---

VHS_PAD = 2.0
VHS_REST_POS = 0.82                       # where the tracking band parks, as a fraction of height
VHS_SWEEP = (0.66, 0.46, 0.26, 0.08)      # band positions while it travels up
VHS_SWEEP_MS = 70
VHS_REST_MS = 900


def vhs(rgba: np.ndarray, size: int, seed: str, intensity: float = 1.0,
        pos: float = VHS_REST_POS, wobble: float = 0.0) -> np.ndarray:
    """Worn tape: soft magenta/green fringes, washed out tones and a tracking
    band of torn rows and white dropouts at ``pos`` (fraction of the shape's height).

    The noise is drawn on a 24-row grid and scaled, so it matches across sizes.
    ``wobble`` shifts the whole picture sideways, in units.
    """
    h, w, _ = rgba.shape
    unit = size / 24
    noise = np.random.RandomState(zlib.crc32(seed.encode()))
    a = rgba[..., 3]
    pm = rgba[..., :3] * a[..., None]

    # washed out: lifted blacks, a little less contrast, cold tint
    pm = pm * 0.86 + np.array([0.07, 0.08, 0.11], np.float32) * a[..., None]

    # chroma error: red+blue drift one way, green the other, all a bit smeared
    s = max(1, round(unit * intensity))
    soft = _blur(pm, unit * 0.55, axes=(1,))
    soft_a = _blur(a, unit * 0.55, axes=(1,))
    r, g, b = _shift(soft[..., 0], -s), _shift(soft[..., 1], s), _shift(soft[..., 2], -s)
    alpha = np.maximum.reduce([soft_a, _shift(soft_a, s), _shift(soft_a, -s)])
    pm = np.stack([np.maximum(r, pm[..., 0] * 0.7), np.maximum(g, pm[..., 1] * 0.7),
                   np.maximum(b, pm[..., 2] * 0.7)], -1)

    # tracking band: rows torn sideways by ragged amounts
    rows = np.minimum((np.arange(h) / unit).astype(int), 63)   # 24-grid row of every pixel row
    tear = (noise.uniform(-1, 1, 64) * 3.0 * intensity)[rows]
    ys = np.flatnonzero(a.max(1) > 0.05)                 # the band is placed within the shape
    top, span = (ys.min(), ys.max() - ys.min() + 1) if ys.size else (0, h)
    center = top + pos * span
    in_band = np.abs(np.arange(h) - center) <= 0.09 * span
    if wobble:
        pm, alpha = _shift(pm, round(wobble * unit)), _shift(alpha, round(wobble * unit))
    for y in np.flatnonzero(in_band):
        d = int(round(tear[y] * unit)) or 1
        pm[y], alpha[y] = _shift(pm[y:y + 1], d)[0], _shift(alpha[y:y + 1], d)[0]

    # dropouts: short white dashes in and around the band, also off the shape
    xs = np.flatnonzero(a.max(0) > 0.05)
    if xs.size:
        x0, x1 = xs.min() / unit - 1.5, xs.max() / unit + 1.5
        for _ in range(5):
            gy = center / unit + noise.uniform(-1.6, 1.6)
            gx, length = noise.uniform(x0, x1), noise.uniform(0.8, 3.0)
            ya, yb = int(gy * unit), int(gy * unit) + max(1, round(unit * 0.7))
            xa, xb = max(0, int(gx * unit)), int((gx + length) * unit)
            if 0 <= ya < h:
                pm[ya:yb, xa:xb] = np.maximum(pm[ya:yb, xa:xb], 0.8)
                alpha[ya:yb, xa:xb] = np.maximum(alpha[ya:yb, xa:xb], 0.8)

    # faint scanlines
    pm = pm * (1.0 - 0.12 * ((np.arange(h) // max(1, round(unit))) % 2))[:, None, None]
    return _straight(pm, alpha)


def style_vhs(name: str, frames: list[Frame], intensity: float, color=None) -> list[Frame]:
    """Static worn tape look. Already-animated cursors keep their frames and timing."""
    return _each(frames, lambda px, size: vhs(px, size, name, intensity), VHS_PAD)


def style_vhs_anim(name: str, frames: list[Frame], intensity: float, color=None) -> list[Frame]:
    """The tape at rest, then the tracking band travels up the cursor while the
    picture wobbles sideways.

    Cursors that are already animated keep their frames and delays, with the
    band climbing along the loop.
    """
    def render(f: Frame, delay: int, step: int | None) -> Frame:
        if step is None:
            fn = lambda px, size: vhs(px, size, name, intensity)                    # noqa: E731
        else:
            fn = lambda px, size: vhs(px, size, f"{name}/{step}", intensity,       # noqa: E731
                                      VHS_SWEEP[step], (0.5, -0.5, 0.5, 0.0)[step] * intensity)
        return _each([Frame(f.size, f.xhot, f.yhot, delay, f.rgba)], fn, VHS_PAD)[0]

    groups = _by_size(frames)
    out: list[Frame] = []
    if all(len(g) == 1 for g in groups.values()):
        rest = VHS_REST_MS + _rng(name).randrange(0, 400)
        for f in frames:
            out.append(render(f, rest, None))
            out += [render(f, VHS_SWEEP_MS, i) for i in range(len(VHS_SWEEP))]
        return out

    index: dict[int, int] = {}
    for f in frames:
        i = index.get(f.size, 0)
        index[f.size] = i + 1
        step = i % (3 * len(VHS_SWEEP))
        out.append(render(f, f.delay, step if step < len(VHS_SWEEP) else None))
    return out


# --------------------------------------------------------------- registry ---

@dataclass(frozen=True)
class Style:
    name: str
    description: str
    render: Callable[..., list[Frame]]  # (name, frames, intensity, color) -> frames
    color: RGB | None = None  # default color; None means the style takes no --color

    def apply(self, name: str, frames: list[Frame], intensity: float = 1.0,
              color: RGB | None = None) -> list[Frame]:
        return self.render(name, frames, intensity, color or self.color)


STYLES: dict[str, Style] = {
    s.name: s
    for s in (
        Style("glitch", "Static RGB split, torn band and scanlines.", style_glitch),
        Style("glitch-anim", "Glitch at rest with short random bursts (~every 1.5 s).",
              style_glitch_anim),
        Style("crt", "Phosphor monitor: tint, scanlines and bloom (default green, see --color).",
              style_crt, color=(0.25, 1.0, 0.45)),
        Style("crt-anim", "CRT with scanlines rolling down, like a filmed TV (see --color).",
              style_crt_anim, color=(0.25, 1.0, 0.45)),
        Style("vhs", "Worn tape: color fringes, washed tones and a tracking noise band.", style_vhs),
        Style("vhs-anim", "VHS whose tracking band travels up the cursor now and then.",
              style_vhs_anim),
    )
}
