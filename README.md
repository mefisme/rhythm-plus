# Rhythm Plus

Rhythm Plus is a custom firmware for the **Novation Circuit Rhythm**. Its goal is a better stock Circuit Rhythm: the same instrument, with the same workflow, made deeper for working with samples.

It starts from the official firmware 2.0.1 (build 5706) and keeps what the stock firmware does. On top of that it has three aims:

- **Go deeper with samples:** a granular engine, time stretch that keeps the pitch, and more control over each track's sample.
- **Find new ideas:** Pattern Mutate and Step Mutate change the order of your patterns, or the steps inside them, so a beat can grow in ways you would not write by hand. Your own patterns stay safe.
- **Sequence more of the sound:** Grid FX can play in time with the pattern from its own track, and each track can be kept out of Grid FX.

If you know the stock Circuit Rhythm, you already know how to use Rhythm Plus. The new features are there when you want them.

Rhythm Plus is not affiliated with Novation or Focusrite. Novation and Focusrite do not endorse it.

- **Stable build:** A0213. **Test build:** A0233.
- **Manual:** [`manual/rhythm_plus_manual.pdf`](manual/rhythm_plus_manual.pdf). It shows every feature, with drawings of the pads.
- **More detail:** [the Granular controls](manual/granular-a0201.md) and [the Track Parameter Editor](manual/track_parameter_editor.md).

## Risks

- You install modified firmware at your own risk.
- Make a full copy of the SD card (projects, packs and samples) before you install.
- A test build can have errors that damage stored projects or samples. Do not use a test build on important projects.
- Install the result only on a Circuit Rhythm.

## Return to stock

Use Novation Components. If the device does not start, hold **Sample Rec + Samples + Note** while you switch it on (Novation's bootloader mode), then send the official firmware. Rhythm Plus does not change the bootloader.

## Install

An installer comes with the first release. Until then, build the firmware yourself (below): `tools/make_uploader.py` then makes a local installer page, `tools/uploader.html`, from your builds.

## Credits

Rhythm Plus is built on the work of **Ghillermo**, the author of **Circuit Remix** and **CIRCUIT-HACKS**. His patcher, build tools and firmware work make this project possible. Please look at his projects and support his work:

- Circuit Remix (Circuit Rhythm): https://github.com/Ghillermo/CIRCUIT-REMIX
- CIRCUIT-HACKS (Circuit Tracks): https://github.com/Ghillermo/CIRCUIT-HACKS-RC
- Donate: https://PayPal.me/ghillermo

Rhythm Plus is a separate project. It is not Circuit Remix, and it does not include the Circuit Remix features.

## Build

This repository does not contain Novation's firmware or any file made from it. You supply the official firmware, and the build checks it.

You need Python 3.10 or newer and git.

1. Get the repository with its submodule (Circuit Remix's build tools, in `remix/`):

   ```bash
   git clone --recurse-submodules https://github.com/mefisme/rhythm-plus.git
   cd rhythm-plus
   python -m venv .venv
   .venv/Scripts/python -m pip install -r requirements.txt      # on macOS / Linux: .venv/bin/python
   ```

2. Download the official firmware Circuit Rhythm 2.0.1 (build 5706) from Novation: [circuitrhythm-firmware-5706.syx](https://components.novationmusic.com/api/v2/firmwares/169/file). Store it for the builds (the script checks its SHA-256):

   ```bash
   .venv/Scripts/python tools/setup_stock.py PATH/TO/circuitrhythm-firmware-5706.syx
   ```

3. Build a version:

   ```bash
   .venv/Scripts/python builds/build_a0213.py
   ```

   The result is in `firmware/a0213/`: `rhythmplus-A0213.syx` (to send), `.bin` and `manifest.json`. The build is reproducible: the manifest records the SHA-256 of the result.

   Some modules are C. They need zig 0.13: set `RH_ZIG` to the path of `zig.exe` (default `buildtmp/zig-toolchain/ziglang/zig.exe`). The DSP code needs `DSPTOOL` (see Tests).

### Tests

The tests run the firmware in an emulator. They need:

- `DSPTOOL`: the path of the DSP56300 tool. CIRCUIT-HACKS' `tools/setup_dev.py` builds it (`ext/bin/dsptool`).
- A RAM dump of a Circuit Rhythm at `remix/stock/rhythm-ram-frd1-synced.bin`.

```bash
DSPTOOL=PATH/TO/dsptool PYTHON=.venv/Scripts/python bash tests/run_all.sh a0213
```

### Update Circuit Remix's tools

`remix/` is a git submodule, fixed at the Circuit Remix version the builds are tested with. To use a newer one:

```bash
git -C remix fetch && git -C remix checkout origin/main
```

Then rebuild and compare the SHA-256 with the manifests before you commit the new submodule version.

## Repository

| Folder | What it holds |
|---|---|
| `builds/` | One script for each version. |
| `modules/` | The features: each module adds its code to the firmware. |
| `tests/` | The emulator tests. |
| `tools/` | Setup, the manual and the installer page generators. |
| `manual/` | The user documentation. |
| `firmware/` | Each version's `manifest.json`. The `.syx` / `.bin` files stay on your computer. |
| `remix/` | Circuit Remix (submodule): its build tools are used by the builds. |

## License

MIT, see [`LICENSE`](LICENSE). The MIT license does not apply to the Novation firmware. Circuit Remix (`remix/`) has its own MIT license.

Circuit Rhythm, Components and Novation are trademarks of Focusrite Audio Engineering Ltd.
