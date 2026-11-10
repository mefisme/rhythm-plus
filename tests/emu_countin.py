"""Emulation of the count-in (tools/countin.py) with our RAM block (ourram.py) on a built image, against the stock.

    python tests/emu_countin.py STOCK.bin BUILT.bin RAM.bin        (RAM.bin: a RAM dump read with tools/rhremote.py)

RH_BUILD (default stci9) names the build folder whose manifest is read.  In a build with clkci the count is clkci's (emu_clkci.py).

The block's setup; Shift + Clear through the four states; buttons the count-in does not take behave as the stock; a full count (clicks,
the Record LED, the Play press at the end); the count cancelled by Play or by a start from elsewhere; Shift + Play kept through the count;
cibpm's count at an external clock's tempo; vismet's Clear flash on each click at level 0; errled's blink when a check fails.
The click level (master parameter 9) is set by a hook on its getter; its real getter is read once from the dump.
"""
import json
from functools import lru_cache
import os
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
MAN = json.loads((HERE / "firmware" / os.environ.get("RH_BUILD", "stci9") / "manifest.json").read_text())
os.environ["RH_STOCKPLUS"] = "1" if "stockplus" in MAN["report"] else "0"     # (ourram's layout: Stock+'s slots first)
os.environ["RH_TMCLICK"] = str(MAN["report"].get("tmenu", {}).get("tmclick", int(bool(MAN["report"].get("tmenu", {}).get("click")))))
os.environ["RH_PAGECLEAR"] = "1" if MAN["report"].get("pageclear") else "0"
os.environ["RH_TRACKRESET"] = "1" if MAN["report"].get("trackreset") else "0"
os.environ["RH_GRAIN"] = "1" if "grain" in MAN["report"] else "0"
os.environ["RH_PSHAPE"] = "1" if "pshape" in MAN["report"] else "0"
os.environ["RH_FSHAPE"] = "1" if "fshape" in MAN["report"] else "0"
os.environ["RH_UPGUARD"] = "1" if "upguard" in MAN["report"] else "0"
os.environ["RH_MUTSET"] = ("2" if MAN["report"]["mutset"].get("mutate") else "1") if "mutset" in MAN["report"] else "0"
import ourram  # noqa: E402,F401
import countin as C  # noqa: E402
import rhstate  # noqa: E402
from ciearly import EARLY_MS  # noqa: E402
from emu_playfix import RAM, call, machine  # noqa: E402
from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1  # noqa: E402

L = {k: int(v, 16) for k, v in MAN["report"]["countin"]["labels"].items()}
C_RST = int(MAN["report"]["rhstate"]["labels"]["c_rst"], 16)
C_ERLED = int(MAN["report"].get("errled", {}).get("labels", {}).get("c_erled", "0"), 16)
ST, SIZE, TOP = rhstate.ST, rhstate.SIZE, rhstate.HEAP_LIMIT
CI = ST + rhstate.OFF["countin"][0]
VM = ST + rhstate.OFF["vismet"][0]
CLOCK, CLK_EXT, METRO_OBJ, METRO_FN = 0x200126E8, 0x48, 0x2003C200, 0x080333AA
PUSH = 0x08046D0C                                # the stock's filter push(filter, time)
FRAME = 0x2004FF00 - 0x200                       # a scratch frame of 69 halfwords in the dump's unused stack area
LEDTASK = 0x0803E80C
DELAY = 0x08024150                               # the RTOS delay(ms): it waits for ticks the emulation never makes
GETTER, GRP_MASTER, IDX_CLICK = 0x08046410, 0x21, 9
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        fails.append(name)


def u32(uc, a): return struct.unpack("<I", uc.mem_read(a, 4))[0]
def w32(uc, a, v): uc.mem_write(a, struct.pack("<I", v))


def setp(uc, store, i, v):
    """Parameter i of a store set in both copies (no commit, no listeners)."""
    for o in (0xC, 0x10):
        uc.mem_write(u32(uc, store + o) + 4 * i, bytes([v]))


def newest(uc, store, i):
    call(uc, C.PARAM_NEW, store, i)
    return uc.mem_read(uc.reg_read(UC_ARM_REG_R0), 1)[0]


def shift_store(uc): return u32(uc, C.CTRL + 0xC)
def state(uc): return (newest(uc, C.METRO_STORE, 3) & 1) | (2 if uc.mem_read(CI + 0, 1)[0] == C.CI_ON else 0)
def tick(uc, t): w32(uc, C.HAL_TICK, t)


class Log:
    """Hooks: the click, the stock's button press and release, the stock LED task, the delay (all return at once); the click level's
    getter returns self.level."""
    def __init__(self, uc, built, level=64):
        self.clicks, self.press, self.release = [], [], []
        self.uc, self.level = uc, level

        def lvl(u, a, s, d):
            if u.reg_read(UC_ARM_REG_R0) == GRP_MASTER and u.reg_read(UC_ARM_REG_R1) == IDX_CLICK:
                u.reg_write(UC_ARM_REG_R0, self.level)
                u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
        uc.hook_add(UC_HOOK_CODE, lvl, None, GETTER, GETTER + 1)
        stops = {C.CLICK: self.clicks, C.BTN_RELEASE: self.release, LEDTASK: None, DELAY: None}
        stops[L["c_cibtn_stock"] if built else C.BTN_ENTRY] = self.press

        def hk(u, a, s, d):
            if a in stops:
                lst = stops[a]
                if lst is not None:
                    shift = newest_raw(u)
                    lst.append((u32(u, C.HAL_TICK), u.reg_read(UC_ARM_REG_R1), shift))
                u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
        for a in stops:
            uc.hook_add(UC_HOOK_CODE, hk, None, a, a + 1)


def newest_raw(uc):
    """Shift's newest byte, read without a call (safe inside a hook)."""
    s = shift_store(uc)
    act = u32(uc, s + 4) & 1
    return uc.mem_read(u32(uc, s + (0x10 if act else 0xC)), 1)[0]


def setup(fw, ram, built, level=64):
    uc = machine(fw, ram)
    log = Log(uc, built, level)
    tick(uc, 10000)
    if built:
        call(uc, C_RST)
    return uc, log


def press(uc, bid): call(uc, C.BTN_ENTRY, C.CTRL, bid)


@lru_cache(maxsize=8)
def led_target(site, code):
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    ins = next(Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(code, site))
    assert ins.mnemonic == "bl"
    return int(ins.op_str.lstrip("#"), 0)


def led(uc):
    # Follow the actual patched call, including builds without the error reporter.
    site = C.LED_CALLS[0]
    call(uc, led_target(site, bytes(uc.mem_read(site, 4))), C.CTRL, FRAME)


def test_block(fw, ram):
    uc = machine(fw, ram)
    uc.mem_write(ST, b"\xAA" * SIZE)
    around = bytes(uc.mem_read(ST - 64, 64)) + bytes(uc.mem_read(TOP, 64))
    call(uc, C_RST)
    r0 = uc.reg_read(UC_ARM_REG_R0)
    check("block: c_rst returns the block", r0 == ST, hex(r0))
    check("block: heap limit lowered to the block", u32(uc, rhstate.HEAP_LIMIT_PTR) == ST)
    check("block: magic at its lowest word", u32(uc, ST) == rhstate.MAGIC)
    check("block: the rest zeroed", bytes(uc.mem_read(ST + 4, SIZE - 4)) == bytes(SIZE - 4))
    check("block: memory around it untouched", bytes(uc.mem_read(ST - 64, 64)) + bytes(uc.mem_read(TOP, 64)) == around)
    check("block: heap's current pointer untouched", u32(uc, rhstate.HEAP_CUR_PTR) == 0x2004EA98)
    uc.mem_write(CI, b"\x55")
    call(uc, C_RST)
    check("block: a second call keeps the contents", uc.reg_read(UC_ARM_REG_R0) == ST and uc.mem_read(CI, 1)[0] == 0x55)
    uc = machine(fw, ram)
    w32(uc, rhstate.HEAP_CUR_PTR, ST + 4)
    call(uc, C_RST)
    check("block: heap already past it -> off, limit kept", uc.reg_read(UC_ARM_REG_R0) == 0 and u32(uc, rhstate.HEAP_LIMIT_PTR) == TOP)
    uc = machine(fw, ram)
    w32(uc, rhstate.HEAP_LIMIT_PTR, TOP - 0x100)
    call(uc, C_RST)
    check("block: unexpected limit -> off", uc.reg_read(UC_ARM_REG_R0) == 0 and u32(uc, rhstate.HEAP_LIMIT_PTR) == TOP - 0x100)


def test_cycle(fw, ram):
    uc, log = setup(fw, ram, True)
    setp(uc, shift_store(uc), 0, 1)
    s0, seen = state(uc), []
    for _ in range(5):
        press(uc, C.ID_CLEAR)
        seen.append(state(uc))
    want = [(s0 + k) % 4 for k in range(1, 6)]
    check("Shift + Clear: four states in turn", seen == want, f"{seen} != {want}")
    check("Shift + Clear: never reaches the stock", not log.press)
    for s in range(4):
        while state(uc) != s:
            press(uc, C.ID_CLEAR)
        uc.mem_write(FRAME, bytes(140))
        led(uc)
        col = struct.unpack("<H", uc.mem_read(FRAME + 2 * C.LED_CLEAR, 2))[0]
        check(f"Shift held: the Clear LED shows state {s}", col == C.COLS[s], hex(col))
    setp(uc, shift_store(uc), 0, 0)
    uc.mem_write(FRAME, bytes(140))
    led(uc)
    check("Shift up, no count: the LED frame untouched", bytes(uc.mem_read(FRAME, 140)) == bytes(140))


def ram_except_block(uc):
    r = bytearray(uc.mem_read(RAM, 0x50000))
    for a, n in ((ST, SIZE), (rhstate.HEAP_LIMIT_PTR, 4)):
        r[a - RAM:a - RAM + n] = bytes(n)
    return bytes(r)


def test_passthrough(stock, fw, ram):
    def run(img, built, prep, bid):
        uc, log = setup(img, ram, built)
        prep(uc, built)
        press(uc, bid)
        return ram_except_block(uc), log.press

    def ci(on, play=0, rec=0, shift=0):
        def prep(uc, built):
            if built and on:
                uc.mem_write(CI, bytes([C.CI_ON]))
            setp(uc, C.TRANSPORT, 0, play)
            setp(uc, C.TRANSPORT, 1, rec)
            setp(uc, shift_store(uc), 0, shift)
        return prep
    cases = [("Clear without Shift", ci(True), C.ID_CLEAR),
             ("Play, count-in off, Record armed", ci(False, rec=1), C.ID_PLAY),
             ("Play, count-in on, Record not armed", ci(True), C.ID_PLAY),
             ("Play, count-in on, already playing", ci(True, play=1, rec=1), C.ID_PLAY),
             ("Record, count-in on", ci(True), 16),
             ("track button 1, count-in on", ci(True), 0)]
    for name, prep, bid in cases:
        rs, ps = run(stock, False, prep, bid)
        rb, pb = run(fw, True, prep, bid)
        diff = [hex(RAM + i) for i in range(len(rs)) if rs[i] != rb[i]][:6]
        check(f"as stock: {name}", not diff and len(ps) == len(pb) == 1, f"RAM differs at {diff}, presses {len(ps)}/{len(pb)}")
    uc, log = setup(fw, ram, True)
    w32(uc, C.CTRL, 0)
    setp(uc, shift_store(uc), 0, 1)
    press(uc, C.ID_CLEAR)
    check("controller not where expected: Shift + Clear goes to the stock", len(log.press) == 1)


def pulses(uc, bpm, now, there=True, age=0):
    """An external clock at bpm while stopped: 49 pulse times in the clock's filter, the last one age ms before now; the external
    bit as there; the clock's external flag (set only at Play) left at 0."""
    flags = uc.mem_read(CLOCK + 0x54, 1)[0]
    uc.mem_write(CLOCK + 0x54, bytes([flags | 2 if there else flags & ~2]))
    setp(uc, u32(uc, CLOCK + CLK_EXT), 0, 0)
    last = now - age
    for k in range(48, -1, -1):
        call(uc, PUSH, u32(uc, CLOCK + 0x7C), round(last - k * 60000 / (24 * bpm)))
    w32(uc, CLOCK + 0x64, now)


def counting(fw, ram, bpm=None, shift=False, ext=None, level=64, there=True, age=0):
    """ext: an external clock's BPM, measured while stopped (pulses())."""
    uc, log = setup(fw, ram, True, level)
    uc.mem_write(CI, bytes([C.CI_ON]))
    setp(uc, C.TRANSPORT, 0, 0)
    setp(uc, C.TRANSPORT, 1, 1)
    setp(uc, shift_store(uc), 0, 1 if shift else 0)
    if bpm is not None:
        setp(uc, C.TEMPO, 0, bpm)
    if ext is not None:
        pulses(uc, ext, 300000, there, age)
    live = ext is not None and there and age <= 1600
    b = ext if live and 40 <= ext <= 240 else newest(uc, C.TEMPO, 0)
    beat = 60000 // (b if b >= 30 else 120)
    press(uc, C.ID_PLAY)
    if shift:
        setp(uc, shift_store(uc), 0, 0)
    return uc, log, beat


def test_count(fw, ram):
    for bpm, ext, there, age in ((None, None, 1, 0), (20, None, 1, 0), (200, None, 1, 0), (90, 150, 1, 0), (90, 97, 1, 1500),
                                 (90, 250, 1, 0), (90, 39, 1, 0), (90, 150, 0, 0), (90, 150, 1, 1700)):
        uc, log, beat = counting(fw, ram, bpm, ext=ext, there=there, age=age)
        tag = f"count at {60000 // beat} BPM" + (f" (external clock {ext}{'' if there else ' gone'}, last pulse {age} ms ago)"
                                                 if ext is not None else "")
        check(f"{tag}: the Play press is kept", not log.press and u32(uc, CI + 4) == 10000)
        rec_led = []
        for t in range(10000, 10000 + 5 * beat, 2):
            tick(uc, t)
            led(uc)
            if t < 10000 + 4 * beat - EARLY_MS:
                rec_led.append((t, struct.unpack("<H", uc.mem_read(FRAME + 2 * C.LED_REC, 2))[0]))
        clicks = [c[0] - 10000 for c in log.clicks]
        check(f"{tag}: 4 clicks on the beats", clicks == [k * beat for k in range(4)], f"{clicks}")
        presses = [(p[0] - 10000, p[1]) for p in log.press]
        check(f"{tag}: Play pressed once, {EARLY_MS} ms before the end of the bar", presses == [(4 * beat - EARLY_MS, C.ID_PLAY)], f"{presses}")
        check(f"{tag}: Play released once", len(log.release) == 1)
        check(f"{tag}: Record LED red the first 100 ms of each beat, else dark",
              all(v == (C.COL_REC if (t - 10000) % beat < 100 else 0) for t, v in rec_led))
        check(f"{tag}: state cleared after", u32(uc, CI + 4) == 0 and uc.mem_read(CI + 2, 1)[0] == 0)
        check(f"{tag}: clicks heard (level 64): no time kept, no flash", u32(uc, VM) == 0)

    for metro in (0, 1):
        uc, log, beat = counting(fw, ram, level=0)
        setp(uc, C.METRO_STORE, 3, metro)
        colour = C.COLS[2 + metro]
        flashes = []
        for t in range(10000, 10000 + 4 * beat, 2):
            tick(uc, t)
            uc.mem_write(FRAME + 2 * C.LED_CLEAR, bytes(2))   # the stock's LED task draws every frame anew
            led(uc)
            flashes.append(struct.unpack("<H", uc.mem_read(FRAME + 2 * C.LED_CLEAR, 2))[0] == colour)
        on = [10000 + 2 * k for k, f in enumerate(flashes) if f]
        want = [t for t in range(10000, 10000 + 4 * beat, 2) if (t - 10000) % beat < 100]
        name = "magenta" if metro == 0 else "cyan"
        check(f"{name}, click level 0: 4 clicks still sent (silent)", len(log.clicks) == 4)
        check(f"{name}, click level 0: Clear in {name} for 100 ms from each click", on == want, f"only flashed {sorted(set(on) - set(want))[:4]}, missing {sorted(set(want) - set(on))[:4]}, beat {beat}")

    uc, log, beat = counting(fw, ram)
    for t in range(10000, 10000 + 2 * beat, 2):
        tick(uc, t)
        led(uc)
    press(uc, C.ID_PLAY)
    for t in range(10000 + 2 * beat, 10000 + 6 * beat, 2):
        tick(uc, t)
        led(uc)
    check("Play during the count cancels it", len(log.clicks) == 2 and not log.press and u32(uc, CI + 4) == 0,
          f"clicks {len(log.clicks)}, presses {len(log.press)}")

    uc, log, beat = counting(fw, ram)
    for t in range(10000, 10000 + beat + beat // 2, 2):
        tick(uc, t)
        led(uc)
    setp(uc, C.TRANSPORT, 0, 1)
    for t in range(10000 + beat + beat // 2, 10000 + 6 * beat, 2):
        tick(uc, t)
        led(uc)
    check("a start from elsewhere cancels the count", len(log.clicks) == 2 and not log.press and u32(uc, CI + 4) == 0)

    uc, log, beat = counting(fw, ram, shift=True)
    for t in range(10000, 10000 + 5 * beat, 2):
        tick(uc, t)
        led(uc)
    check("Shift + Play: the end's press has Shift", [p[2] for p in log.press] == [1], f"{log.press}")
    check("Shift + Play: Shift up again after", newest(uc, shift_store(uc), 0) == 0 and uc.mem_read(CI + 3, 1)[0] == 0)


def test_errled(fw, ram):
    def clear_led(prep, t):
        uc = machine(fw, ram)
        Log(uc, True)
        prep(uc)
        tick(uc, t)
        uc.mem_write(FRAME, bytes(140))
        uc.mem_write(FRAME + 2 * C.LED_CLEAR, struct.pack("<H", 0x1234))
        led(uc)
        return struct.unpack("<H", uc.mem_read(FRAME + 2 * C.LED_CLEAR, 2))[0]
    on, off = 0x2800, 0x2900                              # bit 8 of the HAL tick: 0 red, 1 dark
    for t in (on, off):
        check(f"no error: the Clear LED untouched (t={t:#x})", clear_led(lambda uc: None, t) == 0x1234)
    cases = [("the RAM block cannot be set up", lambda uc: w32(uc, rhstate.HEAP_CUR_PTR, ST + 4)),
             ("the controller is not where expected", lambda uc: w32(uc, C.CTRL, 0)),
             ("the clock is not where expected", lambda uc: w32(uc, 0x200126E8, 0))]
    for name, prep in cases:
        got = (clear_led(prep, on), clear_led(prep, on + 0xFF), clear_led(prep, off), clear_led(prep, off + 0xFF))
        check(f"error, {name}: Clear LED red 256 ms, dark 256 ms", got == (C.COL_REC, C.COL_REC, 0, 0), f"{got}")


def test_vismet(stock, fw, ram):
    def metro(uc, on, pulse):
        setp(uc, u32(uc, METRO_OBJ + 0xC), 3, on)
        uc.mem_write(u32(uc, METRO_OBJ + 8) + 0x20, bytes([pulse]))
        args = []
        h = uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: args.append(tuple(u.reg_read(UC_ARM_REG_R0 + i) for i in range(3))),
                        None, C.CLICK, C.CLICK + 1)
        call(uc, METRO_FN, METRO_OBJ)
        uc.hook_del(h)
        return args

    def clear_led(uc, t, shift=0):
        tick(uc, t)
        setp(uc, shift_store(uc), 0, shift)
        uc.mem_write(FRAME, bytes(140))
        uc.mem_write(FRAME + 2 * C.LED_CLEAR, struct.pack("<H", 0x1234))
        led(uc)
        return struct.unpack("<H", uc.mem_read(FRAME + 2 * C.LED_CLEAR, 2))[0]

    uc = machine(fw, ram)
    call(uc, GETTER, GRP_MASTER, IDX_CLICK)
    lv = uc.reg_read(UC_ARM_REG_R0)
    check("the real getter returns a click level 0..127 from the dump", 0 <= lv <= 127, hex(lv))

    def as_stock(on, pulse, flag, level):
        out = []
        for img, built in ((stock, False), (fw, True)):
            uc, _ = setup(img, ram, built, level)
            if built:
                uc.mem_write(CI, bytes([flag]))
            tick(uc, 20000)
            got = metro(uc, on, pulse)
            out.append((got, ram_except_block(uc)))
            if built:
                kept = u32(uc, VM)
        return out[0] == out[1], kept
    for name, on, pulse, flag, level, kept_want in (("red, level 0", 0, 0, 0, 0, False),
                                                   ("green, level 64", 1, 0, 0, 64, False), ("green, level 0", 1, 24, 0, 0, True),
                                                   ("magenta, level 0", 0, 0, C.CI_ON, 0, True), ("magenta, level 64", 0, 24, C.CI_ON, 64, False),
                                                   ("cyan, level 64", 1, 48, C.CI_ON, 64, False), ("cyan, level 0", 1, 0, C.CI_ON, 0, True),
                                                   ("green, level 0, between beats", 1, 7, 0, 0, False), ("green, level 1", 1, 0, 0, 1, False)):
        same, kept = as_stock(on, pulse, flag, level)
        check(f"beat check, {name}: clicks and RAM as stock", same)
        check(f"beat check, {name}: " + ("the beat's time kept" if kept_want else "no time kept"),
              kept == (20000 if kept_want else 0), hex(kept))

    for name, on, flag, level, want in (("red", 0, 0, 0, None), ("green", 1, 0, 0, C.COLS[1]), ("magenta", 0, C.CI_ON, 0, C.COLS[2]), ("cyan", 1, C.CI_ON, 0, C.COLS[3]),
                                        ("green, level 64", 1, 0, 64, None)):
        uc, log = setup(fw, ram, True, level)
        uc.mem_write(CI, bytes([flag]))
        tick(uc, 20000)
        got = metro(uc, on, 0)
        check(f"{name}: the stock click, same arguments" if on else f"{name}: no click", got == ([(0xFF, 0, 0x60)] if on else []), f"{got}")
        if want is None:
            check(f"{name}: no flash", clear_led(uc, 20000) == 0x1234 and clear_led(uc, 20050) == 0x1234)
            continue
        check(f"{name}: Clear {name} 0 ms after the beat", clear_led(uc, 20000) == want)
        check(f"{name}: Clear {name} 99 ms after the beat", clear_led(uc, 20099) == want)
        check(f"{name}: Clear untouched 100 ms after the beat", clear_led(uc, 20100) == 0x1234)
        check(f"{name}: Shift held: the mode's colour", clear_led(uc, 20050, shift=1) == want)
        held = u32(uc, C.CTRL + 0xA0)
        w32(uc, C.CTRL + 0xA0, held | 1 << C.ID_CLEAR)
        check(f"{name}: Clear held: no flash", clear_led(uc, 20050) == 0x1234)
        w32(uc, C.CTRL + 0xA0, held)
        check(f"{name}: Clear let go within 100 ms: the flash again", clear_led(uc, 20060) == want)
        setp(uc, u32(uc, METRO_OBJ + 0xC), 3, 0)
        uc.mem_write(CI, bytes([0]))
        check(f"{name}: switched to red within 100 ms: no flash", clear_led(uc, 20050) == 0x1234)

    uc = machine(fw, ram)
    lg = Log(uc, True, 0)
    tick(uc, 20000)
    before = bytes(uc.mem_read(ST - 16, rhstate.SIZE + 32))
    got = metro(uc, 1, 0)
    check("block not set up: the stock click still runs", got == [(0xFF, 0, 0x60)])
    check("block not set up: nothing written", bytes(uc.mem_read(ST - 16, rhstate.SIZE + 32)) == before)

    uc, log = setup(fw, ram, True, 0)
    tick(uc, 0x5000)                                      # bit 8 clear: errled's red half
    metro(uc, 1, 0)
    check("no error, 20 ms after a silent beat: green", clear_led(uc, 0x5000 + 20) == C.COLS[1])
    if not C_ERLED:
        check("error reporter omitted: silent-beat indicator remains green", clear_led(uc, 0x5000 + 20) == C.COLS[1])
        return
    w32(uc, C.CTRL, 0)                                    # an error: errled's blink wins over the flash
    check("error, 20 ms after a silent beat: red, not green", clear_led(uc, 0x5000 + 20) == C.COL_REC and u32(uc, VM) == 0x5000)


def main():
    stock, built, ram = (open(p, "rb").read() for p in sys.argv[1:4])
    test_block(built, ram)
    test_cycle(built, ram)
    test_passthrough(stock, built, ram)
    if "clkci" not in MAN["report"]:                    # with clkci the count is clkci's (tests/emu_clkci.py)
        test_count(built, ram)
    test_vismet(stock, built, ram)
    if C_ERLED:
        test_errled(built, ram)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
