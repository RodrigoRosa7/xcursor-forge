# xcursor-forge

CLI that reads an existing Xcursor theme, applies a visual style to every
cursor and writes a new, ready to use theme. Python 3.10+, NumPy as the only
runtime dependency. Code is MIT; see "Licensing" below for generated themes.

## Commands

```sh
python3 -m unittest discover -s tests          # tests (no pytest needed)
python3 -m xcursor_forge styles                # list styles
python3 -m xcursor_forge preview capitaine-cursors -s crt -o /tmp/p.png
python3 -m xcursor_forge build capitaine-cursors -s crt -o /tmp/dist
python3 scripts/make_previews.py               # regenerate docs/preview-* (needs ImageMagick)
```

There is no build step and no linter configured. Run the tests and a real
`build` of at least one theme before calling a change done, and look at a
`preview` PNG for any change that affects pixels.

## Layout

- `xcursor_forge/xcursor.py`: reader/writer for the Xcursor binary format. The
  only place that converts between Xcursor's premultiplied ARGB32 and the
  straight float RGBA used everywhere else.
- `xcursor_forge/styles.py`: all styles plus the `STYLES` registry.
- `xcursor_forge/cli.py`: `styles`, `build`, `preview` subcommands.
- `xcursor_forge/png.py`: stdlib-only PNG writer for previews.
- `scripts/make_previews.py`: regenerates the README images in `docs/`.
- `tests/test_xcursor.py`: format round trip and invariants every style must keep.

## Conventions for styles

- A style is `(name, frames, intensity, color) -> list[Frame]`, registered in
  `STYLES`. Call styles through `Style.apply`, which fills in the default color.
- Pixels are float32 `(H, W, 4)`, straight alpha, 0..1. Do the math
  premultiplied and convert back with `_straight`. Output must stay finite and
  within 0..1; RGB brighter than alpha cannot be stored (no additive glow).
- All distances scale with `unit = size / 24`, so a style looks the same at
  every nominal size (themes ship 24 to 144 px or more).
- Never change the click point. If a style needs room (glow), grow the canvas
  symmetrically with `_each(..., pad_units)`, which moves the hotspot with it.
- Keep every nominal size and its frame order. Cursors that are already
  animated in the base theme (e.g. `wait`) keep their frame count and delays;
  animated styles only vary the effect per frame for those.
- Output must be deterministic: use `_rng(name)` (seeded by the cursor name),
  never unseeded randomness or the clock.
- Only styles with a default `color` accept `--color`.
- Animated styles multiply disk usage by their frame count; keep frame counts
  small.
- A cursor theme cannot react to pointer movement, speed or clicks. Effects
  such as motion trails belong to the compositor, not to this project.

When adding or changing a style, also update the styles table and previews in
`README.md` (English section first, then the short Portuguese section), add the
style to `STATIC` or `ANIMATED` in `scripts/make_previews.py`, and regenerate
`docs/`.

## Licensing

- The code is MIT.
- Generated themes are derived works of the base theme's artwork and carry the
  base theme's license (Capitaine Cursors: LGPL-3.0), never MIT. Anything that
  redistributes a built theme must ship that license text and credits to the
  original author. Do not commit built themes to the repository; `dist/` is
  ignored and prebuilt themes go in GitHub releases.

## Repository etiquette

- Code, comments, commit messages and the main README are in English.
- Commits use the identity configured in this repository's local git config;
  do not change it or add a global one.
- Do not push, tag or create releases without the maintainer asking for it.
