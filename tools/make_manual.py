"""Writes manual/rhythm_plus_manual.html: the Rhythm Plus user manual (A4 pages, drawings of the unit's top panel).
Print it to PDF with:  chrome --headless --no-pdf-header-footer --generate-pdf-document-outline --print-to-pdf=manual/rhythm_plus_manual.pdf manual/rhythm_plus_manual.html"""
import json
import re
from html import escape
from pathlib import Path

FIRMWARE = "A329"
OUT = Path(__file__).resolve().parents[1] / "manual" / "rhythm_plus_manual.html"

GRAD = ["ffc866", "ffd966", "fff766", "e5ff66", "c7ff66", "a6ff66", "87ff66", "66ff66"]   # the probability page's colours
TRK = ["ff4e13", "ffff19", "9865ff", "00ffb5", "c63ac6", "3db24f", "1a47ff", "ff4c7b"]    # tracks 1-8
GREEN, RED, WHITE = "66ff66", "ff2a1a", "ffffff"
OFF = (46, 46, 50)


def lit(hexc, k=1.0):
    """an LED's look at k of full (0..1) on the dark panel"""
    c = [int(hexc[i:i + 2], 16) for i in (0, 2, 4)]
    if k >= 1:
        return "#" + hexc
    k = 0.18 + 0.82 * k
    return "#%02x%02x%02x" % tuple(round(o + (v - o) * k) for v, o in zip(c, OFF))


FULL, DIM, VDIM = 1.0, 0.32, 0.12
FRAMES = json.loads((OUT.parent / "frames.json").read_text())["frames"]   # tools/manual_frames.py: the unit's LED words

# The top panel as in the Circuit Rhythm user guide's Top View, in that drawing's pixels. LED indices: 0-31 pads,
# 32 + button id (0-7 tracks), 60-67 K1-K8, 68 Master Filter.
PW, PH, CROP = 805, 705, 250
COLX = [121 + 71 * c for c in range(8)]
ROWY = [388 + 71 * r for r in range(4)]
LX, RX, BW, TOPY, TRKY = 44, 694, 66, 268, 313
KNOBS = [(154, 192), (224, 106), (295, 192), (365, 106), (437, 192), (507, 106), (579, 192), (649, 106)]
LEGENDS = ["1 Tune", "2 Start", "3 Length", "4 Slope", "5 Distortion", "6 HP Filter", "7 LP Filter", "8 Resonance"]
SIDE = [("Sample", "Sample Mode"), ("Note", "Expand"), ("Velocity", "Fixed"), ("Gate", "Micro Step"), ("Pattern\nSettings", "Probability"),
        ("Patterns", "View Lock"), ("Mixer", "Grid FX"), ("FX", "Side Chain"), ("●", "Rec Quantise"), ("▶", "")]
TOP = ["Sample Rec", "▼", "▲", "1-16\n17-32", "Tempo\nSwing", "Clear", "Duplicate", "Save", "Projects", "Shift"]
ABOVE = {50: "Drum Pads", 54: "Tap", 55: "Click", 56: "Mutate", 58: "Packs"}
UNDER = ["One Shot", "Gated", "Loop", "Reverse", "Choke", "", "Keyboard", "Slice"]


def buttons_at():
    """LED index: (x, y, w, h, label, legend)"""
    at = {32 + t: (COLX[t], TRKY, 62, 62, str(t + 1), "") for t in range(8)}
    for i, (name, legend) in enumerate(SIDE):
        x, y = (LX, TRKY if i == 0 else ROWY[i - 1]) if i < 5 else (RX, TRKY if i == 5 else ROWY[i - 6])
        at[40 + i] = (x, y, BW, 62, name, legend)
    for i, name in enumerate(TOP):
        at[50 + i] = (LX if i == 0 else RX if i == 9 else COLX[i - 1], TOPY, BW if i in (0, 9) else 62, 30, name, "")
    return at


BUTTONS = buttons_at()
LED_OF = {"Up": 52, "Down": 51, "Duplicate": 56, "Shift": 59, "Clear": 55, "Play": 49, "Projects": 58, "Mixer": 46, "Patterns": 45,
          "Sample": 40, "Sample Rec": 50, "Pattern Settings": 44}
HELD = "#ffcc33"
NL = chr(10)
LABEL_EM = 13.5                                                  # a label letter's width, in the panel's pixels


def led_rgb(word):
    """an output word (full is 0x8c a channel) as the LED looks on paper; None: off"""
    c = [word >> 16 & 255, word >> 8 & 255, word & 255]
    m = max(c)
    return None if m < 4 else lit("%02x%02x%02x" % tuple(v * 255 // m for v in c), min(1.0, m / 0x8C))


def frame_leds(name, **change):
    """a captured frame as {LED: colour}; change: {'i<LED>': word} on top"""
    words = list(FRAMES[name])
    for i, w in change.items():
        words[int(i[1:])] = w
    return {i: led_rgb(w) for i, w in enumerate(words)}


IDLE = {i: led_rgb(0x161616) for i in list(range(32, 60)) + [68]}   # the stock's dim white on the buttons


def dark(fill):
    return bool(fill) and fill.startswith("#") and sum(int(fill[j:j + 2], 16) for j in (1, 3, 5)) > 400


def target(i):
    """an LED's box (x, y, w, h): pads 0-31, buttons, knobs 60-67, Master Filter 68"""
    if i < 32:
        return COLX[i % 8], ROWY[i // 8], 62, 62
    if 60 <= i < 68:
        x, y = KNOBS[i - 60]
        return x - 31, y - 31, 62, 62
    if i == 68:
        return 694, 159, 66, 66
    return BUTTONS[i][:4]


def labels(callouts, y0, h, right_x):
    """label text and leader lines in margins left and right of the panel: callouts [(LED, text) or (LED, text, 'L' | 'R')]"""
    o, sides = [], {"L": [], "R": []}
    for n, c in enumerate(callouts):
        x, y, bw, bh = target(c[0])
        side = c[2] if len(c) > 2 else ("L" if x + bw / 2 < PW / 2 else "R")
        sides[side].append((y + bh / 2, n, x, bw, c[1]))
    for side, items in sides.items():
        last = y0 - 100
        for cy, _, x, bw, text in sorted(items):
            lines = text.split(NL)
            ty = max(cy, last + 30 * len(lines) + 8, y0 + 24)
            ty = min(ty, y0 + h - 30 * (len(lines) - 1) - 10)
            last = ty
            tx, ex = (-16, x) if side == "L" else (right_x + 16, x + bw)
            lx = -10 if side == "L" else right_x + 10
            o.append(f'<polyline points="{lx},{ty} {ex},{cy}" fill="none" stroke="#ffffff" stroke-width="7" stroke-linecap="round"/>'
                     f'<polyline points="{lx},{ty} {ex},{cy}" fill="none" stroke="#16161a" stroke-width="2.5"/>'
                     f'<circle cx="{ex}" cy="{cy}" r="6" fill="#16161a" stroke="#ffffff" stroke-width="2.5"/>')
            for j, line in enumerate(lines):
                o.append(f'<text x="{tx}" y="{ty + 9 - 15 * (len(lines) - 1) + 30 * j}" class="co" '
                         f'text-anchor="{"end" if side == "L" else "start"}">{escape(line)}</text>')
    room = {k: max((LABEL_EM * max(map(len, t[-1].split(NL))) + 30 for t in v), default=0) for k, v in sides.items()}
    return o, room["L"], room["R"]


def panel(leds, marks=None, held=(), cols=None, rows=None, top=True, width=None, callouts=None):
    """the Circuit Rhythm's top panel. leds: {LED: fill or None}; marks: {LED: text | 'pulse'}; held: LEDs with a finger on them;
    callouts: labels with a line to their LED (see labels)"""
    y0 = 0 if top else CROP
    w, h = PW + (130 if rows else 0), PH - y0 + (34 if cols else 0)
    o = [f'<svg class="dev" viewBox="0 {y0} {w} {h}" width="{width or (340 if top else 360) + (50 if rows else 0)}" role="img">',
         f'<rect x="1" y="1" width="{PW - 2}" height="{PH - 2}" rx="14" fill="#8d8e93" stroke="#6c6d72" stroke-width="2"/>']
    off_pad, off_btn = "#3a3a3f", "#2b2b2f"

    def knob(x, y, r, colour, legend, led_y=None):
        o.append(f'<circle cx="{x}" cy="{y}" r="{r + 5}" fill="none" stroke="#6c6d72" stroke-width="2"/>'
                 f'<circle cx="{x}" cy="{y}" r="{r}" fill="#1c1c1f"/><circle cx="{x}" cy="{y}" r="{r - 7}" fill="#29292d"/>'
                 f'<line x1="{x}" y1="{y - 6}" x2="{x}" y2="{y - r + 4}" stroke="#e8e8ec" stroke-width="4" stroke-linecap="round"/>')
        if led_y is not None:
            o.append(f'<rect x="{x - 15}" y="{led_y}" width="30" height="10" rx="5" fill="{colour or off_btn}" stroke="#55565a"/>')
        o.append(f'<text x="{x}" y="{led_y + 21 if led_y else y + r + 22}" class="lg">{escape(legend)}</text>')

    if top:
        knob(80, 108, 33, None, "Master Volume")
        for k, (x, y) in enumerate(KNOBS):
            knob(x, y, 31, leds.get(60 + k), LEGENDS[k], y + 38)
        knob(727, 192, 33, leds.get(68), "Master Filter", 230)
    for i, (x, y, bw, bh, name, legend) in BUTTONS.items():
        fill = leds.get(i) or off_btn
        ink = "#111" if dark(fill) else "#ececf0"
        o.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="6" fill="{fill}" stroke="#1d1d20" stroke-width="1.5"/>')
        lines = name.split("\n")
        big = name in ("●", "▶", "▼", "▲")
        ty = y + (bh / 2 - (6 if legend else 0)) - 7 * (len(lines) - 1) + (6 if big else 5)
        for j, line in enumerate(lines):
            o.append(f'<text x="{x + bw / 2}" y="{ty + 14 * j}" class="{"bb" if big else "bt"}" fill="{ink}">{escape(line)}</text>')
        if legend:
            o.append(f'<text x="{x + bw / 2}" y="{y + bh - 7}" class="bs" fill="{ink}">{escape(legend)}</text>')
        if i in ABOVE:
            o.append(f'<text x="{x + bw / 2}" y="{y - 3}" class="lg">{ABOVE[i]}</text>')
    for p in range(32):
        x, y = COLX[p % 8], ROWY[p // 8]
        fill = leds.get(p) or off_pad
        o.append(f'<rect x="{x}" y="{y}" width="62" height="62" rx="5" fill="{fill}" stroke="#1d1d20" stroke-width="1.5"/>')
    for c, t in enumerate(UNDER):
        o.append(f'<text x="{COLX[c] + 31}" y="{ROWY[3] + 80}" class="lg">{t}</text>')
    for i, m in (marks or {}).items():
        x, y, bw, bh = (COLX[i % 8], ROWY[i // 8], 62, 62) if i < 32 else BUTTONS[i][:4]
        if m == "pulse":
            o.append(f'<rect x="{x - 5}" y="{y - 5}" width="{bw + 10}" height="{bh + 10}" rx="8" fill="none" stroke="#ffffff" '
                     f'stroke-width="3" stroke-dasharray="7 5"/>')
        else:
            o.append(f'<text x="{x + bw / 2}" y="{y + bh / 2 + 6}" class="pm" fill="{"#111" if dark(leds.get(i)) else "#f2f2f4"}">{escape(m)}</text>')
    for i in held:
        x, y, bw, bh = (COLX[i % 8], ROWY[i // 8], 62, 62) if i < 32 else BUTTONS[i][:4]
        o.append(f'<rect x="{x - 5}" y="{y - 5}" width="{bw + 10}" height="{bh + 10}" rx="9" fill="none" stroke="{HELD}" stroke-width="6"/>')
    for c, t in (cols or {}).items():
        o.append(f'<text x="{COLX[c] + 31}" y="{PH + 24}" class="an">{escape(t)}</text>')
    for r, t in (rows or {}).items():
        o.append(f'<text x="{PW + 12}" y="{ROWY[r] + 37}" class="ar">{escape(t)}</text>')
    if callouts:
        drawn, ml, mr = labels(callouts, y0, h, w)
        o += drawn
        shown = (width or (340 if top else 360) + (50 if rows else 0)) * (w + ml + mr) / w
        o[0] = f'<svg class="dev" viewBox="{-ml} {y0} {w + ml + mr} {h}" width="{shown:.0f}" role="img">'
    o.append("</svg>")
    return "".join(o)


def grid(cells, cols=None, rows=None, marks=None, knobs=False, buttons=None, held=(), top=None, base=None, callouts=None, width=None):
    """a panel from pad fills {0..31: fill}, knob light fills [K1..K8], buttons [(name, fill)]; the other buttons as base (IDLE)"""
    leds = dict(IDLE if base is None else base)
    leds.update(cells)
    if knobs:
        leds.update({60 + k: f for k, f in enumerate(knobs)})
    for name, fill in buttons or ():
        leds[LED_OF[name]] = fill
    return panel(leds, marks, held, cols, rows, bool(knobs) if top is None else top, width, callouts)


REV, DLY, AMB = "4cd964", "ff4fa0", "ffaf2f"                 # the reverb return, the delay return, the Grid FX blend


def fx_page2():
    """the FX track's page 2: the reverb return chosen, on track 1's lane; the blend on track 3's"""
    cells, marks = {}, {}
    for i in range(16):
        cells[i] = lit("ff4fd8" if i % 4 == 0 else "2f5bff", FULL if i % 4 == 0 else DIM)
        marks[i] = str(i + 1)
    for l in range(8):
        cells[16 + l] = lit(REV, FULL) if l == 0 else lit(AMB, DIM) if l == 2 else lit(WHITE, DIM)
        marks[16 + l] = f"T{l + 1}"
    cells[24], marks[24] = lit(REV, FULL), "25"
    cells[31], marks[31] = lit(GREEN, FULL), "32"
    return grid(cells, rows={0: "Steps", 1: "", 2: "Lanes", 3: ""}, marks=marks, knobs=[REV, DLY, AMB] + [None] * 5,
                buttons=[("Up", lit(WHITE, DIM)), ("Down", lit(AMB, FULL))])


def table(head, rows, cls=""):
    h = "".join(f"<th>{c}</th>" for c in head)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>'


def figure(svg, caption, legend=None):
    lg = ""
    if legend:
        lg = '<ul class="legend">' + "".join(f'<li><span class="sw" style="background:{f}"></span>{t}</li>' for f, t in legend) + "</ul>"
    return f'<figure>{svg}<figcaption>{caption}</figcaption>{lg}</figure>'


def page(body, cls=""):
    return f'<section class="page {cls}">{body}<footer><span>Rhythm Plus {FIRMWARE}</span><span class="pn"></span></footer></section>'


def key(t):
    return f'<kbd>{escape(t)}</kbd>'


SH, DU, CL, PL, PA, MI, UP, DN = (key(t) for t in ("Shift", "Duplicate", "Clear", "Play", "Patterns", "Mixer", "Up", "Down"))


def how_to_open(pad):
    return (f'<p class="how"><b>Open:</b> hold pad {pad} for a moment. <b>Assignments:</b> in Settings, press {DN}. '
            f'<b>Back:</b> {UP}. <b>Close:</b> tap pad {pad}. All four pages work the same (chapter 11).</p>')


# ---------------------------------------------------------------- drawings
def mutate_page1(callouts=None):
    cells = {}
    for r in range(4):
        cells[8 * r + 2] = lit(GRAD[2], FULL)                 # Length: Exact 4, the bar full
    for r, on in enumerate((0, 1, 0)):
        cells[8 * r + 3] = lit(GRAD[3], FULL if on else DIM)  # Length type: Exact
    for r, on in enumerate((1, 0)):
        cells[8 * r + 4] = lit(GRAD[4], FULL if on else DIM)  # Pool: With steps
    for r, on in enumerate((1, 0)):
        cells[8 * r + 5] = lit(GRAD[5], FULL if on else DIM)  # When: On the tap
    cells[0], cells[8] = lit(GREEN, FULL), lit(GREEN, DIM)   # Live Off
    marks = {2: "1", 10: "2", 18: "3", 26: "4"}
    return grid(cells, cols={0: "Live", 2: "Length", 3: "Type", 4: "Pool", 5: "When"}, rows={0: "1", 1: "2", 2: "3", 3: "4"},
                marks=marks, buttons=[("Up", lit("444448")), ("Down", "#ffffff"), ("Duplicate", lit(GREEN, 0.6))], callouts=callouts)


def mutate_page2():
    cells = {}
    for r in range(4):
        cells[8 * r + 2] = lit(GRAD[2], DIM)                  # Length 5-8, past Length 4: dim
    meter = [GRAD[7], GRAD[5], GRAD[3], GRAD[1]]
    for r in range(4):
        cells[8 * r + 3] = lit(meter[r], FULL if r >= 2 else DIM)   # Amount: Some
    cells[4], cells[12] = lit(GREEN, FULL), lit(GREEN, DIM)  # Repeats On
    cells[5], cells[13] = lit(GREEN, DIM), lit(GREEN, FULL)  # Keep slot 1 On
    cells[0], cells[8] = lit(GREEN, DIM), lit(GREEN, FULL)   # Live On
    marks = {2: "5", 10: "6", 18: "7", 26: "8"}
    return grid(cells, cols={0: "Live", 2: "Length", 3: "Amount", 4: "Repeats", 5: "Keep 1"}, rows={0: "1", 1: "2", 2: "3", 3: "4"},
                marks=marks, buttons=[("Up", "#ffffff"), ("Down", lit("444448")), ("Duplicate", lit(GREEN, 0.6))])


def patterns_cells():
    cells, marks = {}, {}
    lst = {0: (0, 2, 3), 2: (1, 3), 5: (0, 1, 2, 3)}         # tracks with a mutate: their list's patterns on page 1
    chain = {1: (0, 1), 3: (0,), 4: (0, 1, 2), 6: (0,), 7: (0, 1)}
    for t in range(8):
        for r in range(4):
            i = 8 * r + t
            if t in lst:
                cells[i] = lit(TRK[t], 0.44 if r in lst[t] else 0.03)
            else:
                cells[i] = lit(TRK[t], 0.45 if r in chain[t] else 0.09)
    for t, r in ((0, 2), (2, 1), (5, 3), (1, 0), (3, 0), (4, 1), (6, 0), (7, 1)):
        cells[8 * r + t] = lit(TRK[t], FULL)
        marks[8 * r + t] = "pulse"
    return cells, marks


def patterns_mutated():
    cells, marks = patterns_cells()
    return grid(cells, cols={t: f"T{t + 1}" for t in range(8)}, rows={0: "1", 1: "2", 2: "3", 3: "4"}, marks=marks)


def patterns_shift_duplicate(callouts=None):
    """Shift + Duplicate on the Patterns page"""
    cells, marks = patterns_cells()
    return grid(cells, held=(59, 56), buttons=[("Duplicate", lit(GREEN))], cols={t: f"T{t + 1}" for t in range(8)},
                marks=marks if callouts else None, callouts=callouts)


def patterns_clear():
    """Clear held on the Patterns page: the mutated tracks' buttons green"""
    cells, _ = patterns_cells()
    cells.update({32 + t: lit(GREEN) if t in (0, 2, 5) else None for t in range(8)})
    return grid(cells, held=(55,))


G9 = ["ffc866", "eece66", "ddd466", "ccda66", "bbe066", "aae766", "99ed66", "88f366", "77f966", "66ff66"]   # the Step Mutate targets
SM_TARGETS = [(0, "Note"), (1, "Flip"), (2, "Move"), (8, "Vel"), (16, "Gate"), (17, "Micro"), (24, "Length"), (25, "Speed"), (26, "Mode"),
              (27, "Prob")]


def step_mutate_page():
    cells, marks = {}, {}
    for g, (p, name) in enumerate(SM_TARGETS):
        cells[p] = lit(G9[g], FULL if name in ("Move", "Vel") else DIM)
        marks[p] = name
    for r in range(4):
        cells[8 * r + 5] = lit(GRAD[(7, 5, 3, 1)[r]], FULL if r >= 2 else DIM)   # Amount: Some
        cells[8 * r + 6] = lit(GRAD[(7, 5, 3, 1)[r]], FULL if r >= 2 else DIM)   # Range: Up to 24
    for r in range(3):
        cells[8 * r + 7] = lit(G9[3], FULL if r == 2 else DIM)                     # Direction: Both
    return grid(cells, cols={k: str(k + 1) for k in range(8)}, rows={0: "1", 1: "2", 2: "3", 3: "4"},
                marks=marks, buttons=[("Shift", None), ("Duplicate", lit(GREEN, 0.6))])


PAD_NUMBERS = {i: str(i + 1) for i in range(16, 31)}
def editor(name="stock", marks=None, held=(), row3="Bar", callouts=None, width=None, change=None):
    """a Track Parameter Editor frame from the emulator, track 1 selected, with the pad numbers of rows 3 and 4; change as in frame_leds"""
    return panel(frame_leds(name, **(change or {})), {**PAD_NUMBERS, **(marks or {})}, held, rows={0: "Steps", 2: row3, 3: "Pages"}, width=width,
                 callouts=callouts)


def advanced_setup():
    """Advanced Setup with Merge chosen: Duplicate yellow, pad 23 (USB merge) dim green; the other lights not drawn"""
    return grid({22: lit("1eff00", 0.25)}, marks={22: "23"}, buttons=[("Duplicate", "#ffff19")], base={i: None for i in range(32, 69)},
                callouts=[(56, "Duplicate: yellow = Merge"), (22, "Pad 23: USB merge", "L"), (49, "▶: leave Advanced Setup")])


def midi_chain():
    """keyboard -> MIDI In; the Thru jack -> the second unit"""
    box = lambda x, t: (f'<rect x="{x}" y="20" width="170" height="70" rx="10" fill="#f2f2f4" stroke="#16161a" stroke-width="2.5"/>'
                        f'<text x="{x + 85}" y="62" class="cb">{t}</text>')
    arrow = lambda x1, x2, a, b: (f'<line x1="{x1}" y1="55" x2="{x2 - 10}" y2="55" stroke="#16161a" stroke-width="3"/>'
                                  f'<path d="M{x2 - 12},46 L{x2},55 L{x2 - 12},64 Z" fill="#16161a"/>'
                                  f'<text x="{(x1 + x2) / 2}" y="40" class="cs">{a}</text><text x="{(x1 + x2) / 2}" y="82" class="cs">{b}</text>')
    return ('<svg viewBox="0 0 760 110" width="600" role="img">' + box(10, "Keyboard") + arrow(180, 295, "MIDI Out", "to MIDI In") +
            box(295, "Circuit Rhythm") + arrow(465, 580, "Thru", "to MIDI In") + box(580, "Second unit") + "</svg>")


SM_LEN = ["e6d166", "ccda66", "b3e466", "99ed66", "80f666", "66ff66"]   # Sample mode pads 11-16


def sample_mode(callouts=None):
    """Sample mode with stretch on at 1 bar, Granular off; only the Rhythm Plus pads 9-20 lit"""
    cells = {8: lit(GREEN), 9: lit(WHITE), 16: lit("ff3040"), 17: lit(WHITE), 19: lit(WHITE)}
    for k, c in enumerate(SM_LEN):
        cells[10 + k] = lit(c, FULL if k == 2 else 48 / 255)
    marks = {i: str(i + 1) for i in range(8, 20)}
    return grid(cells, marks=marks, base={i: None for i in range(32, 69)}, top=False, callouts=callouts)


def scrub():
    """Latched: K1 green, K2 blue, K3 the scanner, K4 the timing's colour, K5 sound; pads 17-24 the timing, 25-32 cues; Shift green; tracks green"""
    bar = (0x404040, 0xFFC866, 0xFFD966, 0xFFF766, 0xE5FF66, 0xC7FF66, 0xA6FF66, 0x66FF66)
    c = {f"i{60 + k}": 0 for k in range(8)}
    c.update(i60=0x00FF00, i61=0x0040FF, i62=0x403219, i63=0xA6FF66, i64=0x00FF00)
    c.update({f"i{16 + i}": v if i == 6 else (v >> 2) & 0x3F3F3F for i, v in enumerate(bar)})
    c.update({f"i{p}": 0x66FF66 if p in (24, 25) else 0x403219 for p in range(24, 32)})
    c.update({f"i{32 + t}": 0x00FF00 if t == 0 else 0x004000 for t in range(8)})
    c.update(i59=0x00FF00)
    return panel(frame_leds("stock", **c))


# ---------------------------------------------------------------- the pages
CSS = """
@page { size: A4; margin: 0; }
:root { --ink: #16161a; --muted: #5d5d66; --line: #d9d9de; --accent: #1f6f5c; --band: #f2f2f4; --paper: #ffffff;
  --body: "Source Sans 3", "Segoe UI", "Helvetica Neue", Arial, sans-serif; --head: "Barlow Semi Condensed", "Segoe UI", Arial, sans-serif; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --paper: #ffffff; } }
* { box-sizing: border-box; }
html, body { margin: 0; background: #e6e6ea; color: var(--ink); font-family: var(--body); font-size: 10pt; line-height: 1.4; }
.page { width: 210mm; height: 297mm; overflow: hidden; margin: 10mm auto; padding: 15mm 17mm 20mm; background: var(--paper); position: relative;
  box-shadow: 0 1px 6px rgba(0,0,0,.15); page-break-after: always; break-after: page; }
@media print { html, body { background: #fff; } .page { margin: 0; box-shadow: none; } }
footer { position: absolute; left: 18mm; right: 18mm; bottom: 10mm; display: flex; justify-content: space-between; font-size: 8.5pt;
  color: var(--muted); border-top: 1px solid var(--line); padding-top: 3mm; }
body { counter-reset: pg; } .page { counter-increment: pg; } .pn::after { content: counter(pg); }
h1, h2, h3 { font-family: var(--head); font-weight: 600; letter-spacing: .01em; text-wrap: balance; margin: 0; }
h1 { font-size: 30pt; line-height: 1.05; }
h2 { font-size: 18pt; margin-bottom: 4mm; padding-bottom: 2mm; border-bottom: 2.5px solid var(--ink); }
h3 { font-size: 12pt; margin: 4mm 0 1.5mm; }
.eyebrow { font-family: var(--head); text-transform: uppercase; letter-spacing: .12em; font-size: 9pt; color: var(--accent); margin-bottom: 1.5mm; }
p { margin: 0 0 2.5mm; max-width: 165mm; }
table { width: 100%; border-collapse: collapse; margin: 1.5mm 0 3mm; font-size: 9.5pt; }
th { text-align: left; font-family: var(--head); font-weight: 600; background: var(--band); border-bottom: 1.5px solid var(--ink); padding: 1.3mm 2mm; }
td { border-bottom: 1px solid var(--line); padding: 1.2mm 2mm; vertical-align: top; }
td:first-child { white-space: nowrap; }
kbd { font-family: var(--head); font-size: 9pt; font-weight: 600; border: 1px solid #9a9aa2; border-bottom-width: 2px; border-radius: 3px;
  padding: 0 1.4mm; background: #fafafa; white-space: nowrap; }
figure { margin: 3mm 0 4mm; } figure svg { display: block; max-width: 100%; height: auto; }
figcaption { font-size: 9pt; color: var(--muted); margin-top: 1.5mm; }
.legend { list-style: none; padding: 0; margin: 2mm 0 0; display: flex; flex-wrap: wrap; gap: 1.5mm 5mm; font-size: 9pt; }
.legend li { display: flex; align-items: center; gap: 1.5mm; }
.sw { width: 4mm; height: 4mm; border-radius: 1mm; display: inline-block; border: 1px solid #0003; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 6mm; } .cols > * { min-width: 0; }
.steps { counter-reset: st; list-style: none; padding: 0; margin: 2mm 0 4mm; }
.steps li { counter-increment: st; position: relative; padding: 0 0 2.4mm 9mm; }
.steps li::before { content: counter(st); position: absolute; left: 0; top: 0; width: 6mm; height: 6mm; border-radius: 50%; background: var(--ink);
  color: #fff; font-family: var(--head); font-weight: 600; font-size: 9pt; display: flex; align-items: center; justify-content: center; }
.note { border-left: 3px solid var(--accent); background: #eef6f3; padding: 2.5mm 3.5mm; margin: 3mm 0; font-size: 9.8pt; }
.tip { border-left: 3px solid #b06f0a; background: #fbf3e4; padding: 2.5mm 3.5mm; margin: 3mm 0; font-size: 9.8pt; }
.tip b { color: #8a5508; }
.use { color: var(--muted); font-style: italic; }
.gloss td:first-child { font-weight: 600; white-space: nowrap; }
.help td:first-child { width: 38%; }
.cover { display: flex; flex-direction: column; }
.cover .mast { background: #18181b; color: #fff; margin: -15mm -17mm 6mm; padding: 18mm 17mm 10mm; }
.cover .mast .eyebrow { color: #8be0c4; }
.cover .mast p { color: #c9c9d0; font-size: 12pt; }
.toc { list-style: none; padding: 0; margin: 3mm 0; } .toc li { display: flex; justify-content: space-between; border-bottom: 1px dotted var(--line); padding: .4mm 0; }
svg .lg { font: 600 11.5px var(--body); fill: #232326; text-anchor: middle; }
svg .bt { font: 600 12px var(--body); text-anchor: middle; }
svg .bb { font: 700 18px var(--body); text-anchor: middle; }
svg .bs { font: 400 10px var(--body); text-anchor: middle; }
svg .pm { font: 700 17px var(--head); text-anchor: middle; }
svg .an { font: 600 19px var(--head); fill: #16161a; text-anchor: middle; }
svg .ar { font: 600 19px var(--head); fill: #16161a; text-anchor: start; }
svg .co { font: 600 26px var(--head); fill: #16161a; }
.how { background: #eef3ea; border-radius: 2mm; padding: 1.6mm 3mm; font-size: 9.5pt; }
svg .cb { font: 600 20px var(--head); fill: #16161a; text-anchor: middle; }
svg .cs { font: 600 15px var(--body); fill: #5d5d66; text-anchor: middle; }
"""


def build():
    pages = []
    pages.append(page(f"""
<div class="mast"><div class="eyebrow">Rhythm Plus firmware {FIRMWARE} · Circuit Rhythm</div>
<h1>Rhythm Plus User Manual</h1>
<p>Pattern and Step Mutate, the Track Parameter Editor with Granular, Filter, Pitch and Extras, time stretch, Grid FX sends,
the FX track, the scrub, copying, MIDI Merge and quantize.</p></div>
<h3>Contents</h3>
<ul class="toc">
<li><span>Start here: back up, install, how to read this manual</span><span>@S@</span></li>
<li><span>Glossary</span><span>@G@</span></li>
<li><span>Tutorials: first mutate (@T1@), Granular (@T2@), loop to tempo (@T3@), keyboard and second unit (@T4@), knob on a lane</span><span>@T5@</span></li>
<li><span>1 · Pattern Mutate: overview and quick start</span><span>@1@</span></li>
<li><span>2 · The Mutate settings, page 1</span><span>@2@</span></li>
<li><span>3 · The Mutate settings, page 2</span><span>@3@</span></li>
<li><span>4 · Playing a mutate</span><span>@4@</span></li>
<li><span>5 · Ending a mutate, scenes and saving</span><span>@5@</span></li>
<li><span>6 · Pattern Mutate quick reference</span><span>@6@</span></li>
<li><span>7 · Step Mutate: overview and the settings page</span><span>@7@</span></li>
<li><span>8 · The Step Mutate targets</span><span>@8@</span></li>
<li><span>9 · The Track Parameter Editor</span><span>@9@</span></li>
<li><span>10 · The Stock page: view, automate and lock</span><span>@10@</span></li>
<li><span>11 · Settings and Assignments</span><span>@11@</span></li>
<li><span>12 · The Granular page</span><span>@12@</span></li>
<li><span>13 · The Filter page</span><span>@13@</span></li>
<li><span>14 · The Pitch page</span><span>@14@</span></li>
<li><span>15 · The Extras page</span><span>@15@</span></li>
<li><span>16 · Sample Mode</span><span>@16@</span></li>
<li><span>17 · Resetting knobs and tracks</span><span>@17@</span></li>
<li><span>18 · Grid FX sends</span><span>@18@</span></li>
<li><span>19 · The FX track and Shift controls</span><span>@19@</span></li>
<li><span>20 · The playhead scrub</span><span>@20@</span></li>
<li><span>21 · Copying projects and samples, deleting packs</span><span>@21@</span></li>
<li><span>22 · MIDI Thru, Merge and USB merge</span><span>@22@</span></li>
<li><span>23 · Quantize</span><span>@23@</span></li>
<li><span>Help: problems and fixes</span><span>@H@</span></li>
</ul>
<div class="note">Rhythm Plus saves some project settings in a small RP_ file next to the project, in the pack's Sessions folder:
<b>RP_05_MyBeat_…rps</b> goes with <b>05_MyBeat.ncs</b>. When you copy a project on a computer, copy its RP_ file too. Copies made on the unit (chapter 21) take the RP_ files with them. If it is missing, Save flashes red and does not save: hold {CL} and press Save two times
to save with the default settings. Internal pack projects keep their RP_ files on the card, in RP_INTERNAL (see Help).</div>""", "cover"))

    pages.append(page(f"""
<div class="eyebrow">Start here</div><h2>Before you start</h2>
<p>Rhythm Plus is firmware for the Novation Circuit Rhythm. It starts from the official firmware 2.0.1 and keeps how the unit works; the
new features sit on top. This manual shows only what Rhythm Plus adds. For everything else, read Novation's Circuit Rhythm User Guide.</p>
<h3>1. Back up the SD card</h3>
<p>Open the Rhythm Plus app (rhythm_plus_app.html) in Chrome or Edge. Its Backup page copies the packs and the RP_AUTO and RP_INTERNAL folders
to the computer and checks the copy. Open the card's top folder, so that the app sees all three. Restore puts a backup back on the card.</p>
<h3>2. Install or update</h3>
<ol class="steps"><li>In the app, open the Firmware page and choose a build: Stable is tested on the unit, In development is the newest.</li>
<li>Download Circuit Rhythm 2.0.1 (5706) from Novation and drop it on the page. The page adds the chosen build to it.</li>
<li>Connect the unit over USB and turn it on. Close Novation Components. Press Connect.</li>
<li>Press Install. When the unit asks, press {PL} on it. Do not disconnect it until the end.</li></ol>
<p>To go back to the official firmware, drop Novation's own .syx file in the box "Your .syx file" and install it, or use Novation Components.</p>
<h3>3. How to read this manual</h3>
{table(["You see", "It means"], [
        [f"{SH}", "A button on the unit."],
        ["Pad 1-32", "The grid pads: 1-8 the top row, 25-32 the bottom row."],
        ["K1-K8", "The eight knobs, left to right."],
        ["A yellow ring in a drawing", "Hold that button or pad."],
        ["Lights in a drawing", "The Circuit Rhythm's top panel. The Track Parameter Editor lights are the firmware's own."],
        ["Tip", "Advice that makes a job easier. You do not have to follow it."],
        ["Hold, tap", "Hold: keep it pressed. Tap: press and let go."]])}
<div class="tip"><b>Tip:</b> the Glossary on the next page explains the words that Rhythm Plus uses.</div>"""))

    pages.append(page(f"""
<div class="eyebrow">Glossary</div><h2>Words in this manual</h2>
{table(["Word", "Meaning"], [
        ["Assignments", "On the Granular, Filter, Pitch and Extras pages: where a control gets an automation lane (chapter 11)."],
        ["Extras", "The page with Ring Mod and Scan (chapter 15)."],
        ["Filter (MIDI)", "A Thru jack mode: MIDI In, without the channels that the unit listens on (chapter 22)."],
        ["Follow", "Stretch with no length chosen: the sample plays at its own speed, then stretches when the tempo changes (chapter 16)."],
        ["FX track", "A track whose steps turn the Grid FX pads on and off, in time with the pattern (chapter 19)."],
        ["Granular", "Plays the track's sample as many short grains (chapter 12)."],
        ["Grid FX send", "How much of a track goes into Grid FX (chapter 18)."],
        ["Lane", "One of a track's 8 automation lanes, one for each Stock knob. A control of another page can record on a lane (chapter 11)."],
        ["Live", "A Mutate setting: a setting change is heard at once, while you are on the settings page (chapter 3)."],
        ["Merge", "A Thru jack mode: MIDI In and the unit's own MIDI together (chapter 22)."],
        ["Mutate", "Pattern Mutate: each track gets a new play list of its own patterns, in a random order. Your patterns do not change (chapter 1)."],
        ["Page", "The set of controls on the knobs in the Track Parameter Editor: Stock, Granular, Filter, Pitch or Extras (chapter 9)."],
        ["Page pad", "Pads 26-30 in the Track Parameter Editor. Tap one to choose its page; hold it to open the page's Settings."],
        ["Play list", "The run of a track's patterns that a mutate makes (chapter 1)."],
        ["RP_ file", "The small file next to a project that holds its Rhythm Plus settings (see the cover)."],
        ["RP_AUTO", "The SD card folder that keeps Rhythm Plus files of deleted projects and packs (chapter 21)."],
        ["RP_INTERNAL", "The SD card folder that holds the RP_ files of the internal pack's projects (see the cover)."],
        ["Scan", "Moves the start of each note through the sample (chapter 15)."],
        ["Scrub", f"Hold {SH} + {PL} for 0.5 s, then turn K1: moves the playhead step by step (chapter 20)."],
        ["Seed", "The start number of a track's random choices in a mutate. The same seed and settings give the same list (chapter 3)."],
        ["Settings", "Pads 17-24 of a page: its on/off and mode choices. Hold the page pad to open them (chapter 11)."],
        ["Step Mutate", "Changes the steps of the selected track's pattern: notes, velocities, gates and more (chapter 7)."],
        ["Stretch", "Time stretch: a sample plays over the length you choose, in time with the tempo (chapter 16)."],
        ["Track Parameter Editor", "Tap the selected track's button again: its knobs, steps and a value bar (chapter 9)."],
        ["Wipe", f"{CL} + a track button: the track goes back to its defaults. Its steps and sample stay (chapter 17)."]], "gloss")}"""))

    pages.append(page(f"""
<div class="eyebrow">Tutorial 1</div><h2>Your first mutate</h2>
<p class="use">About 2 minutes. You need a project with a few patterns on its tracks.</p>
<ol class="steps"><li>Load the project. Press {PA}, then {PL}.</li>
<li>Hold {SH} and tap {DU}. Each track gets a new play list of its own patterns. Each list starts at the end of the track's pattern.</li>
<li>Listen. Tap {DU} again, with {SH} still held, for new lists.</li></ol>
{figure(patterns_shift_duplicate(callouts=[(59, "1. Hold Shift"), (56, "2. Tap Duplicate"), (34, "The pattern that plays\npulses", "L")]),
        "Tracks 1, 3 and 6 have a play list. The other tracks play their chains.")}
<ol class="steps" style="counter-reset: st 3"><li>Hold {SH} and hold {DU} for a moment: the Mutate settings open. Tap a pad in the Length column for a longer or
shorter list. Tap {DU} to close the settings. The next mutate uses them.</li>
<li>To go back to your chains, hold {CL} and tap {DU}.</li></ol>
{figure(mutate_page1(callouts=[(0, "Live", "L"), (26, "Length of the list", "L"), (51, "▼: page 2"),
        (56, "Tap: close")]), "The Mutate settings, page 1 (chapter 2).")}
<div class="tip"><b>Tip:</b> do you like the lists? Hold {SH} and tap a scene pad: the scene keeps each track's mutate (chapter 5).</div>"""))

    pages.append(page(f"""
<div class="eyebrow">Tutorial 2</div><h2>Your first Granular sound</h2>
<p class="use">About 3 minutes. A long sample works best: a pad, a voice or a loop.</p>
<ol class="steps"><li>Select track 1 and choose a long sample in Sample View.</li>
<li>Tap track button 1 again: the Track Parameter Editor opens. Tap pad 27: the Granular page.</li>
<li>Hold pad 27 for a moment: its Settings open. Tap pad 17: it turns green, Granular is on. Tap pad 27 to close the Settings.</li></ol>
{figure(editor("granular_settings", row3="Settings", marks={16: "On", 17: "Mode", 22: "Frz"}, width=300,
               callouts=[(16, "Pad 17: green = on", "L"), (22, "Pad 23: Freeze", "L"), (26, "Pad 27: hold", "L")]),
        "Granular Settings, Granular still off: pad 17 is red.")}
<ol class="steps" style="counter-reset: st 3"><li>Play notes, or press {PL} if the track has steps. Turn K2 (Size) and K3 (Density): you hear the grains change.
Turn K1 (Position) to move through the sample.</li>
<li>Turn K5 (Position scatter) and K6 (Pitch scatter) for a cloud. For one held moment, open the Settings and tap pad 23: Freeze.</li></ol>
{figure(editor("granular", width=300, callouts=[(61, "K2: Size"), (62, "K3: Density", "R"), (60, "K1: Position", "L"), (64, "K5, K6: scatter"),
        (18, "The bar: its value", "L")]), "The Granular page, knob page 1 (chapter 12).")}
<div class="tip"><b>Tip:</b> the knobs work when Granular is off too. Their values stay for when you turn it on.</div>"""))

    pages.append(page(f"""
<div class="eyebrow">Tutorial 3</div><h2>Fit a loop to the tempo</h2>
<p class="use">About 2 minutes. You need a drum loop or a break as a sample.</p>
<ol class="steps"><li>Select the track and choose the loop in Sample View.</li>
<li>Press {key('Sample')} two times: Sample Mode opens.</li>
<li>Tap the length of the loop: pad 13 for 1 bar, pad 14 for 2 bars. Pad 9 turns green: stretch is on.</li></ol>
{figure(sample_mode(callouts=[(8, "Pad 9: green = stretch on", "L"), (9, "Pad 10: white = the whole sample", "L"),
        (12, "Pads 11-16: 1/4 to 8 bars", "R"), (16, "Pad 17: Granular (red = off)", "L")]),
        "Sample Mode with 1 bar chosen. Only the Rhythm Plus pads are drawn lit.")}
<ol class="steps" style="counter-reset: st 3"><li>Press {PL}. Change the tempo: the loop stays in time, and its pitch does not change.</li>
<li>Tap pad 9 to hear the loop at its own speed again: pad 9 turns red. Tap it again and the length comes back.</li></ol>
<div class="tip"><b>Tip:</b> a dim red length pad is a length the sample cannot reach: it would play more than 4 times slower or
faster.</div>
<p>To play only a part of the loop, tap pad 10 (amber): K2 and K3 then choose the start and the end that fill the length (chapter 16).</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Tutorial 4</div><h2>A keyboard and a second unit</h2>
<p class="use">Play a synth or a second unit from a keyboard through the Rhythm, in time with the Rhythm's clock. You need a MIDI
keyboard, a second MIDI device and two MIDI cables.</p>
{figure(midi_chain(), "The cables: the keyboard into MIDI In, the Thru jack to the second unit.")}
<ol class="steps"><li>Connect the cables as in the drawing.</li>
<li>Hold {SH} while you turn the Rhythm on: Advanced Setup opens.</li>
<li>Press {DU} until it is yellow: Merge. Press {PL} to leave Advanced Setup.</li></ol>
{figure(advanced_setup(), "Advanced Setup with Merge. Only the lights used here are drawn.")}
<ol class="steps" style="counter-reset: st 3"><li>Hold {SH} and press {key('Save')}: Setup opens. Pad 32, Clock Tx, must be bright: on.</li>
<li>Set the keyboard to a channel that no Rhythm track uses, for example 9. Or tap pad 25 in Setup: Note Rx off. Then the Rhythm's
tracks do not play the keyboard. Press {PL} to leave Setup.</li>
<li>On the second unit, turn on its clock sync and set its sound to the keyboard's channel.</li>
<li>Press {PL} on the Rhythm. The second unit follows its tempo, and the keyboard plays it.</li></ol>"""))

    pages.append(page(f"""
<div class="eyebrow">Tutorial 5</div><h2>Record a Granular knob on a lane</h2>
<p class="use">About 3 minutes. A Granular knob records its moves on one of the track's 8 automation lanes. Here, Size (K2) gets
lane K6. Do Tutorial 2 first, so that Granular is on.</p>
<ol class="steps"><li>Open the Track Parameter Editor and tap pad 27: the Granular page.</li>
<li>Hold pad 27 for a moment: Settings open, and pad 27 pulses.</li>
<li>Press {DN} (lit white): Assignments open.</li>
<li>Turn K2 a little. Its light goes white: Size is the picked control. Its value does not change.</li>
<li>Tap pad 22: lane K6. It turns bright lime. Size now records on lane K6.</li></ol>
{figure(editor("granular_assign", row3="Lanes", change={"i60": 0x0A1105, "i61": 0x8C8C8C, "i21": 0x568C30}, width=380,
               callouts=[(61, "K2 white: picked", "L"), (21, "Pad 22: lane K6", "L"), (52, "▲: back to Settings", "L")]),
        "Assignments: Size (K2) on lane K6.")}
<ol class="steps" style="counter-reset: st 5"><li>Press {UP} to go back to Settings, then tap pad 27 to close them.</li>
<li>Press Record (●), then {PL}. Turn K2 while the pattern plays: the bar is red, and the moves go into the steps.</li>
<li>Press Record again to stop recording. The pattern now plays your Size moves.</li></ol>
<div class="tip"><b>Tip:</b> choose a lane that has no Stock automation you want. Lane K6 is the Stock HP Filter's lane. That
knob still works by hand, but it does not record while Size uses the lane.</div>
<p>To delete the moves, hold {CL} and turn K2 left until it stops. To free the lane, open Assignments, pick K2 and tap pad 22
again.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 1</div><h2>Pattern Mutate: overview and quick start</h2>
<p>A mutate gives each track a new play list: a short run of that track's own patterns, in a random order. The track plays the list
in a loop in place of its chain. Your patterns do not change. You can go back to the chains at any time.</p>
<p>Use it to find new variations of a groove: try a mutate, keep it if you like it, try another if you do not.</p>
<h3>Quick start</h3>
<ol class="steps">
<li>Press {PA} to show the Patterns View. Press {PL}.</li>
<li>Hold {SH} and tap {DU}. Each track gets a new list. The lists start at each track's next pattern end.</li>
<li>Tap again for another mutate. Each tap makes new lists.</li>
<li>To go back to the chains: hold {CL} and tap {DU}.</li>
</ol>
{figure(patterns_shift_duplicate(), f"{SH} + {DU} (yellow rings) on the Patterns View: {DU} is full green. Columns are tracks 1-8.")}
<h3>The Duplicate button</h3>
<p>On the Patterns View, {DU} shows the state of the mutate:</p>
{table(["Duplicate", "Meaning"], [
        ["Its normal light", "No button held: {DU} copies patterns, as normal.".replace("{DU}", DU)],
        [f'<span class="sw" style="background:{lit(GREEN, 0.4)}"></span> Dim green', f"{SH} is held: a tap mutates."],
        [f'<span class="sw" style="background:{lit(GREEN)}"></span> Full green', f"{SH} + {DU} is down."],
        [f'<span class="sw" style="background:{lit(GREEN, 0.6)}"></span> Green, pulsing', "The Mutate settings page is open."],
        [f'<span class="sw" style="background:{lit(RED)}"></span> Red', f"{CL} is held and a track has a mutate: a tap ends every mutate."]])}
<h3>The settings</h3>
<p>Hold {SH} and hold {DU} for a moment to open the Mutate settings page. Tap {DU} to close it. {SH} + tap {DU} on the page makes a mutate and keeps the page open. The settings are for all tracks and
are saved with the project. Chapters 2 and 3 show each setting.</p>
<div class="note">A track's mutate stays until you end it, pick a pattern for that track, or change the scene (see chapter 5).</div>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 2</div><h2>The Mutate settings, page 1</h2>
<p>Hold {SH} and hold {DU} to open the page. It opens in the Patterns, Mixer, Grid FX, FX and Side Chain views; the knobs work as
normal. Columns 3 to 6 are the settings; each pad in a column is one value. The chosen value is full, the other values are dim.
Column 1 is Live, on both pages. {DN} shows page 2, {UP} shows page 1 again. Hold {PA}, {MI} or FX to look at
that view, or {SH} + a track button to look at that track (with {SH} held, the track buttons show the tracks' colours, the
selected track bright); when you let go, the settings page comes back. A tap goes to that view
and closes the settings.</p>
{figure(mutate_page1(), "Page 1 with Live Off, Length 4, Length type Exact, Pool With steps and When On the tap.")}
{table(["Column", "Setting", "Pads, top to bottom", "What it does"], [
        ["1", "Live", "Off (default) · On", "On: you hear a setting change at once, while you are on the settings page. You do not have to mutate again. The same pad on both pages (chapter 3)."],
        ["3", "Length", "1, 2, 3, 4 (5-8 on page 2)", "How many slots a list has, when Length type is Exact or Random. Tap the last pad of the bar."],
        ["4", "Length type", "Same as the chain (default) · Exact · Random", "Same as the chain: a list as long as the track's chain (the Length column is very dim, not used). Exact: always Length slots. Random: 1 to Length slots, new at each mutate."],
        ["5", "Pool", "With steps (default) · All", "With steps: only the patterns that have notes. All: all 8 patterns, also empty ones."],
        ["6", "When", "On the tap (default) · Every chain end", "On the tap: the list starts at the next pattern end and loops. Every chain end: the track waits for its chain's end, then gets a new list each time its list ends."]])}
<h3>The track buttons on this page</h3>
<p>Tap a track button to choose if that track mutates. Bright = it mutates, very dim = it keeps its chain. All tracks are on at first.</p>
<h3>The Length bar</h3>
<p>Same as the chain: very dim, not used. Exact: full up to the Length. Random: dim, with the Length's pad full.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 3</div><h2>The Mutate settings, page 2</h2>
<p>Press {DN} on the settings page. Column 1 is Live, as on page 1. Column 3 goes on with Length 5-8. Columns 4 to 6 are three more
settings.</p>
{figure(mutate_page2(), "Page 2 with Live On, Amount Some, Repeats On and Keep slot 1 On.")}
{table(["Column", "Setting", "Pads, top to bottom", "What it does"], [
        ["3", "Length", "5, 6, 7, 8", "The Length bar goes on from page 1."],
        ["4", "Amount", "All (default) · Most · Some · A little", "How much of the chain a mutate changes. The meter fills from the bottom up: more light, more change."],
        ["5", "Repeats", "On (default) · Off", "Off: a list never plays the same pattern twice in a row (also not from its last slot back to slot 1). With only one pattern that has notes, it plays that one."],
        ["6", "Keep slot 1", "Off (default) · On", "On: each list starts on the chain's first pattern, a home beat. Only the slots after it change."]])}
<h3>Amount, step by step</h3>
<div class="cols"><div>
{table(["Amount", "Changes", "Chain 1 · 2 · 3 · 4"], [
        ["All", "4 of 4", "7 · 6 · 2 · 5"], ["Most", "3 of 4", "5 · 2 · 8 · 6"], ["Some", "2 of 4", "1 · 6 · 3 · 2"],
        ["A little", "1 of 4", "1 · 2 · 7 · 4"]])}
</div><div>
<p>Each slot of a list either keeps the chain's pattern at that place, or gets a random one. The table shows a chain of 4 patterns.</p>
<p>For other lengths the number is rounded, and at least one slot changes. Slots past the end of the chain are always random. With
Keep slot 1 On, Amount counts only the slots after slot 1.</p>
</div></div>
<h3>Live (column 1)</h3>
<p>Live lets you hear the settings while you change them. With Live Off, a change is used at the next mutate ({SH} + tap {DU}).
With Live On, when you change Length, Length type, Pool, Amount, Repeats or Keep slot 1, the list of each track that mutates
changes at once, while it plays. Tracks that do not mutate keep their lists.</p>
<p>The change is not a new random list. Each mutate gives each track a seed: a start number for its random choices. Live makes the
list again from the same seed with the new setting. So when you set a setting back, the list that you had comes back. With Live
On, setting When to Every chain end also starts it at once, as a tap does.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 4</div><h2>Playing a mutate</h2>
<p>On the Patterns View, each column is a track and each pad is a pattern. A mutated track shows its list:</p>
{figure(patterns_mutated(), "Tracks 1, 3 and 6 are mutated. The other tracks show their chains.",
        legend=[(lit(TRK[0], 0.44), "In the list"), (lit(TRK[0], 0.03), "Not in the list (very dark)"),
                (lit(TRK[0]), "The pattern playing (it pulses)")])}
{table(["You do", "Result"], [
        [f"{PL}", "Each mutated track starts on slot 1 of its list."],
        [f"{SH} + {PL}", "Play goes on from where you stopped. Then the list goes on from slot 1."],
        [f"Mutate while stopped", "The mutated tracks show their whole new list. The pad of the old stop point shows again when you play."],
        [f"Tap a pattern pad of a mutated track", "That track's mutate ends. The pattern that you tap plays, as normal."],
        [f"{CL} + pad, {DU} + pad", "Clear or copy a pattern, as normal. The mutate stays."],
        [f"{SH} held", "The track buttons show their normal {SH} lights. The pads keep showing the lists.".replace("{SH}", SH)]])}
<h3>View Lock</h3>
<p>Hold {SH} and press {PA} to turn View Lock on or off. When you turn it on, the patterns that play at that moment turn white and
stay white.</p>
{table(["With View Lock on", "Result"], [
        [f"{SH} + a pad", "That track's white pad moves to this pattern. The mutate and the chain do not change."],
        ["A pad without {SH}".replace("{SH}", SH), "The track's mutate ends and the pattern is picked, as normal. The white pads stay."],
        [f"{CL} + a green track button", "The track's mutate ends (chapter 5). The white pads stay."],
        ["View Lock off, then on", "The white pads move to the patterns that play now."]])}"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 5</div><h2>Ending a mutate, scenes and saving</h2>
<h3>See which tracks are mutated</h3>
<p>Hold {CL} on the Patterns View. The buttons of the mutated tracks are green, the others dark. {DU} is red when there is a mutate to end.</p>
{figure(patterns_clear(), f"{CL} held: tracks 1, 3 and 6 are mutated.")}
{table(["You do", "Result"], [
        [f"{CL} + a green track button", "That track's mutate ends. Its button flashes red, then goes dark. The track goes back to its chain."],
        [f"{CL} + a dark track button", "Nothing happens. The track is not selected."],
        [f"{CL} + {DU}", f"Every mutate ends. The mutated tracks flash red. This also works in the Mixer, Grid FX, FX and Side Chain views."],
        [f"{CL} held on the settings page", f"The pads show the Patterns View, so you can see each mutate. {DU} keeps pulsing green: you are still on the settings page. The pads do nothing. {DN} / {UP} show the other page of patterns. {CL} + a track button ends that track's mutate."]])}
<p>In a track's Sample View or Note View, {CL} + a track button wipes the track (chapter 17).</p>
"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 5, continued</div><h2>Scenes and saving</h2>
<h3>Scenes</h3>
<p>A scene keeps the mutate of each track: its seed, the settings that made its list and its chain. So a scene plays the exact
lists that you heard when you saved it, and Live goes on from them.</p>
{table(["On the Mixer View", "Result"], [
        [f"{SH} + a scene pad", "Saves the scene with each track's mutate."],
        ["A scene pad", "Plays the scene with its saved lists. Stopped: at once. Playing: at the end of track 1's pattern. The mutate plays until then."],
        [f"{DU} + a scene pad, then another", "Copies the scene, its mutate too."],
        [f"{CL} + a scene pad", "Clears the scene, its mutate too."]])}
<p>A scene saved without a mutate plays its chains: a scene change ends the mutate of the tracks with no list in that scene.</p>
<p>In a scene chain, the chain goes to the next scene when each mutated track has played the last slot of its list. {PL} starts on
the chain's first scene, with its own lists.</p>
<div class="note">With Pool With steps, a list uses only the patterns that have notes. If you add notes to an empty pattern, or clear
a pattern, a saved list can change.</div>
<h3>Saving</h3>
<p>The project keeps the Mutate settings, each track's mutate and the mutate of each scene. A project from an earlier firmware opens
with the default settings and no mutate.</p>"""))

    ref = [
        [f"{SH} + tap {DU}", "Patterns, Mixer, Grid FX, FX, Side Chain", "Mutate (new lists with the settings)"],
        [f"{SH} + hold {DU}", "Patterns, Mixer, Grid FX, FX, Side Chain", "Open the Mutate settings page"],
        [f"Tap {DU}", "Settings page", "Close the settings page"],
        [f"{SH} + tap {DU}", "Settings page", "Mutate, the page stays open"],
        [f"{DN} / {UP}", "Settings page", "Page 2 / page 1"],
        ["A setting's pad", "Settings page", "Choose that value"],
        ["A track button", "Settings page", "That track mutates or not"],
        [f"{CL} held", "Settings page", "Show the mutate; pads do nothing"],
        [f"{CL} + a track button", "Settings page", "End that track's mutate"],
        [f"{CL} held", "Patterns View", "Mutated tracks' buttons green"],
        [f"{CL} + a green track button", "Patterns View", "End that track's mutate"],
        [f"{CL} + {DU}", "Patterns, Mixer, Grid FX, FX, Side Chain", "End every mutate"],
        ["A pattern pad", "Patterns View", "End that track's mutate, pick the pattern"],
        [f"{SH} + a pad (View Lock on)", "Patterns View", "Move the white pad; the mutate stays"],
        [f"{PL}", "Any page", "Start the lists from slot 1"],
        [f"{SH} + {PL}", "Any page", "Go on from the stop point"],
        [f"{SH} + a scene pad", "Mixer View", "Save the scene with the mutate"],
    ]
    pages.append(page(f"""
<div class="eyebrow">Chapter 6</div><h2>Pattern Mutate quick reference</h2>
{table(["Control", "Where", "Result"], ref)}
<h3>Defaults</h3>
{table(["Setting", "Default"], [["Length", "4"], ["Length type", "Same as the chain"], ["Pool", "With steps"], ["When", "On the tap"],
                              ["Amount", "All"], ["Repeats", "On"], ["Keep slot 1", "Off"], ["Live", "Off"], ["Tracks", "All on"]])}"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 7</div><h2>Step Mutate: overview and the settings page</h2>
<p class="use">Use it to vary one track's pattern, for example new velocities, notes or gates for a hi-hat line.</p>
<p>Step Mutate changes the steps of the selected track's pattern: their notes, velocities, gates and more. It changes only the steps
from the pattern's start step to its end step, so it works the same for 16 or 32 steps. Each track has its own settings.</p>
<div class="note">Step Mutate changes the pattern itself. There is no undo. To keep the pattern as it is, duplicate it to an empty
pattern on the Patterns View first, then mutate the copy.</div>
<h3>Quick start</h3>
<ol class="steps">
<li>Select a track: its Sample View or Note View shows.</li>
<li>Hold {SH} and tap {DU}. The pattern's steps change places, as the standard Mutate does.</li>
<li>Hold {SH} and hold {DU} for a moment. The settings page opens.</li>
<li>Tap a target pad to turn it on or off. Hold it to see its settings on columns 6-8.</li>
<li>Tap {DU} to close the page. Hold {SH} and tap {DU} to mutate with the new settings.</li>
</ol>
{figure(step_mutate_page(), "The settings page: Step movement and Velocity on, Velocity's settings shown (it pulses).")}
{table(["Pads", "What they do"], [
        ["Pads 1-3, 9, 17, 18, 25-28", "The targets (chapter 8). Bright = on, dim = off. Tap to turn on or off. Hold to show the target's settings: they stay after you let go."],
        ["Columns 6-8", "The shown target's settings. A pad is one value. A meter fills from the bottom: more light, more change. A choice: the chosen value is full."],
        ["The other pads", "Dark. They do nothing."]])}
{table(["Duplicate", "Meaning"], [
        [f'<span class="sw" style="background:{lit(GREEN, 0.4)}"></span> Dim green', f"In a track's view with {SH} held: a tap mutates."],
        [f'<span class="sw" style="background:{lit(GREEN)}"></span> Full green', f"{SH} + {DU} is down."],
        [f'<span class="sw" style="background:{lit(GREEN, 0.6)}"></span> Green, pulsing', "The Step Mutate settings page is open."],
        ["Its normal light", "All the track's targets are off: a tap does nothing."]])}"""))

    sm = [
        ["Note", "1", "Amount", "Range: Any, 12, 7, 3 semitones", "Direction: Up, Down, Both", "Off; Some, 3, Both"],
        ["Sample flip", "2", "Amount", "Range: Any, Growing, within 8, within 4", "Steps: Pink only, All steps", "Off; Some, within 8, Pink only"],
        ["Step movement", "3", "Amount", "Range: Anywhere, up to 8, 4, 2 steps", "", "On; All, Anywhere"],
        ["Velocity", "9", "Amount", "Range: Any (1-127), up to 48, 24, 8", "Direction: Up, Down, Both", "Off; Some, 24, Both"],
        ["Gate", "17", "Amount", "Range: Any (up to 16 steps), up to 2 steps, 1 step, half a step", "Direction: Longer, Shorter, Both", "Off; Some, 1 step, Both"],
        ["Microsteps", "18", "Amount", "Hits: up to 6, 4, 3, or 2", "Hits: Any microstep, On the beat", "Off; Some, 2, On the beat"],
        ["Pattern length", "25", "Range: Any, up to 8, 4, 2 steps", "Moves: End, Start, Both", "", "Off; 4, End"],
        ["Pattern speed", "26", "Range: Any rate, 2 rates away, 1 rate away", "", "", "Off; 1 rate away"],
        ["Play mode", "27", "Modes: Forward, Reverse, Ping-pong, Random (each on or off)", "", "", "Off; all but Random"],
        ["Probability", "28", "Amount", "Range: down to 12 %, 25 %, 50 %, 75 %", "", "Off; Some, 50 %"],
    ]
    pages.append(page(f"""
<div class="eyebrow">Chapter 8</div><h2>The Step Mutate targets</h2>
<p>A mutate changes each target that is on. Columns 6, 7 and 8 are the target's settings, top pad first.</p>
{table(["Target", "Pad", "Column 6", "Column 7", "Column 8", "Default"], sm)}
<h3>Direction</h3>
<p>Up: only higher (or longer). Down: only lower (or shorter). Both: either way.</p>
<h3>Amount</h3>
<p>Amount is a share of the steps that have a note, from the start step to the end step: All, Most (3 of 4), Some (2 of 4) or
A little (1 of 4). At least one step changes. Steps with no note do not change.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 8, continued</div><h2>What each target does</h2>
{table(["Target", "A changed step"], [
        ["Note", "Its note moves by 1 to the Range, in the Direction. Any: anywhere on the note keyboard (7 octaves), in the Direction."],
        ["Sample flip", "Plays another sample. Any: one of the 64. Growing: one sample up or down from the step's flip, so the flips spread out over many mutates. Within 8 or 4: near the track's sample in the Sample View. Pink only: only steps that have a flip change. All steps: blue steps can get a flip too."],
        ["Step movement", "All + Anywhere: the standard Mutate shuffle. Every step from the start to the end gets a new place, empty steps too. Other settings: a changed step changes places with a step up to the Range away. Automation goes with its step."],
        ["Velocity", "Its velocity moves by 1 to the Range, in the Direction. Any: anywhere from 1 to 127, in the Direction."],
        ["Gate", "Its gate moves by 1 microstep to the Range, in the Direction. Any: anywhere up to 16 steps, in the Direction."],
        ["Microsteps", "Gets 1 hit (no roll) up to the Hits value, by chance. Any microstep: the hits land on random microsteps. On the beat: an even roll from the first microstep."],
        ["Pattern length", "The whole pattern: its end step, start step or both move up to the Range. The start stays before the end."],
        ["Pattern speed", "The whole pattern: its speed moves up to the Range, for example from 1/16 to 1/8."],
        ["Play mode", "The whole pattern: it gets one of the modes that are on, a different one if it can."],
        ["Probability", "Gets a new chance, from the Range's value to 100 %."]])}"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 8, continued</div><h2>Clear and the buttons</h2>
<h3>Clear + a target pad</h3>
<p>Hold {CL} on the settings page. The target pads turn dim red. Tap one: that part of each step with a note, from the start step
to the end step, goes back to its default. The pad flashes red three times. Your settings and the targets' on or off do not
change. There is no undo.</p>
{table(["Clear +", "Result"], [
        ["Note", "Every note back to the sample's own pitch"], ["Sample flip", "No flips: each step plays the track's sample"],
        ["Velocity", "Velocity 96"], ["Gate", "1 step"], ["Microsteps", "Each step keeps only its first hit"],
        ["Probability", "100 %"], ["Pattern length", "Start 1, end 16"], ["Pattern speed", "1/16"], ["Play mode", "Forward"],
        ["Step movement", "Nothing (its pad is dark while Clear is held)"]])}
<h3>Buttons on the settings page</h3>
{table(["You do", "Result"], [
        [f"Tap {DU}", "The page closes. If you opened it from the Track Parameter Editor, the editor comes back."],
        [f"{SH} + tap {DU}", "Mutate. The page stays open."],
        ["Another track's button", "Select that track. The page shows its settings."],
        ["Tap the selected track's button", "The page closes. The track's Note View or Sample View shows (the one it had last)."],
        ["Hold the selected track's button", "The track's Note View or Sample View shows while you hold it. Let go: the settings page comes back."],
        [f"{CL}, {SH}, Record, {PL}", "They work as normal. The page stays open."],
        ["Hold another button", f"Its first view shows while you hold it ({SH} + hold: its second view). Let go: the settings page comes back."],
        ["Tap another button", "The page closes and the button does its job."]])}
<p>The page opens with Step movement's settings shown. The project saves each track's settings. A project from an earlier firmware opens with the defaults. In the Track Parameter
Editor, {SH} + {DU} mutates but does not open the page.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 9</div><h2>The Track Parameter Editor</h2>
<p class="use">Use it to see and shape one track's sound, and to reach the Granular, Filter, Pitch and Extras pages.</p>
<p>The Track Parameter Editor shows the selected track's knobs, the steps of its pattern, and the value of one knob on a bar.
The knobs have pages: Stock, Granular, Filter, Pitch and Extras.</p>
<ol class="steps"><li>Select a track. Tap its track button again to open the Track Parameter Editor.</li>
<li>Tap a page pad (pads 26-30) to put that page on the knobs.</li>
<li>Turn a knob. The bar shows its value.</li>
<li>Tap the track button again to close the Track Parameter Editor.</li></ol>
{figure(editor(callouts=[(32, "Track button: tap again\nto open or close"), (24, "Pad 25: knob pick", "L"), (25, "Pads 26-30: pages", "L"),
        (60, "K1: the knob shown", "L")]),
        "Track 1 on the Stock page. K1 is shown: its light is white, and the bar (pads 17-24) shows its value from the middle. "
        "Pads 26-30 are the pages; pad 26, Stock, is in the track's colour.")}
{table(["Pads", "Name", "What they do"], [
        ["1-16", "Steps", "The steps of the pattern, as on the track page. Hold a step to view or lock its values (chapter 10)."],
        ["17-24", "Bar", "The value of the shown knob, in the track's colour. Value-bar taps set the value (chapter 10)."],
        ["25", "Knob pick", f"Shows the next knob on the bar, without turning it. {SH} + pad 25: the knob before."],
        ["26", "Stock", "The track's own knobs (chapter 10). Track colour."],
        ["27", "Granular", "Granular sound (chapter 12). Lime."],
        ["28", "Filter", "Filter envelope and LFO (chapter 13). Blue."],
        ["29", "Pitch", "Pitch envelope and LFO (chapter 14). Amber."],
        ["30", "Extras", "Ring modulation and Scan (chapter 15). Deep purple."],
        ["31", "-", "Dark."],
        ["32", "-", "Dark."]])}
<p>The pad of the page on the knobs is bright; the other page pads are dim. Each track keeps its own page. When you load a project,
a track on the Filter, Pitch or Extras page shows Stock again.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 9, continued</div><h2>Lights and terms</h2>
{table(["Light", "Meaning"], [
        ["White knob", "The shown knob."],
        ["Knob in the page's colour", "The page's other knobs. The higher the value, the brighter the light. On the Stock page, and for the Stock knobs on other pages, the track's colour."],
        ["Dark knob", "The knob does nothing on this page."],
        ["Red knob or bar", "Automation: see chapter 10."],
        ["Track buttons", "The selected track is in its own colour. The other tracks are white."],
        ["Pulsing page pad", "The page's Settings or Assignments are open (chapter 11)."]])}
<h3>Terms</h3>
{table(["Term", "Meaning"], [
        ["Shown knob", "The last knob that you turned, or the knob that you picked with pad 25."],
        ["Page", "The set of controls on the knobs: Stock, Granular, Filter, Pitch or Extras."],
        ["Settings", "Choices for a page. Hold the page pad to open them (chapter 11)."],
        ["Lane", "A track has 8 automation lanes, one for each Stock knob. A control of another page can use one (chapter 11)."],
        ["Reset", f"Hold {CL} and turn the knob right until it stops. The value goes back to its default."]])}"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 10</div><h2>The Stock page: view, automate and lock</h2>
<p>Pad 26. The track's own eight knobs, the same as on a standard Circuit Rhythm. Here you can see their values, automate
and lock them, reset them and delete their automation.</p>
{table(["Knob", "Parameter", f"{SH} + knob", "Bar"], [
        ["K1", "Pitch", "-", "From the middle"], ["K2", "Sample start", "Fine start", "2048 steps a pad"],
        ["K3", "Sample length", "Fine length", "2048 steps a pad"],
        ["K4", "Envelope: left of the middle = decay, middle = sustain, right = slow attack", "-", "From the middle"],
        ["K5", "Distortion", "-", "From the left"], ["K6", "High-pass filter", "-", "From the left"],
        ["K7", "Low-pass filter", "-", "From the left"], ["K8", "Resonance", "-", "From the left"]])}
<h3>View a step's value</h3>
<p>Hold a step on pads 1-16. Each knob light turns red if that knob has automation on the step. If the shown knob has automation
on the held step, the bar shows the step's value.</p>
<h3>Automate and lock</h3>
{table(["To", "Do this"], [
        ["Automate", "Arm Record, play, turn the knob. The movement is recorded into the steps that play."],
        ["Lock", "Arm Record, hold a step, turn the knob. The value goes into the held step, also while the pattern plays."],
        ["Delete automation", f"Hold {CL} and turn the knob left until it stops. The knob's automation is deleted; the knob light turns red."]])}
<p>While Record is armed and you turn a knob, the bar is red. While you hold a step with Record armed, the step's pad is red.
This works the same on every page.</p>
<h3>Stock settings</h3>
<p>Hold pad 26 to open them. Tap pad 26 to close them. Bright white: on. Dim white: off.</p>
{table(["Pad", "Setting"], [
        ["17", "Value-bar taps. On: tap a bar pad to set the shown knob to 0, 18, 36, 54, 72, 90, 108 or 127. Tap pads 20 and 21 together for the middle (64). A tap records like a turn. It works on every page of the track."],
        ["18", "Silent step select. On: pads 1-16 select and hold steps without playing them."]])}"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 11</div><h2>Settings and Assignments</h2>
<p>The Granular, Filter, Pitch and Extras pages have Settings and Assignments. They open the same way on each page.</p>
{table(["To", "Do this"], [
        ["Open Settings", "Hold the page pad for a moment. Settings stay open when you let go. The page pad pulses. Pads 17-24 show the settings."],
        ["Close Settings", "Tap the page pad. Selecting another track also closes them."],
        ["Open Assignments", f"In Settings, press {DN} (lit white). The page pad pulses."],
        ["Back to Settings", f"In Assignments, press {UP} (lit in the page's colour)."]])}
<p>In Settings, a knob turn shows the bar for half a second, then the settings come back.</p>
{figure(editor("granular_settings", row3="Settings", marks={16: "On", 17: "Mode", 22: "Frz"},
               callouts=[(51, "▼ white: Assignments", "L"), (16, "Pads 17-24: the settings", "L"), (26, "Page pad: hold = open,\ntap = close", "L")]),
        "Settings open on the Granular page. The page pad (27) pulses.")}
"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 11, continued</div><h2>Assignments: record a control on a lane</h2>
<p>A track has 8 automation lanes, one for each Stock knob. A control of another page records and plays its automation on
one of these lanes.</p>
<ol class="steps"><li>Open Assignments.</li>
<li>Pick the control: turn its knob (the value does not change), or tap pad 25. Its knob is white.</li>
<li>Tap a pad 17-24: lane K1-K8. The control now uses that lane. Tap the same pad again to free the lane.</li></ol>
{figure(editor("granular_assign", row3="Lanes", callouts=[(52, "▲: back to Settings", "L"), (16, "Pads 17-24: lanes K1-K8", "L"),
        (24, "Pad 25: pick the control", "L"), (60, "White knob: the picked control", "L")]), "Assignments on the Granular page: every lane is free (dim white). Pad 25 picks the control. "
        "▲ is lime: back to Settings.")}
{table(["Light in Assignments", "Meaning"], [
        ["Pad 17-24 bright, page colour", "The lane of the picked control."],
        ["Pad 17-24 dim, page colour", "A lane of another control of this page."],
        ["Pad 17-24 dim white", "A free lane, or a lane of another page."],
        ["Pad 17-24 dim red (Granular)", "A lane of a control on Granular's other knob page."],
        ["Pad 25 white", "Picks the control."]])}
<p>A control uses one lane. A lane has one control: a new one replaces the old one. The automation that is on the lane stays,
and it plays into the new control. The Stock knob of that lane still works by hand, but it does not record on the lane.
{CL} + pad 26 does not delete that lane.</p>
<h3>Clear on these pages</h3>
<p>{CL} + turn a knob right until it stops: the control goes back to its default. Left until it stops: its automation is deleted.
This works with Record off. On the Granular and Filter pages the knob light turns blue or red. In Assignments, {CL} + turn only
picks the control. {CL} + a page pad resets that page (chapter 17).</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 12</div><h2>The Granular page</h2>
<p class="use">Use it to turn a sample into textures, pads and clouds of sound.</p>
<p>Pad 27. Granular plays the track's sample as many short grains. Turn it on in Settings (pad 17) or in Sample Mode (pad 17,
chapter 16). The knobs work when Granular is off, and the values stay for when it is on.</p>
<p>Granular has two knob pages. The lime arrow shows the other one: {DN} goes to page 2, {UP} to page 1. Pad 25 picks knobs on both pages.</p>
<div class="cols"><div>
{table(["Knob", "Page 1"], [
        ["K1", "Position"], ["K2", "Size"], ["K3", "Density"], ["K4", "Scan (from the middle)"],
        ["K5", "Position scatter"], ["K6", "Pitch scatter"], ["K7", "Edge"], ["K8", "Reverse"]])}
</div><div>
{table(["Knob", "Page 2"], [
        ["K1", "Level"], ["K2", "Size scatter"], ["K3", "Timing (from the middle)"], ["K4", "Jitter"],
        ["K5", "Slice"], ["K6", "Lock"], ["K7", "-"], ["K8", "-"]])}
</div></div>
<p>{SH} + turn K1-K6 on page 1: fine steps, 16 to one normal step. A fine turn is not recorded. The bar for Slice shows the count:
pad 17 white = off, then 2, 3, 4, 6, 8, 12, 16 and 32 slices from pad 17 to pad 24.</p>
{figure(editor("granular"), "The Granular page, knob page 1. ▼ is lime: knob page 2 is below.")}
"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 12, continued</div><h2>Granular settings</h2>
{how_to_open(27)}
{table(["Pad", "Setting", "Light"], [
        ["17", "Granular on or off", "Green: on. Red: off."],
        ["18", "Mode", "White: Triggered. Amber: Textured."],
        ["19", "Retrigger, shown with Textured: each note starts the texture again", "Bright: on. Dim: off."],
        ["20", "Scan length (chapter 16)", "White: the track's sample. Amber: each sample."],
        ["21", "-", "Dark."],
        ["22", "Bounce: Scan goes back and forth", "Bright: on. Dim: off."],
        ["23", "Freeze", "Bright: on. Dim: off."],
        ["24", "Pitch Set: tap for the next set", "Dim lime: off. White: octaves. Blue: fifths. Yellow: minor. Pink: major."]])}
{figure(editor("granular_settings", row3="Settings", marks={16: "On", 17: "Mode", 19: "Scan", 21: "Bnce", 22: "Frz", 23: "Set"}),
        "Granular settings open: Granular off (red), Triggered, Scan length of the track's sample. ▼ is white: Assignments.")}
<p>Pitch Set moves the pitch scatter (K6) to the notes of the set. Assignments hold all 14 controls of both knob pages
(chapter 11).</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 13</div><h2>The Filter page</h2>
<p class="use">Use it for plucks, filter sweeps and wobbles that move on each note or in time.</p>
<p>Pad 28. An envelope and an LFO move the track's low-pass filter. K7 and K8 are the Stock filter knobs, with the same values and
automation.</p>
{table(["Knob", "Control", "Range", "Bar"], [
        ["K1", "Envelope amount", "Middle: off. Right: opens the filter at each note. Left: closes it.", "From the middle"],
        ["K2", "-", "Dark", "-"],
        ["K3", "Envelope decay", "20 ms to 1.3 s", "From the left"],
        ["K4", "LFO depth", "0: off", "From the left"],
        ["K5", "LFO shape", "Triangle, ramp, square", "One pad: 17, 20 or 24"],
        ["K6", "LFO rate", "Free: about 8 s to 1/4 s a cycle. Tempo Sync: 2 bars, 1 bar, 1/2, 1/4, 1/8, 1/16.", "From the left"],
        ["K7", "Low-pass filter (Stock K7)", "As on the Stock page", "-"],
        ["K8", "Resonance (Stock K8)", "As on the Stock page", "-"]])}
<p>The envelope starts again at each note. The LFO runs all the time; notes do not restart it. The filter cannot go past its
fully open or fully closed point.</p>
{figure(editor("filter", width=340), "The Filter page. K1 is shown; K2 is dark; K7 and K8 are the Stock filter knobs, in the track's colour.")}
<h3>Filter settings</h3>
{how_to_open(28)}
{table(["Pad", "Setting", "Light"], [
        ["17", "LFO rate: Free or Tempo Sync", "Blue: Tempo Sync. White: Free."]])}
<p>K1 and K3-K6 can use a lane (chapter 11). K7 and K8 record on their own Stock lanes.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 14</div><h2>The Pitch page</h2>
<p class="use">Use it for kick drops, zaps and vibrato.</p>
<p>Pad 29. An envelope and an LFO move the track's pitch. K1 is the Stock pitch knob, with the same value and automation.
The envelope and the LFO move the pitch from where K1 puts it.</p>
{table(["Knob", "Control", "Range", "Bar"], [
        ["K1", "Pitch (Stock K1)", "As on the Stock page", "From the middle"],
        ["K2", "Envelope amount", "Middle: off. Right: up, left: down, up to about 2 octaves.", "From the middle"],
        ["K3", "Envelope length", "5 ms to 4 s", "From the left"],
        ["K4", "Envelope shape", "Fast drop, straight drop, rise, bounce", "One pad: 17, 19, 22 or 24"],
        ["K5", "LFO depth", "0: off. Up to about 1 octave.", "From the left"],
        ["K6", "LFO shape", "Triangle, ramp, square", "One pad: 17, 20 or 24"],
        ["K7", "LFO rate", "As the Filter LFO rate (chapter 13)", "From the left"],
        ["K8", "-", "Dark", "-"]])}
<p>The envelope starts again at each note and ends after its length. Then the pitch is back at K1's value. With the rise shape,
the pitch goes up during the length and drops back at its end. The LFO runs all the time; notes do not restart it.</p>
{figure(editor("pitch"), "The Pitch page. K1 is shown; K8 is dark.")}
<h3>Pitch settings</h3>
{how_to_open(29)}
{table(["Pad", "Setting", "Light"], [
        ["17", "LFO rate: Free or Tempo Sync", "Amber: Tempo Sync. White: Free."]])}
<p>K2-K7 can use a lane (chapter 11). K1 records on its own Stock lane.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 15</div><h2>The Extras page</h2>
<p>Pad 30. Ring modulation gives the track a metallic or robotic sound. Scan moves the start of each note through the sample.</p>
{table(["Knob", "Control", "Range"], [
        ["K1", "Ring Mod amount", "0: off"],
        ["K2", "Ring Mod frequency", f"Low to high. {SH} + turn: fine steps, 16 to one normal step. A fine turn is not recorded."],
        ["K3", "Scan depth", "0: off. Full: the start moves up to most of the way to the sample's end."],
        ["K4", "Scan rate", "As the Filter LFO rate (chapter 13)"],
        ["K5-K8", "-", "Dark"]])}
<p>Scan: a slow wave moves the start of each note further into the sample and back again. The wave starts from the sample start that K2 on the
Stock page sets, and never goes before it. The wave runs all the time; notes do not restart it. On a Granular track, Scan moves Position the same way, so
the grains move through the sample. This is not Granular's own Scan (K4 on the Granular page), which moves the playhead during a note.</p>
{figure(editor("extras"), "The Extras page. K1 is shown; K2-K4 are purple; K5-K8 are dark. Pad 31 is dark.")}
{how_to_open(30)}
{table(["Pad in Settings", "Setting", "Light"], [
        ["17", "Ring Mod before or after the filter", "Purple: before the filter. White: after the filter (default)."],
        ["18", "Scan rate: Free or Tempo Sync", "Purple: Tempo Sync. White: Free (default)."]])}
<p>K1-K4 can use a lane (chapter 11).</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 16</div><h2>Sample Mode</h2>
<p class="use">Use it to fit a loop or a break to the tempo, and to set how a sample plays.</p>
<p>Press {key('Sample')} two times to open Sample Mode. It shows the selected track's sample settings.</p>
<p>A sample in One Shot or Gated mode fades out at its end, as normal. A looped sample plays through its loop point
with no drop in level.</p>
<h3>Pitch</h3>
<p>In Sample Mode, hold {CL} and tap pad 1 or 2: the track's pitch goes back to the sample's own pitch.</p>
{figure(sample_mode(callouts=[(8, "Pad 9: stretch", "L"), (12, "Pad 13: 1 bar", "R"), (16, "Pad 17: Granular", "L")]),
        "Sample Mode: stretch on (pad 9), the whole sample (pad 10), 1 bar chosen (pad 13), Granular off (pad 17). "
        "Only the Rhythm Plus pads are drawn lit.")}
<h3>Time stretch</h3>
<p>Pads 9-16 change the length of the selected track's sample without a change to its pitch. The length follows the tempo.
Pads 1 and 2 and the pitch knob change only the pitch.</p>
{table(["Pad", "What it does"], [
        ["9", "Stretch on or off. Green: on. Red: off (the same red as Granular off). When off, the length stays half bright for the next time you turn stretch on. If no length is kept, stretch starts in Follow."],
        ["10", "What fits the length. White: the whole sample. K2 and K3 then choose the part that plays, and it stays in time. Amber: the part from the start (K2) to the end (K3) fills the length."],
        ["11-16", "The sample lasts 1/4, 1/2, 1, 2, 4 or 8 bars, and stretch turns on. Tap the bright length again for Follow."],
        ["17", "Granular on or off, as in the Track Parameter Editor. Green: on. Red: off. Granular on turns stretch off; pad 9 turns it back."],
        ["18", "Granular's mode, as in its settings. White: Triggered. Amber: Textured. Set it before or after Granular is on."],
        ["19", "Retrigger, shown with Textured: bright on, dim off. On: each note starts the texture again."],
        ["20", "Scan length, as in Granular's settings (pad 20 there). White: the track's sample. Amber: each sample."]])}
<p>Follow (no length pad bright): the sample plays at its own speed at the tempo of the moment that Follow starts. When the tempo
changes later, the sample stretches with it. The chosen length is bright and the other lengths are dim. A dim red pad is a length that the sample cannot reach: it
would have to play more than 4 times slower or faster. The pads show this as soon as you choose the sample. A flipped step's sample gets the same length.
In Loop mode the stretched sample loops; in One Shot mode it plays
one time; in Gated mode it stops at the end of the note. Each track keeps its own settings, and the project saves them.</p>
"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 16, continued</div><h2>Stretch while playing, and Granular tracks</h2>
<h3>Stretch while the sample plays</h3>
<p>You can turn stretch on and off while the sample plays. On: the sound goes on from where it is. Off: it goes on at the sample's own
speed to the end of the note; the next note plays without stretch. Each change fades over about 5 ms, so it does not click.</p>
<h3>Sample Mode on a Granular track</h3>
<p>On a Granular track, pads 11-16 set Scan: the playhead moves through the part from K2 to K3 in that length, in time with the
tempo. Tap the bright pad again and Scan goes back to its value from before. The sweeps stay in time, also when the tempo changes:
each sweep ends on a whole number of its lengths, counted from bar 1. If you tap a pad part way through, the sweep ends at the next
of these points, or at the one after it when less than half the length is left. When each note restarts the playhead (Triggered,
or Retrigger on), each note plays one sweep. If you turn Scan, no length pad is chosen. The Scan length is kept apart from the
stretch length: it stays when you turn Granular off and on again, and the project saves it. On a Granular track, pad 9 is red
and pad 10 is dark. While Slice is on, pads 11-16 are dim red.</p>
<p>Pad 20 picks which sample sets the sweep's speed. White: the track's sample, the one chosen in Sample View. A flipped step's sample then moves at the same
speed, so a shorter one plays through more than once in the length and a longer one is cut off at its end. Amber: each sample.
Every note's own sample, flipped or not, moves through its part once in the length.</p>
<p>In One Shot mode, a Granular note plays until the playhead has moved through the part one time. If the sample at its own
speed plays longer, the note lasts that long. Then the grains fade out, and no new grains start until the next note.</p>
<p>Scan starts in the middle, so the playhead stays still. Turn Scan back to the middle and the playhead goes back to the start of
the part, unless Freeze is on. The middle is Scan 63 to 65, with any fine setting. The slower the Scan, the longer a One Shot
note: near the middle a sweep through a short drum takes minutes.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 17</div><h2>Resetting knobs and tracks</h2>
<p class="use">Use it to start a sound again from the defaults without losing your steps.</p>
<h3>One knob</h3>
{table(["Do this", "Result"], [
        [f"{CL} + turn the knob right until it stops", "The value goes back to its default. The knob light turns blue."],
        [f"{CL} + turn the knob left until it stops", "The knob's automation is deleted. The knob light turns red."]])}
<h3>A whole page</h3>
{figure(editor("clear", held=(55,)), f"{CL} held (yellow ring): the page pads 26-30 are dim red.")}
{table(["Do this", "Result"], [
        [f"Hold {CL}", "The page pads 26-30 turn dim red."],
        [f"{CL} + tap a page pad", "That page goes back to its defaults, and its automation in the current pattern is deleted. The pad flashes red three times."],
        [f"Let go of {CL}", "The page pads show their colours again."]])}
{table(["Page pad", "What goes back to its default"], [
        ["26 Stock", "The eight knobs, the fine values too. Lanes that other pages use are kept."],
        ["27 Granular", "The knobs of both knob pages and their fine values; Retrigger, Freeze, Bounce, Pitch Set and Scan length. On or off, the mode and the lanes stay."],
        ["28 Filter", "The five Filter controls; the LFO rate to Free."],
        ["29 Pitch", "The six Pitch controls; the LFO rate to Free."],
        ["30 Extras", "Ring Mod amount 0, frequency to the middle, after the filter. Scan depth 0, rate to its default, Free."]])}
<p>This works on the selected track only. It does not change the sample, the mixer or the FX sends.</p>
"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 17, continued</div><h2>The whole track: wipe</h2>
<p>Hold {CL} and press a track button: it turns red. Let go of the button and press it again, with {CL} still held: the track's
sound goes back to the unit's defaults (three red flashes). Your beat stays. To cancel, let go of {CL}, or press another button or a
pad. Use it to start a track again with a clean sound. To go back to the last save, load the project again.</p>
{table(["Part of the track", "After the wipe"], [
        ["The 8 knobs and their fine values", "Their defaults"],
        ["Level, pan, reverb send, delay send", "100, centre, 0, 0"],
        ["Side-chain", "Its defaults"],
        ["Play mode, reverse, choke, slices", "One Shot; reverse and choke off; the slice settings at their defaults"],
        ["Granular", "Off; its knobs and settings at their defaults"],
        ["Filter, Pitch, Extras", "Their defaults"],
        ["Lanes of the other pages", "Free"],
        ["Time stretch", "Off; the whole sample fits"],
        ["Automation", "Deleted in all 8 patterns of the track"],
        ["The sample, the steps (with velocity, gate and probability), sample flips, pattern settings", "Kept"],
        ["The other tracks", "Not changed"]])}"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 18</div><h2>Grid FX sends</h2>
<p>Grid FX changes the whole mix. The sends let you keep some tracks out of it: a kick that stays clean while the rest of the
mix stutters, for example. Each track has its own send.</p>
<h3>The sends page</h3>
{table(["Do this", "Result"], [
        ["Mixer or Grid FX: press ▼ to the pan knobs, then ▼ again", "The sends page. The knob lights show each track's send."],
        ["Turn a knob", "That track's send. Full: the track goes through Grid FX, as normal. Down to 0: Grid FX does not touch the track."],
        [f"{CL} + turn a knob until it stops", "With an FX track: left sets the send to 0, right sets it to full. Without an FX track: the send goes back to full."],
        ["Press ▲", "Back to the pan knobs."],
        ["Grid FX, an effect held: press ▲ (lit in the effect's colour)", "That effect's settings. ▼ (lit amber) goes straight back to the sends."]])}
<p>The pads stay as they are: on the Mixer they mute tracks, on Grid FX they play the effects. So you can hold a Grid FX pad and
turn the sends at the same time.</p>
<h3>What a send changes</h3>
<p>A send splits the track's sound: the part you send goes through Grid FX, the rest goes around it. The level, pan, mute, side chain
and Master Filter still work on all of the track. The shared delay and reverb returns go through Grid FX by default. Hold {SH} on the sends page: K1 is the reverb return, K2 the delay return and K3 the Grid FX blend, the same controls as page 2 of the FX track (chapter 19). Let go of {SH} for the sends.</p>
<p>While a Beat Repeat plays, a send that you turn up waits until the repeat ends: the track keeps playing live. The next Beat
Repeat records it. A send that you turn down works at once.</p>
<p>The project saves the sends. A new project, or one from an earlier firmware, has every send at full.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 19</div><h2>The FX track</h2>
<p>One track can play Grid FX for you. Its steps turn the Grid FX pads on and off, so the effects play in time with the pattern,
on the whole mix, as on the Grid FX View. The FX track does not play its own samples. Any track can be the FX track, also one
with steps: the steps are shared, and its own samples come back when it is a normal track again.</p>
<h3>Make a track the FX track</h3>
{table(["Do this", "Result"], [
        [f"Select a track, press {key('Sample')} two times (Sample Mode), tap pad 8", "The track is the FX track. Pad 8 and the track's button are amber. On the other views the Mixer button is amber: bright while the FX track is selected, dim otherwise."],
        ["Tap pad 8 again", "The track is a normal track again: its own samples, flips and knobs. Pad 8 is dim amber. Tap pad 8 again later and its effects are back."],
        ["Hold Clear", "Pad 8 is dim red."],
        ["Hold Clear, tap pad 8", "The track is cleared: its steps, automation and effects in all 8 patterns. Pad 8 flashes red three times. The FX track stays on or off."],
        ["Another track is the FX track", "Pad 8 is dark and does nothing. Only one track at a time can be the FX track."]])}
<h3>The FX track's view</h3>
<p>In the FX track's Sample View, pads 1-16 are its steps and pads 17-32 are the 16 Grid FX pads, in the Grid FX View's colours
(bright while they play). The steps work as on any track: gate, microsteps, probability, pattern length, speed, play modes,
Pattern Mutate and Step Mutate.</p>
{table(["Do this", "Result"], [
        ["Hold Grid FX pads", "They play while you hold them, as on the Grid FX View. A held pad is white. With Latch on (pad 16 of the Grid FX View), a tapped pad stays on and white until you tap it again."],
        ["Hold Grid FX pads, tap a step", "A pink step with those pads. Tap it again with the same pads: the step is deleted."],
        ["Hold a step", "The step is red, and the Grid FX pads that it plays are bright."],
        ["Hold a step, tap Grid FX pads", "Each pad that you tap goes on or off on that step, in place of a pad of the same type. Its last pad off: the step is deleted."],
        ["Tap an empty step", "A blue step: it plays the selected Grid FX pad (the last one that you played, pulsing white)."],
        ["Tap a step", "The step is deleted."],
        ["Record on, play the Grid FX pads", "Pink steps with the pads you played, with their gate lengths. Pads pressed on one step all go on it. A pad played on a step with pads puts the new pad in place of them."]])}
<p>In Sample View and Gate View, pink steps have their own Grid FX pads and blue steps play the selected pad. In Gate View, a
selected step pulses white as normal and keeps its pink or blue colour. Note View and Velocity View are dark and do nothing on the
FX track.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 19</div><h2>The FX track: the arrows, saving and the knobs</h2>
<h3>The arrows</h3>
{table(["Hold", "▼", "▲"], [
        ["A step", "Random on or off: each time, the step plays one of its pads (one of all the pads, when it has none). Bright when on.",
         "Repeat on or off: the step plays the pads of the step before it. Bright when on."],
        ["A Grid FX pad", "Back to the sends (lit amber).", "That pad's settings on the knobs, with its effect type (lit in its colour)."]])}
<p>The settings are the Grid FX View's, with the same values. Let go of all the pads and the knobs are the sends. The Track
Parameter Editor does not open on the FX track.</p>
<h3>Gates</h3>
<p>A step's pads play for the step's gate. The next step does not cut them off: a long gate plays on under the next steps. If a
step inside the gate (a step that the gate lights) has the same pad, the pad plays on; on the first step after the gate, it
starts again.</p>
<p>Each effect type plays one effect at a time. When two steps use the same type, the newer step takes over with no restart (Beat
Repeat goes from 1/16 to 1/4 and keeps playing). When the newer gate ends and the older gate is still on, the older pad comes
back. If the older gate was over when the newer step started, the effect starts again. A step has one pad of each type: when you
record or hold the step, a new pad replaces the pad of the same type.</p>
<h3>Saving</h3>
<p>The steps' effects are saved with the project, apart from the track's own data, so the track's samples and flips do not
change. A project holds up to 47 different pad sets. A set is two or more pads on a step, or Random or Repeat; one pad on a step
needs no set. When all 47 are in use, a step cannot get a new set and keeps what it had. A step that you delete in any view loses
its effects. A pattern copy (Duplicate) copies the steps but not their Grid FX pads. Step Mutate moves the pads with their steps
and automation. Its Sample flip target changes the Grid FX pads, and follows its Pink only or All steps setting.</p>
<h3>The knobs are the sends</h3>
<p>The FX track's K1-K8 are the sends of tracks 1-8, the same values as the sends page (chapter 18). Automate or lock them as on
any track, and the sends follow the steps. A send turned on the sends page with Record on is recorded too, as the FX track's
automation. In the Grid FX view, the pads that the FX track plays are bright.</p>
<p>The track has one set of knob automation: on the FX track it moves the sends, on a normal track the track's own K1-K8. When the
track stops being the FX track, its knobs go back to the values they had before, and the sends page keeps the last sends. The
project saves which track is the FX track.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 19</div><h2>The FX track: page 2</h2>
<p>On the FX track's view, press {DN} to show page 2. Press {UP} to go back to page 1 and the Grid FX pads. {DN} is amber while page 2 shows.
Pads 1-16 are the steps on both pages.</p>
{figure(fx_page2(), "Page 2: K1 (the reverb return) is chosen and uses track 1's lane. The blend uses track 3's lane. Audition is on.")}
{table(["Control", "What it does"], [
        ["K1", "Reverb return into Grid FX. Full: all of it goes through Grid FX; 0: it goes around Grid FX. Green."],
        ["K2", "Delay return into Grid FX, as K1. Pink."],
        ["K3", "Grid FX blend. Full: the effects; 0: no effects. Tracks and returns that go around Grid FX stay as they are. Amber."],
        ["Pads 17-24", "The lanes of the FX track's K1-K8 (the sends of tracks 1-8). Tap one to give it to the chosen control."],
        ["Pad 25", "The control that a lane pad gives a lane to, in its colour. Tap it for the next one: K1, K2, K3."],
        ["Pad 32", "Audition. Green: you hear the Grid FX pads that you hold. Red: you edit with no sound. The steps' effects still play."]])}
<p>K4-K8 and pads 26-31 are dark on page 2. All three controls are full by default.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 19, continued</div><h2>Page 2: automate the controls</h2>
<p>A control with no lane is a setting that the project saves. To automate it, give it one of the FX track's lanes:</p>
<ol><li>Tap pad 25 until it shows the control's colour.</li>
<li>Tap a pad from 17 to 24. The pad is bright in the control's colour: the control now uses that lane.</li>
<li>Automate and lock as on any knob: arm Record and turn, or hold a step and turn.</li>
<li>To give the lane back to its send, tap the bright pad again.</li></ol>
{table(["Lane pad", "Meaning"], [
        ["Bright, the chosen control's colour", "The chosen control's lane. Tap: the lane goes back to its send."],
        ["Dim, another control's colour", "That control's lane. Tap: the chosen control takes it."],
        ["Dim white", "A send. Tap: the chosen control takes it."]])}
<p>A control has one lane at most. While a control has a lane, the lane's knob on page 1 still sets that track's send, but the send is
not automated. When a control takes a lane, the lane's automation stays and moves the control. When a control gives a lane back, the
control keeps its last value.</p>
<p>The automation is in the project, in the FX track's lanes. The project also saves which lanes the controls use.
Hold {CL} and turn a control until it stops: left sets 0, right sets full. With a lane, this also deletes the lane's automation. A track wipe of the FX track gives every lane back and sets the three controls to full.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 20</div><h2>The playhead scrub</h2>
<p class="use">Use it to find a step by ear, or to step through a pattern while you edit it.</p>
<p>Hold {SH} + {PL} for 0.5 s: the scrub opens and stays on until you leave it (see Leave and look). A shorter tap does what
{SH} + {PL} normally does. In the scrub, K1 moves the playhead, K2 sets how fast K1 moves, K3 moves the cue scanner, K4 steps through the cue
timing on pads 18-24 and K5 sets if you hear the steps while playback is stopped. K6-K8 are dark. {SH} pulses green.</p>
{table(["Do this", "Result"], [
        ["Turn K1", "The playhead moves one step for each 2 clicks (K2 changes this), at once: right goes forward, left goes back. It moves through the scene chain that plays. With one scene, it moves through that scene's longest pattern chain. The cue scanner comes back to the playhead."],
        ["Turn K2", "Sets K1's speed: 1 to 8 clicks for each step (default 2). 4 clicks change it by one. Right is faster. For 2 s, pads 17-24 show it in blue: one bright pad for each click. The project saves it."],
        ["Turn K5", "Right: you hear each step that you turn to while playback is stopped; K5 is green (default). Left: no sound; K5 is red. While playback runs, you always hear it."],
        ["Reach the first or last step", "Playback stops on that step. With K5 green, you hear the step. The playhead does not jump to the other end."],
        ["Keep turning past the first or last step", "That step plays again. The playhead stays on it."],
        ["Turn back from the first or last step", "The playhead moves back into the chain. If playback ran before it stopped there, it starts again. A scrub started while stopped stays stopped."],
        [f"Tap {SH} + {PL} in the scrub", "Playback starts from the playhead, also from the first or last step. A tap is shorter than 0.3 s, with no knob turn."],
        [f"Tap {SH} + {PL} before 0.5 s", f"Outside the scrub: what {SH} + {PL} normally does. The scrub does not open."]])}
{figure(scrub(), f"The scrub: K1 green, K2 blue (K1's speed), K3 the scanner, K4 the timing's colour, K5 green (sound on). Pads 17-24 the cue timing (1 bar), pads 25 and 26 hold cues. {SH} and the track buttons are green.")}
"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 20, continued</div><h2>Cues, range and sound</h2>
<h3>Cues</h3>
<p>Pads 25-32 are 8 cues: song steps that you can jump to while the scrub is on. Empty cue pads are dim amber, saved cues
are green. The project saves the cues and the timing.</p>
{table(["Do this", "Result"], [
        ["Tap an empty cue pad", "It saves the scanner's step (or the playhead's) and goes green. The scanner then follows the playhead again."],
        ["Turn K3", "The scanner moves one step for each 2 clicks, with no sound; playback does not change. K3 is bright while the scanner is away."],
        [f"Hold {CL}, turn K3", "The scanner goes back to the playhead and follows it again."],
        ["Tap a step on pads 1-16", "The scanner goes there; the step does not change. Tap the white playhead step and the scanner follows it again. Hold a step with a cue: its slot flashes."],
        ["Tap the amber scanner step", "Punch-in. Playing: a jump there at the next timing point (it blinks until then). Stopped: playback starts there. A hold only shows its cue."],
        ["Tap pads 17-24", "Sets the timing of jumps and held-cue loops: pad 17 at once (white), then 1/32 to 2 bars (default 1 bar). 1 bar = one pass of the selected track's pattern; shorter timings count from its start."],
        ["Turn K4", "Moves the timing along pads 18-24 (4 clicks a step), never to at once. K4 has the chosen pad's colour. It also works during a loop."],
        ["Tap a saved cue while playback runs", "The playhead jumps to the cue at the next point that pads 17-24 set, in time. The pad blinks until then: tap it again to cancel."],
        ["Tap a saved cue while playback is stopped", f"The stop point moves to the cue. Tap {SH} + {PL} to start from there."],
        ["Hold a saved cue while playback runs", "It jumps as a tap does, then goes back to the cue at the end of each timing length while you hold it. At once does not loop. Let go and playback goes on."],
        [f"Hold {CL}, tap a saved cue", f"Deletes the cue. While {CL} is held, saved cues are red."]])}
<h3>The range and the display</h3>
<p>The scrub moves across step pages, patterns and scenes. Only the first and last step stop playback. Pads 1-16 show the
selected track's steps on the scanner's page: the playhead white, the scanner amber, saved cues pulsing green (only in the part of the song that holds them). The scanner follows
forward, reverse and ping-pong patterns (random as forward). A cue past the song end jumps to the last step. A timed jump
takes the place of the step at its point: the old bar's first hit does not play. Every track takes its last automation value.</p>
<h3>Leave and look</h3>
<p>In the scrub, {PL} keeps its normal light. A {SH} + {PL} tap starts playback from the playhead, {PL} starts or stops, and the
track buttons select tracks (no editor opens). With sticky Shift on, {PL} continues as {SH} + {PL} does. To leave, tap {SH} alone (shorter than 0.3 s),
or tap any other button except Record and {CL}: it also does its job. Hold a button, or {SH} + a button, to see its view; let go
and the scrub comes back.</p>
<h3>Sound and effects</h3>
<p>With K5 green, each step that you turn to sounds while playback is stopped, until 120 ms after the last turn.
While you scrub, the FX track plays no effects from its steps, and the {SH} views do not open.</p>"""))

    PR, SR = key("Projects"), key("Sample Rec")
    packs_cells = {i: lit(RED, DIM) for i in (5, 6, 9)}
    packs_cells[2] = lit(WHITE)
    pages.append(page(f"""
<div class="eyebrow">Chapter 21</div><h2>Copying projects and samples</h2>
<p class="use">Use it to try changes on a copy and keep the original, without a computer.</p>
<p>Copy a project or a sample to another slot of the loaded pack. The internal memory is never changed. Stop playback first:
while the unit plays, these pads do nothing.</p>
<h3>A project</h3>
<p>Press {PR} to see the projects. {DU} is white on this page, and green while you hold it. Hold {DU} for every step.</p>
{table(["Do this", "Result"], [
        [f"{DU} + tap a project", "It is the source. Its pad pulses green."],
        [f"{DU} + tap an empty slot", "The project is copied there. The pad pulses green three times. The source is no longer chosen."],
        [f"{DU} + tap a slot that has a project", f"The pad pulses red: the project there will be replaced. Tap it again, with {DU} still held, to copy."],
        [f"{DU} + tap the source again", "The source is no longer chosen."],
        [f"Let go of {DU}", "Nothing is chosen. To copy again, hold {DU} and tap the source again."]])}
<p>The project's Rhythm Plus settings go with it. The project that is loaded is never replaced: its pad shows red. The copy is
the project as it was last saved.</p>
<h3>A sample</h3>
<p>Press {SR}. Pads 1-16 show the samples of the page. {DU} is lit here too. Hold {DU} for every step; the steps are the same as for a project.</p>
{table(["Do this", "Result"], [
        [f"{DU} + tap a sample", "It is the source. Its pad pulses green."],
        [f"{DU} + tap an empty slot", "The sample is copied there and is ready to play. The pad pulses green three times. The source is no longer chosen."],
        [f"{DU} + tap a slot that has a sample", "The pad pulses red. Tap it again to replace that sample."]])}
<p>A pad shows steady red and nothing is copied when the sample memory is full, or while the unit saves or deletes a sample.</p>
<div class="tip"><b>Tip:</b> Step Mutate changes the steps themselves. Copy the project first to keep the original.</div>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 21, continued</div><h2>Deleting a pack</h2>
<p>Press {PR} two times to see the packs. {CL} is white on this page, and red while you hold it. Stop playback first.</p>
{figure(grid(packs_cells, buttons=[("Clear", lit(RED)), ("Projects", lit(WHITE))], held=(55,)),
        f"{CL} held: the packs that can be deleted are dim red. The loaded pack keeps its light.")}
{table(["Do this", "Result"], [
        [f"Hold {CL}", "Every pack that can be deleted turns dim red. Other pads are dark, apart from the loaded pack."],
        [f"{CL} + tap a pack", "It lights and pulses red. Nothing is deleted yet. Tap another pack to choose that one instead."],
        [f"{CL} + tap the same pack again", "The pack is deleted from the SD card, with all its projects and samples. The pad pulses red three times, then goes dark."],
        [f"Let go of {CL}", "Nothing is chosen. The pads show the packs again."]])}
<p>You cannot delete the loaded pack or the internal pack. A deleted pack cannot be brought back on the unit, so keep a backup
of the SD card. The pack's Rhythm Plus settings files move to the RP_AUTO folder, as when you delete a pack with Components.</p>
<h3>Copying a pack</h3>
<p>The unit's own pack copy ({DU} + tap an empty pack slot) also copies the pack's Rhythm Plus settings files.</p>
<h3>USB</h3>
<p>Over USB the unit is a MIDI device only. Easy Start, the USB drive with Novation's links, is not available: button 9 of
Advanced Setup is dark and does nothing.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 22</div><h2>MIDI Thru, Merge and USB merge</h2>
<p class="use">Use it to play other gear from one keyboard through the Rhythm, in time with its clock.</p>
<p>These are in Advanced Setup: hold {SH} while you turn the unit on. The unit saves them when you change them. If it plays, it saves them
when it stops.</p>
<h3>The Thru jack: {DU}</h3>
<p>Press {DU} to go to the next mode. {DU}'s light shows the mode.</p>
{table(["Mode", "Light", "What goes out of the Thru jack"], [
        ["Thru (default)", "Dim red", "A copy of MIDI In. Nothing from the unit."],
        ["Out 2", "Green", "The unit's own MIDI, as from MIDI Out. Nothing from MIDI In."],
        ["Merge", "Yellow", "MIDI In and the unit's own MIDI together."],
        ["Filter", "Blue", "MIDI In, but not the notes and controls on a channel that the unit listens on. Nothing from the unit."]])}
<h3>USB merge: pad 23</h3>
<p>Pad 23 green: MIDI In also goes to the computer over USB. Dim green: off.</p>
<h3>Clock</h3>
<p>With Clock Tx on, the clock, start, stop and continue that come in on MIDI In do not go out of the Thru jack in Merge, or over USB.
The unit sends its own clock. With Clock Rx also on, the unit follows the incoming clock, so its clock has the same tempo. With Clock Tx
off, the incoming clock goes out. In Filter the incoming clock always goes out. So only one clock goes out.</p>
<h3>Example: a keyboard through the unit</h3>
<p>Keyboard to MIDI In, the Thru jack to a second unit. Set the Thru jack to Merge. The second unit gets the keyboard's notes and
this unit's clock. Tracks 1-8 use MIDI channels 1-8 at first, so a keyboard on channel 1 plays track 1 too. To keep the keyboard's notes
off this unit's tracks, turn Note Rx off in Setup ({SH} + {key('Save')}, pad 25), or set the keyboard to a channel that no track uses.
To send no notes from this unit, turn Note Tx off (pad 26). Clock Rx and Clock Tx are pads 31 and 32.</p>
<p>SysEx from MIDI In is not copied.</p>
<div class="tip"><b>Tip:</b> with Merge, set the keyboard to a channel that no track uses, for example 9-15. Then the tracks do not play it,
and Note Rx can stay on.</div>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 23</div><h2>Quantize</h2>
<p class="use">Use it after you record live, to put the hits on the steps.</p>
<p>Press {key('Pattern Settings')} on a track. Tap pad 25. The track's pattern is quantized at once, from its start step to its end
step. It works while the pattern plays and while it is stopped.</p>
{figure(grid({24: lit(GREEN)}, buttons=[("Pattern Settings", lit(WHITE))]),
        "Pattern Settings: pad 25 is green, the colour of Mutate. The other pads are the unit's own Pattern Settings.")}
{table(["A step has", "After a quantize"], [
        ["One hit on microstep 1", "No change."],
        ["One hit on microstep 2 or 3", "The hit moves to microstep 1 of the same step."],
        ["One hit on microstep 4, 5 or 6", "The hit moves to microstep 1 of the next step. If that step is empty, the hit takes its note, velocity, gate, probability and sample flip with it. If that step has a note, it gets a hit on microstep 1."],
        ["Two or more hits (a roll)", "No change."]])}
<p>A late hit on the end step moves to the start step. Steps outside the start and end do not change. On the FX track, the Grid FX
pads of a step move with its hit. Automation stays on its steps.</p>
{table(["Pad 25", "Meaning"], [
        [f'<span class="sw" style="background:{lit(GREEN)}"></span> Green', "Ready."],
        [f'<span class="sw" style="background:{lit(GREEN)}"></span> Green, three flashes', "The pattern is quantized."]])}
<div class="note">Quantize changes the pattern itself. There is no undo. To keep the pattern as it is, duplicate it to an empty
pattern on the Patterns View first.</div>"""))

    pages.append(page(f"""
<div class="eyebrow">Help</div><h2>Problems and fixes</h2>
{table(["Problem", "Fix"], [
        [f"{key('Save')} flashes red and does not save.", f"The project's RP_ file is missing. Restore it from a backup, or use Plus files, Check and Fix, in the app's Backup page. Or hold {CL} and press {key('Save')} two times: the project saves with the default Rhythm Plus settings."],
        ["An internal pack project loses its Granular, Filter, Pitch or Extras settings.", "Put the SD card in before you load and save. The settings go to the RP_INTERNAL folder on the card. With no card the project still saves, but these settings and the Step Mutate settings show their defaults and changes to them are not kept. With the card in again, the settings of the last save with the card come back."],
        ["The app does not find the unit.", "Close Novation Components. Use Chrome or Edge. Connect the unit over USB and turn it on, then press Connect."],
        ["The unit does not start.", "Unplug it from power and hold the power button for 15-30 seconds. Hold Sample Rec + Sample + Note while you turn it on, then install the stable build or the official firmware with the app."],
        ["The unit starts in a strange state after the power went off during a save.", f"Hold {SH} + {CL} while you turn it on: it loads a blank project. Then clear or replace the damaged project."],
        ["A copy or a pack delete does nothing.", "Stop playback first (chapter 21)."],
        ["A sample copy shows steady red.", "The sample memory is full, or the unit is saving or deleting a sample (chapter 21)."],
        ["A keyboard on MIDI In plays this unit's tracks.", "Turn Note Rx off (Setup, pad 25), or set the keyboard to a channel that no track uses (chapter 22)."],
        ["The tempo of a second unit jumps.", "Two clocks reach it. Only one device may send a clock: see Clock in chapter 22."],
        ["A track sounds wrong and you do not know why.", f"{CL} + its track button wipes it to the defaults. Its steps and sample stay (chapter 17)."]], "help")}
<p>Before you install a new build, back up the SD card. To go back, install the stable build or the official firmware with the app.</p>"""))

    spans = {}
    for i, body in enumerate(pages, 1):
        for m in re.finditer(r'class="eyebrow">(?:Chapter (\d+)|Tutorial (\d+)|(Start here|Glossary|Help))', body):
            n = m[1] or (m[2] and "T" + m[2]) or m[3][0]
            a, b = spans.get(n, (i, i))
            spans[n] = (min(a, i), max(b, i))
    pages[0] = re.sub(r"@(\d+|T\d|[SGH])@", lambda m: "%d" % spans[m[1]][0] if len(set(spans[m[1]])) == 1 else "%d-%d" % spans[m[1]],
                      pages[0])
    head = ('<title>Rhythm Plus Manual</title><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@600&'
            'family=Source+Sans+3:wght@400;600&display=swap">')
    html = f'<!doctype html><html lang="en"><head><meta charset="utf-8">{head}<style>{CSS}</style></head><body>{"".join(pages)}</body></html>'
    OUT.write_text(html, encoding="utf-8")
    return OUT


if __name__ == "__main__":
    print(build())
