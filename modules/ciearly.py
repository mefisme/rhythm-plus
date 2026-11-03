"""countin presses Play EARLY_MS before its bar ends, so recording starts on the "1" (MIT; Circuit Rhythm 5706).

Measured on the device (STCI5, the Play fix's start time against countin's press time): the transport started 28-29 ms (140 BPM)
and 32-33 ms (80 BPM) after the bar's end.  countin's end test `udiv r0, r7, r6; cmp r0, #4` (r7 = ms since the press, r6 = ms
per beat) takes `bl c_ciearly` for its udiv: the beat is 4 once r7 + EARLY_MS reaches the bar, else r7 / r6 as before (the clicks
and the Record LED keep their times).  It runs inside countin's LED code, which saved lr; it uses r0 only.  Install after countin.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import Asm, adds_reg, b_cond, bl, bx_lr, cmp_imm, movs_imm, raw  # noqa: E402
import countin as C  # noqa: E402

EARLY_MS = 30
OLD = ["subs r7, r0, r1", "bpl", "movs r7, #0", "udiv r0, r7, r6", f"cmp r0, #{C.BEATS}"]


def find(img, report):
    """The `udiv` of countin's end test."""
    import capstone
    import rh_fw
    lo = int(report["countin"]["base"], 16)
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    ins = list(md.disasm(bytes(img[lo - rh_fw.APP_BASE:lo - rh_fw.APP_BASE + 0x400]), lo))
    seq = lambda k: [f"{x.mnemonic} {x.op_str}" if x.mnemonic != "bpl" else "bpl" for x in ins[k:k + 5]]
    hits = [ins[k + 3].address for k in range(len(ins) - 4) if seq(k) == OLD]
    assert len(hits) == 1, hits
    return hits[0]


def install(img, report, base_addr):
    import rh_fw
    import rhbuild
    a = Asm(base_addr)
    a.label("c_ciearly")                               # r7 = ms since the press, r6 = ms per beat -> r0 = the beat (4 = the end)
    a.emit(movs_imm, 0, EARLY_MS)
    a.emit(adds_reg, 0, 0, 7)
    a.emit(raw, C.udiv(0, 0, 6))
    a.emit(cmp_imm, 0, C.BEATS)
    a.emit(b_cond, "ce_x", "hs")
    a.emit(raw, C.udiv(0, 7, 6))
    a.label("ce_x")
    a.emit(bx_lr)
    code, labels = a.assemble()
    img += bytes([0xFF]) * (base_addr - rh_fw.APP_BASE - len(img)) + code
    while len(img) % 4:
        img += bytes([0xFF])
    at = find(img, report)
    rhbuild.patch(img, at, "udiv r0, r7, r6", bl(at, labels["c_ciearly"]))
    report["ciearly"] = dict(at=hex(at), labels={k: hex(v) for k, v in labels.items() if k.startswith("c_")})
    return labels, code
