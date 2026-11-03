"""First steps after Play at the real tempo (MIT; Circuit Rhythm 5706).

Play's work (pattern switch, 8 track setups, transport listeners: ~23 ms) holds back the clock's 1 ms timer callbacks
(clock_tick 0x08032430); the timer then runs the missed ones back to back, so pulse 0 is late and the next pulses rush
to a grid anchored at Play.  Each tick adds the per-ms increment r4:r8 to the sequencer phase (+0x28) and to the MIDI
clock-out accumulator (+0x34).  `ldrb r3, [r7, #2]; cmp r3, #3` before the state dispatch (0x080326EE) -> `bl c_fxgate`:
  state 1 (internal start, pulse 0 this tick): arm, H0 = HAL ms, N = 0, held = 0
  state 3 while armed and less than WINDOW ms after H0: a tick with N > (ms since H0) gets r4:r8 = 0 (both counters
  hold), the others count in N; the grid then starts at pulse 0
  any other state: disarm.  External clock starts do not pass state 1 and are not touched.
State (+0 armed, +4 H0, +8 N, +12 ticks held since the last start): with rhstate in the build, its block's "playfix" slot, used
only once another module's c_rst has reserved and set up the block (the tick never sets it up: it runs in the timer's task);
otherwise FIXST, unused while the stock heap (a bump allocator) reaches past it.
Test: tools/emu_playfix.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import Asm, adds_imm8, b, b_cond, bl, cmp_imm, cmp_reg, ldr_imm, ldrb_imm, mov_reg, movs_imm, movt, movw, pop_list, push_list, str_imm, subs_reg  # noqa: E402
import rhstate  # noqa: E402

SITE = 0x080326EE
FIXST = rhstate.ST - 0x410                          # 0x2004F250, 16 bytes below playprobe's log
UWTICK = 0x20000820                                 # HAL ms tick, +1 in the SysTick handler 0x08066BD0
WINDOW = 200


def arm_code(base, block=False):
    a = Asm(base)
    E = a.emit

    def imm32(rd, v):
        E(movw, rd, v & 0xFFFF)
        E(movt, rd, v >> 16)

    # ---- bl from SITE: the stock's `ldrb r3, [r7, #2]; cmp r3, #3` (flags out), may zero r4 and r8
    a.label("c_fxgate")
    E(push_list, [0, 1, 2], lr=True)
    E(ldrb_imm, 3, 7, 2)
    if block:
        imm32(0, rhstate.ST)
        imm32(1, rhstate.HEAP_LIMIT_PTR)
        E(ldr_imm, 1, 1, 0)
        E(cmp_reg, 1, 0)
        E(b_cond, "fx_out", "ne")
        E(ldr_imm, 1, 0, 0)
        imm32(2, rhstate.MAGIC)
        E(cmp_reg, 1, 2)
        E(b_cond, "fx_out", "ne")
        E(adds_imm8, 0, rhstate.OFF["playfix"][0])
    else:
        imm32(0, FIXST)
        imm32(1, rhstate.HEAP_CUR_PTR)
        E(ldr_imm, 1, 1, 0)
        E(cmp_reg, 1, 0)
        E(b_cond, "fx_out", "hi")
    imm32(1, UWTICK)
    E(ldr_imm, 1, 1, 0)
    E(cmp_imm, 3, 1)
    E(b_cond, "fx_run", "ne")
    E(str_imm, 1, 0, 4)
    E(movs_imm, 2, 0)
    E(str_imm, 2, 0, 8)
    E(str_imm, 2, 0, 12)
    E(movs_imm, 2, 1)
    E(str_imm, 2, 0, 0)
    E(b, "fx_out")
    a.label("fx_run")
    E(cmp_imm, 3, 3)
    E(b_cond, "fx_off", "ne")
    E(ldr_imm, 2, 0, 0)
    E(cmp_imm, 2, 0)
    E(b_cond, "fx_out", "eq")
    E(ldr_imm, 2, 0, 4)
    E(subs_reg, 1, 1, 2)                            # ms since H0
    E(cmp_imm, 1, WINDOW)
    E(b_cond, "fx_off", "hs")
    E(ldr_imm, 2, 0, 8)
    E(cmp_reg, 2, 1)
    E(b_cond, "fx_hold", "hi")
    E(adds_imm8, 2, 1)
    E(str_imm, 2, 0, 8)
    E(b, "fx_out")
    a.label("fx_hold")
    E(movs_imm, 4, 0)
    E(mov_reg, 8, 4)
    E(ldr_imm, 2, 0, 12)
    E(adds_imm8, 2, 1)
    E(str_imm, 2, 0, 12)
    E(b, "fx_out")
    a.label("fx_off")
    E(movs_imm, 2, 0)
    E(str_imm, 2, 0, 0)
    a.label("fx_out")
    E(cmp_imm, 3, 3)
    E(pop_list, [0, 1, 2], pc=True)
    return a.assemble()


def install(img, report, base_addr):
    import rh_fw
    import rhbuild
    block = "rhstate" in report
    code, labels = arm_code(base_addr, block)
    img += bytes([0xFF]) * (base_addr - rh_fw.APP_BASE - len(img)) + code
    while len(img) % 4:
        img += bytes([0xFF])
    rhbuild.patch(img, SITE, "ldrb r3, [r7, #2]|cmp r3, #3", bl(SITE, labels["c_fxgate"]))
    state = rhstate.ST + rhstate.OFF["playfix"][0] if block else FIXST
    report["playfix"] = dict(state=hex(state), labels={k: hex(v) for k, v in labels.items() if k.startswith("c_")})
    return labels, code
