"""A faster redraw of the step pads' lights after a step store commit (MIT; Circuit Rhythm 5706): the same flags and colours.

The pad view's store listener 0x0805D092 (r4 = view, r8 = the commit's written-word mask), for the view's step store [view + 0xC]:
  loop 1, each written word w 0-7: steps 4w..4w + 3, flag bit 1 of [view + 0x74 + 2 step] = (step's byte in word w != 0), then the
  pad's colour 0x0805CF24(view, step);
  loop 2, each written word 24 + w: flag bit 8 = (step's byte in word 24 + w != 0xFF), the colour, then 0x0805D044(view, [[view + 0x64]]
  p1) when that p1 is not 0xFF (bit 9 of that step's flags from the store's values, then its colour).
The colour is a pure function of the step's flags (it writes one entry), and 0x0805D044 depends only on the store's committed values,
so setting both bits of a step and drawing it once, then 0x0805D044 once, leaves the same flags and colours with half the colour
calls and a quarter of the store reads.  c_padlit takes the branch's place (b.w at 0x0805D174, after its movs r5, #0) and ends at the function's pop 0x0805D3A2;
r5-r7 and sb are the function's own (saved by its push).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import (Asm, adds_imm8, adds_reg, ands_reg, b, b_cond, b_w, bics_reg, bl, cmp_imm, h, ldr_imm, ldr_sp, lsls_imm, lsrs_reg,  # noqa: E402
                   mov_reg, movs_imm, orrs_reg, raw)

SITE, AFTER = 0x0805D174, 0x0805D3A2
SITE_OLD = "mov.w sb, #4"
PARAM_GET, COLOUR, PLAYPAD = 0x0803FC58, 0x0805CF24, 0x0805D044
SB, R8 = 9, 8


def str_sp(rt, imm): return h(0x9000 | rt << 8 | imm >> 2)
def ldrh0(rt, rn): return h(0x8800 | rn << 3 | rt)
def strh0(rt, rn): return h(0x8000 | rn << 3 | rt)
def uxtb(rd, rm): return h(0xB2C0 | rm << 3 | rd)


def arm_code(base):
    a = Asm(base)
    E = a.emit
    a.label("c_padlit")
    E(raw, h(0xB082))                                  # sub sp, #8: [sp] = lane, [sp + 4] = bit 0 word w written, bit 1 word 24 + w
    E(movs_imm, 0, 0)
    E(mov_reg, SB, 0)                                  # sb = 1 once a word 24-31 was written
    E(movs_imm, 5, 0)                                  # r5 = w
    a.label("pl_w")
    E(mov_reg, 0, R8)
    E(lsrs_reg, 0, 5)
    E(movs_imm, 1, 1)
    E(ands_reg, 0, 1)                                  # r0 = word w written
    E(mov_reg, 2, R8)
    E(mov_reg, 3, 5)
    E(adds_imm8, 3, 24)
    E(lsrs_reg, 2, 3)
    E(ands_reg, 2, 1)                                  # r2 = word 24 + w written
    E(lsls_imm, 2, 2, 1)
    E(orrs_reg, 0, 2)
    E(cmp_imm, 0, 0)
    E(b_cond, "pl_next", "eq")
    E(raw, str_sp(0, 4))
    E(lsls_imm, 0, 0, 31)
    E(b_cond, "pl_nob", "pl")
    E(ldr_imm, 0, 4, 0xC)
    E(mov_reg, 1, 5)
    E(bl, PARAM_GET)
    E(ldr_imm, 6, 0, 0)                                # r6 = word w
    a.label("pl_nob")
    E(ldr_sp, 0, 4)
    E(lsls_imm, 0, 0, 30)
    E(b_cond, "pl_noc", "pl")
    E(ldr_imm, 0, 4, 0xC)
    E(mov_reg, 1, 5)
    E(adds_imm8, 1, 24)
    E(bl, PARAM_GET)
    E(ldr_imm, 7, 0, 0)                                # r7 = word 24 + w
    E(movs_imm, 0, 1)
    E(mov_reg, SB, 0)
    a.label("pl_noc")
    E(movs_imm, 0, 0)
    E(raw, str_sp(0, 0))
    a.label("pl_lane")
    E(ldr_sp, 3, 0)
    E(lsls_imm, 2, 5, 2)
    E(adds_reg, 2, 2, 3)                               # r2 = step
    E(lsls_imm, 3, 3, 3)                               # r3 = the lane's shift
    E(mov_reg, 0, 4)
    E(adds_imm8, 0, 0x74)
    E(lsls_imm, 2, 2, 1)
    E(adds_reg, 0, 0, 2)                               # r0 = the step's flags
    E(raw, ldrh0(1, 0))
    E(ldr_sp, 2, 4)
    E(lsls_imm, 2, 2, 31)
    E(b_cond, "pl_a", "pl")
    E(mov_reg, 2, 6)
    E(lsrs_reg, 2, 3)
    E(raw, uxtb(2, 2))
    E(cmp_imm, 2, 0)
    E(b_cond, "pl_a0", "eq")
    E(movs_imm, 2, 2)
    E(orrs_reg, 1, 2)
    E(b, "pl_a")
    a.label("pl_a0")
    E(movs_imm, 2, 2)
    E(bics_reg, 1, 2)
    a.label("pl_a")
    E(ldr_sp, 2, 4)
    E(lsls_imm, 2, 2, 30)
    E(b_cond, "pl_c", "pl")
    E(mov_reg, 2, 7)
    E(lsrs_reg, 2, 3)
    E(raw, uxtb(2, 2))
    E(cmp_imm, 2, 0xFF)
    E(b_cond, "pl_c0", "eq")
    E(movs_imm, 2, 1)
    E(lsls_imm, 2, 2, 8)
    E(orrs_reg, 1, 2)
    E(b, "pl_c")
    a.label("pl_c0")
    E(movs_imm, 2, 1)
    E(lsls_imm, 2, 2, 8)
    E(bics_reg, 1, 2)
    a.label("pl_c")
    E(raw, strh0(1, 0))
    E(ldr_sp, 1, 0)
    E(lsls_imm, 2, 5, 2)
    E(adds_reg, 1, 1, 2)
    E(mov_reg, 0, 4)
    E(bl, COLOUR)
    E(ldr_sp, 1, 0)
    E(adds_imm8, 1, 1)
    E(raw, str_sp(1, 0))
    E(cmp_imm, 1, 4)
    E(b_cond, "pl_lane", "lo")
    a.label("pl_next")
    E(adds_imm8, 5, 1)
    E(cmp_imm, 5, 8)
    E(b_cond, "pl_w", "lo")
    E(mov_reg, 0, SB)
    E(cmp_imm, 0, 0)
    E(b_cond, "pl_x", "eq")
    E(ldr_imm, 0, 4, 0x64)
    E(movs_imm, 1, 1)
    E(bl, PARAM_GET)
    E(raw, h(0x7801))                                  # ldrb r1, [r0]
    E(cmp_imm, 1, 0xFF)
    E(b_cond, "pl_x", "eq")
    E(mov_reg, 0, 4)
    E(bl, PLAYPAD)
    a.label("pl_x")
    E(raw, h(0xB002))                                  # add sp, #8
    E(b_w, AFTER)
    return a.assemble()


def install(img, report, base_addr):
    import rh_fw
    import rhbuild
    code, labels = arm_code(base_addr)
    img += bytes([0xFF]) * (base_addr - rh_fw.APP_BASE - len(img)) + code
    while len(img) % 4:
        img += bytes([0xFF])
    rhbuild.patch(img, SITE, SITE_OLD, b_w(SITE, labels["c_padlit"]))
    report["padlit"] = dict(labels={k: hex(v) for k, v in labels.items() if k.startswith("c_")})
    return labels, code
