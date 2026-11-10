# Track + parameters

This section defines the parameters that you can see and change in Track +. It also tells you which of them you can automate or lock to a step.

Firmware: Rhythm Plus A0121 (local development build; not yet tested on hardware).

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

### Pad 30

No page. The pad is dark.

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
The stock's filters and resonance remain on the Parameter Editor. Clear + pads 27, 28 or 30 does nothing.

Projects saved on an archived Filter or Mix page open in the Parameter Editor. Old Filter/Mix settings remain in the project for compatibility and do not affect this build.
