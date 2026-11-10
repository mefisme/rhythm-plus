"""The DSP memory ledger of a build (modules/dspmap.py): no two regions share a word, and every data address core 1's program names
(x:/y: absolute, and a #> pointer loaded into an address register) lies in a region of its space.
    python tests/emu_dspmap.py BUILD [BUILD ...]      (BUILD: firmware/<build>)
Prints each core's free words.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE / d) for d in ("modules", "builds", "tests", "remix/tools")]
import rpasm  # noqa: E402
rpasm.use()
os.environ["RH_PSHAPE"] = os.environ["RH_FSHAPE"] = "1"
import dspmap as M  # noqa: E402
import rhdsp  # noqa: E402
import rhdsp1  # noqa: E402

FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAILS.append(name)


def refs(P):
    """core 1's program -> {(space, address): [P addresses]}: x:/y: absolute and #> pointers into r0-r7 ("any" space)"""
    with tempfile.TemporaryDirectory() as t:
        fn = Path(t) / "p.bin"
        fn.write_bytes(b"".join(P.get(a, 0).to_bytes(3, "big") for a in range(0x1000)))
        dis = subprocess.run([rhdsp.TOOL, "dis", str(fn)], capture_output=True, text=True).stdout
    out = {}
    for line in dis.splitlines():
        m = re.match(r"^([0-9a-f]{6}): (?:[0-9a-f]{6} ?)+\s+(\S+)\s*(.*)$", line)
        if not m or int(m.group(1), 16) not in P:
            continue
        a, op, rest = int(m.group(1), 16), m.group(2), m.group(3)
        for sp, v in re.findall(r"\b([xy]):[<>]*\$([0-9a-f]+)", rest):
            if 0x40 <= int(v, 16) < 0x3000:
                out.setdefault((sp, int(v, 16)), []).append(a)
        if op == "move":
            for v in re.findall(r"#>\$([0-9a-f]+),r[0-7]\b", rest):
                if 0x40 <= int(v, 16) < 0x3000:
                    out.setdefault(("any", int(v, 16)), []).append(a)
    return out


def main():
    for build in sys.argv[1:]:
        d = HERE / "firmware" / build
        rep = json.loads((d / "manifest.json").read_text())["report"]
        regs = M.regions(rep)
        bad = M.overlaps(regs)
        # AD007 deliberately probed an unverified bank. Hardware then disproved
        # X3000..3FFF ownership. Keep that historical diagnostic collision visible,
        # never exempt a production allocation or a future diagnostic build.
        if build == "ad007" and rep.get("autobank", {}).get("proof_only"):
            quarantined = [(a,b) for a,b in bad
                           if {a.owner,b.owner} == {
                               "stock: Grid FX runtime workspace (AD007 hardware)",
                               "autobank: opt-in candidate-bank proof"}]
            check("ad007: known Grid FX diagnostic collision quarantined; NOT usable storage", len(quarantined)==1)
            bad = [pair for pair in bad if pair not in quarantined]
        check(f"{build}: no production ownership overlaps ({len(regs)} regions)", not bad,
              [f"core {a.core} {a.space.upper()}:${max(a.start, b.start):X}..: {a.owner} / {b.owner}" for a, b in bad])
        img = bytearray((d / f"rhythmplus-{build.upper()}.bin").read_bytes())
        segs, _ = rhdsp1.parse(rhdsp1.sent(img, rep, "pitchmod"))
        P = {}
        for sp, a, w in segs:
            if sp == "p":
                P.update({a + i: x for i, x in enumerate(w)})
        miss = []
        for (sp, v), at in sorted(refs(P).items(), key=lambda k: k[0][1]):
            spaces = ("x", "y") if sp == "any" else (sp,)
            if not any(r.core == 1 and r.space in spaces and r.start <= v < r.end for r in regs):
                miss.append(f"{sp}:${v:X} (P:${at[0]:X})")
        check(f"{build}: every data address core 1's program names is in a region", not miss, miss[:12])
        for core in (1, 0):
            for sp in ("p", "x", "y"):
                fr = M.free(regs, core, sp)
                print(f"     core {core} {sp.upper()} free: {sum(e - s for s, e in fr)} words: "
                      + ", ".join(f"${s:X}..${e - 1:X}" for s, e in fr if e - s >= 8))
    print("ALL PASS" if not FAILS else f"FAILED: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
