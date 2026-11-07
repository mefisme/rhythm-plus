"""Writes manual/rhythm_plus_manual.html: the Pattern Mutate and Track + chapters (A4 pages, pad drawings in the unit's colours).
Print it to PDF with:  chrome --headless --print-to-pdf=manual/rhythm_plus_manual.pdf manual/rhythm_plus_manual.html"""
from html import escape
from pathlib import Path

FIRMWARE = "A0120"
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
            out.append(f'<circle cx="{cx}" cy="26" r="14" fill="#2a2a2e" stroke="{lit(fill) if fill else "#55555c"}" stroke-width="3"/>')
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
    marks = {2: "1", 10: "2", 18: "3", 26: "4"}
    return grid(cells, cols={2: "Length", 3: "Type", 4: "Pool", 5: "When"}, rows={0: "1", 1: "2", 2: "3", 3: "4"},
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
    marks = {2: "5", 10: "6", 18: "7", 26: "8"}
    return grid(cells, cols={2: "Length", 3: "Amount", 4: "Repeats", 5: "Keep 1"}, rows={0: "1", 1: "2", 2: "3", 3: "4"},
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


def trackplus():
    cells, marks = {}, {}
    c = TRK[0]
    for i in range(16):
        cells[i] = lit(c, FULL if i % 4 == 0 else VDIM)
        marks[i] = str(i + 1)
    for i in range(16, 24):
        cells[i] = lit(c, FULL if i < 21 else VDIM)
    cells[24] = lit(c, 0.2)
    pages = [("ffffff", "26"), ("b8ff3a", "27"), ("3affc0", "28"), ("4ab8ff", "29"), (None, "30"), ("ffb020", "31")]
    for k, (col, n) in enumerate(pages):
        cells[25 + k] = lit(col, FULL if k == 0 else 0.45) if col else lit("000000", 0)
        marks[25 + k] = n
    cells[31] = lit("8c8c8c", 0.45)
    marks.update({24: "25", 31: "32"})
    for i in range(16, 24):
        marks[i] = str(i + 1)
    knobs = [TRK[0] if k == 4 else None for k in range(8)]
    return grid(cells, rows={0: "Steps", 1: "", 2: "Bar", 3: "Pages"}, marks=marks, knobs=knobs)


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
.cover .mast { background: #18181b; color: #fff; margin: -15mm -17mm 12mm; padding: 26mm 17mm 16mm; }
.cover .mast .eyebrow { color: #8be0c4; }
.cover .mast p { color: #c9c9d0; font-size: 12pt; }
.toc { list-style: none; padding: 0; margin: 4mm 0; } .toc li { display: flex; justify-content: space-between; border-bottom: 1px dotted var(--line); padding: 1.6mm 0; }
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
<h1>Pattern Mutate<br>and Track +</h1>
<p>New ways to vary your patterns and to shape each track. This chapter shows every control, page and light.</p></div>
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
<li><span>9 · The extra pages (pads 27-31)</span><span>10-11</span></li>
<li><span>10 · Resetting values and pages</span><span>12</span></li>
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
<li>To go back to the chains: hold {CL} and {SH}, and tap {DU}.</li>
</ol>
<h3>The Duplicate button</h3>
<p>On the Patterns page, {DU} shows the state of the mutate:</p>
{table(["Duplicate", "Meaning"], [
        ["Its normal light", "No button held: {DU} copies patterns, as before.".replace("{DU}", DU)],
        [f'<span class="sw" style="background:{lit(GREEN, 0.4)}"></span> Dim green', f"{SH} is held: a tap mutates."],
        [f'<span class="sw" style="background:{lit(GREEN)}"></span> Full green', f"{SH} + {DU} is down."],
        [f'<span class="sw" style="background:{lit(GREEN, 0.6)}"></span> Green, pulsing', "The Mutate settings page is open."],
        [f'<span class="sw" style="background:{lit(RED)}"></span> Red', f"{CL} and {SH} are held: a tap ends every mutate."]])}
<h3>The settings</h3>
<p>Hold {SH} and hold {DU} for a moment to open the Mutate settings page. Tap {DU} to close it. The settings are for all tracks and
are saved with the project. Chapters 2 and 3 show each setting.</p>
<div class="note">A track's mutate stays until you end it, pick a pattern for that track, or change the scene (see chapter 5).</div>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 2</div><h2>The Mutate settings, page 1</h2>
<p>Hold {SH} and hold {DU} to open the page. Columns 3 to 6 are the settings; each pad in a column is one value. The chosen value is
full, the other values are dim. {DN} shows page 2, {UP} shows page 1 again.</p>
{figure(mutate_page1(), "Page 1 with Length 4, Length type Exact, Pool With steps and When On the tap.")}
{table(["Column", "Setting", "Pads, top to bottom", "What it does"], [
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
<p>Press {DN} on the settings page. Column 3 goes on with Length 5-8. Columns 4 to 6 are three more settings. The greener colours
tell you that you are on page 2.</p>
{figure(mutate_page2(), "Page 2 with Amount Some, Repeats On and Keep slot 1 On.")}
{table(["Column", "Setting", "Pads, top to bottom", "What it does"], [
        ["3", "Length", "5, 6, 7, 8", "The Length bar goes on from page 1."],
        ["4", "Amount", "All (default) · Most · Some · A little", "How much of the chain a mutate changes. The meter fills from the bottom up: more light, more change."],
        ["5", "Repeats", "On (default) · Off", "Off: a list never plays the same pattern twice in a row (also not from its last slot back to slot 1)."],
        ["6", "Keep slot 1", "Off (default) · On", "On: each list starts on the chain's first pattern, a home beat. Only the slots after it change."]])}
<h3>Amount, step by step</h3>
<p>Each slot of a list either keeps the chain's pattern at that place, or gets a random one. For a chain of 4 patterns:</p>
{table(["Amount", "Slots that change", "Example: chain 1 · 2 · 3 · 4"], [
        ["All", "4 of 4", "7 · 6 · 2 · 5"], ["Most", "3 of 4", "5 · 2 · 8 · 6"], ["Some", "2 of 4", "1 · 6 · 3 · 2"],
        ["A little", "1 of 4", "1 · 2 · 7 · 4"]])}
<p>For other lengths the number is rounded, and at least one slot changes. Slots past the end of the chain are always random. With
Keep slot 1 On, Amount counts only the slots after slot 1.</p>
<div class="note">With Repeats Off, a track that has only one pattern with notes still gets a list. It plays that pattern.</div>"""))

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
<p>Hold {CL} on the Patterns page. The track buttons of the mutated tracks are green; the other track buttons are dark.</p>
{figure(patterns_clear(), f"{CL} held: tracks 1, 3 and 6 are mutated.")}
{table(["You do", "Result"], [
        [f"{CL} + a green track button", "That track's mutate ends. Its button flashes red, then goes dark. The track goes back to its chain."],
        [f"{CL} + a dark track button", "Nothing happens. The track is not selected."],
        [f"{CL} + {SH} + {DU}", f"Every mutate ends. {DU} is red while {CL} and {SH} are held. The mutated tracks flash red."],
        [f"{CL} held on the settings page", f"The pads show the Patterns page, so you can see each mutate. {DU} keeps pulsing green, so you know that you are still on the settings page. The pads do nothing. {CL} + a track button ends that track's mutate."]])}
<p>On a track page, {CL} + a track button is the track reset, as before.</p>
<h3>Scenes</h3>
<p>A scene keeps the mutate of each track, so a scene plays the exact lists that you heard when you saved it.</p>
{table(["On the Mixer page", "Result"], [
        [f"{SH} + a scene pad", "Saves the scene with each track's mutate."],
        ["A scene pad", "Plays the scene with its saved lists. Stopped: at once. Playing: when the scene starts."],
        [f"{DU} + a scene pad, then another", "Copies the scene, its mutate too."],
        [f"{CL} + a scene pad", "Clears the scene, its mutate too."]])}
<p>A scene saved without a mutate plays its chains: a scene change ends the mutate of the tracks with no list in that scene.</p>
<h3>Saving</h3>
<p>When you save the project, it keeps the Mutate settings, each track's current mutate and the mutate of each scene. A project
from an earlier firmware opens with the default settings.</p>"""))

    ref = [
        [f"{SH} + tap {DU}", "Patterns page", "Mutate (new lists with the settings)"],
        [f"{SH} + hold {DU}", "Patterns page", "Open the Mutate settings page"],
        [f"Tap {DU}", "Settings page", "Close the settings page"],
        [f"{DN} / {UP}", "Settings page", "Page 2 / page 1"],
        ["A setting's pad", "Settings page", "Choose that value"],
        ["A track button", "Settings page", "That track mutates or not"],
        [f"{CL} held", "Settings page", "Show the mutate; pads do nothing"],
        [f"{CL} + a track button", "Settings page", "End that track's mutate"],
        [f"{CL} held", "Patterns page", "Mutated tracks' buttons green"],
        [f"{CL} + a green track button", "Patterns page", "End that track's mutate"],
        [f"{CL} + {SH} + {DU}", "Patterns page", "End every mutate"],
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
                              ["Amount", "All"], ["Repeats", "On"], ["Keep slot 1", "Off"], ["Tracks", "All on"]])}"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 7</div><h2>Track +: overview and layout</h2>
<p>Track + is the track menu. It shows the eight knobs of the selected track on pages: the stock's own parameters and the extra
parameters that Rhythm Plus adds, such as envelopes, LFOs, movement, glide and ring modulation.</p>
<ol class="steps"><li>Select a track. Tap its track button again to open Track +.</li>
<li>Tap a page pad (26-31) to choose a page. Each track keeps its own page.</li>
<li>Turn a knob. The bar shows its value. Tap the track button again to close Track +.</li></ol>
{figure(trackplus(), "Track + on track 1, the Parameter Editor (pad 26) open, K5 shown on the bar.")}
{table(["Pads", "Name", "What they do"], [
        ["1-16", "Steps", "The steps of the pattern, as on the track page. Hold a step to view or lock its values."],
        ["17-24", "Bar", "The value of the shown knob."],
        ["25", "Knob pick", "Shows the page's next knob on the bar, without turning it."],
        ["26", "Parameter Editor (white)", "The stock's eight knobs of the track."],
        ["27-31", "Extra pages", "27 Filter (lime), 28 Mix (mint), 29 Pitch (sky blue), 30 none (dark), 31 FX (amber)."],
        ["32", "All", f"With {CL} held: resets all pages (chapter 10)."]])}
<h3>Terms</h3>
{table(["Term", "Meaning"], [
        ["Shown knob", "The last knob that you turned, or the knob that you picked with pad 25. Its light is in the track's colour."],
        ["Edit", "Turn the knob to change the value for the whole track."],
        ["Automate", "Arm Record and turn the knob while the pattern plays. The movement is recorded into the steps."],
        ["Lock", "Hold a step, arm Record and turn the knob. The value goes into that step only."],
        ["Reset", f"Hold {CL} and turn the knob right until it stops. The value goes back to its default; the knob light turns blue."],
        ["Delete automation", f"Hold {CL} and turn the knob left until it stops. The knob's automation is deleted; the knob light turns red."]])}"""))

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
        ["Lock", "Arm Record, hold a step, turn the knob. The value goes into the held step, also while the pattern plays."]])}
<p>While Record is armed and you turn a knob, the bar is red. While you hold a step with Record armed, the step's pad is red.</p>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 9</div><h2>The extra pages (pads 27-31)</h2>
<p>The extra parameters are kept for each track and saved with the project. You can view, edit and reset them; they have no
automation and no step locks. Filter K7 and K8 are the stock's low-pass and resonance (white lights): you can automate and lock
them, as on the Parameter Editor.</p>
<p>{SH} on these pages: on a shape knob, or a rate knob in its synced half, {SH} + turn right goes to the same pad on the second
sweep, {SH} + turn left goes back. On the other knobs, {SH} + turn moves the value in fine steps.</p>
<div class="cols"><div>
<h3>Filter (pad 27, lime)</h3>
{table(["Knob", "Parameter", f"{SH} + knob"], [
        ["K1", "Envelope amount (from the middle)", "Fine"], ["K2", "Envelope shape", "2nd sweep"], ["K3", "Envelope decay", "Fine"],
        ["K4", "LFO depth", "Fine"], ["K5", "LFO shape", "2nd sweep"], ["K6", "LFO rate: right = synced, left = free", "2nd sweep / fine"],
        ["K7", "Low-pass (stock)", "Filter type: stock or 24 dB"], ["K8", "Resonance (stock)", "Pitch follow"]])}
</div><div>
<h3>Mix (pad 28, mint)</h3>
{table(["Knob", "Parameter", f"{SH} + knob"], [
        ["K1", "Volume movement depth", "Fine"], ["K2", "Volume movement shape (10 LFO, 6 gates)", "2nd sweep"],
        ["K3", "Volume movement rate: right = synced, left = free", "2nd sweep / fine"], ["K4", "Pan movement depth", "Fine"],
        ["K5", "Move shape (pan and sends)", "2nd sweep"], ["K6", "Move rate: right = synced, left = free, middle = off", "2nd sweep / fine"],
        ["K7", "Reverb send movement (from the middle)", "Fine"], ["K8", "Delay send movement (from the middle)", "Fine"]])}
</div></div>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 9, continued</div><h2>The extra pages (pads 27-31)</h2>
<div class="cols"><div>
<h3>Pitch (pad 29, sky blue)</h3>
{table(["Knob", "Parameter", f"{SH} + knob"], [
        ["K1", "Envelope amount (from the middle)", "Fine"], ["K2", "Envelope shape", "2nd sweep"], ["K3", "Envelope decay", "Fine"],
        ["K4", "LFO depth (vibrato)", "Fine"], ["K5", "LFO shape", "2nd sweep"], ["K6", "LFO rate: right = synced, left = free", "2nd sweep / fine"],
        ["K7", "Random pitch, up to 12 semitones", "LFO fade-in, up to 2 s"], ["K8", "Glide, up to about 1 s", "Fine"]])}
</div><div>
<h3>FX (pad 31, amber)</h3>
{table(["Knob", "Parameter", f"{SH} + knob"], [
        ["K1", "Ring modulation amount", "Fine"], ["K2", "Ring modulation frequency", "Fine"], ["K3-K6", "None (dark)", "-"],
        ["K7", "Scan depth: moves the sample start", "Fine"], ["K8", "Scan speed: right = synced, left = free", "2nd sweep / fine"]])}
<p>Pad 30 has no page; it is dark.</p>
</div></div>"""))

    pages.append(page(f"""
<div class="eyebrow">Chapter 10</div><h2>Resetting values and pages</h2>
<h3>One knob</h3>
{table(["Do this", "Result"], [
        [f"{CL} + turn the knob right until it stops", "The value goes back to its default. The knob light turns blue."],
        [f"{CL} + turn the knob left until it stops", "Parameter Editor (and Filter K7 / K8): the knob's automation is deleted; the light turns red."]])}
<p>To reset the Pitch page's LFO fade-in ({SH} + K7): hold {CL}, then hold {SH}, then turn K7 right. Press {CL} first: {SH} + {CL}
changes the metronome.</p>
<h3>A whole page</h3>
{table(["Do this", "Result"], [
        [f"{CL} + tap pad 26", "The eight stock parameters go back to their defaults, and their automation in the current pattern is deleted."],
        [f"{CL} + tap a page pad (27-31)", "All extra parameters of that page go back to their defaults."],
        [f"{CL} + tap pad 32", "All of the above: the stock parameters, their automation in the current pattern, and the extra parameters of all pages."]])}
<p>Page resets work on the selected track only. They do not change the sample, the mixer or the FX sends. The Filter page's K7 and
K8 (the stock's low-pass and resonance) change only with pad 26 and pad 32, not with pad 27.</p>"""))

    head = ('<title>Rhythm Plus Manual</title><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@600&'
            'family=Source+Sans+3:wght@400;600&display=swap">')
    html = f'<!doctype html><html lang="en"><head><meta charset="utf-8">{head}<style>{CSS}</style></head><body>{"".join(pages)}</body></html>'
    OUT.write_text(html, encoding="utf-8")
    return OUT


if __name__ == "__main__":
    print(build())
