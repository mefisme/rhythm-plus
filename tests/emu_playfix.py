"""Emulation of tools/playfix.py (Circuit Rhythm 5706): the clock's 1 ms tick on the stock and on a built image, side by side.

    python tools/emu_playfix.py BASE.bin BUILT.bin RAM.bin [--block]     (RAM.bin: a RAM dump read with tools/rhremote.py)

BASE is the image without playfix (the stock, or Alpha 0.03 for A0.03F).  --block: a build with rhstate, whose block is set up first
(limit, zeroed, magic: as another module's c_rst does); its "not set up" case must then match BASE.

Each case runs the clock set-mode 0x080329C0(clock, 0) (internal start: state 1), then ticks with a given HAL ms per tick,
and compares the sequencer phase (+0x28), the clock-out accumulator (+0x34) and the pulse count (+0x20) after each tick.
"""
import os
import struct
import sys

from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_THUMB, Uc
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R4, UC_ARM_REG_SP

sys.path[:0] = [str(__import__("pathlib").Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import playfix  # noqa: E402
import rhstate  # noqa: E402

FLASH, RAM, STACK, SENT = 0x08010000, 0x20000000, 0x30000000, 0x08000100
CLOCK, SETMODE, TICK = 0x200126E8, 0x080329C0, 0x0803242C
EXT_STORE_BUFS = (0x20012880, 0x20012884, 0x20012888)    # the clock's external-clock store; the dump may hold a synced clock
WAIT = 0x0802B66C                                        # the DSP link's busy-wait: another task ends it
BURST = [0, 0, 0, 1] + [3] * 22 + list(range(4, 40)) + [199, 200, 201, 250]   # HAL ms of each tick after the start tick: Play's late burst, then 1 a ms


def machine(fw, ram):
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    uc.mem_map(0x08000000, 0x80000)
    uc.mem_write(FLASH, fw)
    uc.mem_write(SENT, b"\x00\xbf" * 8)
    uc.mem_map(RAM, 0x60000)
    uc.mem_write(RAM, ram)
    uc.mem_map(STACK, 0x100000)
    for base, size in ((0x40000000, 0x20000000), (0xE0000000, 0x100000), (0x00000000, 0x100000)):
        uc.mem_map(base, size)
    for a in EXT_STORE_BUFS:
        uc.mem_write(a, b"\x00")
    uc.mem_write(CLOCK + 0x55, b"\x00")

    def hk(u, a, s, d):
        if a == WAIT:
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE, hk, None, WAIT, WAIT + 1)
    if os.environ.get("RH_MEMAUDIT") and len(fw) > OUR_CODE - FLASH:
        audit_hook(uc)
    return uc


OUR_CODE = 0x0806A570                                    # our appended code starts here in every build (the stock image's end)
AUDIT = set()


def audit_hook(uc):
    """RH_MEMAUDIT=<file>: every load / store our appended code runs, (pc, address, size, 'r' / 'w'), appended to the file at exit"""
    import atexit
    from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs
    from capstone.arm import ARM_OP_MEM
    cs = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    cs.detail = True
    seen = {}
    sizes = {"ldrb": 1, "strb": 1, "ldrsb": 1, "ldrh": 2, "strh": 2, "ldrsh": 2, "ldr": 4, "str": 4, "ldrd": 8, "strd": 8}

    def decode(u, a):
        if a not in seen:
            ins = next(cs.disasm(bytes(u.mem_read(a, 4)), a), None)
            op = None
            if ins is not None:
                name = ins.mnemonic.split(".")[0]
                for o in ins.operands:
                    if o.type == ARM_OP_MEM and name in sizes:
                        op = (name[0], sizes[name], ins.reg_name(o.mem.base), ins.reg_name(o.mem.index) if o.mem.index else None, o.mem.disp,
                              ins.writeback and len(ins.operands) > 2)
            seen[a] = op
        return seen[a]

    def hk(u, a, n, d):
        op = decode(u, a)
        if op is None or op[2] in ("pc", "sp"):
            return
        kind, size, base, index, disp, post = op
        addr = reg(u, base) + (reg(u, index) if index else 0) + (0 if post else disp)
        if RAM <= addr < RAM + 0x60000:
            AUDIT.add((a, addr, size, "w" if kind == "s" else "r"))
    uc.hook_add(UC_HOOK_CODE, hk, None, OUR_CODE, FLASH + 0x80000)
    if not getattr(audit_hook, "armed", False):
        audit_hook.armed = True

        def dump():
            with open(os.environ["RH_MEMAUDIT"], "a") as f:
                for row in sorted(AUDIT):
                    f.write("%x %x %d %s\n" % row)
        atexit.register(dump)


def reg(u, name):
    from unicorn import arm_const
    return u.reg_read(getattr(arm_const, "UC_ARM_REG_" + {"sb": "R9", "sl": "R10", "fp": "R11", "ip": "R12"}.get(name, name.upper())))


def call(uc, fn, *args):
    sp = STACK + 0xF0000
    for i, a in enumerate(args):
        uc.reg_write(UC_ARM_REG_R0 + i, a)
    for r in range(4, 12):
        uc.reg_write(UC_ARM_REG_R4 + (r - 4), 0x1110 + r)
    uc.reg_write(UC_ARM_REG_SP, sp)
    uc.reg_write(UC_ARM_REG_LR, SENT | 1)
    uc.emu_start(fn | 1, SENT, count=5_000_000)
    assert uc.reg_read(UC_ARM_REG_PC) == SENT, f"{fn:#x}: stopped at {uc.reg_read(UC_ARM_REG_PC):#x}"
    assert [uc.reg_read(UC_ARM_REG_R4 + (r - 4)) for r in range(4, 12)] == [0x1110 + r for r in range(4, 12)], f"{fn:#x}: r4-r11"
    assert uc.reg_read(UC_ARM_REG_SP) == sp, f"{fn:#x}: sp"


def counters(uc):
    phase = struct.unpack("<Q", uc.mem_read(CLOCK + 0x28, 8))[0]
    acc = struct.unpack("<I", uc.mem_read(CLOCK + 0x34, 4))[0]
    return phase, acc, uc.mem_read(CLOCK + 0x20, 1)[0]


def run(fw, ram, ms, heap_past=False, start=True, block=False):
    uc = machine(fw, ram)
    if block:
        uc.mem_write(rhstate.HEAP_LIMIT_PTR, struct.pack("<I", rhstate.ST))
        uc.mem_write(rhstate.ST, bytes(rhstate.SIZE))
        uc.mem_write(rhstate.ST, struct.pack("<I", rhstate.MAGIC))
    if heap_past:
        uc.mem_write(rhstate.HEAP_CUR_PTR, struct.pack("<I", playfix.FIXST + 4))
    uc.mem_write(playfix.UWTICK, struct.pack("<I", 1000))
    if start:
        call(uc, SETMODE, CLOCK, 0)
        call(uc, TICK, 0, CLOCK)                            # the start tick
    else:
        uc.mem_write(CLOCK + 0x56, b"\x03")                 # already running (not through state 1)
    first, out = counters(uc), []
    for m in ms:
        uc.mem_write(playfix.UWTICK, struct.pack("<I", 1000 + m))
        call(uc, TICK, 0, CLOCK)
        out.append(counters(uc))
    return uc, first, out


def main():
    stock, built, ram = (open(p, "rb").read() for p in sys.argv[1:4])
    blk = "--block" in sys.argv
    state = rhstate.ST + rhstate.OFF["playfix"][0] if blk else playfix.FIXST
    ok = True

    us, s0, s = run(stock, ram, BURST, block=blk)
    ub, b0, b = run(built, ram, BURST, block=blk)
    armed, h0, n, held = struct.unpack("<4I", ub.mem_read(state, 16))
    print(f"burst case: {len(BURST)} ticks after the start tick; built: held {held}, armed {armed} (0: off after {playfix.WINDOW} ms), N {n}; start tick equal: {s0 == b0}")
    ok &= s0 == b0 and held > 0 and armed == 0
    # after k advances the built counters must be the stock's after k ticks; k <= ms since start + 1
    k, prev = 0, b0
    for i, m in enumerate(BURST):
        if b[i] != prev:
            k += 1
        prev = b[i]
        want = s[k - 1] if k else s0
        good = b[i] == want and k <= m + 1
        ok &= good
        if i < 30 or not good:
            print(f"  tick {i:2d} at {m:2d} ms: stock pulses {s[i][2]:2d} | built pulses {b[i][2]:2d}, advances {k:2d}"
                  f"{'' if good else '  FAIL'}")
    print(f"  built == stock {held} ticks earlier at the end: {b[-1] == s[-1 - held]}")
    ok &= b[-1] == s[-1 - held]

    cases = [("running without a start (external clock path)", dict(start=False, block=blk))]
    cases.append(("the block not set up", dict(block=False)) if blk else ("heap past the fix state", dict(heap_past=True)))
    for name, kw in cases:
        _, _, s2 = run(stock, ram, BURST, **kw)
        _, _, b2 = run(built, ram, BURST, **kw)
        same = s2 == b2
        print(f"{name}: built == stock on every tick: {same}")
        ok &= same
    print("ALL PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
