"""fshape loopxf: Circuit Remix's loop crossfade (loopxf v4) in a build's core 1, its words moved to ours.
    python tests/emu_loopxf.py BUILD [BUILD ...]      (BUILD: firmware/<build>)
The refill's two jumps P:$197 / $19F go to XF; XF (P:$534..) and WC (P:$12A..) are Remix's code word for word, only the moved Y
addresses differ; nothing else in the program uses those addresses or TEMP; the regions were the stock's dead code.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE / d) for d in ("modules", "builds", "tests", "remix/tools")]
import rpasm  # noqa: E402
rpasm.use()
import loopxf as XF  # noqa: E402
import rhdsp  # noqa: E402
import rhdsp1  # noqa: E402
import rhdspemu  # noqa: E402

FAILS = []
NAMES = ("XFON", "XR", "XA", "XE", "XS", "XN", "XQ", "WR4", "WS", "WL", "WB")


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAILS.append(name)


def remix_words(consts):
    for k, v in consts.items():
        setattr(XF, k, v)
    return XF.code4()


def main():
    orig = {k: getattr(XF, k) for k in NAMES}
    stock = {}
    for sp, a, w in rhdspemu.segments(1, 0):
        if sp == "p":
            stock.update({a + i: x for i, x in enumerate(w)})
    for build in sys.argv[1:]:
        d = HERE / "firmware" / build
        rep = json.loads((d / "manifest.json").read_text())["report"]
        img = bytearray((d / f"rhythmplus-{build.upper()}.bin").read_bytes())
        fs = rep["fshape"]
        ours = {k: int(v, 16) for k, v in fs["xf_words"].items()}
        ours["XFON"] = int(fs["xfb"], 16)
        segs, _ = rhdsp1.parse(rhdsp1.sent(img, rep, "pitchmod"))
        P = {}
        for sp, a, w in segs:
            if sp == "p":
                P.update({a + i: x for i, x in enumerate(w)})
        xw0, at0 = remix_words(orig)
        xw, at = remix_words(ours)
        remix_words(orig)
        check(f"{build}: P:$197 and P:$19F = jmp XF (${at:x})", P[0x197] == P[0x19F] == 0x0C0000 | at and at == at0, (hex(P[0x197]), hex(P[0x19F])))
        check(f"{build}: XF and WC in the program as Remix's code with the moved words ({len(xw)} words)", all(P[a] == w for a, w in xw.items()))
        amap = {orig[k]: ours[k] for k in NAMES}
        diff = [(hex(a), hex(xw0[a]), hex(xw[a])) for a in xw if xw[a] != xw0[a] and amap.get(xw0[a]) != xw[a]]
        check(f"{build}: XF and WC differ from Remix's only in the moved addresses", not diff and set(xw) == set(xw0), diff[:4])
        dead = [a for a in xw if not (XF.AT <= a < XF.END or XF.WC_AT <= a < XF.WC_END)]
        check(f"{build}: XF in P:${XF.AT:X}..${XF.END - 1:X}, WC in P:${XF.WC_AT:X}..${XF.WC_END - 1:X}", not dead, dead[:3])
        check(f"{build}: those regions were the stock's code from ${XF.WC_FIRST:06X} / ${XF.FIRST:06X}",
              stock[XF.AT] == XF.FIRST and stock[XF.END - 1] == XF.LAST and stock[XF.WC_AT] == XF.WC_FIRST and stock[XF.WC_END - 1] == XF.WC_LAST)
        moved = set(ours[k] for k in NAMES if k != "XFON") | {ours["XFON"]}
        with tempfile.TemporaryDirectory() as t:
            fn = Path(t) / "p.bin"
            fn.write_bytes(b"".join(P.get(a, 0).to_bytes(3, "big") for a in range(0x1000)))
            dis = subprocess.run([rhdsp.TOOL, "dis", str(fn)], capture_output=True, text=True).stdout
        users = {}
        for line in dis.splitlines():
            m = re.match(r"^([0-9a-f]{6}):", line)
            if not m:
                continue
            a = int(m.group(1), 16)
            for x in re.findall(r"\$([0-9a-f]{3,5})\b", line.split(None, 2)[-1] if len(line.split(None, 2)) > 2 else ""):
                v = int(x, 16)
                if v in moved or XF.TEMP <= v < XF.TEMP + XF.N_MAX:
                    users.setdefault(hex(v), set()).add(a)
        outside = {k: sorted(hex(a) for a in v if a not in xw) for k, v in users.items()}
        outside = {k: v for k, v in outside.items() if v}
        check(f"{build}: the moved words (Y:${min(moved):X}..) and TEMP (Y:${XF.TEMP:X}..) used only by XF and WC", users and not outside, (outside, len(users)))
        check(f"{build}: the moved words sit past envelope 4's points, below envelope 5", all(0x1780 + 4 * 64 + 34 <= v < 0x1780 + 5 * 64 for v in moved))
    print("ALL PASS" if not FAILS else f"FAILED: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
