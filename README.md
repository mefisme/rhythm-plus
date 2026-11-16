# Rhythm Plus

Rhythm Plus is a custom firmware for the **Novation Circuit Rhythm**. It is the original firmware 2.0.1 (build 5706) with **Pattern Mutate**, **Step Mutate**, **Grid FX sends**, an **FX track**, the **Track Parameter Editor** (a full view of each track's knobs), switches for each track's sample, a count-in and some workflow features.

## Credits

Rhythm Plus is built on the work of **Ghillermo**, the author of **Circuit Remix** and **CIRCUIT-HACKS**. His patcher, build tools and firmware work make this project possible. Please look at his projects and support his work:

- Circuit Remix (Circuit Rhythm): https://github.com/Ghillermo/CIRCUIT-REMIX
- CIRCUIT-HACKS (Circuit Tracks): https://github.com/Ghillermo/CIRCUIT-HACKS-RC
- Donate: https://PayPal.me/ghillermo

Rhythm Plus is a separate project. It is not Circuit Remix, and it does not include the Circuit Remix features.

> **Status: A0213 is the stable build** (in the uploader). Development continues from it. A0213 made Freeze hold the whole sound while the knobs keep working. A0212 added up to 32 slices, with one lit pad per Slice and Lock choice. It gives Timing, Slice and Lock clear zones, makes Slice-mode scatter jump whole slices and draws the value bar at Stock brightness. It puts Granular on pad 27 and shows the value bar while a knob turns over open settings. It has fine adjust: Shift + turn moves six Granular knobs (Position, Size, Density, Scan, Position scatter, Pitch scatter) in 1/16 steps, saved in the SD companion. Burst is removed and the knob cycle pad only goes forward. It keeps lossless DSP compression, full Granular, parameter-view ownership, LED fixes and track settings, with 10,220 firmware bytes free. Tested on the unit. See [controls and settings](manual/granular-a0201.md).

Legal note: the firmware from Novation is proprietary. This repository does not contain Novation's firmware or any file made from it. You supply the official firmware, and the build checks it. Do not install the result on any device other than a Circuit Rhythm.

> ⚠️ **Before you install: back up the SD card.**
> - Make a full copy of the SD card (projects, packs and samples) before you send any modified firmware.
> - Do not work on important projects on the device while you test a build.
> - A development build can have problems that damage stored projects or samples.
> - Novation's bootloader does not change: hold **Sample Rec + Samples + Note** while you switch the device on, then send the official firmware with Novation Components.

## Features

### Playhead scrub

Hold **Shift + Play** and turn **K1** to move through the active scene chain, or the longest track pattern chain in the selected scene. Page and pattern boundaries do not interrupt scrubbing.

- Scrubbing onto the first or last step stops playback and holds there. Outward turns retrigger that boundary step: left at the beginning, right at the end. Turn inward or tap Shift + Play to continue. Normal playback still starts and loops as usual.
- **K2 right:** audition while stopped (default on, green). **K2 left:** silent stopped scrubbing (red). Running playback remains audible.
- **K3–K8:** dark and disabled while held. Normal knob controls return on release.
- Stopped audition uses normal sample playback, with no time stretching or turntable effect. Preview notes release when you let go or stop turning.

### Track Parameter Editor

Tap the selected track's button to open the Track Parameter Editor. Tap it again to close it. While it is open:

| Pads | What they do |
|---|---|
| 1-16 | Select a step. Hold a step to see its values. Arm Record and turn a knob to record into the held step. |
| 17-24 | The bar: the value of the shown knob. |
| 25 | Selects the next knob. |
| 26 | White. Hold Clear: it turns dim red. Tap it: the track's eight knobs go back to their defaults and their automation in the current pattern is deleted (three red flashes). |
| 27-32 | Dark. They do nothing. |

- **Clear + knob:** turn right until it stops: the knob goes back to its default (blue). Turn left until it stops: the knob's automation is deleted (red).
- **Shift + Patterns** (View Lock) keeps the Track Parameter Editor open. **Hold** the selected track's button to see the other view while you hold it.

All parameters, and what you can do with each one: [`manual/track_parameter_editor.md`](manual/track_parameter_editor.md).

### Pattern Mutate

On the Patterns, Mixer, Grid FX, FX or Sidechain page, hold Shift and tap Duplicate: each track gets a new play list, a short run of its own patterns in a random order. The track plays the list in a loop in place of its chain. Your patterns do not change. Hold Clear and tap Duplicate to go back to the chains (A0120: hold Clear and Shift and tap Duplicate).

- **Settings:** hold Shift and hold Duplicate, on the Patterns, Mixer, Grid FX, FX or Sidechain page. Shift + tap Duplicate on the page mutates and keeps it open. Column 1 on both pages: Live. Hold a view button, or Shift + a track button, to look at that view; let go and the settings come back. Page 1: Length, Length type, Pool, When. Page 2 (Down): Length 5-8, Amount, Repeats, Keep slot 1. The track buttons choose which tracks mutate.
- **Live:** each mutate keeps a seed for each track. With Live on, a setting change makes the lists again from the same seeds, while they play. Change the setting back and the lists come back. (AG016 and later.)
- **Scenes** keep each track's mutate. In a scene chain, a mutated track is done at the end of its list, and Play starts on the chain's first scene. View Lock works with a mutate.

### Step Mutate

On a track's page, hold Shift and tap Duplicate: the selected track's pattern changes, from its start step to its end step. Each track has its own settings. There is no undo: to keep a pattern, duplicate it first.

- **Settings:** hold Shift and hold Duplicate on a track's page (in the Track Parameter Editor too: a Duplicate tap takes you back to it). Tap a target to turn it on or off, hold it to show its settings on columns 6-8. Tap Duplicate or the selected track's button to close the page. Hold a view button to look at its first view (Shift + hold: its second view), or the selected track's button to look at its Note or Sample view; let go and the page comes back.
- **Targets:** note, sample flip, step movement, velocity, gate, microsteps, pattern length, pattern speed, play mode and probability. Most have an Amount (the share of the steps with a note that change) and a Range.
- **Sample flip:** Range Any, Growing (one sample up or down from the step's flip), within 8 or within 4 of the track's sample. Pink only or All steps.
- **Clear + a target pad** on the settings page: that target goes back to the stock default on the steps from start to end. The settings stay.
- **Default:** step movement only, all steps, anywhere: the stock Mutate's shuffle, with the stock's random generator.

### Grid FX sends

Keep tracks out of Grid FX. In the Mixer or Grid FX view, press Down to the pan knobs, then Down again: the sends page. Each knob is a track's send into Grid FX: full = as the stock, 0 = Grid FX does not touch the track. Clear + knob = full. Up goes back to the pans. The pads stay as the view's. The level, pan, mute, sidechain and master filter still work on the whole track; the shared delay and reverb still go through Grid FX. Saved with the project.

### The FX track

One track can play Grid FX in time with the pattern. In Sample mode, tap pad 8 on any track: it is the FX track (pad 8 bright amber); tap again and it is a normal track with its own samples, flips and knobs. Hold Clear and tap pad 8 to clear the track (pad 8 flashes red). Only one track at a time. The FX track does not play its own samples; its steps turn the Grid FX pads on for the note's length, on the whole mix. In its sample view, pads 1-16 are the steps and pads 17-32 the 16 Grid FX pads, played live as on the Grid FX page (a held or latched pad is white). Hold pads and tap a step for a pink step with those pads; hold a step and tap pads to put them on or off it; tap an empty step for a blue step (the selected pad, which pulses white). Recording makes pink steps with the pads played, with their gate lengths (all the pads pressed on one step; on a step with pads, in place of them). Note and Velocity are off on the FX track. Record, gate, microsteps, probability, length, speed, play modes and the Mutates work as on any track. Each step's pads play for its gate, under the next steps too; the same effect type on a newer step takes over with no restart, or starts again after a gap. Hold a step + Down / Up: random / repeat. Hold a pad + Up: all its Grid FX settings on the knobs, the effect type too; Down: the sends. Its K1-K8 are the eight sends; turned on the sends page with Record on, they record as its automation. The Grid FX view lights the pads it plays. Its track button is lit amber, and the Mixer button dim amber on the other views; the Track Parameter Editor does not open on it. The steps share the track's steps; their effects are saved in the project apart from the track's data (47 sets of pads a project).

The manual, with drawings of the pads: [`manual/rhythm_plus_manual.pdf`](manual/rhythm_plus_manual.pdf). It covers Pattern Mutate, Step Mutate, the Track Parameter Editor, the Sample mode switches, the Grid FX sends and the FX track.

### More

- **Metronome with count-in:** Shift + Clear steps through: no metronome (red), metronome (green), count-in only (magenta), both (cyan). With Record armed, Play from stop counts one bar, and the music starts on the 1. The count follows the music's clock, its own or an external MIDI clock.
- **Sample Rec count-in:** in the Sample Rec view, pad 23 turns the count on. With pad 24, the music and the sampling start together on the 1.
- **Fixed recording with an external MIDI clock:** the fixed-length sample recording follows the external clock's tempo.
- **Faster start:** the first steps load faster when you press Play.
- **Track reset:** hold Clear, press a track button, let go of it and press it again (Clear still held): the track's sound knobs go back to their defaults and its automation in the current pattern is deleted (three red flashes). The notes stay.
- **Sample mode:** pads 19, 20 and 21 are switches for the selected track: 19 loop crossfade (default off), 20 drone (off), 21 end fade (on). The project saves them. Hold Clear and tap pad 1 or 2: the pitch goes back to the sample's own pitch.

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

   From A0125 on, one module (`modules/stepmut.c`) is C. It needs zig 0.13: set `RH_ZIG` to the path of `zig.exe` (default `buildtmp/zig-toolchain/ziglang/zig.exe`).

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
| `builds/` | One script for each version (`build_a0143.py` is the newest). |
| `modules/` | The features: each module adds its code to the firmware. |
| `tests/` | The emulator tests. |
| `tools/` | Setup and the installer page generator. |
| `manual/` | The user documentation. |
| `firmware/` | Each version's `manifest.json`. The `.syx` / `.bin` files stay on your computer. |
| `remix/` | Circuit Remix (submodule): its build tools are used by the builds. |

## License

MIT, see [`LICENSE`](LICENSE). Circuit Remix (`remix/`) has its own MIT license.

Circuit Rhythm, Components and Novation are trademarks of Focusrite Audio Engineering Ltd. This project is not affiliated with them.
