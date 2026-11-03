"""The Record LED during countin's count: dark, red for the first 100 ms of each beat (MIT; Circuit Rhythm 5706).

countin lights Record for the first half of each beat; Record is already lit while armed, so the eye takes the dark half as the beat.
Its test `lsls r0, r0, #1; movs r1, #0; cmp r0, r6` (2 * ms into the beat < ms per beat) becomes `nop; movs r1, #0; cmp r0, #100`,
the time vismet lights Clear for.  Install after countin.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import cmp_imm, nop  # noqa: E402
import vismet  # noqa: E402

OLD = ["udiv r0, r7, r6", "muls r0, r6, r0", "subs r0, r7, r0", "lsls r0, r0, #1", "movs r1, #0", "cmp r0, r6"]


def find(img, report):
    """The `lsls` of countin's Record LED test."""
    import capstone
    import rh_fw
    lo = int(report["countin"]["base"], 16)
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    ins = list(md.disasm(bytes(img[lo - rh_fw.APP_BASE:lo - rh_fw.APP_BASE + 0x400]), lo))
    hits = [ins[k + 3].address for k in range(len(ins) - 5) if [f"{x.mnemonic} {x.op_str}" for x in ins[k:k + 6]] == OLD]
    assert len(hits) == 1, hits
    return hits[0]


def install(img, report, base_addr):
    import rhbuild
    at = find(img, report)
    rhbuild.patch(img, at, "lsls r0, r0, #1", nop())
    rhbuild.patch(img, at + 4, "cmp r0, r6", cmp_imm(0, vismet.FLASH_MS))
    report["recblink"] = dict(at=hex(at))
    return {}, b""
