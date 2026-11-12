import tempfile
import unittest
from pathlib import Path

import numpy as np

from xcursor_forge import xcursor
from xcursor_forge.styles import STYLES


def arrow(size: int) -> np.ndarray:
    img = np.zeros((size, size, 4), np.float32)
    for y in range(size):
        img[y, : y // 2 + 1] = (1.0, 1.0, 1.0, 1.0)
    return img


class RoundTrip(unittest.TestCase):
    def test_write_then_read(self):
        frames = [xcursor.Frame(s, 1, 2, 50, arrow(s)) for s in (24, 48)]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "default"
            xcursor.write(path, frames)
            back = xcursor.read(path)
        self.assertEqual([(f.size, f.xhot, f.yhot, f.delay) for f in back],
                         [(24, 1, 2, 50), (48, 1, 2, 50)])
        np.testing.assert_allclose(back[1].rgba, frames[1].rgba, atol=1 / 255)

    def test_rejects_non_xcursor(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "x"
            path.write_bytes(b"not a cursor")
            with self.assertRaises(xcursor.XcursorError):
                xcursor.read(path)


class Styles(unittest.TestCase):
    def test_every_style_keeps_sizes_and_hotspots(self):
        frames = [xcursor.Frame(s, 3, 4, 0, arrow(s)) for s in (24, 32)]
        for style in STYLES.values():
            out = style.apply("default", frames, 1.0)
            self.assertEqual({f.size for f in out}, {24, 32}, style.name)
            for f in out:
                # styles may grow the canvas (glow), but only symmetrically,
                # moving the hotspot by the same padding
                pad = f.xhot - 3
                self.assertGreaterEqual(pad, 0, style.name)
                self.assertEqual(f.yhot, 4 + pad, style.name)
                self.assertEqual(f.rgba.shape, (f.size + 2 * pad, f.size + 2 * pad, 4), style.name)
                self.assertEqual(f.rgba.dtype, np.float32, style.name)
                self.assertTrue(np.isfinite(f.rgba).all(), style.name)
                self.assertTrue((f.rgba >= 0).all() and (f.rgba <= 1).all(), style.name)

    def test_color_override_changes_output(self):
        frames = [xcursor.Frame(24, 0, 0, 0, arrow(24))]
        for name in ("crt", "crt-anim"):
            a = STYLES[name].apply("default", frames, 1.0)[0].rgba
            b = STYLES[name].apply("default", frames, 1.0, (1.0, 0.1, 0.8))[0].rgba
            self.assertFalse(np.allclose(a, b), name)

    def test_deterministic(self):
        frames = [xcursor.Frame(24, 0, 0, 0, arrow(24))]
        for style in STYLES.values():
            a = style.apply("pointer", frames, 1.0)
            b = style.apply("pointer", frames, 1.0)
            self.assertEqual([f.delay for f in a], [f.delay for f in b], style.name)
            for fa, fb in zip(a, b):
                np.testing.assert_array_equal(fa.rgba, fb.rgba)

    def test_animated_base_keeps_frames_and_delays(self):
        frames = [xcursor.Frame(24, 5, 5, 30 + i, arrow(24)) for i in range(12)]
        for style in STYLES.values():
            out = style.apply("wait", frames, 1.0)
            self.assertEqual([f.delay for f in out], [f.delay for f in frames], style.name)
            self.assertEqual(len({f.rgba.shape for f in out}), 1, style.name)


if __name__ == "__main__":
    unittest.main()
