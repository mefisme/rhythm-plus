"""tools/uploader.html: the authors' Circuit Remix installer page (tools/make_rm_uploader.py) with only the builds of this folder.
tools/rm_uploader.html is not touched.

    python tools/make_uploader.py         (needs firmware/<dir>/*.bin and the stock image)
"""
import base64
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import make_rm_uploader as m  # noqa: E402
import rh_fw  # noqa: E402

MINE = ("AD007", "AD004", "AD003", "AD002", "AD001", "A0122", "A0120", "A0119", "A0118", "A0117", "A0116", "A0115", "A0114", "A0113", "A0112", "A0111", "A0110", "A0109", "A0108", "A0107", "A0106", "A0105", "A0104", "A0103", "A0102", "A0101", "A0100", "A0099", "A0098", "A0097", "A0096", "A0095", "A0094", "A0093", "A0092", "A0091", "A0090", "A0089", "A0088", "A0087", "A0086", "A0085", "A0084", "A0083", "A0082", "A0081", "A0080", "A0079", "A0078", "A0077", "A0076", "A0075", "A0074", "A0073", "A0072", "A0071", "A0070", "A0069", "A0068", "A0066", "A0065", "A0064", "A0063", "A0020", "A0019", "A0018", "A0017", "A0016", "A0015", "A0014", "A0013", "A0012", "A0011", "A0010", "A0009", "A0008", "A0001", "A04FS", "A0.04F", "STC11", "STC10", "STCI9", "ST2FX", "STFRS", "A0.03F", "A03FS", "STPF1", "STPD5")
DESC = {
    "AD007": ("Research build with a CONFIRMED Grid FX conflict in its optional full-bank test. Do not flash for a new memory test or refill the full candidate bank. First-playback prototype fix and bounded lock restore remain available; no SD automation persistence.", "Research build with a CONFIRMED Grid FX conflict in its optional full-bank test. Do not flash for a new memory test or refill the full candidate bank. First-playback prototype fix and bounded lock restore remain available; no SD automation persistence."),
    "AD004": ("Research prototype with KNOWN first-playback suspension bug after stopped lock recording. Do not flash for a new test. Volatile one-lane Track 1 Pattern 1 proof; no saved automation.", "Research prototype with KNOWN first-playback suspension bug after stopped lock recording. Do not flash for a new test. Volatile one-lane Track 1 Pattern 1 proof; no saved automation."),
    "AD003": ("Diagnostic only: AD002 fixed-window transfer proof using stock consecutive reads. Guided stopped-playback timing test; no automation feature yet.", "Diagnostic only: AD002 fixed-window transfer proof using stock consecutive reads. Guided stopped-playback timing test; no automation feature yet."),
    "AD002": ("Diagnostic only: AD001 + keyed, fixed-window core-0 X/Y RAM canaries and DSP-to-ITCM lossless decoder transfer timing. No SD/sample-memory writes or DSP program changes. Guided test only.", "Diagnostic only: AD001 + keyed, fixed-window core-0 X/Y RAM canaries and DSP-to-ITCM lossless decoder transfer timing. No SD/sample-memory writes or DSP program changes. Guided test only."),
    "AD001": ("Diagnostic only: A0120 + opt-in ITCM canary and lossless decoder benchmarks. No Track + automation yet; no SD writes. Use only for the guided test.", "Diagnostic only: A0120 + opt-in ITCM canary and lossless decoder benchmarks. No Track + automation yet; no SD writes. Use only for the guided test."),
    "A0122": ("Base de prueba sin Granular: sin las páginas Filter y Mix ni el aviso de error de Clear.", "Test base with no Granular: no Filter or Mix pages and no Clear error light."),
    "A0120": ("A0119 + View Lock works over a mutate: its white pads always show, and Shift + pad moves them without ending the mutate.", "A0119 + View Lock works over a mutate: its white pads always show, and Shift + pad moves them without ending the mutate."),
    "A0119": ("A0118 + a mutate while stopped shows the whole new list (the old paused pad hidden until you play).", "A0118 + a mutate while stopped shows the whole new list (the old paused pad hidden until you play)."),
    "A0118": ("A0117 + Keep slot 1 on page 2 of the mutate page: On, each list starts on the chain's first pattern.", "A0117 + Keep slot 1 on page 2 of the mutate page: On, each list starts on the chain's first pattern."),
    "A0117": ("A0116 + Repeats On / Off on page 2 of the mutate page: Off, no pattern twice in a row.", "A0116 + Repeats On / Off on page 2 of the mutate page: Off, no pattern twice in a row."),
    "A0116": ("A0115 + Amount on page 2 of the mutate page: how much of the chain a mutate changes (All, Most, Some, A little).", "A0115 + Amount on page 2 of the mutate page: how much of the chain a mutate changes (All, Most, Some, A little)."),
    "A0115": ("A0114 + a mutated track's list pads bright again (as A0112); only the pads not in the list are darker.", "A0114 + a mutated track's list pads bright again (as A0112); only the pads not in the list are darker."),
    "A0114": ("A0113 + on the Patterns page, Clear + a track with no mutate does nothing (no track change).", "A0113 + on the Patterns page, Clear + a track with no mutate does nothing (no track change)."),
    "A0113": ("A0112 + a mutated track's list pads that are not playing are dimmer, so the pattern playing stands out.", "A0112 + a mutated track's list pads that are not playing are dimmer, so the pattern playing stands out."),
    "A0112": ("A0111 + with Clear held, only the mutated tracks light (green); the others are dark.", "A0111 + with Clear held, only the mutated tracks light (green); the others are dark."),
    "A0111": ("A0110 + the stock's track colours on the Patterns page: the mutated tracks show green only while Clear is held.", "A0110 + the stock's track colours on the Patterns page: the mutated tracks show green only while Clear is held."),
    "A0110": ("A0109 + the Mixer's scene save, copy and clear keep the mutate: Shift + a scene pad saves each track's mutate with the scene.", "A0109 + the Mixer's scene save, copy and clear keep the mutate: Shift + a scene pad saves each track's mutate with the scene."),
    "A0109": ("A0108 + Clear for the mutate: on the Patterns page Clear + a track ends its mutate; Clear held shows the mutated tracks green; Clear + Shift turns Duplicate red; on the mutate page Clear held shows the mutate; a deleted mutate flashes red.", "A0108 + Clear for the mutate: on the Patterns page Clear + a track ends its mutate; Clear held shows the mutated tracks green; Clear + Shift turns Duplicate red; on the mutate page Clear held shows the mutate; a deleted mutate flashes red."),
    "A0108": ("A0107 + with Shift held the pads keep showing the mutate; only the track buttons show the stock's Shift lights.", "A0107 + with Shift held the pads keep showing the mutate; only the track buttons show the stock's Shift lights."),
    "A0107": ("A0106 + Shift held on the Patterns page shows the stock's lights; only Duplicate keeps its green.", "A0106 + Shift held on the Patterns page shows the stock's lights; only Duplicate keeps its green."),
    "A0106": ("A0105 + on the mutate page, Clear held shows the mutated tracks green; Clear + a track button ends that track's mutate.", "A0105 + on the mutate page, Clear held shows the mutated tracks green; Clear + a track button ends that track's mutate."),
    "A0105": ("A0104 + the Duplicate button green: dim with Shift held, pulsing on the mutate page, full while pressed.", "A0104 + the Duplicate button green: dim with Shift held, pulsing on the mutate page, full while pressed."),
    "A0104": ("A0103 + each scene keeps the mutate lists it is saved with; pushing the scene plays them.", "A0103 + each scene keeps the mutate lists it is saved with; pushing the scene plays them."),
    "A0103": ("A0102 + Play starts a track that has a mutate list on the list's first pattern.", "A0102 + Play starts a track that has a mutate list on the list's first pattern."),
    "A0102": ("A0101 + Clear + Shift + Duplicate ends every track's mutate list, on or off in the settings.", "A0101 + Clear + Shift + Duplicate ends every track's mutate list, on or off in the settings."),
    "A0101": ("A0100 + on a track with a mutate list, the pads not in the list are very dim: tap any of them to take the track back to its chain.", "A0100 + on a track with a mutate list, the pads not in the list are very dim: tap any of them to take the track back to its chain."),
    "A0100": ("A0099 + the Patterns page reads its page number as the stock does: the list's pads show on the page you look at, and a pad press works as the stock's.", "A0099 + the Patterns page reads its page number as the stock does: the list's pads show on the page you look at, and a pad press works as the stock's."),
    "A0099": ("A0098 + the Patterns page shows a track's mutate list on its pads: the list's patterns lit in the track colour, the one playing as the stock's, the old chain dark. A scene press in the Mixer ends every list at once.", "A0098 + the Patterns page shows a track's mutate list on its pads: the list's patterns lit in the track colour, the one playing as the stock's, the old chain dark. A scene press in the Mixer ends every list at once."),
    "A0098": ("A0097 + the pattern mutate: on the Patterns page, Shift + tap Duplicate gives each track that is on a new play list of its patterns, by the settings page. Clear + Shift + Duplicate gives back the chains. A pattern pad or a scene ends a track's list. Tracks with a list have soft green buttons. The lists save with the project. On the settings page, Random's Length bar lights only the chosen pad, and Duplicate pulses lime, not green.", "A0097 + the pattern mutate: on the Patterns page, Shift + tap Duplicate gives each track that is on a new play list of its patterns, by the settings page. Clear + Shift + Duplicate gives back the chains. A pattern pad or a scene ends a track's list. Tracks with a list have soft green buttons. The lists save with the project. On the settings page, Random's Length bar lights only the chosen pad, and Duplicate pulses lime, not green."),
    "A0097": ("A0096 + the Mutate settings page on the Patterns page: hold Shift + Duplicate to open it, tap Duplicate to close it. The track buttons pick the tracks that mutate; columns 3-6 are Length, Length type, Pool and When. The settings save with the project. The mutate itself is not in this build.", "A0096 + the Mutate settings page on the Patterns page: hold Shift + Duplicate to open it, tap Duplicate to close it. The track buttons pick the tracks that mutate; columns 3-6 are Length, Length type, Pool and When. The settings save with the project. The mutate itself is not in this build."),
    "A0096": ("A0095 + the pitch page's K7 turns tan while Shift is held (Shift + K7 is the fade-in). The filter page's K7 / K8 are white, as the stock's knobs. The pitch follow follows the note's pitch with the glide and the random pitch.", "A0095 + the pitch page's K7 turns tan while Shift is held (Shift + K7 is the fade-in). The filter page's K7 / K8 are white, as the stock's knobs. The pitch follow follows the note's pitch with the glide and the random pitch."),
    "A0095": ('A0094 + the volume LFO, the move LFO and the ring mod run on the second DSP core. This frees room on the first core for new features. The sound is the same.', 'A0094 + the volume LFO, the move LFO and the ring mod run on the second DSP core. This frees room on the first core for new features. The sound is the same.'),
    "A0094": ('A0093 + drone mode on pad 20 (Sample mode): the same note again on a track that still plays does not restart the sample, so a long sound holds with no click. Pad 20 is off by default.', 'A0093 + drone mode on pad 20 (Sample mode): the same note again on a track that still plays does not restart the sample, so a long sound holds with no click. Pad 20 is off by default.'),
    "A0093": ('A0092 without the comb filter: the filter types are stock and 24 dB (Shift + K7 on the filter page). A track saved with the comb plays with the 24 dB filter. The sound engine has more room for new features.', 'A0092 without the comb filter: the filter types are stock and 24 dB (Shift + K7 on the filter page). A track saved with the comb plays with the 24 dB filter. The sound engine has more room for new features.'),
    "A0092": ("A0091 + smoother retrigger: in Sample mode with pad 20 on (the default), when a new note starts while the old one still plays, the old note fades out on a smooth curve over its last 0.7 ms, so the cut gives a much softer click. With pad 20 off, the stock's straight-line fade. The new note starts at the same time as before.", "A0091 + smoother retrigger: in Sample mode with pad 20 on (the default), when a new note starts while the old one still plays, the old note fades out on a smooth curve over its last 0.7 ms, so the cut gives a much softer click. With pad 20 off, the stock's straight-line fade. The new note starts at the same time as before."),
    "A0091": ("A0090 + clean preview loops: in the Sample Rec preview, a loop runs on from its end into its start with no dip in volume (the stock fades it out and restarts it at each pass). One-shot and reverse previews are as before.", "A0090 + clean preview loops: in the Sample Rec preview, a loop runs on from its end into its start with no dip in volume (the stock fades it out and restarts it at each pass). One-shot and reverse previews are as before."),
    "A0090": ("A0089 + loop crossfade (from Circuit Remix): in Sample mode, pad 19 (dim = off, the default) blends the end of a loop into its start, for loops that do not join cleanly. Very short loops also repeat at their real length. Saved with the project.", "A0089 + loop crossfade (from Circuit Remix): in Sample mode, pad 19 (dim = off, the default) blends the end of a loop into its start, for loops that do not join cleanly. Very short loops also repeat at their real length. Saved with the project."),
    "A0089": ("A0088 + retrigger de-click: in Sample mode, pad 20 (lit = on, the default) smooths the cut when a new note stops the one still playing on the track, so a retriggered sample no longer clicks. The new note itself is unchanged. Saved with the project.", "A0088 + retrigger de-click: in Sample mode, pad 20 (lit = on, the default) smooths the cut when a new note stops the one still playing on the track, so a retriggered sample no longer clicks. The new note itself is unchanged. Saved with the project."),
    "A0088": ("A0087 + end fade switch: in Sample mode, pad 21 turns the end fade on or off for the selected track (lit = on, the default). The end fade is the short fade in the last moment of a one-shot or gate sample, so it does not click when it stops. Saved with the project.", "A0087 + end fade switch: in Sample mode, pad 21 turns the end fade on or off for the selected track (lit = on, the default). The end fade is the short fade in the last moment of a one-shot or gate sample, so it does not click when it stops. Saved with the project."),
    "A0087": ("A0086 + clean loops: in loop mode a sample no longer dips in volume just before each pass (the stock fades every sample out near its end, also while it loops). One-shot and gate keep that fade.", "A0086 + clean loops: in loop mode a sample no longer dips in volume just before each pass (the stock fades every sample out near its end, also while it loops). One-shot and gate keep that fade."),
    "A0086": ("A0085 + safe sample sends: while the unit loads a sample (from Components or a pack), Rhythm Plus sends nothing to the sound engine, so the sample is not cut.", "A0085 + safe sample sends: while the unit loads a sample (from Components or a pack), Rhythm Plus sends nothing to the sound engine, so the sample is not cut."),
    "A0085": ("A0084 + the Clear lights on the filter page's K7 / K8 (pad 27): hold Clear and turn right = back to the default, the knob blue; left = its automation deleted, the knob red.", "A0084 + the Clear lights on the filter page's K7 / K8 (pad 27): hold Clear and turn right = back to the default, the knob blue; left = its automation deleted, the knob red."),
    "A0084": ("A0083 + the pitch LFO's fade-in on the pitch page (pad 29) Shift + K7: at each note the vibrato starts at 0 and grows to the K4 depth. 0 = none, the right end = 2 seconds. Hold Clear, then Shift, and turn K7 right to reset it; Clear + pad 29 and Clear All reset it too.", "A0083 + the pitch LFO's fade-in on the pitch page (pad 29) Shift + K7: at each note the vibrato starts at 0 and grows to the K4 depth. 0 = none, the right end = 2 seconds. Hold Clear, then Shift, and turn K7 right to reset it; Clear + pad 29 and Clear All reset it too."),
    "A0083": ("A0082 + glide on the pitch page (pad 29) K8: the pitch slides from the last note to the new note. K8 sets the time: 0 = none, the right end = about 1 second. The same pitch again does not slide. Clear + K8, Clear + pad 29 and Clear All reset it.", "A0082 + glide on the pitch page (pad 29) K8: the pitch slides from the last note to the new note. K8 sets the time: 0 = none, the right end = about 1 second. The same pitch again does not slide. Clear + K8, Clear + pad 29 and Clear All reset it."),
    "A0082": ("A0081 + random pitch on the pitch page (pad 29) K7: each new note starts at a random pitch, up or down. K7 sets the largest jump: 0 = none, the right end = 12 semitones. K8 is dark. Clear + K7, Clear + pad 29 and Clear All reset it.", "A0081 + random pitch on the pitch page (pad 29) K7: each new note starts at a random pitch, up or down. K7 sets the largest jump: 0 = none, the right end = 12 semitones. K8 is dark. Clear + K7, Clear + pad 29 and Clear All reset it."),
    "A0081": ("A0080 + pan and the sends on the mix page (pad 28): K4 pan depth, K5 move shape, K6 move rate, K7 reverb and K8 delay send depth from the middle (right adds send, left takes it away). The FX page's sends and the mixer's pan stay as set; the move works on top.", "A0080 + pan and the sends on the mix page (pad 28): K4 pan depth, K5 move shape, K6 move rate, K7 reverb and K8 delay send depth from the middle (right adds send, left takes it away). The FX page's sends and the mixer's pan stay as set; the move works on top."),
    "A0080": ("A0079 + the page pads in a new order: pad 27 filter, 28 mix, 29 pitch, 30 dark (the sample page later), 31 FX. Each page keeps its knobs and colour.", "A0079 + the page pads in a new order: pad 27 filter, 28 mix, 29 pitch, 30 dark (the sample page later), 31 FX. Each page keeps its knobs and colour."),
    "A0079": ("A0078 + the scan on pad 28 (FX): K7 scan depth, K8 scan speed (locked to the tempo right of the middle, free left). Pad 27 (pitch) K7 and K8 are dark. Clear + pad 28 resets the ring and the scan.", "A0078 + the scan on pad 28 (FX): K7 scan depth, K8 scan speed (locked to the tempo right of the middle, free left). Pad 27 (pitch) K7 and K8 are dark. Clear + pad 28 resets the ring and the scan."),
    "A0078": ("A0077 + each knob group's amount or depth first, so the first knob makes a sound with the defaults. Stock+ (pad 27) and filter (pad 29): K1 env amount, K2 env shape, K3 decay, K4 LFO depth, K5 LFO shape, K6 LFO rate. Movement (pad 30): K1 vol depth, K2 shape, K3 rate.", "A0077 + each knob group's amount or depth first, so the first knob makes a sound with the defaults. Stock+ (pad 27) and filter (pad 29): K1 env amount, K2 env shape, K3 decay, K4 LFO depth, K5 LFO shape, K6 LFO rate. Movement (pad 30): K1 vol depth, K2 shape, K3 rate."),
    "A0077": ("A0076 + one bar language for the rate and shape knobs: right of the middle locks to the tempo (one pad a step: 8 bars to 1/16 in the track's colour, then the triplets in the page's colour), left of the middle is free. Shift + turn right / left: the same pad on the other sweep. Filter page: filter type on Shift + K7, pitch follow on Shift + K8.", "A0076 + one bar language for the rate and shape knobs: right of the middle locks to the tempo (one pad a step: 8 bars to 1/16 in the track's colour, then the triplets in the page's colour), left of the middle is free. Shift + turn right / left: the same pad on the other sweep. Filter page: filter type on Shift + K7, pitch follow on Shift + K8."),
    "A0076": ("A0075 + the movement page on pad 30, volume first: K1 vol shape (the 10 LFO shapes and 6 gates: pump, short gate, long gate, pattern 1, pattern 2, stutter), K2 rate (middle off, right free, left locked to the tempo), K3 depth. K4-K8 dark for now.", "A0075 + the movement page on pad 30, volume first: K1 vol shape (the 10 LFO shapes and 6 gates: pump, short gate, long gate, pattern 1, pattern 2, stutter), K2 rate (middle off, right free, left locked to the tempo), K3 depth. K4-K8 dark for now."),
    "A0075": ("A0074 with K7 and K8 on the filter page in the page's light green, not white.", "A0074 with K7 and K8 on the filter page in the page's light green, not white."),
    "A0074": ("A0073 + the filter page on pad 29: K1 env shape, K2 amount, K3 decay, K4 LFO shape, K5 rate, K6 depth (the same shapes as Stock+), K7 cutoff and K8 resonance (the stock's own knobs, white). Shift + K1 filter type, Shift + K4 pitch follow. Pad 28 has the ring only.", "A0073 + the filter page on pad 29: K1 env shape, K2 amount, K3 decay, K4 LFO shape, K5 rate, K6 depth (the same shapes as Stock+), K7 cutoff and K8 resonance (the stock's own knobs, white). Shift + K1 filter type, Shift + K4 pitch follow. Pad 28 has the ring only."),
    "A0073": ("A0072 + the shape tables go to the DSP once after each start, not all the time.", "A0072 + the shape tables go to the DSP once after each start, not all the time."),
    "A0072": ("A0071 + a new overshoot envelope: it goes up to the top, comes back down, then settles.", "A0071 + a new overshoot envelope: it goes up to the top, comes back down, then settles."),
    "A0071": ("A0070 + the shape bar's second set in sky blue (the Stock+ colour) in place of white: pads 17 to 24 in the track's colour, then pads 17 to 24 in sky blue.", "A0070 + the shape bar's second set in sky blue (the Stock+ colour) in place of white: pads 17 to 24 in the track's colour, then pads 17 to 24 in sky blue."),
    "A0070": ("A0069 + the shape bar. On the Stock+ page, K1 and K4 light one pad for each shape: pads 17 to 24 in the track's colour, then pads 17 to 24 in white.", "A0069 + the shape bar. On the Stock+ page, K1 and K4 light one pad for each shape: pads 17 to 24 in the track's colour, then pads 17 to 24 in white."),
    "A0069": ("A0068 + shapes for the Stock+ page's pitch envelope and LFO. Pad 27: K1 envelope shape (16: drop, rise, up and down, steps, trill, random and more), K2 amount, K3 decay, K4 LFO shape (10: triangle, sine, saws, square, steps, random), K5 rate, K6 depth, K7 / K8 the scan.", "A0068 + shapes for the Stock+ page's pitch envelope and LFO. Pad 27: K1 envelope shape (16: drop, rise, up and down, steps, trill, random and more), K2 amount, K3 decay, K4 LFO shape (10: triangle, sine, saws, square, steps, random), K5 rate, K6 depth, K7 / K8 the scan."),
    "A0068": ("A0066 + each track keeps its own Track + page (pads 26-31): select a track and its page shows. Saved with the project. Pads 29-31 light green, mint and pale lilac.", "A0066 + each track keeps its own Track + page (pads 26-31): select a track and its page shows. Saved with the project. Pads 29-31 light green, mint and pale lilac."),
    "A0066": ("A0065 + no bitcrusher: on Track +'s FX page (pad 28), K1 is the filter type, K2 pitch follow, K3 and K4 ring mod. The stock FX page keeps its own bitcrusher.", "A0065 + no bitcrusher: on Track +'s FX page (pad 28), K1 is the filter type, K2 pitch follow, K3 and K4 ring mod. The stock FX page keeps its own bitcrusher."),
    "A0065": ('A0064 + hold the selected track button to see the other view while you hold it: from the track view you see Track +, from Track + you see the track view. Let go and you are back where you started. A short tap works as before.', 'A0064 + hold the selected track button to see the other view while you hold it: from the track view you see Track +, from Track + you see the track view. Let go and you are back where you started. A short tap works as before.'),
    "A0064": ('A0063 + View Lock: with Track + open, Shift + Patterns turns View Lock on or off and Track + stays open.', 'A0063 + View Lock: with Track + open, Shift + Patterns turns View Lock on or off and Track + stays open.'),
    "A0063": ("Rhythm Plus A0063: no time stretch. Sample mode: hold Clear and tap pad 1 or 2 to set the pitch back to the sample's own (64); without Clear, pads 1 and 2 work as the stock. Track + pad 28 (FX page): K1 bitcrush, K2 filter type, K3 pitch follow, K4 ring mod amount, K5 ring mod frequency. Track +, page and track resets, the step marker, Stock+ and the count-in are kept.", "Rhythm Plus A0063: no time stretch. Sample mode: hold Clear and tap pad 1 or 2 to set the pitch back to the sample's own (64); without Clear, pads 1 and 2 work as the stock. Track + pad 28 (FX page): K1 bitcrush, K2 filter type, K3 pitch follow, K4 ring mod amount, K5 ring mod frequency. Track +, page and track resets, the step marker, Stock+ and the count-in are kept."),
    "A0020": ("Rhythm Plus alpha 20 (colour test): A0019 + off the parameter editor the shown knob is its track's colour at full brightness.", "Rhythm Plus alpha 20 (colour test): A0019 + off the parameter editor the shown knob is its track's colour at full brightness."),
    "A0019": ("Rhythm Plus alpha 19 (colour test): A0018 + the knob lights not shown on the bar dim (a quarter) in the page's colour, so the shown knob stands out.", "Rhythm Plus alpha 19 (colour test): A0018 + the knob lights not shown on the bar dim (a quarter) in the page's colour, so the shown knob stands out."),
    "A0018": ("Rhythm Plus alpha 18 (colour test): A0017 + page colours stronger, in hues between the track colours (Stock+ sky blue; test pages amber, lime, violet, rose).", "Rhythm Plus alpha 18 (colour test): A0017 + page colours stronger, in hues between the track colours (Stock+ sky blue; test pages amber, lime, violet, rose)."),
    "A0017": ("Rhythm Plus alpha 17 (colour test): A0016 + pads 29-32 are test pages in Stock+'s blue at four strengths; Stock+ light blue.", "Rhythm Plus alpha 17 (colour test): A0016 + pads 29-32 are test pages in Stock+'s blue at four strengths; Stock+ light blue."),
    "A0016": ("Rhythm Plus alpha 16 (colour test): A0015 + page colours as light shades (Stock+ the lightest blue); light shades on pads 29-32.", "Rhythm Plus alpha 16 (colour test): A0015 + page colours as light shades (Stock+ the lightest blue); light shades on pads 29-32."),
    "A0015": ("Rhythm Plus alpha 15 (colour test): A0014 + pad 25 cycles only the page's knobs (Stock+ K1-K4) and each page keeps its own; the bar's centre pads white on every page; page colours dimmer.", "Rhythm Plus alpha 15 (colour test): A0014 + pad 25 cycles only the page's knobs (Stock+ K1-K4) and each page keeps its own; the bar's centre pads white on every page; page colours dimmer."),
    "A0014": ("Rhythm Plus alpha 14 (colour test): A0013 + pad 25 brighter (about 10 %), so it keeps the track's colour.", "Rhythm Plus alpha 14 (colour test): A0013 + pad 25 brighter (about 10 %), so it keeps the track's colour."),
    "A0013": ("Rhythm Plus alpha 13 (colour test): A0012 + a colour for each page (the parameter editor white, Stock+ sky blue) on the other track numbers and knob lights; colour samples on pads 29-32.", "Rhythm Plus alpha 13 (colour test): A0012 + a colour for each page (the parameter editor white, Stock+ sky blue) on the other track numbers and knob lights; colour samples on pads 29-32."),
    "A0012": ("Rhythm Plus alpha 12: A0011 + Circuit Remix's Stock+ page 1 on pad 28 (K1 pitch envelope amount, K2 its decay, K3 pitch LFO rate, K4 its depth; Shift = fine; Clear + a knob = its default; saved with the project); pad 25 dimmer; with Record on the bar stays red while a step is held. The test pages are gone.", "Rhythm Plus alpha 12: A0011 + Circuit Remix's Stock+ page 1 on pad 28 (K1 pitch envelope amount, K2 its decay, K3 pitch LFO rate, K4 its depth; Shift = fine; Clear + a knob = its default; saved with the project); pad 25 dimmer; with Record on the bar stays red while a step is held. The test pages are gone."),
    "A0011": ("Rhythm Plus alpha 11: A0010 + pad 25 lit dim in the track's colour.", "Rhythm Plus alpha 11: A0010 + pad 25 lit dim in the track's colour."),
    "A0010": ("Rhythm Plus alpha 10: A0009 + the page is kept until power-off, one page for all tracks.", "Rhythm Plus alpha 10: A0009 + the page is kept until power-off, one page for all tracks."),
    "A0009": ("Rhythm Plus alpha 9: A0008 + page pads: pad 26 dark (a separator), pad 27 the parameter editor, pads 28 and 29 test pages; the page shown white, the others dim.", "Rhythm Plus alpha 9: A0008 + page pads: pad 26 dark (a separator), pad 27 the parameter editor, pads 28 and 29 test pages; the page shown white, the others dim."),
    "A0008": ("Rhythm Plus alpha 8: A0001 + Track +, a menu for each track. Tap the selected track's button to open it, tap it again to close it; hold the button to keep it open while held. While open: pads 1-16 select steps (no step added or removed), pads 17-24 are a bar of the shown knob in the track's colour, pad 25 shows the next knob. The shown knob lights in the track's colour, the other knobs white, red as on the stock. With Record on and playing, hold a step and turn a knob: the automation goes into that step only. The bar is red while a knob turn records. USB diagnostics (read-only).", "Rhythm Plus alpha 8: A0001 + Track +, a menu for each track. Tap the selected track's button to open it, tap it again to close it; hold the button to keep it open while held. While open: pads 1-16 select steps (no step added or removed), pads 17-24 are a bar of the shown knob in the track's colour, pad 25 shows the next knob. The shown knob lights in the track's colour, the other knobs white, red as on the stock. With Record on and playing, hold a step and turn a knob: the automation goes into that step only. The bar is red while a knob turn records. USB diagnostics (read-only)."),
    "A0001": ("Rhythm Plus alpha 1: the official firmware + Fixed Recording at the external clock's tempo + even first steps after Play + the count-in on the music's clock (Shift + Clear: off red / metronome green / count-in only magenta / both cyan; with Record armed, Play from stop counts one bar and the music starts on the 1; nothing records during the count and the Play LED stays as stopped until the 1; as a slave it starts on the master's next bar) + with the click at 0, Clear flashes on each click + Sample Rec count-in (pad 23 on, pad 24 starts the music and the sampling on the 1) + a faster step load on Play + the Clear LED blinks red if a feature cannot run; USB diagnostics (read-only). Same code as STC11.", "Rhythm Plus alpha 1: the official firmware + Fixed Recording at the external clock's tempo + even first steps after Play + the count-in on the music's clock (Shift + Clear: off red / metronome green / count-in only magenta / both cyan; with Record armed, Play from stop counts one bar and the music starts on the 1; nothing records during the count and the Play LED stays as stopped until the 1; as a slave it starts on the master's next bar) + with the click at 0, Clear flashes on each click + Sample Rec count-in (pad 23 on, pad 24 starts the music and the sampling on the 1) + a faster step load on Play + the Clear LED blinks red if a feature cannot run; USB diagnostics (read-only). Same code as STC11."),
    "A04FS": ("Remix line, safe build: Circuit Remix Alpha 0.04S (experimental; nothing creates, changes or deletes files on the card by itself) + the count-in on the music's clock, the visual metronome, the faster step load and the error light of A0.04F. No USB diagnostics.", "Remix line, safe build: Circuit Remix Alpha 0.04S (experimental; nothing creates, changes or deletes files on the card by itself) + the count-in on the music's clock, the visual metronome, the faster step load and the error light of A0.04F. No USB diagnostics."),
    "A0.04F": ("Remix line test: Circuit Remix Alpha 0.04 (experimental) + our count-in on the music's clock: Shift + Clear steps through off (red) / metronome (green) / count-in only (magenta) / both (cyan); with Record armed, Play from stop counts one bar and the music starts on the 1; nothing records during the count and the Play LED stays as stopped until the 1; as a slave it starts on the master's next bar when its position is known from Start or Song Position; Record flashes red on each click; with the click at 0, Clear flashes on each click; a faster step load on Play; the Clear LED blinks red if a feature cannot run; Remix's own start fix and Sample Rec pads 23 / 24 unchanged; USB diagnostics (read-only)", "Remix line test: Circuit Remix Alpha 0.04 (experimental) + our count-in on the music's clock: Shift + Clear steps through off (red) / metronome (green) / count-in only (magenta) / both (cyan); with Record armed, Play from stop counts one bar and the music starts on the 1; nothing records during the count and the Play LED stays as stopped until the 1; as a slave it starts on the master's next bar when its position is known from Start or Song Position; Record flashes red on each click; with the click at 0, Clear flashes on each click; a faster step load on Play; the Clear LED blinks red if a feature cannot run; Remix's own start fix and Sample Rec pads 23 / 24 unchanged; USB diagnostics (read-only)"),
    "STC11": ("Prueba: ST2FX + metrónomo con cuenta atrás: Shift + Clear recorre apagado (rojo) / metrónomo (verde) / solo cuenta (magenta) / "
              "las dos (cian); con Record armado, Play desde parado cuenta un compás y la música empieza en el 1; durante la cuenta no se graba nada y el LED "
              "de Play se queda como parado hasta el 1; la cuenta sigue el reloj de la música, el propio o el reloj MIDI externo (en esclavo, empieza en el "
              "siguiente compás del maestro si se conoce su posición por Start o Song Position; si no, en el primer pulso tras Play); Record destella en rojo "
              "en cada clic; con el clic a 0 (K5 en Tempo / Swing), Clear destella en el color del modo; el LED de Clear parpadea en rojo si una función no "
              "puede funcionar; en la vista Sample Rec, el pad 23 activa la cuenta (verde), con el pad 24 la música y el muestreo empiezan juntos en el 1, y "
              "con la música sonando la cuenta marca los tiempos que quedan del compás (un compás entero si el siguiente tiempo es el 1) y el muestreo empieza "
              "en el 1; Record otra vez, en cualquier vista, cancela la cuenta de Sample Rec; carga de pasos más rápida al pulsar Play; diagnóstico por USB "
              "(solo lectura); nada escribe en la tarjeta SD",
              "Test: ST2FX + metronome with count-in: Shift + Clear steps through off (red) / metronome (green) / count-in only (magenta) / "
              "both (cyan); with Record armed, Play from stop counts one bar and the music starts on the 1; nothing records during the count, and the Play "
              "LED stays as stopped until the 1; the count follows the music's clock, its own or an external MIDI clock (as a slave it starts on the master's "
              "next bar when its position is known from Start or Song Position, else on the first clock pulse after Play); Record flashes red on each click; "
              "with the click at 0 (K5 in Tempo / Swing), Clear flashes in the mode's colour; the Clear LED blinks red if a feature cannot run; in the "
              "Sample Rec view, pad 23 turns the count on (green), with pad 24 the music and the sampling start together on the 1, and while the music plays "
              "the count clicks the beats left in the bar (a full bar when the next beat is the 1) and sampling starts on the 1; Record again, in any view, "
              "cancels a Sample Rec count; a faster step load on Play; USB diagnostics (read-only); nothing writes to the SD card"),
    "STC10": ("Prueba: ST2FX + metrónomo con cuenta atrás: Shift + Clear recorre apagado (rojo) / metrónomo (verde) / solo cuenta (magenta) / "
              "las dos (cian); con Record armado, Play desde parado cuenta un compás y la música empieza en el 1; durante la cuenta no se graba nada y el LED "
              "de Play se queda como parado hasta el 1; la cuenta sigue el reloj de la música, el propio o el reloj MIDI externo (en esclavo, empieza en el "
              "siguiente compás del maestro si se conoce su posición por Start o Song Position; si no, en el primer pulso tras Play); Record destella en rojo "
              "en cada clic; con el clic a 0 (K5 en Tempo / Swing), Clear destella en el color del modo; el LED de Clear parpadea en rojo si una función no "
              "puede funcionar; en la vista Sample Rec, el pad 23 activa la cuenta (verde), con el pad 24 la música y el muestreo empiezan juntos en el 1, y "
              "con la música sonando la cuenta sigue los tiempos de la canción y el muestreo empieza en el 5.º tiempo; Record otra vez, en cualquier vista, "
              "cancela la cuenta de Sample Rec; carga de pasos más rápida al pulsar Play; diagnóstico por USB (solo lectura) y registros de tiempos; nada "
              "escribe en la tarjeta SD",
              "Test: ST2FX + metronome with count-in: Shift + Clear steps through off (red) / metronome (green) / count-in only (magenta) / "
              "both (cyan); with Record armed, Play from stop counts one bar and the music starts on the 1; nothing records during the count, and the Play "
              "LED stays as stopped until the 1; the count follows the music's clock, its own or an external MIDI clock (as a slave it starts on the master's "
              "next bar when its position is known from Start or Song Position, else on the first clock pulse after Play); Record flashes red on each click; "
              "with the click at 0 (K5 in Tempo / Swing), Clear flashes in the mode's colour; the Clear LED blinks red if a feature cannot run; in the "
              "Sample Rec view, pad 23 turns the count on (green), with pad 24 the music and the sampling start together on the 1, and while the music plays "
              "the count follows the song's beats and sampling starts on the 5th beat; Record again, in any view, cancels a Sample Rec count; a faster step "
              "load on Play; USB diagnostics (read-only) and timing logs; nothing writes to the SD card"),
    "STCI9": ("Prueba: ST2FX + metrónomo con cuenta atrás: Shift + Clear recorre apagado (rojo) / metrónomo (verde) / solo cuenta (magenta) / "
              "las dos (cian); con Record armado, Play desde parado cuenta un compás y la música empieza en el 1; la cuenta sigue el reloj de la música, "
              "el propio o el reloj MIDI externo (en esclavo, el primer clic cae en el primer pulso tras Play); Record destella en rojo en cada clic; con el clic "
              "a 0 (K5 en Tempo / Swing), Clear destella en el color del modo en cada clic y en cada tiempo al tocar; el LED de Clear parpadea en rojo si una "
              "función no puede funcionar; en la vista Sample Rec, el pad 23 recorre sin cuenta / cuenta con clic / cuenta muda (Clear destella en amarillo), y con el pad 24 "
              "la música y el muestreo empiezan juntos en el 1; Record otra vez en Sample Rec cancela; diagnóstico por USB (solo lectura) y registros de tiempos; nada escribe en la tarjeta SD",
              "Test: ST2FX + metronome with count-in: Shift + Clear steps through off (red) / metronome (green) / count-in only (magenta) / "
              "both (cyan); with Record armed, Play from stop counts one bar and the music starts on the 1; the count follows the music's clock, "
              "its own or an external MIDI clock (as a slave, the first click is on the first clock pulse after Play); Record flashes red on each click; with the "
              "click at 0 (K5 in Tempo / Swing), Clear flashes in the mode's colour on each click, and on each beat while playing; the Clear LED blinks red if a "
              "feature cannot run; in the Sample Rec view, pad 23 steps through no count / count with click / silent count (Clear flashes yellow), and with pad 24 "
              "the music and the sampling start together on the 1; Record again in Sample Rec cancels; USB diagnostics (read-only) and timing logs; nothing writes to the SD card"),
    "ST2FX": ("Firmware oficial + los dos arreglos: Fixed Recording al tempo del reloj MIDI externo, y los primeros pasos tras Play al tempo "
              "real; nada escribe en la tarjeta SD",
              "Official firmware + both fixes: Fixed Recording at the external MIDI clock's tempo, and the first steps after Play at the real "
              "tempo; nothing writes to the SD card"),
    "A0.03F": ("Alpha 0.03 + los primeros pasos tras Play al tempo real (el reloj ya no acelera los pasos que Play retrasa)",
               "Alpha 0.03 + the first steps after Play at the real tempo (the clock no longer rushes the steps Play delays)"),
    "A03FS": ("Alpha 0.03S (más segura) + los primeros pasos tras Play al tempo real",
              "Alpha 0.03S (safer) + the first steps after Play at the real tempo"),
    "STFRS": ("Firmware oficial + solo el arreglo de Fixed Recording al tempo del reloj MIDI externo; nada escribe en la tarjeta SD",
              "Official firmware + only the Fixed Recording fix (external MIDI clock tempo); nothing writes to the SD card"),
    "STPF1": ("Prueba: STFRS + los primeros pasos tras Play al tempo real + medición de Play (solo RAM); nada escribe en la tarjeta SD",
              "Test: STFRS + the first steps after Play at the real tempo + a Play timing log (RAM only); nothing writes to the SD card"),
    "STPD5": ("Prueba: STPF1 + medición de los oyentes que tardan durante Play (solo RAM); nada escribe en la tarjeta SD",
              "Test: STPF1 + a log of the slow listeners during Play (RAM only); nothing writes to the SD card"),
}
OUT = HERE / "tools" / "uploader.html"
# the list shows only the version names; the chosen version's description goes in a box under it
DESC_BOX = (
    ('    <select id="ver"></select>\n',
     '    <select id="ver"></select>\n    <div id="verDesc" style="margin-top:10px;line-height:1.45"></div>\n'),
    ('const verLabel = v => v === "Oficial" ? t("Oficial — el firmware de Novation sin cambios (para volver atrás)", '
     '"Official — Novation’s firmware unchanged (to go back)")\n  : (DESC[v] ? DESC[v][LANG === "en" ? 1 : 0] : v);\n',
     'const verLabel = v => v === "Oficial" ? t("Oficial", "Official") : v;\n'
     'const verText = v => v === "Oficial" ? t("El firmware de Novation sin cambios (para volver atrás).", '
     '"Novation’s firmware unchanged (to go back).")\n  : (DESC[v] ? DESC[v][LANG === "en" ? 1 : 0] : v);\n'
     'function showDesc() { $("verDesc").textContent = verText($("ver").value); }\n'),
    ('o.textContent = verLabel(v); $("ver").appendChild(o); }\n',
     'o.textContent = verLabel(v); $("ver").appendChild(o); }\nshowDesc();\n'),
    ('  for (const o of $("ver").options) o.textContent = verLabel(o.value);\n',
     '  for (const o of $("ver").options) o.textContent = verLabel(o.value);\n  showDesc();\n'),
    ('$("ver").onchange = () => { updateAck(true); prepare(); updateSend(); };',
     '$("ver").onchange = () => { showDesc(); updateAck(true); prepare(); updateSend(); };'),
)


def main():
    stock = m.STOCK_BIN.read_bytes()
    assert hashlib.sha256(stock).hexdigest() == rh_fw.STOCK_5706["image_sha256"]
    versions = list(MINE)
    hardware = {"AG015": HERE / "buildtmp" / "granular-hardware-ag015",
                "AG014": HERE / "buildtmp" / "granular-hardware-ag014",
                "AG012": HERE / "buildtmp" / "granular-hardware-ag012",
                "AG011": HERE / "buildtmp" / "granular-hardware-ag011",
                "AG010": HERE / "buildtmp" / "granular-hardware-ag010",
                "AG009": HERE / "buildtmp" / "granular-hardware-ag009",
                "AG008": HERE / "buildtmp" / "granular-hardware-ag008",
                "AG007": HERE / "buildtmp" / "granular-hardware-ag007",
                "AG006": HERE / "buildtmp" / "granular-hardware-ag006",
                "AG005": HERE / "buildtmp" / "granular-hardware-ag005",
                "AG004": HERE / "buildtmp" / "granular-hardware-ag004",
                "AG003": HERE / "buildtmp" / "granular-hardware-ag003"}
    versions[:0] = [v for v, path in hardware.items() if (path / "manifest.json").is_file()]
    patches = {}
    for v in versions:
        d = hardware.get(v, HERE / "firmware" / v.lower())
        man = json.loads((d / "manifest.json").read_text())
        img = next(d.glob("*.bin")).read_bytes()
        assert hashlib.sha256(img).hexdigest() == man["image_sha256"], v
        ops = m.make_patch(stock, img)
        assert m.apply(stock, ops) == img
        m.check_add(stock, ops)
        assert hashlib.sha256(rh_fw.encode(img)).hexdigest() == man["syx_sha256"], v
        patches[v] = dict(dir=v.lower(), image_sha256=man["image_sha256"], syx_sha256=man["syx_sha256"], size=len(img), ops=ops)
        print(v, len(ops), "ops,", sum(len(base64.b64decode(o[1])) for o in ops if o[0] == 1), "bytes of our own")
    desc = {**DESC,
            "AG014": ("Prueba granular: arranque del DSP más rápido para evitar el bucle de arranque; color lima.",
                      "Granular test: faster DSP start to stop the boot loop; lime page color."),
            "AG015": ("Prueba granular: Lock en Shift + K6 repite los granos; Slice en Shift + K5 corta la muestra en 2 a 16 partes y Scan avanza una parte a tempo.",
                      "Granular test: Lock on Shift + K6 repeats the grains; Slice on Shift + K5 cuts the sample into 2 to 16 parts, and Scan steps one part at a time on the tempo."),
            "AG012": ("Prueba granular: color lima y colores ordenados en la fila de ajustes.",
                      "Granular test: lime page color and tidy settings row colors."),
            "AG011": ("Prueba granular: Bounce, Freeze y Pitch Set bajo sus perillas.",
                      "Granular test: Bounce, Freeze and Pitch Set sit under their knobs."),
            "AG010": ("Prueba granular: perillas Shift de Dispersion, Tiempo y Jitter; pads Pitch Set y Rebote; Texture respeta Mute.",
                      "Granular test: Shift knobs for Size Scatter, Timing and Jitter; Pitch Set and Bounce pads; Texture follows mutes."),
            "AG009": ("Prueba granular: Limpiar pista conserva el modo de muestra; filtro limpio siempre activo.",
                      "Granular test: Clear Track keeps the sample mode; the clean filter is always on."),
            "AG008": ("Prueba granular: Texture sigue Play y Stop, con cola suave al parar.",
                      "Granular test: Texture follows Play and Stop, with a soft tail at Stop."),
            "AG007": ("Prueba granular: fundidos curvos, Clean/Raw, nivel estable y nueva curva de densidad.",
                      "Granular test: curved fades, Clean/Raw, steady level, and a new Density curve."),
            "AG006": ("Prueba granular: One Shot termina con la muestra; Gated y Loop siguen la nota.",
                      "Granular test: One Shot ends with the sample; Gated and Loop follow the note."),
            "AG005": ("Prueba granular: Triggered sigue la nota, Freeze, Retrigger, nivel fino y luces de knobs.",
                      "Granular test: Triggered follows the note, Freeze, Retrigger, fine Level, and knob lights."),
            "AG004": ("Prueba granular: On/Off, Freeze, nivel, Clear + knob y Scan con Granular.",
                      "Granular test: On/Off, Freeze, Level, Clear + knob, and FX Scan with Granular."),
            "AG003": ("Prueba granular con acceso DSP nativo. Comprueba el arranque con Granular apagado.",
                      "Granular hardware test using stock DSP access. Check boot with Granular Off first.")}
    tpl = m.TEMPLATE.replace("const DESC = " + json.dumps(m.DESC, ensure_ascii=False), "const DESC = " + json.dumps(desc, ensure_ascii=False))
    assert tpl != m.TEMPLATE
    for old, new in DESC_BOX:
        assert tpl.count(old) == 1, old[:60]
        tpl = tpl.replace(old, new)
    page = tpl.replace("__PATCHES__", json.dumps(patches, separators=(",", ":"))).replace("__STOCK_SYX__", rh_fw.STOCK_5706["syx_sha256"]) \
        .replace("__STOCK_IMG__", rh_fw.STOCK_5706["image_sha256"]).replace("__VERSIONS__", ", ".join(versions)).replace("__SAFER__", "ST2FX")
    OUT.write_text(page, encoding="utf-8", newline="")
    print(OUT, len(page), "bytes")


if __name__ == "__main__":
    main()
