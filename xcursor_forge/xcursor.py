"""Minimal reader/writer for the Xcursor file format.

Pixels are exposed as float32 arrays of shape (H, W, 4) holding *straight*
(non-premultiplied) RGBA in the 0..1 range. Xcursor itself stores
premultiplied ARGB32, so conversion happens here and nowhere else.

Format reference: Xcursor(3), section "FILE FORMAT".
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

MAGIC = b"Xcur"
FILE_HEADER_SIZE = 16
FILE_VERSION = 0x10000
IMAGE_TYPE = 0xFFFD0002
IMAGE_HEADER_SIZE = 36
IMAGE_VERSION = 1


@dataclass
class Frame:
    size: int  # nominal size (the value cursor-size settings match against)
    xhot: int
    yhot: int
    delay: int  # milliseconds; only meaningful when a size has several frames
    rgba: np.ndarray  # (H, W, 4) float32, straight alpha, 0..1


class XcursorError(ValueError):
    pass


def read(path: str | Path) -> list[Frame]:
    """Return every image chunk in table-of-contents order."""
    data = Path(path).read_bytes()
    if data[:4] != MAGIC:
        raise XcursorError(f"{path}: not an Xcursor file")
    header_size, _version, ntoc = struct.unpack_from("<III", data, 4)
    frames: list[Frame] = []
    for i in range(ntoc):
        typ, _subtype, pos = struct.unpack_from("<III", data, header_size + 12 * i)
        if typ != IMAGE_TYPE:
            continue  # comments and unknown chunks
        (chunk_size, _ctype, nominal, _ver, w, h, xhot, yhot, delay) = struct.unpack_from(
            "<9I", data, pos
        )
        start = pos + chunk_size
        if start + 4 * w * h > len(data):
            raise XcursorError(f"{path}: truncated image chunk")
        px = np.frombuffer(data, dtype="<u4", count=w * h, offset=start).reshape(h, w)
        frames.append(Frame(nominal, xhot, yhot, delay, _unpremultiply(px)))
    if not frames:
        raise XcursorError(f"{path}: no images")
    return frames


def write(path: str | Path, frames: list[Frame]) -> None:
    """Write frames in the given order (frames of one size form its animation)."""
    toc, chunks = [], []
    offset = FILE_HEADER_SIZE + 12 * len(frames)
    for f in frames:
        h, w, _ = f.rgba.shape
        body = struct.pack(
            "<9I", IMAGE_HEADER_SIZE, IMAGE_TYPE, f.size, IMAGE_VERSION,
            w, h, f.xhot, f.yhot, f.delay,
        ) + _premultiply(f.rgba).tobytes()
        toc.append(struct.pack("<III", IMAGE_TYPE, f.size, offset))
        chunks.append(body)
        offset += len(body)
    header = MAGIC + struct.pack("<III", FILE_HEADER_SIZE, FILE_VERSION, len(frames))
    Path(path).write_bytes(header + b"".join(toc) + b"".join(chunks))


def _unpremultiply(px: np.ndarray) -> np.ndarray:
    a = ((px >> 24) & 0xFF).astype(np.float32)
    rgb = np.stack([(px >> 16) & 0xFF, (px >> 8) & 0xFF, px & 0xFF], -1).astype(np.float32)
    safe = np.maximum(a, 1.0)[..., None]
    rgb = np.where(a[..., None] > 0, rgb / safe, 0.0)
    return np.concatenate([np.clip(rgb, 0, 1), (a / 255.0)[..., None]], -1).astype(np.float32)


def _premultiply(rgba: np.ndarray) -> np.ndarray:
    a = np.clip(rgba[..., 3], 0, 1)
    rgb = np.clip(rgba[..., :3], 0, 1) * a[..., None]
    v = (np.concatenate([rgb, a[..., None]], -1) * 255 + 0.5).astype(np.uint32)
    return ((v[..., 3] << 24) | (v[..., 0] << 16) | (v[..., 1] << 8) | v[..., 2]).astype("<u4")
