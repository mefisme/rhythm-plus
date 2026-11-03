"""Store commits while the play method runs (MIT; test builds only): which commits change nothing, and what each one costs.

A store (0x0803FC58 / 0x0803FD26 / 0x0803FBEC): +4 the active buffer of each word (bit i), +8 the words written since the last commit
(bit i, set by the first WPTR of the word, which copies the old value into the other buffer), +0xC / +0x10 the two buffers.  The commit
flips +4 for the written words and calls each listener whose mask meets +8 (every listener when byte 0 is 0), then clears +8.
c_cmt (b.w from the commit's entry) runs the stock commit unchanged; while playprobe's window flag (LOG + 28) is set it first compares old and
new value of each written word, and after the commit logs to CLOG: +0 entries, +4 commits seen, +8 commits that changed no word, +12 the
current nesting depth; entries from +16, 16 bytes, written when a commit ends: store & 0xFFFFFF | depth << 24, written words, changed words,
cycles (the commit with everything it set off).  Nothing is written while the stock heap reaches past CLOG; the first write lowers its limit.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import (Asm, adds_imm8, adds_reg, b, b_cond, b_w, bl, cmp_imm, cmp_reg, ldr_imm, lsls_imm, lsls_reg, lsrs_imm, mov_reg,  # noqa: E402
                   movs_imm, movt, movw, orrs_reg, pop_list, push_list, raw, str_imm, subs_imm8, subs_reg, tst_reg)
import playprobe  # noqa: E402
import rhstate  # noqa: E402

COMMIT, COMMIT_BODY = 0x0803FBEC, 0x0803FBF0
PROLOGUE = bytes.fromhex("f8b50446")                # push {r3, r4, r5, r6, r7, lr}; mov r4, r0
CLOG, CN = 0x2004EB00, 116
assert CLOG + 16 + 16 * CN <= 0x2004F250            # playfix's FIXST
CYCCNT = playprobe.CYCCNT


def arm_code(base, magic):
    a = Asm(base)
    E = a.emit

    def imm32(rd, v):
        E(movw, rd, v & 0xFFFF)
        E(movt, rd, v >> 16)

    # ---- the commit's entry (b.w from COMMIT); outside the window: r1, r2 and ip only, then the stock's commit
    a.label("c_cmt")
    imm32(1, playprobe.LOG)
    E(ldr_imm, 2, 1, 8)
    imm32(12, magic)
    E(cmp_reg, 2, 12)
    E(b_cond, "c_cmtorig", "ne")
    E(ldr_imm, 2, 1, 28)
    E(cmp_imm, 2, 0)
    E(b_cond, "c_cmtorig", "eq")
    imm32(1, CLOG)
    if not playprobe.IN_BLOCK:                       # in our block, the window flag already means the block is set up
        imm32(2, rhstate.HEAP_CUR_PTR)
        E(ldr_imm, 2, 2, 0)
        E(cmp_reg, 2, 1)
        E(b_cond, "c_cmtorig", "hi")
    E(push_list, [3, 4, 5, 6, 7], lr=True)
    E(mov_reg, 4, 0)
    imm32(2, rhstate.HEAP_LIMIT_PTR)                 # the heap may never reach CLOG
    E(ldr_imm, 3, 2, 0)
    E(cmp_reg, 3, 1)
    E(b_cond, "cm_lim", "ls")
    E(str_imm, 1, 2, 0)
    a.label("cm_lim")
    E(ldr_imm, 6, 4, 8)                              # the written words
    E(movs_imm, 5, 0)                                # the changed words
    E(movs_imm, 3, 0)
    a.label("cm_word")
    E(movs_imm, 0, 1)
    E(lsls_reg, 0, 3)
    E(tst_reg, 6, 0)
    E(b_cond, "cm_next", "eq")
    E(ldr_imm, 7, 4, 4)
    E(tst_reg, 7, 0)
    E(b_cond, "cm_a0", "eq")
    E(ldr_imm, 1, 4, 16)                             # active buffer 1: old in +0x10, new in +0xC
    E(ldr_imm, 2, 4, 12)
    E(b, "cm_cmp")
    a.label("cm_a0")
    E(ldr_imm, 1, 4, 12)
    E(ldr_imm, 2, 4, 16)
    a.label("cm_cmp")
    E(lsls_imm, 7, 3, 2)
    E(adds_reg, 1, 1, 7)
    E(adds_reg, 2, 2, 7)
    E(ldr_imm, 1, 1, 0)
    E(ldr_imm, 2, 2, 0)
    E(cmp_reg, 1, 2)
    E(b_cond, "cm_next", "eq")
    E(orrs_reg, 5, 0)
    a.label("cm_next")
    E(adds_imm8, 3, 1)
    E(cmp_imm, 3, 32)
    E(b_cond, "cm_word", "ne")
    imm32(0, CLOG)
    E(ldr_imm, 1, 0, 12)                             # depth + 1
    E(adds_imm8, 1, 1)
    E(str_imm, 1, 0, 12)
    E(ldr_imm, 1, 0, 4)
    E(adds_imm8, 1, 1)
    E(str_imm, 1, 0, 4)
    E(cmp_imm, 5, 0)
    E(b_cond, "cm_chg", "ne")
    E(ldr_imm, 1, 0, 8)
    E(adds_imm8, 1, 1)
    E(str_imm, 1, 0, 8)
    a.label("cm_chg")
    imm32(7, CYCCNT)
    E(ldr_imm, 7, 7, 0)
    E(mov_reg, 0, 4)
    E(bl, "c_cmtorig")
    imm32(0, CYCCNT)
    E(ldr_imm, 0, 0, 0)
    E(subs_reg, 1, 0, 7)                             # the cycles
    imm32(2, CLOG)
    E(ldr_imm, 3, 2, 12)
    E(subs_imm8, 3, 1)
    E(str_imm, 3, 2, 12)                             # r3 = this commit's depth
    E(ldr_imm, 0, 2, 0)
    E(cmp_imm, 0, CN)
    E(b_cond, "cm_out", "hs")
    E(lsls_imm, 7, 0, 4)
    E(adds_reg, 7, 7, 2)
    E(adds_imm8, 0, 1)
    E(str_imm, 0, 2, 0)
    E(lsls_imm, 0, 4, 8)
    E(lsrs_imm, 0, 0, 8)
    E(lsls_imm, 3, 3, 24)
    E(orrs_reg, 0, 3)
    E(str_imm, 0, 7, 16)
    E(str_imm, 6, 7, 20)
    E(str_imm, 5, 7, 24)
    E(str_imm, 1, 7, 28)
    a.label("cm_out")
    E(pop_list, [0, 4, 5, 6, 7], pc=True)            # r0 = the caller's r3, as the stock's commit returns

    # ---- the stock's commit: its prologue, then its body
    a.label("c_cmtorig")
    E(raw, PROLOGUE)
    E(b_w, COMMIT_BODY)
    return a.assemble()


def install(img, report, base_addr):
    import rh_fw
    import rhbuild
    magic = int(report["playprobe"]["magic"], 16)
    code, labels = arm_code(base_addr, magic)
    img += bytes([0xFF]) * (base_addr - rh_fw.APP_BASE - len(img)) + code
    while len(img) % 4:
        img += bytes([0xFF])
    rhbuild.patch(img, COMMIT, "push {r3, r4, r5, r6, r7, lr}|mov r4, r0", b_w(COMMIT, labels["c_cmt"]))
    report["commitprobe"] = dict(clog=hex(CLOG), labels={k: hex(v) for k, v in labels.items() if k.startswith("c_")})
    return labels, code
