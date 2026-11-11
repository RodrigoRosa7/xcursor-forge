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
            out = style.render("default", frames, 1.0)
            self.assertEqual({f.size for f in out}, {24, 32}, style.name)
            self.assertTrue(all((f.xhot, f.yhot) == (3, 4) for f in out), style.name)
            self.assertTrue(all(f.rgba.shape == (f.size, f.size, 4) for f in out), style.name)

    def test_deterministic(self):
        frames = [xcursor.Frame(24, 0, 0, 0, arrow(24))]
        a = STYLES["glitch-anim"].render("pointer", frames, 1.0)
        b = STYLES["glitch-anim"].render("pointer", frames, 1.0)
        for fa, fb in zip(a, b):
            np.testing.assert_array_equal(fa.rgba, fb.rgba)


if __name__ == "__main__":
    unittest.main()
