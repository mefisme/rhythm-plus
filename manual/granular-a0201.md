# A0201 — Track Parameter Editor settings

## Fine adjust and Burst removal

On Granular's primary knob page, hold **Shift** (or use sticky Shift) and turn:

| Knob | Control | Shift + turn |
|---|---|---|
| K1 | Position | 1/16 of a knob step |
| K2 | Size | 1/16 of a knob step |
| K3 | Density | 1/16 of a knob step |
| K4 | Scan | 1/16 of a knob step |
| K5 | Position scatter | 1/16 of a knob step |
| K6 | Pitch scatter | 1/16 of a knob step |
| K7 | Edge | normal step |
| K8 | Reverse chance | normal step |

- Each fine control has 2,048 positions instead of 128.
- Keep turning and the fine steps carry into the next knob step.
- A turn without Shift moves whole knob steps and keeps the fine part.
- With Shift, the other primary knobs and all secondary knobs turn as they do
  without Shift.
- Clear + turn, a value-bar tap, Clear + Granular pad 27 and Clear Track set the
  fine part to 0.

Fine adjust is manual only, like Stock's fine Start and Length. A Shift turn
never records automation or a step lock, even with Record armed. Recorded steps
hold the 7-bit knob value; on playback the knob takes that value and keeps
its fine part.

Save stores the fine parts in the `RP_AUTO/*.RPS` SD companion. Its settings
section is **GS v5**, 288 bytes. A0213 reads GS v2–v5 companions; v2–v4 load with every
fine part at 0. A0206 and older builds cannot read GS v5, so keep a card backup
if you need to go back.

With all fine parts at 0, the granular engine renders the same audio as A0206.

Burst is removed:

- Secondary **K7** and **K8** are dark and do nothing. Pad 25 cycles the six
  secondary knobs, K1–K6.
- Sound settings pads **23** and **24** are dark and do nothing.
- The assignment cycle has 14 controls: the 8 primary and secondary K1–K6.
  While a secondary control is selected, K7 and K8 are dark, so the knobs show
  which set you are on.
- Saved Burst values are ignored. A sound lane assigned to Burst in an older
  project stays reserved; assign it to another control to reuse it.

## Freeze (A0213)

Sound settings **pad 21** freezes the sound. While Freeze is on:

- the playhead stops: Scan does not move it;
- in Slice mode, the slice step stops;
- every random choice is held, as with Lock fully right: the same 16 grains
  loop, including their Position scatter, Pitch scatter, Reverse chance, Size
  scatter and Jitter.

All knobs still work while frozen. Turn **Position** to move the held spot.
Turn **K5 Position scatter** to widen or narrow the held area: the same frozen
pattern spreads over more or less of the sample, or over more or fewer slices.
Tap pad 21 again to release; everything moves again.

Lock repeats a pattern while the sound keeps moving. Freeze holds the sound.

## Timing, Slice and Lock zones (A0212)

These second-page knobs now have a few clear zones. The value bar shows the zone.

**K3 Timing.** Left of the middle: free spacing, as before. The middle: off.
Right of the middle, eight zones, one grain every:

| Zone | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Grain every | 1 step | ⅔ step | ½ step | ⅓ step | ¼ step | ⅙ step | ⅛ step | 1/12 step |

Fast zones sound like ratchets; the last zones become a buzz.

**K5 Slice.** One pad lights to show the choice:

| Lit pad | 17 white | 17 colour | 18 | 19 | 20 | 21 | 22 | 23 | 24 |
|---|---|---|---|---|---|---|---|---|---|
| Slices | off | 2 | 3 | 4 | 6 | 8 | 12 | 16 | 32 |

Off and 2 are each a short zone at the far left of the knob. Every other
choice is 1/8 of the knob. With value-bar tap editing on, tap pads 18–24 to
pick 3–32, or pad 17 for off. For a 2-bar loop, 32 gives one slice per step.

Slices are equal pieces of time between Stock's Start and End, not hits.
In Slice mode, **Position scatter** jumps to a random whole slice and wraps
around the loop. Scatter smaller than one slice keeps the playhead's slice.

**K6 Lock.** Three zones. Lock repeats the random choices: Position scatter,
Pitch scatter, Reverse chance, Size scatter and Jitter. With all of those at 0,
Lock has nothing to repeat.

| Knob | Left third | Middle third | Right third |
|---|---|---|---|
| Lock | off: random | loose: about 1 grain in 4 changes | locked: the same 16 grains loop |
| Lit pad | 17 white | 20 | 24 |

Projects saved with older builds keep their knob positions, so Timing, Slice
and Lock can land in a different zone.

## Value bar brightness

Granular's value bar uses Stock's levels. A centred knob at the centre shows
the two middle pads in Stock's white; a knob at 0 shows pad 17 in that white.

## Granular pad moves to pad 27 (A0210)

The Granular parameter pad view is now on **pad 27**, next to Stock's pad 26.
Every gesture that used pad 32 now uses pad 27: tap to open, hold for
settings, Clear + pad 27 to reset. Pad 32 is dark.

## Value bar while settings are open (A0210)

When Stock or Granular settings are open (Shift held, or latched by holding
the parameter pad), turning a knob shows the value bar on pads 17–24. The
settings pads come back 500 ms after the last turn. This includes Shift + turn
fine adjust. Assignment pages keep their pads, because knobs do nothing there.

A0213 has 10,220 bytes of firmware space free. Fine adjust needs no extra RAM.

## Earlier builds

A0206 stores the DSP program compressed and restores the exact original
instructions during loading. Granular sound, controls, assignments, automation
and project formats remain unchanged. It recovers another 9,376 firmware bytes,
leaving 11,324 bytes free. It uses a dedicated 288-byte SRAM slot, without
borrowing automation ITCM or the companion-file buffers. Physical boot/load
timing still needs hardware confirmation.

A0205 retains these controls and A0204 behavior while removing unused firmware
routines. Granular sound, grain budget, controls, assignments and the companion
format are unchanged. Free firmware storage increases from 620 to 1,948 bytes.

A0204 clears automation by **parameter-view ownership**:

- Clear + Stock pad 26 resets Stock values and clears only Stock-owned sound
  lanes in the viewed pattern. Lanes assigned to Granular are protected.
- Clear + Granular pad 32 resets its manual settings and clears only lanes
  assigned to its primary or secondary controls in that pattern.
- Either target can be cleared regardless of which parameter pad view is open.
  Whole-view clear affects the full lane even with a step held; individual
  Clear + knob retains native held-step scope. Assignments remain attached.
- Notes, other patterns/tracks, and mixer/send lanes remain untouched by these
  view resets. Clear Track is the explicit exception that resets the whole track.

Future parameter pad views must follow the same ownership rule; a borrowed lane
can be cleared only from its owning view/control, or by an explicit whole-track reset.

A0203 additionally keeps Granular's knobs/value bar at normal brightness while
Clear is held. Stock and Granular parameter pads both show Stock's reset cue;
Clear + tapping one flashes only that reset target. Stock's native Clear preview
colors are preserved, including when its automation lanes belong to Granular.
This is not an ownership-color indicator. Outside the editor, native lighting
is unchanged. The companion format and saved settings are unchanged.

A0202 retains these controls and aligns Granular LED feedback with Stock:

- Clear left/right feedback uses Stock's palette and dimming brightness.
  Releasing Clear restores normal knob colors and resets the next gesture.
- Recording a turn or a parameter lock flashes the **value bar red**, using
  Stock's short movement timeout (500 ms after the last movement). The bar
  then returns to track color, even if the step remains held.
- The assigned knob also turns red **during a recording turn**, returning to its
  normal color when the movement indication expires. Playback alone does not
  make it red. A **held step containing its automation** keeps it red, including
  with Record off, until the step is released.

Live knob feedback is temporary, rather than latched for the rest of recording.

Granular controls and native lane assignments from A0200 remain available. See
[the granular knob and assignment reference](granular-a0200.md). The Stock
settings and Shift behavior below supersede that build's Stock-view description.

## Track-wide settings

Use an SD-card pack. Open the Track Parameter Editor and tap **Stock pad 26**.
Hold pad 26 to open its settings; releasing after the hold leaves them latched.
Tap pad 26 once to return to values.

Alternatively, hold **Shift** while Stock is the active parameter pad view.
Its settings show while Shift is held.

| Settings pad | Track-wide option | Default |
|---|---|---|
| 17 | Value-bar tap and slide editing | Off |
| 18 | Silent step selection | Off |

These toggles are bright white when enabled and dim white when disabled.
Pads 19–24 are dark. They are settings controls, not automation targets.
The options belong to the selected track and apply to both Stock and Granular
parameter pad views, including both Granular knob pages.

The active parameter pad pulses while its settings are visible, using the same
pulse as Granular and Mutate. The selected track button stays steady.
Stock currently has one settings page; its arrows do not enter Granular assignments.

## Tap, slide and center

When tap editing is enabled, pads **17–24** act as a coarse slider for the knob
selected by pad 25. Turning a knob also selects it, as before.
Sliding across the pads updates on each newly touched pad.
The eight positions are **0, 18, 36, 54, 72, 90, 108, 127**.
Press the two center pads, **20 and 21**, together for exactly **64**.
Knob turns remain available for finer adjustment.

With Record off, taps adjust the manual value. With Record armed, an assigned
control records using the same live/held-step boundary as its knob:

- While playing, taps record live automation.
- Hold a step and tap or slide to record only that step's lock, stopped or playing.
- Stock controls whose lanes belong to Granular remain manually adjustable but
  cannot overwrite that borrowed automation.

Settings and assignment pads retain their own functions; they never become a slider.
With the option off, the value bar remains display-only.

## Silent selection

When enabled, selecting a step in the Track Parameter Editor does not audition
its sample. The step remains selected for inspecting and editing parameter locks.
Sequence playback continues normally. Pad behavior outside the editor is unchanged.

## Saving and compatibility

Explicit Save stores these two options per track in the existing
`RP_AUTO/*.RPS` SD companion, alongside Granular settings, all manual knob
positions, lane assignments and remembered views/pages.
No extra RAM or companion-file bytes are needed. Unsaved edits stay in RAM.
Clear Track resets the options to Off as well as the existing Granular reset.

The fixed 224-byte settings section is now **GS v4**. A0201 imports GS v2/v3
companions; older projects start with both new options Off. Startup, pack-load
and project-switch integration points are unchanged.
After saving in A0201, A0200 and older builds cannot restore that GS v4 section;
keep a card backup if you need to downgrade.

Holding Shift shows settings on Stock as well as Granular in supported SD
projects. Internal-memory projects
have no Stock settings.

Selective automation copy is deferred. Native Duplicate behavior is unchanged.

A0201 has passed emulation; these new pad gestures still need hardware validation.
