"""Circuit Remix's Stock+ (tools/stockplus.py, unchanged) for Rhythm Plus, where Track + chooses the page (MIT; Circuit Rhythm 5706).

stockplus flips a track's page (bit t of its slot's byte 0) on a second press of the selected track's button; in Rhythm Plus that tap opens
Track +, and tmenu.py sets the bits from Track +'s page.  So the flip's store (strb r0, [r5, #0] just before c_spbtn's label bt_p, after
eors r0, r1) becomes a nop; the rest of the button code (Clear + the button = the defaults, Duplicate A -> B = the values copied) stays.
Track +'s pad 28 shows the page, so c_spled's white blink of the track's LEDs (lsls r0, r0, #23; bpl ld_x: bit 8 of the tick) is skipped:
the bpl becomes a b to the same label.

lfodef=True: the LFOs' speeds default to moving, so their depth alone is heard: K3 (the pitch LFO's speed) LFO_DEF[2] (about 5 Hz on
its free half), K8 (the scan's speed) LFO_DEF[7] (1 bar on its synced half).  Patched in stockplus's two default tables: t_def (the
stored form: K8 XOR 8192, as k8sync stores it) and t_defu (the values).  Projects that saved a speed keep it.  lfodef = a dict: those
speeds in place of LFO_DEF's.

Rhythm Plus has no time stretch: c_spdsp writes 0 (off) to the speed word whatever K7 holds, and c_spgrain returns at once.
nocrush=True: no bitcrusher: c_spdsp writes drive type 0 (off) whatever value 10 holds (nocrush.py takes the drive out of core 1).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import stockplus  # noqa: E402

STRB_FLIP, EORS, NOP = 0x7028, 0x4048, 0xBF00             # strb r0, [r5, #0]; eors r0, r1; nop
LSLS23, BPL, B = 0x05C0, 0xD500, 0xE000                   # lsls r0, r0, #23; bpl; b
MOV_R0_R1, MOVS_R0_0, PUSH_R4_LR, BX_LR = 0x4608, 0x2000, 0xB510, 0x4770
CMP_R0_0, BNE = 0x2800, 0xD100
LFO_DEF = {stockplus.K3: 14080, stockplus.K8: 3200}       # K3: 8192 + 46 clicks (4.96 Hz); K8: 8192 - 39 clicks (division 9, 1 bar)


def defaults(lfodef):
    """the 12 values' defaults (stockplus's DEFU8, with lfodef's speeds; a dict: {value: default}, keys may be strings)"""
    d = list(stockplus.DEFU8)
    if lfodef:
        for k, v in (lfodef if isinstance(lfodef, dict) else LFO_DEF).items():
            d[int(k)] = v
    return d


def install(img, report, base_addr, lfodef=False, nocrush=False, **kw):
    import rhbuild
    labels, code = stockplus.install(img, report, base_addr, **kw)
    at = labels["bt_p"] - 2
    o = at - rhbuild.BASE
    assert int.from_bytes(img[o:o + 2], "little") == STRB_FLIP and int.from_bytes(img[o - 2:o], "little") == EORS, "c_spbtn's flip moved"
    img[o:o + 2] = NOP.to_bytes(2, "little")
    report["stockplus"]["no_flip"] = hex(at)
    hw = lambda a: int.from_bytes(img[a - rhbuild.BASE:a - rhbuild.BASE + 2], "little")
    blink = [a for a in range(labels["c_spled"], labels["ld_x"], 2) if hw(a) == LSLS23 and hw(a + 2) & 0xFF80 == BPL
             and a + 2 + 4 + 2 * (hw(a + 2) & 0x7F) == labels["ld_x"]]
    assert len(blink) == 1, "c_spled's blink moved"
    o = blink[0] + 2 - rhbuild.BASE
    img[o:o + 2] = (B | hw(blink[0] + 2) & 0x7F).to_bytes(2, "little")
    report["stockplus"]["no_blink"] = hex(blink[0] + 2)
    if lfodef:
        assert kw.get("v2") and kw.get("k8sync") and kw.get("k3sync"), "lfodef needs v2, k8sync and k3sync"
        t_def = base_addr + 8 * 129
        t_defu = t_def + 2 * stockplus.NPAR + 3 * 4 * 129
        lfo = lfodef if isinstance(lfodef, dict) else LFO_DEF
        for k, v in lfo.items():
            stored = v ^ stockplus.X7 if k == stockplus.K8 else v
            for t, old, new in ((t_def, stockplus.DEF[k], stored), (t_defu, stockplus.DEFU8[k], v)):
                o = t + 2 * k - rhbuild.BASE
                assert int.from_bytes(img[o:o + 2], "little") == old, f"stockplus's default table at {t:#x} moved"
                img[o:o + 2] = new.to_bytes(2, "little")
        report["stockplus"]["lfodef"] = {str(k): v for k, v in lfo.items()}
    if kw.get("v2"):
        for lab, old, new in (("sd_sw", MOV_R0_R1, MOVS_R0_0), ("c_spgrain", PUSH_R4_LR, BX_LR)):
            o = labels[lab] - rhbuild.BASE
            assert int.from_bytes(img[o:o + 2], "little") == old, f"stockplus's {lab} moved"
            img[o:o + 2] = new.to_bytes(2, "little")
        report["stockplus"]["no_stretch"] = True
        report["stockplus"]["sd_sw"] = hex(labels["sd_sw"])
    if nocrush:
        assert kw.get("v2"), "nocrush patches v2's drive words"
        cut = [a for a in range(labels["sd_sw"], labels["sd_cr"], 2) if hw(a) == CMP_R0_0 and hw(a + 2) & 0xFF00 == BNE
               and a + 2 + 4 + 2 * (hw(a + 2) & 0xFF) == labels["sd_cr"]]
        assert len(cut) == 1, "c_spdsp's bitcrush test moved"
        o = cut[0] - rhbuild.BASE
        img[o:o + 4] = MOVS_R0_0.to_bytes(2, "little") + NOP.to_bytes(2, "little")
        report["stockplus"]["no_crush"] = hex(cut[0])
    return labels, code
