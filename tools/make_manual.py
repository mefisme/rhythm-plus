"""Writes manual/rhythm_plus_manual.html: Pattern Mutate, Step Mutate, the Track Parameter Editor and Sample mode (A4 pages, pad drawings in the unit's colours).
Print it to PDF with:  chrome --headless --print-to-pdf=manual/rhythm_plus_manual.pdf manual/rhythm_plus_manual.html"""
from html import escape
from pathlib import Path

FIRMWARE = "A276"
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


CUE_RED = "ff2a1a"                                        # pad 26 with Clear held: the dim reset red


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
                marks=marks, buttons=[("Shift", "#2e2e32"), ("Duplicate", lit(GREEN, 0.6))])


def editor(clear=False):
    """the Track Parameter Editor on track 1: the steps, the bar with K5, pad 26 white (or dim red with Clear held)"""
    cells, marks = {}, {}
    c = TRK[0]
    for i in range(16):
        cells[i] = lit(c, FULL if i % 4 == 0 else VDIM)
        marks[i] = str(i + 1)
    for i in range(8):
        cells[16 + i] = lit(c, FULL if i < 5 else VDIM)
        marks[16 + i] = str(17 + i)
    cells[24] = lit(c, 0.2)
    cells[25] = lit(CUE_RED, 0.3) if clear else lit("ffffff")
    for k in range(25, 32):
        marks[k] = str(k + 1)
    knobs = [TRK[0] if k == 4 else None for k in range(8)]
    return grid(cells, rows={0: "Steps", 1: "", 2: "Bar", 3: ""}, marks=marks, knobs=knobs)


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
<h1>Pattern Mutate, Step Mutate<br>and the Track Parameter Editor</h1>
<p>New ways to vary your patterns, a full view of each track's knobs, and time stretch for each track's sample. This manual
shows every control and light.</p></div>
<h3>Contents</h3>
<ul class="toc">
<li><span>1 · Pattern Mutate: overview and quick start</span><span>2</span></li>
<li><span>2 · The Mutate settings, page 1</span><span>3</span></li>
<li><span>3 · The Mutate settings, page 2</span><span>4</span></li>
<li><span>4 · Playing a mutate</span><span>5</span></li>
<li><span>5 · Ending a mutate, scenes and saving</span><span>6</span></li>
<li><span>6 · Pattern Mutate quick reference</span><span>7</span></li>
<li><span>7 · Step Mutate: overview and the settings page</span><span>8</span></li>
<li><span>8 · The Step Mutate targets</span><span>9</span></li>
<li><span>9 · The Track Parameter Editor</span><span>12</span></li>
<li><span>10 · The knobs: view, automate and lock</span><span>13</span></li>
<li><span>11 · Sample mode</span><span>14</span></li>
<li><span>12 · Resetting knobs and tracks</span><span>15-16</span></li>
<li><span>13 · Grid FX sends</span><span>17</span></li>
<li><span>14 · The FX track and Shift controls</span><span>18-21</span></li>
<li><span>15 · The playhead scrub</span><span>22</span></li>
<li><span>16 · Copying projects and samples, deleting packs</span><span>23-24</span></li>
</ul>
<div class="note">The drawings show the pads and buttons of the Circuit Rhythm as a plan, not to scale. The colours are close to the colours
on the unit; on the unit, a dim pad is darker than it is on paper.</div>
<div class="note">Rhythm Plus saves some project settings in a small file next to the project, in the pack's Sessions folder. Its
name starts with RP_, the same number and the project's name: <b>RP_05_MyBeat_…rps</b> goes with <b>05_MyBeat.ncs</b>. When you copy a
project on a computer, copy its RP_ file too. A project copy made on the unit (chapter 16) and a pack copy with Duplicate take the RP_ files with them. If the file is missing, Save flashes red and does not save. Hold {SH} and press Save
to save the project with the default Rhythm Plus settings.</div>""", "cover"))

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
<p>Hold {CL} on the Patterns page. The buttons of the mutated tracks are green, the others dark. {DU} is red when there is a mutate to end.</p>
{figure(patterns_clear(), f"{CL} held: tracks 1, 3 and 6 are mutated.")}
{table(["You do", "Result"], [
        [f"{CL} + a green track button", "That track's mutate ends. Its button flashes red, then goes dark. The track goes back to its chain."],
        [f"{CL} + a dark track button", "Nothing happens. The track is not selected."],
        [f"{CL} + {DU}", f"Every mutate ends. The mutated tracks flash red. This also works on the Mixer, Grid FX, FX and Sidechain pages."],
        [f"{CL} held on the settings page", f"The pads show the Patterns page, so you can see each mutate. {DU} keeps pulsing green: you are still on the settings page. The pads do nothing. {DN} / {UP} show the other page of patterns. {CL} + a track button ends that track's mutate."]])}
<p>On a track page, {CL} + a track button wipes the track (chapter 12).</p>
<h3>Scenes</h3>
<p>A scene keeps the mutate of each track: its seed, the settings that made its list and its chain. So a scene plays the exact
lists that you heard when you saved it, and Live goes on from them.</p>
{table(["On the Mixer page", "Result"], [
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
<div class="eyebrow">Chapter 7</div><h2>Step Mutate: overview and the settings page</h2>
<p>Step Mutate changes the steps of the selected track's pattern: their notes, velocities, gates and more. It changes only the steps
from the pattern's start step to its end step, so it works the same for 16 or 32 steps. Each track has its own settings.</p>
<div class="note">Step Mutate changes the pattern itself. There is no undo. To keep the pattern as it is, duplicate it to an empty
pattern on the Patterns page first, then mutate the copy.</div>
<h3>Quick start</h3>
<ol class="steps">
<li>Open a track's page.</li>
<li>Hold {SH} and tap {DU}. The pattern's steps change places, as the stock Mutate does.</li>
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
        [f'<span class="sw" style="background:{lit(GREEN, 0.4)}"></span> Dim green', f"On a track's page with {SH} held: a tap mutates."],
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
        ["Sample flip", "Plays another sample. Any: one of the 64. Growing: one sample up or down from the step's flip, so the flips spread out over many mutates. Within 8 or 4: near the track's sample in the Sample view. Pink only: only steps that have a flip change. All steps: blue steps can get a flip too."],
        ["Step movement", "All + Anywhere: the stock Mutate's shuffle. Every step from the start to the end gets a new place, empty steps too. Other settings: a changed step changes places with a step up to the Range away. Automation goes with its step."],
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
to the end step, goes back to the stock default. The pad flashes red three times. Your settings and the targets' on or off do not
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
        ["Tap the selected track's button", "The page closes. The track's Note or Sample view shows (the one it had last)."],
        ["Hold the selected track's button", "The track's Note or Sample view shows while you hold it. Let go: the settings page comes back."],
        [f"{CL}, {SH}, Record, {PL}", "As before. The page stays open."],
        ["Hold another button", f"Its first view shows while you hold it ({SH} + hold: its second view). Let go: the settings page comes back."],
        ["Tap another button", "The page closes and the button does its job."]])}
<p>The page opens with Step movement's settings shown. The project saves each track's settings. A project from an earlier firmware opens with the defaults. In the Track Parameter
Editor, {SH} + {DU} mutates but does not open the page.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 9</div><h2>The Track Parameter Editor</h2>
<p>The Track Parameter Editor shows the selected track's eight knobs, the steps of its pattern, and the value of one knob on a bar.</p>
<ol class="steps"><li>Select a track. Tap its track button again to open the Track Parameter Editor.</li>
<li>Turn a knob. The bar shows its value.</li>
<li>Tap the track button again to close the Track Parameter Editor.</li></ol>
{figure(editor(), "The Track Parameter Editor on track 1, with K5 shown on the bar.")}
{table(["Pads", "Name", "What they do"], [
        ["1-16", "Steps", "The steps of the pattern, as on the track page. Hold a step to view or lock its values (chapter 10)."],
        ["17-24", "Bar", "The value of the shown knob."],
        ["25", "Knob pick", "Shows the next knob on the bar, without turning it."],
        ["26", "Reset (white)", f"With {CL} held it is dim red. Tap it to reset the track's knobs (chapter 12)."],
        ["27-32", "-", "Dark. They do nothing."]])}
<h3>Terms</h3>
{table(["Term", "Meaning"], [
        ["Shown knob", "The last knob that you turned, or the knob that you picked with pad 25. Its light is in the track's colour."],
        ["Reset", f"Hold {CL} and turn the knob right until it stops. The value goes back to its default; the knob light turns blue."]])}"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 10</div><h2>The knobs: view, automate and lock</h2>
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
<p>While Record is armed and you turn a knob, the bar is red. While you hold a step with Record armed, the step's pad is red.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 11</div><h2>Sample mode</h2>
<p>Press Samples two times to open Sample mode. It shows the selected track's sample settings.</p>
<p>A sample in One Shot or Gated mode fades out at its end, as on the stock unit. A looped sample plays through its loop point
with no drop in level.</p>
<h3>Pitch</h3>
<p>In Sample mode, hold {CL} and tap pad 1 or 2: the track's pitch goes back to the sample's own pitch.</p>
<h3>Time stretch</h3>
<p>Pads 9-16 change the length of the selected track's sample without a change to its pitch. The length follows the tempo.
Pads 1 and 2 and the pitch knob change only the pitch.</p>
{table(["Pad", "What it does"], [
        ["9", "Stretch on or off. Green: on. Red: off, as Granular's off. Off keeps the length (half bright) for the next on. With no length kept, on starts Follow."],
        ["10", "What fits the length. White: the whole sample. K2 and K3 then choose the part that plays, and it stays in time. Amber: the part from the start (K2) to the end (K3) fills the length."],
        ["11-16", "The sample lasts 1/4, 1/2, 1, 2, 4 or 8 bars, and stretch turns on. The bright length again: Follow."],
        ["17", "Granular on or off, as in the Track Parameter Editor. Green: on. Red: off. Granular on turns stretch off; pad 9 turns it back."],
        ["18", "Granular's mode, as in its settings. White: Triggered. Amber: Textured. Set it before or after Granular is on."],
        ["19", "Retrigger, shown with Textured: bright on, dim off. On: each note starts the texture again."],
        ["20", "Scan length, as in Granular's settings (pad 20 there). White: the track's sample. Amber: each sample."]])}
<p>Follow: no length is bright. The sample plays at its own speed at the tempo when Follow starts, and stretches with later tempo
changes. The chosen length is bright and the other lengths are dim. A dim red pad is a length the track's sample cannot get to: it must play more
than 4 times slower or faster. The pads show this as soon as you choose the sample. A flipped step's sample gets the same length.
In Loop mode the stretched sample loops; in One Shot mode it plays
one time; in Gated mode it stops at the end of the note. Each track keeps its own settings, and the project saves them.</p>
<p>You can turn stretch on and off while the sample plays. On: the sound goes on from where it is. Off: it goes on at the sample's own
speed to the end of the note; the next note plays without stretch. Each change fades over about 5 ms, so it does not click.</p>
<p>On a Granular track, pads 11-16 set Scan, so the playhead moves through the part from K2 to K3 in that length, at the tempo. Tap
the bright pad again: Scan goes back to the value it had before. The sweeps stay on the clock, also when the tempo changes: each
one ends on a multiple of its length, counted from bar 1. A pad tapped part way through starts a sweep that ends on the next
multiple, or on the one after it when less than half the length is left. When notes restart the playhead (Triggered, or Retrigger
on), each note plays one sweep of that length. If you turn Scan, the pad is no longer chosen. The track keeps its
Scan length when Granular is turned off and on, apart from the stretch length, and the project saves it. Pad 9 is red and
pad 10 is dark. While Slice is on, pads 11-16 are dim red.</p>
<p>Pad 20 picks which sample sets the sweep's speed. White: the track's sample, the one chosen in Sample View. A flipped step's sample then moves at the same
speed, so a shorter one plays through more than once in the length and a longer one is cut off at its end. Amber: each sample.
Every note's own sample, flipped or not, moves through its part once in the length.</p>
<p>In One Shot mode, a Granular note plays until the playhead has moved through the part one time. If the sample at its own
speed plays longer, the note lasts that long. Then the grains that play fade out, and no new grains start until the next note.</p>
<p>Scan starts in the middle, so the playhead stays still. Turn Scan back to the middle and the playhead goes back to the start of
the part, unless Freeze is on. The middle is Scan 63 to 65, with any fine setting. The slower the Scan, the longer a One Shot
note: near the middle a sweep through a short drum takes minutes.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 12</div><h2>Resetting knobs and tracks</h2>
<h3>One knob</h3>
{table(["Do this", "Result"], [
        [f"{CL} + turn the knob right until it stops", "The value goes back to its default. The knob light turns blue."],
        [f"{CL} + turn the knob left until it stops", "The knob's automation is deleted. The knob light turns red."]])}
<h3>All eight knobs</h3>
{figure(editor(clear=True), f"{CL} held: pad 26 is dim red.")}
{table(["Do this", "Result"], [
        [f"Hold {CL}", "Pad 26 turns dim red."],
        [f"{CL} + tap pad 26", "The eight knobs go back to their defaults, the fine values too. Their automation in the current pattern is deleted. Pad 26 flashes red three times."],
        [f"Let go of {CL}", "Pad 26 is white again."]])}
<p>This works on the selected track only. It does not change the sample, the mixer or the FX sends.</p>
"""))

    pages.append(page(f"""
<h3>The whole track: wipe</h3>
<p>Hold {CL} and press a track button: it turns red. Let go of the button and press it again, with {CL} still held: the track's
sound goes back to the unit's defaults (three red flashes). Your beat stays. To cancel, let go of {CL}, or press another button or a
pad. Use it to start a track again with a clean sound. To go back to the last save, load the project again.</p>
{table(["Part of the track", "After the wipe"], [
        ["The 8 knobs and their fine values", "Their defaults"],
        ["Level, pan, reverb send, delay send", "100, centre, 0, 0"],
        ["Side-chain", "Its defaults"],
        ["Play mode, reverse, choke, slices", "One Shot; reverse and choke off; the slice settings at their defaults"],
        ["Granular", "Off; its knobs and settings at their defaults"],
        ["Time stretch", "Off; the whole sample fits"],
        ["Automation", "Deleted in all 8 patterns of the track"],
        ["The sample, the steps (with velocity, gate and probability), sample flips, pattern settings", "Kept"],
        ["The other tracks", "Not changed"]])}"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 13</div><h2>Grid FX sends</h2>
<p>Grid FX changes the whole mix. The sends let you keep some tracks out of it: a kick that stays clean while the rest of the
mix stutters, for example. Each track has its own send.</p>
<h3>The sends page</h3>
{table(["Do this", "Result"], [
        ["Mixer or Grid FX: press ▼ to the pan knobs, then ▼ again", "The sends page. The knob lights show each track's send."],
        ["Turn a knob", "That track's send. Full: the track goes through Grid FX, as on the stock unit. Down to 0: Grid FX does not touch the track."],
        [f"{CL} + turn a knob", "On the FX track: left to minimum, right to full, with the stock Clear turn threshold. Without an FX track: the send returns to full."],
        ["Press ▲", "Back to the pan knobs."],
        ["Grid FX, an effect held: press ▲ (lit in the effect's colour)", "That effect's settings. ▼ (lit amber) goes straight back to the sends."]])}
<p>The pads stay as they are: on the Mixer they mute tracks, on Grid FX they play the effects. So you can hold a Grid FX pad and
turn the sends at the same time.</p>
<h3>What a send changes</h3>
<p>A send splits the track's sound: the part you send goes through Grid FX, the rest goes around it. The level, pan, mute, sidechain
and master filter still work on all of the track. The shared delay and reverb returns go through Grid FX by default. Hold {SH} on the sends page: K1 is the reverb return, K2 the delay return and K3 the Grid FX blend, the same controls as page 2 of the FX track (chapter 14). Let go of {SH} for the sends.</p>
<p>While a beat repeat plays, a send that you turn up waits until the repeat ends: the track keeps playing live. The next beat
repeat records it. A send that you turn down works at once.</p>
<p>The project saves the sends. A new project, or one from an earlier firmware, has every send at full.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 14</div><h2>The FX track</h2>
<p>One track can play Grid FX for you. Its steps turn the Grid FX pads on and off, so the effects play in time with the pattern,
on the whole mix, as on the Grid FX page. The FX track does not play its own samples. Any track can be the FX track, also one
with steps: the steps are shared, and its own samples come back when it is a normal track again.</p>
<h3>Make a track the FX track</h3>
{table(["Do this", "Result"], [
        ["Select a track, press Samples two times (Sample mode), tap pad 8", "The track is the FX track. Pad 8 and the track's button are amber. On the other views the Mixer button is amber: bright while the FX track is selected, dim otherwise."],
        ["Tap pad 8 again", "The track is a normal track again: its own samples, flips and knobs. Pad 8 is dim amber. Tap pad 8 again later and its effects are back."],
        ["Hold Clear", "Pad 8 is dim red."],
        ["Hold Clear, tap pad 8", "The track is cleared: its steps, automation and effects in all 8 patterns. Pad 8 flashes red three times. The FX track stays on or off."],
        ["Another track is the FX track", "Pad 8 is dark and does nothing. Only one track at a time can be the FX track."]])}
<h3>The FX track's view</h3>
<p>In the FX track's sample view, pads 1-16 are its steps and pads 17-32 are the 16 Grid FX pads, in the Grid FX page's colours
(bright while they play). The steps work as on any track: gate, microsteps, probability, pattern length, speed, play modes and
the Mutates.</p>
{table(["Do this", "Result"], [
        ["Hold Grid FX pads", "They play while you hold them, as on the Grid FX page. A held pad is white. With Latch on (pad 16 of the Grid FX page), a tapped pad stays on and white until you tap it again."],
        ["Hold Grid FX pads, tap a step", "A pink step with those pads. Tap it again with the same pads: the step is deleted."],
        ["Hold a step", "The step is red, and the Grid FX pads that it plays are bright."],
        ["Hold a step, tap Grid FX pads", "Each pad that you tap goes on or off on that step, in place of a pad of the same type. Its last pad off: the step is deleted."],
        ["Tap an empty step", "A blue step: it plays the selected Grid FX pad (the last one that you played, pulsing white)."],
        ["Tap a step", "The step is deleted."],
        ["Record on, play the Grid FX pads", "Pink steps with the pads you played, with their gate lengths. Pads pressed on one step all go on it. A pad played on a step with pads puts the new pad in place of them."]])}
<p>In Sample and Gate views, pink steps have their own FX assignments; blue steps use the selected pad. Selecting a step in Gate adds the native white pulse without changing its pink/blue color. Note and Velocity are dark and do nothing on the FX track.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 14</div><h2>The FX track: the arrows, saving and the knobs</h2>
<h3>The arrows</h3>
{table(["Hold", "▼", "▲"], [
        ["A step", "Random on or off: each time, the step plays one of its pads (one of all the pads, when it has none). Bright when on.",
         "Repeat on or off: the step plays the pads of the step before it. Bright when on."],
        ["A Grid FX pad", "Back to the sends (lit amber).", "That pad's settings on the knobs, with its effect type (lit in its colour)."]])}
<p>The settings are the Grid FX page's, with the same values. Let go of all the pads and the knobs are the sends. The Track
Parameter Editor does not open on the FX track.</p>
<h3>Gates</h3>
<p>A step's pads play for its gate. A later step does not cut them off: a long gate under the next steps plays together with them. A pad again on a step inside its gate (a step that its gate lights) plays on; on the first step after its gate, it starts again.
One effect type has one engine, so for the same type the newer step takes over, with no restart (Beat Repeat goes from 1/16 to
1/4 and keeps playing). When its gate ends and the older gate still runs, the older pad comes back. If the older gate is over
when the newer step starts, the effect starts again. A step has one pad of each type: a pad of a type that the step has goes in place of it, when you record or hold the step.</p>
<h3>Saving</h3>
<p>The steps' effects are saved with the project, apart from the track's own data, so the track's samples and flips do not
change. A project holds 47 different sets of pads (two or more pads, or random or repeat); one pad on a step needs no set. When
all 47 are in use, a step cannot get a new set and keeps what it had. A step deleted on any view loses its effects. Pattern
copy and duplicate do not carry the separate FX assignments. Step Mutate moves assignments with their steps and automation, including multi-pad sets and random/repeat. Its Sample flip target changes Grid FX pads and respects Pink only / All steps.</p>
<h3>The knobs are the sends</h3>
<p>The FX track's K1-K8 are the sends of tracks 1-8, the same values as the sends page (chapter 13). Automate or lock them as on
any track, and the sends follow the steps. A send turned on the sends page with Record on is recorded too, as the FX track's
automation. In the Grid FX view, the pads that the FX track plays are bright.</p>
<p>The track has one set of knob automation: on the FX track it moves the sends, on a normal track the track's own K1-K8. When the
track stops being the FX track, its knobs go back to the values they had before, and the sends page keeps the last sends. The
project saves which track is the FX track.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 14</div><h2>The FX track: page 2</h2>
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
<div class="eyebrow">Chapter 14, continued</div><h2>Page 2: automate the controls</h2>
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
<div class="eyebrow">Chapter 15</div><h2>The playhead scrub</h2>
<p>Hold <strong>Shift + Play</strong> to scrub with K1. K1 is green. K2 controls sound while stopped: green = on (the default), red = off. K3-K8 are dark and disabled while held.</p>
{table(["Do this", "Result"], [
        ["Turn K1", "Move one step per click: right forward, left backward. The active scene chain sets the range; with one scene, its longest track pattern chain sets the range."],
        ["Reach the first or last step", "Playback stops and holds at that step. With K2 on, the step is auditioned. There is no wrap to the other end."],
        ["Turn outward at an endpoint", "Retrigger that same step: left at the beginning, right at the end. The position stays held."],
        ["Turn inward after a hold", "Move back into the chain and resume if playback was running before the boundary hold. A scrub that started stopped stays stopped."],
        ["Tap Shift + Play", "Explicitly resume from the scrubbed position, including either held endpoint. A tap is under 0.3 seconds, with no knob turn."],
        ["Turn K2 right / left", "Enable / disable stopped audition. Running scrub stays audible. Changing K2 alone does not trigger a Shift + Play tap."],
        ["Release after a turn", "Inside the range, running playback continues from the new place. A boundary hold or stopped transport stays stopped. Preview notes release."],
        ["Hold, then release without a turn", "A tap continues as Shift + Play normally does; a longer hold does nothing."]])}
<h3>The range and the display</h3>
<p>Scrub passes across step pages, patterns and intermediate scenes. Only the beginning and end of the active range hold playback. A single 32-step pattern includes both pages. On a track's step view, the playhead pad is white and the displayed page follows it, including steps 17-32.</p>
<h3>Sound and effects</h3>
<p>Stopped audition uses the native step-preview path: normal sample playback, with no turntable effect or time stretching. With K2 on, each turn can audition the located step, including the first and last steps. Preview notes release when you let go or after about 120 ms without a turn, subject to the sample's play mode.</p>
<p>The FX track plays no sequenced effects while scrub is held, preventing irregular triggers during running scrubs. Shift's alternate pages do not open. Release restores normal knob controls. Ordinary Play starts from the song's start; ordinary playback still loops normally.</p>"""))

    PR, SR = key("Projects"), key("Sample Rec")
    packs_cells = {i: lit(RED, DIM) for i in (5, 6, 9)}
    packs_cells[2] = lit(WHITE)
    pages.append(page(f"""
<div class="eyebrow">Chapter 16</div><h2>Copying projects and samples</h2>
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
<p>A pad shows steady red and nothing is copied when the sample memory is full, or while the unit saves or deletes a sample.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 16, continued</div><h2>Deleting a pack</h2>
<p>Press {PR} two times to see the packs. {CL} is white on this page, and red while you hold it. Stop playback first.</p>
{figure(grid(packs_cells),
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

    head = ('<title>Rhythm Plus Manual</title><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@600&'
            'family=Source+Sans+3:wght@400;600&display=swap">')
    html = f'<!doctype html><html lang="en"><head><meta charset="utf-8">{head}<style>{CSS}</style></head><body>{"".join(pages)}</body></html>'
    OUT.write_text(html, encoding="utf-8")
    return OUT


if __name__ == "__main__":
    print(build())
