# Granular — A0196 development build

Use an SD-card pack. Granular is unavailable on internal-memory projects in this build.

## Open and enable

Select a normal track and open the Track Parameter Editor. Tap **pad 32** for granular.
Hold **pad 32** to show its sound settings on pads 17–24. While holding it,
tap **pad 17** to turn the engine on or off. Pad 18 selects Triggered or Texture.
After a hold, release pad 32 and the settings stay open. Tap pad 32 once to return to the value bar. The engine starts disabled on a new project.
An FX-sequencer track cannot enable granular; an active or pending granular track cannot become the FX sequencer.

## Knobs and settings

Down alone selects secondary knobs; Up returns to primary knobs. Shift is unnecessary.
Pad 25 cycles the shown knob; an ordinary knob turn also selects it. The value bar follows the selected knob. Both value bars and selected knobs use the track color. Both arrows are granular green; brightness identifies the active page. Up identifies primary controls and Down secondary controls. The inactive arrow is much dimmer.

| Knob | Primary | Secondary |
|---|---|---|
| K1 | Position | Level |
| K2 | Size | Size scatter |
| K3 | Density | Timing: free / tempo |
| K4 | Scan | Jitter |
| K5 | Position scatter | Slice |
| K6 | Pitch scatter | Lock |
| K7 | Edge | Burst |
| K8 | Reverse chance | Burst speed |

Hold pad 32 for the original sound settings:

| Pad | Setting |
|---|---|
| 17 | Engine On/Off |
| 18 | Triggered / Texture |
| 19 | Flow / Retrigger (Texture) |
| 20 | Bounce |
| 21 | Freeze |
| 22 | Pitch set |
| 23 | Burst fade |
| 24 | Burst pitch |

## Shift settings belong to the active parameter pad view

In the active Granular parameter pad view, **hold Shift** to show sound settings.
While Shift is active, **Down** selects lane assignments and **Up** returns to sound settings.
Release Shift to return to values, on the same primary/secondary knob page as before.
With native sticky Shift, the layer stays visible until sticky Shift is turned off.

This belongs to the active parameter pad view, not to a global granular menu.
The Stock parameter pad view retains its original Shift/fine controls and has no added settings or assignment view.
Future parameter pad views need their own settings handler; they must not inherit granular settings.

The existing pad-hold entry remains available. A menu opened by holding pad 32
still latches and closes with a tap of pad 32. A later Shift press/release does not
cancel that independent pad-held latch. Shift-only entry returns to values when Shift disengages.

Outside settings, Up/Down still select primary/secondary knobs. Shift navigation never changes that selection.

## Assign automation

1. Hold **pad 32**, then press **Down while still holding pad 32**.
2. Release pad 32; the assignment view stays open. **Pad 25** cycles all 16 granular destinations. Turning a knob in this view does not change its value.
3. **Pads 17–24** select the lanes originally belonging to stock K1–K8.
4. Tap the highlighted assigned lane again to give it back to its stock knob.
5. Tap pad 32 once to leave assignment settings and return to values. Up within assignment settings returns to sound settings. Record on the granular knob page using the usual gestures.

Dim white lane pads belong to stock. Dim granular green indicates another assigned control in the current knob group. Dim red indicates a lane owned by the opposite knob group. Bright granular green marks the selected control's lane. Up/Down lights distinguish the primary and secondary destination groups. The arrows identify the primary/secondary group while cycling. In assignments, the selected knob is bright granular green and the other seven are fixed dim green; knob values are not displayed. Outside assignments, the selected knob uses the track color except red recording/held-lock feedback.
A control has at most one lane. Moving its assignment releases its previous lane.
Assignments apply to that track's eight patterns, independently on each of the eight tracks.

**Assignment changes preserve recorded values.** Reassigning a lane makes its existing values drive the new destination.
Unassigning returns those values to the original stock parameter. Clear the recording first if you do not want that behavior.
No lane is taken automatically.

## Record, clear and stock controls

Arm Record and turn an assigned granular knob while playing for live automation.
Hold a step and turn the knob with Record armed for a lock, stopped or playing.
While a step is held, only that step is written; playback continues.
The held lock's value is available for editing, and recording feedback belongs to the actual granular control.

Clear + turn follows the existing click threshold: left clears that control's assigned automation;
right clears it and resets its manual value. Clear follows the current pattern or held-step scope.
No Clear + lane-pad gesture is needed.

Original stock knobs remain manually adjustable. A borrowed lane does not record from its stock knob,
and clearing that stock knob cannot erase the granular recording. Stock editor knobs retain their normal colors; borrowed granular automation is not shown as stock held-lock or recording feedback.
Mixer level, pan, reverb and delay lanes remain native. The three independent global FX controls are unchanged.

The existing **Clear Track reset** also restores granular manual values/settings and stock lane ownership.
Native sequence clearing keeps its existing scope; another track is not changed.

## Saving and testing

Save writes granular settings, all 16 current knob positions and 64 lane assignments to the
existing `RP_AUTO/*.RPS` companion file. Automation values themselves stay in the native project's reassigned lanes.
Older projects without granular settings load granular defaults with stock ownership.
Unsaved edits remain in RAM; no temporary SD recording cache is used.

This retains A0193’s SO v4 / RA04 companion bundles with GS v2 granular settings.
Builds older than A0193 cannot restore this companion format. Use a copied pack for the first test and keep an earlier card backup for downgrading.

A0196 is a hardware-test build. Emulation covers storage/routing and rendered DSP audio;
live audio continuity and worst-case eight-track automation bandwidth still require hardware testing.
All eight tracks share 16 grains. The ARM-to-DSP control publisher has bounded bandwidth and serves tracks fairly;
heavy simultaneous automation can update less frequently than the native stored microstep points.

Terminology: Granular and Stock are parameter pad views. Within a parameter pad view, Up/Down select pages; Shift changes those arrows to settings page 1 / lane-assignment page 2.

## Settings indicator

The selected track stays steadily lit in the Track Parameter Editor.
Granular pad 32 pulses only while its sound settings or lane-assignment page is visible.
This uses the same nonzero-floor pulse as the Pattern/Step Mutate menus, regardless
of whether entry was by pad hold, held Shift or sticky Shift. It is not a recording indicator.
Value mode keeps pad 32 steady. Closing the menu or disengaging a Shift-only entry stops the pulse.
A retained pad-hold latch keeps pulsing until closed with a tap of pad 32.
The value bar and knob LEDs do not inherit this pulse; recording/held-lock red feedback remains separate.
