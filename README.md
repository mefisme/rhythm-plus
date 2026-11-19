# Rhythm Plus

**Rhythm Plus turns the Novation Circuit Rhythm into a deeper sampler and an idea machine, and keeps the feel of the original.**

Rhythm Plus is a custom firmware for musicians who make beats with samples, want more sound design from their own sounds, and like happy accidents. It starts from the official firmware 2.0.1 and keeps how the Circuit Rhythm works. The new features sit on top.

Rhythm Plus is not affiliated with Novation or Focusrite. Novation and Focusrite do not endorse it.

## What it gives you

- **Shape your samples.** Turn a sample into a granular texture, or stretch a loop so it stays in time at any tempo, with its pitch unchanged.
- **Get unstuck.** Mutate shuffles your patterns, or the steps inside a pattern, and gives you new ideas to keep or throw away.
- **Move your effects.** Sequence Grid FX like a track, so effects come and go in time with the beat. Keep any track out of the effects.
- **Control every track.** See and change all of a track's sound settings in one view, step by step.

## Status

Rhythm Plus is a work in progress.

- **Stable build (A0213):** tested on the device. Use this one to make music.
- **Test build (A0233):** the newest features. It can have bugs.
- **The [manual](manual/rhythm_plus_manual.pdf)** is a work in progress too. Some pages and drawings do not show the newest build yet.

## Risks

- You install modified firmware at your own risk.
- Make a full copy of the SD card (projects, packs and samples) on a computer before you install.
- Rhythm Plus keeps some project settings in the `RP_AUTO` folder on the SD card. When you back up, copy the whole card with this folder. A backup made with Components may not include it.
- Projects saved with Rhythm Plus are not tested on the official firmware.
- A test build can have errors that damage stored projects or samples. Do not use a test build on important projects.
- Install Rhythm Plus only on a Circuit Rhythm.

**Tip:** you can copy your SD card onto a second card and use the second card for Rhythm Plus. Your projects from the official firmware then stay as they are.

## Get started

1. Back up your SD card.
2. Install Rhythm Plus. An installer comes with the first release; until then, see [For developers](#for-developers).
3. Read the [manual](manual/rhythm_plus_manual.pdf).

**Back to the official firmware:** use Novation Components. If the device does not start, hold **Sample Rec + Samples + Note** while you switch it on, then send the official firmware. Rhythm Plus does not change this start-up mode.

## Credits

Rhythm Plus is built on the work of **Ghillermo**, the author of **Circuit Remix** and **CIRCUIT-HACKS**. His patcher, build tools and firmware work make this project possible. Please look at his projects and support his work:

- Circuit Remix (Circuit Rhythm): https://github.com/Ghillermo/CIRCUIT-REMIX
- CIRCUIT-HACKS (Circuit Tracks): https://github.com/Ghillermo/CIRCUIT-HACKS-RC
- Donate: https://PayPal.me/ghillermo

Rhythm Plus is a separate project. It is not Circuit Remix, and it does not include the Circuit Remix features.

## For developers

### Build

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

4. To install, `.venv/Scripts/python tools/make_app.py` makes the Rhythm Plus app, `tools/rhythm_plus_app.html`, from your builds. Open it in Chrome or Edge: its Firmware page installs a build, and its Packs and Backup pages manage the SD card.

#### Tests

The tests run the firmware in an emulator. They need:

- `DSPTOOL`: the path of the DSP56300 tool. CIRCUIT-HACKS' `tools/setup_dev.py` builds it (`ext/bin/dsptool`).
- A RAM dump of a Circuit Rhythm at `remix/stock/rhythm-ram-frd1-synced.bin`.

```bash
DSPTOOL=PATH/TO/dsptool PYTHON=.venv/Scripts/python bash tests/run_all.sh a0213
```

#### Update Circuit Remix's tools

`remix/` is a git submodule, fixed at the Circuit Remix version the builds are tested with. To use a newer one:

```bash
git -C remix fetch && git -C remix checkout origin/main
```

Then rebuild and compare the SHA-256 with the manifests before you commit the new submodule version.

### Repository

| Folder | What it holds |
|---|---|
| `builds/` | The scripts for the stable and test builds, and the builds they start from. |
| `modules/` | The features: each module adds its code to the firmware. |
| `tests/` | The emulator tests. |
| `tools/` | Setup, and the tools that make the manual and the Rhythm Plus app. |
| `manual/` | The user documentation. |
| `firmware/` | The `manifest.json` of the builds that the builds and tests use. The `.syx` / `.bin` files stay on your computer. |
| `remix/` | Circuit Remix (submodule): its build tools are used by the builds. |

## License

MIT, see [`LICENSE`](LICENSE). The MIT license does not apply to the Novation firmware. Circuit Remix (`remix/`) has its own MIT license.

Circuit Rhythm, Components and Novation are trademarks of Focusrite Audio Engineering Ltd.
