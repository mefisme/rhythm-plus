# A0201 — Track Parameter Editor settings

Granular controls and native lane assignments from A0200 remain available. See
[the granular knob and assignment reference](granular-a0200.md). The Stock
settings and Shift behavior below supersede that build's Stock-view description.

## Track-wide settings

Use an SD-card pack. Open the Track Parameter Editor and tap **Stock pad 26**.
Hold pad 26 to open its settings; releasing after the hold leaves them latched.
Tap pad 26 once to return to values.

Alternatively, hold **Shift** while Stock is the active parameter pad view.
Its settings remain visible until Shift releases. Sticky Shift works too.
A separately pad-held latch survives a Shift press/release.

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

Shift now opens settings on Stock as well as Granular in supported SD projects.
Settings/assignment knob cycling always goes forward. Stock fine knob movement
still works under Shift, but its value bar is temporarily replaced by settings.
Internal-memory projects retain the previous native Stock behavior.

Selective automation copy is deferred. Native Duplicate behavior is unchanged.

A0201 has passed emulation; these new pad gestures still need hardware validation.
