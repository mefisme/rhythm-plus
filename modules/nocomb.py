"""No comb filter in Rhythm Plus (MIT; Circuit Rhythm 5706): the filter types are stock and 24 dB.

The comb (voicefx mode 5, voicefilt type 2) keeps a ring of 256 words a voice at Y:$1800 + $100 v, over pshape's tables and our words;
core 1 has no free 2048 words for it.  strip() (before pitchmod installs, after nocrush.strip()): voicefx without its filter stage (the lite
filter was the comb alone), voicefilt without the comb's tests and tuning (HPIDX = the stock's index), tmenu's filter type bar in 2 zones.
install(): Stock+'s two type computations (value x 3 >> 14, the DSP's word and the K6 LED's colour) -> x 2: stock / 24 dB.
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import voicefilt  # noqa: E402
import voicefx  # noqa: E402

TYPE3 = bytes.fromhex("0321" "4843" "800b")       # movs r1, #3 / muls r0, r1 / lsrs r0, r0, #14 (after c_spval(type))
TYPE2 = bytes.fromhex("0221" "4843" "800b")
_FX, _VF = [None], [None]


def fx_items(shift=0, pre=None, lite=False):
    out = _FX[0](shift, pre, lite)
    assert lite
    a, b = out.index(("label", "filt")), out.index(("label", "drive"))
    return out[:a + 1] + out[b:]


def vf_items():
    L = _VF[0]()
    K = f"move #>${voicefilt.KTYPE:x},r1"

    def cut(start, stop):
        a, b = L.index(start), L.index(stop)
        del L[a:b]
    a = L.index(("label", "hpidx"))
    L[a:L.index(("label", "lpidx"))] = [("label", "hpidx"), "move y:(r7+$b),n5", "rts"]
    a = L.index(("label", "lpidx"))
    assert L[a + 2:a + 6] == [K, "move y:(r1+n1),a", "cmp #>$2,a", ("jcc", "eq", "lp_c")], L[a:a + 6]
    del L[a + 2:a + 6]
    cut(("label", "lp_c"), ("label", "hpsave"))
    a = L.index(("label", "post"))
    assert L[a + 5:a + 8] == [("jcc", "eq", "p24"), "cmp #>$2,a", ("jcc", "eq", "pcomb")], L[a:a + 8]
    del L[a + 6:a + 8]
    cut(("label", "pcomb"), ("label", "scan"))
    return L


def strip():
    import tmenu
    _FX[0], _VF[0] = voicefx.items, voicefilt.items
    voicefx.items, voicefilt.items = fx_items, vf_items
    tmenu.F_SHN[5] = 2


def install(img, report, base_addr=None):
    import rhbuild
    bases = sorted(int(v["base"], 16) - rhbuild.BASE for v in report.values() if isinstance(v, dict) and "base" in v)
    sp = int(report["stockplus"]["base"], 16) - rhbuild.BASE
    end = next((b for b in bases if b > sp), len(img))                  # Stock+'s block: up to the next module's
    hits = []
    at = img.find(TYPE3, sp, end)
    while at >= 0:
        hits.append(at)
        at = img.find(TYPE3, at + 2, end)
    assert len(hits) == 2, [hex(h) for h in hits]
    for h in hits:
        img[h:h + len(TYPE2)] = TYPE2
    report["nocomb"] = dict(types=2, sites=[hex(h + rhbuild.BASE) for h in hits])
    return {}, b""
