"""Unicorn test of stepmut on a build with it: Shift + tap Duplicate mutates on the release, Shift + hold opens the page, the page's
pads, lights and buttons, a held view button, the settings in the project, and each target's change (inside the pattern's start
and end only).

    python tests/emu_stepmut.py STOCK.bin BUILT.bin RAM.bin
"""
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("RH_BUILD", Path(sys.argv[2]).parent.name if len(sys.argv) > 2 else "a0126")
import emu_tmenu as ET  # noqa: E402  (ourram's layout from the build's manifest)
from emu_tmenu import C, T, call, check, ptr, u32  # noqa: E402
from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1  # noqa: E402

R = ET.MAN["report"]["stepmut"]
LB = {k: int(v, 16) for k, v in R["labels"].items()}
PREV = {k: int(v, 16) for k, v in R["prev"].items()}
SLOT = int(R["slot"], 16)
TM = int(ET.MAN["report"]["tmenu"]["slot"], 16)                 # the Track Parameter Editor: + 0 open, + 2 its track press, + 34 Shift + track
RRT = int(ET.MAN["report"]["rhrec"]["labels"]["c_rrt"], 16)
ENGINE, PAT_SZ, MUT_CALL = 0x2003D2FC, 0xA28, 0x0803656C
GRAD0, PULSE, LED_DUP = 0x76, 0x0A, 56
T_PAD = (0, 1, 2, 8, 16, 17, 24, 25, 26, 27)
NOTE, SAMPLE, MOVE, VEL, GATE, MICRO, LEN, SPEED, MODE, PROB = range(10)
ON, COL0, VERSION = 10, 5, 2
CLR_CUE, CLR_RED = 0x54, 0x55
DEF = bytes([0x2E, 0x0A, 0x00, 0x2A, 0x2A, 0x1E, 0x02, 0x02, 0x07, 0x0A, 1 << MOVE, 0])
T_RGB = (0xFFC866, 0xEECE66, 0xDDD466, 0xCCDA66, 0xBBE066, 0xAAE766, 0x99ED66, 0x88F366, 0x77F966, 0x66FF66)
OUT, FRAME = 0x2004FA00, 0x2004FD00
BIT_DUP, BIT_SHIFT, ID_PATTERNS = 24, 27, 13


def b8(uc, a): return uc.mem_read(a, 1)[0]
def tick(uc, ms): uc.mem_write(C.HAL_TICK, struct.pack("<I", u32(uc, C.HAL_TICK) + ms))
def obj(uc, t): return u32(uc, ENGINE + 0x84 + 4 * t)
def pat(uc, t): return u32(uc, obj(uc, t) + 4) + PAT_SZ * (b8(uc, ptr(uc, u32(uc, obj(uc, t) + 0x28), 0)) & 7)
def tail(uc): call(uc, RRT); return uc.reg_read(UC_ARM_REG_R0)
def blk(uc): return tail(uc) + R["blk_off"]
def sel(uc, t): uc.mem_write(ptr(uc, u32(uc, T.CONT + 0x25C), 0), bytes([t]))
def is_open(uc): return b8(uc, SLOT) & 1 == 1
def view(uc, v): uc.mem_write(C.CTRL + 0x7C, struct.pack("<I", v))


def held(uc, bit, on):
    v = u32(uc, C.CTRL + 0xA0)
    uc.mem_write(C.CTRL + 0xA0, struct.pack("<I", v | 1 << bit if on else v & ~(1 << bit)))


def btn(uc, i): call(uc, C.BTN_ENTRY, C.CTRL, i)
def rel(uc, i): call(uc, C.BTN_RELEASE, C.CTRL, i)
def pad(uc, p): call(uc, T.PP_ENTRY, C.CTRL, p, 100)
def unpad(uc, p): call(uc, T.PR_ENTRY, C.CTRL, p)
def tpad(uc, p): pad(uc, p); unpad(uc, p)


def out(uc):
    uc.mem_write(FRAME, bytes(140))
    uc.mem_write(OUT, bytes(69 * 4))
    call(uc, LB["c_sm_out"], C.CTRL, OUT, FRAME)
    return struct.unpack("<69I", uc.mem_read(OUT, 69 * 4))


def dup_down(uc, t=0):
    """Shift + Duplicate pressed: the stock's Mutate call follows the press (0x0803656C -> c_sm_mut)"""
    held(uc, BIT_SHIFT, True)
    btn(uc, 24)
    held(uc, BIT_DUP, True)
    call(uc, LB["c_sm_mut"], obj(uc, t))


def dup_up(uc):
    held(uc, BIT_DUP, False)
    rel(uc, 24)
    held(uc, BIT_SHIFT, False)


def tap(uc, t=0):
    dup_down(uc, t); tick(uc, 60); out(uc); dup_up(uc); tick(uc, 7)


def open_page(uc):
    dup_down(uc); tick(uc, 340); out(uc); dup_up(uc)


def scl(rgb, lvl): return sum((((rgb >> s) & 0xFF) * (lvl + 1) >> 8) << s for s in (0, 8, 16))


def set_rec(uc, t, rec, version=VERSION):
    b = blk(uc)
    data = bytearray(uc.mem_read(b, 100))
    if data[:2] != b"SM" or data[3] != version:
        data[4:] = DEF * 8
        data[0:2] = b"SM"
        data[3] = version
    data[4 + 12 * t:16 + 12 * t] = rec
    data[2] = (sum(data[4:]) & 0xFF) ^ 0x5C
    uc.mem_write(b, bytes(data))


def only(*targets, **cols):
    r = bytearray(DEF)
    on = sum(1 << x for x in targets)
    r[ON], r[ON + 1] = on & 0xFF, on >> 8
    for k, v in cols.items():
        r[globals()[k.upper()]] = v
    return bytes(r)


def fill(uc, t=0, start=0, end=15, empty=()):
    """32 steps with a note each (velocity 10 + s; `empty`: no note), lanes 0..11 at microstep 0 = s + l; start / end"""
    p = pat(uc, t)
    for s in range(32):
        uc.mem_write(p + 8 * s, bytes([0, 6, 0 if s in empty else 1, 10 + s, 7, 0xFF, 0, 0]))
        for ln in range(12):
            uc.mem_write(p + 0x128 + 0xC0 * ln + 6 * s, bytes([(s + ln) & 0x7F]) + b"\xff" * 5)
    uc.mem_write(p + 0x100, bytes([end, start, 3, 0]))
    return p


def steps(uc, p): return [bytes(uc.mem_read(p + 8 * s, 8)) for s in range(32)]
def lanes(uc, p, s): return [bytes(uc.mem_read(p + 0x128 + 0xC0 * ln + 6 * s, 6)) for ln in range(12)]


def main():
    fw = open(sys.argv[2], "rb").read()
    ram = open(sys.argv[3], "rb").read()
    uc = ET.setup(fw, ram)
    sel(uc, 0)
    B = 0x08010000
    from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs
    ins = next(Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(fw[MUT_CALL - B:MUT_CALL - B + 4], MUT_CALL))
    check("the stock's Mutate call is ours", ins.mnemonic == "bl" and int(ins.op_str[1:], 16) == LB["c_sm_mut"])
    check("a new project reads the defaults", bytes(uc.mem_read(blk(uc), 2)) != b"SM")
    rand = []
    hk = uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: rand.append(a), None, 0x08047104, 0x08047105)

    # ---- tap: the default (Step movement, All, Anywhere) is the stock's shuffle, empty steps too, on the release
    p = fill(uc, empty=(2, 5, 9))
    before = steps(uc, p)
    lanes0 = {before[s][3]: lanes(uc, p, s) for s in range(32)}
    dup_down(uc)
    check("Shift + Duplicate down: nothing changes yet", steps(uc, p) == before)
    tick(uc, 100); out(uc)
    dup_up(uc)
    after = steps(uc, p)
    check("the release: steps 1-16 shuffled", after[:16] != before[:16] and sorted(after[:16]) == sorted(before[:16]))
    check("empty steps move too", [s for s in range(16) if after[s][2] == 0] != [2, 5, 9])
    check("steps 17-32 (past the end) unchanged", after[16:] == before[16:])
    check("each step's lanes moved with it", all(lanes(uc, p, s) == lanes0[after[s][3]] for s in range(32)))
    check("the stock's random generator", len(rand) >= 15)
    uc.hook_del(hk)
    check("the page stays closed after a tap", not is_open(uc))

    # ---- hold: the page opens at 333 ms, the release does not mutate
    p = fill(uc)
    before = steps(uc, p)
    dup_down(uc)
    tick(uc, 300); out(uc)
    check("held 300 ms: closed", not is_open(uc))
    tick(uc, 40); out(uc)
    check("held 340 ms: the page opens", is_open(uc))
    dup_up(uc)
    check("the hold's release: no mutate", steps(uc, p) == before)
    check("the page stays open after the release", is_open(uc))

    # ---- the page's lights: Step movement shown first (on, pulsing), the other targets dim; its settings on columns 6-7
    o = out(uc)
    dimmed = u32(uc, ptr(uc, u32(uc, C.CTRL + 0x88), 2)) >> 10 & 1
    full = 141 if dimmed else 255
    lo = 48 * full >> 8
    pl = 64 + ((255 - (u32(uc, T.COLOURS + 4 * PULSE) & 0xFF)) * 192 >> 8)
    lvl = [full * pl >> 8 if i == MOVE else lo for i in range(10)]
    check("target pads: Step movement on and pulsing, the others dim",
          all(o[T_PAD[i]] == scl(T_RGB[i], lvl[i]) for i in range(10)), [hex(o[q]) for q in T_PAD])
    grad = [u32(uc, T.COLOURS + 4 * (GRAD0 + c)) for c in (7, 5, 3, 1)]
    meter = lambda k, v: all(o[8 * r + COL0 + k] == scl(grad[r], full if r >= v else lo) for r in range(4))
    check("column 6: Amount All (all lit)", meter(0, 0))
    check("column 7: Range Anywhere (all lit)", meter(1, 0))
    check("columns 5 and 8 and the free pads dark", all(o[8 * r + 4] == 0 and o[8 * r + 7] == 0 for r in range(4))
          and all(o[q] == 0 for q in (3, 9, 10, 11, 18, 19, 28)))
    g = u32(uc, T.COLOURS + 4 * (GRAD0 + 7))
    check("Duplicate pulses green on the page", o[LED_DUP] == scl(g, pl))

    # ---- a tap toggles a target, a hold shows its settings; the settings in the project
    pad(uc, 8); tick(uc, 100); out(uc); unpad(uc, 8)
    b = blk(uc)
    rec = bytes(uc.mem_read(b + 4, 12))
    check("tap Velocity: on, the block ours (SM, check, version 1)", bytes(uc.mem_read(b, 2)) == b"SM" and b8(uc, b + 3) == VERSION
          and rec[ON] == (1 << MOVE | 1 << VEL) and b8(uc, b + 2) == (sum(uc.mem_read(b + 4, 96)) & 0xFF) ^ 0x5C)
    check("the other tracks keep the defaults", bytes(uc.mem_read(b + 16, 12)) == DEF)
    pad(uc, 0); tick(uc, 420); out(uc)
    check("hold Note 420 ms: Note shown", b8(uc, SLOT + 1) == NOTE + 1)
    unpad(uc, 0)
    check("the hold's release does not toggle Note", b8(uc, b + 4 + ON) & 1 == 0)
    tpad(uc, 7)
    check("Note's Direction: Up (column 8, row 1)", b8(uc, b + 4 + NOTE) >> 4 & 3 == 0)
    tpad(uc, 24 + 5)
    check("Note's Amount: A little (column 6, row 4)", b8(uc, b + 4 + NOTE) & 3 == 3)
    sm = bytes(uc.mem_read(b, 100))
    tpad(uc, 24 + 7); tpad(uc, 24 + 4)
    check("Direction has 3 values; column 5 is free: nothing", bytes(uc.mem_read(b, 100)) == sm)
    pad(uc, 24); tick(uc, 420); out(uc); unpad(uc, 24)
    o = out(uc)
    check("Pattern length (pad 25) shown: Range up to 4, End", b8(uc, SLOT + 1) == LEN + 1
          and [o[8 * r + COL0 + 1] for r in range(4)] == [scl(T_RGB[LEN], full), scl(T_RGB[LEN], lo), scl(T_RGB[LEN], lo), 0])

    # ---- buttons on the page
    calls = []
    hk = uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: calls.append(a), None, PREV["prev_btn"], PREV["prev_btn"] + 1)
    btn(uc, 3); rel(uc, 3)
    check("another track's button goes on to the stock, the page stays", len(calls) == 1 and is_open(uc))
    sel(uc, 0)
    main0 = ptr(uc, u32(uc, T.CONT + 0x260), 0)          # track 0's main view (its Note or Sample view)
    uc.mem_write(T.CONT + 0x264, bytes([b8(uc, main0)]))
    calls.clear()
    btn(uc, 0); rel(uc, 0)
    check("the selected track's button closes the page, nothing else", not calls and not is_open(uc))
    open_page(uc)
    hk3 = uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: calls.append(a), None, PREV["prev_rel"], PREV["prev_rel"] + 1)
    calls.clear(); btn(uc, 0); o = out(uc)
    check("the selected track's button held: the track's steps show, the page waits",
          not calls and is_open(uc) and b8(uc, SLOT) & 0x10 and o[T_PAD[VEL]] != scl(T_RGB[VEL], full))
    tick(uc, 400); rel(uc, 0); o = out(uc)
    check("let go after a hold: the page again, nothing else", not calls and is_open(uc) and b8(uc, SLOT) & 0x30 == 0
          and o[T_PAD[VEL]] == scl(T_RGB[VEL], full))
    uc.hook_del(hk3)
    uc.hook_del(hk)
    open_page(uc)
    held(uc, 23, True); btn(uc, C.ID_CLEAR); held(uc, 23, False); rel(uc, C.ID_CLEAR)
    check("Clear keeps the page open", is_open(uc))
    held(uc, BIT_DUP, True); btn(uc, 24); held(uc, BIT_DUP, False); rel(uc, 24)
    check("Duplicate without Shift closes the page", not is_open(uc))

    # ---- a view button: held, its view shows and the page comes back; tapped, the page closes
    def skip(addr):
        """the stock's code at addr returns at once (its release after a long hold does not run in the emulator)"""
        return uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR)), None, addr, addr + 1)

    def stub_rel(i):
        hk = skip(PREV["prev_rel"]); rel(uc, i); uc.hook_del(hk)

    open_page(uc)
    btn(uc, ID_PATTERNS)
    o = out(uc)
    check("a view button held: its view shows, the page waits", is_open(uc) and b8(uc, SLOT) & 0x10
          and o[T_PAD[MOVE]] != scl(T_RGB[MOVE], lvl[MOVE]))
    hk = skip(PREV["prev_pad"]); calls = []
    hk2 = uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: calls.append(a), None, PREV["prev_pad"], PREV["prev_pad"] + 1)
    call(uc, LB["c_sm_pad"], C.CTRL, 8, 100)
    uc.hook_del(hk); uc.hook_del(hk2)
    check("pads go to that view meanwhile", len(calls) == 1 and bytes(uc.mem_read(b + 4, 12))[ON] == (1 << MOVE | 1 << VEL))
    tick(uc, 400); stub_rel(ID_PATTERNS); view(uc, T.CONT); o = out(uc)
    check("let go after a hold: the page again", is_open(uc) and b8(uc, SLOT) & 0x30 == 0
          and o[T_PAD[VEL]] == scl(T_RGB[VEL], full))
    btn(uc, ID_PATTERNS); tick(uc, 100); stub_rel(ID_PATTERNS); view(uc, T.CONT); out(uc)
    check("a tap: the page closes", not is_open(uc))
    open_page(uc)
    btn(uc, ID_PATTERNS); tick(uc, 400); stub_rel(ID_PATTERNS); view(uc, ET.MIXER); out(uc)
    check("let go after a hold, the stock on another view: the page closes", not is_open(uc))
    view(uc, T.CONT)
    open_page(uc)
    view(uc, ET.MIXER); out(uc)
    check("leaving the track view closes the page", not is_open(uc))
    view(uc, T.CONT)

    # ---- a two-view button (11: modes 3 / 5) pressed on its own view: the stock's second view; on the page, its first
    vw = ptr(uc, u32(uc, C.CTRL + 0x14), 0)
    w_keep, m_keep = u32(uc, vw), b8(uc, T.CONT + 0x264)

    def two_view(on_page):
        if on_page:
            open_page(uc)
        uc.mem_write(T.CONT + 0x264, bytes([3]))
        uc.mem_write(vw, struct.pack("<I", (w_keep & 0xFF00FF00) | 3 << 16))
        req = []

        def mode_set(u, a, n, d):                         # the stock's mode set: note the mode asked for, "no change" back
            req.append(u.reg_read(UC_ARM_REG_R1))
            u.reg_write(UC_ARM_REG_R0, 0xFFFFFFFF); u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
        hk = uc.hook_add(UC_HOOK_CODE, mode_set, None, 0x0804D6B6, 0x0804D6B7)
        btn(uc, 11)
        uc.hook_del(hk)
        w = u32(uc, vw)
        tick(uc, 400); stub_rel(11); held(uc, 11, False); view(uc, T.CONT); out(uc)
        return req, w

    m, w = two_view(False)
    check("page closed: the stock asks for view 11's second view (mode 5)", m == [5], m)
    m, w = two_view(True)
    check("on the page: view 11's first view (mode 3), the view word kept", m == [3] and (w >> 16 & 0xFF) == 3, (m, hex(w)))
    check("let go after the hold: the page again", is_open(uc))
    uc.mem_write(vw, struct.pack("<I", w_keep)); uc.mem_write(T.CONT + 0x264, bytes([m_keep]))
    close = lambda: (held(uc, BIT_DUP, True), btn(uc, 24), held(uc, BIT_DUP, False), rel(uc, 24))
    close()

    # ---- the selected track's button on mode 2 (not Note or Sample): the press and release go on (the stock's: its main view)
    def trk_press(ms):
        open_page(uc)
        uc.mem_write(T.CONT + 0x264, bytes([2]))
        got = []

        def take(u, a, n, d):                             # the next press / release handler: noted, returns at once
            if a == PREV["prev_btn"]:
                u.mem_write(TM + 2, b""); u.mem_write(TM + 34, b"")    # as the editor notes a track press
            got.append(a); u.reg_write(UC_ARM_REG_R0, 0); u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
        hks = [uc.hook_add(UC_HOOK_CODE, take, None, PREV[k], PREV[k] + 1) for k in ("prev_btn", "prev_rel")]
        btn(uc, 0)
        hidden = b8(uc, SLOT) & 0x10 and b8(uc, TM + 2) == 0 and b8(uc, TM + 34) == 0
        tick(uc, ms); rel(uc, 0); view(uc, T.CONT); out(uc)
        for h in hks:
            uc.hook_del(h)
        return got, hidden

    got, hidden = trk_press(400)
    check("on mode 2, the selected track held: press and release go on, the editor forgets the press; let go: the page again",
          got == [PREV["prev_btn"], PREV["prev_rel"]] and hidden and is_open(uc), (got, hidden))
    got, hidden = trk_press(100)
    check("on mode 2, the selected track tapped: press and release go on, the page closes",
          got == [PREV["prev_btn"], PREV["prev_rel"]] and not is_open(uc))
    uc.mem_write(T.CONT + 0x264, bytes([m_keep]))

    # ---- Shift + hold Duplicate with the Track Parameter Editor open: the editor closes, the page opens
    uc.mem_write(TM, b""); uc.mem_write(TM + 35, b"")
    open_page(uc)
    check("the editor open: Shift + hold Duplicate hides it and opens the page",
          is_open(uc) and bytes(uc.mem_read(TM, 3)) == bytes(3) and b8(uc, TM + 35) == 0 and b8(uc, TM + 32) == 0xFF and b8(uc, TM + 34) == 0)
    close()
    check("Duplicate tapped: the page closes, the editor comes back", not is_open(uc) and bytes(uc.mem_read(TM, 2)) == b"")
    open_page(uc)
    uc.mem_write(T.CONT + 0x264, bytes([b8(uc, main0)]))
    btn(uc, 0); rel(uc, 0)
    check("from the editor, the selected track tapped: the page closes, the editor stays closed", not is_open(uc) and b8(uc, TM) == 0)
    uc.mem_write(T.CONT + 0x264, bytes([m_keep]))

    # ---- closed, Shift held: Duplicate green dim, full while down; all targets off: the stock's light
    held(uc, BIT_SHIFT, True)
    check("Shift held: Duplicate dim green", out(uc)[LED_DUP] == scl(g, 80))
    held(uc, BIT_DUP, True)
    check("Shift + Duplicate down: full green", out(uc)[LED_DUP] == g)
    held(uc, BIT_DUP, False)
    set_rec(uc, 0, only())
    check("all targets off: Duplicate left to the stock", out(uc)[LED_DUP] == 0)
    held(uc, BIT_SHIFT, False)
    p = fill(uc); before = steps(uc, p); tap(uc)
    check("all targets off: a tap changes nothing", steps(uc, p) == before)
    set_rec(uc, 0, only(), version=0)
    held(uc, BIT_SHIFT, True)
    check("a block of another version reads as the defaults", out(uc)[LED_DUP] == scl(g, 80))
    held(uc, BIT_SHIFT, False)

    # ---- each target (start 3, end 12: steps 4-13)
    rng = range(3, 13)

    def run(rec, n=1):
        set_rec(uc, 0, rec)
        p = fill(uc, start=3, end=12)
        b0 = steps(uc, p)
        for _ in range(n):
            tap(uc)
        a0 = steps(uc, p)
        return b0, a0, all(a0[s] == b0[s] for s in range(32) if s not in rng)

    def diff(b0, a0, keep):
        ch = [s for s in range(32) if a0[s] != b0[s]]
        return ch, all(a0[s][i] == b0[s][i] for s in range(32) for i in range(8) if i not in keep)

    b0, a0, out_ok = run(only(VEL, vel=0x2A))
    ch, other = diff(b0, a0, (3,))
    check("Velocity, Some: 5 of the 10 steps change, only inside start-end", len(ch) == 5 and out_ok and other, ch)
    check("Velocity, Up to 24: each change 1-24, 1-127", all(1 <= abs(a0[s][3] - b0[s][3]) <= 24 for s in ch))
    b0, a0, out_ok = run(only(VEL, vel=0x00 | 1 << 4))
    ch, other = diff(b0, a0, (3,))
    check("Velocity, All, Any, Down: every step lower", len(ch) == 10 and all(a0[s][3] < b0[s][3] for s in ch) and other)
    b0, a0, out_ok = run(only(VEL, vel=0x03 | 0x03 << 2 | 0x01 << 4))
    ch, other = diff(b0, a0, (3,))
    check("Velocity, A little, Up to 8, Down: 3 steps lower by 1-8", len(ch) == 3 and all(1 <= b0[s][3] - a0[s][3] <= 8 for s in ch) and other)

    notes = []
    for _ in range(3):
        b0, a0, out_ok = run(only(NOTE, note=0x00 | 0x00 << 2 | 0x02 << 4))   # All, Any, Both
        ch, other = diff(b0, a0, (0,))
        notes += [a0[s][0] for s in ch]
    check("Note, Any, Both: the whole keyboard (25-108), low and high", len(notes) == 30 and all(25 <= n <= 108 for n in notes)
          and min(notes) < 40 and max(notes) > 84, sorted(notes))
    b0, a0, out_ok = run(only(NOTE, note=0x00 | 0x01 << 2 | 0x00 << 4))   # 12 up
    ch, other = diff(b0, a0, (0,))
    check("Note, 12 semitones up: 0x31-0x3C", len(ch) == 10 and all(0x31 <= a0[s][0] <= 0x3C for s in ch) and other and out_ok)
    b0, a0, out_ok = run(only(NOTE, note=0x00 | 0x03 << 2 | 0x01 << 4))   # 3 down
    ch, other = diff(b0, a0, (0,))
    check("Note, 3 semitones down: 0x2D-0x2F", len(ch) == 10 and all(0x2D <= a0[s][0] <= 0x2F for s in ch) and other)

    ts = b8(uc, ptr(uc, u32(uc, 0x200470D4 + 0x60), 0)) & 63

    def run_flip(rec, pink, n=1):
        set_rec(uc, 0, rec)
        p = fill(uc, start=3, end=12)
        for s in pink:
            uc.mem_write(p + 8 * s + 5, bytes([ts]))
        b0 = steps(uc, p)
        for _ in range(n):
            tap(uc)
        a0 = steps(uc, p)
        ch, other = diff(b0, a0, (5,))
        return b0, a0, ch, other and all(a0[s] == b0[s] for s in range(32) if s not in rng)

    b0, a0, ch, ok = run_flip(only(SAMPLE, sample=0x00 | 1 << 2 | 0 << 4), pink=(3, 5, 7, 20))
    check("Sample flip, Pink only, Growing: only the pink steps inside change, to the sample before or after",
          ch == [3, 5, 7] and ok and all(a0[s][5] in ((ts - 1) % 64, (ts + 1) % 64) for s in ch), (ts, ch, [a0[s][5] for s in ch]))
    b0, a0, ch, ok = run_flip(only(SAMPLE, sample=0x00 | 1 << 2 | 0 << 4), pink=(3, 5, 7, 20), n=12)
    g = [min((a0[s][5] - ts) % 64, (ts - a0[s][5]) % 64) for s in (3, 5, 7)]
    check("Sample flip, Growing, 12 mutates: each flip within 12 of the track's sample, the same parity",
          ok and all(d <= 12 and d % 2 == 0 for d in g), (ts, g))
    b0, a0, ch, ok = run_flip(only(SAMPLE, sample=0x00 | 1 << 2 | 0 << 4), pink=(), n=2)
    check("Sample flip, Pink only, no pink steps: nothing changes", ch == [] and ok)
    w = []
    for _ in range(3):
        b0, a0, ch, ok = run_flip(only(SAMPLE, sample=0x00 | 3 << 2 | 1 << 4), pink=())
        w += [a0[s][5] for s in ch]
    check("Sample flip, All steps, within 4: blue steps get flips, all inside the track's sample +- 4, many times",
          len(w) == 30 and ok and all(max(0, ts - 4) <= x <= min(63, ts + 4) for x in w), (ts, sorted(set(w))))
    w = []
    for _ in range(3):
        b0, a0, ch, ok = run_flip(only(SAMPLE, sample=0x00 | 2 << 2 | 1 << 4), pink=())
        w += [a0[s][5] for s in ch]
    check("Sample flip, All steps, within 8: all inside the track's sample +- 8",
          len(w) == 30 and ok and all(max(0, ts - 8) <= x <= min(63, ts + 8) for x in w), (ts, sorted(set(w))))
    b0, a0, ch, ok = run_flip(only(SAMPLE, sample=0x00 | 0 << 2 | 1 << 4), pink=(), n=4)
    check("Sample flip, Any, All steps: 0-63", len(ch) == 10 and all(a0[s][5] < 64 for s in ch) and ok)

    b0, a0, out_ok = run(only(GATE, gate=0x00 | 0x02 << 2 | 0x00 << 4))
    ch, other = diff(b0, a0, (1,))
    check("Gate, Up to 1 step, Longer: 7-12", len(ch) == 10 and all(7 <= a0[s][1] <= 12 for s in ch) and other and out_ok)
    b0, a0, out_ok = run(only(GATE, gate=0x00 | 0x03 << 2 | 0x01 << 4))
    ch, other = diff(b0, a0, (1,))
    check("Gate, half a step, Shorter: 3-5", all(3 <= a0[s][1] <= 5 for s in ch) and len(ch) == 10 and other)

    bits = lambda m: bin(m).count("1")
    seen = set()
    for _ in range(4):
        b0, a0, out_ok = run(only(MICRO, micro=0x00 | 0x03 << 2 | 1 << 4))
        ch, other = diff(b0, a0, (2,))
        seen |= {a0[s][2] for s in rng}
    check("Microsteps, 1 or 2 hits, On the beat: 1 hit or microsteps 1 and 4, by chance; the gate kept",
          seen == {0x01, 0x09} and other and out_ok, sorted(seen))
    seen = set()
    for _ in range(4):
        b0, a0, out_ok = run(only(MICRO, micro=0x00 | 0x03 << 2))
        seen |= {a0[s][2] for s in rng}
    check("Microsteps, 1 or 2 hits, Any microstep: 1 or 2 hits on random microsteps",
          all(1 <= bits(x) <= 2 and x < 64 for x in seen) and len(seen) >= 6 and out_ok, sorted(seen))
    seen = set()
    for _ in range(4):
        b0, a0, out_ok = run(only(MICRO, micro=0x00), n=2)
        seen |= {a0[s][2] for s in rng}
    check("Microsteps, up to 6, Any microstep: 1-6 hits on random microsteps, the gate kept",
          all(1 <= bits(x) <= 6 and x < 64 for x in seen) and all(a0[s][1] == 6 for s in rng)
          and {bits(x) for x in seen} >= {1, 2, 3, 4} and out_ok, sorted(seen))
    seen = set()
    for _ in range(4):
        b0, a0, out_ok = run(only(MICRO, micro=0x00 | 1 << 4), n=2)
        seen |= {a0[s][2] for s in rng}
    check("Microsteps, up to 6, On the beat: only the even rolls", seen <= {0x01, 0x09, 0x15, 0x1B, 0x1F, 0x3F} and len(seen) >= 4, sorted(seen))

    b0, a0, out_ok = run(only(PROB, prob=0x00 | 0x02 << 2))
    ch, other = diff(b0, a0, (4,))
    check("Probability, down to 50 %: 3-7", all(3 <= a0[s][4] <= 7 for s in rng) and other and out_ok)

    def setting(rec, start=0, end=15):
        set_rec(uc, 0, rec)
        p = fill(uc, start=start, end=end)
        st = steps(uc, p)
        tap(uc)
        return bytes(uc.mem_read(p + 0x100, 4)), st == steps(uc, p)
    s4, same = setting(only(SPEED, speed=0x02))
    check("Pattern speed, 1 rate away: 3 -> 2 or 4, the steps kept", s4[2] in (2, 4) and s4[3] == 0 and same)
    s4, _ = setting(only(SPEED, speed=0x00))
    check("Pattern speed, any: 0-7, not 3", s4[2] in range(8) and s4[2] != 3)
    s4, _ = setting(only(MODE, mode=0b1010))
    check("Play mode, Reverse and Random on: one of them", s4[3] in (1, 3) and s4[2] == 3)
    s4, _ = setting(only(MODE, mode=0b0001))
    check("Play mode, Forward only: Forward", s4[3] == 0)
    s4, same = setting(only(LEN, len=0x02 | 0x00 << 2), start=3, end=12)
    check("Pattern length, up to 4, End: the end 8-16, the start kept, the steps kept",
          s4[1] == 3 and 8 <= s4[0] <= 16 and s4[0] != 12 and same, list(s4))
    s4, _ = setting(only(LEN, len=0x02 | 0x01 << 2), start=3, end=12)
    check("Pattern length, Start: the start 0-7, the end kept", s4[0] == 12 and s4[1] <= 7 and s4[1] != 3, list(s4))
    s4, _ = setting(only(LEN, len=0x00 | 0x02 << 2), start=3, end=12)
    check("Pattern length, Any, Both: start <= end, inside 1-32", s4[1] <= s4[0] <= 31 and (s4[0], s4[1]) != (12, 3), list(s4))

    p = fill(uc, start=3, end=12)
    set_rec(uc, 0, only(MOVE, move=0x00 | 0x03 << 2))
    b0 = steps(uc, p); tap(uc); a0 = steps(uc, p)
    check("Step movement, up to 2: the steps stay inside, the rest unchanged",
          sorted(a0[3:13]) == sorted(b0[3:13]) and a0 != b0 and all(a0[s] == b0[s] for s in range(32) if s not in rng))

    sel(uc, 2)
    set_rec(uc, 2, only(VEL))
    p2 = fill(uc, t=2)
    b2 = steps(uc, p2)
    p0 = pat(uc, 0); b0 = steps(uc, p0)
    tap(uc, t=2)
    check("track 3's settings mutate track 3 only", steps(uc, p2) != b2 and steps(uc, p0) == b0)

    # ---- Clear + a target pad: that target back to the stock's default, from the start to the end
    sel(uc, 0)
    set_rec(uc, 0, only(MOVE, VEL))
    open_page(uc)
    p = fill(uc, start=3, end=12, empty=(8,))
    for s in range(32):
        uc.mem_write(p + 8 * s, bytes([0x3A, 9, 0x15, 10 + s, 3, ts]) if s != 8 else bytes(8))
    b0 = steps(uc, p)
    sm = bytes(uc.mem_read(blk(uc), 100))
    held(uc, 23, True)
    o = out(uc)
    cue = scl(u32(uc, T.COLOURS + 4 * CLR_CUE), full)
    check("Clear held: the target pads dim red, Step movement dark",
          all(o[T_PAD[i]] == (0 if i == MOVE else cue) for i in range(10)))

    def clr(i):
        tpad(uc, T_PAD[i])
        return steps(uc, p)
    inside = [s for s in rng if s != 8]
    a0 = clr(VEL)
    check("Clear + Velocity: velocity 96 inside, the rest kept",
          all(a0[s][3] == 0x60 for s in inside) and all(a0[s] == b0[s] for s in range(32) if s not in inside)
          and all(a0[s][:3] + a0[s][4:] == b0[s][:3] + b0[s][4:] for s in inside))
    check("an empty step stays empty", a0[8] == bytes(8))
    o = out(uc)
    red = scl(u32(uc, T.COLOURS + 4 * CLR_RED), full)
    tick(uc, 70); o2 = out(uc)
    tick(uc, 400); o3 = out(uc)
    check("the pad flashes red, then the dim red again", o[T_PAD[VEL]] == red and o2[T_PAD[VEL]] == 0 and o3[T_PAD[VEL]] == cue)
    a0 = clr(MICRO)
    check("Clear + Microsteps: the first hit only", all(a0[s][2] == 0x01 for s in inside) and a0[20][2] == 0x15)
    a0 = clr(SAMPLE)
    check("Clear + Sample flip: no flips inside", all(a0[s][5] == 0xFF for s in inside) and a0[20][5] == ts)
    a0 = clr(NOTE)
    check("Clear + Note: the sample's pitch", all(a0[s][0] == 0 for s in inside) and a0[20][0] == 0x3A)
    a0 = clr(GATE)
    check("Clear + Gate: 1 step", all(a0[s][1] == 6 for s in inside) and a0[20][1] == 9)
    a0 = clr(PROB)
    check("Clear + Probability: 100 %", all(a0[s][4] == 7 for s in inside) and a0[20][4] == 3)
    before = steps(uc, p)
    a0 = clr(MOVE); o = out(uc)
    check("Clear + Step movement: nothing, no flash", a0 == before and o[T_PAD[MOVE]] == 0)
    uc.mem_write(p + 0x100, bytes([12, 3, 6, 2]))
    clr(LEN); clr(SPEED); clr(MODE)
    check("Clear + Pattern length, speed, play mode: 1-16, 1/16, Forward", bytes(uc.mem_read(p + 0x100, 4)) == bytes([15, 0, 3, 0]))
    tpad(uc, 8 * 3 + COL0)
    check("Clear + a setting pad: nothing; the settings and toggles kept", bytes(uc.mem_read(blk(uc), 100)) == sm)
    held(uc, 23, False)
    check("the page stays open", is_open(uc))

    print("ALL PASS" if not ET.FAILS else f"{len(ET.FAILS)} FAILED")


if __name__ == "__main__":
    main()
