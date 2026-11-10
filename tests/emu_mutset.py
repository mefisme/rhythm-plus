"""Unicorn test of mutset.py on a build with it and the RAM dump: the Mutate settings page on the Patterns view (Shift + Duplicate held
opens it, a shorter press does not, Clear held never; a Duplicate press closes it; the settings in columns 3-6 in the probability
gradient, a pad a value, Down / Up the values 5-8 / 1-4, the Length bar by Length type; the track buttons switch tracks on / off; the
settings in the project's record with their check byte, the defaults from a block not ours; Shift + Patterns swallowed, Record / Clear /
Shift keep it open, other buttons close it; off the Patterns view it closes; closed, the pads are the stock's). With the mutate: the
lists of a Shift + Duplicate tap by the settings, the next-pattern hook (play, look-ahead, forced, a scene change), a pattern pad and
Clear + Shift + Duplicate end lists, Every chain end, the soft green track buttons.

    python tests/emu_mutset.py STOCK.bin BUILT.bin RAM.bin
"""
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("RH_BUILD", Path(sys.argv[2]).parent.name if len(sys.argv) > 2 else "a0097")
import emu_tmenu as ET  # noqa: E402  (ourram's layout from the build's manifest)
import mutset as M  # noqa: E402
from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_R0  # noqa: E402

check, u32, call, MAN = ET.check, ET.u32, ET.call, ET.MAN
C = ET.C
REP = MAN["report"]["mutset"]
SEEDS = REP.get("seeds", False)
if SEEDS:
    M.use_seeds()
if REP.get("livecol"):
    M.use_livecol()
LB = {k: int(v, 16) for k, v in REP["labels"].items()}
SLOT = int(REP["slot"], 16)
C_RRT = int(MAN["report"]["rhrec"]["labels"]["c_rrt"], 16)
SEEK = 0x080342E0                                         # the stock's seek(engine, track, time, flag): a track's pattern and step at time


def fl(uc): return uc.mem_read(SLOT + M.O_FL, 1)[0]
def page(uc): return uc.mem_read(SLOT + M.O_PAGE, 1)[0]
def is_open(uc): return fl(uc) & M.FL_OPEN == 1


def blk(uc):
    call(uc, C_RRT)
    return uc.reg_read(UC_ARM_REG_R0) + M.BLK_OFF


def block(uc): return bytes(uc.mem_read(blk(uc), M.BLK_LEN))


def ours(b):
    return b[0] == M.MARK0 and b[1] == M.MARK1 and b[2] == (sum(b[M.B_VAL:]) & 0xFF) ^ M.CHECK


def vals(uc):
    """the settings as the page reads them: Length 1-8, Length type, Pool, When, the tracks off"""
    b = block(uc)
    v = list(b[M.B_VAL:M.B_VAL + 5]) if ours(b) else [0] * 5
    return [(v[0] ^ M.LEN_X) + 1] + v[1:]


def set_shift(uc, on):
    uc.mem_write(ET.ptr(uc, u32(uc, C.CTRL + 0xC), 0), bytes([on]))


def set_clear(uc, on):
    h = u32(uc, C.CTRL + M.O_HELD) & ~(1 << M.BIT_CLEAR) | on << M.BIT_CLEAR
    uc.mem_write(C.CTRL + M.O_HELD, struct.pack("<I", h))


def lights(uc):
    ET.led(uc, ET.PREV_LED)
    return ET.out(uc, LB["c_msout"])


def want_page(uc, pulse_hi):
    w = {}
    ln, lt, pool, when, off = vals(uc)
    pg = page(uc)
    for t in range(8):
        tc = u32(uc, M.COLOURS + 4 * M.TRK_SLOTS[t])
        w[M.LED_TRK0 + t] = ET.scl(tc, M.VDIM) if off >> t & 1 else tc
    for c in range(8):
        for r in range(4):
            w[8 * r + c] = 0
    chosen = (ln - 1, lt, pool, when)
    for k, (c, n) in enumerate(zip(M.COLS, M.NVAL)):
        col = u32(uc, M.COLOURS + 4 * (M.GRAD0 + c))
        for r in range(4):
            v = 4 * pg + r
            if k == 0:
                w[8 * r + c] = (ET.scl(col, M.VDIM) if lt == 0 else ET.scl(col, M.DIM) if v > chosen[0] else
                                col if lt == 1 or v == chosen[0] else ET.scl(col, M.HALF if REP.get("randfill") else M.DIM))
            else:
                w[8 * r + c] = 0 if v >= n else col if v == chosen[k] else ET.scl(col, M.DIM)
    if REP.get("amount") and pg == 1:
        b = block(uc)
        amt = b[M.B_VAL2] & M.AM_MASK if ours(b) else 0
        for r in range(4):
            col = u32(uc, M.COLOURS + 4 * (M.GRAD0 + M.AM_CODES[r]))
            w[8 * r + M.AM_COL] = col if r >= amt else ET.scl(col, M.DIM)
        if REP.get("norep"):
            g = u32(uc, M.COLOURS + 4 * M.GREEN)
            off = b[M.B_VAL2] >> M.NR_BIT & 1 if ours(b) else 0
            w[M.NR_COL] = ET.scl(g, M.DIM) if off else g
            w[8 + M.NR_COL] = g if off else ET.scl(g, M.DIM)
        if REP.get("keep1"):
            g = u32(uc, M.COLOURS + 4 * M.GREEN)
            on = b[M.B_VAL2] >> M.K1_BIT & 1 if ours(b) else 0
            w[M.K1_COL] = ET.scl(g, M.DIM) if on else g
            w[8 + M.K1_COL] = g if on else ET.scl(g, M.DIM)
        if REP.get("live") and not REP.get("livecol"):
            g = u32(uc, M.COLOURS + 4 * M.GREEN)
            on = b[M.B_VAL2] >> M.LV_BIT & 1 if ours(b) else 0
            w[M.LV_COL] = ET.scl(g, M.DIM) if on else g
            w[8 + M.LV_COL] = g if on else ET.scl(g, M.DIM)
    if REP.get("livecol"):                                # Live on column 1 of both pages
        b = block(uc)
        g = u32(uc, M.COLOURS + 4 * M.GREEN)
        on = b[M.B_VAL2] >> M.LV_BIT & 1 if ours(b) else 0
        w[M.LV_COL] = ET.scl(g, M.DIM) if on else g
        w[8 + M.LV_COL] = g if on else ET.scl(g, M.DIM)
    w[M.LED_DOWN], w[M.LED_UP] = (M.WHITE, 0) if pg == 0 else (0, M.WHITE)
    if REP.get("greendup"):
        g = u32(uc, M.COLOURS + 4 * M.GREEN)
        p = uc.mem_read(M.COLOURS + 4 * M.FRAME_PULSE, 1)[0]
        w[M.LED_DUP] = g if u32(uc, C.CTRL + M.O_HELD) >> M.BIT_DUPH & 1 else ET.scl(g, 64 + ((255 - p) * 192 >> 8))
    else:
        g = u32(uc, M.COLOURS + 4 * (M.PULSE if REP.get("mutate") else M.GREEN))
        w[M.LED_DUP] = g if pulse_hi else ET.scl(g, M.PULSE_LO)
    return w


def page_ok(uc, name):
    for hi in (1, 0):
        t = u32(uc, C.HAL_TICK) & ~(1 << 9) | hi << 9
        uc.mem_write(C.HAL_TICK, struct.pack("<I", t))
        if REP.get("greendup"):
            uc.mem_write(M.COLOURS + 4 * M.FRAME_PULSE, bytes([0 if hi else 200]))
        o, w = lights(uc), want_page(uc, hi)
        bad = [(i, f"{o[i]:06x}", f"{v:06x}") for i, v in w.items() if o[i] != v]
        check(f"{name} (Duplicate's pulse {'up' if hi else 'down'})", not bad, bad[:4])


def hold_open(uc):
    set_shift(uc, 1)
    ET.press(uc, M.ID_DUP); ET.tick(uc, 400); lights(uc); ET.release(uc, M.ID_DUP)
    set_shift(uc, 0)


def main():
    fw, ram = Path(sys.argv[2]).read_bytes(), Path(sys.argv[3]).read_bytes()
    uc = ET.setup(fw, ram)
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    vt = lambda k: u32(uc, M.PV_VT + 4 * k)
    check("the Patterns view's pad press / release slots are ours", vt(0) == LB["c_mspad"] | 1 and vt(1) == LB["c_mspr"] | 1)
    import rhbuild
    stock = Path(sys.argv[1]).read_bytes()
    sw = lambda a: int.from_bytes(stock[a - rhbuild.BASE:a - rhbuild.BASE + 4], "little") & ~1
    stock_pads = []
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: stock_pads.append("press"), None, sw(M.PV_VT), sw(M.PV_VT) + 1)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: stock_pads.append("release"), None, sw(M.PV_VT + 4), sw(M.PV_VT + 4) + 1)
    held = lambda: u32(uc, C.CTRL + M.O_HELD) >> 24 & 1

    b0 = block(uc)
    check("the dump's block is not ours: the defaults (Length 4, Same as the chain, With steps, On the tap, all tracks on)",
          not ours(b0) and vals(uc) == [4, 0, 0, 0, 0], (b0[:12].hex(), vals(uc)))
    o = lights(uc)
    check("closed, no Shift: Duplicate's light the stock's (dark)", o[M.LED_DUP] == 0, f"{o[M.LED_DUP]:06x}")
    set_shift(uc, 1)
    o = lights(uc)
    if REP.get("greendup"):
        tan = ET.scl(u32(uc, M.COLOURS + 4 * M.GREEN), M.DUP_DIM)
        check(f"closed, Shift held: Duplicate dim green ({tan:06x})", o[M.LED_DUP] == tan, f"{o[M.LED_DUP]:06x}")
    else:
        tan = u32(uc, M.COLOURS + 4 * M.SHIFT_DIM)
        check(f"closed, Shift held: Duplicate the stock's dim Shift tan ({tan:06x})", o[M.LED_DUP] == tan, f"{o[M.LED_DUP]:06x}")
    ET.press(uc, M.ID_DUP)
    check("  Shift + Duplicate: the stock's Duplicate held bit set", held() == 1)
    if REP.get("mutate"):
        o = lights(uc)
        lit = u32(uc, M.COLOURS + 4 * (M.GREEN if REP.get("greendup") else M.SHIFT_BRT))
        check(f"  while it is down: Duplicate {'full green' if REP.get('greendup') else 'the stock lit Shift tan'} ({lit:06x})",
              o[M.LED_DUP] == lit, f"{o[M.LED_DUP]:06x}")
    ET.tick(uc, 150); lights(uc)
    ET.release(uc, M.ID_DUP); lights(uc)
    check("  a 150 ms press: the page stays closed, the stock's bit clear again", not is_open(uc) and held() == 0, fl(uc))
    set_clear(uc, 1)
    ET.press(uc, M.ID_DUP); ET.tick(uc, 600); lights(uc); ET.release(uc, M.ID_DUP); lights(uc)
    check("  Clear + Shift + Duplicate held 600 ms: the page stays closed", not is_open(uc), fl(uc))
    set_clear(uc, 0)
    ET.press(uc, M.ID_DUP); ET.tick(uc, 200); lights(uc)
    check("  held 200 ms: not open yet", not is_open(uc))
    ET.tick(uc, 200); lights(uc)
    check(f"  held 400 ms ({M.HOLD_MS} ms the hold): the page opens while held", is_open(uc))
    ET.tick(uc, 400); lights(uc)
    ET.release(uc, M.ID_DUP); lights(uc)
    check("  held longer, then let go: still open", is_open(uc))
    set_shift(uc, 0)
    page_ok(uc, "  the lights: the defaults (the Length column very dim, the other 3 columns' top value full), all tracks full, "
                "Down white, Duplicate pulsing")

    stock_pads.clear()
    ET.pad(uc, 8 * 1 + 3); ET.unpad(uc, 8 * 1 + 3)
    check("column 4, row 2: Length type Exact; the stock's pad press / release not reached; the block now ours",
          vals(uc)[1] == 1 and not stock_pads and ours(block(uc)), (vals(uc), stock_pads))
    page_ok(uc, "  the Length bar full to 4, dim below")
    ET.pad(uc, 8 * 1 + 2); ET.unpad(uc, 8 * 1 + 2)
    check("column 3, row 2: Length 2", vals(uc)[0] == 2, vals(uc))
    ET.pad(uc, 8 * 2 + 3); ET.unpad(uc, 8 * 2 + 3)
    check("column 4, row 3: Length type Random", vals(uc)[1] == 2, vals(uc))
    page_ok(uc, "  Random: row 2 full, the others dim")
    for p in (8 * 1 + 4, 8 * 1 + 5):
        ET.pad(uc, p); ET.unpad(uc, p)
    check("columns 5 and 6, row 2: Pool All, When Every chain end", vals(uc)[2:4] == [1, 1], vals(uc))
    stock_pads.clear()
    before = vals(uc)
    for p in (8 * 2 + 4, 8 * 3 + 5, 8 * 2 + 0, 8 * 0 + 7):
        ET.pad(uc, p); ET.unpad(uc, p)
    check("pads with no value (column 5 row 3, column 6 row 4, columns 1 and 8): nothing changes, the stock not reached",
          vals(uc) == before and not stock_pads and ours(block(uc)), (vals(uc), stock_pads))
    ET.press(uc, M.ID_DOWN); ET.release(uc, M.ID_DOWN)
    check("Down: values 5-8", page(uc) == 1)
    page_ok(uc, "  page 2: the Length column (dim)" + (", the Amount meter (All)" if REP.get("amount") else " only") + ", Up white")
    ET.pad(uc, 8 * 2 + 2); ET.unpad(uc, 8 * 2 + 2)
    check("  column 3, row 3: Length 7", vals(uc)[0] == 7, vals(uc))
    page_ok(uc, "  Random on page 2: row 3 full, the others dim")
    ET.pad(uc, 8 * 0 + 3); ET.unpad(uc, 8 * 0 + 3)
    check("  column 4 on page 2: Length type kept" + (" (row 1: Amount All, as it was)" if REP.get("amount") else " (no value)"),
          vals(uc)[1] == 2 and (not REP.get("amount") or block(uc)[M.B_VAL2] & M.AM_MASK == 0), vals(uc))
    ET.press(uc, M.ID_UP); ET.release(uc, M.ID_UP)
    check("Up: values 1-4 again", page(uc) == 0)

    for t in (2, 2, 6):
        ET.press(uc, t); ET.release(uc, t)
    check("track 3 tapped twice, track 7 once: track 7 off, track 3 on; the view kept", vals(uc)[4] == 1 << 6 and ours(block(uc))
          and u32(uc, C.CTRL + M.O_VIEW) == M.PV, vals(uc))
    page_ok(uc, "  track 7's button very dim")
    set_shift(uc, 1)
    ET.press(uc, M.ID_PATTERNS); ET.release(uc, M.ID_PATTERNS)
    set_shift(uc, 0)
    check("Shift + Patterns: swallowed, the page open", is_open(uc) and u32(uc, C.CTRL + M.O_VIEW) == M.PV)
    for k in M.KEEP:
        if k == C.ID_PLAY:
            continue
        ET.press(uc, k); ET.release(uc, k)
        check(f"button {k}: the page stays open", is_open(uc))
    set_shift(uc, 0); set_clear(uc, 0)
    ET.press(uc, M.ID_DUP)
    check("a Duplicate press: the page closes", not is_open(uc))
    ET.tick(uc, 600); lights(uc); ET.release(uc, M.ID_DUP); lights(uc)
    check("  held 600 ms after: it stays closed", not is_open(uc), fl(uc))
    stock_pads.clear()
    ET.pad(uc, 5); ET.unpad(uc, 5)
    check("closed: a pad reaches the stock's press and release", stock_pads == ["press", "release"], stock_pads)

    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    hold_open(uc)
    check("held again: open on values 1-4, the settings kept", is_open(uc) and page(uc) == 0 and vals(uc) == [7, 2, 1, 1, 1 << 6],
          vals(uc))
    ET.press(uc, 10); ET.release(uc, 10)
    check("another button (10): the page closes", not is_open(uc))
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    hold_open(uc)
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", ET.T.CONT))
    lights(uc)
    check("off the Patterns view: the page closes", not is_open(uc))
    uc.mem_write(blk(uc) + 2, bytes([block(uc)[2] ^ 1]))
    check("a wrong check byte: the defaults again", vals(uc) == [4, 0, 0, 0, 0], vals(uc))
    if REP.get("mutate"):
        mutate_tests(uc, stock_pads)
    print("ALL PASS" if not ET.FAILS else f"{len(ET.FAILS)} FAILED")


import emu_playfix as PF  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_R3, UC_ARM_REG_R8, UC_ARM_REG_R2, UC_ARM_REG_R11, UC_ARM_REG_SP, UC_ARM_REG_LR  # noqa: E402

KEEP_REGS = {3: 0x2223, 4: 0x2224, 5: 0x2225, 6: 0x2226, 7: 0x2227, 9: 0x2229, 10: 0x222A}


def reg(r): return UC_ARM_REG_R3 + (r - 3) if r < 8 else UC_ARM_REG_R8 + (r - 8)


def nxt(uc, t, ch, first, last, forced=0, scene=0, la=0, sc=0):
    """the track advance's call at 0x08034E06 -> the next pattern (r2, also in [sp + 1])"""
    sp = PF.STACK + 0xE0000
    fr = bytearray(0x50)
    fr[0], fr[1], fr[2], fr[0x18], fr[0x44], fr[0x48] = t, ch, last, forced, scene, sc
    uc.mem_write(sp, bytes(fr))
    for r, v in KEEP_REGS.items():
        uc.reg_write(reg(r), v)
    uc.reg_write(UC_ARM_REG_R8, first)
    uc.reg_write(UC_ARM_REG_R11, la)
    uc.reg_write(UC_ARM_REG_SP, sp)
    uc.reg_write(UC_ARM_REG_LR, PF.SENT | 1)
    uc.emu_start(LB["c_mtnext"] | 1, PF.SENT, count=2_000_000)
    assert all(uc.reg_read(reg(r)) == v for r, v in KEEP_REGS.items()), "c_mtnext: r3-r7, r9, r10"
    assert uc.reg_read(UC_ARM_REG_R8) == first and uc.reg_read(UC_ARM_REG_R11) == la and uc.reg_read(UC_ARM_REG_SP) == sp, "c_mtnext"
    r2 = uc.reg_read(UC_ARM_REG_R2)
    assert uc.mem_read(sp + 1, 1)[0] == r2, "c_mtnext: [sp + 1] = r2"
    return r2


def lst(uc, t):
    if SEEDS:
        call(uc, LB["c_mtls"])
        b = bytes(uc.mem_read(SLOT + M.O_LISTS + M.LIST_LEN * t, M.LIST_LEN))
        return list(b[1:1 + b[0]])
    b = block(uc)
    o = M.B_LISTS + M.LIST_LEN * t
    return list(b[o + 1:o + 1 + b[o]])


GEN_AT = PF.STACK + 0xC0000                               # (seeds) c_mtgen's list, in the test's own RAM


def key_of(uc, t): return struct.unpack_from("<I", block(uc), M.B_KEYS + 4 * t)[0]


def mk(seed, n, typ=1, pool=1, first=0, last=0, val2=0):
    """(seeds) a key: Length n, Length type (1 Exact), Pool (1 All), the page 2 bits, the chain"""
    return seed | (n - 1) << 12 | typ << 15 | pool << 17 | val2 << 18 | first << 22 | last << 25


def gen(uc, t, key):
    """(seeds) the list a key makes for track t"""
    uc.mem_write(GEN_AT, bytes(M.LIST_LEN))
    call(uc, LB["c_mtgen"], t, key, GEN_AT)
    b = bytes(uc.mem_read(GEN_AT, M.LIST_LEN))
    return list(b[1:1 + b[0]])


def set_key(uc, t, key):
    """(seeds) the block's key of track t (the block made ours)"""
    b = bytearray(block(uc))
    if not ours(b):
        b = bytearray(M.BLK_LEN)
        b[0], b[1] = M.MARK0, M.MARK1
    struct.pack_into("<I", b, M.B_KEYS + 4 * t, key)
    b[2] = (sum(b[M.B_VAL:]) & 0xFF) ^ M.CHECK
    uc.mem_write(blk(uc), bytes(b))


def renew(uc): return block(uc)[M.B_RENEW]
def pos(uc, t): return uc.mem_read(SLOT + M.O_POS + t, 1)[0]


def tap(uc, clear=False):
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    set_clear(uc, int(clear))
    set_shift(uc, 1)
    ET.press(uc, M.ID_DUP); ET.tick(uc, 100); lights(uc); ET.release(uc, M.ID_DUP)
    set_shift(uc, 0)
    set_clear(uc, 0)


def setting(uc, col, value):
    """a setting's value by its pad (the page opened and closed around it)"""
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    hold_open(uc)
    if value >= 4:
        ET.press(uc, M.ID_DOWN); ET.release(uc, M.ID_DOWN)
    p = 8 * (value % 4) + col
    ET.pad(uc, p); ET.unpad(uc, p)
    ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)


def mutate_tests(uc, stock_pads):
    import rhbuild
    from thumb import bl
    img = Path(sys.argv[2]).read_bytes()
    o = M.NEXT_SITE - rhbuild.BASE
    check("the track advance's read of the next pattern (0x08034E06) calls c_mtnext", img[o:o + 4] == bl(M.NEXT_SITE, LB["c_mtnext"]))
    call(uc, C_RRT)
    R = uc.reg_read(UC_ARM_REG_R0) - 0x29110
    pat = lambda t, p: R + M.STEPS0 + M.TRK_STRIDE * t + M.PAT_STRIDE * p

    def steps(t, p, hit_step):
        uc.mem_write(pat(t, p) + M.P_LAST, bytes([15, 0]))
        uc.mem_write(pat(t, p) + 8 * hit_step + 3, b"\x60")

    for p in (0, 2, 5):
        steps(0, p, 3)
    steps(0, 7, 20)                                       # a hit past the last step: not in the pool
    steps(2, 4, 0)

    def chain(t, first, last):
        call(uc, M.PARAM_GET, u32(uc, M.CHAINS), t)
        uc.mem_write(uc.reg_read(UC_ARM_REG_R0), bytes([first, last]))

    chain(0, 0, 1)
    chain(2, 2, 2)
    uc.mem_write(blk(uc), bytes(M.BLK_LEN))
    check("no lists: the hook answers the stock's choice", [nxt(uc, t, 3, 0, 4) for t in range(8)] == [3] * 8)

    tap(uc)
    check("Shift + tap Duplicate, the defaults (Same as the chain, With steps, On the tap): track 1 a list of 2 (its chain 1-2) from "
          "patterns 1, 3, 6; track 3 one of 1, pattern 5; the tracks without hits none", len(lst(uc, 0)) == 2 and
          set(lst(uc, 0)) <= {0, 2, 5} and lst(uc, 2) == [4] and all(lst(uc, t) == [] for t in (1, 3, 4, 5, 6, 7)) and ours(block(uc)),
          [lst(uc, t) for t in range(8)])
    L0 = lst(uc, 0)
    seq = []
    for k in range(5):
        la = nxt(uc, 0, 1, 0, 1, la=1)
        pl = nxt(uc, 0, 1, 0, 1)
        seq.append((la, pl))
    check("  track 1 plays its list round and round; the look-ahead before each end answers the same",
          seq == [(L0[k % 2],) * 2 for k in range(5)], (seq, L0))
    p0 = pos(uc, 0)
    nxt(uc, 0, 1, 0, 1, la=1); nxt(uc, 0, 1, 0, 1, la=1)
    check("  the look-ahead changes nothing", pos(uc, 0) == p0)
    check("  forced (a play start): slot 1", nxt(uc, 0, 0, 0, 1, forced=1) == L0[0] and pos(uc, 0) == 0)

    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    o = lights(uc)
    g = ET.scl(u32(uc, M.COLOURS + 4 * M.GREEN), M.SOFT)
    if REP.get("stocktrk"):
        b = block(uc)
        for t in range(8):
            set_list(uc, t, [])
        stock = lights(uc)
        uc.mem_write(blk(uc), b)
        trk = [M.LED_TRK0 + t for t in range(8)]
        check("Patterns page: the track buttons the stock's with lists on tracks 1 and 3 (no green)",
              [o[k] for k in trk] == [stock[k] for k in trk], ([f"{o[k]:06x}" for k in trk], [f"{stock[k]:06x}" for k in trk]))
    else:
        check(f"Patterns page: tracks 1 and 3 (a list) soft green ({g:06x}), the others not", o[M.LED_TRK0] == o[M.LED_TRK0 + 2] == g and
              all(o[M.LED_TRK0 + t] != g for t in (1, 3, 4, 5, 6, 7)), [f"{o[M.LED_TRK0 + t]:06x}" for t in range(8)])
    if REP.get("shiftstock"):
        b = block(uc)
        no_shift = lights(uc)
        set_shift(uc, 1)
        with_lists = lights(uc)
        for t in range(8):
            set_list(uc, t, [])
        no_lists = lights(uc)
        uc.mem_write(blk(uc), b)
        set_shift(uc, 0)
        trk, pads = [M.LED_TRK0 + t for t in range(8)], list(range(32))
        if REP.get("shiftpads"):
            check("  Shift held: the track buttons as with no lists (the stock's Shift lights), the pads the mutate's (as without Shift)",
                  all(with_lists[k] == no_lists[k] for k in trk) and all(with_lists[k] == no_shift[k] for k in pads) and
                  any(no_shift[k] != no_lists[k] for k in pads),
                  [(k, f"{with_lists[k]:06x}", f"{no_lists[k]:06x}", f"{no_shift[k]:06x}") for k in trk + pads
                   if with_lists[k] != (no_lists[k] if k in trk else no_shift[k])][:4])
        else:
            check("  Shift held: the track buttons and the pads as with no lists (the stock's Shift lights)",
                  all(with_lists[k] == no_lists[k] for k in trk + pads),
                  [(k, f"{with_lists[k]:06x}", f"{no_lists[k]:06x}") for k in trk + pads if with_lists[k] != no_lists[k]][:4])

    stock_pads.clear()
    set_clear(uc, 1); ET.pad(uc, 8 + 0); ET.unpad(uc, 8 + 0); set_clear(uc, 0)
    hd = u32(uc, C.CTRL + M.O_HELD)
    uc.mem_write(C.CTRL + M.O_HELD, struct.pack("<I", hd | 1 << M.BIT_DUPH))
    ET.pad(uc, 8 + 0); ET.unpad(uc, 8 + 0)
    uc.mem_write(C.CTRL + M.O_HELD, struct.pack("<I", hd))
    check("Clear + pad, Duplicate + pad on track 1: its list kept, the stock's pads reached", lst(uc, 0) == L0 and len(stock_pads) == 4,
          stock_pads)
    ET.pad(uc, 8 + 0); ET.unpad(uc, 8 + 0)
    check("a pattern pad on track 1: its list gone, track 3's kept; the stock's pad reached", lst(uc, 0) == [] and lst(uc, 2) == [4]
          and stock_pads[-2:] == ["press", "release"])
    check("  the next pattern end: a pattern outside the chain (6) goes to the first (1)", nxt(uc, 0, 5, 0, 1, la=1) == 0 and
          nxt(uc, 0, 5, 0, 1) == 0)
    check("  after that: the stock's choice", nxt(uc, 0, 5, 0, 1) == 5)
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    o = lights(uc)
    check("  track 1's button not green now", o[M.LED_TRK0] != g)

    setting(uc, 3, 1)                                     # Exact
    setting(uc, 2, 2)                                     # Length 3
    setting(uc, 4, 1)                                     # Pool All
    check("the settings: Exact, Length 3, All", vals(uc)[:3] == [3, 1, 1], vals(uc))
    tap(uc)
    ls = [lst(uc, t) for t in range(8)]
    check("Shift + tap: each track a list of 3 from all 8 patterns", all(len(x) == 3 and all(0 <= p < 8 for p in x) for x in ls), ls)
    hold_open(uc)
    ET.press(uc, 7); ET.release(uc, 7)
    ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)
    check("  the page opened and closed: the lists kept; track 8 off", [lst(uc, t) for t in range(8)] == ls and vals(uc)[4] == 0x80)
    tap(uc)
    ls2 = [lst(uc, t) for t in range(8)]
    check("  Shift + tap again: new lists, track 8's kept (off)", ls2[7] == ls[7] and ls2[:7] != ls[:7], ls2)
    had = [t for t in range(8) if lst(uc, t)]
    tap(uc, clear=True)
    if REP.get("pclrv"):
        uc.mem_write(C.HAL_TICK, struct.pack("<I", u32(uc, C.HAL_TICK) & ~0x40))
        uc.mem_write(SLOT + M.O_RTIME, struct.pack("<H", u32(uc, C.HAL_TICK) & 0xFFFF))
        uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
        o = lights(uc)
        red = u32(uc, M.COLOURS + 4 * M.CLR_RED)
        check("  Clear + Shift + tap: the tracks that had a list flash red", [o[M.LED_TRK0 + t] == red for t in range(8)] ==
              [t in had for t in range(8)], (had, [f"{o[M.LED_TRK0 + t]:06x}" for t in range(8)]))
        uc.mem_write(C.HAL_TICK, struct.pack("<I", u32(uc, C.HAL_TICK) + 400))
        lights(uc)
    if REP.get("clearall"):
        check("Clear + Shift + tap: every list gone, track 8's too (off)", all(lst(uc, t) == [] for t in range(8)))
    else:
        check("Clear + Shift + tap: the lists of the tracks that are on gone, track 8's kept", all(lst(uc, t) == [] for t in range(7)) and
              lst(uc, 7) == ls[7])

    setting(uc, 3, 2)                                     # Random
    setting(uc, 2, 7)                                     # Length 8
    lens = set()
    for k in range(12):
        tap(uc)
        lens |= {len(lst(uc, t)) for t in range(7)}
    check(f"Random, Length 8: lengths 1-8 at random ({sorted(lens)})", lens <= set(range(1, 9)) and len(lens) >= 5)

    tap(uc, clear=True)
    setting(uc, 3, 1)                                     # Exact
    setting(uc, 2, 2)                                     # Length 3
    setting(uc, 5, 1)                                     # Every chain end
    tap(uc)
    check("Every chain end: Shift + tap: no list yet, the tracks that are on renew", all(lst(uc, t) == [] for t in range(7)) and
          renew(uc) == 0x7F, hex(renew(uc)))
    check("  track 3 (chain 3-3), forced: the stock's", nxt(uc, 2, 2, 2, 2, forced=1) == 2 and lst(uc, 2) == [])
    if REP.get("pending"):                                # the next list hidden until it plays: the pads show the list playing
        a = nxt(uc, 2, 2, 2, 2, la=1)
        hidden = lst(uc, 2) == []
        p = nxt(uc, 2, 2, 2, 2)
        A = lst(uc, 2)
        check("  its chain's end: the look-ahead answers the next list's slot 1, not shown; the play: a list of 3, slot 1 plays",
              hidden and len(A) == 3 and a == p == A[0] and pos(uc, 2) == 0, (a, p, A))
        p2 = nxt(uc, 2, 2, 2, 2)
        p3 = nxt(uc, 2, 2, 2, 2)
        a = nxt(uc, 2, 2, 2, 2, la=1)
        check("  slot 3 (the last) plays and its look-ahead: the list playing still shown, slot 3 playing",
              (p2, p3) == (A[1], A[2]) and lst(uc, 2) == A and pos(uc, 2) == 2, (p2, p3, lst(uc, 2)))
        p = nxt(uc, 2, 2, 2, 2)
        B = lst(uc, 2)
        check("  its end: the new list (a new seed), its slot 1 as the look-ahead said", len(B) == 3 and p == a == B[0] and
              pos(uc, 2) == 0, (a, p, B))
        check("  track 1 (chain 1-2) enters its chain's last: the stock's (2), no list shown yet", nxt(uc, 0, 1, 0, 1) == 1 and
              lst(uc, 0) == [])
        a = nxt(uc, 0, 0, 0, 1, la=1)
        p = nxt(uc, 0, 0, 0, 1)
        C0 = lst(uc, 0)
        check("  its chain's end: its list, slot 1 (the look-ahead the same)", len(C0) == 3 and a == p == C0[0], (a, p, C0))
    else:
        a = nxt(uc, 2, 2, 2, 2, la=1)
        A = lst(uc, 2)
        p = nxt(uc, 2, 2, 2, 2)
        check("  its chain's end: a list of 3, slot 1 plays (the look-ahead the same)", len(A) == 3 and a == p == A[0], (a, p, A))
        p2 = nxt(uc, 2, 2, 2, 2)
        p3 = nxt(uc, 2, 2, 2, 2)
        B = lst(uc, 2)
        check("  slot 3 (the last) plays: a new list for after it", (p2, p3) == (A[1], A[2]) and pos(uc, 2) == 0xFF and len(B) == 3,
              (p2, p3, B))
        check("  then the new list's slot 1", nxt(uc, 2, 2, 2, 2, la=1) == B[0] == nxt(uc, 2, 2, 2, 2))
        check("  track 1 (chain 1-2) enters its chain's last: the stock's (2), its list made for after it",
              nxt(uc, 0, 1, 0, 1) == 1 and len(lst(uc, 0)) == 3 and pos(uc, 0) == 0xFF)
        C0 = lst(uc, 0)
        check("  then its list", nxt(uc, 0, 0, 0, 1) == C0[0])
    setting(uc, 5, 0)                                     # On the tap
    B = lst(uc, 2)
    for k in range(3):
        nxt(uc, 2, 2, 2, 2)
    check("When back to On the tap: track 3's list kept, no new list at its end", lst(uc, 2) == B)
    nxt(uc, 2, 2, 2, 2, scene=1, la=1)
    check("a scene change, the look-ahead: the list kept", lst(uc, 2) == B)
    check("a scene change, the play: the stock's choice, the list gone", nxt(uc, 2, 3, 3, 3, scene=1) == 3 and lst(uc, 2) == [] and
          renew(uc) >> 2 & 1 == 0)
    check("the block still ours (its check byte right)", ours(block(uc)))
    if REP.get("listpads"):
        listpads_tests(uc)
    if REP.get("scenecut"):
        scenecut_tests(uc)
    if REP.get("liststart"):
        liststart_tests(uc, chain)
    if REP.get("scenesave"):
        scenesave_tests(uc)
    if REP.get("pageclr"):
        pageclr_tests(uc)
    if REP.get("pclrv"):
        pclrv_tests(uc)
    if REP.get("amount"):
        amount_tests(uc, chain)
    if REP.get("norep"):
        norep_tests(uc, chain)
    if REP.get("keep1"):
        keep1_tests(uc, chain)
    if REP.get("hidepause"):
        hidepause_tests(uc)
    if REP.get("vlock"):
        vlock_tests(uc)
    if SEEDS:
        seeds_tests(uc, chain)
    real_play()
    if REP.get("scchain"):
        scene_play(chain=True)
        scene_play(chain=False)
    if REP.get("scplay"):
        play_start(chain=True)
        play_start(chain=False)
    if REP.get("livecol"):
        livecol_tests(uc)
    if REP.get("views"):
        views_tests(uc)
    if REP.get("bounce"):
        bounce_tests(uc)
    if REP.get("shtrk"):
        shtrk_tests(uc)
    if REP.get("clrpage"):
        clrpage_tests(uc)
    if REP.get("shmut"):
        shmut_tests(uc)


def amount_set(uc, r):
    """Amount by its pad: page 2, column 4, row r (0 All .. 3 A little)"""
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    hold_open(uc)
    ET.press(uc, M.ID_DOWN); ET.release(uc, M.ID_DOWN)
    p = 8 * r + M.AM_COL
    ET.pad(uc, p); ET.unpad(uc, p)
    ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)


def amount_tests(uc, chain):
    NAMES = ("All", "Most", "Some", "A little")
    for t in range(8):
        set_list(uc, t, [])
    chain(0, 0, 3)                                        # track 1: chain 1-4
    setting(uc, 2, 3)                                     # Length 4
    setting(uc, 3, 0)                                     # Same as the chain
    setting(uc, 4, 1)                                     # Pool All
    setting(uc, 5, 0)                                     # On the tap
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    hold_open(uc)
    ET.press(uc, M.ID_DOWN); ET.release(uc, M.ID_DOWN)
    page_ok(uc, "page 2: Length 5-8, column 4 the Amount meter full (All, the default)")
    for r in (2, 3, 1, 0):
        p = 8 * r + M.AM_COL
        ET.pad(uc, p); ET.unpad(uc, p)
        check(f"  column 4, row {r + 1}: Amount {NAMES[r]} (the block's byte {M.B_VAL2}, bits 0-1 = {r})",
              block(uc)[M.B_VAL2] & M.AM_MASK == r and ours(block(uc)), block(uc)[M.B_VAL2])
        page_ok(uc, f"  the meter lit from the bottom up to row {r + 1}")
    for p in (8 * 3 + 4, 8 * 2 + 5, 8 * 0 + 6):            # column 5 row 4, column 6 row 3, column 7: never a setting
        b = block(uc)
        ET.pad(uc, p); ET.unpad(uc, p)
        check(f"  page 2, pad {p + 1} (no setting): nothing changes", block(uc) == b)
    ET.press(uc, M.ID_UP); ET.release(uc, M.ID_UP)
    page_ok(uc, "  Up: page 1 as before")
    ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)

    def runs(n, want_len):
        out = []
        for k in range(n):
            tap(uc)
            L = lst(uc, 0)
            assert len(L) == want_len, L
            out.append(L)
        return out

    def diff(L, c): return sum(1 for i in range(c) if L[i] != i)
    for r, m in ((1, 3), (2, 2), (3, 1)):
        amount_set(uc, r)
        R = runs(40, 4)
        d = [diff(L, 4) for L in R]
        check(f"Amount {NAMES[r]}, chain 1-4, Same as the chain: 40 lists of 4, at most {m} slot{'s' if m > 1 else ''} not the chain's, {m} in some",
              max(d) == m and all(x <= m for x in d), (d[:12], R[:3]))
    setting(uc, 2, 7)                                     # Length 8
    setting(uc, 3, 1)                                     # Exact
    amount_set(uc, 3)
    R = runs(30, 8)
    d = [diff(L, 4) for L in R]
    tail = sum(1 for L in R for i in range(4, 8) if L[i] != i)
    check("Amount A little, Exact 8: of the chain's 4 slots at most 1 not the chain's; slots 5-8 random", max(d) == 1 and
          tail > 30, (d[:12], tail))
    amount_set(uc, 0)
    setting(uc, 3, 0)                                     # Same as the chain
    R = runs(30, 4)
    d = [diff(L, 4) for L in R]
    check("Amount All: every slot random (3 or 4 slots not the chain's in some lists)", max(d) >= 3, d[:12])
    setting(uc, 2, 3)                                     # Length 4
    setting(uc, 4, 0)                                     # With steps
    chain(0, 0, 1)
    for t in range(8):
        set_list(uc, t, [])


def page2_pad(uc, col, r):
    """a page 2 setting by its pad (the page opened and closed around it)"""
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    hold_open(uc)
    ET.press(uc, M.ID_DOWN); ET.release(uc, M.ID_DOWN)
    p = 8 * r + col
    ET.pad(uc, p); ET.unpad(uc, p)
    ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)


def norep_tests(uc, chain):
    for t in range(8):
        set_list(uc, t, [])
    setting(uc, 2, 7)                                     # Length 8
    setting(uc, 3, 1)                                     # Exact
    setting(uc, 4, 1)                                     # Pool All
    setting(uc, 5, 0)                                     # On the tap
    amount_set(uc, 0)
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    hold_open(uc)
    ET.press(uc, M.ID_DOWN); ET.release(uc, M.ID_DOWN)
    page_ok(uc, "page 2: column 5 Repeats, On (row 1) full, Off (row 2) dim, darkest green")
    p = 8 * 1 + M.NR_COL
    ET.pad(uc, p); ET.unpad(uc, p)
    check(f"  column 5, row 2: Repeats Off (the block's byte {M.B_VAL2}, bit {M.NR_BIT}), Amount kept",
          block(uc)[M.B_VAL2] == 1 << M.NR_BIT and ours(block(uc)), block(uc)[M.B_VAL2])
    page_ok(uc, "  Off full, On dim")
    for r in (2, 3):
        b = block(uc)
        ET.pad(uc, 8 * r + M.NR_COL); ET.unpad(uc, 8 * r + M.NR_COL)
        check(f"  column 5, row {r + 1} (no value): nothing changes", block(uc) == b)
    ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)

    def reps(L): return sum(1 for i in range(len(L)) if len(L) > 1 and L[i] == L[(i + 1) % len(L)])
    R = []
    for k in range(30):
        tap(uc)
        R.append(lst(uc, 0))
    check("Repeats Off, Pool All, Exact 8: 30 lists of 8, no pattern twice in a row (the last and slot 1 too)",
          all(len(L) == 8 and reps(L) == 0 for L in R), [L for L in R if reps(L)][:3])
    chain(0, 0, 3)
    setting(uc, 2, 3)                                     # Length 4
    setting(uc, 3, 0)                                     # Same as the chain
    for r in (2, 3):
        amount_set(uc, r)
        R = []
        for k in range(30):
            tap(uc)
            R.append(lst(uc, 0))
        check(f"  with Amount {('Some', 'A little')[r - 2]}, chain 1-4: no repeats next to the chain's kept slots either",
              all(len(L) == 4 and reps(L) == 0 for L in R), [L for L in R if reps(L)][:3])
    amount_set(uc, 0)
    setting(uc, 4, 0)                                     # With steps: track 3 has only pattern 5
    setting(uc, 2, 3)
    setting(uc, 3, 1)                                     # Exact 4
    tap(uc)
    check("  a pool of 1 pattern (track 3): its list still made (the repeats taken)", lst(uc, 2) == [4, 4, 4, 4], lst(uc, 2))
    page2_pad(uc, M.NR_COL, 0)
    check("Repeats On again (row 1): the byte's bit clear", block(uc)[M.B_VAL2] >> M.NR_BIT & 1 == 0)
    setting(uc, 4, 1)
    setting(uc, 2, 7)                                     # Exact 8, Pool All
    R = []
    for k in range(30):
        tap(uc)
        R.append(lst(uc, 0))
    check("  Repeats On, Pool All, Exact 8: repeats come (some in 30 lists)", sum(reps(L) for L in R) > 0)
    setting(uc, 2, 3)
    setting(uc, 3, 0)
    setting(uc, 4, 0)
    chain(0, 0, 1)
    for t in range(8):
        set_list(uc, t, [])


def keep1_tests(uc, chain):
    for t in range(8):
        set_list(uc, t, [])
    chain(0, 2, 5)                                        # track 1: chain 3-6
    setting(uc, 2, 7)                                     # Length 8
    setting(uc, 3, 1)                                     # Exact
    setting(uc, 4, 1)                                     # Pool All
    setting(uc, 5, 0)                                     # On the tap
    amount_set(uc, 0)
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    hold_open(uc)
    ET.press(uc, M.ID_DOWN); ET.release(uc, M.ID_DOWN)
    page_ok(uc, "page 2: column 6 Keep slot 1, Off (row 1) full, On (row 2) dim, darkest green")
    p = 8 * 1 + M.K1_COL
    ET.pad(uc, p); ET.unpad(uc, p)
    check(f"  column 6, row 2: Keep slot 1 On (the block's byte {M.B_VAL2}, bit {M.K1_BIT}), the other page 2 settings kept",
          block(uc)[M.B_VAL2] == 1 << M.K1_BIT and ours(block(uc)), block(uc)[M.B_VAL2])
    page_ok(uc, "  On full, Off dim")
    for r in (2, 3):
        b = block(uc)
        ET.pad(uc, 8 * r + M.K1_COL); ET.unpad(uc, 8 * r + M.K1_COL)
        check(f"  column 6, row {r + 1} (no value): nothing changes", block(uc) == b)
    ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)

    def lists(n):
        out = []
        for k in range(n):
            tap(uc)
            out.append(lst(uc, 0))
        return out
    R = lists(30)
    check("Keep slot 1 On, Exact 8, Pool All, chain 3-6: 30 lists, slot 1 always pattern 3, the others random",
          all(len(L) == 8 and L[0] == 2 for L in R) and len({tuple(L[1:]) for L in R}) > 20, R[:3])
    chain(0, 0, 3)
    setting(uc, 2, 3)                                     # Length 4
    setting(uc, 3, 0)                                     # Same as the chain
    amount_set(uc, 2)                                     # Some: of the 3 chain slots after slot 1, 2 change
    R = lists(40)
    d = [sum(1 for i in range(1, 4) if L[i] != i) for L in R]
    check("  with Amount Some, chain 1-4: slot 1 pattern 1; of slots 2-4 at most 2 not the chain's, 2 in some",
          all(L[0] == 0 for L in R) and max(d) == 2, (d[:12], R[:3]))
    amount_set(uc, 0)
    page2_pad(uc, M.NR_COL, 1)                            # Repeats Off
    setting(uc, 2, 7)
    setting(uc, 3, 1)                                     # Exact 8
    R = lists(30)
    check("  with Repeats Off: slot 2 and the last slot never pattern 1 (slot 1's)",
          all(L[0] == 0 and L[1] != 0 and L[-1] != 0 for L in R), R[:3])
    page2_pad(uc, M.NR_COL, 0)
    setting(uc, 2, 0)                                     # Exact 1
    R = lists(30)
    check("  a list of 1: random (Keep slot 1 needs 2 slots or more)", all(len(L) == 1 for L in R) and len({L[0] for L in R}) > 2,
          R[:6])
    page2_pad(uc, M.K1_COL, 0)
    check("Keep slot 1 Off again (row 1): the byte 0", block(uc)[M.B_VAL2] == 0)
    setting(uc, 2, 7)
    R = lists(30)
    check("  Keep slot 1 Off, Exact 8: slot 1 random", len({L[0] for L in R}) > 2, [L[0] for L in R][:10])
    setting(uc, 2, 3)
    setting(uc, 3, 0)
    setting(uc, 4, 0)
    chain(0, 0, 1)
    for t in range(8):
        set_list(uc, t, [])


def hidepause_tests(uc):
    run = item(uc, M.O_RUN, 0)
    was = bytes(uc.mem_read(run, 1))
    page = M.PV + M.O_PV_PAGE
    uc.mem_write(page, b"\x00")
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    for t in range(8):
        set_list(uc, t, [])
    uc.mem_write(item(uc, M.O_PLAYING, 0), b"\x01")      # track 1 paused on pattern 2 (row 2)
    uc.mem_write(run, b"\x00")
    stock = lights(uc)[8]
    tc = u32(uc, M.COLOURS + 4 * M.TRK_SLOTS[0])
    rest = ET.scl(tc, REP.get("restlvl", M.VDIM))
    hidden = lambda: fl(uc) & M.FL_HIDE != 0
    set_list(uc, 0, [3, 0])
    check("stopped, a list without pattern 2: the paused pad (pattern 2) the stock's light", lights(uc)[8] == stock and not hidden())
    tap(uc)
    set_list(uc, 0, [3, 0])
    o = lights(uc)
    check(f"  a mutate while stopped: the paused pad drawn as the list's (not in the list: {rest:06x})", hidden() and o[8] == rest
          and stock != rest, (f"{o[8]:06x}", f"{stock:06x}"))
    set_list(uc, 0, [1, 0])
    o = lights(uc)
    member = ET.scl(tc, REP.get("memlvl", M.MEMBER))
    check("  pattern 2 in the list: the list's colour", o[8] == member, f"{o[8]:06x}")
    set_list(uc, 0, [3, 0])
    uc.mem_write(run, b"\x01")
    o = lights(uc)
    check("  the clock runs (Play or Shift + Play): the playing pad the stock's again, the hide ended", o[8] == stock and not hidden())
    uc.mem_write(run, b"\x00")
    check("  stopped again, no mutate: the paused pad the stock's", lights(uc)[8] == stock and not hidden())
    uc.mem_write(run, b"\x01")
    tap(uc)
    check("a mutate while playing: nothing hidden", not hidden())
    uc.mem_write(run, was)
    for t in range(8):
        set_list(uc, t, [])
    lights(uc)


def vlock_tests(uc):
    NOTIFY = 0x0804E49F                                   # the Patterns view's slot 9 (a store changed: r1)
    PV = M.PV
    vstore = lambda t: u32(uc, u32(uc, u32(uc, PV + 0x14) + t * u32(uc, PV + 0xC)) + 0xC)
    pads = lambda t: bytes(uc.mem_read(u32(uc, PV + M.O_PV_PADS + 4 * t), 8))

    def lock(on):
        uc.mem_write(ET.ptr(uc, u32(uc, PV + M.O_PV_LOCK), 0), bytes([on]))
        call(uc, NOTIFY, PV, u32(uc, PV + M.O_PV_LOCK), 0)
    uc.mem_write(PV + M.O_PV_PAGE, b"\x00")
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", PV))
    for t in range(8):
        set_list(uc, t, [])
    uc.mem_write(item(uc, M.O_PLAYING, 0), b"\x00")
    uc.mem_write(ET.ptr(uc, vstore(0), 0), b"\x02")    # track 1 viewing pattern 3
    lock(1)
    check("View Lock on: track 1's viewed pattern 3 marked (the stock's 0x10)", pads(0)[2] & M.PAD_LOCK and
          not pads(0)[1] & M.PAD_LOCK, pads(0).hex())
    stock = lights(uc)
    set_list(uc, 0, [1, 3])
    o = lights(uc)
    check("  track 1 mutated (list 2, 4): its white pad (pattern 3, not in the list, not playing) the stock's; the list's pads ours",
          o[16] == stock[16] and o[8] != stock[8], (f"{o[16]:06x}", f"{stock[16]:06x}", f"{o[8]:06x}"))
    set_shift(uc, 1)
    o = lights(uc)
    check("  Shift held: the white pad still the stock's", o[16] == stock[16] or o[16] == lights(uc)[16])
    ET.pad(uc, 24); ET.unpad(uc, 24)
    set_shift(uc, 0)
    check("  Shift + pad (track 1, pattern 4): the list kept, the stock's view pick (the white mark to pattern 4)",
          lst(uc, 0) == [1, 3] and pads(0)[3] & M.PAD_LOCK and not pads(0)[2] & M.PAD_LOCK, (lst(uc, 0), pads(0).hex()))
    set_list(uc, 0, [5, 6])
    o = lights(uc)
    set_list(uc, 0, [])
    s2 = lights(uc)
    check("  the white pad (pattern 4) the stock's with any list", o[24] == s2[24], (f"{o[24]:06x}", f"{s2[24]:06x}"))
    set_list(uc, 0, [5, 6])
    ET.pad(uc, 0); ET.unpad(uc, 0)
    check("  a pad without Shift (pattern 1): the list ends, the white mark stays (the stock's)", lst(uc, 0) == [] and
          pads(0)[3] & M.PAD_LOCK, (lst(uc, 0), pads(0).hex()))
    lock(0)
    set_list(uc, 0, [1, 3])
    set_shift(uc, 1)
    ET.pad(uc, 16); ET.unpad(uc, 16)
    set_shift(uc, 0)
    check("View Lock off: Shift + pad ends the list (as before)", lst(uc, 0) == [])
    set_list(uc, 0, [1, 4])
    o = lights(uc)
    rest = ET.scl(u32(uc, M.COLOURS + 4 * M.TRK_SLOTS[0]), REP.get("restlvl", M.VDIM))
    check("  no white marks; pattern 4 (not in the list, not playing) ours again", not any(p & M.PAD_LOCK for p in pads(0)) and
          o[24] == rest, (pads(0).hex(), f"{o[24]:06x}"))
    for t in range(8):
        set_list(uc, t, [])
    lights(uc)


def item(uc, off, i):
    call(uc, M.PARAM_GET, u32(uc, M.ENG + off), i)
    return uc.reg_read(UC_ARM_REG_R0)


def set_list(uc, t, pats):
    if SEEDS:                                             # a list the test chose: a key nobody makes, the RAM's list made from it
        k = 0x0F000F00 | t + 1 if pats else 0
        set_key(uc, t, k)
        uc.mem_write(SLOT + M.O_LISTS + M.LIST_LEN * t, bytes([len(pats)] + pats + [0] * (8 - len(pats))))
        uc.mem_write(SLOT + M.O_RKEY + 4 * t, struct.pack("<I", k))
        return
    b = bytearray(block(uc))
    o = M.B_LISTS + M.LIST_LEN * t
    b[o:o + M.LIST_LEN] = bytes([len(pats)] + pats + [0] * (8 - len(pats)))
    b[2] = (sum(b[M.B_VAL:]) & 0xFF) ^ M.CHECK
    uc.mem_write(blk(uc), bytes(b))


def listpads_tests(uc):
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    for t in range(8):
        set_list(uc, t, [])
    page = M.PV + M.O_PV_PAGE if REP.get("pagebyte") else item(uc, M.PV + M.O_PV_PAGE - M.ENG, 0)
    for pg in (0, 1):
        uc.mem_write(page, bytes([pg]))
        set_list(uc, 0, [])
        o0 = lights(uc)
        set_list(uc, 0, [3, 1, 6])
        uc.mem_write(item(uc, M.O_PLAYING, 0), bytes([1 + 4 * pg]))
        o1 = lights(uc)
        member = ET.scl(u32(uc, M.COLOURS + 4 * M.TRK_SLOTS[0]), REP.get("memlvl", M.MEMBER))
        rest = ET.scl(u32(uc, M.COLOURS + 4 * M.TRK_SLOTS[0]), REP.get("restlvl", M.VDIM)) if REP.get("dimrest") else 0
        want = {8 * r: (o0[8 * r] if r == 1 else member if 4 * pg + r in (3, 1, 6) else rest) for r in range(4)}
        bad = [(i, f"{o1[i]:06x}", f"{v:06x}") for i, v in want.items() if o1[i] != v]
        others = all(o1[8 * r + c] == o0[8 * r + c] for r in range(4) for c in range(1, 8))
        check(f"Patterns page {pg + 1}: track 1 with the list 4, 2, 7 playing {2 + 4 * pg}: the pad playing the stock's light, the list's "
              f"others the track colour at {REP.get('memlvl', M.MEMBER)}, the rest {'at ' + str(REP.get('restlvl', M.VDIM)) if REP.get('dimrest') else 'dark'}; the other tracks the stock's",
              not bad and others, bad)
    if REP.get("pagebyte"):
        uc.mem_write(page, b"\x00")
        set_list(uc, 0, [])
        stock = lights(uc)
        set_list(uc, 0, [3, 1, 6])
        drawn = lights(uc)
        for junk in (2, 0x80, 0xFF):
            uc.mem_write(page, bytes([junk]))
            o1 = lights(uc)
            check(f"  the page byte {junk:#x} (not a page): our pads not drawn, the stock's kept", o1[:32] == stock[:32])
        uc.mem_write(page, b"\x00")
        uc.mem_write(page + 1, b"\xa5\x5a\xff")
        o1 = lights(uc)
        check("  page 1 with other bytes after the page byte: the same pads", o1[:32] == drawn[:32])
        uc.mem_write(page + 1, b"\x00\x00\x00")
    uc.mem_write(page, b"\x00")
    set_list(uc, 0, [])


def scenecut_tests(uc):
    MIX = 0x2004E090
    tap(uc, clear=True)
    setting(uc, 4, 1)                                     # Pool All
    setting(uc, 5, 0)                                     # On the tap
    hold_open(uc)
    for t in range(8):
        if vals(uc)[4] >> t & 1:
            ET.press(uc, t); ET.release(uc, t)
    ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)
    tap(uc)
    check("scenecut: all 8 tracks with a list", all(lst(uc, t) for t in range(8)), [lst(uc, t) for t in range(8)])
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", MIX))
    ET.pad(uc, 0); ET.unpad(uc, 0)
    check("  the Mixer's pad 1 (not a scene): the lists kept", all(lst(uc, t) for t in range(8)))
    ET.pad(uc, 16); ET.unpad(uc, 16)
    if REP.get("scchain"):
        check("  the Mixer's pad 17 (scene 1), playing: the lists kept to the scene's start", all(lst(uc, t) for t in range(8)))
        for t in range(8):
            call(uc, LB["c_mtcl"], t)
    else:
        check("  the Mixer's pad 17 (scene 1): every list gone at the press", all(lst(uc, t) == [] for t in range(8)) and
              renew(uc) == 0)
    uc.mem_write(item(uc, M.O_SCASK, 1), b"\x00")         # the scene started
    tap(uc)
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", MIX))
    ET.pad(uc, 18); ET.unpad(uc, 18)
    if REP.get("scchain"):
        check("  new lists, then pad 19 (scene 3): the lists kept", all(lst(uc, t) for t in range(8)))
        for t in range(8):
            call(uc, LB["c_mtcl"], t)
    else:
        check("  new lists, then pad 19 (scene 3): every list gone", all(lst(uc, t) == [] for t in range(8)))
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))


def liststart_tests(uc, chain):
    """the stock's seek (0x080342E0, Play's start of each track): a track with a list starts on its slot 1, as the stock starts a chain
    of that pattern"""
    import rhbuild
    from thumb import bl
    img = Path(sys.argv[2]).read_bytes()
    o = M.SEEK_SITE - rhbuild.BASE
    check("the seek's read of the chain's first (0x08034330) calls c_mtseek", img[o:o + 4] == bl(M.SEEK_SITE, LB["c_mtseek"]))

    def got(t):
        return [uc.mem_read(item(uc, M.O_PLAYING + 4 * t, 0), 1)[0], uc.mem_read(item(uc, M.O_PLAYING + 4 * t, 1), 1)[0],
                struct.unpack("<I", uc.mem_read(item(uc, M.O_PLAYING + 4 * t, 2), 4))[0]]

    for t in range(8):
        set_list(uc, t, [])
    chain(0, 5, 5)
    call(uc, SEEK, M.ENG, 0, 0, 0)
    want = got(0)
    chain(0, 0, 1)
    set_list(uc, 0, [5, 2, 0])
    uc.mem_write(SLOT + M.O_POS, b"\xff")
    call(uc, SEEK, M.ENG, 0, 0, 0)
    check("Play, track 1 with the list 6, 3, 1 (chain 1-2): it starts as the stock starts a chain of pattern 6 (pattern, step, time); "
          "slot 1 playing", got(0) == want and want[0] == 5 and pos(uc, 0) == 0, (got(0), want))
    chain(2, 2, 2)
    call(uc, SEEK, M.ENG, 2, 0, 0)
    check("  track 3 without a list (chain 3-3): the chain's first", got(2)[0] == 2, got(2))
    set_list(uc, 0, [])
    chain(0, 0, 1)
    call(uc, SEEK, M.ENG, 0, 1, 0)
    want = got(0)
    set_list(uc, 0, [5, 2, 0])
    call(uc, SEEK, M.ENG, 0, 1, 0)
    check("  a seek not at the chain's start: the stock's", got(0) == want and want[0] in (0, 1), (got(0), want))
    set_list(uc, 0, [])


SCOBJ, SCGET = 0x2003D2FC, 0x08033242                     # the scene commands' object; the stock's scene chain (store, scene, track) -> first


def scene_bytes(uc, sc):
    """scene sc's 29 B of lists, by the layout: + 2, + 3 of each track and + 34 .. 39 of its record, then 7 B of the tail"""
    call(uc, C_RRT)
    tail = uc.reg_read(UC_ARM_REG_R0)
    rec = tail - 0x29110 + 0x40 + 40 * sc
    addrs = [rec + 4 * (k >> 1) + 2 + (k & 1) for k in range(16)] + [rec + 34 + k for k in range(6)] + \
            [tail + M.SC_TOFF + M.SC_TLEN * sc + k for k in range(M.SC_TLEN)]
    return addrs, bytes(uc.mem_read(a, 1)[0] for a in addrs)


def scene_lists(uc, sc):
    """scene sc's lists (None: no lists in it); (seeds) the lists its keys make"""
    _, b = scene_bytes(uc, sc)
    if b[28] != (sum(b[:28]) + sc) & 0xFF ^ M.SC_CHECK:
        return None
    bits = int.from_bytes(b[:28], "little")
    if SEEDS:
        return [gen(uc, t, k) if (k := bits >> 28 * t & 0xFFFFFFF) else [] for t in range(8)]
    out = []
    for t in range(8):
        n = bits >> 28 * t & 15
        out.append([bits >> 28 * t + 4 + 3 * j & 7 for j in range(n)])
    return out


def put(uc, want, keys):
    """the tracks' lists: (seeds) by their keys, else as they are"""
    for t in range(8):
        if SEEDS:
            set_key(uc, t, keys[t])
        else:
            set_list(uc, t, want[t])


def scmsg(uc, cmd, r2, r3):
    call(uc, LB["c_scmsg"], SCOBJ, u32(uc, SCOBJ + cmd), r2, r3)


def scenesave_tests(uc):
    import rhbuild
    img = Path(sys.argv[2]).read_bytes()
    o = M.SCMSG_VT - rhbuild.BASE
    check("the scene commands' handler (0x08068B18) is c_scmsg", struct.unpack_from("<I", img, o)[0] == LB["c_scmsg"] | 1)
    want = [[5, 2, 0], [], [7, 7, 1, 3, 4, 6, 0, 2], [], [3], [], [], [1, 1]]
    keys = [mk(0x3A1 + 77 * t, len(w), first=0, last=1) if w else 0 for t, w in enumerate(want)]
    if SEEDS:
        want = [gen(uc, t, k) if k else [] for t, k in enumerate(keys)]
    put(uc, want, keys)
    call(uc, C_RRT)
    tail = uc.reg_read(UC_ARM_REG_R0)
    area = lambda: bytes(uc.mem_read(tail - 0x29110 + 0x40, 640)) + bytes(uc.mem_read(tail + M.SC_TOFF, 16 * M.SC_TLEN))
    before = area()
    scmsg(uc, 0x70, 3, 0)
    after = area()
    ours = set()
    for k in range(16):
        ours |= {a - (tail - 0x29110 + 0x40) if a < tail else 640 + a - tail - M.SC_TOFF for a in scene_bytes(uc, k)[0]}
    changed = {i for i in range(len(after)) if before[i] != after[i]}
    stock4 = {120 + 4 * t + k for t in range(8) for k in (0, 1)} | {152, 153}     # scene 4's chains, its used flag and byte + 33
    chains = all(call(uc, SCGET, u32(uc, M.ENG + 0x24), 3, t) is None and uc.reg_read(UC_ARM_REG_R0) ==
                 uc.mem_read(chain_item(uc, t), 1)[0] for t in range(8))
    check("save scene 4: its lists in the scene; the stock's save too (the scene's chains = the tracks'); no other byte changed than "
          "ours and the stock's of scene 4", scene_lists(uc, 3) == want and chains and changed & ours and changed <= ours | stock4,
          (scene_lists(uc, 3), sorted(changed - ours - stock4)[:8]))
    check("  the other scenes: no lists", all(scene_lists(uc, k) is None for k in range(16) if k != 3))
    for t in range(8):
        set_list(uc, t, [6])
    a = nxt(uc, 0, 1, 0, 1, scene=1, la=1, sc=3)
    check("scene 4 starts, the look-ahead: its slot 1, track 1's list kept", a == want[0][0] and lst(uc, 0) == [6], (a, lst(uc, 0)))
    p = nxt(uc, 0, 1, 0, 1, scene=1, sc=3)
    check("  the play: track 1 the scene's list, slot 1 playing", p == want[0][0] and lst(uc, 0) == want[0] and pos(uc, 0) == 0,
          (p, lst(uc, 0), pos(uc, 0)))
    p = nxt(uc, 2, 1, 0, 1, scene=1, sc=3)
    check("  track 3: its list of 8", p == want[2][0] and lst(uc, 2) == want[2], (p, lst(uc, 2)))
    p = nxt(uc, 1, 4, 4, 4, scene=1, sc=3)
    check("  track 2 (none in the scene): the stock's, its list gone", p == 4 and lst(uc, 1) == [])
    p = nxt(uc, 3, 4, 4, 4, scene=1, sc=6)
    check("scene 7 (no lists) starts: the stock's, the list gone", p == 4 and lst(uc, 3) == [])
    scmsg(uc, 0x68, 0, 3)
    scmsg(uc, 0x68, 1, 5)
    check("copy scene 4, paste into scene 6: scene 6's lists = scene 4's", uc.mem_read(SCOBJ + 0x65, 1)[0] == 3 and
          scene_lists(uc, 5) == want)
    scmsg(uc, 0x68, 2, 3)
    check("clear scene 4: no lists in it (its bytes 0), scene 6 kept", scene_bytes(uc, 3)[1] == bytes(29) and scene_lists(uc, 5) == want)
    for t in range(8):
        set_list(uc, t, [])
    scmsg(uc, 0x68, 2, 5)
    scmsg(uc, 0x70, 5, 0)
    check("save scene 6 with no lists: no lists in it", scene_bytes(uc, 5)[1] == bytes(29))
    put(uc, want, keys)
    scmsg(uc, 0x70, 8, 0)
    for t in range(8):
        set_list(uc, t, [])
    MIX = 0x2004E090
    run = item(uc, M.O_RUN, 0)
    was = uc.mem_read(run, 1)
    uc.mem_write(run, b"\x00")
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", MIX))
    ET.pad(uc, 24); ET.unpad(uc, 24)
    check("stopped, the Mixer's pad 25 (scene 9, saved with lists): its lists now", [lst(uc, t) for t in range(8)] == want,
          [lst(uc, t) for t in range(8)])
    uc.mem_write(item(uc, M.O_SCASK, 1), b"\x00")
    uc.mem_write(run, b"\x01")
    ET.pad(uc, 16); ET.unpad(uc, 16)
    if REP.get("scchain"):
        check("  playing, pad 17 (scene 1): every list kept at the press (the scene's own at its start)",
              [lst(uc, t) for t in range(8)] == want)
    else:
        check("  playing, pad 17 (scene 1): every list gone at the press", all(lst(uc, t) == [] for t in range(8)))
    uc.mem_write(item(uc, M.O_SCASK, 1), b"\x00")
    uc.mem_write(run, bytes(was))
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    scmsg(uc, 0x68, 2, 8)
    if REP.get("scenefix"):
        mixscene_tests(uc, img, want, keys)


def mixscene_tests(uc, img, want, keys):
    """the Mixer's scene pads, through the stock's own sends (its scene object at view + 0x0C, base 0x2003D300)"""
    import rhbuild
    o = M.SCMSG_VT2 - rhbuild.BASE
    check("the second base's slot (0x08068B24) is c_scmsg2", struct.unpack_from("<I", img, o)[0] == LB["c_scmsg2"] | 1)
    MIX, SO = 0x2004E090, 0x2004E09C
    held = ET.ptr(uc, u32(uc, SO + 0x28), 0)              # bit 0 Clear, bit 1 Duplicate (the scene object's)
    copied = u32(uc, SO + 0x2C)
    was = bytes(uc.mem_read(copied, 1))
    uc.mem_write(copied, bytes(1))                        # nothing copied: the next Duplicate + pad copies
    put(uc, want, keys)
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", MIX))
    set_shift(uc, 1)
    ET.pad(uc, 31); ET.unpad(uc, 31)
    set_shift(uc, 0)
    check("the Mixer, Shift + pad 32: scene 16 saved with the lists, the lists kept", scene_lists(uc, 15) == want and
          [lst(uc, t) for t in range(8)] == want, (scene_lists(uc, 15), [lst(uc, t) for t in range(8)]))

    def mx(v, pad):
        uc.mem_write(held, bytes([v]))
        ET.pad(uc, pad); ET.unpad(uc, pad)
        uc.mem_write(held, bytes(1))
    mx(2, 31)
    mx(2, 29)
    check("  Duplicate + pad 32, then pad 30: scene 14's lists = scene 16's", scene_lists(uc, 13) == want, scene_lists(uc, 13))
    mx(1, 31)
    check("  Clear + pad 32: no lists in scene 16, scene 14 kept", scene_lists(uc, 15) is None and scene_lists(uc, 13) == want)
    mx(1, 29)
    uc.mem_write(copied, was)
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    for t in range(8):
        set_list(uc, t, [])


NW = "dark" if REP.get("cleardark") else "dim white"


def nolist():
    """Clear held: the track button of a track with no list"""
    return 0 if REP.get("cleardark") or not REP.get("pclrv") else ET.scl(0xFFFFFF, M.DIMW)


def pageclr_tests(uc):
    for t in range(8):
        set_list(uc, t, [1, 2] if t in (0, 2, 5) else [])
    hold_open(uc)
    set_clear(uc, 1)
    o = lights(uc)
    g = u32(uc, M.COLOURS + 4 * M.GREEN)
    check("the page, Clear held: the track buttons of tracks 1, 3, 6 (with a list) green, the others dark",
          [o[M.LED_TRK0 + t] for t in range(8)] == [g if t in (0, 2, 5) else nolist() for t in range(8)],
          [f"{o[M.LED_TRK0 + t]:06x}" for t in range(8)])
    set_clear(uc, 0)
    page_ok(uc, "  Clear let go: the page's lights again")
    ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)
    for t in range(8):
        set_list(uc, t, [1, 2])
    off = vals(uc)[4]
    hold_open(uc)
    set_clear(uc, 1)
    ET.press(uc, 2); ET.release(uc, 2)
    set_clear(uc, 0)
    check("the page, Clear + track 3's button: track 3's list gone, the others kept, the page open, on / off the same",
          lst(uc, 2) == [] and all(lst(uc, t) == [1, 2] for t in range(8) if t != 2) and is_open(uc) and vals(uc)[4] == off,
          ([lst(uc, t) for t in range(8)], vals(uc)[4], off))
    if REP.get("pclrv"):
        set_clear(uc, 1)
        o = lights(uc)
        set_clear(uc, 0)
        check("  track 3's button red right after (the flash)", o[M.LED_TRK0 + 2] == u32(uc, M.COLOURS + 4 * M.CLR_RED),
              f"{o[M.LED_TRK0 + 2]:06x}")
    ET.press(uc, 4); ET.release(uc, 4)
    check("  track 5's button without Clear: track 5 off, its list kept", vals(uc)[4] == off ^ 1 << 4 and lst(uc, 4) == [1, 2])
    ET.press(uc, 4); ET.release(uc, 4)
    ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)
    for t in range(8):
        set_list(uc, t, [])


def prev_btn():
    """the button chain after c_msbtn: the target of its first b.w"""
    import rhbuild
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    img = Path(sys.argv[2]).read_bytes()
    st = LB["c_msbtn"]
    for i in Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(img[st - rhbuild.BASE:st - rhbuild.BASE + 0x600], st):
        if i.mnemonic == "b.w":
            return int(i.op_str.lstrip("#"), 16)


def pclrv_tests(uc):
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    uc.mem_write(C.HAL_TICK, struct.pack("<I", u32(uc, C.HAL_TICK) + 400))
    lights(uc)                                            # an earlier red flash over
    g = u32(uc, M.COLOURS + 4 * M.GREEN)
    has = (0, 2, 5)
    dimw = nolist()
    want_trk = [g if t in has else dimw for t in range(8)]
    for t in range(8):
        set_list(uc, t, [1, 2] if t in has else [])
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    closed = lights(uc)
    set_clear(uc, 1)
    o = lights(uc)
    red = u32(uc, M.COLOURS + 4 * M.CLR_RED)
    dup = red if REP.get("clrdup") else closed[M.LED_DUP]
    check(f"Patterns page, Clear held: the track buttons of tracks 1, 3, 6 (a list) green, the others {NW}; the pads as without Clear; "
          f"Duplicate {'red' if REP.get('clrdup') else 'as without Clear'}", [o[M.LED_TRK0 + t] for t in range(8)] == want_trk and
          all(o[k] == closed[k] for k in range(32)) and o[M.LED_DUP] == dup,
          ([f"{o[M.LED_TRK0 + t]:06x}" for t in range(8)], f"{o[M.LED_DUP]:06x}"))
    reached = []
    pb = prev_btn()
    h = uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: reached.append(1), None, pb, pb + 1)
    t0 = u32(uc, C.HAL_TICK)
    ET.press(uc, 2); ET.release(uc, 2)
    red = u32(uc, M.COLOURS + 4 * M.CLR_RED)
    flash = []
    for dt in (10, 70, 140, 300, 400):
        uc.mem_write(C.HAL_TICK, struct.pack("<I", t0 + dt))
        flash.append(lights(uc)[M.LED_TRK0 + 2])
    uc.mem_write(C.HAL_TICK, struct.pack("<I", t0))
    check(f"  then track 3's button flashes red (64 ms on / off) for 384 ms, then {NW}",
          flash == [red, 0, red, red, nolist()], [f"{v:06x}" for v in flash])
    check("  Clear + track 3's button: its list gone, the others kept, the press not passed on (no track switch)",
          lst(uc, 2) == [] and lst(uc, 0) == lst(uc, 5) == [1, 2] and not reached, (lst(uc, 2), len(reached)))
    ET.press(uc, 1); ET.release(uc, 1)
    if REP.get("clrnone"):
        check("  Clear + track 2's button (no list): nothing (not passed on, no track switch)", not reached, len(reached))
        set_clear(uc, 0)
        ET.press(uc, 1); ET.release(uc, 1)
        check("  track 2's button without Clear: the stock's (passed on)", bool(reached))
        set_clear(uc, 1)
    else:
        check("  Clear + track 2's button (no list): the stock's (passed on)", bool(reached))
    set_shift(uc, 1)
    o = lights(uc)
    check(f"  Clear + Shift held: Duplicate red ({red:06x})", o[M.LED_DUP] == red, f"{o[M.LED_DUP]:06x}")
    set_clear(uc, 0)
    o = lights(uc)
    check("  Shift alone again: Duplicate dim green", o[M.LED_DUP] == ET.scl(g, M.DUP_DIM), f"{o[M.LED_DUP]:06x}")
    set_shift(uc, 0)
    set_clear(uc, 1)
    uc.hook_del(h)
    set_clear(uc, 0)
    set_list(uc, 2, [1, 2])
    closed = lights(uc)
    hold_open(uc)
    vals0 = vals(uc)
    set_clear(uc, 1)
    o = lights(uc)
    p = uc.mem_read(M.COLOURS + 4 * M.FRAME_PULSE, 1)[0]
    dup = ET.scl(g, 64 + ((255 - p) * 192 >> 8))
    check("the page, Clear held: the preview: the pads as the Patterns page's (the lists, the patterns playing), the track buttons "
          f"green / {NW}, Duplicate the page's green pulse", all(o[k] == closed[k] for k in range(32)) and
          [o[M.LED_TRK0 + t] for t in range(8)] == want_trk and o[M.LED_DUP] == dup,
          ([k for k in range(32) if o[k] != closed[k]][:4], f"{o[M.LED_DUP]:06x}", f"{dup:06x}"))
    for pad in (8 * 0 + 2, 8 * 1 + 3, 8 * 0 + 4):
        ET.pad(uc, pad); ET.unpad(uc, pad)
    check("  pads with Clear held: no setting changed, the page open", vals(uc) == vals0 and is_open(uc), (vals(uc), vals0))
    set_clear(uc, 0)
    ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)
    for t in range(8):
        set_list(uc, t, [])


def seeds_tests(uc, chain):
    """the keys in place of the lists: a load, an old project, Live, a scene recall with Live, Clear + Duplicate"""
    keys = lambda: [key_of(uc, t) for t in range(8)]                           # noqa: E731
    lists = lambda: [lst(uc, t) for t in range(8)]                             # noqa: E731
    for t in range(8):
        chain(t, 0, 1)
    for col, v in ((3, 1), (2, 2), (4, 1), (5, 0)):          # Exact, Length 3, Pool All, On the tap
        setting(uc, col, v)
    for col in (M.AM_COL, M.NR_COL, M.K1_COL, M.LV_COL):     # Amount All, Repeats On, Keep slot 1 Off, Live Off
        page2_pad(uc, col, 0)
    hold_open(uc)
    off = vals(uc)[4]
    for t in range(8):
        if (off >> t & 1) != (t == 7):
            ET.press(uc, t); ET.release(uc, t)
    ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)
    tap(uc, clear=True)
    tap(uc)
    K, L = keys(), lists()
    want_set = 2 | 1 << 3 | 1 << 5                           # Length 3, Exact, Pool All
    check("seeds: a tap: tracks 1-7 a key each (a seed, the settings, the chain 1-2), each list in RAM the one its key makes; track 8 "
          "(off) none", all(K[t] & 0xFFF and K[t] >> 12 & 0x3FF == want_set and K[t] >> 22 == 1 << 3 and len(L[t]) == 3 and
                            L[t] == gen(uc, t, K[t]) for t in range(7)) and K[7] == 0 and L[7] == [] and vals(uc)[4] == 0x80,
          ([hex(k) for k in K], L))
    check("  the seeds differ track to track", len({k & 0xFFF for k in K[:7]}) == 7)
    uc.mem_write(SLOT + M.O_LISTS, bytes(M.O_RKEY + 4 * 8 - M.O_LISTS))
    check("a project load (the lists in RAM gone): the same lists again from the keys", lists() == L, lists())
    saved = block(uc)
    other = [mk(0x111 + 9 * t, 2, first=0, last=1) for t in range(8)]
    for t in range(8):
        set_key(uc, t, other[t])
    check("  another project's keys: its lists", lists() == [gen(uc, t, other[t]) for t in range(8)])
    old = bytearray(saved)
    old[2] = (sum(old[M.B_VAL:]) & 0xFF) ^ 0x5A
    uc.mem_write(blk(uc), bytes(old))
    check("  a project of the builds before (their check byte): no lists, the settings the defaults", lists() == [[]] * 8 and
          vals(uc) == [4, 0, 0, 0, 0], vals(uc))
    uc.mem_write(blk(uc), saved)
    check("  the first project again: its lists", lists() == L)

    setting(uc, 2, 4)                                     # Length 5
    check("Live Off, Length 5: the keys and the lists kept", keys() == K and lists() == L)
    setting(uc, 2, 2)
    setting(uc, 5, 1)                                     # Every chain end
    check("Live Off, When Every chain end: nothing until a tap (no track renews)", renew(uc) == 0 and keys() == K, hex(renew(uc)))
    setting(uc, 5, 0)
    page2_pad(uc, M.LV_COL, 1)
    check(f"page 2, column 7, row 2: Live On (the block's byte {M.B_VAL2}, bit {M.LV_BIT}); the keys kept",
          block(uc)[M.B_VAL2] >> M.LV_BIT & 1 == 1 and keys() == K, block(uc)[M.B_VAL2])
    hold_open(uc)
    ET.press(uc, M.ID_DOWN); ET.release(uc, M.ID_DOWN)
    page_ok(uc, "  page 2: column 7 Live, On (row 2) full, Off (row 1) dim")
    ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)
    setting(uc, 2, 4)                                     # Length 5
    K5, L5 = keys(), lists()
    check("Live On, Length 5: tracks 1-7 lists of 5, their first 3 slots kept (the same seeds and chains); track 8 (off) kept",
          all(len(L5[t]) == 5 and L5[t][:3] == L[t] and K5[t] & ~M.K_SET == K[t] & ~M.K_SET for t in range(7)) and
          K5[7] == K[7] and L5[7] == L[7], (L5, L))
    setting(uc, 2, 2)                                     # Length 3
    check("  Length 3 again: the first lists back (the same keys)", keys() == K and lists() == L)
    setting(uc, 4, 0)                                     # Pool With steps
    check("  Pool With steps: track 1 only its patterns with hits (1, 3, 6), the tracks with no hits none, their keys kept",
          set(lst(uc, 0)) <= {0, 2, 5} and len(lst(uc, 0)) == 3 and lst(uc, 1) == [] and all(key_of(uc, t) for t in range(7)),
          lists())
    setting(uc, 4, 1)                                     # Pool All
    check("  Pool All again: the first lists back", lists() == L)
    page2_pad(uc, M.NR_COL, 1)
    check("  Repeats Off: no slot the same as the one before it (the list loops)",
          all(x[i] != x[i - 1] for x in lists()[:7] for i in range(3)), lists())
    page2_pad(uc, M.NR_COL, 0)
    check("  Repeats On again: the first lists back", lists() == L)
    setting(uc, 5, 1)                                     # Every chain end
    check("  When Every chain end: at once, as a tap: tracks 1-7 (on) renew, track 8 (off) not; the lists kept until then",
          renew(uc) == 0x7F and keys() == K, hex(renew(uc)))
    for k in range(3):
        nxt(uc, 0, 1, 0, 1)
    check("  track 1 plays its list to the end: a new list (a new seed) for after it", key_of(uc, 0) & 0xFFF != K[0] & 0xFFF and
          len(lst(uc, 0)) == 3, (hex(key_of(uc, 0)), hex(K[0])))
    setting(uc, 5, 0)
    for t in range(8):
        set_key(uc, t, K[t])

    scmsg(uc, 0x70, 10, 0)
    check("save scene 11: its lists the tracks' (their keys in the scene)", scene_lists(uc, 10) == L, scene_lists(uc, 10))
    tap(uc)
    check("  a new tap: new lists", lists()[:7] != L[:7])
    for t in range(8):
        call(uc, LB["c_scget"], 10, t, 0)
    check("  scene 11 again (stopped): its lists", lists() == L, lists())
    setting(uc, 2, 4)                                     # Length 5
    check("  then Live, Length 5: the scene's lists grow (their first 3 slots kept)",
          all(len(x) == 5 and x[:3] == L[t] for t, x in enumerate(lists()[:7])), lists())
    setting(uc, 2, 2)
    check("  Length 3 again: the scene's lists", lists() == L)
    scmsg(uc, 0x68, 2, 10)
    page2_pad(uc, M.LV_COL, 0)

    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    set_clear(uc, 1)
    o = lights(uc)
    red = u32(uc, M.COLOURS + 4 * M.CLR_RED)
    check("Patterns page, Clear held (no Shift), lists: Duplicate red", o[M.LED_DUP] == red, f"{o[M.LED_DUP]:06x}")
    ET.press(uc, M.ID_DUP); ET.tick(uc, 400); lights(uc); ET.release(uc, M.ID_DUP)
    set_clear(uc, 0)
    check("  Clear + Duplicate, held 400 ms: every list and key gone, the page not opened",
          lists() == [[]] * 8 and keys() == [0] * 8 and not is_open(uc))
    tap(uc)
    set_clear(uc, 1)
    ET.press(uc, M.ID_DUP)
    set_clear(uc, 0)
    ET.release(uc, M.ID_DUP)
    check("  Clear + Duplicate, Clear let go first: the lists gone at the press, no mutate at the release", lists() == [[]] * 8)
    set_shift(uc, 1)
    ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)
    set_shift(uc, 0)
    check("  Shift + Duplicate still mutates", all(lists()[:7]))
    tap(uc, clear=True)
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    plain = lights(uc)
    set_clear(uc, 1)
    o = lights(uc)
    set_shift(uc, 1)
    o2 = lights(uc)
    set_shift(uc, 0)
    set_clear(uc, 0)
    g = u32(uc, M.COLOURS + 4 * M.GREEN)
    check("no lists, Clear held: Duplicate not red (its light as without Clear); Clear + Shift: Shift's dim green",
          o[M.LED_DUP] == plain[M.LED_DUP] != red and o2[M.LED_DUP] == ET.scl(g, M.DUP_DIM),
          (f"{o[M.LED_DUP]:06x}", f"{plain[M.LED_DUP]:06x}", f"{o2[M.LED_DUP]:06x}"))


def chain_item(uc, t):
    call(uc, M.PARAM_GET, u32(uc, M.CHAINS), t)
    return uc.reg_read(UC_ARM_REG_R0)


def real_play():
    """the stock's clock and sequencer for 7 s, track 1 with a list of 3 (4, 2, 7; seeds: a key's): the patterns it plays (the engine's
    playing store)"""
    import playfix
    fw, ram = Path(sys.argv[2]).read_bytes(), Path(sys.argv[3]).read_bytes()
    uc = PF.machine(fw, ram)
    uc.mem_write(ET.rhstate.HEAP_LIMIT_PTR, struct.pack("<I", ET.rhstate.ST))
    uc.mem_write(ET.rhstate.ST, bytes(ET.rhstate.SIZE))
    uc.mem_write(ET.rhstate.ST, struct.pack("<I", ET.rhstate.MAGIC))
    if SEEDS:
        seed = 0x5C3                                      # Repeats Off, and the chain's pattern 1 not in the list (as 4, 2, 7)
        while 0 in gen(uc, 0, mk(seed, 3, val2=1 << M.NR_BIT)):
            seed += 1
        k = mk(seed, 3, val2=1 << M.NR_BIT)
        set_key(uc, 0, k)
        L = gen(uc, 0, k)
    else:
        L = [3, 1, 6]
        b = bytearray(M.BLK_LEN)
        b[0], b[1] = M.MARK0, M.MARK1
        b[M.B_LISTS:M.B_LISTS + 4] = bytes([3] + L)
        b[2] = (sum(b[M.B_VAL:]) & 0xFF) ^ M.CHECK
        uc.mem_write(blk(uc), bytes(b))
    uc.mem_write(SLOT + M.O_POS, b"\xff")

    def playing(off):
        call(uc, M.PARAM_GET, u32(uc, M.ENG + off), 0)
        return uc.mem_read(uc.reg_read(UC_ARM_REG_R0), 1)[0]

    uc.mem_write(playfix.UWTICK, struct.pack("<I", 1000))
    call(uc, PF.SETMODE, PF.CLOCK, 0)
    call(uc, PF.TICK, 0, PF.CLOCK)
    seen = [playing(0x30)]
    ahead = []
    for m in range(1, 7001):
        uc.mem_write(playfix.UWTICK, struct.pack("<I", 1000 + m))
        call(uc, PF.TICK, 0, PF.CLOCK)
        p, la = playing(0x30), playing(0x70)
        if p != seen[-1]:
            seen.append(p)
        if la != p and (not ahead or ahead[-1] != la):
            ahead.append(la)
    check("the stock's sequencer plays track 1's list in order (the playing store), the look-ahead store before each the same",
          seen[1:5] == L + L[:1] and (ahead[:4] == L + L[:1] if REP.get("scchain") else ahead[:3] == L[1:] + L[:1]),
          (seen, ahead, L))


def scene_play(chain):
    """(scchain) the stock's clock: scene 1 (pattern 1, each track a list of 3 without patterns 1 and 5), scene 2 (pattern 5, no lists);
    chain: the scene chain 1-2 moves on after every track's list's last slot; else scene 2 pressed mid-pattern, the lists kept to the
    switch at track 1's pattern end"""
    import playfix
    fw, ram = Path(sys.argv[2]).read_bytes(), Path(sys.argv[3]).read_bytes()
    uc = PF.machine(fw, ram)
    uc.mem_write(ET.rhstate.HEAP_LIMIT_PTR, struct.pack("<I", ET.rhstate.ST))
    uc.mem_write(ET.rhstate.ST, bytes(ET.rhstate.SIZE))
    uc.mem_write(ET.rhstate.ST, struct.pack("<I", ET.rhstate.MAGIC))
    for t in range(8):
        uc.mem_write(chain_item(uc, t), b"\x04\x04")
        set_key(uc, t, 0)
    scmsg(uc, 0x70, 1, 0)
    keys = []
    for t in range(8):
        uc.mem_write(chain_item(uc, t), b"\x00\x00")
        k = 0x123 + 37 * t
        while {0, 4} & set(gen(uc, t, mk(k, 3))):
            k += 1
        keys.append(mk(k, 3))
        set_key(uc, t, keys[t])
    scmsg(uc, 0x70, 0, 0)
    lists = [gen(uc, t, keys[t]) for t in range(8)]
    uc.mem_write(SLOT + M.O_POS, b"\xff" * 8)
    if chain:
        uc.mem_write(item(uc, M.O_SCASK, 0), bytes([0, 1]))
    scene = lambda: uc.mem_read(item(uc, 0x2C, 0), 1)[0]
    playing = lambda: [uc.mem_read(item(uc, M.O_PLAYING + 4 * t, 0), 1)[0] for t in range(8)]
    uc.mem_write(playfix.UWTICK, struct.pack("<I", 1000))
    call(uc, PF.SETMODE, PF.CLOCK, 0)
    call(uc, PF.TICK, 0, PF.CLOCK)
    log, kept = [], None
    for m in range(1, 9001):
        uc.mem_write(playfix.UWTICK, struct.pack("<I", 1000 + m))
        if not chain and m == 3300:
            call(uc, LB["c_mxpad"], 0x2004E090, 17, 127)
            call(uc, LB["c_mxpr"], 0x2004E090, 17, 0)
            kept = [lst(uc, t) for t in range(8)]
        call(uc, PF.TICK, 0, PF.CLOCK)
        st = (scene(), playing())
        if not log or st != log[-1][1:]:
            log.append((m,) + st)
    if chain:
        start = next(r[0] for r in log if r[1] == 0 and r[0] > 2000)
        sw = [r[0] for r in log if r[1] == 1 and r[0] > start]
        check("the scene chain 1-2: scene 1 plays its lists of 3 (3 bars), then scene 2 (every track's list at its last slot)",
              sw and 5900 < sw[0] - start < 6100, log[-6:])
    else:
        before = [r for r in log if 3300 <= r[0] and r[1] == 0]
        sw = [r[0] for r in log if r[1] == 1]
        check("scene 2 pressed mid-pattern: the lists kept, no track back to its chain's pattern before the switch, then scene 2",
              kept == lists and all(0 not in r[2] for r in before) and sw and log[-1][2] == [4] * 8, log[-4:])


def play_start(chain):
    """(scplay) the stock's Play (its seek from the start, 0x08034082): scene 1 (pattern 1, no lists), scene 2 (pattern 5, lists), the
    state scene 2's (a project saved while it played); chain (scenes 1-2): scene 1 starts with its own patterns, scene 2 then with its
    lists; else (scene 2 alone): the lists play from the start"""
    import playfix
    fw, ram = Path(sys.argv[2]).read_bytes(), Path(sys.argv[3]).read_bytes()
    uc = PF.machine(fw, ram)
    uc.mem_write(ET.rhstate.HEAP_LIMIT_PTR, struct.pack("<I", ET.rhstate.ST))
    uc.mem_write(ET.rhstate.ST, bytes(ET.rhstate.SIZE))
    uc.mem_write(ET.rhstate.ST, struct.pack("<I", ET.rhstate.MAGIC))
    for t in range(8):
        uc.mem_write(chain_item(uc, t), b"\x00\x00")
        set_key(uc, t, 0)
    scmsg(uc, 0x70, 0, 0)
    keys = []
    for t in range(8):
        uc.mem_write(chain_item(uc, t), b"\x04\x04")
        k = 0x123 + 37 * t
        while {0, 4} & set(gen(uc, t, mk(k, 3, first=4, last=4))):
            k += 1
        keys.append(mk(k, 3, first=4, last=4))
        set_key(uc, t, keys[t])
    scmsg(uc, 0x70, 1, 0)
    lists = [gen(uc, t, keys[t]) for t in range(8)]
    uc.mem_write(SLOT + M.O_POS, b"\xff" * 8)
    uc.mem_write(item(uc, M.O_SCASK, 0), bytes([0, 1]) if chain else bytes([1, 1]))
    uc.mem_write(item(uc, 0x2C, 0), bytes([1]))
    scene = lambda: uc.mem_read(item(uc, 0x2C, 0), 1)[0]
    playing = lambda: [uc.mem_read(item(uc, M.O_PLAYING + 4 * t, 0), 1)[0] for t in range(8)]
    uc.mem_write(playfix.UWTICK, struct.pack("<I", 1000))
    call(uc, PF.SETMODE, PF.CLOCK, 0)
    call(uc, 0x08034082, M.ENG, 0)
    first = (scene(), playing(), [lst(uc, t) for t in range(8)])
    log = []
    for m in range(1, 2601):
        uc.mem_write(playfix.UWTICK, struct.pack("<I", 1000 + m))
        call(uc, PF.TICK, 0, PF.CLOCK)
        st = (scene(), playing())
        if not log or st != log[-1][1:]:
            log.append((m,) + st)
    if chain:
        check("Play, the scene chain 1-2 (the state scene 2's mutate): scene 1 with its own patterns, no lists; then scene 2 with "
              "its lists", first[0] == 0 and first[1] == [0] * 8 and first[2] == [[]] * 8 and log[-1][1] == 1 and
              log[-1][2] == [L[0] for L in lists], (first, log[-3:]))
    else:
        check("Play, scene 2 alone: the mutate as saved, slot 1 at the start", first[0] == 1 and
              first[1] == [L[0] for L in lists] and first[2] == lists, (first, log[-2:]))


def livecol_tests(uc):
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    hold_open(uc)
    page_ok(uc, "Live on column 1, page 1")
    ET.pad(uc, 8 + M.LV_COL); ET.unpad(uc, 8 + M.LV_COL)
    on = block(uc)[M.B_VAL2] >> M.LV_BIT & 1
    page_ok(uc, "  page 1, column 1, row 2: Live On, drawn")
    ET.press(uc, M.ID_DOWN); ET.release(uc, M.ID_DOWN)
    page_ok(uc, "  page 2: Live On on column 1 too")
    ET.pad(uc, M.LV_COL); ET.unpad(uc, M.LV_COL)
    off = block(uc)[M.B_VAL2] >> M.LV_BIT & 1
    page_ok(uc, "  page 2, column 1, row 1: Live Off")
    ET.press(uc, M.ID_UP); ET.release(uc, M.ID_UP)
    page_ok(uc, "  page 1: Live Off there too")
    ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)
    check("  Live in the block's byte: On, then Off", (on, off) == (1, 0), (on, off))


def views_tests(uc):
    import rhbuild
    img = Path(sys.argv[2]).read_bytes()
    pv_vt = lambda k: struct.unpack_from("<I", img, M.PV_VT + 4 * k - rhbuild.BASE)[0]
    MIXV, FXV, CONT = M.MIX_VIEW, M.FX_VIEW, M.CONT
    was = bytes(uc.mem_read(CONT + M.O_CMODE, 1))
    stock = []
    h = [uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: stock.append(a), None, x & ~1, (x & ~1) + 1)
         for x in (LB["c_mxpad"], u32(uc, 0x08067990))]

    def on(view, mode=None):
        if mode is not None:
            uc.mem_write(CONT + M.O_CMODE, bytes([mode]))
        uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", view))
        hold_open(uc)
        return is_open(uc)
    for row, (name, view, mode) in enumerate((("the Mixer (Grid FX)", MIXV, None), ("the FX view", FXV, None),
                                              ("the Sidechain view", CONT, M.MODE_SC)), 1):
        opened = on(view, mode)
        page_ok(uc, f"{name}: Shift + hold Duplicate opens the page, drawn")
        before = block(uc)[M.B_VAL]
        del stock[:]
        ET.pad(uc, 8 * row + M.COLS[0]); ET.unpad(uc, 8 * row + M.COLS[0])
        got = block(uc)[M.B_VAL]
        check(f"  {name}: a pad sets the page's setting (Length {row + 1}), not the view's own pad", opened and got != before and not stock,
              (opened, before, got, [hex(x) for x in stock]))
        ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)
        check(f"  {name}: Duplicate closes the page", not is_open(uc))
        set_key(uc, 0, 0) if SEEDS else set_list(uc, 0, [])
        set_shift(uc, 1)
        ET.press(uc, M.ID_DUP); ET.tick(uc, 100); lights(uc); ET.release(uc, M.ID_DUP)
        set_shift(uc, 0)
        check(f"  {name}: Shift + tap Duplicate mutates", any(lst(uc, t) for t in range(8)), [lst(uc, t) for t in range(8)])
        set_clear(uc, 1)
        red = lights(uc)[M.LED_DUP] == u32(uc, M.COLOURS + 4 * M.CLR_RED)
        ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)
        set_clear(uc, 0)
        set_clear(uc, 1)
        dark = lights(uc)[M.LED_DUP] != u32(uc, M.COLOURS + 4 * M.CLR_RED)
        set_clear(uc, 0)
        check(f"  {name}: Clear held, Duplicate red; Clear + Duplicate ends every mutate; then not red", red and dark and
              all(lst(uc, t) == [] for t in range(8)), (red, dark, [lst(uc, t) for t in range(8)]))
    uc.mem_write(CONT + M.O_CMODE, bytes([0]))
    check("a track view (the container, not Sidechain): the page never opens", not on(CONT))
    uc.mem_write(CONT + M.O_CMODE, was)
    for x in h:
        uc.hook_del(x)
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    setting(uc, M.COLS[0], 3)


def bounce_tests(uc):
    """(bounce) a button that closes the page, held past the stock's hold: the page again on its release, on a page's view"""
    def run(held_ms, back_to, bid=14):
        uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
        hold_open(uc)
        ET.press(uc, bid)
        shut = not is_open(uc)
        uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.MIX_VIEW))
        ET.tick(uc, held_ms); lights(uc)
        during = is_open(uc)
        ET.release(uc, bid)
        uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", back_to))
        lights(uc)
        after = is_open(uc)
        if after:
            ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)
        return shut, during, after
    r = run(500, M.PV)
    check("the page open, Mixer held (500 ms): closed while held, open again on the release", r == (True, False, True), r)
    r = run(100, M.MIX_VIEW)
    check("  Mixer tapped (100 ms): the page stays closed (the Mixer shows)", r == (True, False, False), r)
    r = run(500, M.FX_VIEW, 15)
    check("  FX held, then back on the FX view: open again", r == (True, False, True), r)
    uc.mem_write(M.CONT + M.O_CMODE, bytes([0]))
    r = run(500, M.CONT)
    check("  held, then on a track view: the page stays closed", r == (True, False, False), r)
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))


def shtrk_tests(uc):
    """(shtrk) the page open, Shift + a track button: the page closes, the stock gets the press with its Shift flag down; held past the
    stock's hold, the page again on its release; a tap leaves it closed"""
    flag = lambda: uc.mem_read(item_ctrl(uc), 1)[0]
    plain = []
    back = []

    def run(held_ms, back_to, t=2):
        uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
        hold_open(uc)
        off0 = vals(uc)[4]
        set_shift(uc, 1)
        held0 = u32(uc, C.CTRL + M.O_HELD)
        uc.mem_write(C.CTRL + M.O_HELD, struct.pack("<I", held0 | 1 << M.BIT_SHIFT if REP.get("shkeep") else held0))
        reads = []
        nxt = int(REP["prev_btn"], 16)
        fa = item_ctrl(uc)
        hk = uc.hook_add(UC_HOOK_CODE, lambda u, ad, n, d: reads.append(u.mem_read(fa, 1)[0]), None, nxt, nxt + 1)
        ET.press(uc, t)
        uc.hook_del(hk)
        plain.append(reads == [0])
        shut, kept = not is_open(uc), vals(uc)[4] == off0
        up = 1 - flag() if REP.get("shkeep") else flag()
        uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", back_to))
        ET.tick(uc, held_ms); lights(uc)
        ET.release(uc, t)
        if REP.get("shkeep"):
            back.append(flag())
            uc.mem_write(C.CTRL + M.O_HELD, struct.pack("<I", u32(uc, C.CTRL + M.O_HELD) & ~(1 << M.BIT_SHIFT)))
        set_shift(uc, 0)
        uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", back_to))
        lights(uc)
        after = is_open(uc)
        if after:
            ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)
        return shut, kept, up, after
    r = run(500, M.PV)
    check("the page open, Shift + track 3 held: the page closes (track 3's on / off kept), Shift up after; open again on the release",
          r == (True, True, 1, True), r)
    uc.mem_write(M.CONT + M.O_CMODE, bytes([0]))
    r = run(100, M.CONT)
    check("  Shift + track 3 tapped, the stock on the track view: the page stays closed", r == (True, True, 1, False), r)
    check("  both presses: the next handler gets the press once, with the Shift flag down (a plain track press)", plain == [True, True],
          plain)
    if REP.get("shkeep"):
        check("  Shift's flag down while the track is held (the track page with no Shift layer); up again at its release, Shift held",
              back == [1, 1], back)
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    hold_open(uc)
    off0 = vals(uc)[4]
    ET.press(uc, 2); ET.release(uc, 2)
    check("  a track button without Shift: the page stays open, track 3 on / off", is_open(uc) and vals(uc)[4] == off0 ^ 4,
          (is_open(uc), off0, vals(uc)[4]))
    ET.press(uc, 2); ET.release(uc, 2)
    if REP.get("shtrkled"):
        ET.press(uc, 2); ET.release(uc, 2)
        set_shift(uc, 1)
        o = lights(uc)
        set_shift(uc, 0)
        call(uc, M.SELTRK, M.CONT)
        sel = uc.reg_read(UC_ARM_REG_R0)
        tc = [u32(uc, M.COLOURS + 4 * M.TRK_SLOTS[t]) for t in range(8)]
        want = [tc[t] if t == sel else ET.scl(tc[t], M.DIM) for t in range(8)]
        got = [o[M.LED_TRK0 + t] for t in range(8)]
        check(f"  the page, Shift held: the track buttons as a track view (each colour dim, the selected track {sel + 1} full); "
              "track 3 off on the page still shown in its colour", got == want and sel < 8, ([f"{x:06x}" for x in got], sel))
        o = lights(uc)
        check("  Shift up: the page's track buttons again (track 3 very dim, off)", o[M.LED_TRK0 + 2] == ET.scl(tc[2], M.VDIM))
        ET.press(uc, 2); ET.release(uc, 2)
    ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)


def clrpage_tests(uc):
    """(clrpage) the page open, Clear held (the preview): Down / Up page the Patterns view (its byte, its arrows), the page's own kept"""
    pvpage = lambda: uc.mem_read(M.PV + M.O_PV_PAGE, 1)[0]
    for view in (M.PV, M.MIX_VIEW):
        uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", view))
        uc.mem_write(M.PV + M.O_PV_PAGE, b"\x00")
        hold_open(uc)
        set_clear(uc, 1)
        ET.press(uc, M.ID_DOWN); ET.release(uc, M.ID_DOWN)
        o = lights(uc)
        a = (pvpage(), page(uc), o[M.LED_UP], o[M.LED_DOWN])
        ET.press(uc, M.ID_UP); ET.release(uc, M.ID_UP)
        o = lights(uc)
        b = (pvpage(), page(uc), o[M.LED_UP], o[M.LED_DOWN])
        set_clear(uc, 0)
        ET.press(uc, M.ID_DOWN); ET.release(uc, M.ID_DOWN)
        c = (pvpage(), page(uc))
        ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)
        name = "Patterns" if view == M.PV else "Mixer"
        check(f"the page on {name}, Clear held: Down = the Patterns view's page 2 (Up white), Up = page 1 (Down white), the "
              "settings page kept; Clear up: Down = the settings page 2", a == (1, 0, M.WHITE, 0) and b == (0, 0, 0, M.WHITE) and
              c == (0, 1), (a, b, c))
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))


def shmut_tests(uc):
    """(shmut) on the page: Shift + Duplicate mutates (the page kept open); Duplicate alone closes it"""
    for t in range(8):
        call(uc, LB["c_mtcl"], t)
    for view in (M.PV, M.MIX_VIEW):
        uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", view))
        hold_open(uc)
        set_shift(uc, 1)
        ET.press(uc, M.ID_DUP); ET.tick(uc, 100); lights(uc); ET.release(uc, M.ID_DUP)
        set_shift(uc, 0)
        a = (is_open(uc), [lst(uc, t) for t in range(8)])
        set_shift(uc, 1)
        ET.press(uc, M.ID_DUP); ET.tick(uc, 600); lights(uc); ET.release(uc, M.ID_DUP)
        set_shift(uc, 0)
        b = (is_open(uc), [lst(uc, t) for t in range(8)])
        ET.press(uc, M.ID_DUP); ET.release(uc, M.ID_DUP)
        c = is_open(uc)
        name = "Patterns" if view == M.PV else "Mixer"
        check(f"the page on {name}: Shift + Duplicate mutates, the page stays open; again (held 600 ms): new lists, still open; "
              "Duplicate alone closes it", a[0] and any(a[1]) and b[0] and b[1] != a[1] and not c, (a, b, c))
        for t in range(8):
            call(uc, LB["c_mtcl"], t)
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))


def item_ctrl(uc):
    call(uc, M.PARAM_GET, u32(uc, C.CTRL + M.O_SHIFTF), 0)
    return uc.reg_read(UC_ARM_REG_R0)


if __name__ == "__main__":
    main()
