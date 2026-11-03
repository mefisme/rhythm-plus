"""Test only: when the Sample Rec count-in's sampler really starts (MIT; Circuit Rhythm 5706).

uwTick (0x20000820, the clock of playfix's start time H0) at the sampler's switch to recording (fixedrec's first tempo read 0x0803CEA0,
which runs once then; with threshold on, when the sound comes), and at the record function's calls listed in report["srcount"]["rec_calls"]
when a build has them (clkci logs its own call).
Slot "srprobe": + 0 the call, + 4 recording (0 = none).  Read over USB with rdiag, against playfix's H0.  Install after srcount and fixedrec.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import Asm, b_cond, bl, cmp_reg, ldr_imm, movt, movw, pop_list, push_list, str_imm  # noqa: E402
import rhstate  # noqa: E402
import clkci  # noqa: E402

UWTICK = 0x20000820
REC_START = 0x0803CEA0                                 # fixedrec's bl c_frbpm at the sampler's start of recording


def arm_code(base, frbpm):
    slot = rhstate.ST + rhstate.OFF["srprobe"][0]
    a = Asm(base)
    E = a.emit

    def imm32(rd, v):
        E(movw, rd, v & 0xFFFF)
        E(movt, rd, v >> 16)

    def wrapper(name, off, target):                    # [slot + off] = uwTick (our block set up), then target(r0, r1)
        a.label(name)
        E(push_list, [0, 1, 4], lr=True)
        imm32(2, rhstate.HEAP_LIMIT_PTR)
        E(ldr_imm, 2, 2, 0)
        imm32(1, rhstate.ST)
        E(cmp_reg, 1, 2)
        E(b_cond, name + "_go", "ne")
        E(ldr_imm, 1, 1, 0)
        imm32(2, rhstate.MAGIC)
        E(cmp_reg, 1, 2)
        E(b_cond, name + "_go", "ne")
        imm32(1, UWTICK)
        E(ldr_imm, 1, 1, 0)
        imm32(2, slot)
        E(str_imm, 1, 2, off)
        a.label(name + "_go")
        E(pop_list, [0, 1])
        E(bl, target)
        E(pop_list, [4], pc=True)

    wrapper("c_sprec", 0, clkci.REC_FN)
    wrapper("c_sp3", 4, frbpm)
    return a.assemble()


def install(img, report, base_addr):
    import rh_fw
    import rhbuild
    frbpm = int(report["fixedrec"]["labels"]["c_frbpm"], 16)
    code, labels = arm_code(base_addr, frbpm)
    img += bytes([0xFF]) * (base_addr - rh_fw.APP_BASE - len(img)) + code
    while len(img) % 4:
        img += bytes([0xFF])
    calls = [int(x, 16) for x in report["srcount"].get("rec_calls", [])]
    for x in calls:
        rhbuild.patch(img, x, f"bl #{clkci.REC_FN:#x}", bl(x, labels["c_sprec"]))
    rhbuild.patch(img, REC_START, f"bl #{frbpm:#x}", bl(REC_START, labels["c_sp3"]))
    report["srprobe"] = dict(slot=hex(rhstate.ST + rhstate.OFF["srprobe"][0]), calls=[hex(x) for x in calls],
                             labels={k: hex(v) for k, v in labels.items() if k.startswith("c_")})
    return labels, code
