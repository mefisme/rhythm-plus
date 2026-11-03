"""Timing probes around Play on the Circuit Rhythm 5706 (MIT; test builds only): when does the first step after Play leave?

Each probe writes (tag, DWT cycle counter at 216 MHz) to a RAM log that tools/rdiag.py reads over USB.
  tag 1  the engine's play method 0x08033D32 is entered (the log and the RESET_TOO words restart here)
  tag 6  that method returns
  tag 2  the clock's set-mode 0x080329C0 restarts the 1 ms timer (its `bl 0x08046DDE` at 0x080329E6): the grid's origin
  tag 3  clock_tick's case 1 calls the clock start 0x08032A82 (its `bl` at 0x08032712); byte 1 = r1, nonzero = pulse 0 fires now
  tag 4  each of the first TICKS timer callbacks after tag 2 (the restart's callback is swapped for c_pptick, which runs the stock's)
  tag 7  inside the play method: byte 1 = k before and k + 1 after each call in PLAY_WRAPS
  tag 8  (listeners=True) a store listener that ran LTHRESH cycles or more while the play method ran: bytes 1-3 = its handler's
         address & 0xFFFFFF, the entry's waits word = its cycles (the commit loop's `ldr.w ip, [r3]; blx ip` at LCALL -> bl c_pplcall)
Every wait of the DSP link's busy-wait 0x0802B66C (its 5 callers, WAIT_SITES) is counted with its cycles; each entry copies the count.
Log at LOG: +0 entries, +4 ticks logged since tag 2, +8 MAGIC once set up, +12 the play method's return address, +20 waits, +24 their
cycles, +28 1 while the play method runs (listeners=True); entries from +32, 16 bytes each: tag | extra << 8, cycle counter, waits,
HAL ms tick.  Nothing is written while the stock heap (a bump allocator, rhstate.py) reaches past LOG; on first use the heap's limit
is lowered to LOG, the DWT cycle counter is turned on and DBG_SLEEP keeps it counting through the idle task's wfi.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import (Asm, adds_imm8, adds_reg, b_cond, b_w, bl, blx_reg, cmp_imm, cmp_reg, h, ldr_imm, lsls_imm, mov_reg, movs_imm, movt, movw,  # noqa: E402
                   nop, orrs_reg, pop_list, push_list, raw, str_imm, subs_reg)
import rhstate  # noqa: E402

PLAY, PLAY_CONT = 0x08033D32, 0x08033D36
PLAY_PROLOGUE = bytes.fromhex("38b50446")           # push {r3, r4, r5, lr}; mov r4, r0
T0_SITE, TIMER_START = 0x080329E6, 0x08046DDE
CLOCK_TICK_CB = 0x0803242D                          # the callback set-mode registers (a thunk in front of clock_tick 0x08032430)
START_SITE, CLOCK_START = 0x08032712, 0x08032A82
LOG = rhstate.ST - 0x400                            # 0x2004F260, below rhstate's block
MAGIC = 0x35504C50                                  # "PLP5"
WAIT = 0x0802B66C
WAIT_SITES = ((0x08046416, "b.w"), (0x08046442, "bl"), (0x08046488, "bl"), (0x080464B6, "bl"), (0x08046500, "b.w"))
NMAX, TICKS = 60, 40
RESET_TOO = (0, 0)                                  # (address, words) zeroed with the log at tag 1 (a build sets commitprobe's counters)
IN_BLOCK = False                                    # set by a build that places LOG inside our block (ourram's "plog" slot)
# (site, callee, k): MIDI Start sent | store +0xA0 commit | position reset 0x08034082 | after locate + client start; none takes stack arguments
PLAY_WRAPS = ((0x08033DC0, 0x0803FD26, 1), (0x08033DCC, 0x0803FBEC, 3), (0x08033DD4, 0x08034082, 5), (0x08033DF0, 0x0803FD26, 7))
assert LOG + 32 + 16 * NMAX <= rhstate.ST
LCALL, LTHRESH = 0x0803FC1C, 12000                 # the commit loop's listener call; ~0.1 ms of cycle counter
MAGIC_L = 0x36504C50                                # "PLP6": the listeners build's log
DEMCR, DWT_LAR, DWT_CTRL, CYCCNT = 0xE000EDFC, 0xE0001FB0, 0xE0001000, 0xE0001004
DBGMCU_CR = 0xE0042004                                # bit 0 DBG_SLEEP: core clock stays on in sleep
UWTICK = 0x20000820                                   # HAL ms tick, +1 in the SysTick handler 0x08066BD0
BX_LR, BX_R12, MOV_R2_LR = h(0x4770), h(0x4760), h(0x4672)
POP_LR = h(0xF85D) + h(0xEB04)                      # ldr.w lr, [sp], #4


def arm_code(base, ret_addr=0, tick_addr=0, listeners=False):
    magic = MAGIC_L if listeners else MAGIC
    a = Asm(base)
    E = a.emit

    def imm32(rd, v):
        E(movw, rd, v & 0xFFFF)
        E(movt, rd, v >> 16)

    # ---- c_pplog(r0 = tag | extra << 8) -> Z set when the log is usable; tag 1 restarts the log, tag 2 the tick count; clobbers r0
    a.label("c_pplog")
    E(push_list, [1, 2, 3, 4])
    imm32(1, LOG)
    if IN_BLOCK:                                     # the log inside our block: usable once the block is set up
        imm32(3, rhstate.HEAP_LIMIT_PTR)
        E(ldr_imm, 3, 3, 0)
        imm32(2, rhstate.ST)
        E(cmp_reg, 3, 2)
        E(b_cond, "pl_out", "ne")
        E(ldr_imm, 3, 2, 0)
        imm32(2, rhstate.MAGIC)
        E(cmp_reg, 3, 2)
        E(b_cond, "pl_out", "ne")
    else:
        imm32(3, rhstate.HEAP_CUR_PTR)
        E(ldr_imm, 3, 3, 0)
        E(cmp_reg, 3, 1)
        E(b_cond, "pl_out", "hi")
    imm32(4, magic)
    E(ldr_imm, 2, 1, 8)
    E(cmp_reg, 2, 4)
    E(b_cond, "pl_on", "eq")
    imm32(3, rhstate.HEAP_LIMIT_PTR)
    E(ldr_imm, 2, 3, 0)
    E(cmp_reg, 2, 1)
    E(b_cond, "pl_lim", "ls")
    E(str_imm, 1, 3, 0)
    a.label("pl_lim")
    imm32(3, DEMCR)
    E(ldr_imm, 2, 3, 0)
    imm32(4, 1 << 24)
    E(orrs_reg, 2, 4)
    E(str_imm, 2, 3, 0)
    imm32(3, DWT_LAR)
    imm32(2, 0xC5ACCE55)
    E(str_imm, 2, 3, 0)
    imm32(3, DWT_CTRL)
    E(ldr_imm, 2, 3, 0)
    E(movs_imm, 4, 1)
    E(orrs_reg, 2, 4)
    E(str_imm, 2, 3, 0)
    imm32(3, DBGMCU_CR)
    E(ldr_imm, 2, 3, 0)
    E(movs_imm, 4, 1)
    E(orrs_reg, 2, 4)
    E(str_imm, 2, 3, 0)
    imm32(2, 0x7FFFFFFF)
    E(str_imm, 2, 1, 4)
    E(movs_imm, 2, 0)
    E(str_imm, 2, 1, 0)
    E(str_imm, 2, 1, 20)
    E(str_imm, 2, 1, 24)
    imm32(2, magic)
    E(str_imm, 2, 1, 8)
    a.label("pl_on")
    E(lsls_imm, 2, 0, 24)                            # the tag alone, in the top byte
    E(movs_imm, 3, 1)
    E(lsls_imm, 3, 3, 24)
    E(cmp_reg, 2, 3)
    E(b_cond, "pl_t2", "ne")
    E(movs_imm, 3, 0)
    E(str_imm, 3, 1, 0)
    if RESET_TOO[1]:
        imm32(4, RESET_TOO[0])
        for k in range(RESET_TOO[1]):
            E(str_imm, 3, 4, 4 * k)
    if listeners:
        E(movs_imm, 3, 1)
        E(str_imm, 3, 1, 28)
    a.label("pl_t2")
    if listeners:
        E(movs_imm, 3, 6)
        E(lsls_imm, 3, 3, 24)
        E(cmp_reg, 2, 3)
        E(b_cond, "pl_t6", "ne")
        E(movs_imm, 3, 0)
        E(str_imm, 3, 1, 28)
        a.label("pl_t6")
    E(movs_imm, 3, 2)
    E(lsls_imm, 3, 3, 24)
    E(cmp_reg, 2, 3)
    E(b_cond, "pl_add", "ne")
    E(movs_imm, 3, 0)
    E(str_imm, 3, 1, 4)
    a.label("pl_add")
    E(ldr_imm, 2, 1, 0)
    E(cmp_imm, 2, NMAX)
    E(b_cond, "pl_ok", "hs")
    E(lsls_imm, 3, 2, 4)
    E(adds_reg, 3, 3, 1)
    E(str_imm, 0, 3, 32)
    imm32(4, CYCCNT)
    E(ldr_imm, 4, 4, 0)
    E(str_imm, 4, 3, 36)
    E(ldr_imm, 4, 1, 20)
    E(str_imm, 4, 3, 40)
    imm32(4, UWTICK)
    E(ldr_imm, 4, 4, 0)
    E(str_imm, 4, 3, 44)
    E(adds_imm8, 2, 1)
    E(str_imm, 2, 1, 0)
    a.label("pl_ok")
    E(movs_imm, 0, 0)                                # Z = usable
    a.label("pl_out")
    E(pop_list, [1, 2, 3, 4])
    E(raw, BX_LR)

    # ---- the play method's entry (b.w from PLAY): tag 1; when the log is usable its return goes through c_ppret
    a.label("c_ppplay")
    E(push_list, [0, 1, 2, 3, 4])
    E(raw, MOV_R2_LR)
    E(movs_imm, 0, 1)
    E(bl, "c_pplog")
    E(b_cond, "pp_plain", "ne")
    imm32(1, LOG)
    E(str_imm, 2, 1, 12)
    E(pop_list, [0, 1, 2, 3, 4])
    imm32(12, ret_addr)
    E(mov_reg, 14, 12)
    E(raw, PLAY_PROLOGUE)
    E(b_w, PLAY_CONT)
    a.label("pp_plain")
    E(pop_list, [0, 1, 2, 3, 4])
    E(raw, PLAY_PROLOGUE)
    E(b_w, PLAY_CONT)

    a.label("c_ppret")
    E(push_list, [0, 1, 2, 3, 4])
    E(movs_imm, 0, 6)
    E(bl, "c_pplog")
    imm32(1, LOG)
    E(ldr_imm, 1, 1, 12)
    E(mov_reg, 12, 1)
    E(pop_list, [0, 1, 2, 3, 4])
    E(raw, BX_R12)

    # ---- the timer restart (bl from T0_SITE): tag 2; the clock's callback swapped for c_pptick when the log is usable
    a.label("c_ppt0")
    E(push_list, [0, 1, 2, 3, 4], lr=True)
    E(movs_imm, 0, 2)
    E(bl, "c_pplog")
    E(pop_list, [0, 1, 2, 3, 4])
    E(raw, POP_LR)
    E(b_cond, "t0_go", "ne")
    imm32(12, CLOCK_TICK_CB)
    E(cmp_reg, 3, 12)
    E(b_cond, "t0_go", "ne")
    imm32(3, tick_addr)
    a.label("t0_go")
    E(b_w, TIMER_START)

    # ---- the timer callback: tag 4 for the first TICKS calls after tag 2, then the stock's
    a.label("c_pptick")
    E(push_list, [0, 1, 2, 3, 4], lr=True)
    imm32(1, LOG)
    imm32(4, magic)
    E(ldr_imm, 2, 1, 8)
    E(cmp_reg, 2, 4)
    E(b_cond, "tk_skip", "ne")
    E(ldr_imm, 2, 1, 4)
    E(cmp_imm, 2, TICKS)
    E(b_cond, "tk_skip", "hs")
    E(adds_imm8, 2, 1)
    E(str_imm, 2, 1, 4)
    E(movs_imm, 0, 4)
    E(bl, "c_pplog")
    a.label("tk_skip")
    E(pop_list, [0, 1, 2, 3, 4])
    E(raw, POP_LR)
    E(b_w, CLOCK_TICK_CB & ~1)

    # ---- the clock start from clock_tick's case 1 (bl from START_SITE): tag 3 | r1 << 8
    a.label("c_ppstart")
    E(push_list, [0, 1, 2, 3, 4], lr=True)
    E(lsls_imm, 0, 1, 8)
    E(movs_imm, 2, 3)
    E(orrs_reg, 0, 2)
    E(bl, "c_pplog")
    E(pop_list, [0, 1, 2, 3, 4])
    E(raw, POP_LR)
    E(b_w, CLOCK_START)

    # ---- the DSP link's busy-wait (bl or b.w from WAIT_SITES): the stock's, timed; returns r0 as it does, clobbers r1-r3
    a.label("c_ppwait")
    E(push_list, [4, 5, 6], lr=True)
    E(mov_reg, 6, 0)
    imm32(4, CYCCNT)
    E(ldr_imm, 5, 4, 0)
    E(bl, WAIT)
    E(ldr_imm, 0, 4, 0)
    E(subs_reg, 0, 0, 5)
    imm32(1, LOG)
    imm32(3, magic)
    E(ldr_imm, 2, 1, 8)
    E(cmp_reg, 2, 3)
    E(b_cond, "wt_out", "ne")
    E(ldr_imm, 2, 1, 24)
    E(adds_reg, 2, 2, 0)
    E(str_imm, 2, 1, 24)
    E(ldr_imm, 2, 1, 20)
    E(adds_imm8, 2, 1)
    E(str_imm, 2, 1, 20)
    a.label("wt_out")
    E(mov_reg, 0, 6)
    E(pop_list, [4, 5, 6], pc=True)

    # ---- a call in the play method (bl from a PLAY_WRAPS site): tag 7 | k << 8 before, 7 | (k + 1) << 8 after; keeps r0-r3 in and r0 out
    for site, callee, k in PLAY_WRAPS:
        a.label(f"c_ppw{k}")
        E(push_list, [0, 1, 2, 3, 4], lr=True)
        E(movw, 0, 7 | k << 8)
        E(bl, "c_pplog")
        E(pop_list, [0, 1, 2, 3])
        E(bl, callee)
        E(push_list, [0, 1])
        E(movw, 0, 7 | (k + 1) << 8)
        E(bl, "c_pplog")
        E(pop_list, [0, 1])
        E(pop_list, [4], pc=True)

    # ---- the commit loop's listener call (bl from LCALL, then a nop): r0 obj, r1 store, r2 mask, r3 vtable; r0-r3 and ip are dead after
    if listeners:
        a.label("c_pplcall")
        E(push_list, [4, 5, 6], lr=True)
        E(ldr_imm, 6, 3, 0)                          # the handler
        imm32(5, CYCCNT)
        E(ldr_imm, 5, 5, 0)
        E(blx_reg, 6)
        imm32(4, CYCCNT)
        E(ldr_imm, 4, 4, 0)
        E(subs_reg, 4, 4, 5)                         # its cycles
        imm32(1, LOG)
        imm32(3, magic)
        E(ldr_imm, 2, 1, 8)
        E(cmp_reg, 2, 3)
        E(b_cond, "lc_out", "ne")
        E(ldr_imm, 2, 1, 28)
        E(cmp_imm, 2, 0)
        E(b_cond, "lc_out", "eq")
        imm32(2, LTHRESH)
        E(cmp_reg, 4, 2)
        E(b_cond, "lc_out", "lo")
        E(ldr_imm, 5, 1, 20)                         # the waits count: the entry's waits word carries the cycles instead
        E(str_imm, 4, 1, 20)
        E(lsls_imm, 0, 6, 8)
        E(adds_imm8, 0, 8)
        E(bl, "c_pplog")
        imm32(1, LOG)
        E(str_imm, 5, 1, 20)
        a.label("lc_out")
        E(pop_list, [4, 5, 6], pc=True)
    return a.assemble()


def install(img, report, base_addr, listeners=False):
    import rh_fw
    import rhbuild
    _, labels = arm_code(base_addr, listeners=listeners)
    code, labels2 = arm_code(base_addr, labels["c_ppret"] | 1, labels["c_pptick"] | 1, listeners)
    assert labels2 == labels
    img += bytes([0xFF]) * (base_addr - rh_fw.APP_BASE - len(img)) + code
    while len(img) % 4:
        img += bytes([0xFF])
    rhbuild.patch(img, PLAY, "push {r3, r4, r5, lr}|mov r4, r0", b_w(PLAY, labels["c_ppplay"]))
    rhbuild.patch(img, T0_SITE, f"bl #{TIMER_START:#x}", bl(T0_SITE, labels["c_ppt0"]))
    rhbuild.patch(img, START_SITE, f"bl #{CLOCK_START:#x}", bl(START_SITE, labels["c_ppstart"]))
    for site, kind in WAIT_SITES:
        rhbuild.patch(img, site, f"{kind} #{WAIT:#x}", (bl if kind == "bl" else b_w)(site, labels["c_ppwait"]))
    for site, callee, k in PLAY_WRAPS:
        rhbuild.patch(img, site, f"bl #{callee:#x}", bl(site, labels[f"c_ppw{k}"]))
    if listeners:
        rhbuild.patch(img, LCALL, "ldr.w ip, [r3]|blx ip", bl(LCALL, labels["c_pplcall"]) + nop())
    report["playprobe"] = dict(log=hex(LOG), magic=hex(MAGIC_L if listeners else MAGIC), labels={k: hex(v) for k, v in labels.items() if k.startswith("c_")})
    return labels, code
