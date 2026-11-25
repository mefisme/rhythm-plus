"""Unicorn test of quantize (stepmut.c, QUANTIZE): Pattern Settings pad 25 quantizes the track's pattern from its start step to its
end step; the other pads stay the stock's; pad 25's light: ready, green when done, red flashes when refused (no step object).

    python tests/emu_quantize.py STOCK.bin BUILT.bin RAM.bin
"""
import struct
import sys

import emu_stepmut as SM  # noqa: E402  (sets RH_BUILD from the arguments)
from emu_stepmut import ET, LB, R, call, check, obj, pat, tick, u32  # noqa: E402
from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_R2  # noqa: E402

PS0, PS_SZ, PS_VT = 0x2004C4B8, 0x60, 0x08067EA4
Q_PAD = 24
EMPTY = bytes([0, 6, 0, 0, 7, 0xFF, 0, 0])
GREEN, RED = 0x1E, 0x55


def step(mask, vel, flip=0xFF): return bytes([0, 6, mask, vel, 7, flip, 0, 0])


def put(uc, t, steps, start=0, end=15):
    p = pat(uc, t)
    for s in range(32):
        uc.mem_write(p + 8 * s, steps.get(s, EMPTY))
    uc.mem_write(p + 0x100, bytes([end, start]))
    return p


def steps(uc, t): p = pat(uc, t); return [bytes(uc.mem_read(p + 8 * s, 8)) for s in range(32)]
def press(uc, t, pad=Q_PAD, vel=100): call(uc, LB["c_sm_qpad"], PS0 + PS_SZ * t, pad, vel)


def light(uc, t):
    v = PS0 + PS_SZ * t
    call(uc, LB["c_sm_qled"], v)
    return struct.unpack("<H", uc.mem_read(u32(uc, u32(uc, v + 4)) + 2 * Q_PAD, 2))[0]


def main():
    fw = open(sys.argv[2], "rb").read()
    uc = ET.setup(fw, open(sys.argv[3], "rb").read())
    q = R.get("quantize")
    check("the build has quantize on Pattern Settings pad 25", q and q["pad"] == 25)
    B = 0x08010000
    slots = [struct.unpack_from("<I", fw, PS_VT + 4 * k - B)[0] & ~1 for k in (0, 7)]
    check("the Pattern Settings views' pad and light calls are ours", slots == [LB["c_sm_qpad"], LB["c_sm_qled"]])
    reloads = []
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: reloads.append(a), None, 0x08048932, 0x08048933)

    # a single hit early in a step goes to its start; late, to the next step's start; rolls stay; the end step wraps to the start
    before = {0: step(1, 10), 1: step(2, 11), 2: step(8, 12, flip=5), 4: step(32, 14), 5: step(3, 15), 6: step(16, 16),
              7: step(8, 17), 8: step(4, 18), 15: step(16, 25), 20: step(16, 30)}
    put(uc, 0, before)
    press(uc, 0)
    got = steps(uc, 0)
    exp = {0: step(1, 10), 1: step(1, 11), 2: EMPTY, 3: step(1, 12, flip=5), 4: EMPTY, 5: step(3, 15), 6: EMPTY,
           7: step(1, 16), 8: step(1, 18), 15: EMPTY, 20: step(16, 30)}
    for s, v in exp.items():
        check(f"step {s + 1}: {v.hex()}", got[s] == v, got[s].hex())
    check("a late hit into a step with a hit adds microstep 1 there (step 5's to the roll on 6, step 16's to step 1)",
          got[5][2] == 3 and got[0][2] == 1)
    check("steps outside the start and end are not changed", got[20] == step(16, 30) and all(got[s] == EMPTY for s in range(16, 32) if s != 20))
    check("the stock's pattern load ran after the write", len(reloads) == 1, len(reloads))
    ready = int(q.get("idle", "0x1"), 16)
    if q.get("flash"):
        seq = []
        for _ in range(6):
            seq.append(light(uc, 0)); tick(uc, 64)
        check("a quantize flashes the ready colour: 3 times, 64 ms on, 64 ms off", seq == [ready, 0] * 3, [hex(x) for x in seq])
        check("ready is the probability green, Mutate's Duplicate light (palette 0x7D)", ready == 0x76 + 7)
    else:
        check("pad 25 green after a quantize", light(uc, 0) == GREEN, hex(light(uc, 0)))
    tick(uc, 400)
    idle = light(uc, 0)
    check("pad 25 back to its ready light after 384 ms", idle == ready, hex(idle))

    # through the stock: Pattern Settings (the track view's mode 4), a pad press and the view's lights
    seen, lit = [], []
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: seen.append(u.reg_read(UC_ARM_REG_R2)), None, LB["c_sm_qpad"], LB["c_sm_qpad"] + 1)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: lit.append(a), None, LB["c_sm_qled"], LB["c_sm_qled"] + 1)
    keep_mode = uc.mem_read(SM.T.CONT + 0x264, 1)
    uc.mem_write(SM.T.CONT + 0x264, bytes([4]))
    put(uc, 0, {1: step(2, 11)})
    SM.pad(uc, Q_PAD)
    check("a pad 25 press on Pattern Settings reaches quantize with its velocity", seen == [100] and steps(uc, 0)[1] == step(1, 11), seen)
    seen.clear(); SM.unpad(uc, Q_PAD)
    check("its release does not", not seen)
    call(uc, u32(uc, u32(uc, SM.T.CONT) + 0x1C), SM.T.CONT)
    check("the stock's light call for the view reaches pad 25's light", bool(lit))
    uc.mem_write(SM.T.CONT + 0x264, bytes(keep_mode))
    tick(uc, 400)

    # again: nothing left to move
    put(uc, 0, before)
    press(uc, 0)
    press(uc, 0)
    check("a second quantize changes nothing", steps(uc, 0) == got)

    # a release (velocity 0) does nothing
    put(uc, 0, {1: step(2, 11)})
    press(uc, 0, vel=0)
    check("velocity 0 does not quantize", steps(uc, 0)[1] == step(2, 11))

    # start and end in the middle; the end step's late hit wraps to the start step
    put(uc, 0, {4: step(1, 1), 9: step(32, 2)}, start=4, end=9)
    press(uc, 0)
    g = steps(uc, 0)
    check("start 5, end 10: the end step's late hit wraps to the start step", g[9] == EMPTY and g[4] == step(1, 1), (g[4].hex(), g[9].hex()))
    put(uc, 0, {3: step(32, 2)}, start=3, end=3)
    press(uc, 0)
    check("a one-step pattern: a late hit stays on its step, at microstep 1", steps(uc, 0)[3] == step(1, 2), steps(uc, 0)[3].hex())

    # another pad: the stock's
    calls = []
    stock_pad = int(q["prev"][0], 16)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: calls.append(a), None, stock_pad, stock_pad + 1)
    put(uc, 0, {1: step(2, 11)})
    press(uc, 0, pad=25)
    check("pad 26 goes to the stock and does not quantize", calls and steps(uc, 0)[1] == step(2, 11))

    # refused: the track has no step object
    keep = obj(uc, 1)
    uc.mem_write(SM.ENGINE + 0x84 + 4, struct.pack("<I", 0))
    press(uc, 1)
    r = light(uc, 1)
    tick(uc, 64)
    r2 = light(uc, 1)
    check("refused: pad 25 flashes red", {r, r2} == {RED, 0}, (hex(r), hex(r2)))
    uc.mem_write(SM.ENGINE + 0x84 + 4, struct.pack("<I", keep))
    print("ALL PASS")


if __name__ == "__main__":
    main()
