# Track + parameters

This section defines the parameters that you can see and change in Track +. It also tells you which of them you can automate or lock to a step.

Firmware: Rhythm Plus AG015 (test build).

## Terms

| Term | Definition |
|---|---|
| **Track +** | The track menu. Tap the selected track's button to open it. Tap the button again to close it. |
| **Page** | A set of eight knobs for the selected track. Pads 26-31 select the page. Each track keeps its own page. |
| **Parameter Editor** | The page on pad 26 (white). Its knobs are the stock's own eight knobs of the track. |
| **Extra parameter** | A parameter that Rhythm Plus adds. Extra parameters are on Pitch (pad 29) and FX (pad 31). |
| **Bar** | Pads 17-24. The bar shows the value of the shown knob. |
| **Shown knob** | The last knob that you turned, or the knob that you selected with pad 25. Its light is in the track's colour. |
| **View** | The bar shows the value of the parameter. |
| **Edit** | Turn the knob to change the value for the whole track. |
| **Automate** | Arm Record and turn the knob while the pattern plays. The movement is recorded into the steps. |
| **Lock** | Hold a step on pads 1-16, arm Record and turn the knob. The value is recorded into that step only. |
| **Reset** | Hold Clear and turn the knob right until it stops. The value goes back to its default and the knob light turns blue. |
| **Delete automation** | Hold Clear and turn the knob left until it stops. The automation of that knob is deleted and the knob light turns red. |

## Parameter Editor (pad 26, white)

These are the stock's parameters. You can view, edit, automate, lock, reset and delete the automation of all eight.

| Knob | Parameter | Shift + knob | Bar |
|---|---|---|---|
| K1 | Pitch | - | from the middle |
| K2 | Sample start | fine start | 2048 steps a pad (coarse and fine together) |
| K3 | Sample length | fine length | 2048 steps a pad (coarse and fine together) |
| K4 | Envelope: left of the middle = decay, middle = sustain, right = slow attack | - | from the middle |
| K5 | Distortion | - | from the left |
| K6 | High-pass filter | - | from the left |
| K7 | Low-pass filter | - | from the left |
| K8 | Resonance | - | from the left |

### View a step's value

- Hold a step on pads 1-16. Each knob light turns red if that knob has automation on the step.
- If the shown knob has automation on the held step, the bar shows the step's value.

### Automate and lock

- Knob turns on this page are the stock's. They record only while Record is armed.
- **Automate:** arm Record, play, turn the knob. The stock records the movement into the steps that play.
- **Lock:** arm Record, hold a step, turn the knob. The value goes into the held step, also while the pattern plays.
- While Record is armed and you turn a knob, the bar is red. While you hold a step with Record armed, the step's pad is red.

## Extra parameters (Pitch and FX)

The extra parameters are kept for each track and saved with the project.

For all extra parameters:

| Action | Available |
|---|---|
| View | yes |
| Edit | yes |
| Automate | no |
| Lock | no |
| Reset (Clear + turn right) | yes |
| Delete automation (Clear + turn left) | no (an extra parameter has no automation) |

### Shift on the extra pages

- **Shape knobs and rate knobs in their synced half:** hold Shift and turn right to go to the same pad on the second sweep. Turn left to go back to the first sweep.
- **Other knobs:** Shift + turn moves the value in fine steps.
- **Exception:** Pitch page Shift + K7 is a separate parameter. It moves in normal steps.

### Pads 27 and 28

The Filter and Mix pages are archived. These pads are dark and do nothing.

### Pitch (pad 29, sky blue)

| Knob | Parameter | Shift + knob |
|---|---|---|
| K1 | Pitch envelope amount, from the middle | fine |
| K2 | Pitch envelope shape | second sweep |
| K3 | Pitch envelope decay | fine |
| K4 | Pitch LFO depth (vibrato) | fine |
| K5 | Pitch LFO shape | second sweep |
| K6 | Pitch LFO rate: right of the middle = synced, left = free | second sweep (synced half), fine (free half) |
| K7 | Random pitch: each note gets a random jump, up to 12 semitones up or down | LFO fade-in: at each note the vibrato grows from 0, up to 2 seconds |
| K8 | Glide: the pitch slides from the last note, up to about 1 second | fine |

To reset Shift + K7 (LFO fade-in): hold Clear, then hold Shift, then turn K7 right. Do not press Shift first: Shift + Clear changes the metronome.

### Granular (pad 30, lime)

The Granular page plays the track's sample as many short grains. It works inside the part of the sample that Sample start and Sample length (Parameter Editor K2, K3) set. Pad 25 does nothing on this page.

**Knobs**

| Knob | Parameter | What it does | Default |
|---|---|---|---|
| K1 | Position | Where in the sample the grains start. Left: the start of the sample. | Left |
| K2 | Size | The length of each grain: 5 ms at the left, 0.5 s at the right. | Middle |
| K3 | Density | How many grains play at the same time: 1 to 16. With Timing on: the chance that a step plays a grain. | 40 % |
| K4 | Scan | Moves Position by itself. Middle: stop. Right: forward. Left: backward. Further from the middle: faster. With Slice on: one part a step, on the tempo. | A little right of the middle |
| K5 | Position scatter | Each grain starts at a random place near Position, up to half the sample away. | Left (off) |
| K6 | Pitch scatter | Each grain gets a random pitch, up to 12 semitones up or down. | Left (off) |
| K7 | Edge | The fades of each grain. Left: short and hard. Middle: smooth. Right: a fast start and a long fade out. | Middle |
| K8 | Reverse | The chance that a grain plays backward. Right: all grains. | Left (off) |

**Shift + knob**

| Knob | Parameter | What it does | Default |
|---|---|---|---|
| Shift + K1 | Level | The volume of the grains, in fine steps. | Middle |
| Shift + K2 | Size scatter | Each grain is a random amount shorter. Right: up to its whole length. | Left (off) |
| Shift + K3 | Timing | Middle: off, Density spaces the grains. Left: a fixed time between grains, 0.5 s near the middle to 6 ms at the left. Right: one grain a step on the tempo: 1/2, 1/4, 1/4 triplet, 1/8, 1/8 triplet, 1/16, 1/16 triplet, 1/32. | Middle (off) |
| Shift + K4 | Jitter | Moves each grain earlier or later, up to one gap between grains. | Left (off) |
| Shift + K5 | Slice | Left: off. Right: cuts the sample into 2 to 16 equal parts; each grain starts at the start of a part. K1 Position jumps from part to part, and K4 Scan steps one part at a time on the tempo (the same eight steps as Timing). | Left (off) |
| Shift + K6 | Lock | Left: each grain is new. Right: the same 16 grains repeat in a loop. Between: some grains change each time round. It repeats position, pitch, length, timing and reverse. | Left (off) |
| Shift + K7, K8 | - | Dark. | - |

The bar: K4 and Shift + K3 fill from the middle. Shift + K3 on the tempo side moves half a pad a step. Shift + K5 lights half a pad for each part (16 parts fill all 8 pads). With Shift held, the bar and the live knobs are lime.

**Settings (hold pad 30, then tap a pad)**

| Pad | Setting | Lights | What it does |
|---|---|---|---|
| 17 | On / Off | Green: on. Red: off. It blinks while it changes. | Turns Granular on or off for the track. |
| 18 | Mode | White: Triggered. Amber: Texture. | Triggered: each note plays grains; One Shot stops at the sample's end, Gated and Loop at the note's end. Texture: the grains play all the time while the pattern plays, with a soft tail when it stops; a muted track plays no new grains; while stopped, a pad plays the grains as in Triggered. |
| 19 | Flow / Retrigger | Dim: Flow. Bright: Retrigger. Shown in Texture only. | Retrigger: each note from the pattern starts the grains again at Position. Flow: notes do not restart them. |
| 20 | Bounce | Dim: off. Bright: on. | Scan turns back at each end of the sample, in place of a jump to the other end. |
| 21 | Freeze | Dim: off. Bright: on. | Holds the sound on one spot: Scan and Position scatter stop, and notes do not restart the grains. |
| 22 | Pitch Set | Dim lime: Off. White: Octaves. Sky blue: Fifths. Amber: Minor. Pink: Major. | Tap to step. Pitch scatter (K6) picks only the notes of the set. |
| 23, 24 | - | Dark. | - |

**Reset**

- Clear + turn a knob right until it stops: that knob goes back to its default. For a Shift knob: hold Clear, then hold Shift, then turn.
- Clear + pad 30: all knobs, Shift knobs, Level, Flow, Bounce, Freeze and Pitch Set go back to their defaults. On / Off and the mode stay.
- Clear + the track button (track reset): also turns Granular off and resets its page.

The Granular values are kept for each track and saved with the project. They have no automation and no step locks.

### FX (pad 31, amber)

| Knob | Parameter | Shift + knob |
|---|---|---|
| K1 | Ring modulation amount | fine |
| K2 | Ring modulation frequency | fine |
| K3-K6 | none (dark) | - |
| K7 | Scan depth: moves the sample start point | fine |
| K8 | Scan speed: right of the middle = synced, left = free | second sweep (synced half), fine (free half) |

## Reset a whole page

| Action | Result |
|---|---|
| Hold Clear, tap pad 26 | The eight stock parameters go back to their defaults, and their automation in the current pattern is deleted (also with a step held). |
| Hold Clear, tap Pitch (29) or FX (31) | All extra parameters of that page go back to their defaults. |
| Hold Clear, tap pad 32 | All of the above: the stock parameters, their automation in the current pattern, and the extra parameters of all pages. |

All page resets work on the selected track only. They do not change the sample, the mixer or the FX page's sends.
The stock's filters and resonance remain on the Parameter Editor. Clear + pad 27 or 28 does nothing.

Projects saved on an archived Filter or Mix page open in the Parameter Editor. Old Filter/Mix settings remain in the project for compatibility and do not affect this build.
