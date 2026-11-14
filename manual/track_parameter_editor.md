# Track Parameter Editor

This section defines the parameters that you can see and change in the Track Parameter Editor. It also tells you which of them you can automate or lock to a step.

Firmware: Rhythm Plus A0175 (test build).

## Terms

| Term | Definition |
|---|---|
| **Track Parameter Editor** | The track view. Tap the selected track's button to open it. Tap the button again to close it. Its knobs are the stock's own eight knobs of the track. It does not open on the FX track. |
| **Bar** | Pads 17-24. The bar shows the value of the shown knob. |
| **Shown knob** | The last knob that you turned, or the knob that you selected with pad 25. Its light is in the track's colour. |
| **View** | The bar shows the value of the parameter. |
| **Edit** | Turn the knob to change the value for the whole track. |
| **Automate** | Arm Record and turn the knob while the pattern plays. The movement is recorded into the steps. |
| **Lock** | Hold a step on pads 1-16, arm Record and turn the knob. The value is recorded into that step only. |
| **Reset** | Hold Clear and turn the knob right until it stops. The value goes back to its default and the knob light turns blue. |
| **Delete automation** | Hold Clear and turn the knob left until it stops. The automation of that knob is deleted and the knob light turns red. |

## The pads

| Pads | What they do |
|---|---|
| 1-16 | The steps of the pattern. Hold a step to view or lock its values. |
| 17-24 | The bar. |
| 25 | Shows the next knob on the bar, without turning it. |
| 26 | White. With Clear held: dim red; tap it to reset the eight knobs (below). |
| 27-32 | Dark. They do nothing. |

## The knobs

You can view, edit, automate, lock, reset and delete the automation of all eight.

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

- Knob turns record only while Record is armed.
- **Automate:** arm Record, play, turn the knob. The movement is recorded into the steps that play.
- **Lock:** arm Record, hold a step, turn the knob. The value goes into the held step, also while the pattern plays.
- While Record is armed and you turn a knob, the bar is red. While you hold a step with Record armed, the step's pad is red.

## Reset all eight knobs

| Action | Result |
|---|---|
| Hold Clear | Pad 26 turns dim red. |
| Hold Clear, tap pad 26 | The eight knobs go back to their defaults, the fine values too. Their automation in the current pattern is deleted, also with a step held. Pad 26 flashes red three times. |
| Let go of Clear | Pad 26 is white again. |

The reset works on the selected track only. It does not change the sample, the mixer, the FX sends or the Sample mode switches.
