# Rhythm Plus

Rhythm Plus is a firmware for the **Novation Circuit Rhythm**. It is the original firmware 2.0.1 (build 5706) with **Track +** added: a track menu with pages of extra sound controls for each track. It also adds **Pattern Mutate**, a count-in and some workflow features.

## Credits

Rhythm Plus is built on the work of **Ghillermo**, the author of **Circuit Remix** and **CIRCUIT-HACKS**. His patcher, build tools and firmware work make this project possible. Please look at his projects and support his work:

- Circuit Remix (Circuit Rhythm): https://github.com/Ghillermo/CIRCUIT-REMIX
- CIRCUIT-HACKS (Circuit Tracks): https://github.com/Ghillermo/CIRCUIT-HACKS-RC
- Donate: https://PayPal.me/ghillermo

Rhythm Plus is a separate project. It is not Circuit Remix, and it does not include the Circuit Remix features.

> **Status: in development, no release yet.** A0122 removes the custom error reporter after A0121 removed the Filter and Mix pages; Normal, Pitch and FX stay in place. It is locally tested and has not been flashed for hardware validation. Automation development is on hold; granular synthesis is the next design discussion.

Legal note: the firmware from Novation is proprietary. This repository does not contain Novation's firmware or any file made from it. You supply the official firmware, and the build checks it. Do not install the result on any device other than a Circuit Rhythm.

> ⚠️ **Before you install: back up the SD card.**
> - Make a full copy of the SD card (projects, packs and samples) before you send any modified firmware.
> - Do not work on important projects on the device while you test a build.
> - A development build can have problems that damage stored projects or samples.
> - Novation's bootloader does not change: hold **Sample Rec + Samples + Note** while you switch the device on, then send the official firmware with Novation Components.

## Features

### Track +

Tap the selected track's button to open Track +. Tap it again to close it. While Track + is open:

| Pads | What they do |
|---|---|
| 1-16 | Select a step. Hold a step to see its values. Arm Record and turn a knob to record into the held step. |
| 17-24 | The bar: the value of the shown knob. |
| 25 | Selects the next knob. |
| 26-31 | The pages (below). Each track keeps its own page. |
| 32 | Hold Clear and tap pad 32: reset all pages of the track. |

| Pad | Page | Knobs |
|---|---|---|
| 26 | Parameter Editor (white) | The stock's eight knobs of the track |
| 27 | Reserved (dark) | Filter page archived |
| 28 | Reserved (dark) | Mix page archived |
| 29 | Pitch (sky blue) | Pitch envelope and LFO, random pitch, glide; Shift + K7: LFO fade-in |
| 30 | Granular (lime) | The grain engine: Position, Size, Density, Scan, scatter, Edge, Reverse; Shift: Level, Size scatter, Timing, Jitter, Slice, Lock |
| 31 | FX (amber) | Ring modulation, sample start scan |

- **Shapes:** 16 pitch-envelope shapes and 10 pitch-LFO shapes.
- **Rates:** right of the middle locks to the tempo (8 bars to 1/16, then the triplets); left of the middle is free. Hold Shift and turn to change between the two sweeps.
- **Clear + knob:** turn right until it stops: the knob goes back to its default (blue). Turn left until it stops: the knob's automation is deleted (red).
- **Clear + page pad:** reset that page for the track.
- The extra values are kept for each track and saved with the project.
- **Shift + Patterns** (View Lock) keeps Track + open. **Hold** the selected track's button to see the other view while you hold it.

All parameters, and what you can do with each one: [`manual/track_plus_parameters.md`](manual/track_plus_parameters.md).

### Pattern Mutate

On the Patterns, Mixer, Grid FX, FX or Sidechain page, hold Shift and tap Duplicate: each track gets a new play list, a short run of its own patterns in a random order. The track plays the list in a loop in place of its chain. Your patterns do not change. Hold Clear and tap Duplicate to go back to the chains (A0120: hold Clear and Shift and tap Duplicate).

- **Settings:** hold Shift and hold Duplicate, on the Patterns, Mixer, Grid FX, FX or Sidechain page. Shift + tap Duplicate on the page mutates and keeps it open. Column 1 on both pages: Live. Hold a view button, or Shift + a track button, to look at that view; let go and the settings come back. Page 1: Length, Length type, Pool, When. Page 2 (Down): Length 5-8, Amount, Repeats, Keep slot 1. The track buttons choose which tracks mutate.
- **Live:** each mutate keeps a seed for each track. With Live on, a setting change makes the lists again from the same seeds, while they play. Change the setting back and the lists come back. (AG016 and later.)
- **Scenes** keep each track's mutate. In a scene chain, a mutated track is done at the end of its list, and Play starts on the chain's first scene. View Lock works with a mutate.

### Granular

Track + pad 30 plays the track's sample as many short grains: clouds, drones, stutters and chopped beats. Hold pad 30 for its settings: on or off, Triggered or Texture, Flow or Retrigger, Bounce, Freeze and Pitch Set. Slice cuts the sample into 2 to 16 parts, Scan steps through them on the tempo, and Lock repeats the random grains as a loop. The Granular page is in the AG test builds.

The manual, with drawings of the pads: [`manual/rhythm_plus_manual.pdf`](manual/rhythm_plus_manual.pdf). It covers Pattern Mutate, Track +, the Pitch page and Granular.

### More

- **Metronome with count-in:** Shift + Clear steps through: no metronome (red), metronome (green), count-in only (magenta), both (cyan). With Record armed, Play from stop counts one bar, and the music starts on the 1. The count follows the music's clock, its own or an external MIDI clock.
- **Sample Rec count-in:** in the Sample Rec view, pad 23 turns the count on. With pad 24, the music and the sampling start together on the 1.
- **Fixed recording with an external MIDI clock:** the fixed-length sample recording follows the external clock's tempo.
- **Faster start:** the first steps load faster when you press Play.
- **Track reset:** hold Clear, press a track button, let go of it and press it again (Clear still held): the track's sound knobs and extra values go back to their defaults and its automation in the current pattern is deleted (three red flashes). The notes stay.
- **Sample mode:** hold Clear and tap pad 1 or 2: the pitch goes back to the sample's own pitch.

## Install

An installer comes with the first release.

**Back to the official firmware:** use Novation Components. If the device does not start, hold **Sample Rec + Samples + Note** while you switch it on (Novation's bootloader mode), then send the official firmware.

## Build

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
   .venv/Scripts/python builds/build_a0085.py
   ```

   The result is in `firmware/a0085/`: `rhythmplus-A0085.syx` (to send), `.bin` and `manifest.json`. The build is reproducible: the manifest records the SHA-256 of the result.

### Tests

The tests run the firmware in an emulator. They need:

- `DSPTOOL`: the path of the DSP56300 tool. CIRCUIT-HACKS' `tools/setup_dev.py` builds it (`ext/bin/dsptool`).
- A RAM dump of a Circuit Rhythm at `remix/stock/rhythm-ram-frd1-synced.bin`.

```bash
DSPTOOL=PATH/TO/dsptool PYTHON=.venv/Scripts/python bash tests/run_all.sh a0085
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
| `builds/` | One script for each version (`build_a0120.py` is the newest). |
| `modules/` | The features: each module adds its code to the firmware. |
| `tests/` | The emulator tests. |
| `tools/` | Setup and the installer page generator. |
| `manual/` | The user documentation. |
| `firmware/` | Each version's `manifest.json`. The `.syx` / `.bin` files stay on your computer. |
| `remix/` | Circuit Remix (submodule): its build tools are used by the builds. |

## License

MIT, see [`LICENSE`](LICENSE). Circuit Remix (`remix/`) has its own MIT license.

Circuit Rhythm, Components and Novation are trademarks of Focusrite Audio Engineering Ltd. This project is not affiliated with them.
