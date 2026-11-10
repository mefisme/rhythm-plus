"""Writes manual/rhythm_plus_manual.html: the Pattern Mutate, Track + and Granular chapters (A4 pages, pad drawings in the unit's colours).
Print it to PDF with:  chrome --headless --print-to-pdf=manual/rhythm_plus_manual.pdf manual/rhythm_plus_manual.html"""
from html import escape
from pathlib import Path

FIRMWARE = "AG026"
OUT = Path(__file__).resolve().parents[1] / "manual" / "rhythm_plus_manual.html"

GRAD = ["ffc866", "ffd966", "fff766", "e5ff66", "c7ff66", "a6ff66", "87ff66", "66ff66"]   # the probability page's colours
TRK = ["ff4e13", "ffff19", "9865ff", "00ffb5", "c63ac6", "3db24f", "1a47ff", "ff4c7b"]    # tracks 1-8
GREEN, RED, WHITE = "66ff66", "ff2a1a", "ffffff"
SKY, LIME, AMBER, GOLD, PINK = "4ab8ff", "9eff59", "ffa020", "ffc859", "ff59c2"   # Pitch page, Granular page, Texture, Pitch Set steps
ON_G, OFF_R = "35df74", "ff3040"                                                  # Granular on / off
ENV = ("Drop", "Fast drop", "Straight drop", "Rise", "Fast rise", "Up and down", "Down and up", "Hold then drop",
       "Overshoot", "Bounce", "Octave steps", "Fifth and octave", "Stairs", "Trill", "Random steps", "Swell")
LFO = ("Triangle", "Sine", "Saw up", "Saw down", "Square", "Narrow pulse", "Stairs", "Random steps", "Smooth random", "Bounce")
OFF = (46, 46, 50)


def lit(hexc, k=1.0):
    """an LED's look at k of full (0..1) on the dark panel"""
    c = [int(hexc[i:i + 2], 16) for i in (0, 2, 4)]
    if k >= 1:
        return "#" + hexc
    k = 0.18 + 0.82 * k
    return "#%02x%02x%02x" % tuple(round(o + (v - o) * k) for v, o in zip(c, OFF))


FULL, DIM, VDIM = 1.0, 0.32, 0.12
PAD, GAP = 38, 7


def grid(cells, cols=None, rows=None, marks=None, knobs=False, buttons=None, notes=None, width=None):
    """an 8 x 4 pad grid. cells: {index 0..31: fill}; marks: {index: 'pulse' | 'ring' | text}; buttons: [(label, fill)]"""
    left, top = 34 if rows else 12, 12
    if knobs:
        top += 46
    if buttons:
        top += 0
    gw = 8 * PAD + 7 * GAP
    w = left + gw + 12
    h = top + 4 * PAD + 3 * GAP + (22 if cols else 10)
    bh = 0
    if buttons:
        bh = 44
        h += bh
    out = [f'<svg class="dev" viewBox="0 0 {w} {h}" width="{width or w}" role="img">',
           f'<rect x="0" y="0" width="{w}" height="{h}" rx="10" fill="#18181b"/>']
    if knobs:
        for k in range(8):
            cx = left + k * (PAD + GAP) + PAD / 2
            fill = knobs[k] if isinstance(knobs, (list, tuple)) else None
            out.append(f'<circle cx="{cx}" cy="26" r="14" fill="#2a2a2e" stroke="{(fill if fill.startswith("#") else lit(fill)) if fill else "#55555c"}" stroke-width="3"/>')
            out.append(f'<line x1="{cx}" y1="26" x2="{cx + 7}" y2="16" stroke="#d8d8de" stroke-width="2" stroke-linecap="round"/>')
            out.append(f'<text x="{cx}" y="52" class="kl">K{k + 1}</text>')
    for i in range(32):
        r, c = divmod(i, 8)
        x, y = left + c * (PAD + GAP), top + r * (PAD + GAP)
        fill = cells.get(i, lit("000000", 0))
        out.append(f'<rect x="{x}" y="{y}" width="{PAD}" height="{PAD}" rx="5" fill="{fill}"/>')
        m = (marks or {}).get(i)
        if m == "pulse":
            out.append(f'<rect x="{x - 3}" y="{y - 3}" width="{PAD + 6}" height="{PAD + 6}" rx="7" fill="none" stroke="#ffffff" '
                       f'stroke-width="2" stroke-dasharray="4 3"/>')
        elif m:
            dark = fill.startswith("#") and sum(int(fill[j:j + 2], 16) for j in (1, 3, 5)) > 360
            out.append(f'<text x="{x + PAD / 2}" y="{y + PAD / 2 + 4}" class="pl" fill="{"#111" if dark else "#eee"}">{escape(m)}</text>')
    if cols:
        for c, t in cols.items():
            out.append(f'<text x="{left + c * (PAD + GAP) + PAD / 2}" y="{top + 4 * PAD + 3 * GAP + 15}" class="cl">{escape(t)}</text>')
    if rows:
        for r, t in rows.items():
            out.append(f'<text x="{left - 8}" y="{top + r * (PAD + GAP) + PAD / 2 + 4}" class="rl">{escape(t)}</text>')
    if buttons:
        y = h - bh + 6
        x = left
        for label, fill in buttons:
            bw = max(52, 8 * len(label) + 18)
            out.append(f'<rect x="{x}" y="{y}" width="{bw}" height="26" rx="5" fill="{fill}" stroke="#55555c"/>')
            dark = sum(int(fill[j:j + 2], 16) for j in (1, 3, 5)) > 360
            out.append(f'<text x="{x + bw / 2}" y="{y + 17}" class="bl" fill="{"#111" if dark else "#eee"}">{escape(label)}</text>')
            x += bw + 8
    out.append("</svg>")
    return "".join(out)


def trackrow(fills, label="Track buttons"):
    """the 8 track buttons as a strip"""
    w = 12 + 8 * PAD + 7 * GAP + 12
    out = [f'<svg class="dev" viewBox="0 0 {w} 46" width="{w}"><rect width="{w}" height="46" rx="10" fill="#18181b"/>']
    for t in range(8):
        x = 12 + t * (PAD + GAP)
        out.append(f'<rect x="{x}" y="10" width="{PAD}" height="16" rx="4" fill="{fills[t]}"/>')
        out.append(f'<text x="{x + PAD / 2}" y="40" class="kl">{t + 1}</text>')
    out.append("</svg>")
    return "".join(out)


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


# ---------------------------------------------------------------- drawings
def mutate_page1():
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
                marks=marks, buttons=[("Up", lit("444448")), ("Down", "#ffffff"), ("Duplicate", lit(GREEN, 0.6))])


def mutate_page2():
    cells = {}
    for r in range(4):
        cells[8 * r + 2] = lit(GRAD[2], DIM)                  # Length 5-8, past Length 4: dim
    meter = [GRAD[7], GRAD[5], GRAD[3], GRAD[1]]
    for r in range(4):
        cells[8 * r + 3] = lit(meter[r], FULL if r >= 2 else DIM)   # Amount: Some
    cells[5], cells[13] = lit(GREEN, FULL), lit(GREEN, DIM)  # Repeats On
    cells[6], cells[14] = lit(GREEN, DIM), lit(GREEN, FULL)  # Keep slot 1 On
    cells[0], cells[8] = lit(GREEN, DIM), lit(GREEN, FULL)   # Live On
    marks = {2: "5", 10: "6", 18: "7", 26: "8"}
    return grid(cells, cols={0: "Live", 2: "Length", 3: "Amount", 4: "Repeats", 5: "Keep 1"}, rows={0: "1", 1: "2", 2: "3", 3: "4"},
                marks=marks, buttons=[("Up", "#ffffff"), ("Down", lit("444448")), ("Duplicate", lit(GREEN, 0.6))])


def patterns_mutated():
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
    return grid(cells, cols={t: f"T{t + 1}" for t in range(8)}, rows={0: "1", 1: "2", 2: "3", 3: "4"}, marks=marks)


def patterns_clear():
    return trackrow([lit(GREEN) if t in (0, 2, 5) else lit("000000", 0) for t in range(8)])


PAGE_COLOURS = {0: "ffffff", 3: SKY, 4: LIME, 5: AMBER}   # pads 26-31 by offset; 27 and 28 dark


def trackplus_cells(page, bar, knob_colour, shown, knob_levels=None):
    """Track + on track 1: the steps, the bar (8 fills 0..1), the page pads with `page` (offset 0..5) open"""
    cells, marks = {}, {}
    c = TRK[0]
    for i in range(16):
        cells[i] = lit(c, FULL if i % 4 == 0 else VDIM)
        marks[i] = str(i + 1)
    for i, f in enumerate(bar):
        cells[16 + i] = lit(c if isinstance(f, (int, float)) else f[0], f if isinstance(f, (int, float)) else f[1]) if f else lit("000000", 0)
        marks[16 + i] = str(17 + i)
    cells[24] = lit(c, 0.2) if page == 0 else lit("000000", 0)
    for k in range(6):
        col = PAGE_COLOURS.get(k)
        cells[25 + k] = lit(col, FULL if k == page else 0.4) if col else lit("000000", 0)
        marks[25 + k] = str(26 + k)
    cells[31] = lit("8c8c8c", 0.45)
    marks.update({24: "25", 31: "32"})
    knobs = [TRK[0] if k == shown else (lit(knob_colour, knob_levels[k]) if knob_levels else None) for k in range(8)]
    return grid(cells, rows={0: "Steps", 1: "", 2: "Bar", 3: "Pages"}, marks=marks, knobs=knobs)


def trackplus():
    return trackplus_cells(0, [FULL] * 5 + [VDIM] * 3, None, 4)


def pitch_page():
    bar = [0, 0, FULL, 0, 0, 0, 0, 0]
    return trackplus_cells(3, bar, SKY, 1, [0.7, 1, 0.3, 0.35, 1, 0.5, 0.2, 0.2])


def granular_page():
    bar = [FULL, FULL, 0.5, 0, 0, 0, 0, 0]
    return trackplus_cells(4, bar, LIME, 0, [1, 0.55, 0.45, 0.3, 0.2, 0.2, 0.55, 0.2])


def granular_settings():
    cells, marks = {}, {}
    c = TRK[0]
    for i in range(16):
        cells[i] = lit(c, FULL if i % 4 == 0 else VDIM)
        marks[i] = str(i + 1)
    row = [lit(ON_G), lit(AMBER), lit(LIME), lit(LIME, DIM), lit(LIME, DIM), "#ffffff", lit("000000", 0), lit("000000", 0)]
    for i, f in enumerate(row):
        cells[16 + i], marks[16 + i] = f, str(17 + i)
    for k in range(6):
        col = PAGE_COLOURS.get(k)
        cells[25 + k] = lit(col, FULL if k == 4 else 0.4) if col else lit("000000", 0)
        marks[25 + k] = str(26 + k)
    cells[31] = lit("8c8c8c", 0.45)
    marks.update({24: "25", 31: "32", 29: "pulse"})
    names = {0: "On", 1: "Mode", 2: "Flow", 3: "Bounce", 4: "Freeze", 5: "Set"}
    return grid(cells, cols=names, rows={0: "Steps", 1: "", 2: "Bar", 3: "Pages"}, marks=marks,
                knobs=[lit(LIME, v) for v in (1, 0.55, 0.45, 0.3, 0.2, 0.2, 0.55, 0.2)])


def pitch_curve():
    """the pitch of one note: the envelope's drop, then the vibrato that fades in"""
    import math
    w, h, x0, y0 = 600, 170, 46, 112
    pts_env = [(x0 + t, y0 - 78 * math.exp(-t / 34)) for t in range(0, 170, 4)]
    pts_vib = [(x0 + t, y0 - 14 * min(1, max(0, (t - 170) / 230)) * math.sin((t - 170) / 14)) for t in range(170, 540, 3)]
    path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts_env + pts_vib)
    out = [f'<svg viewBox="0 0 {w} {h}" width="{w}" role="img"><rect width="{w}" height="{h}" rx="10" fill="#18181b"/>',
           f'<line x1="{x0}" y1="{y0}" x2="{w - 20}" y2="{y0}" stroke="#55555c" stroke-dasharray="4 4"/>',
           f'<text x="{x0 + 176}" y="{y0 - 8}" class="kl" style="text-anchor:start">the note\'s pitch</text>',
           f'<line x1="{x0}" y1="18" x2="{x0}" y2="{h - 22}" stroke="#55555c"/>',
           f'<text x="{x0 - 6}" y="26" class="rl">pitch</text><text x="{w - 22}" y="{h - 8}" class="rl">time</text>',
           f'<path d="{path}" fill="none" stroke="#{SKY}" stroke-width="2.5"/>',
           f'<text x="{x0 + 50}" y="40" class="kl" style="fill:#d8d8de;text-anchor:start">K1 amount, K2 shape</text>',
           f'<line x1="{x0}" y1="{h - 30}" x2="{x0 + 130}" y2="{h - 30}" stroke="#d8d8de"/><text x="{x0 + 65}" y="{h - 14}" class="kl">K3 decay</text>',
           f'<line x1="{x0 + 170}" y1="{h - 30}" x2="{x0 + 400}" y2="{h - 30}" stroke="#d8d8de"/><text x="{x0 + 285}" y="{h - 14}" class="kl">{"Shift + K7 fade-in"}</text>',
           f'<text x="{x0 + 440}" y="80" class="kl" style="fill:#d8d8de">K4 depth, K5 shape, K6 rate</text>', "</svg>"]
    return "".join(out)


def grain_picture():
    """the sample as a strip: Position, the scatter range, the grains, the slice lines"""
    import math
    import random
    rnd = random.Random(5)
    w, h, left, right, top = 600, 214, 20, 580, 96
    out = [f'<svg viewBox="0 0 {w} {h}" width="{w}" role="img"><rect width="{w}" height="{h}" rx="10" fill="#18181b"/>']
    for x in range(left, right, 3):
        a = 6 + 30 * abs(math.sin(x / 23)) * (0.4 + 0.6 * rnd.random()) * (1.6 if (x - left) % 70 < 9 else 1)
        a = min(a, 40)
        out.append(f'<line x1="{x}" y1="{top + 44 - a}" x2="{x}" y2="{top + 44 + a}" stroke="#4a4a52" stroke-width="2"/>')
    for k in range(1, 8):
        x = left + k * (right - left) / 8
        out.append(f'<line x1="{x}" y1="{top - 6}" x2="{x}" y2="{top + 94}" stroke="#8c8c94" stroke-dasharray="3 3"/>')
    pos, spread = 250, 95
    out.append(f'<rect x="{pos - spread}" y="{top}" width="{2 * spread}" height="88" fill="#{LIME}" fill-opacity=".12"/>')
    out.append(f'<line x1="{pos}" y1="{top - 10}" x2="{pos}" y2="{top + 94}" stroke="#{LIME}" stroke-width="2.5"/>')
    for i, gx in enumerate((168, 196, 232, 255, 282, 305, 330)):
        gy = 22 + (i % 3) * 20
        out.append(f'<path d="M{gx},{gy + 16} Q{gx + 13},{gy - 12} {gx + 26},{gy + 16}" fill="#{LIME}" fill-opacity=".85"/>')
        out.append(f'<line x1="{gx + 2}" y1="{gy + 17}" x2="{gx + 2}" y2="{top}" stroke="#{LIME}" stroke-opacity=".35"/>')
    out.append(f'<text x="{pos}" y="{top + 110}" class="kl" style="fill:#{LIME}">Position (K1)</text>')
    out.append(f'<text x="{pos + spread + 8}" y="{top + 14}" class="kl" style="fill:#d8d8de;text-anchor:start">scatter (K5)</text>')
    out.append(f'<text x="{pos + 110}" y="34" class="kl" style="fill:#d8d8de;text-anchor:start">grains: length K2, how many K3</text>')
    out.append(f'<text x="{right}" y="{top - 12}" class="rl">slice lines ({"Shift"} + K5)</text>')
    out.append(f'<text x="{left + 4}" y="{top - 12}" class="kl" style="text-anchor:start">the sample</text></svg>')
    return "".join(out)


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
.cover { display: flex; flex-direction: column; }
.cover .mast { background: #18181b; color: #fff; margin: -15mm -17mm 8mm; padding: 20mm 17mm 12mm; }
.cover .mast .eyebrow { color: #8be0c4; }
.cover .mast p { color: #c9c9d0; font-size: 12pt; }
.toc { list-style: none; padding: 0; margin: 3mm 0; } .toc li { display: flex; justify-content: space-between; border-bottom: 1px dotted var(--line); padding: 1mm 0; }
svg .kl { font: 600 10px var(--head); fill: #b8b8c0; text-anchor: middle; }
svg .cl { font: 600 10px var(--head); fill: #d8d8de; text-anchor: middle; }
svg .rl { font: 600 10px var(--head); fill: #b8b8c0; text-anchor: end; }
svg .pl { font: 700 11px var(--head); text-anchor: middle; }
svg .bl { font: 600 10.5px var(--head); text-anchor: middle; }
"""


def build():
    pages = []
    pages.append(page(f"""
<div class="mast"><div class="eyebrow">Rhythm Plus firmware {FIRMWARE} · Circuit Rhythm</div>
<h1>Pattern Mutate,<br>Track + and Granular</h1>
<p>New ways to vary your patterns, to shape each track, and to turn a sample into grains. This manual shows every control, page and light.</p></div>
<h3>Contents</h3>
<ul class="toc">
<li><span>1 · Pattern Mutate: overview and quick start</span><span>2</span></li>
<li><span>2 · The Mutate settings, page 1</span><span>3</span></li>
<li><span>3 · The Mutate settings, page 2</span><span>4</span></li>
<li><span>4 · Playing a mutate</span><span>5</span></li>
<li><span>5 · Ending a mutate, scenes and saving</span><span>6</span></li>
<li><span>6 · Pattern Mutate quick reference</span><span>7</span></li>
<li><span>7 · Track +: overview and layout</span><span>8</span></li>
<li><span>8 · The Parameter Editor (pad 26)</span><span>9</span></li>
<li><span>9 · The Pitch page (pad 29)</span><span>10</span></li>
<li><span>10 · Pitch page: shapes, rates and sounds</span><span>11</span></li>
<li><span>11 · The FX page (pad 31)</span><span>12</span></li>
<li><span>12 · Granular: what it does</span><span>13</span></li>
<li><span>13 · The Granular page (pad 30)</span><span>14</span></li>
<li><span>14 · Granular: the Shift knobs</span><span>15</span></li>
<li><span>15 · Granular: the settings (hold pad 30)</span><span>16</span></li>
<li><span>16 · Granular: Timing, Slice and Lock</span><span>17</span></li>
<li><span>17 · Granular: sounds to try</span><span>18</span></li>
<li><span>18 · Resetting values and pages</span><span>19</span></li>
</ul>
<div class="note">The drawings show the pads and buttons of the Circuit Rhythm as a plan, not to scale. The colours are close to the colours
on the unit; on the unit, a dim pad is darker than it is on paper.</div>""", "cover"))

    pages.append(page(f"""
<div class="eyebrow">Chapter 1</div><h2>Pattern Mutate: overview and quick start</h2>
<p>A mutate gives each track a new play list: a short run of that track's own patterns, in a random order. The track plays the list
in a loop in place of its chain. Your patterns do not change. You can go back to the chains at any time.</p>
<p>Use it to find new variations of a groove: try a mutate, keep it if you like it, try another if you do not.</p>
<h3>Quick start</h3>
<ol class="steps">
<li>Press {PA} to show the Patterns page. Press {PL}.</li>
<li>Hold {SH} and tap {DU}. Each track gets a new list. The lists start at each track's next pattern end.</li>
<li>Tap again for another mutate. Each tap makes new lists.</li>
<li>To go back to the chains: hold {CL} and tap {DU}.</li>
</ol>
<h3>The Duplicate button</h3>
<p>On the Patterns page, {DU} shows the state of the mutate:</p>
{table(["Duplicate", "Meaning"], [
        ["Its normal light", "No button held: {DU} copies patterns, as before.".replace("{DU}", DU)],
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
<p>Hold {SH} and hold {DU} to open the page. It opens on the Patterns, Mixer, Grid FX, FX and Sidechain pages; the knobs keep their
jobs. Columns 3 to 6 are the settings; each pad in a column is one value. The chosen value is full, the other values are dim.
Column 1 is Live, on both pages. {DN} shows page 2, {UP} shows page 1 again. Hold {PA}, {MI} or FX to look at
that page, or {SH} + a track button to look at that track (with {SH} held, the track buttons show the tracks' colours, the
selected track bright); when you let go, the settings page comes back. A tap goes to that page
and closes the settings.</p>
{figure(mutate_page1(), "Page 1 with Live Off, Length 4, Length type Exact, Pool With steps and When On the tap.")}
{table(["Column", "Setting", "Pads, top to bottom", "What it does"], [
        ["1", "Live", "Off (default) · On", "The same setting on both pages. See chapter 3."],
        ["3", "Length", "1, 2, 3, 4 (5-8 on page 2)", "How many slots a list has, when Length type is Exact or Random. Tap the last pad of the bar."],
        ["4", "Length type", "Same as the chain (default) · Exact · Random", "Same as the chain: a list as long as the track's chain (the Length column is very dim, not used). Exact: always Length slots. Random: 1 to Length slots, new at each mutate."],
        ["5", "Pool", "With steps (default) · All", "With steps: only the patterns that have notes. All: all 8 patterns, also empty ones."],
        ["6", "When", "On the tap (default) · Every chain end", "On the tap: the list starts at the next pattern end and loops. Every chain end: the track waits for its chain's end, then gets a new list each time its list ends."]])}
<h3>The track buttons on this page</h3>
<p>Tap a track button to choose if that track mutates. Bright = it mutates, very dim = it keeps its chain. All tracks are on at first.</p>
<h3>The Length bar</h3>
{table(["Length type", "The bar in column 3"], [["Same as the chain", "Very dim: not used"], ["Exact", "Full up to the Length"],
                                             ["Random", "Dim, with the Length's pad full"]])}"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 3</div><h2>The Mutate settings, page 2</h2>
<p>Press {DN} on the settings page. Column 1 is Live, as on page 1. Column 3 goes on with Length 5-8. Columns 4 to 6 are three more
settings.</p>
{figure(mutate_page2(), "Page 2 with Live On, Amount Some, Repeats On and Keep slot 1 On.")}
{table(["Column", "Setting", "Pads, top to bottom", "What it does"], [
        ["3", "Length", "5, 6, 7, 8", "The Length bar goes on from page 1."],
        ["4", "Amount", "All (default) · Most · Some · A little", "How much of the chain a mutate changes. The meter fills from the bottom up: more light, more change."],
        ["5", "Repeats", "On (default) · Off", "Off: a list never plays the same pattern twice in a row (also not from its last slot back to slot 1). With only one pattern that has notes, it plays that one."],
        ["6", "Keep slot 1", "Off (default) · On", "On: each list starts on the chain's first pattern, a home beat. Only the slots after it change."],
        ["1", "Live", "Off (default) · On", "On: a setting change changes the lists that play, at once. It is the same mutation with the new setting."]])}
<h3>Amount, step by step</h3>
<p>Each slot of a list either keeps the chain's pattern at that place, or gets a random one. For a chain of 4 patterns:</p>
{table(["Amount", "Slots that change", "Example: chain 1 · 2 · 3 · 4"], [
        ["All", "4 of 4", "7 · 6 · 2 · 5"], ["Most", "3 of 4", "5 · 2 · 8 · 6"], ["Some", "2 of 4", "1 · 6 · 3 · 2"],
        ["A little", "1 of 4", "1 · 2 · 7 · 4"]])}
<p>For other lengths the number is rounded, and at least one slot changes. Slots past the end of the chain are always random. With
Keep slot 1 On, Amount counts only the slots after slot 1.</p>
<h3>Live</h3>
<p>Each mutate gives each track a seed. With Live On, a change to Length, Length type, Pool, Amount, Repeats or Keep slot 1 makes
each list again from its seed. Set it back and the list comes back. Tracks that do not mutate keep their lists. Every chain end
starts at once, with no tap.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 4</div><h2>Playing a mutate</h2>
<p>On the Patterns page, each column is a track and each pad is a pattern. A mutated track shows its list:</p>
{figure(patterns_mutated(), "Tracks 1, 3 and 6 are mutated. The other tracks show their chains as before.",
        legend=[(lit(TRK[0], 0.44), "In the list"), (lit(TRK[0], 0.03), "Not in the list (very dark)"),
                (lit(TRK[0]), "The pattern playing (it pulses)")])}
{table(["You do", "Result"], [
        [f"{PL}", "Each mutated track starts on slot 1 of its list."],
        [f"{SH} + {PL}", "Play goes on from where you stopped. Then the list goes on from slot 1."],
        [f"Mutate while stopped", "The mutated tracks show their whole new list. The pad of the old stop point shows again when you play."],
        [f"Tap a pattern pad of a mutated track", "That track's mutate ends. The stock pattern pick plays, as before."],
        [f"{CL} + pad, {DU} + pad", "Clear or copy a pattern, as before. The mutate stays."],
        [f"{SH} held", "The track buttons show their normal {SH} lights. The pads keep showing the lists.".replace("{SH}", SH)]])}
<h3>View Lock</h3>
<p>Hold {SH} and press {PA} to turn View Lock on or off. When you turn it on, the patterns that play at that moment turn white and
stay white.</p>
{table(["With View Lock on", "Result"], [
        [f"{SH} + a pad", "That track's white pad moves to this pattern. The mutate and the chain do not change."],
        ["A pad without {SH}".replace("{SH}", SH), "The track's mutate ends and the chain is picked, as before. The white pads stay."],
        [f"{CL} + a green track button", "The track's mutate ends (chapter 5). The white pads stay."],
        ["View Lock off, then on", "The white pads move to the patterns that play now."]])}"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 5</div><h2>Ending a mutate, scenes and saving</h2>
<h3>See which tracks are mutated</h3>
<p>Hold {CL} on the Patterns page. The track buttons of the mutated tracks are green; the other track buttons are dark. {DU} is red when there is a mutate to end.</p>
{figure(patterns_clear(), f"{CL} held: tracks 1, 3 and 6 are mutated.")}
{table(["You do", "Result"], [
        [f"{CL} + a green track button", "That track's mutate ends. Its button flashes red, then goes dark. The track goes back to its chain."],
        [f"{CL} + a dark track button", "Nothing happens. The track is not selected."],
        [f"{CL} + {DU}", f"Every mutate ends. The mutated tracks flash red. This also works on the Mixer, Grid FX, FX and Sidechain pages."],
        [f"{CL} held on the settings page", f"The pads show the Patterns page, so you can see each mutate. {DU} keeps pulsing green, so you know that you are still on the settings page. The pads do nothing. {DN} / {UP} show the other page of patterns, as on the Patterns page. {CL} + a track button ends that track's mutate."]])}
<p>On a track page, {CL} + a track button is the track reset, as before.</p>
<h3>Scenes</h3>
<p>A scene keeps the mutate of each track: its seed, the settings that made its list and its chain. So a scene plays the exact
lists that you heard when you saved it, and Live goes on from them.</p>
{table(["On the Mixer page", "Result"], [
        [f"{SH} + a scene pad", "Saves the scene with each track's mutate."],
        ["A scene pad", "Plays the scene with its saved lists. Stopped: at once. Playing: at the end of track 1's pattern. The mutate plays until then."],
        [f"{DU} + a scene pad, then another", "Copies the scene, its mutate too."],
        [f"{CL} + a scene pad", "Clears the scene, its mutate too."]])}
<p>A scene saved without a mutate plays its chains: a scene change ends the mutate of the tracks with no list in that scene.</p>
<p>In a scene chain, a track with a mutate is done when it plays the last slot of its list. The chain goes to the next scene when every
track is done. With a scene chain set, {PL} starts on the chain's first scene, with that scene's own lists.</p>
<div class="note">With Pool With steps, a list uses only the patterns that have notes. If you add notes to an empty pattern, or clear
a pattern, a saved list can change.</div>
<h3>Saving</h3>
<p>When you save the project, it keeps the Mutate settings, each track's current mutate and the mutate of each scene. A project
from an earlier firmware opens with the default settings and no mutate.</p>"""))

    ref = [
        [f"{SH} + tap {DU}", "Patterns, Mixer, Grid FX, FX, Sidechain", "Mutate (new lists with the settings)"],
        [f"{SH} + hold {DU}", "Patterns, Mixer, Grid FX, FX, Sidechain", "Open the Mutate settings page"],
        [f"Tap {DU}", "Settings page", "Close the settings page"],
        [f"{SH} + tap {DU}", "Settings page", "Mutate, the page stays open"],
        [f"{DN} / {UP}", "Settings page", "Page 2 / page 1"],
        ["A setting's pad", "Settings page", "Choose that value"],
        ["A track button", "Settings page", "That track mutates or not"],
        [f"{CL} held", "Settings page", "Show the mutate; pads do nothing"],
        [f"{CL} + a track button", "Settings page", "End that track's mutate"],
        [f"{CL} held", "Patterns page", "Mutated tracks' buttons green"],
        [f"{CL} + a green track button", "Patterns page", "End that track's mutate"],
        [f"{CL} + {DU}", "Patterns, Mixer, Grid FX, FX, Sidechain", "End every mutate"],
        ["A pattern pad", "Patterns page", "End that track's mutate, pick the pattern"],
        [f"{SH} + a pad (View Lock on)", "Patterns page", "Move the white pad; the mutate stays"],
        [f"{PL}", "Any page", "Start the lists from slot 1"],
        [f"{SH} + {PL}", "Any page", "Go on from the stop point"],
        [f"{SH} + a scene pad", "Mixer page", "Save the scene with the mutate"],
    ]
    pages.append(page(f"""
<div class="eyebrow">Chapter 6</div><h2>Pattern Mutate quick reference</h2>
{table(["Control", "Where", "Result"], ref)}
<h3>Defaults</h3>
{table(["Setting", "Default"], [["Length", "4"], ["Length type", "Same as the chain"], ["Pool", "With steps"], ["When", "On the tap"],
                              ["Amount", "All"], ["Repeats", "On"], ["Keep slot 1", "Off"], ["Live", "Off"], ["Tracks", "All on"]])}"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 7</div><h2>Track +: overview and layout</h2>
<p>Track + is the track menu. It shows the eight knobs of the selected track on pages: the stock's own parameters, the Pitch page,
the Granular page and the FX page.</p>
<ol class="steps"><li>Select a track. Tap its track button again to open Track +.</li>
<li>Tap a page pad: 26, 29, 30 or 31. Each track keeps its own page.</li>
<li>Turn a knob. The bar shows its value. Tap the track button again to close Track +.</li></ol>
{figure(trackplus(), "Track + on track 1, the Parameter Editor (pad 26) open, K5 shown on the bar.")}
{table(["Pads", "Name", "What they do"], [
        ["1-16", "Steps", "The steps of the pattern, as on the track page. Hold a step to view or lock its values."],
        ["17-24", "Bar", "The value of the shown knob."],
        ["25", "Knob pick", "Shows the page's next knob on the bar, without turning it."],
        ["26", "Parameter Editor (white)", "The stock's eight knobs of the track (chapter 8)."],
        ["29", "Pitch (sky blue)", "Pitch envelope, vibrato, random pitch and glide (chapters 9 and 10)."],
        ["30", "Granular (lime)", "The grain engine (chapters 12 to 17)."],
        ["31", "FX (amber)", "Ring modulation and sample-start scan (chapter 11)."],
        ["27, 28", "-", "Dark. They do nothing."],
        ["32", "All", f"With {CL} held: resets all pages (chapter 18)."]])}
<h3>Terms</h3>
{table(["Term", "Meaning"], [
        ["Shown knob", "The last knob that you turned, or the knob that you picked with pad 25. Its light is in the track's colour."],
        ["Reset", f"Hold {CL} and turn the knob right until it stops. The value goes back to its default; the knob light turns blue."]])}
<p>Only the Parameter Editor's knobs can be automated and locked to steps (chapter 8).</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 8</div><h2>The Parameter Editor (pad 26)</h2>
<p>These are the stock's parameters of the track. You can view, edit, automate, lock, reset and delete the automation of all
eight.</p>
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
<p>While Record is armed and you turn a knob, the bar is red. While you hold a step with Record armed, the step's pad is red.</p>
<div class="note">Sample start and Sample length also set the part of the sample that the Granular page uses.</div>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 9</div><h2>The Pitch page (pad 29)</h2>
<p>The Pitch page moves the pitch of each note while it plays. It has four parts: an envelope that bends the pitch at the start of
the note, a vibrato (the LFO), a random jump for each note, and a glide from the last note.</p>
{figure(pitch_curve(), "One note on the Pitch page: the envelope drops the pitch to the note, then the vibrato fades in.")}
{table(["Knob", "Parameter", "What it does", f"{SH} + knob"], [
        ["K1", "Envelope amount", "How far the envelope bends the pitch. Right of the middle: the pitch starts high. Left: it starts low. Middle: off.", "Fine"],
        ["K2", "Envelope shape", "The path of the bend: 16 shapes (chapter 10).", "2nd sweep"],
        ["K3", "Envelope decay", "How long the bend takes. Left: a fast click. Right: a slow sweep.", "Fine"],
        ["K4", "Vibrato depth", "How far the vibrato moves the pitch. Left: off.", "Fine"],
        ["K5", "Vibrato shape", "The wave of the vibrato: 10 shapes (chapter 10).", "2nd sweep"],
        ["K6", "Vibrato rate", "Right of the middle: locked to the tempo. Left: free speed.", "2nd sweep / fine"],
        ["K7", "Random pitch", "Each note starts at a random pitch, up to 12 semitones up or down. Left: off.", "Vibrato fade-in"],
        ["K8", "Glide", "The pitch slides from the last note to the new one, up to about 1 second. Left: off.", "Fine"]])}
<h3>{SH} on this page</h3>
<p>On a shape knob (K2, K5), or on K6 in its synced half, {SH} + turn right goes to the same pad on the second sweep, and {SH} + turn
left goes back. On the other knobs, {SH} + turn moves the value in fine steps.</p>
<p>{SH} + K7 is the vibrato fade-in: at each note the vibrato starts at 0 and grows to the K4 depth, up to 2 seconds. K7 lights tan
while {SH} is held.</p>
<div class="note">The Pitch page's values are kept for each track and saved with the project. They have no automation and no step locks.</div>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 10</div><h2>Pitch page: shapes, rates and sounds</h2>
{figure(pitch_page(), "The Pitch page with K2 shown: the bar lights one pad for each shape. Here, shape 3.")}
<p>A shape knob lights one pad on the bar. Pads 17-24 in the track's colour are shapes 1-8. Pads 17-24 in sky blue are the second
sweep: shapes 9-16. A synced vibrato rate shows the same way: the first sweep is 8 bars to 1/16, the second sweep is the same values as
triplets.</p>
<div class="cols"><div>
{table(["Pad", "Envelope (K2)", ""], [[str(17 + i), ENV[i], ENV[i + 8]] for i in range(8)])}
</div><div>
{table(["Pad", "Vibrato (K5)", ""], [[str(17 + i), LFO[i], LFO[i + 8] if i + 8 < len(LFO) else "-"] for i in range(8)])}
</div></div>
<p>The second column of each table is the second sweep. Vibrato rate (K6) synced, pads 17-24: 8 bars, 4 bars, 2 bars, 1 bar, 1/2,
1/4, 1/8, 1/16.</p>
<h3>Sounds to try</h3>
{table(["Sound", "Settings"], [
        ["Kick with a punch", "K1 far right, K2 drop, K3 a little right of the left end."],
        ["Laser or zap", "K1 right, K2 fast drop, K3 at the middle."],
        ["Rising tom", "K1 left of the middle: the pitch starts low and rises to the note. K2 drop, K3 at a third."],
        ["Slow, singing vibrato", f"K4 at a quarter, K5 sine, K6 at 1/8 synced, {SH} + K7 at the middle."],
        ["Hats that never repeat", "K7 at a quarter: each hit is a little higher or lower."],
        ["Sliding pitch", "K8 at a third and K7 at a quarter: each note slides to its new random pitch."]])}"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 11</div><h2>The FX page (pad 31)</h2>
<p>The FX page adds a ring modulator and a scan that moves the sample's start point.</p>
{table(["Knob", "Parameter", "What it does", f"{SH} + knob"], [
        ["K1", "Ring modulation amount", "How much of the ring sound you hear. Left: off.", "Fine"],
        ["K2", "Ring modulation frequency", "The tone of the ring: low for a wobble, high for metal and bells.", "Fine"],
        ["K3-K6", "-", "Dark.", "-"],
        ["K7", "Scan depth", "How far the sample's start point moves.", "Fine"],
        ["K8", "Scan speed", "Right of the middle: locked to the tempo. Left: free speed.", "2nd sweep / fine"]])}
<h3>How the bar reads</h3>
{table(["Knob type", "The bar"], [
        ["Most knobs", "Fills from the left (pad 17) to the right (pad 24)."],
        ["Knobs with a middle (amounts, rates, Scan)", "Fills from the middle out: right of the middle to the right, left of it to the left."],
        ["Shape knobs, synced rates", "One pad for each value. Track colour: first sweep. Page colour: second sweep."]])}
<div class="note">The FX page's values are kept for each track and saved with the project. They have no automation and no step locks.</div>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 12</div><h2>Granular: what it does</h2>
<p>The Granular page plays the track's sample as many very short pieces called grains. Each grain is a few milliseconds to half a
second long, with a soft fade in and out. Many grains together make a new sound from the sample: a cloud, a drone, a stutter, or a
chopped beat.</p>
{figure(grain_picture(), "The sample, with Position, the scatter range around it, the grains that play, and the slice lines.")}
<p>You choose where the grains come from (Position), how long they are (Size) and how many play (Density). Scan moves Position through
the sample by itself. Scatter adds random changes to each grain. Slice, Lock and Timing turn the cloud into a rhythm.</p>
<h3>Quick start</h3>
<ol class="steps">
<li>Select a track that has a sample. Tap its track button again to open Track +.</li>
<li>Tap pad 30. The Granular page opens and pad 30 lights lime.</li>
<li>Hold pad 30. Pads 17-22 show the settings. Tap pad 17 until it is green: Granular is on.</li>
<li>Still holding pad 30, tap pad 18 for amber: Texture plays all the time while the pattern plays. Let go of pad 30.</li>
<li>Press {PL}. Turn K2 Size, K3 Density and K4 Scan, and listen.</li>
</ol>
<div class="note">After a reset, K4 Scan is a little right of the middle, so Position moves slowly forward. Turn K4 to the middle to
stop it.</div>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 13</div><h2>The Granular page (pad 30)</h2>
{figure(granular_page(), "The Granular page on track 1, with K1 Position shown on the bar.")}
{table(["Knob", "Parameter", "What it does", "Default"], [
        ["K1", "Position", "Where in the sample the grains start. Left: the start of the sample.", "Left"],
        ["K2", "Size", "The length of each grain: 5 ms at the left, 0.5 s at the right.", "Middle"],
        ["K3", "Density", "How many grains play at the same time: 1 to 16. With Timing on: the chance that a step plays a grain.", "40 %"],
        ["K4", "Scan", "Moves Position by itself. Middle: stop. Right: forward. Left: backward. Further from the middle: faster.", "A little right"],
        ["K5", "Position scatter", "Each grain starts at a random place near Position, up to half the sample away.", "Left (off)"],
        ["K6", "Pitch scatter", "Each grain gets a random pitch, up to 12 semitones up or down.", "Left (off)"],
        ["K7", "Edge", "The fades of each grain. Left: short and hard. Middle: smooth. Right: a fast start and a long fade out.", "Middle"],
        ["K8", "Reverse", "The chance that a grain plays backward. Right: all grains.", "Left (off)"]])}
<p>The knob lights show each knob's value in lime. The shown knob is in the track's colour, and the bar shows its value. K4 fills the
bar from the middle out. Pad 25 does nothing on this page.</p>
<p>Position, Scan and Slice work inside the part of the sample that Sample start and Sample length (Parameter Editor K2, K3) set.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 14</div><h2>Granular: the {SH} knobs</h2>
<p>Hold {SH} on the Granular page. K1-K6 show the second set of knobs in lime, and the bar shows the turned knob in lime. K7 and K8 are
dark.</p>
{table(["Knob", "Parameter", "What it does"], [
        [f"{SH} + K1", "Level", "The volume of the grains, in fine steps. Default: the middle."],
        [f"{SH} + K2", "Size scatter", "Each grain is a random amount shorter. Right: up to its whole length."],
        [f"{SH} + K3", "Timing", "Middle: off, Density spaces the grains. Left: the grains come at a fixed time apart, from 0.5 s near the middle to 6 ms at the left. Right: the grains come on the tempo (chapter 16)."],
        [f"{SH} + K4", "Jitter", "Moves each grain earlier or later, up to one gap between grains. It loosens a strict rhythm."],
        [f"{SH} + K5", "Slice", "Left: off. Right: cuts the sample into 2 to 16 equal parts. Each grain starts at the start of a part (chapter 16)."],
        [f"{SH} + K6", "Lock", "Left: each grain is new. Right: the same 16 grains repeat in a loop. Between: some grains change each time round (chapter 16)."]])}
<h3>The bar with {SH} held</h3>
{table(["Knob", "The bar"], [
        [f"{SH} + K3 Timing", "From the middle. On the tempo side, half a pad for each step: 1/2, 1/4, 1/4 triplet, 1/8, 1/8 triplet, 1/16, 1/16 triplet, 1/32."],
        [f"{SH} + K5 Slice", "Half a pad for each part: 4 slices fill 2 pads, 16 slices fill all 8."],
        ["The other knobs", "Fills from the left."]])}
<div class="note">To reset a {SH} knob: hold {CL}, then hold {SH}, then turn the knob right until it stops. Press {CL} first:
{SH} + {CL} changes the metronome.</div>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 15</div><h2>Granular: the settings (hold pad 30)</h2>
<p>Hold pad 30 for a moment. Pads 17-22 show the track's Granular settings. Tap a settings pad while you hold pad 30. Each pad sits
under the knob it works with.</p>
{figure(granular_settings(), "Pad 30 held: Granular on, Texture, Retrigger, Bounce off, Freeze off, Pitch Set Octaves.")}
{table(["Pad", "Setting", "Lights"], [
        ["17", "Granular on or off", f'<span class="sw" style="background:{lit(ON_G)}"></span> green: on · <span class="sw" style="background:{lit(OFF_R)}"></span> red: off. It blinks while it changes.'],
        ["18", "Mode", f'<span class="sw" style="background:#ffffff"></span> white: Triggered · <span class="sw" style="background:{lit(AMBER)}"></span> amber: Texture'],
        ["19", "Flow or Retrigger (Texture only)", f'<span class="sw" style="background:{lit(LIME, DIM)}"></span> dim: Flow · <span class="sw" style="background:{lit(LIME)}"></span> bright: Retrigger'],
        ["20", "Bounce (under K4 Scan)", "Dim: off · bright: on"],
        ["21", "Freeze (under K5)", "Dim: off · bright: on"],
        ["22", "Pitch Set (under K6)", f'Tap to step: <span class="sw" style="background:{lit(LIME, DIM)}"></span> Off · <span class="sw" style="background:#ffffff"></span> Octaves · <span class="sw" style="background:{lit(SKY)}"></span> Fifths · <span class="sw" style="background:{lit(GOLD)}"></span> Minor · <span class="sw" style="background:{lit(PINK)}"></span> Major']])}
{table(["Setting", "What it does"], [
        ["Triggered", "Each note plays grains. The grains follow the note: a One Shot sample stops at its end, Gated and Loop stop at the note's end."],
        ["Texture", f"The grains play all the time while the pattern plays, with no notes. When the pattern stops, they stop with a soft tail. A muted track plays no new grains. While stopped, a pad plays the grains as in Triggered."],
        ["Retrigger", "Each note from the pattern starts the grains again at Position."],
        ["Flow", "Notes do not restart the grains. The texture flows on."],
        ["Bounce", "Scan turns back at each end of the sample, in place of a jump to the other end."],
        ["Freeze", "Holds the sound on one spot: Scan and Position scatter stop, and notes do not restart the grains."],
        ["Pitch Set", "Pitch scatter (K6) picks only the notes of the set: octaves, fifths, a minor chord or a major chord."]])}"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 16</div><h2>Granular: Timing, Slice and Lock</h2>
<h3>Timing ({SH} + K3)</h3>
<p>Right of the middle, each grain starts on a step of the tempo: from one grain each 1/2 note to one each 1/32 note. Density then
sets the chance that a step plays: at the left only a few steps play, at the right every step plays. Low Density can leave a few
steps in a row with no grain, so the sound stops for a moment. Turn Density up to fill the gaps.</p>
<h3>Slice ({SH} + K5)</h3>
<p>Slice cuts the sample into equal parts and makes each grain start at the start of a part. On a drum loop cut to whole bars, the grains
then start on the beat, not between the hits. Slice cuts the sample, not the grains: each grain keeps the length that K2 Size sets. To play one whole
hit for each grain, set Size to about one part.</p>
{table(["With Slice on", "Result"], [
        ["K1 Position", "Jumps from part to part. It does not slide."],
        ["K5 Position scatter", "Each grain starts on a random part."],
        ["K4 Scan", "Steps one part at a time, on the tempo. Middle: stop. Right: forward. Left: backward. Further from the middle: faster, from one part each 1/2 note to one each 1/32 note."]])}
<p>For a 2-bar loop cut into 16 parts, each part is an eighth note. Set Scan to step one part each 1/8 note, and the loop plays back
in order, in time. Then add Position scatter to jump between the parts.</p>
<h3>Lock ({SH} + K6)</h3>
<p>Lock repeats the random choices of the grains: position, pitch, length, timing and reverse. At the right, the same 16 grains play
again and again. In the middle, some grains change each time round, so the pattern changes slowly. Lock needs something random to
repeat: turn up K5, K6, {SH} + K2 or {SH} + K4.</p>
<div class="note">With Timing on the tempo, 16 grains at 1/16 make one bar. Lock at the right then repeats a one-bar pattern. For the
clearest loop, set K4 Scan to the middle.</div>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 17</div><h2>Granular: sounds to try</h2>
<p>Start each sound from a reset Granular page ({CL} + pad 30), with Granular on.</p>
{table(["Sound", "Settings"], [
        ["Soft cloud", "Texture. K2 Size right of the middle, K3 Density at the right, K4 Scan a little right, K5 at a third, K7 Edge at the middle."],
        ["Frozen drone", "Texture, Freeze on. K2 Size at the right, K3 Density at the right. Move K1 Position to choose the spot."],
        ["Shimmer", "As Soft cloud, plus K6 Pitch scatter at a third and Pitch Set Octaves."],
        ["Chord cloud", "As Soft cloud, plus K6 at a half and Pitch Set Major or Minor."],
        ["Stutter", f"Triggered. K2 Size small, K3 Density low, {SH} + K3 Timing at 1/16."],
        ["Chopped beat", f"A drum loop. K4 Scan at the middle. {SH} + K5 Slice at 16. {SH} + K3 Timing at 1/16. K5 at a half. K2 Size about one part."],
        ["Beat replay", f"A drum loop. {SH} + K5 Slice at 16. K4 Scan right, one part each 1/8 note. {SH} + K3 Timing at 1/8. K2 Size about one part."],
        ["Repeating glitch", f"As Chopped beat, plus K6 at a quarter, K8 Reverse at a quarter, and {SH} + K6 Lock at the right."],
        ["Backward wash", "Texture. K4 Scan left of the middle, K8 Reverse at the right, K2 Size at the right, K3 Density at the right."]])}"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 18</div><h2>Resetting values and pages</h2>
<h3>One knob</h3>
{table(["Do this", "Result"], [
        [f"{CL} + turn the knob right until it stops", "The value goes back to its default. The knob light turns blue."],
        [f"{CL} + turn the knob left until it stops", "Parameter Editor only: the knob's automation is deleted; the light turns red."],
        [f"{CL}, then {SH}, + turn right", f"A {SH} knob (Pitch {SH} + K7, the Granular {SH} knobs) goes back to its default."]])}
<p>Press {CL} first: {SH} + {CL} changes the metronome.</p>
<h3>A whole page</h3>
{table(["Do this", "Result"], [
        [f"{CL} + tap pad 26", "The eight stock parameters go back to their defaults, and their automation in the current pattern is deleted."],
        [f"{CL} + tap pad 29 or 31", "All values of the Pitch or FX page go back to their defaults."],
        [f"{CL} + tap pad 30", "All Granular knobs, {SH} knobs, Level, Flow, Bounce, Freeze and Pitch Set go back to their defaults. Granular on or off and the mode stay.".replace("{SH}", SH)],
        [f"{CL} + tap pad 32", "The stock parameters, their automation in the current pattern, and the Pitch and FX pages."]])}
<p>Page resets work on the selected track only. They do not change the sample, the mixer or the FX sends.</p>
<h3>The whole track</h3>
<p>On a track page, {CL} + the track button resets the track as before. It also turns Granular off and resets its page.</p>"""))

    head = ('<title>Rhythm Plus Manual</title><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@600&'
            'family=Source+Sans+3:wght@400;600&display=swap">')
    html = f'<!doctype html><html lang="en"><head><meta charset="utf-8">{head}<style>{CSS}</style></head><body>{"".join(pages)}</body></html>'
    OUT.write_text(html, encoding="utf-8")
    return OUT


if __name__ == "__main__":
    print(build())
