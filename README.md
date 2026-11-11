# xcursor-forge

Turn the Linux cursor theme you already like into a styled variant: a
glitchy RGB-split version, an animated one, and more styles over time.

xcursor-forge reads an existing Xcursor theme, applies a style to every cursor
(all sizes, hotspots and animations preserved) and writes a new, ready to use
theme. It works on any desktop that uses Xcursor themes: niri, Hyprland, Sway,
GNOME, KDE, X11…

| `glitch` | `glitch-anim` |
|---|---|
| ![glitch preview](docs/preview-glitch.png) | ![glitch-anim preview](docs/preview-glitch-anim.gif) |

*Previews made from [Capitaine Cursors](https://github.com/keeferrourke/capitaine-cursors).*

> 🇧🇷 [Leia em português](#português)

## Styles

| Style | Description |
|---|---|
| `glitch` | Static RGB split (red/blue channels pulled apart), a torn horizontal band and scanlines. |
| `glitch-anim` | The glitch at rest for 1.2 s, then a ~0.35 s burst of heavier, random glitches. Each cursor gets its own burst. Cursors that were already animated (e.g. `wait`) keep their timing. |

## Requirements

- Python 3.10+
- [NumPy](https://numpy.org/) (`sudo pacman -S python-numpy`, `sudo apt install python3-numpy`, …)
- ImageMagick only if you want to regenerate the README previews

## Usage

Run it straight from a clone, no install needed:

```sh
git clone https://github.com/RodrigoRosa7/xcursor-forge
cd xcursor-forge
python3 -m xcursor_forge styles

# preview one cursor (original + styled frames) before building
python3 -m xcursor_forge preview Adwaita -s glitch -c default -o preview.png

# build into ./dist
python3 -m xcursor_forge build Adwaita -s glitch-anim

# or build straight into ~/.local/share/icons
python3 -m xcursor_forge build capitaine-cursors -s glitch-anim --install
```

Or install the `xcursor-forge` command with `pipx install .` (from the clone).

The base theme can be a name found in `~/.local/share/icons`, `~/.icons`,
`/usr/local/share/icons` or `/usr/share/icons`, or a path to a theme directory.

| Option | |
|---|---|
| `-s, --style` | style to apply (see `styles`) |
| `-n, --name` | output theme name (default `<base>-<style>`) |
| `-o, --out` | output directory (default `./dist`) |
| `-i, --install` | write into `~/.local/share/icons` |
| `--intensity` | effect strength multiplier, e.g. `0.75` or `1.5` (default `1.0`) |
| `-f, --force` | replace an existing output theme |

### Applying the theme

- **niri**: `cursor { xcursor-theme "capitaine-cursors-glitch-anim"; xcursor-size 32; }` in your config.
- **GTK apps**: `gsettings set org.gnome.desktop.interface cursor-theme 'capitaine-cursors-glitch-anim'`
- **Noctalia**: the [Cursor plugin](https://noctalia.dev/plugins/community/cursor) can install and apply a built theme folder for you, and revert it later.
- Already running apps keep the old cursor until restarted.

The effect is drawn in proportion to the cursor size. At 24 px it is subtle;
32 px or more shows the colors better.

## License

The **code** is MIT licensed (see [LICENSE](LICENSE)).

**Generated themes are derived works of the base theme's artwork** and are
covered by the base theme's license, not by MIT. For example, a theme built
from Capitaine Cursors is LGPL-3.0. Each generated theme contains a
`GENERATED.txt` noting its base. If you redistribute a generated theme, keep
the base theme's license and credits with it.

## Adding a style

Styles live in [`xcursor_forge/styles.py`](xcursor_forge/styles.py). A style is
a function that receives the frames of one cursor (straight RGBA arrays, with
size, hotspot and delay) and returns new frames; register it in `STYLES`.
Run the tests with `python3 -m unittest discover -s tests`.

---

## Português

O xcursor-forge pega um tema de cursor que você já tem no Linux e gera uma
versão estilizada dele: com efeito glitch (separação RGB), glitch animado e,
no futuro, outros estilos. Todos os tamanhos, hotspots e animações do tema
original são mantidos.

**Uso rápido:**

```sh
git clone https://github.com/RodrigoRosa7/xcursor-forge
cd xcursor-forge
python3 -m xcursor_forge build capitaine-cursors -s glitch-anim --install
```

Depois escolha o tema `capitaine-cursors-glitch-anim` no seu ambiente (no niri:
`xcursor-theme` dentro do bloco `cursor`; nos apps GTK: `gsettings`). O plugin
[Cursor do Noctalia](https://noctalia.dev/plugins/community/cursor) também
instala e aplica o tema, e permite reverter pela interface.

**Licença:** o código é MIT. Os temas gerados são derivados do tema base e
seguem a licença dele (ex.: Capitaine Cursors → LGPL-3.0).
