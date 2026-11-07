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
    b = block(uc)
    o = M.B_LISTS + M.LIST_LEN * t
    return list(b[o + 1:o + 1 + b[o]])


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
    real_play()


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
    check("  the Mixer's pad 17 (scene 1): every list gone at the press", all(lst(uc, t) == [] for t in range(8)) and renew(uc) == 0)
    uc.mem_write(item(uc, M.O_SCASK, 1), b"\x00")         # the scene started
    tap(uc)
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", MIX))
    ET.pad(uc, 18); ET.unpad(uc, 18)
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
    """scene sc's lists (None: no lists in it)"""
    _, b = scene_bytes(uc, sc)
    if b[28] != (sum(b[:28]) + sc) & 0xFF ^ M.SC_CHECK:
        return None
    bits = int.from_bytes(b[:28], "little")
    out = []
    for t in range(8):
        n = bits >> 28 * t & 15
        out.append([bits >> 28 * t + 4 + 3 * j & 7 for j in range(n)])
    return out


def scmsg(uc, cmd, r2, r3):
    call(uc, LB["c_scmsg"], SCOBJ, u32(uc, SCOBJ + cmd), r2, r3)


def scenesave_tests(uc):
    import rhbuild
    img = Path(sys.argv[2]).read_bytes()
    o = M.SCMSG_VT - rhbuild.BASE
    check("the scene commands' handler (0x08068B18) is c_scmsg", struct.unpack_from("<I", img, o)[0] == LB["c_scmsg"] | 1)
    want = [[5, 2, 0], [], [7, 7, 1, 3, 4, 6, 0, 2], [], [3], [], [], [1, 1]]
    for t in range(8):
        set_list(uc, t, want[t])
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
    check("scene 4 starts, the look-ahead: its slot 1, track 1's list kept", a == 5 and lst(uc, 0) == [6], (a, lst(uc, 0)))
    p = nxt(uc, 0, 1, 0, 1, scene=1, sc=3)
    check("  the play: track 1 the scene's list, slot 1 playing", p == 5 and lst(uc, 0) == [5, 2, 0] and pos(uc, 0) == 0,
          (p, lst(uc, 0), pos(uc, 0)))
    p = nxt(uc, 2, 1, 0, 1, scene=1, sc=3)
    check("  track 3: its list of 8", p == 7 and lst(uc, 2) == want[2], (p, lst(uc, 2)))
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
    for t in range(8):
        set_list(uc, t, want[t])
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
    check("  playing, pad 17 (scene 1): every list gone at the press", all(lst(uc, t) == [] for t in range(8)))
    uc.mem_write(item(uc, M.O_SCASK, 1), b"\x00")
    uc.mem_write(run, bytes(was))
    uc.mem_write(C.CTRL + M.O_VIEW, struct.pack("<I", M.PV))
    scmsg(uc, 0x68, 2, 8)
    if REP.get("scenefix"):
        mixscene_tests(uc, img, want)


def mixscene_tests(uc, img, want):
    """the Mixer's scene pads, through the stock's own sends (its scene object at view + 0x0C, base 0x2003D300)"""
    import rhbuild
    o = M.SCMSG_VT2 - rhbuild.BASE
    check("the second base's slot (0x08068B24) is c_scmsg2", struct.unpack_from("<I", img, o)[0] == LB["c_scmsg2"] | 1)
    MIX, SO = 0x2004E090, 0x2004E09C
    held = ET.ptr(uc, u32(uc, SO + 0x28), 0)              # bit 0 Clear, bit 1 Duplicate (the scene object's)
    copied = u32(uc, SO + 0x2C)
    was = bytes(uc.mem_read(copied, 1))
    uc.mem_write(copied, bytes(1))                        # nothing copied: the next Duplicate + pad copies
    for t in range(8):
        set_list(uc, t, want[t])
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
    check(f"Patterns page, Clear held: the track buttons of tracks 1, 3, 6 (a list) green, the others {NW}; the pads and Duplicate "
          "as without Clear", [o[M.LED_TRK0 + t] for t in range(8)] == want_trk and all(o[k] == closed[k] for k in range(32)) and
          o[M.LED_DUP] == closed[M.LED_DUP], [f"{o[M.LED_TRK0 + t]:06x}" for t in range(8)])
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


def chain_item(uc, t):
    call(uc, M.PARAM_GET, u32(uc, M.CHAINS), t)
    return uc.reg_read(UC_ARM_REG_R0)


def real_play():
    """the stock's clock and sequencer for 7 s, track 1 with the list 4, 2, 7: the patterns it plays (the engine's playing store)"""
    import playfix
    fw, ram = Path(sys.argv[2]).read_bytes(), Path(sys.argv[3]).read_bytes()
    uc = PF.machine(fw, ram)
    uc.mem_write(ET.rhstate.HEAP_LIMIT_PTR, struct.pack("<I", ET.rhstate.ST))
    uc.mem_write(ET.rhstate.ST, bytes(ET.rhstate.SIZE))
    uc.mem_write(ET.rhstate.ST, struct.pack("<I", ET.rhstate.MAGIC))
    b = bytearray(M.BLK_LEN)
    b[0], b[1] = M.MARK0, M.MARK1
    b[M.B_LISTS:M.B_LISTS + 4] = bytes([3, 3, 1, 6])
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
          seen[1:5] == [3, 1, 6, 3] and ahead[:3] == [1, 6, 3], (seen, ahead))


if __name__ == "__main__":
    main()
