"""Unicorn test of gfxmix on a build with it: Down on the Mixer's pans = the sends page, Up back; the knobs set the sends (Clear +
knob = full) in the project's block; the knob and arrow lights; the sends written to core 0 once the DSP is READY.

    python tests/emu_gfxmix.py STOCK.bin BUILT.bin RAM.bin
"""
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("RH_BUILD", Path(sys.argv[2]).parent.name if len(sys.argv) > 2 else "a0166")
import emu_tmenu as ET  # noqa: E402  (ourram's layout from the build's manifest)
from emu_tmenu import C, T, call, check, ptr, u32  # noqa: E402
from emu_playfix import STACK  # noqa: E402
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_R5, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP  # noqa: E402

R = ET.MAN["report"]["gfxmix"]
CUES2 = R.get("cues", {}).get("version") == 2          # the held cue scrub: audition on pad 24, pads 17-32 the bar and the cues
LB = {k: int(v, 16) for k, v in R["labels"].items()}
K1_SLOW = R.get("cues", {}).get("k1_slow")                  # K1 one step for each 2 clicks in the scrub
SCR_FLAG = int(R["scrub_flag"], 16)
PREV = {k: int(v, 16) for k, v in R["prev"].items()}
SLOT, CUT = int(R["slot"], 16), int(R["cut"], 16)
DRUP0 = int(ET.MAN["report"]["cthresh"]["labels"]["c_drup0"], 16)
RRT = int(ET.MAN["report"]["rhrec"]["labels"]["c_rrt"], 16)
MIX, CONT = 0x2004E090, 0x20048B9C
ID_DOWN, ID_UP, BIT_CLEAR = 19, 20, 23
LED_DOWN, LED_UP, LED_KNOB0 = 51, 52, 60
GX_RGB, LVL_ZERO, FULL, WR16 = 0xFFAF2F, 24, 127, 0x08031200
OUT, FRAME = 0x2004FA00, 0x2004FD00
ARG5 = STACK + 0xF0000                                # [sp] at a call: a 5th argument


def b8(uc, a): return uc.mem_read(a, 1)[0]
def tail(uc): call(uc, RRT); return uc.reg_read(UC_ARM_REG_R0)
def blk(uc): return tail(uc) + R["blk_off"]
def view(uc, v): uc.mem_write(C.CTRL + 0x7C, struct.pack("<I", v))
def page_p(uc): return ptr(uc, MIX + 0x68, 0)            # the levels / pans store, inside the view: 0 the levels, 1 the pans
def mode_p(uc): return ptr(uc, u32(uc, MIX + 0x1CC), 0)
def fxpage_p(uc): return ptr(uc, u32(uc, MIX + 0x154), 0)  # Grid FX's effect page - 2, 0xFF = none
def btn(uc, i): call(uc, C.BTN_ENTRY, C.CTRL, i)
def pad(uc, p, vel=100): call(uc, T.PP_ENTRY, C.CTRL, p, vel)
def knob(uc, k, d):
    """A knob turn; in the scrub with a slow K1, d is K1's steps (2 clicks each)"""
    if k == 0 and K1_SLOW and uc.mem_read(SCR_FLAG, 1)[0]:
        d *= 2
    call(uc, T.KN_ENTRY, C.CTRL, k, d & 0xFFFFFFFF)
def knob_raw(uc, k, d): call(uc, T.KN_ENTRY, C.CTRL, k, d & 0xFFFFFFFF)
V3 = R.get("cues", {}).get("v3")
ONE = R.get("cues", {}).get("one")                       # A324: one timing, the pads and K4 (pads 18-24) set it                         # Shift + Play held 0.5 s latches; no hold mode
def scrub_on(uc):
    """Play pressed with Shift on: the scrub (A322: held 0.5 s, then a frame latches it)"""
    if V3:
        out(uc)                                          # the unit's frames run before any press
    btn(uc, 17)
    if V3:
        uc.mem_write(HAL_TICK, struct.pack("<I", u32(uc, HAL_TICK) + 600)); out(uc)
def scrub_off(uc):
    """Play let go: the scrub ends (A322: Play's release is the latch's, a Shift tap ends it)"""
    call(uc, C.BTN_RELEASE, C.CTRL, 17)
    if V3:
        btn(uc, 27); call(uc, C.BTN_RELEASE, C.CTRL, 27)
def scl(rgb, lvl): return sum((((rgb >> s) & 0xFF) * (lvl + 1) >> 8) << s for s in (0, 8, 16))
def sends(uc): return list(uc.mem_read(blk(uc) + 4, 8))


def held(uc, bit, on):
    v = u32(uc, C.CTRL + 0xA0)
    uc.mem_write(C.CTRL + 0xA0, struct.pack("<I", v | 1 << bit if on else v & ~(1 << bit)))


def out(uc, up=0x111111, knobs=None):
    uc.mem_write(FRAME, bytes(140))
    uc.mem_write(OUT, bytes(69 * 4))
    uc.mem_write(OUT + 4 * LED_UP, struct.pack("<I", up))
    if knobs:
        uc.mem_write(OUT + 4 * LED_KNOB0, struct.pack("<8I", *knobs))
    call(uc, LB["c_gx_out"], C.CTRL, OUT, FRAME)
    return struct.unpack("<69I", uc.mem_read(OUT, 69 * 4))


GETTER, GSET, SM_SELTRK = 0x08046410, 0x08038A08, 0x0805800E
ON_CONT, NOTE_WRAP, RELOAD = 0x0804077C, 0x08046780, 0x08048932
SPEED_TAB, HAL_TICK = 0x08068D9C, 0x20006F3C
MGR = 0x200438AC
TBL, PLAYERS, PL_SZ, PAT_SZ, ENGINE = MGR + 0x1D8, 0x200470D4, 0x190, 0xA28, 0x2003D2FC
O_STEPFX, O_ON, O_PEND, O_SET, O_ASK, O_GDOWN, O_DUR = 12, 16, 20, 23, 26, 28, 36
O_PKOK, O_SNAPV = 101, 104
LANE = 0x128 + 0xC0 * 8
K1_LO, K1_HI = 4, 124
WHITE = 0xFFFFFF


def knob_k(uc, t, k): call(uc, GETTER, 0x10 + t, 6 + k); return uc.reg_read(UC_ARM_REG_R0) & 0x7F
def send_knob(k, v): return v if k else K1_LO + (v * (K1_HI - K1_LO) + 63) // FULL
def knob_send(k, v): return v if k else 0 if v <= K1_LO else FULL if v >= K1_HI else ((v - K1_LO) * FULL + 60) // (K1_HI - K1_LO)
def sm_track(uc): call(uc, SM_SELTRK, CONT); return uc.reg_read(UC_ARM_REG_R0)
def sel_p(uc): return ptr(uc, u32(uc, CONT + 0x25C), 0)
def u16(uc, a): return struct.unpack("<H", uc.mem_read(a, 2))[0]
PK_OFF, PS_OFF = R["pk_off"], R["ps_off"]


def pk_encode(uc, t, model):
    """model: (pattern, step) -> slots | flags; the tail's two blocks as gfxmix writes them"""
    codes, sets = [0] * 256, []
    for (n, st), fx in model.items():
        m, fl = fx & 0xFFFF, (1 if fx >> 16 & 1 else 0) | (2 if fx >> 17 & 1 else 0)
        if not fl and not m & (m - 1):
            c = m.bit_length()
        else:
            e = (m & 0xFF, m >> 8, fl)
            if e not in sets:
                sets.append(e)
            c = 17 + sets.index(e)
        codes[n * 32 + st] = c
    q = bytearray(196)
    q[4:] = sum(c << 6 * i for i, c in enumerate(codes)).to_bytes(192, "little")
    q[0:2], q[3] = b"GQ", t
    q[2] = (sum(q[3:]) ^ 0x5C) & 0xFF
    sb = bytearray(145)
    sb[0:2] = b"GS"
    for k, e in enumerate(sets):
        sb[4 + 3 * k:7 + 3 * k] = bytes(e)
    sb[2] = (sum(sb[3:]) ^ 0x5C) & 0xFF
    uc.mem_write(tail(uc) + PK_OFF, bytes(q))
    uc.mem_write(tail(uc) + PS_OFF, bytes(sb))
    uc.mem_write(SLOT + O_PKOK, b"\x03")                  # as the next LED frame finds them


def pk_read(uc, n, st):
    """a step's slots and flags in the tail (0 when the blocks are not ours)"""
    q, sb = bytes(uc.mem_read(tail(uc) + PK_OFF, 196)), bytes(uc.mem_read(tail(uc) + PS_OFF, 145))
    if q[:2] != b"GQ" or q[2] != (sum(q[3:]) ^ 0x5C) & 0xFF:
        return 0
    c = int.from_bytes(q[4:], "little") >> 6 * (n * 32 + st) & 63
    if c < 17:
        return 1 << c - 1 if c else 0
    e = sb[4 + 3 * (c - 17):7 + 3 * (c - 17)]
    return e[0] | e[1] << 8 | (1 << 16 if e[2] & 1 else 0) | (1 << 17 if e[2] & 2 else 0)


def pk_owner(uc): q = bytes(uc.mem_read(tail(uc) + PK_OFF, 4)); return q[3] if q[:2] == b"GQ" else None
def smp(uc, t): return b8(uc, ptr(uc, u32(uc, PLAYERS + PL_SZ * t + 0x60), 0))
def palc(uc, c): return u32(uc, 0x20003974 + 4 * c)
def unpad(uc, p): call(uc, T.PR_ENTRY, C.CTRL, p)


def fx_track(uc, got, takes):
    """the FX track: Sample mode's pad 8 (Clear + pad 8 clears a track); its steps' Grid FX pads; its view; its knobs the sends"""
    calls = []

    def note(kind, pushed=0):                             # pushed: the stock's head, run in the stub, taken back off the stack
        def f(u, a, n, d):
            calls.append((kind, u.reg_read(UC_ARM_REG_R1), u.reg_read(UC_ARM_REG_R2)))
            u.reg_write(UC_ARM_REG_SP, u.reg_read(UC_ARM_REG_SP) + pushed)
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
        return f
    hooks = {kind: uc.hook_add(UC_HOOK_CODE, note(kind, pushed), None, at, at + 1)
             for kind, at, pushed in (("gset", GSET, 0), ("on", ON_CONT, 32), ("s4", int(R["prev_s4"], 16), 0),
                                      ("tknob", PREV["prev_tknob"], 0))}
    gsets = lambda: [(c[1], c[2]) for c in calls if c[0] == "gset"]   # noqa: E731
    view(uc, CONT); uc.mem_write(CONT + 0x264, b"\x09")
    uc.mem_write(sel_p(uc), b"\x02")
    t = sm_track(uc)
    check("Sample mode's track follows the selected track", t == 2, t)
    rec = u32(uc, ENGINE + 0x84 + 4 * t)
    pats = u32(uc, rec + 4)
    uc.mem_write(pats + 8 * 3 + 3, b"\x60"); uc.mem_write(pats + 8 * 3 + 5, b"\x03")   # a step with a flip, automation in pattern 6
    uc.mem_write(pats + 5 * PAT_SZ + 0x128 + 40, b"\x20")
    full = 141 if u32(uc, ptr(uc, u32(uc, C.CTRL + 0x88), 2)) >> 10 & 1 else 255
    send0 = sends(uc)
    before = [knob_k(uc, t, k) for k in range(8)]
    own = smp(uc, t)
    got.clear(); pad(uc, 7)
    b = bytes(uc.mem_read(blk(uc), 24))
    check("pad 8 on a track with steps and automation: the FX track (block v3), the stock not called", b[3] == 3 and b[12] == t
          and PREV["prev_pad"] not in got, b.hex())
    check("its steps, flips and automation kept", b8(uc, pats + 8 * 3 + 3) == 0x60 and b8(uc, pats + 8 * 3 + 5) == 3
          and b8(uc, pats + 5 * PAT_SZ + 0x128 + 40) == 0x20)
    check("its K1-K8 and its sample kept in the block; its sample now its pad selected last (pad 1); its effects empty",
          list(b[13:21]) == before and b[21] == own and smp(uc, t) == 0 and pk_owner(uc) == t and pk_read(uc, 0, 3) == 0,
          (list(b[13:21]), before, b[21], own, smp(uc, t), pk_owner(uc)))
    now = [knob_k(uc, t, k) for k in range(8)]
    check("its K1-K8 = the sends (K1 in 4..124)", now == [send_knob(k, v) for k, v in enumerate(send0)], (now, send0))
    got.clear(); unpad(uc, 7)
    check("pad 8's release kept from the stock", PREV["prev_padrel"] not in got)
    o = out(uc)
    check("pad 8 lit in GX_RGB on the FX track", o[7] == scl(GX_RGB, full), hex(o[7]))
    held(uc, BIT_CLEAR, True); o = out(uc)
    check("Clear held: pad 8 dim red (the stock's cue)", o[7] == scl(palc(uc, 0x54), full), hex(o[7]))
    pk_encode(uc, t, {(0, 3): 1 << 4})
    got.clear(); pad(uc, 7)
    clean = all(b8(uc, pats + n * PAT_SZ + 8 * s + 3) == 0 for n in range(8) for s in range(32)) and \
        all(x == 0xFF for n in range(8) for x in uc.mem_read(pats + n * PAT_SZ + 0x128, 12 * 0xC0))
    check("Clear + pad 8: the track's 8 patterns cleared (hits, automation, effects), still the FX track", clean
          and pk_read(uc, 0, 3) == 0 and b8(uc, blk(uc) + 12) == t and PREV["prev_pad"] not in got)
    unpad(uc, 7); held(uc, BIT_CLEAR, False)
    o = out(uc)
    check("cleared: pad 8 flashes red", o[7] == scl(palc(uc, 0x55), full), hex(o[7]))
    now = u32(uc, HAL_TICK)
    uc.mem_write(HAL_TICK, struct.pack("<I", now + 70)); o = out(uc)
    check("64 ms on: dark", o[7] == 0, hex(o[7]))
    uc.mem_write(HAL_TICK, struct.pack("<I", now + 400)); o = out(uc)
    check("after three flashes: pad 8 lit in GX_RGB again", o[7] == scl(GX_RGB, full), hex(o[7]))
    uc.mem_write(sel_p(uc), b"\x05"); pad(uc, 7); unpad(uc, 7)
    check("another track: pad 8 does nothing (one FX track)", uc.mem_read(blk(uc) + 12, 1)[0] == t)
    o = out(uc)
    check("another track: pad 8 dark", o[7] == 0, hex(o[7]))
    uc.mem_write(sel_p(uc), bytes([t]))
    mark = scl(GX_RGB, 104 * full >> 8)
    o = out(uc)
    check("the FX track selected: its button and the Mixer button bright amber",
          o[32 + t] == scl(GX_RGB, full) and o[46] == scl(GX_RGB, full), (hex(o[32 + t]), hex(o[46])))
    check("the FX track selected: Note and Velocity dark", o[41] == 0 and o[42] == 0, (hex(o[41]), hex(o[42])))
    for i in (9, 10):
        got.clear(); btn(uc, i)
        check(f"the FX track selected: button {i} (Note / Velocity) does nothing", PREV["prev_btn"] not in got)
    uc.mem_write(CONT + 0x264, b"\x01"); out(uc)
    check("the FX track in its Note view: back to its sample view", b8(uc, CONT + 0x264) == 0, b8(uc, CONT + 0x264))
    uc.mem_write(CONT + 0x264, b"\x09")
    uc.mem_write(sel_p(uc), b"\x05"); o = out(uc)
    check("another track selected: the FX track's button and the Mixer button dim amber", o[32 + t] == mark and o[32 + 5] == 0
          and o[46] == mark, (hex(o[32 + t]), hex(o[46])))
    got.clear(); btn(uc, 10)
    check("another track: Velocity is the stock's", PREV["prev_btn"] in got)
    tm = int(ET.MAN["report"]["tmenu"]["slot"], 16)
    uc.mem_write(tm + T.O_OPEN, b"\x01"); out(uc)
    check("the editor on another track: left open", b8(uc, tm + T.O_OPEN) == 1)
    uc.mem_write(sel_p(uc), bytes([t])); out(uc)
    check("the editor on the FX track: closed", b8(uc, tm + T.O_OPEN) == 0)
    ms = int(ET.MAN["report"]["mutset"]["slot"], 16)
    keep = bytes(uc.mem_read(ms, 1)); uc.mem_write(ms, bytes([keep[0] | 1])); o = out(uc)
    check("Pattern Mutate's settings open: the track buttons are its", o[32 + t] == 0, hex(o[32 + t]))
    uc.mem_write(ms, keep)
    view(uc, MIX); o = out(uc); view(uc, CONT)
    check("on the Mixer: the Mixer button the stock's", o[46] == 0, hex(o[46]))
    uc.mem_write(CONT + 0x264, b"\x09")

    old_tbl = bytes(uc.mem_read(TBL, 7 * 16))
    uc.mem_write(TBL, bytes([0xFF]) * (7 * 16))
    uc.mem_write(TBL + 7 * 5, bytes([1, 0x33, 0, 0, 0, 0, 0]))    # slot 5: Reverser, macro 0x33
    uc.mem_write(TBL + 7 * 6, bytes([1, 0x44, 0, 0, 0, 0, 0]))    # slot 6: Reverser too
    uc.mem_write(TBL + 7 * 9, bytes([2, 0x55, 0, 0, 0, 0, 0]))    # slot 9: Gater
    src = u32(uc, MGR + 0xC)
    old_src = bytes(uc.mem_read(src, 7 * 16))
    uc.mem_write(src, bytes(uc.mem_read(TBL, 7 * 16)))
    pl = PLAYERS + PL_SZ * t
    pidx = uc.mem_read(ptr(uc, u32(uc, rec + 0x28), 0), 1)[0] & 7
    pat = pats + PAT_SZ * pidx
    check("the players' and the recorder's patterns are one", u32(uc, pl + 0x50) == pats, (hex(u32(uc, pl + 0x50)), hex(pats)))
    keep_pat = bytes(uc.mem_read(pat, PAT_SZ))

    spd = b8(uc, ptr(uc, u32(uc, pl + 0x10), 1)) & 7
    tk = u32(uc, SPEED_TAB + 4 * spd)                     # the ticks of a step (gate 6)
    s1 = []
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: (s1.append(u32(u, u.reg_read(UC_ARM_REG_SP))),
                                                  u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))),
                None, int(R["prev_s1"], 16), int(R["prev_s1"], 16) + 1)

    def tick(n=1):
        for _ in range(n):
            uc.mem_write(ARG5, struct.pack("<I", 1))
            call(uc, LB["c_gx_tick_e"], pl, pidx, 0, 6)

    model = {}

    def play(step, fx, flip=0xFF, gate=6):
        model[(pidx, step)] = fx
        pk_encode(uc, t, model)
        uc.mem_write(pat + 8 * step + 3, b"\x60")
        uc.mem_write(pat + 8 * step + 1, bytes([gate]))
        uc.mem_write(pat + 8 * step + 5, bytes([flip]))
        calls.clear(); call(uc, LB["c_gx_s4_e"], pl, pidx, step)
        call(uc, LB["c_gx_on_e"], 0x10 + t, 60, 100)

    def frame():
        calls.clear(); out(uc); return gsets()

    def end():
        out(uc); tick(8 * tk); out(uc)
    tick()
    check("the players' tick: on to the stock's slot 1, its 5th argument kept", s1 == [1], s1)
    play(3, 1 << 5 | 1 << 9)
    check("a step starts: its effects read, its gate in ticks, the stock's slot 4 called", u32(uc, SLOT + O_STEPFX) == (1 << 5 | 1 << 9)
          and u16(uc, SLOT + O_DUR) == tk and "s4" in [c[0] for c in calls], (u16(uc, SLOT + O_DUR), tk))
    check("the FX track's note-on: kept from the DSP, pending", "on" not in [c[0] for c in calls] and b8(uc, SLOT + O_PEND) == 1
          and uc.reg_read(UC_ARM_REG_R0) == 0, calls)
    check("the next LED frame: both of the step's slots on, the macros first",
          frame() == [(0xAD, 0x33), (0xAC, 1), (0xAF, 0x55), (0xAE, 1)], gsets())
    calls.clear(); call(uc, LB["c_gx_on_e"], 0x10 + (t + 1) % 8, 60, 100)
    check("another track's note-on: on to the stock", [c[0] for c in calls] == ["on"], calls)
    tick(tk - 1)
    check("its gate not over: still on", frame() == [], gsets())
    tick()
    check("its gate over: both off", sorted(frame()) == [(0xAC, 0), (0xAE, 0)] and u16(uc, SLOT + O_ON) == 0, gsets())

    play(4, 1 << 5, gate=24); frame(); tick(tk)
    play(5, 1 << 9)
    check("a long gate and a step inside it, another type: both play", frame() == [(0xAF, 0x55), (0xAE, 1)]
          and u16(uc, SLOT + O_ON) == 1 << 5 | 1 << 9, gsets())
    tick(tk)
    check("the short gate over: only its type off", frame() == [(0xAE, 0)], gsets())
    tick(2 * tk)
    check("the long gate over: its type off", frame() == [(0xAC, 0)], gsets())

    play(6, 1 << 5, gate=18); frame(); tick(tk)
    play(7, 1 << 6)
    check("the same type inside a gate: the new slot takes over, no restart", frame() == [(0xAD, 0x44)], gsets())
    tick(tk)
    check("its gate over, the first still on: the first slot's settings back, no restart", frame() == [(0xAD, 0x33)], gsets())
    tick(tk)
    check("then the first gate over: off", frame() == [(0xAC, 0)], gsets())
    play(8, 1 << 5); frame(); tick(tk)
    play(9, 1 << 6)
    check("the same type right after a gate (no overlap): it starts again", frame() == [(0xAC, 0), (0xAD, 0x44), (0xAC, 1)], gsets())
    end()
    play(8, 1 << 5); frame(); tick(tk - 1)
    play(9, 1 << 5)
    check("the same pad, its gate one tick from its end as the next step starts: it starts again",
          frame() == [(0xAC, 0), (0xAD, 0x33), (0xAC, 1)], gsets())
    end()
    play(8, 1 << 5, gate=12); frame(); tick(tk - 1)
    play(9, 1 << 5)
    check("a gate on into the next step: it plays on", frame() == [], gsets())
    end()
    for ticks in (tk - 1, tk):
        play(8, 1 << 5); frame(); tick(ticks)
        play(9, 1 << 5)
        check(f"a gate of exactly one step, the next step after {ticks} of {tk} ticks: it starts again",
              frame() == [(0xAC, 0), (0xAD, 0x33), (0xAC, 1)], gsets())
        end()
    if 'retrigger' in ET.MAN['report']['gfxsplit']:
        requests=[];request=int(ET.MAN['report']['gfxsplit']['retrigger'],16)
        def reset_write(u,a,n,d):
            if u.reg_read(UC_ARM_REG_R2)==request:requests.append(u.reg_read(UC_ARM_REG_R1))
        hook=uc.hook_add(UC_HOOK_CODE,reset_write,None,WR16,WR16+1)
        uc.mem_write(TBL+7*4,bytes([0,0,127,0,0,0,0]))
        for gate,expected in ((6,True),(7,False)):
            play(8,1<<4,gate=gate);frame();tick(tk-1);requests.clear()
            play(9,1<<4);frame()
            check(f'Beat Repeat gate {gate}: audio-boundary recapture request only without overlap',bool(requests)==expected,requests)
            end()
        uc.hook_del(hook)
        play(8, 1 << 5, gate=7); frame(); tick(ticks)
        play(9, 1 << 5)
        check(f"a gate one tick past the next step's start, after {ticks} ticks: it plays through", frame() == [], gsets())
        end()
    play(8, 1 << 5, gate=24); frame()
    for st in (9, 10, 11):
        tick(tk); call(uc, LB["c_gx_s4_e"], pl, pidx, st)
    tick(tk)
    play(12, 1 << 5)
    check("a gate of 4 steps, the pad again 4 steps on: it starts again", frame() == [(0xAC, 0), (0xAD, 0x33), (0xAC, 1)], gsets())
    end()
    play(8, 1 << 5, gate=30); frame()
    for st in (9, 10, 11):
        tick(tk); call(uc, LB["c_gx_s4_e"], pl, pidx, st)
    tick(tk)
    play(12, 1 << 5)
    check("a gate of 5 steps, the pad again 4 steps on: it plays through", frame() == [], gsets())
    end()
    play(10, 1 << 5, gate=3); frame(); tick(tk // 2); frame()
    play(11, 1 << 5)
    check("after a gap: it starts again", frame() == [(0xAD, 0x33), (0xAC, 1)], gsets())
    end()

    play(12, 1 << 5 | 1 << 6)
    check("two slots of one type on a step: the higher one plays", frame() == [(0xAD, 0x44), (0xAC, 1)]
          and u16(uc, SLOT + O_ON) == 1 << 6, gsets())
    end()
    play(13, 1 << 17); out(uc)
    check("repeat: the slots of the step before", u16(uc, SLOT + O_ON) == 1 << 6, hex(u16(uc, SLOT + O_ON)))
    end()
    play(14, 1 << 5 | 1 << 9 | 1 << 16); out(uc)
    check("random: one of the step's slots", u16(uc, SLOT + O_ON) in (1 << 5, 1 << 9), hex(u16(uc, SLOT + O_ON)))
    end()
    play(15, 1 << 9)
    check("one pad (a pink step): that slot", u32(uc, SLOT + O_STEPFX) == 1 << 9, hex(u32(uc, SLOT + O_STEPFX)))
    end()
    sm = smp(uc, t) & 15
    play(16, 0, 9)
    check("no pads: the track's sample's slot (a blue step); the track's own flip not read", u32(uc, SLOT + O_STEPFX) == 1 << sm,
          (hex(u32(uc, SLOT + O_STEPFX)), sm))
    end()
    play(17, 1 << 16)
    check("random alone: no slot (any slot with a type)", u32(uc, SLOT + O_STEPFX) == 1 << 16, hex(u32(uc, SLOT + O_STEPFX)))
    end()
    uc.mem_write(CONT + 0x264, b"\x00")                   # the FX track's sample view, playing
    tick(); calls.clear(); call(uc, LB["c_gx_s4_e"], pl, pidx, 20)
    uc.mem_write(pat + 8 * 21 + 3, b"\x60"); uc.mem_write(pat + 8 * 21 + 5, b"\x09")   # step 22: pad 9 from before
    pad(uc, 16 + 5)
    uc.mem_write(pat + 8 * 20 + 3, b"\x60"); uc.mem_write(pat + 8 * 20 + 5, b"\x05")   # the stock records it on step 21
    pad(uc, 16 + 9)
    uc.mem_write(pat + 8 * 20 + 5, b"\x09")             # the second finger: the stock's flip the last pad
    out(uc)
    check("recording: two pads pressed on one step both on it, its flip back to none", pk_read(uc, pidx, 20) == 1 << 5 | 1 << 9
          and b8(uc, pat + 8 * 20 + 5) == 0xFF, (hex(pk_read(uc, pidx, 20)), b8(uc, pat + 8 * 20 + 5)))
    check("recording: a step the stock did not change keeps its flip, no effects", pk_read(uc, pidx, 21) == 0
          and b8(uc, pat + 8 * 21 + 5) == 9)
    unpad(uc, 16 + 9); unpad(uc, 16 + 5)
    s4 = lambda st: (tick(), call(uc, LB["c_gx_s4_e"], pl, pidx, st))   # noqa: E731
    s4(22)
    check("its pads let go, one step on: the window still open", u32(uc, SLOT + O_SNAPV) != 0)
    s4(23)
    check("two steps on: the window ends", u32(uc, SLOT + O_SNAPV) == 0)

    def rec(st, flip, gate=6):                          # the stock's recorded step
        uc.mem_write(pat + 8 * st + 1, bytes([gate])); uc.mem_write(pat + 8 * st + 3, b"\x60")
        uc.mem_write(pat + 8 * st + 5, bytes([flip]))
    s4(24); pad(uc, 16 + 6)
    for st in (25, 26, 27):
        s4(st)
    check("a pad held over three steps: the window still open", u32(uc, SLOT + O_SNAPV) >> 24 & 1)
    rec(24, 6, 24); unpad(uc, 16 + 6)
    check("recording: a held pad's step, written at its release, gets the pad (pink), its flip none",
          pk_read(uc, pidx, 24) == 1 << 6 and b8(uc, pat + 8 * 24 + 5) == 0xFF, (hex(pk_read(uc, pidx, 24)), b8(uc, pat + 8 * 24 + 5)))
    s4(28); s4(29)
    model.clear(); model[(pidx, 26)] = 1 << 9; pk_encode(uc, t, model); rec(26, 0xFF)
    s4(26); pad(uc, 16 + 3); rec(26, 3, 3); unpad(uc, 16 + 3)
    overdub=R.get('overdub',False)
    check("recording over a step: preserves existing different effect on overdub builds", pk_read(uc, pidx, 26) == ((1 << 9 | 1 << 3) if overdub else 1 << 3),
          hex(pk_read(uc, pidx, 26)))
    if overdub:
        s4(27);s4(28);s4(29)
        model.clear();model[(pidx,26)]=(1<<5)|(1<<9)|(1<<16)|(1<<17)
        pk_encode(uc,t,model);rec(26,0xff)
        s4(26);pad(uc,16+6);rec(26,6,3);unpad(uc,16+6)
        check("overdub replaces same-type slot only, preserving other effects and random/repeat flags",
              pk_read(uc,pidx,26)==(1<<6)|(1<<9)|(1<<16)|(1<<17),hex(pk_read(uc,pidx,26)))
    s4(27); s4(28); s4(29)
    s4(28); pad(uc, 16 + 2); s4(29); pad(uc, 16 + 4)
    rec(28, 2); rec(29, 4); out(uc)
    check("pads pressed on two steps side by side: each on its own step", pk_read(uc, pidx, 28) == 1 << 2
          and pk_read(uc, pidx, 29) == 1 << 4, (hex(pk_read(uc, pidx, 28)), hex(pk_read(uc, pidx, 29))))
    unpad(uc, 16 + 4); unpad(uc, 16 + 2)
    s4(30); s4(31); s4(0); s4(1)
    s4(10); pad(uc, 16 + 5); pad(uc, 16 + 6); rec(10, 6); unpad(uc, 16 + 6); unpad(uc, 16 + 5)
    check("recording two pads of one type on a step (Reverser 6, then 7): only the newer", pk_read(uc, pidx, 10) == 1 << 6,
          hex(pk_read(uc, pidx, 10)))
    for st in list(range(11, 16)) + list(range(9)) + list(range(16)):    # a stop at step 9, a start from step 1
        s4(st)
    uc.mem_write(pat, bytes(8)); pad(uc, 16 + 4); s4(0); rec(0, 4); unpad(uc, 16 + 4)
    check("a 16-step loop, a pad pressed late on step 16 (the stock records it on step 1): on step 1, pink",
          pk_read(uc, pidx, 0) == 1 << 4 and b8(uc, pat + 5) == 0xFF, (hex(pk_read(uc, pidx, 0)), b8(uc, pat + 5)))
    s4(1); s4(2); s4(3); s4(4)
    for st in range(9):
        s4(st)
    uc.mem_write(pat + 8 * 9, bytes(8)); pad(uc, 16 + 4); s4(9); rec(9, 4); unpad(uc, 16 + 4)
    check("after a stop at step 9 and a start from step 1, a pad pressed late on step 9: on step 10, pink",
          pk_read(uc, pidx, 9) == 1 << 4 and b8(uc, pat + 8 * 9 + 5) == 0xFF, (hex(pk_read(uc, pidx, 9)), b8(uc, pat + 8 * 9 + 5)))
    uc.mem_write(CONT + 0x264, b"\x09")
    end()
    uc.mem_write(SLOT + O_STEPFX, struct.pack("<I", 1 << 5)); calls.clear()
    call(uc, NOTE_WRAP, 0x10 + t, 60, 100)
    check("the stock's note-on wrapper (its lock): the slot on at the lock's release", gsets() == [(0xAD, 0x33), (0xAC, 1)]
          and b8(uc, SLOT + O_PEND) == 0, gsets())
    now = u32(uc, HAL_TICK)
    uc.mem_write(HAL_TICK, struct.pack("<I", now + 400))
    check("no ticks for 400 ms (the sequencer stopped): the gates end", frame() == [(0xAC, 0)], gsets())
    uc.mem_write(HAL_TICK, struct.pack("<I", now))
    view(uc, MIX); was = bytes(uc.mem_read(mode_p(uc), 1)); uc.mem_write(mode_p(uc), b"\x07")
    tick(); play(18, 1 << 9); o = out(uc)
    c2 = struct.unpack("<H", uc.mem_read(0x08062B30 + 4, 2))[0]
    check("the Grid FX view: a pad the FX track plays is bright", o[16 + 9] == scl(u32(uc, 0x20003974 + 4 * (c2 - 1)), full),
          hex(o[16 + 9]))
    uc.mem_write(mode_p(uc), b"\x02"); o2 = out(uc)
    check("the Mixer view: its pads the stock's", o2[16 + 9] == 0, hex(o2[16 + 9]))
    uc.mem_write(mode_p(uc), was); view(uc, CONT)
    end()
    uc.mem_write(pat, keep_pat)

    uc.hook_del(hooks["tknob"])
    view(uc, MIX); uc.mem_write(page_p(uc), b"\x01"); btn(uc, ID_DOWN)
    ko = u32(uc, CONT + 0x1C4 + 4 * t)
    recd, turned = [], []
    rec_obj = u32(uc, ko + 0x18)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: recd.append(u.reg_read(UC_ARM_REG_R0)), None,
                0x08047D82, 0x08047D83)
    turn = u32(uc, u32(uc, ko) + 0x10) & ~1
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: turned.append((u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_R1),
                                                                u.reg_read(UC_ARM_REG_R2))), None, turn, turn + 1)
    rp = ptr(uc, u32(uc, ko + 0x2C), 0); rwas = bytes(uc.mem_read(rp, 1))
    uc.mem_write(rp, b"\x01")                              # recording
    before_k3 = knob_k(uc, t, 3); knob(uc, 3, 2)
    check("sends page with an FX track: a knob changes the shared FX-track send", knob_k(uc,t,3)==min(127,before_k3+2))
    check("recording: the turn recorded as the FX track's automation (its recorder called)", u32(uc,ENGINE+0x84+4*t) in recd,
          [hex(x) for x in recd])
    uc.mem_write(rp, rwas)
    knob(uc, 3, -2)
    knob(uc, 0, -200)
    check("sends page with an FX track: K1 turned = the FX track's K1, held at 4", knob_k(uc, t, 0) == K1_LO)
    k7 = knob_k(uc, t, 6)
    knob(uc, 6, -20)
    check("K7 turned = the FX track's K7", knob_k(uc, t, 6) == max(k7 - 20, 0), (k7, knob_k(uc, t, 6), b8(uc, SLOT)))
    o = out(uc)
    check("the knob lights by the FX track's knobs", o[LED_KNOB0] == scl(GX_RGB, LVL_ZERO * full >> 8), hex(o[LED_KNOB0]))
    btn(uc, ID_UP)
    ks = [knob_k(uc, t, k) for k in range(8)]
    view(uc, CONT); uc.mem_write(CONT + 0x264, b"\x09")
    uc.mem_write(pats + 8 * 6 + 3, b"\x60")
    pk_encode(uc, t, {(0, 6): 1 << 9})
    uc.mem_write(ptr(uc, u32(uc, PLAYERS + PL_SZ * t + 0x60), 0), b"\x05")    # its pad selected last: 6
    pad(uc, 7); unpad(uc, 7)
    b = bytes(uc.mem_read(blk(uc), 24))
    check("pad 8 on the FX track (its steps and automation): a normal track, the sends from its knobs, its knobs and sample back",
          b[12] == 0xFF and list(b[4:12]) == [knob_send(k, v) for k, v in enumerate(ks)]
          and [knob_k(uc, t, k) for k in range(8)] == before and smp(uc, t) == own, (b.hex(), ks, before, smp(uc, t), own))
    check("its steps and effects kept", b8(uc, pats + 8 * 6 + 3) == 0x60 and pk_read(uc, 0, 6) == 1 << 9 and b[22] == 5)
    pad(uc, 7); unpad(uc, 7)
    check("pad 8 again: the FX track, its effects and its pad selected last back", b8(uc, blk(uc) + 12) == t
          and pk_read(uc, 0, 6) == 1 << 9 and smp(uc, t) == 5, (b8(uc, blk(uc) + 12), smp(uc, t)))
    uc.mem_write(pats + 8 * 6 + 3, b"\x00"); out(uc)
    for _ in range(8):
        out(uc)
    check("a step deleted (anywhere): its effects go", pk_read(uc, 0, 6) == 0, hex(pk_read(uc, 0, 6)))
    pad(uc, 7); unpad(uc, 7)
    uc.mem_write(sel_p(uc), b"\x04"); pk_encode(uc, 4, {})
    pk_encode(uc, t, {(0, 2): 1 << 3}); uc.mem_write(pats + 8 * 2 + 3, b"\x60")
    pad(uc, 7); unpad(uc, 7)
    check("another track the FX track: the effects of the one before cleared", b8(uc, blk(uc) + 12) == 4 and pk_owner(uc) == 4
          and pk_read(uc, 0, 2) == 0)
    pad(uc, 7); unpad(uc, 7); uc.mem_write(sel_p(uc), bytes([t]))
    uc.mem_write(HAL_TICK, struct.pack("<I", u32(uc, HAL_TICK) + 5000))
    uc.mem_write(pats + 8 * 6 + 3, b"\x60")
    held(uc, BIT_CLEAR, True); pad(uc, 7); unpad(uc, 7); held(uc, BIT_CLEAR, False)
    check("Clear + pad 8 on a normal track: the track cleared, no FX track", b8(uc, pats + 8 * 6 + 3) == 0 and b8(uc, blk(uc) + 12) == 0xFF)
    o = out(uc)
    check("cleared: pad 8 flashes red", o[7] == scl(palc(uc, 0x55), full), hex(o[7]))
    uc.mem_write(TBL, old_tbl); uc.mem_write(src, old_src)
    v1 = bytearray(b"GX\x00\x01" + bytes([FULL, 10, FULL, FULL, FULL, FULL, FULL, FULL]))
    v1[2] = (sum(v1[4:12]) ^ 0x5C) & 0xFF
    uc.mem_write(blk(uc), bytes(v1) + bytes([0x02]) * 12)
    view(uc, MIX); uc.mem_write(page_p(uc), b"\x01"); btn(uc, ID_DOWN); o = out(uc); btn(uc, ID_UP)
    check("a v1 block (A0139-A0141): its sends read, no FX track",
          o[LED_KNOB0 + 1] == scl(GX_RGB, (LVL_ZERO + 10 * (255 - LVL_ZERO) // FULL) * full >> 8), hex(o[LED_KNOB0 + 1]))
    view(uc, CONT)


def fx_view():
    """the FX track's sample view, on a fresh unit (the stock's own pad handling run): the Grid FX pads, the steps, the lights"""
    uc = ET.setup(open(sys.argv[2], "rb").read(), open(sys.argv[3], "rb").read())
    calls, got = [], []

    def note(kind, pushed=0):
        def f(u, a, n, d):
            calls.append((kind, u.reg_read(UC_ARM_REG_R1), u.reg_read(UC_ARM_REG_R2)))
            u.reg_write(UC_ARM_REG_SP, u.reg_read(UC_ARM_REG_SP) + pushed)
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
        return f
    hooks = {kind: uc.hook_add(UC_HOOK_CODE, note(kind, 0), None, at, at + 1)
             for kind, at in (("gset", GSET), ("tknob", PREV["prev_tknob"]))}

    def take(u, a, n, d):
        got.append(a); u.reg_write(UC_ARM_REG_R0, 0); u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
    for k in ("prev_btn", "prev_knob", "prev_out"):
        uc.hook_add(UC_HOOK_CODE, take, None, PREV[k], PREV[k] + 1)
    gsets = lambda: [(c[1], c[2]) for c in calls if c[0] == "gset"]   # noqa: E731
    view(uc, CONT); uc.mem_write(CONT + 0x264, b"\x09"); uc.mem_write(sel_p(uc), b"\x02")
    t = 2
    held(uc, BIT_CLEAR, True); pad(uc, 7); unpad(uc, 7); held(uc, BIT_CLEAR, False); pad(uc, 7); unpad(uc, 7)
    check("the view's FX track", b8(uc, blk(uc) + 12) == t)
    full = 141 if u32(uc, ptr(uc, u32(uc, C.CTRL + 0x88), 2)) >> 10 & 1 else 255
    uc.mem_write(TBL, bytes([0xFF]) * (7 * 16))
    uc.mem_write(TBL + 7 * 5, bytes([1, 0x33, 0, 0, 0, 0, 0]))    # slot 5: Reverser, macro 0x33
    uc.mem_write(TBL + 7 * 6, bytes([1, 0x44, 0, 0, 0, 0, 0]))    # slot 6: Reverser too
    uc.mem_write(TBL + 7 * 9, bytes([2, 0x55, 0, 0, 0, 0, 0]))    # slot 9: Gater
    uc.mem_write(u32(uc, MGR + 0xC), bytes(uc.mem_read(TBL, 7 * 16)))
    pl = PLAYERS + PL_SZ * t
    rec = u32(uc, ENGINE + 0x84 + 4 * t)
    pat = u32(uc, rec + 4) + PAT_SZ * (uc.mem_read(ptr(uc, u32(uc, rec + 0x28), 0), 1)[0] & 7)
    uc.mem_write(CONT + 0x264, b"\x00")                   # the FX track's sample view, the stock's pad handling run
    stock_k = [0x123456 + k for k in range(8)]
    o = out(uc, knobs=stock_k)
    check("the FX view: the knob lights the sends", list(o[LED_KNOB0:LED_KNOB0 + 8]) != stock_k)
    held(uc, BIT_CLEAR, True); o = out(uc, knobs=stock_k); held(uc, BIT_CLEAR, False)
    check("Clear held: FX sends keep their knob colors", list(o[LED_KNOB0:LED_KNOB0 + 8]) != stock_k,
          [hex(x) for x in o[LED_KNOB0:LED_KNOB0 + 8]])
    so = u32(uc, CONT + 0x74 + 4 * t)
    page = 16 * (b8(uc, ptr(uc, u32(uc, so + 0x60), 0)) & 1)
    st1 = u32(uc, so + 0xC)
    hit = lambda s: b8(uc, ptr(uc, st1, 16 + s // 4) + (s & 3))     # noqa: E731
    flip = lambda s: b8(uc, ptr(uc, st1, 24 + s // 4) + (s & 3))    # noqa: E731
    fxs = lambda s: pk_read(uc, pidx, s)                              # noqa: E731
    pidx = b8(uc, ptr(uc, u32(uc, rec + 0x28), 0)) & 7
    gheld = lambda s: b8(uc, ptr(uc, u32(uc, MIX + 0x13C + 0xC), s))  # noqa: E731
    code = lambda ty: struct.unpack("<H", uc.mem_read(0x08062B30 + 2 * ty, 2))[0]   # noqa: E731
    pal = lambda c: u32(uc, 0x20003974 + 4 * (c & 0x3FF))             # noqa: E731
    o = out(uc)
    smp = b8(uc, ptr(uc, u32(uc, pl + 0x60), 0)) & 15
    pulse = 64 + ((255 - (u32(uc, 0x20003974 + 4 * 0x0A) & 0xFF)) * 192 >> 8)
    want = [scl(pal(code(1)), full) if s in (5, 6) else scl(pal(code(2)), full) if s == 9 else 0 for s in range(16)]
    want[smp] = scl(WHITE, pulse * full >> 8)
    check("its view: pads 17-32 the Grid FX pads in the stock's colours, the selected one pulsing white", list(o[16:32]) == want,
          [hex(x) for x in o[16:32]])
    s1 = knob_send(1, knob_k(uc, t, 1))
    check("its view: the knob lights the sends", o[LED_KNOB0 + 1] == scl(GX_RGB, (LVL_ZERO + s1 * (255 - LVL_ZERO) // FULL) * full >> 8))
    calls.clear(); pad(uc, 16 + 5)
    check("a Grid FX pad: on as on the Grid FX view (its held flag), its preview note kept, nothing pending",
          (0xAC, 1) in gsets() and gheld(5) == 1 and u16(uc, SLOT + O_GDOWN) == 1 << 5 and b8(uc, SLOT + O_PEND) == 0
          and "on" not in [c[0] for c in calls], (gsets(), gheld(5), calls))
    o = out(uc)
    check("held: the pad white, Up in its bright colour", o[21] == scl(WHITE, full) and o[LED_UP] == scl(pal(code(1) - 1), full),
          (hex(o[21]), hex(o[LED_UP])))
    got.clear(); btn(uc, ID_UP)
    check("Up: its settings on the knobs", b8(uc, SLOT + O_SET) == 1 and PREV["prev_btn"] not in got)
    sk = []
    h = uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: sk.append((u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_R1),
                                                                u.reg_read(UC_ARM_REG_R2))), None, 0x0805EC26, 0x0805EC27)
    calls.clear(); knob(uc, 4, 5); uc.hook_del(h)
    check("a knob: the stock's Grid FX settings knob, not the track's", sk == [(MIX + 0x94, 4, 5)]
          and "tknob" not in [c[0] for c in calls], (sk, calls))
    call(uc, 0x08052108, MIX + 0x94); lb = uc.reg_read(UC_ARM_REG_R0)
    lc = struct.unpack("<8H", uc.mem_read(lb, 16))
    o = out(uc)
    check("its settings: the knob lights the stock's, Down amber",
          [o[LED_KNOB0 + k] for k in range(8)] == [scl(pal(c), full) for c in lc] and o[LED_DOWN] == scl(GX_RGB, full),
          [hex(o[LED_KNOB0 + k]) for k in range(8)])
    btn(uc, ID_DOWN)
    check("Down: the sends again", b8(uc, SLOT + O_SET) == 0)
    calls.clear(); before_send = knob_k(uc, t, 0); knob(uc, 0, -1)
    check("then a knob changes the send through its native knob object", knob_k(uc, t, 0) == max(K1_LO, before_send - 1), (before_send, knob_k(uc,t,0)))
    uc.hook_del(hooks["tknob"])

    s3 = page + 2
    pad(uc, 2)
    check("a Grid FX pad held + step 3: a pink step (its pad in the effects), the track's flip none", hit(s3) and fxs(s3) == 1 << 5
          and flip(s3) == 0xFF, (hit(s3), hex(fxs(s3)), flip(s3)))
    unpad(uc, 2)
    check("step 3 let go: kept", hit(s3) and fxs(s3) == 1 << 5 and flip(s3) == 0xFF)
    uc.mem_write(FRAME, bytes(140)); stock_codes = u32(uc, u32(uc, CONT + 4))
    uc.mem_write(stock_codes + 2 * 2, struct.pack("<H", 0x18)); uc.mem_write(stock_codes + 2 * 5, struct.pack("<H", 0x67))
    o = out(uc)
    check("the steps' colours: pink by its effects (step 3), blue without (a flip of the track's on step 6)",
          o[2] == scl(pal(0x67), full) and o[5] == scl(pal(0x18), full), (hex(o[2]), hex(o[5])))
    uc.mem_write(CONT + 0x264, b"\x03")
    o = out(uc, knobs=stock_k)
    check("Gate view: assigned FX steps pink, unassigned steps blue",
          o[2] == scl(pal(0x67), full) and o[5] == scl(pal(0x18), full))
    check("Gate view keeps native knob lights", list(o[LED_KNOB0:LED_KNOB0 + 8]) == stock_k)
    # Use the native step renderer: selection adds bit 0, sample flip bit 8.
    # FX assignments intentionally leave the native sample-flip byte unset.
    saved_flags = bytes(uc.mem_read(so + 0x74 + 4, 2))
    for flags, expected, label in ((3, 0x69, "selected pink"), (2, 0x67, "released pink"),
                                    (0x103, 0x69, "selected pink with native flip")):
        uc.mem_write(so + 0x74 + 4, struct.pack("<H", flags))
        call(uc, 0x0805CF24, so, 2)
        native = u16(uc, u32(uc, u32(uc, so + 4)) + 4)
        uc.mem_write(stock_codes + 4, struct.pack("<H", native))
        o = out(uc)
        check("Gate native renderer: " + label + " retains its FX color/pulse",
              o[2] == scl(pal(expected), full) if native != expected else o[2] == 0,
              (hex(native), hex(o[2]), hex(expected)))
    uc.mem_write(so + 0x74 + 4, saved_flags)
    uc.mem_write(stock_codes + 2 * 5, struct.pack("<H", 0x69))
    o = out(uc)
    check("Gate selected blue FX step retains native blue/white pulse",
          o[5] == scl(pal(0x1A), full))
    uc.mem_write(stock_codes + 2 * 2, struct.pack("<H", 0x01))
    o = out(uc)
    check("Gate view preserves a held/playhead step color", o[2] == 0)
    uc.mem_write(stock_codes + 2 * 2, struct.pack("<H", 0x18))
    uc.mem_write(CONT + 0x264, b"\x00")
    pad(uc, 16 + 9); pad(uc, 3)
    s4 = page + 3
    check("two Grid FX pads held + step 4: both on it, the track's flip none", hit(s4) and fxs(s4) == 1 << 5 | 1 << 9
          and flip(s4) == 0xFF, (hit(s4), hex(fxs(s4)), flip(s4)))
    unpad(uc, 3); pad(uc, 3); unpad(uc, 3)
    check("tapped again with both held: the step gone", not hit(s4) and fxs(s4) == 0, (hit(s4), hex(fxs(s4))))
    unpad(uc, 16 + 9); unpad(uc, 16 + 5)
    check("the Grid FX pads let go: their held flags off", gheld(5) == 0 and gheld(9) == 0 and u16(uc, SLOT + O_GDOWN) == 0)
    o = out(uc)
    check("nothing held: the knobs the sends again", b8(uc, SLOT + O_SET) == 0)

    pad(uc, 2)
    o = out(uc)
    check("step 3 held: its pad bright, the others dim", o[21] == scl(pal(code(1) - 1), full) and o[25] == scl(pal(code(2)), full),
          (hex(o[21]), hex(o[25])))
    calls.clear(); pad(uc, 16 + 9); unpad(uc, 16 + 9)
    check("step held + a pad: added (not played), the track's flip none", fxs(s3) == 1 << 5 | 1 << 9 and flip(s3) == 0xFF
          and (0xAE, 1) not in gsets(), (hex(fxs(s3)), flip(s3), gsets()))
    pad(uc, 16 + 5); unpad(uc, 16 + 5)
    check("step held + one of its pads: taken off", hit(s3) and fxs(s3) == 1 << 9 and flip(s3) == 0xFF, (hit(s3), hex(fxs(s3))))
    btn(uc, ID_DOWN)
    check("step held + Down: random on", fxs(s3) == 1 << 9 | 1 << 16, hex(fxs(s3)))
    o = out(uc)
    check("step held: Down bright (random on), Up dim (repeat off), its pad bright",
          o[LED_DOWN] == scl(WHITE, full) and o[LED_UP] == scl(WHITE, 40 * full >> 8) and o[25] == scl(pal(code(2) - 1), full))
    unpad(uc, 2)
    check("the step let go after a change: kept", hit(s3) and fxs(s3) == 1 << 9 | 1 << 16 and flip(s3) == 0xFF,
          (hit(s3), hex(fxs(s3)), flip(s3)))
    s7 = page + 6
    pad(uc, 6); unpad(uc, 6)
    check("an empty step tapped: a blue step (no effects, no flip)", hit(s7) and flip(s7) == 0xFF and fxs(s7) == 0,
          (hit(s7), flip(s7), hex(fxs(s7))))
    pad(uc, 2); pad(uc, 16 + 9); unpad(uc, 16 + 9); unpad(uc, 2)
    check("step 3 held, its last pad tapped off: the step deleted", not hit(s3) and fxs(s3) == 0, (hit(s3), hex(fxs(s3))))
    pad(uc, 6); unpad(uc, 6)
    check("the blue step tapped: deleted", not hit(s7), hit(s7))
    s9 = page + 8
    for item, v in ((s9 // 4, 0x60), (16 + s9 // 4, 1), (24 + s9 // 4, 3)):   # a step with the track's flip 3
        call(uc, 0x0803FD26, st1, item); uc.mem_write(uc.reg_read(UC_ARM_REG_R0) + (s9 & 3), bytes([v]))
    call(uc, 0x0803FBEC, st1)
    pad(uc, 8); pad(uc, 16 + 9); unpad(uc, 16 + 9); unpad(uc, 8)
    check("a step of the track's with its own flip, held + a pad: the pad its effect, its flip kept", hit(s9) and fxs(s9) == 1 << 9
          and flip(s9) == 3, (hit(s9), hex(fxs(s9)), flip(s9)))
    full_sets = {((pidx + 1 + k // 32) % 8, k % 32): 1 << 16 | k << 1 for k in range(47)}
    full_sets[(pidx, s9)] = 1 << 9
    pk_encode(uc, 2, full_sets)
    pad(uc, 8); pad(uc, 16 + 5); unpad(uc, 16 + 5); unpad(uc, 8)
    check("all 47 sets in use: a new set not kept, the step keeps its pad", fxs(s9) == 1 << 9, hex(fxs(s9)))
    pad(uc, 8); pad(uc, 16 + 9); unpad(uc, 16 + 9); pad(uc, 16 + 4); unpad(uc, 16 + 4); unpad(uc, 8)
    check("a single pad needs no set: kept", fxs(s9) == 1 << 4, hex(fxs(s9)))
    pk_encode(uc, 2, {(pidx, s9): 1 << 4})                 # the 47 sets free again
    pad(uc, 8); pad(uc, 16 + 5); unpad(uc, 16 + 5); pad(uc, 16 + 6); unpad(uc, 16 + 6); unpad(uc, 8)
    check("step held + two pads of one type (Reverser 6, 7): the newer in place of the older", fxs(s9) & 0xFFFF == 1 << 4 | 1 << 6,
          hex(fxs(s9)))
    s10 = page + 9
    pad(uc, 16 + 6); pad(uc, 16 + 5); pad(uc, 9); unpad(uc, 9); unpad(uc, 16 + 5); unpad(uc, 16 + 6)
    check("two pads of one type held + an empty step: only the one pressed last", hit(s10) and fxs(s10) & 0xFFFF == 1 << 5,
          (hit(s10), hex(fxs(s10))))
    latch = ptr(uc, u32(uc, MIX + 100), 0); was = bytes(uc.mem_read(latch, 1))
    uc.mem_write(latch, b"\x01")                              # Latch on (pad 16 of the Grid FX view)
    pad(uc, 16 + 9); unpad(uc, 16 + 9); o = out(uc)
    check("Latch on, a pad tapped: still on (its held flag) and lit white", gheld(9) == 1 and o[25] == scl(WHITE, full),
          (gheld(9), hex(o[25])))
    pad(uc, 16 + 9); unpad(uc, 16 + 9); o = out(uc)
    check("tapped again: off, now the selected pad (pulsing white)", gheld(9) == 0 and o[25] == scl(WHITE, pulse * full >> 8),
          (gheld(9), hex(o[25])))
    uc.mem_write(latch, was)



def cold_start():
    """a cold start: the stock's recorders, step objects, players' sample stores, the view's light codes and the Grid FX view's
    stores not built yet (random words), a project with the FX track and its effects: the LED frames read none of them"""
    uc = ET.setup(open(sys.argv[2], "rb").read(), open(sys.argv[3], "rb").read())
    for k in ("prev_btn", "prev_knob", "prev_out"):
        uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: (u.reg_write(UC_ARM_REG_R0, 0), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))),
                    None, PREV[k], PREV[k] + 1)
    t = 2
    view(uc, CONT); uc.mem_write(CONT + 0x264, b"\x09"); uc.mem_write(sel_p(uc), bytes([t]))
    pad(uc, 7); unpad(uc, 7)
    pats = u32(uc, u32(uc, ENGINE + 0x84 + 4 * t) + 4)
    uc.mem_write(pats + 8 * 9 + 3, b"\x00")
    pk_encode(uc, t, {(0, 9): 1 << 3})
    uc.mem_write(ENGINE + 0x84, struct.pack("<8I", *[0xFFFFFF00] * 8))
    uc.mem_write(MIX + 0x13C + 0xC, struct.pack("<I", 0xFFFFFF00))
    uc.mem_write(CONT + 0x74, struct.pack("<8I", *[0xFFFFFF00] * 8))       # the step objects
    for k in range(8):
        uc.mem_write(PLAYERS + PL_SZ * k + 0x60, struct.pack("<I", 0xFFFFFF00))   # the players' sample stores
    uc.mem_write(CONT + 4, struct.pack("<I", 0xFFFFFF00))                  # the view's light codes
    uc.mem_write(CONT + 0x264, b"\x00")
    try:
        for _ in range(10):
            out(uc)
        ok = True
    except Exception as e:                                # an unmapped read stops the emulator
        ok = f"{e!r} pc {uc.reg_read(UC_ARM_REG_PC):#x} lr {uc.reg_read(UC_ARM_REG_LR):#x}"
    check("a cold start: ten LED frames, no read through the recorders or the Grid FX view's stores", ok is True, ok)
    check("the sweep finds the patterns in the session record: a deleted step's effects go", pk_read(uc, 0, 9) == 0,
          hex(pk_read(uc, 0, 9)))


def irq_short():
    """a step held + Grid FX pads (a set of two types): interrupts off only for a few instructions (the pads' scan needs them)"""
    uc = ET.setup(open(sys.argv[2], "rb").read(), open(sys.argv[3], "rb").read())
    for k in ("prev_btn", "prev_knob", "prev_out"):
        uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: (u.reg_write(UC_ARM_REG_R0, 0), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))),
                    None, PREV[k], PREV[k] + 1)
    view(uc, CONT); uc.mem_write(CONT + 0x264, b"\x09"); uc.mem_write(sel_p(uc), b"\x02")
    pad(uc, 7); unpad(uc, 7); uc.mem_write(CONT + 0x264, b"\x00")
    uc.mem_write(TBL, bytes([0xFF]) * (7 * 16))
    uc.mem_write(TBL + 7 * 5, bytes([1, 0x33, 0, 0, 0, 0, 0]))
    uc.mem_write(TBL + 7 * 9, bytes([2, 0x55, 0, 0, 0, 0, 0]))
    st = {"off": False, "n": 0, "runs": []}

    def hk(u, a, size, d):
        if st["off"]:
            st["n"] += 1
        if size == 2:
            hw = int.from_bytes(u.mem_read(a, 2), "little")
            if hw == 0xB672:                                # cpsid i
                st["off"], st["n"] = True, 0
            elif hw == 0xB662 and st["off"]:                # cpsie i
                st["off"] = False
                st["runs"].append(st["n"])
    h = uc.hook_add(UC_HOOK_CODE, hk)
    pad(uc, 4); pad(uc, 16 + 5); unpad(uc, 16 + 5); pad(uc, 16 + 9); unpad(uc, 16 + 9); unpad(uc, 4)
    uc.hook_del(h)
    check("a step held + two pads of two types (a set): interrupts off at most 200 instructions at a time",
          st["runs"] and max(st["runs"]) <= 200, st["runs"])


def scrub_test():
    """Shift + Play held: K1 moves the song position through the stock's locate; let go with no turn: Shift + Play to the stock"""
    O_SCR, ENG, LOCATE = 424, 0x2003C380, 0x08034082
    uc = ET.setup(open(sys.argv[2], "rb").read(), open(sys.argv[3], "rb").read())
    uc.mem_write(ptr(uc, C.TRANSPORT, 0), b"\x00")  # these locate cases scrub while stopped
    btns, rels, locs = [], [], []
    sh = ptr(uc, u32(uc, C.CTRL + 0xC), 0)

    def take(log):
        def f(u, a, n, d):
            log.append((u.reg_read(UC_ARM_REG_R1), b8(u, sh)))
            u.reg_write(UC_ARM_REG_R0, 0); u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
        return f
    rel_prev = PREV["prev_rel"]
    uc.hook_add(UC_HOOK_CODE, take(btns), None, PREV["prev_btn"], PREV["prev_btn"] + 1)
    uc.hook_add(UC_HOOK_CODE, take(rels), None, rel_prev, rel_prev + 1)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: (locs.append(u.reg_read(UC_ARM_REG_R1)), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))),
                None, LOCATE, LOCATE + 1)
    for k in ("prev_knob", "prev_out"):
        uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: (u.reg_write(UC_ARM_REG_R0, 0), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))),
                    None, PREV[k], PREV[k] + 1)
    rel = lambda i: call(uc, C.BTN_RELEASE, C.CTRL, i)    # noqa: E731
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: u.reg_write(UC_ARM_REG_PC, 0x0803FC22 | 1), None, 0x0803FC1C, 0x0803FC1D)  # no listeners
    pos = ptr(uc, u32(uc, ENG + 0x90), 0)
    uc.mem_write(pos, struct.pack("<I", 60))                # step 11 of the 16-step song
    uc.mem_write(sh, b"\x01"); scrub_on(uc)
    check("Shift + Play pressed" + (", held 0.5 s" if V3 else "") + ": held back from the stock", b8(uc, SLOT + O_SCR) == 1 and btns == [], btns)
    check("  Shift up in the stock while it scrubs (no Shift pages)", b8(uc, ptr(uc, u32(uc, C.CTRL + 0xC), 0)) == 0)
    o = out(uc)
    check("  K1 green while held", o[LED_KNOB0] & 0xFFFFFF in (scl(0x00FF00, 255), scl(0x00FF00, 141)), hex(o[LED_KNOB0]))
    knob(uc, 0, 2); knob(uc, 0, -5)
    check("  K1 +2, then -5: the stock's locate at step 13, then step 6", locs == [72, 30], locs)
    uc.mem_write(pos, struct.pack("<I", 84)); knob(uc, 0, 3)
    check("  K1 +3 from step 15 of 16: the song's last step", locs[-1] == 90, locs)
    uc.mem_write(pos, struct.pack("<I", 84 + 96 * 3)); knob(uc, 0, 1)
    check("  the position three loops on: still inside the song", locs[-1] == 90, locs)
    scrub_off(uc); uc.mem_write(sh, b"\x00")
    check("  let go after a turn" + (", then a Shift tap" if V3 else "") + ": nothing to the stock", btns == [] and rels == [] and b8(uc, SLOT + O_SCR) == 0, (btns, rels))
    uc.mem_write(pos, struct.pack("<I", 3))
    uc.mem_write(sh, b"\x01"); scrub_on(uc); knob(uc, 0, -1)
    check("  back past the song's start: 0", locs[-1] == 0, locs)
    scrub_off(uc); uc.mem_write(sh, b"\x01")
    btn(uc, 17); uc.mem_write(sh, b"\x00"); locs.clear(); rel(17)
    check("Shift + Play tapped (Shift let go first): the stock's Shift + Play and its release",
          [x for x, _ in btns] == [17] and [x for x, _ in rels] == [17] and locs == [], (btns, rels, locs))
    tr = ptr(uc, 0x200122B0, 0)
    uc.mem_write(tr, b"\x00"); uc.mem_write(pos, struct.pack("<I", 30))
    uc.mem_write(sh, b"\x01"); scrub_on(uc); knob(uc, 0, 3); scrub_off(uc); uc.mem_write(sh, b"\x00")
    locs.clear(); btns.clear(); rels.clear()
    start = uc.hook_add(UC_HOOK_CODE, lambda u, a_, n, d: u.mem_write(tr, b"\x01"), None, PREV["prev_btn"], PREV["prev_btn"] + 1)
    uc.mem_write(sh, b"\x01"); btn(uc, 17); uc.mem_write(sh, b"\x00"); rel(17); uc.hook_del(start)
    check("a stopped scrub (step 6 + 3), then a Shift + Play tap that starts it: from the scrub's place", locs == [8 * 6], locs)
    uc.mem_write(tr, b"\x00")
    view(uc, CONT); t = b8(uc, ptr(uc, u32(uc, CONT + 0x25C), 0)) & 7
    tp = ptr(uc, u32(uc, ENG + 0x30 + 4 * t), 1); so = u32(uc, CONT + 0x74 + 4 * t); pgp = ptr(uc, u32(uc, so + 0x60), 0)
    uc.mem_write(pgp, b"\x00"); uc.mem_write(tp, bytes([20]))
    uc.mem_write(sh, b"\x01"); scrub_on(uc); out(uc)
    check("scrubbing, the track's playhead on step 21: its page 2 shown", b8(uc, ptr(uc, u32(uc, so + 0x60), 0)) & 1 == 1)
    o = out(uc)
    check("  the playhead's pad (pad 5 of page 2) white", o[4] & 0xFFFFFF in (WHITE, scl(WHITE, 141)), hex(o[4]))
    wr = []
    hw = uc.hook_add(UC_HOOK_MEM_WRITE, lambda u, acc, ad, sz, v, d: wr.append(ad), None, u32(uc, so + 0x60), u32(uc, so + 0x60) + 0x20)
    for _ in range(5):
        out(uc)
    uc.hook_del(hw)
    check("  five more frames on that page: the page store not written again", wr == [], [hex(x) for x in wr])
    scrub_off(uc); uc.mem_write(sh, b"\x00")
    btns.clear(); rels.clear(); uc.mem_write(sh, b"\x01"); btn(uc, 17)
    uc.mem_write(HAL_TICK, struct.pack("<I", u32(uc, HAL_TICK) + 300)); o = out(uc); rel(17); uc.mem_write(sh, b"\x00")
    if V3:
        check("Shift + Play held 300 ms: shorter than the latch, the stock's Shift + Play; no scrub lights", [x for x, _ in btns] == [17]
              and [x for x, _ in rels] == [17] and b8(uc, SLOT + O_SCR) == 0 and o[LED_KNOB0] == 0, (btns, rels, hex(o[LED_KNOB0])))
    else:
        check("Shift + Play held 300 ms, no K1 turn: nothing", btns == [] and rels == [] and b8(uc, SLOT + O_SCR) == 0, (btns, rels))
    btns.clear(); rels.clear(); btn(uc, 17); rel(17)
    check("Play alone: to the stock at once", [x for x, _ in btns] == [17] and [x for x, _ in rels] == [17], (btns, rels))


def scrub_boundary_test():
    """Run the stock stop/continue paths: only the active song's final step holds playback."""
    if "build_" + os.environ["RH_BUILD"] < "build_a0167":
        return
    uc = ET.setup(open(sys.argv[2], "rb").read(), open(sys.argv[3], "rb").read())
    eng, stop, cont = 0x2003C380, 0x08033EAE, 0x08033E04
    sh = ptr(uc, u32(uc, C.CTRL + 0xC), 0)
    tr = ptr(uc, C.TRANSPORT, 0)
    pos = ptr(uc, u32(uc, eng + 0x90), 0)
    uc.mem_write(ptr(uc, eng + 0xE4, 0), b"\x01")  # stock engine enabled
    calls = []
    # Use the real engine stop and continue, omit listeners (other RTOS tasks).
    uc.hook_add(UC_HOOK_CODE, lambda u,a,n,d: u.reg_write(UC_ARM_REG_PC, 0x0803FC22 | 1), None, 0x0803FC1C, 0x0803FC1D)
    for fn, name in ((stop, "stop"), (cont, "continue")):
        uc.hook_add(UC_HOOK_CODE, lambda u,a,n,d,name=name: calls.append(name), None, fn, fn+1)
    rel = lambda: scrub_off(uc)
    def hold():
        uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0), b"\x01"); scrub_on(uc)
    def tap():
        uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0), b"\x01"); btn(uc, 17); call(uc, C.BTN_RELEASE, C.CTRL, 17)
    uc.mem_write(tr, b"\x01"); uc.mem_write(pos, struct.pack("<I", 78))
    hold(); knob(uc, 0, 1)
    check("playing, scrub to the penultimate step: keeps playing", b8(uc,ptr(uc,C.TRANSPORT,0)) == 1 and calls == [], calls)
    knob(uc, 0, 1)
    check("scrub to the final step: real stock stop, held at step 16", b8(uc,ptr(uc,C.TRANSPORT,0)) == 0 and u32(uc,ptr(uc,u32(uc,eng+0x90),0)) == 90 and calls == ["stop"], (b8(uc,ptr(uc,C.TRANSPORT,0)),u32(uc,ptr(uc,u32(uc,eng+0x90),0)),calls))
    rel(); uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0),b"\x00")
    check("let go at the end: stays stopped", b8(uc,ptr(uc,C.TRANSPORT,0)) == 0 and calls == ["stop"], calls)
    hold(); knob(uc,0,3)
    check("outward turn at the end: stays stopped at the end", b8(uc,ptr(uc,C.TRANSPORT,0)) == 0 and u32(uc,ptr(uc,u32(uc,eng+0x90),0)) == 90 and calls == ["stop"], calls)
    knob(uc,0,-1)
    check("inward turn: real stock continue from the preceding step", b8(uc,ptr(uc,C.TRANSPORT,0)) == 1 and u32(uc,ptr(uc,u32(uc,eng+0x90),0)) == 84 and calls == ["stop","continue"], (b8(uc,ptr(uc,C.TRANSPORT,0)),u32(uc,ptr(uc,u32(uc,eng+0x90),0)),calls))
    knob(uc,0,-100)
    if os.environ["RH_BUILD"] >= "a0171":
        check("scrub to beginning: real stock stop at step 1",b8(uc,ptr(uc,C.TRANSPORT,0))==0 and u32(uc,ptr(uc,u32(uc,eng+0x90),0))==0 and calls==["stop","continue","stop"],calls)
        rel();uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0),b"\x00")
        check("let go at beginning: stays stopped",b8(uc,ptr(uc,C.TRANSPORT,0))==0)
        hold();knob(uc,0,-1)
        check("outward left at beginning: stays at step 1",b8(uc,ptr(uc,C.TRANSPORT,0))==0 and u32(uc,ptr(uc,u32(uc,eng+0x90),0))==0)
        knob(uc,0,1)
        check("inward right at beginning: real stock continue at step 2",b8(uc,ptr(uc,C.TRANSPORT,0))==1 and u32(uc,ptr(uc,u32(uc,eng+0x90),0))==6 and calls[-1]=="continue",calls)
    else:
        check("scrub back to the beginning: keeps playing", b8(uc,ptr(uc,C.TRANSPORT,0)) == 1 and u32(uc,ptr(uc,u32(uc,eng+0x90),0)) == 0 and calls == ["stop","continue"], calls)
    knob(uc,0,100); rel(); uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0),b"\x00")
    check("end held again before explicit resume", b8(uc,ptr(uc,C.TRANSPORT,0)) == 0, b8(uc,ptr(uc,C.TRANSPORT,0)))
    # The stock controller's Play action is represented as in scrub_test; the
    # dump lacks the live controller listeners. Engine stop/continue above are real.
    taps = []
    tap_sh = ptr(uc,u32(uc,C.CTRL+0xC),0)
    tap_tr = ptr(uc,C.TRANSPORT,0)
    def start_tap(u,a,n,d):
        taps.append(b8(u,tap_sh))
        u.mem_write(tap_tr,b"\x01")
        u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE,start_tap,None,PREV["prev_btn"],PREV["prev_btn"]+1)
    tap(); uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0),b"\x00")
    check("Shift + Play tap resumes from the held last step", taps == [1] and b8(uc,ptr(uc,C.TRANSPORT,0)) == 1 and u32(uc,ptr(uc,u32(uc,eng+0x90),0)) == 90, (b8(uc,ptr(uc,C.TRANSPORT,0)),u32(uc,ptr(uc,u32(uc,eng+0x90),0))))
    if os.environ["RH_BUILD"] >= "a0171":
        tap_sh = ptr(uc,u32(uc,C.CTRL+0xC),0)
        tap_tr = ptr(uc,C.TRANSPORT,0)
        taps.clear();hold();knob(uc,0,-100);rel();uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0),b"\x00")
        tap_sh = ptr(uc,u32(uc,C.CTRL+0xC),0)
        tap_tr = ptr(uc,C.TRANSPORT,0)
        tap();uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0),b"\x00")
        check("Shift + Play tap explicitly resumes from held first step",taps==[1] and b8(uc,ptr(uc,C.TRANSPORT,0))==1 and u32(uc,ptr(uc,u32(uc,eng+0x90),0))==0,(taps,b8(uc,ptr(uc,C.TRANSPORT,0))))



def scrub_audio_test():
    if "build_" + os.environ["RH_BUILD"] < "build_a0168":
        return
    uc = ET.setup(open(sys.argv[2], "rb").read(), open(sys.argv[3], "rb").read())
    uc.hook_add(UC_HOOK_CODE, lambda u,a,n,d: u.reg_write(UC_ARM_REG_PC, 0x0803FC22 | 1), None, 0x0803FC1C, 0x0803FC1D)
    eng = 0x2003C380
    notes, offs, samples, turns = [], [], [], []
    def capture(log, count=3):
        def f(u,a,n,d):
            log.append(tuple(u.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)[:count]))
            u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
        return f
    objs = [u32(uc, u32(uc, CONT+0x74+4*t)+0x38) if os.environ["RH_BUILD"] >= "a0170" else u32(uc, PLAYERS+PL_SZ*t+0x54) for t in range(8)]
    vt = u32(uc, objs[0])
    uc.hook_add(UC_HOOK_CODE,capture(notes),None,u32(uc,vt)&~1,(u32(uc,vt)&~1)+1)
    uc.hook_add(UC_HOOK_CODE,capture(offs),None,u32(uc,vt+4)&~1,(u32(uc,vt+4)&~1)+1)
    uc.hook_add(UC_HOOK_CODE,capture(samples),None,int(R["prev_s4"],16),int(R["prev_s4"],16)+1)
    uc.hook_add(UC_HOOK_CODE,capture(turns),None,PREV["prev_tknob"],PREV["prev_tknob"]+1)
    uc.hook_add(UC_HOOK_CODE,capture([]),None,PREV["prev_out"],PREV["prev_out"]+1)
    # Compute store addresses outside the emulator callbacks (ptr executes ARM).
    song_pos = ptr(uc,u32(uc,eng+0x90),0)
    track_pos = [(ptr(uc,u32(uc,eng+0x30+4*t),0),ptr(uc,u32(uc,eng+0x30+4*t),1)) for t in range(8)]
    def locate(u,a,n,d):
        u.mem_write(song_pos,struct.pack("<I",u.reg_read(UC_ARM_REG_R1)))
        step=(u.reg_read(UC_ARM_REG_R1)//6)&31
        for patp, stepp in track_pos:
            u.mem_write(patp,b"\x00"); u.mem_write(stepp,bytes([step]))
        u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE,locate,None,0x08034082,0x08034083)
    for t in range(8):
        pat=u32(uc,PLAYERS+PL_SZ*t+0x50)
        for step in range(32):
            note=60+t if step==0 else 72+t if step==15 else 48+t
            uc.mem_write(pat+8*step,bytes([note,6,1,90+t,127,0xFF,0,0]))
    uc.mem_write(ptr(uc,C.TRANSPORT,0),b"\x00")
    uc.mem_write(ptr(uc,u32(uc,eng+0x90),0),struct.pack("<I",6))
    uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0),b"\x01"); scrub_on(uc)
    knob(uc,0,1)
    check("stopped scrub: sound on by default, all eight stock note dispatchers called", notes == [(objs[t],48+t,90+t) for t in range(8)], notes)
    check("  stock sample selector called at each track's located step", samples == [(PLAYERS+PL_SZ*t,0,2) for t in range(8)], samples)
    check("  audition leaves transport stopped", b8(uc,ptr(uc,C.TRANSPORT,0)) == 0)
    o=out(uc)
    if V3:
        check("scrub: K1 green, K2 K1's speed (blue), K3 the scanner (dim amber), K4 the loop length (purple), K5 sound on (green), K6-K8 dark",
              o[60] == o[64] and o[60] and o[61] and o[62] and o[63] and len({o[60], o[61], o[62], o[63]}) == 4 and list(o[65:68]) == [0]*3, o[60:68])
    elif CUES2:
        K4LIT = not K1_SLOW or bool(R["cues"].get("k1_speed"))
        check("scrub: K1 green, K2 the scanner (dim amber), K3 the timing" + (", K4 K1's " + ("speed" if K1_SLOW else "timing") if K4LIT else ", K4") + ", the rest dark",
              o[60] and o[61] and o[61] != o[60] and o[62] and bool(o[63]) == K4LIT and list(o[64:68]) == [0]*4, o[60:68])
    elif R.get("cues"):
        check("scrub: K1 and K2 green, K3 and K4 lit (marker, jump timing), K5-K8 dark",
              o[60] == o[61] and o[60] != 0 and o[62] and o[63] and list(o[64:68]) == [0]*4, o[60:68])
    else:
        check("scrub: K1 and K2 green, K3-K8 dark", o[60] == o[61] and o[60] != 0 and list(o[62:68]) == [0]*6, o[60:68])
    for v in (CONT,MIX):
        view(uc,v)
        for k in ((1,2,3,5,6,7) if V3 else range(2,8)): knob(uc,k,1); knob(uc,k,-1)
    check("K2-K8 kept from the stock on track and mixer views" if V3 else "K3-K8 disabled on track and mixer views", turns == [], turns)
    aud = (lambda on=0: knob(uc,4,1 if on else -1)) if V3 else (lambda on=0: pad(uc,23)) if CUES2 else None
    aud() if CUES2 else knob(uc,1,-1)
    check("audition off (" + ("K5 left" if V3 else "K2 left, or pad 24") + "): all audition notes released at once", offs == [(objs[t],48+t,0) for t in range(8)], offs)
    notes.clear(); samples.clear(); knob(uc,0,1)
    check("audition off: K1 still locates silently", notes == [] and samples == [])
    o=out(uc)
    led = o[64] if V3 else o[23] if CUES2 else o[61]
    check("audition off: its light red", led == scl(0xFF0000,255) or led == scl(0xFF0000,141), hex(led))
    aud(1) if CUES2 else knob(uc,1,1)
    knob(uc,0,-1)
    check("audition on again: it resumes on the next K1 turn", len(notes)==8, notes)
    offs.clear(); uc.mem_write(HAL_TICK,struct.pack("<I",u32(uc,HAL_TICK)+120)); out(uc)
    check("no turn for 120 ms: all preview notes released", len(offs)==8, offs)
    offs.clear(); notes.clear(); knob(uc,0,1); scrub_off(uc)
    check(("the scrub left (Shift tap)" if V3 else "release Play") + ": preview notes released", len(notes)==8 and len(offs)==8, (notes,offs))
    view(uc,CONT); knob(uc,2,1)
    check("after scrub: K3 returns to its normal handler", len(turns)==1, turns)
    if V3:
        uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0),b"\x01");scrub_on(uc);knob(uc,4,1)
    else:
        presses=[]
        uc.hook_add(UC_HOOK_CODE,capture(presses),None,PREV["prev_btn"],PREV["prev_btn"]+1)
        uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0),b"\x01");btn(uc,17)
        knob(uc,1,-1);call(uc,C.BTN_RELEASE,C.CTRL,17)
        check("changing K2 without K1: no accidental Shift + Play tap", presses==[],presses)
        # Running scrub uses the stock playback, with no extra audition triggers.
        uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0),b"\x01");btn(uc,17);knob(uc,1,1)
    uc.mem_write(ptr(uc,C.TRANSPORT,0),b"\x01");notes.clear();samples.clear();knob(uc,0,-1)
    check("playing scrub: no duplicate preview notes",notes==[] and samples==[],(notes,samples))



    uc.mem_write(ptr(uc,C.TRANSPORT,0),b"\x00");notes.clear();samples.clear();knob(uc,0,-100)
    check("scrub onto first step: audible, with its own notes",notes==[(objs[t],60+t,90+t) for t in range(8)] and samples==[(PLAYERS+PL_SZ*t,0,0) for t in range(8)],(notes,samples))
    notes.clear();samples.clear();knob(uc,0,100)
    check("scrub onto last step: audible, with its own notes while transport stays stopped",notes==[(objs[t],72+t,90+t) for t in range(8)] and samples==[(PLAYERS+PL_SZ*t,0,15) for t in range(8)] and b8(uc,ptr(uc,C.TRANSPORT,0))==0,(notes,samples))

def scrub_chain_bounds_test():
    if "build_" + os.environ["RH_BUILD"] < "build_a0168":
        return
    uc = ET.setup(open(sys.argv[2],"rb").read(),open(sys.argv[3],"rb").read())
    eng=0x2003C380
    scp=ptr(uc,u32(uc,eng+0xA0),0)
    chains=[ptr(uc,u32(uc,eng+0x9C),t) for t in range(8)]
    pos=ptr(uc,u32(uc,eng+0x90),0)
    sh=ptr(uc,u32(uc,C.CTRL+0xC),0)
    lens=[16]*8; locs=[]; seen=[]
    def length(u,a,n,d):
        t=u.reg_read(UC_ARM_REG_R1); info=u.reg_read(UC_ARM_REG_R2)
        seen.append((t,info))
        u.reg_write(UC_ARM_REG_R0,lens[t]*6*((info>>8&255)-(info&255)+1))
        u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def scene_end(u,a,n,d):
        sc=u.reg_read(UC_ARM_REG_R1); t=u.reg_read(UC_ARM_REG_R2)
        u.reg_write(UC_ARM_REG_R0,1 if sc==2 and t==0 else 0)
        u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def zero(u,a,n,d):
        u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def locate(u,a,n,d):
        locs.append(u.reg_read(UC_ARM_REG_R1));u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    for fn,h in ((0x08034268,length),(0x08033242,zero),(0x08033262,scene_end),(0x08034082,locate)):
        uc.hook_add(UC_HOOK_CODE,h,None,fn,fn+1)
    uc.hook_add(UC_HOOK_CODE,lambda u,a,n,d:u.reg_write(UC_ARM_REG_PC,0x0803FC22|1),None,0x0803FC1C,0x0803FC1D)
    uc.mem_write(ptr(uc,C.TRANSPORT,0),b"\x00")
    uc.mem_write(sh,b"\x01");scrub_on(uc);knob(uc,4 if V3 else 1,-1)
    for name,scene,chain,pattern_lens,expected in (
        ("one 16-step pattern",(0,0),(0,0),[16]*8,15),
        ("one 32-step pattern (both pages)",(0,0),(0,0),[32]+[16]*7,31),
        ("one scene, three chained patterns",(0,0),(0,2),[16]*8,47),
        ("two active scenes, longest track per scene",(1,2),(0,0),[32]+[16]*7,95)):
        uc.mem_write(scp,bytes(scene))
        for ch in chains:uc.mem_write(ch,bytes(chain)+b"\x00\x00")
        lens[:]=pattern_lens
        uc.mem_write(pos,struct.pack("<I",0));locs.clear();seen.clear();knob(uc,0,1000)
        check(f"scrub end: {name}",locs==[expected*6],locs)
    # Passing the first scene's end does not clamp to that intermediate edge.
    uc.mem_write(pos,struct.pack("<I",30*6));locs.clear();knob(uc,0,4)
    check("scene chain: scrub across the intermediate scene edge",locs==[34*6],locs)
    scrub_off(uc)


def scrub_page_recovery_test():
    if "build_" + os.environ["RH_BUILD"] < "build_a0168":
        return
    uc=ET.setup(open(sys.argv[2],"rb").read(),open(sys.argv[3],"rb").read())
    t=ET.sel(uc);so=u32(uc,CONT+0x74+4*t)
    ps=u32(uc,0x2003C380+0x30+4*t);pg=u32(uc,so+0x60)
    step_ptr=ptr(uc,ps,1)
    codes=u32(uc,u32(uc,so+4))
    first=[0x30+i for i in range(16)];second=[0x60+i for i in range(16)]
    uc.mem_write(codes,struct.pack("<32H",*(first+second)))
    drawn=[]
    def capture_frame(u,a,n,d):
        drawn.append(list(struct.unpack("<16H",u.mem_read(u.reg_read(UC_ARM_REG_R2),32))))
        u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE,capture_frame,None,PREV["prev_out"],PREV["prev_out"]+1)
    uc.hook_add(UC_HOOK_CODE,lambda u,a,n,d:u.reg_write(UC_ARM_REG_PC,0x0803FC22|1),None,0x0803FC1C,0x0803FC1D)
    uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0),b"\x01");scrub_on(uc)
    bad=[]
    for st in list(range(16,32))+list(range(30,14,-1)):
        # Reproduce a native page reset between scrub steps, with real store writes.
        call(uc,0x0803FD26,pg,0);uc.mem_write(uc.reg_read(UC_ARM_REG_R0),b"\x00");call(uc,0x0803FBEC,pg)
        uc.mem_write(step_ptr,bytes([st]));o=out(uc)
        want=second if st>=16 else first
        if CUES2:
            f=141 if o[st&15]==scl(WHITE,141) else 255
            shown=[scl(u32(uc,0x20003974+4*c),f) for c in want]; shown[st&15]=scl(WHITE,f)
            if b8(uc,ptr(uc,pg,0)) != st>>4 or [x for x in o[:16]] != shown:
                bad.append(st+1)
        elif b8(uc,ptr(uc,pg,0)) != st>>4 or drawn[-1] != want:
            bad.append(st+1)
    check("all steps 17-32 forward and backward: recover native page reset and draw correct page in the same frame",bad==[],bad)
    scrub_off(uc)


def scrub_any_test():
    """Shift + Play held on another screen or over a settings page: the selected track's steps on pads 1-16, pads 17-32 dark"""
    if not R.get("scrub_any"):
        return
    uc=ET.setup(open(sys.argv[2],"rb").read(),open(sys.argv[3],"rb").read())
    t=ET.sel(uc);so=u32(uc,CONT+0x74+4*t)
    ps=u32(uc,0x2003C380+0x30+4*t)
    codes=u32(uc,u32(uc,so+4))
    first=[0x30+i for i in range(16)];second=[0x60+i for i in range(16)]
    uc.mem_write(codes,struct.pack("<32H",*(first+second)))
    uc.hook_add(UC_HOOK_CODE,lambda u,a,n,d:u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR)),None,PREV["prev_out"],PREV["prev_out"]+1)
    uc.hook_add(UC_HOOK_CODE,lambda u,a,n,d:u.reg_write(UC_ARM_REG_PC,0x0803FC22|1),None,0x0803FC1C,0x0803FC1D)
    def rgb(c): return u32(uc,0x20003974+4*c)
    def steps_shown(o,want,st):
        return all(o[i] in (scl(WHITE,f) if i==st else scl(rgb(want[i]),f) for f in (255,141)) for i in range(16)) and (CUES2 or not any(o[16:32]))
    sm=int(ET.MAN["report"]["stepmut"]["slot"],16)
    step_ptr=ptr(uc,ps,1)
    uc.mem_write(step_ptr,bytes([5]))
    view(uc,ET.MIXER);o=out(uc)
    check("not scrubbing: the Mixer keeps its pads",not steps_shown(o,first,5))
    uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0),b"");scrub_on(uc)
    o=out(uc)
    check("Shift + Play held on the Mixer: the track's steps 1-16, the playhead white on step 6, pads 17-32 dark",steps_shown(o,first,5))
    uc.mem_write(step_ptr,bytes([20]));o=out(uc)
    check("the playhead on step 21: steps 17-32 on pads 1-16",steps_shown(o,second,4))
    view(uc,CONT);keep=b8(uc,sm);uc.mem_write(sm,bytes([1]))
    o=out(uc)
    check("over the Step Mutate settings page: the track's steps, not the settings",steps_shown(o,second,4))
    uc.mem_write(sm,bytes([keep]))
    scrub_off(uc)


def cue_test():
    """The cue scrub: a 1 s Shift + Play hold latches; pads 17-32 store and jump to cues; K3 the marker, K4 the jump timing"""
    if not R.get("cues") or CUES2:
        return
    O_SCR, ENG, LOCATE = 424, 0x2003C380, 0x08034082
    CR, COFF, CLEN = int(R["cues"]["ram"], 16), R["cues"]["off"], R["cues"]["len"]
    uc = ET.setup(open(sys.argv[2], "rb").read(), open(sys.argv[3], "rb").read())
    tr = ptr(uc, 0x200122B0, 0)
    uc.mem_write(tr, bytes(1))
    btns, rels, locs = [], [], []
    sh = ptr(uc, u32(uc, C.CTRL + 0xC), 0)

    def take(log):
        def f(u, a, n, d):
            log.append(u.reg_read(UC_ARM_REG_R1))
            u.reg_write(UC_ARM_REG_R0, 0); u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
        return f
    uc.hook_add(UC_HOOK_CODE, take(btns), None, PREV["prev_btn"], PREV["prev_btn"] + 1)
    uc.hook_add(UC_HOOK_CODE, take(rels), None, PREV["prev_rel"], PREV["prev_rel"] + 1)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: (locs.append(u.reg_read(UC_ARM_REG_R1)), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))),
                None, LOCATE, LOCATE + 1)
    for k in ("prev_knob", "prev_out", "prev_pad", "prev_padrel"):
        uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: (u.reg_write(UC_ARM_REG_R0, 0), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))),
                    None, PREV[k], PREV[k] + 1)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: u.reg_write(UC_ARM_REG_PC, 0x0803FC22 | 1), None, 0x0803FC1C, 0x0803FC1D)

    def rel(i): call(uc, C.BTN_RELEASE, C.CTRL, i)
    def later(ms): uc.mem_write(HAL_TICK, struct.pack("<I", u32(uc, HAL_TICK) + ms))
    def scr(): return b8(uc, SLOT + O_SCR)
    def lat(): return b8(uc, CR) == 1 and scr() == 1
    def shift(on): uc.mem_write(sh, bytes([on])); held(uc, 27, on)
    def blkc(): return bytes(uc.mem_read(tail(uc) + COFF, CLEN))
    def cue(i): b = blkc(); return b[4 + 2 * i] | b[5 + 2 * i] << 8
    pos = ptr(uc, u32(uc, ENG + 0x90), 0)
    out(uc)
    uc.mem_write(pos, struct.pack("<I", 30))
    shift(1); btn(uc, 17); later(1100); rel(17)
    check("Shift + Play held 1 s, no turn: latched; nothing to the stock", lat() and btns == [] and rels == [], (lat(), btns, rels))
    shift(0); rel(27)
    check("  Shift let go: still latched", lat())
    o = out(uc)
    check("  Play pulses green", o[49] and (o[49] >> 8) & 255 >= (o[49] >> 16) & 255, hex(o[49]))
    pad(uc, 16)
    check("tap an empty cue pad (pad 17): it stores the playhead's step", blkc()[:2] == b"GC" and cue(0) == 5, (blkc()[:4], cue(0)))
    knob(uc, 2, 4); pad(uc, 17)
    check("K3 +4, then pad 18: the marker's step stored", cue(1) == 9, cue(1))
    o = out(uc)
    check("  stored cues lit, empty ones dark", o[16] and o[17] and not o[18], [hex(x) for x in o[16:19]])
    locs.clear(); uc.mem_write(pos, struct.pack("<I", 70)); pad(uc, 16)
    check("stopped, tap a stored cue: the pause point moves to it", locs == [30], locs)
    held(uc, 23, 1); pad(uc, 17); held(uc, 23, 0)
    check("Clear + a stored cue: deleted", cue(1) == 0xFFFF, hex(cue(1)))
    uc.mem_write(tr, bytes([1]))
    knob(uc, 3, -3)
    check("K4 one click down from 1 bar (a turn of 3 in one event): 1/2", blkc()[3] == 4, blkc()[3])
    for _ in range(3):
        knob(uc, 3, -1)
    check("  three more clicks: 1/16", blkc()[3] == 1, blkc()[3])
    for _ in range(3):
        knob(uc, 3, -1)
    check("  past the end: at once", blkc()[3] == 0, blkc()[3])
    knob(uc, 3, 1)
    locs.clear(); uc.mem_write(pos, struct.pack("<I", 40)); pad(uc, 16); out(uc)
    check("playing, tap a cue: no jump before the next 1/16", locs == [], locs)
    uc.mem_write(pos, struct.pack("<I", 43)); out(uc)
    check("  at the 1/16, one pulse late: to the cue plus that pulse", locs == [31], locs)
    held(uc, 27, 1); locs.clear(); pad(uc, 16); held(uc, 27, 0)
    check("Shift + a cue while latched: at once", locs == [30], locs)
    btns.clear(); rels.clear(); shift(1); btn(uc, 17); rel(17); shift(0)
    check("Shift + Play tap while latched: the stock's Shift + Play, still latched", btns == [17] and rels == [17] and lat(), (btns, rels, lat()))
    btns.clear(); btn(uc, 2)
    check("a track button while latched: the stock's, still latched", btns == [2] and lat(), (btns, lat()))
    btns.clear(); btn(uc, 13)
    check("another button: the latch off, then the stock's", btns == [13] and not lat() and scr() == 0, (btns, lat()))


def cue2_test():
    """The held cue scrub: K2 a silent scanner, K3 the cue timing, K4 K1's timing; pads 17-23 the bar, 24 audition, 25-32 cues"""
    if not CUES2 or V3:
        return
    O_SCR, ENG, LOCATE = 424, 0x2003C380, 0x08034082
    CR, COFF, CLEN = int(R["cues"]["ram"], 16), R["cues"]["off"], R["cues"]["len"]
    MARK, FREE, BAR, DEL, TSEL, SSTEP, SPAGE = 2, 5, 6, 8, 9, 10, 11
    uc = ET.setup(open(sys.argv[2], "rb").read(), open(sys.argv[3], "rb").read())
    tr = ptr(uc, 0x200122B0, 0)
    pos = ptr(uc, u32(uc, ENG + 0x90), 0)
    btns, locs, tsel = [], [], []
    sh = ptr(uc, u32(uc, C.CTRL + 0xC), 0)

    def take(u, a, n, d):
        btns.append(u.reg_read(UC_ARM_REG_R1)); tsel.append(b8(u, CR + TSEL))
        u.reg_write(UC_ARM_REG_R0, 0); u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE, take, None, PREV["prev_btn"], PREV["prev_btn"] + 1)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: (locs.append(u.reg_read(UC_ARM_REG_R1)), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))),
                None, LOCATE, LOCATE + 1)
    for k in ("prev_rel", "prev_knob", "prev_out", "prev_pad", "prev_padrel"):
        uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: (u.reg_write(UC_ARM_REG_R0, 0), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))),
                    None, PREV[k], PREV[k] + 1)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: u.reg_write(UC_ARM_REG_PC, 0x0803FC22 | 1), None, 0x0803FC1C, 0x0803FC1D)

    def at(t, st): call(uc, LB["c_gx_trackat"], t, st); return uc.reg_read(UC_ARM_REG_R0)
    def later(ms): uc.mem_write(HAL_TICK, struct.pack("<I", u32(uc, HAL_TICK) + ms))
    def rgb(c): return u32(uc, 0x20003974 + 4 * c)
    def blkc(): return bytes(uc.mem_read(tail(uc) + COFF, CLEN))
    def cue(i): b = blkc(); return b[4 + 2 * i] | b[5 + 2 * i] << 8
    def u16(a): return struct.unpack("<H", uc.mem_read(a, 2))[0]
    def mix(a, b, w): return sum(max(0, ((a >> sh_) & 255) + ((((b >> sh_) & 255) - ((a >> sh_) & 255)) * w >> 8)) << sh_ for sh_ in (0, 8, 16))
    out(uc)
    L = next(n for n in range(1, 1024) if not at(0, n))      # the song's length in steps
    p0 = u32(uc, pos) // 6 % L * 6
    bad = []
    for t in range(8):
        ps = u32(uc, ENG + 0x30 + 4 * t)
        want = (b8(uc, ptr(uc, ps, 0)) & 7, b8(uc, ptr(uc, ps, 1)) & 31)
        a = at(t, p0 // 6)
        if not a or ((a >> 8) & 7, a & 31) != want:
            bad.append((t, hex(a), want))
    check(f"each track's pattern and step at the song position (step {p0 // 6 + 1} of {L}): the stock's own", not bad, (p0, bad))
    chp = ptr(uc, u32(uc, ENG + 0x9C), 0)                  # track 0's chain: patterns 1 and 2
    keep = bytes(uc.mem_read(chp, 4))
    uc.mem_write(chp, struct.pack("<I", 0 | 1 << 8))
    pats = u32(uc, u32(uc, 0x2003D2FC + 0x84) + 4)
    n0 = ((b8(uc, pats + 0x100) - b8(uc, pats + 0x101)) & 31) + 1
    s1 = b8(uc, pats + 0xA28 + 0x101) & 31
    a, a2 = at(0, n0 - 1), at(0, n0)
    check(f"a chain of patterns 1-2: the last step of 1 at song step {n0}, then the first step of 2", a >> 8 & 7 == 0 and a2 >> 8 & 7 == 1 and a2 & 31 == s1,
          (hex(a), hex(a2), n0, s1))
    uc.mem_write(chp, keep)
    t = b8(uc, ptr(uc, u32(uc, CONT + 0x25C), 0)) & 7
    uc.mem_write(tr, bytes(1)); uc.mem_write(pos, struct.pack("<I", 30))
    for k in range(8):
        uc.mem_write(ptr(uc, u32(uc, ENG + 0x30 + 4 * k), 1), bytes([5]))   # the tracks on step 6 with the song
    uc.mem_write(sh, b"\x01"); held(uc, 27, 1); btn(uc, 17)
    o = out(uc)
    f = 141 if o[60] == scl(0x00FF00, 141) else 255
    amber, green = rgb(0x76), scl(rgb(0x7D), f)
    check("held: K1 green, K2 dim amber, K5-K8 dark", o[60] == scl(0x00FF00, f) and o[61] == scl(amber, f >> 2) and not any(o[64:68]), [hex(x) for x in o[60:68]])
    check("  the bar (pads 17-23): the 7 timings, 1 bar bright", [x for x in o[16:23]] == [scl(rgb(0x76 + c), f if i == 5 else f >> 2) for i, c in enumerate((0, 1, 2, 3, 4, 5, 7))],
          [hex(x) for x in o[16:23]])
    check("  pad 24 green (audition on), pads 25-32 dim amber (no cues)", o[23] == scl(0x00FF00, f) and all(x == scl(amber, f >> 2) for x in o[24:32]), [hex(x) for x in o[23:32]])
    check("  the selected track's button bright green, the others dim", all(o[32 + i] == scl(0x00FF00, f if i == t else f >> 2) for i in range(8)), [hex(x) for x in o[32:40]])
    pad(uc, 24); o = out(uc)
    check("tap pad 25: the playhead's step (6) saved, pad 25 green", cue(0) == 5 and o[24] == green, (cue(0), hex(o[24])))
    TUNE = R["cues"].get("tune")
    knob(uc, 1, 8 if TUNE else 4); o = out(uc)
    a = at(t, 9)
    check("K2 +4: the scanner free at step 10, K2 bright", b8(uc, CR + FREE) == 1 and u16(CR + MARK) == 9 and o[61] == scl(amber, f), (b8(uc, CR + FREE), u16(CR + MARK)))
    check("  the scanner amber on its step", a and o[a & 15] == scl(amber, f) and b8(uc, CR + SSTEP) == a & 31, (hex(a), [hex(x) for x in o[:16]]))
    pad(uc, 25)
    check("tap pad 26: the scanner's step (10) saved; the scanner follows the playhead again", cue(1) == 9 and b8(uc, CR + FREE) == 0, (cue(1), b8(uc, CR + FREE)))
    o = out(uc)
    w = 64 + ((255 - (rgb(0x0A) & 0xFF)) * 192 >> 8)
    so = u32(uc, CONT + 0x74 + 4 * t)
    codes = list(struct.unpack("<16H", uc.mem_read(u32(uc, so + 4) + 32 * (b8(uc, CR + SPAGE)), 32)))
    if a >> 4 & 1 == b8(uc, CR + SPAGE) and (a >> 8 & 7) == (b8(uc, ptr(uc, u32(uc, ENG + 0x30 + 4 * t), 0)) & 7):
        j = a & 15
        check("  the saved cue on its step pulses green over the step's colour", o[j] == mix(scl(rgb(codes[j]), f), green, w), (hex(o[j]), hex(scl(rgb(codes[j]), f))))
    st0, pg0 = b8(uc, CR + SSTEP), b8(uc, CR + SPAGE)
    pad(uc, 2)
    check("tap step pad 3: the scanner to that step", b8(uc, CR + FREE) == 1 and u16(CR + MARK) == 5 + pg0 * 16 + 2 - st0, (u16(CR + MARK), st0, pg0))
    if R["cues"].get("home"):
        m0 = u16(CR + MARK); held(uc, 23, 1); knob(uc, 1, 1); held(uc, 23, 0)
        check("  Clear + K2: the scanner back on the playhead, K2 dim", b8(uc, CR + FREE) == 0 and out(uc)[61] == scl(amber, f >> 2), (b8(uc, CR + FREE), hex(out(uc)[61])))
        pad(uc, 2)
        check("  tap step pad 3 again: the scanner there", b8(uc, CR + FREE) == 1 and u16(CR + MARK) == m0, (b8(uc, CR + FREE), u16(CR + MARK), m0))
    pad(uc, 18)
    check("tap bar pad 19: K3's timing 1/8", blkc()[3] == 2, blkc()[3])
    if R["cues"].get("k1_speed"):
        o = out(uc)
        check("K4: K1's speed, 2 clicks a step by default (K4 one step from amber)", blkc()[20] == 1 and o[63] == scl(rgb(0x77), f), (blkc()[20], hex(o[63])))
        knob(uc, 3, 1); o = out(uc)
        check("  K4 right: faster, 1 click a step; K4 amber", blkc()[20] == 0 and o[63] == scl(rgb(0x76), f), (blkc()[20], hex(o[63])))
        knob(uc, 3, 1)
        check("  K4 right again: stays at 1 click", blkc()[20] == 0, blkc()[20])
        for _ in range(9):
            knob(uc, 3, -1)
        o = out(uc)
        check("  K4 left 9 clicks: slowest, 8 clicks a step; K4 green", blkc()[20] == 7 and o[63] == scl(rgb(0x7D), f), (blkc()[20], hex(o[63])))
        for _ in range(6):
            knob(uc, 3, 1)
        check("  back to 2 clicks", blkc()[20] == 1, blkc()[20])
    elif K1_SLOW:
        k4 = blkc()[20]; knob(uc, 3, 1); o = out(uc)
        check("K4 does nothing; the bar shows K3's timing", blkc()[20] == k4 and o[18] == scl(rgb(0x78), f) and o[17] == scl(rgb(0x77), f >> 2),
              (blkc()[20], [hex(x) for x in o[16:23]]))
    else:
        knob(uc, 3, 1); o = out(uc)
        check("K4 one click: K1's timing 1/16, the bar shows it", blkc()[20] == 1 and o[17] == scl(rgb(0x77), f), (blkc()[20], hex(o[17])))
        later(2100); o = out(uc)
        check("  2 s on: the bar shows K3's again", o[18] == scl(rgb(0x78), f) and o[17] == scl(rgb(0x77), f >> 2), [hex(x) for x in o[16:23]])
    locs.clear(); uc.mem_write(pos, struct.pack("<I", 70)); pad(uc, 24)
    check("stopped, tap a saved cue: the pause point moves to it", locs == [30], locs)
    unpad(uc, 24)
    uc.mem_write(tr, bytes([1]))
    knob(uc, 2, -1)
    AUTO = R["cues"].get("auto")
    SYNC = R["cues"].get("sync")
    if SYNC:
        uc.hook_add(UC_HOOK_CODE, lambda u, a_, n, d: (u.reg_write(UC_ARM_REG_R0, 0), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))),
                    None, 0x0803391A, 0x0803391B)       # the stock's pulse: our listener's part only
    def pulse(p_):
        """The clock's pulse with the song at p_ (played): the engine's listener sees the pulse store change"""
        uc.mem_write(pos, struct.pack("<I", p_)); uc.mem_write(ENG + 0xA4, bytes(1)); uc.mem_write(ENG + 0xA8, bytes(4))
        clk = u32(uc, ENG + 0x14); call(uc, u32(uc, u32(uc, clk) + 0x14), clk); ps_ = uc.reg_read(UC_ARM_REG_R0)
        call(uc, LB["c_gx_enl"], ENG, ps_, 0)
    locs.clear(); uc.mem_write(pos, struct.pack("<I", 40)); pad(uc, 24); out(uc)
    check("playing, cue timing 1/16: no jump before the next 1/16", locs == [], locs)
    if SYNC:
        pulse(40); out(uc)
        check("  the clock at 41 (40 played): no jump", locs == [], locs)
        pulse(41); out(uc)
        check("  the clock at 42 (the 1/16 next): the jump comes first, so the 1/16 plays the cue's first pulse", locs == [30], locs)
        uc.mem_write(ENG + 0xA4, bytes([1])); pulse(41)
        check("  no second jump", locs == [30], locs)
    elif AUTO:
        uc.mem_write(pos, struct.pack("<I", 41)); out(uc)
        check("  one pulse before the 1/16: to the cue's first pulse, which plays next", locs == [30], locs)
        unpad(uc, 24); locs.clear(); uc.mem_write(pos, struct.pack("<I", 40)); pad(uc, 24); out(uc)
    if not SYNC:
        uc.mem_write(pos, struct.pack("<I", 43)); out(uc)
        check("  at the 1/16, one pulse late: to the cue plus that pulse" + (", counted from the pulse that plays next" if AUTO else ""),
              locs == [32 if AUTO else 31], locs)
    unpad(uc, 24)
    if K1_SLOW:
        locs.clear(); uc.mem_write(pos, struct.pack("<I", 40)); knob_raw(uc, 0, 1)
        check("playing, K1 one click: no move", locs == [], locs)
        knob_raw(uc, 0, 1)
        check("  a second click: one step on at once", len(locs) == 1 and locs[0] // 6 == 7, locs)
        knob_raw(uc, 0, 1); knob_raw(uc, 0, -1)
        check("  a click, then a click back: no move", len(locs) == 1, locs)
        knob_raw(uc, 0, -3); knob_raw(uc, 0, -1)
        check("  four clicks back (3 + 1) from step 7: step 6 at the second click, step 6 again at the fourth", locs == [42, 30, 30], locs)
        if R["cues"].get("k1_speed"):
            knob(uc, 3, 1); locs.clear(); knob_raw(uc, 0, 1)
            check("  K4 at 1 click a step: one click, one step on", len(locs) == 1 and locs[0] // 6 == 7, locs)
            for _ in range(2):
                knob(uc, 3, -1)
            locs.clear(); knob_raw(uc, 0, 1); knob_raw(uc, 0, 1)
            n2 = len(locs); knob_raw(uc, 0, 1)
            check("  K4 at 3 clicks a step: no step after 2 clicks, one at the third", n2 == 0 and len(locs) == 1, (n2, locs))
            knob(uc, 3, 1)
    else:
        locs.clear(); uc.mem_write(pos, struct.pack("<I", 40)); knob(uc, 0, 2); knob(uc, 0, 1); out(uc)
        check("playing, K1 timing 1/16: three clicks wait for the next 1/16", locs == [], locs)
    if K1_SLOW:
        pass
    elif SYNC:
        pulse(41)
        check("  the clock at the 1/16: one jump, three steps on", locs == [42 + 18], locs)
    else:
        uc.mem_write(pos, struct.pack("<I", 43)); out(uc)
        check("  at the 1/16: one jump, three steps on", locs == [(44 if AUTO else 43) + 18], locs)
    if K1_SLOW:
        pass
    elif R["cues"].get("k1_edge"):
        stops = []
        goes = []
        hs = uc.hook_add(UC_HOOK_CODE, lambda u, a_, n, d: (stops.append(1), u.mem_write(tr, bytes(1)), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))), None, 0x08033EAE, 0x08033EAF)
        hg = uc.hook_add(UC_HOOK_CODE, lambda u, a_, n, d: (goes.append(1), u.mem_write(tr, bytes([1])), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))), None, 0x08033E04, 0x08033E05)
        locs.clear(); uc.mem_write(pos, struct.pack("<I", 13)); knob(uc, 0, -4)
        if SYNC:
            pulse(17)
        uc.mem_write(pos, struct.pack("<I", 18)); out(uc)
        check("  four steps back from step 4: playback stops on step 1, as the scrub", locs == [0] and stops == [1], (locs, stops))
        locs.clear(); knob(uc, 0, 1)
        check("  then K1 inward: at once one step on, playback goes on", locs == [6] and goes == [1] and b8(uc, tr) == 1, (locs, goes))
        locs.clear(); stops.clear(); uc.mem_write(pos, struct.pack("<I", 80)); knob(uc, 0, 3)
        if SYNC:
            pulse(83)
        uc.mem_write(pos, struct.pack("<I", 84)); out(uc)
        check("  three steps on from step 15: playback stops on the last step", locs == [90] and stops == [1], (locs, stops))
        knob(uc, 0, -1)                                       # inward again: playback goes on
        locs.clear(); stops.clear(); uc.mem_write(pos, struct.pack("<I", 40)); knob(uc, 0, 2)
        if SYNC:
            pulse(41); out(uc)
        else:
            uc.mem_write(pos, struct.pack("<I", 42)); out(uc)
        check("  inside the song: one jump, playback goes on", locs == [54 if SYNC else 55 if AUTO else 54] and stops == [], (locs, stops))
        uc.hook_del(hs); uc.hook_del(hg)
    else:
        uc.mem_write(pos, struct.pack("<I", 7)); knob(uc, 0, -2); uc.mem_write(pos, struct.pack("<I", 12)); out(uc)
        check("  two steps back over the song's start: from its end", locs[-1:] == [(12 - 12) % 96] and len(locs) == 2, locs)
    if R["cues"].get("peek"):
        uc.mem_write(tr, bytes(1)); pad(uc, 25); later(1100); o = out(uc)
        check("a saved cue held 1 s: kept, green", cue(1) != 0xFFFF and o[25] == green, (hex(cue(1)), hex(o[25])))
        unpad(uc, 25); held(uc, 23, 1); o = out(uc)
        check("Clear held: the saved cues red, the empty ones dim amber", o[24] == o[25] == scl(0xFF0000, f) and o[26] == scl(amber, f >> 2),
              [hex(x) for x in o[24:27]])
        pad(uc, 25); unpad(uc, 25); held(uc, 23, 0); o = out(uc)
        check("  Clear + tap cue 2: deleted, dim amber; cue 1 kept", cue(1) == 0xFFFF and cue(0) != 0xFFFF and o[25] == scl(amber, f >> 2),
              (hex(cue(1)), hex(o[25])))
    else:
        uc.mem_write(tr, bytes(1)); pad(uc, 25); later(1100); o = out(uc)   # stopped: no jump waits
        check("a saved cue held 1 s: deleted, its pad red", cue(1) == 0xFFFF and o[25] == scl(0xFF0000, f), (hex(cue(1)), hex(o[25])))
        unpad(uc, 25); o = out(uc)
        check("  let go: dim amber", o[25] == scl(amber, f >> 2) and b8(uc, CR + DEL) == 0, hex(o[25]))
    btns.clear(); tsel.clear(); btn(uc, 2)
    check("a track button while scrubbing: to the stock with the editor guard on, off after", btns == [2] and tsel == [1] and b8(uc, CR + TSEL) == 0, (btns, tsel))
    if "c_gx_tmallowed" in LB:
        uc.mem_write(CR + TSEL, b"\x01"); call(uc, LB["c_gx_tmallowed"], 3); g = uc.reg_read(UC_ARM_REG_R0); uc.mem_write(CR + TSEL, b"\x00")
        call(uc, LB["c_gx_tmallowed"], 3)
        check("  the guard: no editor for the press (8), the track after (3)", g == 8 and uc.reg_read(UC_ARM_REG_R0) == 3, g)
    if R["cues"].get("cue_plus"):
        PEND = 4
        uc.mem_write(tr, bytes(1)); uc.mem_write(pos, struct.pack("<I", 30))
        pad(uc, 5); o1 = out(uc); later(128); o2 = out(uc)
        check("hold the step of saved cue 1 (pad 6): slot 25 flashes", {o1[24], o2[24]} == {green, 0}, (hex(o1[24]), hex(o2[24])))
        unpad(uc, 5); o = out(uc)
        check("  let go: slot 25 steady green", o[24] == green, hex(o[24]))
        knob(uc, 1, 3); out(uc)
        check("K2 +3: the scanner away from the playhead", b8(uc, CR + FREE) == 1)
        pad(uc, 5); unpad(uc, 5)
        check("  tap the white playhead step: the scanner follows the playhead again", b8(uc, CR + FREE) == 0)
        uc.mem_write(tr, bytes([1])); later(2100); pad(uc, 21)
        locs.clear(); uc.mem_write(pos, struct.pack("<I", 40)); pad(uc, 24); later(1100); o = out(uc)
        check("cue timing 1 bar, a saved cue held 1 s while its jump waits: not deleted", cue(0) == 5 and o[24] != scl(0xFF0000, f) and b8(uc, CR + PEND) == 1,
              (hex(cue(0)), b8(uc, CR + PEND)))
        unpad(uc, 24); pad(uc, 24); unpad(uc, 24)
        uc.mem_write(pos, struct.pack("<I", 2)); out(uc)
        check("  tap it again: the waiting jump cancelled, no jump at the bar", b8(uc, CR + PEND) == 0 and locs == [], (b8(uc, CR + PEND), locs))
        uc.mem_write(tr, bytes(1))
        pats0 = u32(uc, u32(uc, 0x2003D2FC + 0x84) + 4)
        mode = b8(uc, pats0 + 0x103)
        uc.mem_write(pats0 + 0x103, bytes([1])); r1 = [at(0, n) & 31 for n in (0, 1, 15)]
        uc.mem_write(pats0 + 0x103, bytes([2])); r2 = [at(0, n) & 31 for n in (0, 15, 16, 17, 31)]
        uc.mem_write(pats0 + 0x103, bytes([3])); r3 = [at(0, n) & 31 for n in (0, 3)]
        uc.mem_write(pats0 + 0x103, bytes([mode]))
        check("a reverse pattern: steps 16, 15 .. 1", r1 == [15, 14, 0], r1)
        check("a ping-pong pattern: 1 .. 16, then 16 .. 1", r2 == [0, 15, 15, 14, 0], r2)
        check("a random pattern: counted as forward", r3 == [0, 3], r3)
    call(uc, C.BTN_RELEASE, C.CTRL, 17); uc.mem_write(sh, b"\x00"); held(uc, 27, 0)
    check("Play let go: the scrub ends, the scanner follows the playhead", b8(uc, SLOT + O_SCR) == 0 and b8(uc, CR + FREE) == 0)
    if R["cues"].get("latch"):
        LAT = 44
        rels = []
        hr = uc.hook_add(UC_HOOK_CODE, lambda u, a_, n, d: rels.append(u.reg_read(UC_ARM_REG_R1)), None, PREV["prev_rel"], PREV["prev_rel"] + 1)
        def rl(i): call(uc, C.BTN_RELEASE, C.CTRL, i)
        def lat(): return b8(uc, CR + LAT) == 1 and b8(uc, SLOT + O_SCR) == 1
        def shw(v):
            st_ = u32(uc, C.CTRL + 0xC)
            for b_ in range(2):
                uc.mem_write(u32(uc, st_ + 0xC + 4 * b_), bytes([v]))   # both buffers: the firmware's Shift writes swap them
        def shr(): return b8(uc, ptr(uc, u32(uc, C.CTRL + 0xC), 0))
        def shift_play(ms):
            shw(1); held(uc, 27, 1); btn(uc, 17); held(uc, 17, 1); later(ms)
            o_ = out(uc); held(uc, 17, 0); rl(17); shw(0); held(uc, 27, 0); rl(27)
            return o_
        uc.mem_write(tr, bytes(1)); btns.clear()
        o = shift_play(1100)
        DOWN = R["cues"].get("down")
        check("latch: Shift + Play held 1 s, no turn: " + ("Shift" if DOWN else "Play") + " pulses before you let go, latched after; nothing to the stock",
              (o[59] and not o[49] if DOWN else o[49]) and lat() and btns == [], (hex(o[49]), hex(o[59]), lat(), btns))
        o1 = out(uc); later(256); o2 = out(uc)
        if DOWN:
            check("  latched: Shift pulses green, Play keeps the stock's light", o1[59] and o2[59] and not o1[49] and not o2[49],
                  (hex(o1[49]), hex(o2[49]), hex(o1[59]), hex(o2[59])))
        elif R["cues"].get("tune"):
            check("  latched: Play and Shift pulse green together", o1[49] and o1[59] == o1[49] and o2[59] == o2[49],
                  (hex(o1[49]), hex(o2[49]), hex(o1[59]), hex(o2[59])))
        else:
            check("  latched: Play pulses green, Shift flashes green", o1[49] and {o1[59], o2[59]} == {scl(0x00FF00, f), 0}, (hex(o1[49]), hex(o1[59]), hex(o2[59])))
        btns.clear(); rels.clear(); btn(uc, 17); rl(17)
        check("  Play alone: the stock's, still latched", btns == [17] and rels == [17] and lat(), (btns, rels))
        btns.clear(); rels.clear(); held(uc, 27, 1); btn(uc, 27); btn(uc, 17); rl(17); rl(27); held(uc, 27, 0)
        check("  Shift + Play tap: the stock's Shift + Play, still latched", btns == [17] and rels == [17] and lat(), (btns, rels, lat()))
        btns.clear(); btn(uc, 2)
        check("  a track button: the stock's, still latched", btns == [2] and lat(), (btns, lat()))
        if R["cues"].get("latch_tap"):
            btn(uc, 27); later(600); rl(27)
            check("  Shift held 0.6 s alone, then let go: still latched", lat())
        btn(uc, 27); rl(27)
        check("  Shift tapped alone: the latch off", not lat() and b8(uc, SLOT + O_SCR) == 0)
        shift_play(1100); btns.clear(); btn(uc, 13)
        check("latched, another button (Patterns): the latch off, then the stock's", btns == [13] and not lat() and b8(uc, SLOT + O_SCR) == 0, (btns, lat()))
        if R["cues"].get("peek"):
            hq = uc.hook_add(UC_HOOK_CODE, lambda u, a_, n, d: (u.reg_write(UC_ARM_REG_R0, 0), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))),
                             None, PREV["prev_rel"], PREV["prev_rel"] + 1)   # the stock never saw these presses
            rels.clear(); later(100); rl(13)
            check("  a tap (0.1 s): the latch stays off; its release to the stock", b8(uc, CR + LAT) == 0 and b8(uc, SLOT + O_SCR) == 0 and rels == [13], rels)
            shift_play(1100); btns.clear(); rels.clear(); btn(uc, 13)
            check("latched, Patterns held: its view (the scrub off), the latch kept", btns == [13] and b8(uc, SLOT + O_SCR) == 0 and b8(uc, CR + LAT) == 1)
            later(400); rl(13); o = out(uc)
            check("  let go after 0.4 s: the release to the stock, the scrub again", rels == [13] and lat() and o[59 if DOWN else 49], (rels, lat()))
            btns.clear(); btn(uc, 16)
            check("  Record: the stock's, the scrub stays", btns == [16] and lat(), (btns, lat()))
            call(uc, C.BTN_RELEASE, C.CTRL, 16)
            held(uc, 27, 1); btn(uc, 27); btns.clear(); btn(uc, 13)
            check("  Shift held, then Patterns held: its Shift view (Shift on for the stock), the scrub off",
                  btns == [13] and shr() == 1 and b8(uc, SLOT + O_SCR) == 0, (btns, shr()))
            later(400); rl(13); o = out(uc)
            check("  let go of Patterns: the scrub again, without Shift's pages", lat() and shr() == 0, (lat(), shr()))
            rl(27); held(uc, 27, 0)
            check("  then Shift let go: still latched", lat())
            btn(uc, 27); rl(27)
            uc.hook_del(hq)
        shift_play(1100)
        held(uc, 27, 1); btn(uc, 27); btn(uc, 17); later(1100); out(uc)
        if R["cues"].get("auto"):
            btns.clear(); rels.clear(); rl(17); rl(27); held(uc, 27, 0)
            check("latched, Shift + Play held 1 s: still latched, nothing to the stock", lat() and btns == [] and 17 not in rels, (lat(), btns, rels))
            btn(uc, 27); rl(27)
            check("  then Shift tapped alone: the latch off", not lat() and b8(uc, SLOT + O_SCR) == 0)
        else:
            check("latched, Shift + Play held 1 s again: the normal view at once, while still held", not lat() and b8(uc, SLOT + O_SCR) == 0)
            rels.clear(); rl(17); rl(27); held(uc, 27, 0)
            check("  its Play release kept from the stock", 17 not in rels, rels)
        shift_play(500)
        check("Shift + Play held 0.5 s: a temporary scrub, no latch", not lat() and b8(uc, SLOT + O_SCR) == 0)
        uc.hook_del(hr)
    if R["cues"].get("tune"):
        sh = ptr(uc, u32(uc, C.CTRL + 0xC), 0)
        uc.mem_write(tr, bytes(1)); uc.mem_write(sh, b"\x01"); held(uc, 27, 1); btn(uc, 17); held(uc, 17, 1); out(uc)
        knob(uc, 1, 4); m = u16(CR + MARK)
        knob(uc, 1, 1); a1 = u16(CR + MARK)
        knob(uc, 1, 1); a2 = u16(CR + MARK)
        knob(uc, 1, 1); knob(uc, 1, -1); a3 = u16(CR + MARK)
        knob(uc, 1, -2); a4 = u16(CR + MARK)
        check("K2: one click no move, a second click one step, a click and back no move, -2 one step back", (a1, a2, a3, a4) == (m, m + 1, m + 1, m),
              (m, a1, a2, a3, a4))
        b = tail(uc) + COFF
        blk_ = bytearray(uc.mem_read(b, CLEN)); blk_[18:20] = struct.pack("<H", L + 20)
        blk_[2] = (sum(blk_[3:CLEN]) & 0xFF) ^ 0x5C; uc.mem_write(b, bytes(blk_))
        locs.clear(); pad(uc, 31); unpad(uc, 31)
        check(f"a cue past the song end (step {L + 21} of {L}), tapped while stopped: to the last step", locs and locs[-1] == (L - 1) * 6, (locs, L))
        blk_[18:20] = b"\xff\xff"; blk_[2] = (sum(blk_[3:CLEN]) & 0xFF) ^ 0x5C; uc.mem_write(b, bytes(blk_))
        held(uc, 17, 0); call(uc, C.BTN_RELEASE, C.CTRL, 17); uc.mem_write(sh, bytes(1)); held(uc, 27, 0); call(uc, C.BTN_RELEASE, C.CTRL, 27)
    if V3:
        btn(uc, 27); call(uc, C.BTN_RELEASE, C.CTRL, 27)
    if R["cues"].get("loop"):
        sh = ptr(uc, u32(uc, C.CTRL + 0xC), 0)
        uc.mem_write(tr, bytes([1])); uc.mem_write(sh, b"\x01"); held(uc, 27, 1); btn(uc, 17); held(uc, 17, 1); out(uc)
        later(2100); out(uc); pad(uc, 19); unpad(uc, 19)
        if cue(0) == 0xFFFF:
            pad(uc, 24); unpad(uc, 24)
        J = cue(0) * 6
        P0 = J + 10; B = (P0 // 24 + 1) * 24
        SY = R["cues"].get("sync")
        def at_(p_):
            if SY:
                pulse(p_)
            else:
                uc.mem_write(pos, struct.pack("<I", p_))
            out(uc)
        locs.clear(); uc.mem_write(pos, struct.pack("<I", P0)); pad(uc, 24); out(uc)
        at_(B - 1)
        check(f"K3 1/4, cue 1 held while playing: it jumps at the 1/4", locs == [J], (locs, J, B))
        at_(J); at_(J + 21) if SY else at_(J + 22)
        n1 = list(locs)
        at_(J + 23)
        check("  still held: back to the cue at the end of each 1/4 (24 pulses)", n1 == [J] and locs == [J, J], (n1, locs))
        at_(J)
        unpad(uc, 24); out(uc); at_(J + 23); at_(J + 30)
        check("  let go: no more loops, playback goes on", locs == [J, J] and b8(uc, CR + 4) == 0, (locs, b8(uc, CR + 4)))
        locs.clear(); uc.mem_write(pos, struct.pack("<I", P0)); pad(uc, 24); unpad(uc, 24); out(uc)
        at_(B - 1); at_(J + 23)
        check("a tap: one jump, no loop", locs == [J], locs)
        uc.mem_write(tr, bytes(1))
        held(uc, 17, 0); call(uc, C.BTN_RELEASE, C.CTRL, 17); uc.mem_write(sh, bytes(1)); held(uc, 27, 0); call(uc, C.BTN_RELEASE, C.CTRL, 27)
    if V3:
        btn(uc, 27); call(uc, C.BTN_RELEASE, C.CTRL, 27)


def R16ID(uc, pl, k): return struct.unpack("<H", uc.mem_read(u32(uc, pl + 0x40) + 2 * k, 2))[0]


def cue3_test():
    """A322: Shift + Play held 0.5 s latches; pads 17-24 the jump timing; K2 K1's speed, K3 the scanner, K4 the loop length, K5 sound"""
    if not V3:
        return
    O_SCR, ENG, LOCATE = 424, 0x2003C380, 0x08034082
    CR, COFF, CLEN = int(R["cues"]["ram"], 16), R["cues"]["off"], R["cues"]["len"]
    MARK, FREE, PEND, LAT, ARM, STK = 2, 5, 4, 44, 59, 63
    uc = ET.setup(open(sys.argv[2], "rb").read(), open(sys.argv[3], "rb").read())
    tr = ptr(uc, 0x200122B0, 0)
    pos = ptr(uc, u32(uc, ENG + 0x90), 0)
    btns, rels, locs = [], [], []

    def store(): return ptr(uc, u32(uc, C.CTRL + 0xC), 0)
    def shw(v):
        st_ = u32(uc, C.CTRL + 0xC)
        for b_ in range(2):
            uc.mem_write(u32(uc, st_ + 0xC + 4 * b_), bytes([v]))

    def shift_now(u):                                    # the stock's getter: [st + 0xC + 4 * (bit 0 of [st + 4])], element 0
        st_ = u32(u, C.CTRL + 0xC)
        return b8(u, u32(u, st_ + 0xC + 4 * (u32(u, st_ + 4) & 1)))
    def take(log):
        def f(u, a, n, d):
            log.append((u.reg_read(UC_ARM_REG_R1), shift_now(u)))
            u.reg_write(UC_ARM_REG_R0, 0); u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
        return f
    ptr_cache = [store()]
    uc.hook_add(UC_HOOK_CODE, take(btns), None, PREV["prev_btn"], PREV["prev_btn"] + 1)
    uc.hook_add(UC_HOOK_CODE, take(rels), None, PREV["prev_rel"], PREV["prev_rel"] + 1)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: (locs.append(u.reg_read(UC_ARM_REG_R1)), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))),
                None, LOCATE, LOCATE + 1)
    for k in ("prev_knob", "prev_out", "prev_pad", "prev_padrel"):
        uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: (u.reg_write(UC_ARM_REG_R0, 0), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))),
                    None, PREV[k], PREV[k] + 1)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: u.reg_write(UC_ARM_REG_PC, 0x0803FC22 | 1), None, 0x0803FC1C, 0x0803FC1D)
    uc.hook_add(UC_HOOK_CODE, lambda u, a_, n, d: (u.reg_write(UC_ARM_REG_R0, 0), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))),
                None, 0x0803391A, 0x0803391B)                 # the stock's pulse: our listener's part only

    def later(ms): uc.mem_write(HAL_TICK, struct.pack("<I", u32(uc, HAL_TICK) + ms))
    def rgb(c): return u32(uc, 0x20003974 + 4 * c)
    def blkc(): return bytes(uc.mem_read(tail(uc) + COFF, CLEN))
    def cue(i): b = blkc(); return b[4 + 2 * i] | b[5 + 2 * i] << 8
    def u16(a): return struct.unpack("<H", uc.mem_read(a, 2))[0]
    def rl(i): call(uc, C.BTN_RELEASE, C.CTRL, i)
    def lat(): return b8(uc, CR + LAT) == 1 and b8(uc, SLOT + O_SCR) == 1
    def pulse(p_):
        uc.mem_write(pos, struct.pack("<I", p_)); uc.mem_write(ENG + 0xA4, bytes(1)); uc.mem_write(ENG + 0xA8, bytes(4))
        clk = u32(uc, ENG + 0x14); call(uc, u32(uc, u32(uc, clk) + 0x14), clk); ps_ = uc.reg_read(UC_ARM_REG_R0)
        call(uc, LB["c_gx_enl"], ENG, ps_, 0)

    out(uc)
    t = b8(uc, ptr(uc, u32(uc, CONT + 0x25C), 0)) & 7
    uc.mem_write(tr, bytes(1)); uc.mem_write(pos, struct.pack("<I", 30))
    for k in range(8):
        uc.mem_write(ptr(uc, u32(uc, ENG + 0x30 + 4 * k), 1), bytes([5]))
    # the latch
    shw(1); ptr_cache[0] = store(); held(uc, 27, 1); btn(uc, 17); held(uc, 17, 1); o = out(uc)
    check("Shift + Play down: held back from the stock, no scrub screen yet", btns == [] and b8(uc, SLOT + O_SCR) == 0 and o[60] == 0, (btns, hex(o[60])))
    later(400); o = out(uc)
    check("  at 0.4 s: still no scrub screen", b8(uc, SLOT + O_SCR) == 0 and o[60] == 0)
    later(150); o = out(uc)
    f = 141 if o[60] == scl(0x00FF00, 141) else 255
    amber, green = rgb(0x76), scl(rgb(0x7D), f)
    check("  at 0.55 s: latched, the scrub screen; Shift up in the stock", lat() and o[60] == scl(0x00FF00, f) and b8(uc, store()) == 0, (lat(), hex(o[60])))
    held(uc, 17, 0); rl(17); shw(0); held(uc, 27, 0); rl(27)
    check("  Play and Shift let go: nothing to the stock, still latched", btns == [] and rels == [] and lat(), (btns, rels, lat()))
    o1 = out(uc); later(256); o2 = out(uc)
    check("  Shift pulses green; Play keeps the stock's light", o1[59] and o2[59] and o1[49] == 0, (hex(o1[59]), hex(o2[59]), hex(o1[49])))
    o = o1
    k4 = scl(rgb(0x7B), f) if ONE else scl(0xA000FF, f)
    check("knobs: K1 green, K2 blue (K1's speed), K3 dim amber (the scanner), K4 " + ("the timing pad's colour (1 bar)" if ONE else "purple (the loop length)")
          + ", K5 green (sound on), K6-K8 dark",
          [o[60 + k] for k in range(8)] == [scl(0x00FF00, f), scl(0x0040FF, f), scl(amber, f >> 2), k4, scl(0x00FF00, f), 0, 0, 0],
          [hex(x) for x in o[60:68]])
    bar = [scl(WHITE if i == 0 else rgb(0x76 + (0, 1, 2, 3, 4, 5, 7)[i - 1]), f if i == 6 else f >> 2) for i in range(8)]
    check("pads 17-24: at once (white), 1/32, 1/16, 1/8, 1/4, 1/2, 1 bar (bright), 2 bars", list(o[16:24]) == bar, [hex(x) for x in o[16:24]])
    check("  pads 25-32 dim amber (no cues); the selected track's button bright green",
          all(x == scl(amber, f >> 2) for x in o[24:32]) and all(o[32 + i] == scl(0x00FF00, f if i == t else f >> 2) for i in range(8)))
    # pads
    pad(uc, 16); o = out(uc)
    check("tap pad 17: at once, white bright", blkc()[21] == 0 and o[16] == scl(WHITE, f), (blkc()[21], hex(o[16])))
    pad(uc, 23); o = out(uc)
    check("tap pad 24: 2 bars, bright", blkc()[21] == 7 and o[23] == scl(rgb(0x7D), f) and o[16] == scl(WHITE, f >> 2), (blkc()[21], hex(o[23])))
    pad(uc, 17)
    check("tap pad 18: 1/32", blkc()[21] == 1, blkc()[21])
    pad(uc, 24); o = out(uc)
    check("tap pad 25: the playhead's step (6) saved, pad 25 green", cue(0) == 5 and o[24] == green, (cue(0), hex(o[24])))
    # K3 the scanner
    knob(uc, 2, 8); o = out(uc)
    check("K3 8 clicks: the scanner 4 steps on (step 10), K3 bright", b8(uc, CR + FREE) == 1 and u16(CR + MARK) == 9 and o[62] == scl(amber, f),
          (b8(uc, CR + FREE), u16(CR + MARK), hex(o[62])))
    pad(uc, 25)
    check("tap pad 26: the scanner's step (10) saved; the scanner follows the playhead", cue(1) == 9 and b8(uc, CR + FREE) == 0, (cue(1), b8(uc, CR + FREE)))
    knob(uc, 2, 2); held(uc, 23, 1); knob(uc, 2, 1); held(uc, 23, 0)
    check("Clear + K3: the scanner back on the playhead", b8(uc, CR + FREE) == 0)
    # K2 K1's speed
    knob(uc, 1, 3); o = out(uc)
    check("K2 3 clicks: no change (2 clicks a step); the bar shows it: 2 of 8 pads bright blue",
          blkc()[20] == 1 and list(o[16:24]) == [scl(0x0040FF, f if i < 2 else f >> 2) for i in range(8)], (blkc()[20], [hex(x) for x in o[16:24]]))
    knob(uc, 1, 1); o = out(uc)
    check("  the 4th click right: faster, 1 click a step; 1 pad bright", blkc()[20] == 0 and o[16] == scl(0x0040FF, f) and o[17] == scl(0x0040FF, f >> 2),
          (blkc()[20], [hex(x) for x in o[16:24]]))
    locs.clear(); knob_raw(uc, 0, 1)
    check("  K1 one click: one step", len(locs) == 1, locs)
    knob(uc, 1, -8)
    check("  K2 8 clicks left: 2 settings slower, 3 clicks a step", blkc()[20] == 2, blkc()[20])
    locs.clear(); knob_raw(uc, 0, 2); n2 = len(locs); knob_raw(uc, 0, 1)
    check("  K1: no step after 2 clicks, one at the 3rd", n2 == 0 and len(locs) == 1, (n2, locs))
    knob(uc, 1, 4); later(2100); o = out(uc)
    check("  back to 2 clicks; 2 s on: the bar shows the jump timing again", blkc()[20] == 1 and o[17] == scl(rgb(0x76), f), (blkc()[20], hex(o[17])))
    if not ONE:
        # K4 the loop length
        knob(uc, 3, 4); o = out(uc)
        check("K4 4 clicks right: the loop 2 bars; the bar shows it in purple on pads 18-24, pad 17 dark",
              blkc()[22] == 7 and o[16] == 0 and o[23] == scl(0xA000FF, f) and o[22] == scl(0xA000FF, f >> 2), (blkc()[22], [hex(x) for x in o[16:24]]))
        knob(uc, 3, -12)
        check("  12 clicks left: 1/4", blkc()[22] == 4, blkc()[22])
    else:
        # K4 the same timing as the pads, pads 18-24 only
        knob(uc, 3, 4); o = out(uc)
        check("K4 4 clicks right from 1/32: 1/16, pad 19 bright on the timing bar", blkc()[21] == 2 and o[18] == scl(rgb(0x77), f) and o[17] == scl(rgb(0x76), f >> 2),
              (blkc()[21], [hex(x) for x in o[16:24]]))
        knob(uc, 3, 40)
        check("  40 clicks right: stops at 2 bars", blkc()[21] == 7, blkc()[21])
        knob(uc, 3, -40)
        check("  40 clicks left: stops at 1/32, never at once", blkc()[21] == 1, blkc()[21])
        pad(uc, 16); knob(uc, 3, -4)
        check("  at once (pad 17), K4 4 clicks left: 1/32", blkc()[21] == 1, blkc()[21])
        pad(uc, 16); knob(uc, 3, 4)
        check("  at once, K4 4 clicks right: 1/32", blkc()[21] == 1, blkc()[21])
    # K5 sound
    knob(uc, 4, -1); o = out(uc)
    check("K5 left: sound off, K5 red", o[64] == scl(0xFF0000, f), hex(o[64]))
    knob(uc, 4, 1); o = out(uc)
    check("  K5 right: sound on, K5 green", o[64] == scl(0x00FF00, f), hex(o[64]))
    # jumps on the clock: 1/32
    uc.mem_write(tr, bytes([1])); locs.clear(); uc.mem_write(pos, struct.pack("<I", 40)); pad(uc, 24); unpad(uc, 24)
    pulse(40)
    check("playing, 1/32, tap cue 1 at pulse 40: no jump before the 1/32", locs == [], locs)
    pulse(41)
    check("  the clock at 42: the jump comes first, so 42 plays the cue's first pulse", locs == [30], locs)
    if not ONE:
        # a held cue loops at the K4 length (1/4 = 24 pulses); K4 changes it at once
        locs.clear(); uc.mem_write(pos, struct.pack("<I", 40)); pad(uc, 24); pulse(41)
        check("hold cue 1: it jumps at the 1/32", locs == [30], locs)
        pulse(52); n1 = list(locs); pulse(53)
        check("  still held: back to the cue at the end of each 1/4 (24 pulses)", n1 == [30] and locs == [30, 30], (n1, locs))
        uc.mem_write(pos, struct.pack("<I", 40)); knob(uc, 3, -4)
        check("  K4 to 1/8 while it loops (10 pulses in): the loop shorter at once", blkc()[22] == 3, blkc()[22])
        pulse(40); n1 = list(locs); pulse(41)
        check("  back to the cue 12 pulses after it", n1 == [30, 30] and locs == [30, 30, 30], (n1, locs))
        unpad(uc, 24); pulse(41)
        check("  let go: no more loops", locs == [30, 30, 30] and b8(uc, CR + PEND) == 0, (locs, b8(uc, CR + PEND)))
        pad(uc, 16); locs.clear(); uc.mem_write(pos, struct.pack("<I", 40)); pad(uc, 24)
        check("at once, hold cue 1: it jumps at once", locs == [30], locs)
        pulse(40); n1 = list(locs); pulse(41)
        check("  and still loops at the K4 length (1/8)", n1 == [30] and locs == [30, 30], (n1, locs))
        unpad(uc, 24); pad(uc, 17); uc.mem_write(tr, bytes(1))
    else:
        # a held cue loops at the same timing; K4 changes it while it loops
        pad(uc, 20); locs.clear(); uc.mem_write(pos, struct.pack("<I", 40)); pad(uc, 24); pulse(46); n1 = list(locs); pulse(47)
        check("1/4 (pad 21), hold cue 1 at pulse 40: it jumps at the 1/4 (48)", n1 == [] and locs == [30], (n1, locs))
        pulse(52); n1 = list(locs); pulse(53)
        check("  still held: back to the cue each 1/4 (24 pulses)", n1 == [30] and locs == [30, 30], (n1, locs))
        uc.mem_write(pos, struct.pack("<I", 40)); knob(uc, 3, -4)
        check("  K4 to 1/8 while it loops (10 pulses in): the timing 1/8, the loop shorter at once", blkc()[21] == 3, blkc()[21])
        pulse(40); n1 = list(locs); pulse(41)
        check("  back to the cue 12 pulses after it", n1 == [30, 30] and locs == [30, 30, 30], (n1, locs))
        pad(uc, 21)
        check("  pad 22 while it loops: 1/2, the same setting", blkc()[21] == 5, blkc()[21])
        unpad(uc, 24); uc.mem_write(pos, struct.pack("<I", 40)); pulse(41); pulse(53)
        check("  let go: no more loops", locs == [30, 30, 30] and b8(uc, CR + PEND) == 0, (locs, b8(uc, CR + PEND)))
        pad(uc, 16); locs.clear(); uc.mem_write(pos, struct.pack("<I", 40)); pad(uc, 24)
        check("at once, hold cue 1: it jumps at once", locs == [30], locs)
        for p_ in (40, 41, 52, 53, 76, 77):
            pulse(p_)
        check("  and does not loop (K4 or a pad 18-24 gives it a loop)", locs == [30] and b8(uc, CR + PEND) == 0, (locs, b8(uc, CR + PEND)))
        unpad(uc, 24); pad(uc, 17); uc.mem_write(tr, bytes(1))
    # leave: a Shift tap
    btn(uc, 27); rl(27)
    check("a Shift tap: the latch off", not lat())
    # a short Shift + Play: the stock's, with no scrub screen
    btns.clear(); rels.clear(); shw(1); ptr_cache[0] = store(); held(uc, 27, 1); btn(uc, 17); later(200); o = out(uc); rl(17); held(uc, 27, 0); shw(0)
    check("Shift + Play tapped: the stock's Shift + Play (Shift on), no scrub screen", [x for x, _ in btns] == [17] and btns[0][1] == 1 and [x for x, _ in rels] == [17]
          and o[60] == 0 and not lat(), (btns, rels, hex(o[60])))
    # sticky Shift: on in the stock with no Shift button held
    btns.clear(); rels.clear(); shw(1); ptr_cache[0] = store(); btn(uc, 17); held(uc, 17, 1); later(600); out(uc); held(uc, 17, 0); rl(17)
    check("sticky Shift on, Play held 0.5 s: latched, nothing to the stock", lat() and btns == [] and b8(uc, CR + STK) == 1, (lat(), btns, b8(uc, CR + STK)))
    ptr_cache[0] = store(); btn(uc, 17); rl(17)
    check("  Play alone: the stock's Shift + Play (continue), as sticky Shift does", [x for x, _ in btns] == [17] and btns[0][1] == 1 and lat(), (btns, lat()))
    btns.clear(); btn(uc, 13); later(100); rl(13)
    check("  a tap on Patterns: the latch off, sticky Shift on again in the stock", not lat() and b8(uc, store()) == 1 and b8(uc, CR + STK) == 0,
          (lat(), b8(uc, store()), b8(uc, CR + STK)))
    shw(0)


def cols_test():
    """A323: the scanner's page in a pattern the stock does not show: the stock step view's codes for notes, flips, empty steps
    and steps outside the pattern"""
    if not R.get("cues", {}).get("cols"):
        return
    ENG, PAT = 0x2003C380, 0xA28
    CR = int(R["cues"]["ram"], 16)
    uc = ET.setup(open(sys.argv[2], "rb").read(), open(sys.argv[3], "rb").read())
    for k in ("prev_btn", "prev_rel", "prev_knob", "prev_out", "prev_pad", "prev_padrel"):
        uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: (u.reg_write(UC_ARM_REG_R0, 0), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))),
                    None, PREV[k], PREV[k] + 1)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: u.reg_write(UC_ARM_REG_PC, 0x0803FC22 | 1), None, 0x0803FC1C, 0x0803FC1D)
    t = b8(uc, ptr(uc, u32(uc, CONT + 0x25C), 0)) & 7
    check("cols: track 1 selected", t == 0, t)
    rec = u32(uc, 0x2003D2FC + 0x84)
    pats = u32(uc, rec + 4)
    def rgb(c): return u32(uc, 0x20003974 + 4 * c)
    def at(st): call(uc, LB["c_gx_trackat"], 0, st); return uc.reg_read(UC_ARM_REG_R0)
    uc.mem_write(ptr(uc, u32(uc, ENG + 0x9C), 0), struct.pack("<I", 0 | 1 << 8))   # track 1's chain: patterns 1-2
    note, flip = bytes.fromhex("4806016007ff0000"), bytes.fromhex("4806016007040000")
    for st_, b_ in ((2, note), (5, flip), (13, note)):
        uc.mem_write(pats + PAT + 8 * st_, b_)
    uc.mem_write(pats + PAT + 0x100, bytes([11, 0]))     # pattern 2: steps 1-12
    uc.mem_write(ptr(uc, 0x200122B0, 0), bytes(1))
    uc.mem_write(ptr(uc, u32(uc, C.CTRL + 0xC), 0), b"")
    scrub_on(uc)
    o = out(uc)
    f = 141 if o[60] == scl(0x00FF00, 141) else 255
    want = {i: 0 if i > 11 and i != 13 else scl(rgb(0x56 if i > 11 else 0x67 if i == 5 else 0x18 if i == 2 else 0x19), f) for i in range(16)}
    for _ in range(64):
        a = at(struct.unpack("<H", uc.mem_read(CR + 2, 2))[0])
        if b8(uc, CR + 5) and a >> 8 & 7 == 1 and a & 31 == 9:
            break
        knob_raw(uc, 2, 2)
    o = out(uc)
    vp = b8(uc, ptr(uc, u32(uc, rec + 0x28), 0)) & 7
    bad = [(i, hex(o[i]), hex(want[i])) for i in range(16) if i != 9 and o[i] != want[i]]
    check("scanner on pattern 2 step 10, the stock shows pattern 1: notes blue, the flip pink, empty steps dim, outside steps 13-16 dark, a note there red",
          vp == 0 and a >> 8 & 7 == 1 and not bad, (vp, hex(a), bad))
    for _ in range(64):
        ps = u32(uc, ENG + 0x30)
        if b8(uc, ptr(uc, ps, 0)) & 7 == 1 and b8(uc, ptr(uc, ps, 1)) & 31 == 3:
            break
        knob(uc, 0, 1)
    o = out(uc)
    vp = b8(uc, ptr(uc, u32(uc, rec + 0x28), 0)) & 7
    bad = [(i, hex(o[i]), hex(want[i])) for i in range(16) if i not in (3, 9) and o[i] != want[i]]
    check("  then K1 to pattern 2 step 4 (the stock still shows pattern 1): the same colours, the playhead white",
          vp == 0 and o[3] == scl(0xFFFFFF, f) and not bad, (vp, hex(o[3]), bad))
    scrub_off(uc)


def pass_test():
    """A325: a saved cue pulses only on the pattern pass that holds its song step"""
    if not R.get("cues", {}).get("pass"):
        return
    ENG = 0x2003C380
    uc = ET.setup(open(sys.argv[2], "rb").read(), open(sys.argv[3], "rb").read())
    for k in ("prev_btn", "prev_rel", "prev_knob", "prev_out", "prev_pad", "prev_padrel"):
        uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: (u.reg_write(UC_ARM_REG_R0, 0), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))),
                    None, PREV[k], PREV[k] + 1)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: u.reg_write(UC_ARM_REG_PC, 0x0803FC22 | 1), None, 0x0803FC1C, 0x0803FC1D)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR)), None, 0x08034082, 0x08034083)
    pos = ptr(uc, u32(uc, ENG + 0x90), 0)
    uc.mem_write(ptr(uc, u32(uc, ENG + 0x9C), 1), struct.pack("<I", 0 | 1 << 8))   # track 2: patterns 1-2, so the scene is 32 steps
    uc.mem_write(ptr(uc, 0x200122B0, 0), bytes(1))
    def at(n):                                           # the song and every track on song step n + 1
        uc.mem_write(pos, struct.pack("<I", 6 * n))
        for k in range(8):
            ps = u32(uc, ENG + 0x30 + 4 * k)
            uc.mem_write(ptr(uc, ps, 0), bytes([n // 16 & 1 if k == 1 else 0])); uc.mem_write(ptr(uc, ps, 1), bytes([n & 15]))
    def pulsing(i):
        for _ in range(8):
            uc.mem_write(HAL_TICK, struct.pack("<I", u32(uc, HAL_TICK) + 64)); o = out(uc)
            if o[i] != o[(i + 2) % 16]:
                return True
        return False
    at(2)
    uc.mem_write(ptr(uc, u32(uc, C.CTRL + 0xC), 0), b"")
    scrub_on(uc)
    pad(uc, 24); unpad(uc, 24)
    at(5)
    p1 = pulsing(2)
    at(21)
    p2 = pulsing(2)
    check("a cue on song step 3: it pulses on track 1's first pass (playhead on step 6), not on its second (step 22, the same pattern step)",
          p1 and not p2, (p1, p2))
    scrub_off(uc)


def tap_test():
    """A326: a step tap moves the scanner to that step at any pattern speed"""
    if not R.get("cues", {}).get("tap"):
        return
    ENG = 0x2003C380
    CR = int(R["cues"]["ram"], 16)
    uc = ET.setup(open(sys.argv[2], "rb").read(), open(sys.argv[3], "rb").read())
    for k in ("prev_btn", "prev_rel", "prev_knob", "prev_out", "prev_pad", "prev_padrel"):
        uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: (u.reg_write(UC_ARM_REG_R0, 0), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))),
                    None, PREV[k], PREV[k] + 1)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: u.reg_write(UC_ARM_REG_PC, 0x0803FC22 | 1), None, 0x0803FC1C, 0x0803FC1D)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR)), None, 0x08034082, 0x08034083)
    model = u32(uc, u32(uc, ENG + 0x20))                  # [+ 0x5140 t + 0xA28 p + 0x3E6]: the pattern's speed, 0-7 (2-24 pulses a step)
    def at(st): call(uc, LB["c_gx_trackat"], 0, st); return uc.reg_read(UC_ARM_REG_R0)
    uc.mem_write(ptr(uc, 0x200122B0, 0), bytes(1))
    uc.mem_write(ptr(uc, u32(uc, ENG + 0x90), 0), struct.pack("<I", 0))
    for k in range(8):
        ps = u32(uc, ENG + 0x30 + 4 * k)
        uc.mem_write(ptr(uc, ps, 0), bytes(1)); uc.mem_write(ptr(uc, ps, 1), bytes(1))
    for speed, name in ((5, "half speed (12 pulses a step)"), (1, "fast (3 pulses a step)"), (3, "normal")):
        uc.mem_write(model + 0x3E6, bytes([speed]))
        uc.mem_write(ptr(uc, u32(uc, C.CTRL + 0xC), 0), b"\x01")
        scrub_on(uc)
        res = []
        for want in (5, 12):
            pad(uc, want); unpad(uc, want); o = out(uc)
            m = struct.unpack("<H", uc.mem_read(CR + 2, 2))[0]
            a = at(m)
            res.append((want, m, hex(a)))
            pad(uc, 0); unpad(uc, 0); out(uc)       # the playhead's step: the scanner follows again
        ok = all(int(a_, 16) & 31 in ((w,) if speed != 1 else (w, w - 1, w + 1)) and int(a_, 16) >> 8 & 7 == 0 for w, _, a_ in res)
        check(f"track 1 at {name}: a tap on step 6, then 13, moves the scanner to that step", ok, res)
        if R["cues"].get("home1") and speed == 3:
            pad(uc, 9); unpad(uc, 9); f1 = b8(uc, CR + 5); knob_raw(uc, 0, 1); f2 = b8(uc, CR + 5); knob_raw(uc, 0, 0); f3 = b8(uc, CR + 5)
            check("  a tap on step 10, then one K1 click: the scanner follows the playhead again (a zero turn: no change)", f1 == 1 and f2 == 0 and f3 == 0, (f1, f2, f3))
            pad(uc, 9); unpad(uc, 9); knob_raw(uc, 0, 0)
            check("  a K1 event with no turn leaves the scanner where it is", b8(uc, CR + 5) == 1)
        scrub_off(uc)


def bar_punch_test():
    """A328: 1 and 2 bars are passes of the selected track's pattern; a tap on the scanner's own step punches in"""
    if not R.get("cues", {}).get("bar"):
        return
    ENG, LOCATE = 0x2003C380, 0x08034082
    CR = int(R["cues"]["ram"], 16)
    FREE, PEND = 5, 4
    uc = ET.setup(open(sys.argv[2], "rb").read(), open(sys.argv[3], "rb").read())
    btns, locs = [], []
    def stub(log=None):
        def f(u, a, n, d):
            if log is not None:
                log.append(u.reg_read(UC_ARM_REG_R1))
            u.reg_write(UC_ARM_REG_R0, 0); u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
        return f
    uc.hook_add(UC_HOOK_CODE, stub(btns), None, PREV["prev_btn"], PREV["prev_btn"] + 1)
    for k in ("prev_rel", "prev_knob", "prev_out", "prev_pad", "prev_padrel"):
        uc.hook_add(UC_HOOK_CODE, stub(), None, PREV[k], PREV[k] + 1)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: (locs.append(u.reg_read(UC_ARM_REG_R1)), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))),
                None, LOCATE, LOCATE + 1)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: u.reg_write(UC_ARM_REG_PC, 0x0803FC22 | 1), None, 0x0803FC1C, 0x0803FC1D)
    tr = ptr(uc, 0x200122B0, 0)
    def setpos(p_): uc.mem_write(ptr(uc, u32(uc, ENG + 0x90), 0), struct.pack("<I", p_))   # the store's current buffer each time
    def later(ms): uc.mem_write(HAL_TICK, struct.pack("<I", u32(uc, HAL_TICK) + ms))
    def at(n):
        setpos(6 * n)
        for k in range(8):
            ps = u32(uc, ENG + 0x30 + 4 * k)
            uc.mem_write(ptr(uc, ps, 0), bytes(1)); uc.mem_write(ptr(uc, ps, 1), bytes([n % 12]))
    def pulse(p_):
        setpos(p_); uc.mem_write(ENG + 0xA4, bytes(1)); uc.mem_write(ENG + 0xA8, bytes(4))
        clk = u32(uc, ENG + 0x14); call(uc, u32(uc, u32(uc, clk) + 0x14), clk); ps_ = uc.reg_read(UC_ARM_REG_R0)
        call(uc, LB["c_gx_enl"], ENG, ps_, 0)
    for k in range(8):                                   # every track: a 12-step pattern, so the song is 12 steps (72 pulses)
        uc.mem_write(u32(uc, u32(uc, 0x2003D2FC + 0x84 + 4 * k) + 4) + 0x100, bytes([11, 0]))
    uc.mem_write(tr, bytes(1)); at(2)
    uc.mem_write(ptr(uc, u32(uc, C.CTRL + 0xC), 0), b"\x01")
    scrub_on(uc)
    pad(uc, 24); unpad(uc, 24)                           # cue 1 on song step 3 (pulse 12); the timing 1 bar
    uc.mem_write(tr, bytes([1])); locs.clear()
    setpos(40); pad(uc, 24)
    pulse(70); n1 = list(locs); pulse(71)
    check("12-step patterns, 1 bar, hold cue 1 at pulse 40: it jumps at the pattern's end (72), not at 96", n1 == [] and locs == [12], (n1, locs))
    pulse(10); n1 = list(locs); pulse(11)
    check("  still held: it loops one pattern pass (12 steps, 72 pulses)", n1 == [12] and locs == [12, 12], (n1, locs))
    unpad(uc, 24); pulse(11)
    pad(uc, 23); locs.clear(); setpos(40); pad(uc, 24); unpad(uc, 24)
    first = None
    for i_, p_ in enumerate(list(range(40, 72)) + list(range(0, 72))):
        pulse(p_)
        if locs and first is None:
            first = i_
    check("  2 bars (pad 24) at pulse 40: the jump at the end of the next pass (104 pulses on), not at the first", first == 103 and locs == [12], (first, locs))
    pad(uc, 20); setpos(40); locs.clear(); pad(uc, 24); unpad(uc, 24)
    pulse(46); n1 = list(locs); pulse(47)
    check("  1/4 (pad 21) at pulse 40: the grid from the pattern's start, the jump at 48", n1 == [] and locs == [12], (n1, locs))
    pad(uc, 22)
    # punch-in, stopped
    uc.mem_write(tr, bytes(1)); at(1); out(uc)
    pad(uc, 8); unpad(uc, 8); o = out(uc)
    check("punch-in: a tap on step 9: the scanner there", b8(uc, CR + FREE) == 1)
    btns.clear(); locs.clear(); pad(uc, 8); later(500); unpad(uc, 8)
    check("  a hold on the scanner's step (0.5 s): no punch-in", locs == [] and btns == [] and b8(uc, CR + FREE) == 1, (locs, btns))
    pad(uc, 8); later(100); unpad(uc, 8)
    check("  stopped, a tap on the scanner's step: playback starts there (Shift + Play to the stock), the scanner follows",
          locs and locs[0] == 48 and 17 in btns and b8(uc, CR + FREE) == 0, (locs, btns, b8(uc, CR + FREE)))
    # punch-in, playing, 1 bar
    uc.mem_write(tr, bytes([1])); at(1); out(uc)
    pad(uc, 8); unpad(uc, 8); out(uc); locs.clear()
    setpos(40); pad(uc, 8); later(100); unpad(uc, 8)
    blink = set()
    for _ in range(4):
        later(64); blink.add(out(uc)[8])
    check("  playing, a tap on the scanner's step: waits for the pattern's end; the scanner blinks", locs == [] and b8(uc, CR + PEND) == 1 and 0 in blink and len(blink) == 2,
          (locs, b8(uc, CR + PEND), [hex(x) for x in blink]))
    pulse(70); pulse(71)
    check("  at the end: the jump to step 9, the scanner follows the playhead", locs == [48] and b8(uc, CR + FREE) == 0, (locs, b8(uc, CR + FREE)))
    uc.mem_write(tr, bytes(1))
    scrub_off(uc)


def chase_test():
    """After a jump each track's automation lanes take their last value at or before the new place (the real stock locate)"""
    if not (CUES2 and R["cues"].get("auto")):
        return
    ENG, PL, t, k = 0x2003C380, 0x200470D4, 0, 3
    uc = ET.setup(open(sys.argv[2], "rb").read(), open(sys.argv[3], "rb").read())
    pl = PL + 0x190 * t
    ps = u32(uc, pl + 8)
    pat = b8(uc, ptr(uc, ps, 0)) & 7
    pt = u32(uc, u32(uc, ENGINE + 0x84 + 4 * t) + 4) + PAT_SZ * pat
    uc.mem_write(pt + 0x101, bytes([0])); uc.mem_write(pt + 0x100, bytes([15])); uc.mem_write(pt + 0x103, bytes([0]))
    lane = bytearray([0xFF] * 192); lane[2 * 6] = 0x11; lane[6 * 6] = 0x55
    uc.mem_write(pt + 0x128 + 192 * k, bytes(lane))
    for o, v in ((0x30, 1 << k), (0x34, 0), (0x38, 0)):
        st = u32(uc, pl + o)
        for b in range(2):
            uc.mem_write(u32(uc, st + 0xC + 4 * b), struct.pack("<I", v) if o != 0x38 else bytes([v]))
    tr = ptr(uc, 0x200122B0, 0); uc.mem_write(tr, bytes(1))
    sh = ptr(uc, u32(uc, C.CTRL + 0xC), 0)
    out(uc)
    uc.mem_write(sh, b"\x01"); held(uc, 27, 1); btn(uc, 17); held(uc, 17, 1); out(uc)
    if V3:
        uc.mem_write(HAL_TICK, struct.pack("<I", u32(uc, HAL_TICK) + 600)); out(uc)
    def go(step):
        here = b8(uc, ptr(uc, u32(uc, pl + 8), 1)) & 31
        knob(uc, 0, step - here); out(uc)
        return b8(uc, ptr(uc, u32(uc, pl + 8), 1)) & 31, knob_k(uc, t, k)
    def now(): return b8(uc, ptr(uc, u32(uc, pl + 8), 1)) & 31, knob_k(uc, t, k)
    r9 = go(9); r4 = go(4); r1 = go(1)
    check("stopped, K1 to step 10: K4 takes step 7's automation (85)", r9 == (9, 0x55), r9)
    check("  K1 to step 5: step 3's (17)", r4 == (4, 0x11), r4)
    check("  K1 to step 2, before both: the pattern's last value, as it loops (85)", r1 == (1, 0x55), r1)
    uc.mem_write(pt + 0x103, bytes([1])); knob(uc, 0, -1); knob(uc, 0, 11); out(uc); r = now()
    check("a reverse pattern, song step 12 = its step 5: step 7 is earlier in time (85)", r == (4, 0x55), r)
    uc.mem_write(pt + 0x103, bytes([0]))
    st = u32(uc, pl + 0x34)
    for b in range(2):
        uc.mem_write(u32(uc, st + 0xC + 4 * b), struct.pack("<I", 1 << k))
    knob(uc, 0, -7); out(uc); r = now()
    check("K4 turned by hand: the jump gives its lane back to automation, as the stock's locate does (17)", r == (4, 0x11), r)
    last = u32(uc, pl + 0x4C)
    uc.mem_write(last + 2 * k, struct.pack("<H", 0x11))
    sink = u32(uc, pl + 0x2C); call(uc, u32(uc, u32(uc, sink)), sink, R16ID(uc, pl, k), 0x30)
    knob(uc, 0, 1); knob(uc, 0, -1); out(uc); r = now()
    check("  K4 set by hand to 48 while the stock's last applied value is 17, a jump back: 17 again", r == (4, 0x11), r)
    held(uc, 17, 0); call(uc, C.BTN_RELEASE, C.CTRL, 17); uc.mem_write(sh, bytes(1)); held(uc, 27, 0); call(uc, C.BTN_RELEASE, C.CTRL, 27)
    if V3:
        btn(uc, 27); call(uc, C.BTN_RELEASE, C.CTRL, 27)


def down_test():
    """The stock's own press and release keep each button's down bit; a press or release the scrub keeps must leave it right"""
    if not (CUES2 and R["cues"].get("latch")):
        return
    CR = int(R["cues"]["ram"], 16)
    uc = ET.setup(open(sys.argv[2], "rb").read(), open(sys.argv[3], "rb").read())
    def store(v):
        st = u32(uc, C.CTRL + 0xC)
        for k in range(2):
            uc.mem_write(u32(uc, st + 0xC + 4 * k), bytes([v]))
    def press(i):
        if i == 27: store(1)
        btn(uc, i)
    def rel(i):
        if i == 27: store(0)
        call(uc, C.BTN_RELEASE, C.CTRL, i)
    def later(ms): uc.mem_write(HAL_TICK, struct.pack("<I", u32(uc, HAL_TICK) + ms))
    def down(): return u32(uc, C.CTRL + 0xA0) & (1 << 27 | 1 << 17)
    def bits_only(at, on):                               # the stock's press (test-and-set, then its job) and release (clear), jobs not run
        def f(u, adr, n, d):
            i = u.reg_read(UC_ARM_REG_R1); v = u32(u, C.CTRL + 0xA0)
            u.mem_write(C.CTRL + 0xA0, struct.pack("<I", v | 1 << i if on else v & ~(1 << i)))
            u.reg_write(UC_ARM_REG_R0, 0); u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
        uc.hook_add(UC_HOOK_CODE, f, None, at, at + 1)
    bits_only(PREV["prev_btn"], 1)
    bits_only(PREV["prev_rel"], 0)
    for k in ("prev_knob", "prev_out", "prev_pad", "prev_padrel"):
        uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: (u.reg_write(UC_ARM_REG_R0, 0), u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))),
                    None, PREV[k], PREV[k] + 1)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR)), None, 0x08034082, 0x08034083)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: u.reg_write(UC_ARM_REG_PC, 0x0803FC22 | 1), None, 0x0803FC1C, 0x0803FC1D)
    for k in range(2):
        uc.mem_write(u32(uc, 0x200122B0 + 0xC + 4 * k), bytes(1))
    out(uc)
    press(27); press(17); later(100); rel(17)
    check("Shift + Play tap, not latched: Play not left down", down() == 1 << 27, hex(down()))
    rel(27)
    press(27); press(17); out(uc); later(1100); out(uc); rel(17); out(uc); rel(27); out(uc)
    check("Shift + Play held 1 s, both let go: latched, no button left down for the stock", b8(uc, CR + 44) == 1 and down() == 0, (b8(uc, CR + 44), hex(down())))
    press(17)
    check("  latched, Play alone: not taken as Shift + Play", b8(uc, CR + 45) == 0, b8(uc, CR + 45))
    rel(17); out(uc)
    press(27); later(100); rel(27); out(uc)
    check("  a Shift tap: the latch off, no button left down", b8(uc, CR + 44) == 0 and down() == 0, (b8(uc, CR + 44), hex(down())))
    press(27)
    check("  the next Shift press reaches the stock", down() == 1 << 27, hex(down()))
    rel(27)
    check("  and its release", down() == 0, hex(down()))


def sync_test():
    """A waiting cue jump made in the clock's pulse listener, with the stock's own pulse and locate code"""
    if not (CUES2 and R["cues"].get("sync")):
        return
    ENG = 0x2003C380
    CR = int(R["cues"]["ram"], 16)
    uc = ET.setup(open(sys.argv[2], "rb").read(), open(sys.argv[3], "rb").read())
    def pg(st, i): call(uc, 0x0803FC58, st, i); return uc.reg_read(UC_ARM_REG_R0)
    def pos(): return u32(uc, pg(u32(uc, ENG + 0x90), 0))
    def tpos(t): ps = u32(uc, ENG + 0x30 + 4 * t); return [b8(uc, pg(ps, i)) for i in range(3)]
    uc.mem_write(ptr(uc, 0x200122B0, 0), bytes([1])); out(uc)
    clk = u32(uc, ENG + 0x14); call(uc, u32(uc, u32(uc, clk) + 0x14), clk); ps = uc.reg_read(UC_ARM_REG_R0)
    uc.mem_write(ENG + 0xA8, bytes(4))
    call(uc, 0x08034082, ENG, 41); call(uc, LB["c_gx_enl"], ENG, ps, 0)
    check("the clock plays pulse 41 through the listener, as the stock's", pos() == 41 and tpos(0) == [0, 6, 5], (pos(), tpos(0)))
    uc.mem_write(CR + 16, struct.pack("<I", 30)); uc.mem_write(CR + 20, struct.pack("<I", 1))
    uc.mem_write(CR + 56, struct.pack("<IH", 42, 0)); uc.mem_write(CR + 4, bytes([1]))
    call(uc, LB["c_gx_enl"], ENG, ps, 0)
    check("a cue jump to step 6 waits for pulse 42: that pulse plays step 6's first pulse on every track", pos() == 30
          and all(tpos(t) == [0, 5, 0] for t in range(8)) and b8(uc, CR + 4) == 0, (pos(), tpos(0), tpos(7)))
    call(uc, LB["c_gx_enl"], ENG, ps, 0)
    check("  the next pulse goes on from there", pos() == 31 and tpos(0) == [0, 5, 1], (pos(), tpos(0)))


def scrub_native_preview_test():
    if os.environ["RH_BUILD"] < "a0168":
        return
    uc=ET.setup(open(sys.argv[2],"rb").read(),open(sys.argv[3],"rb").read())
    eng=0x2003C380
    packets=[];owners=[]
    def packet(u,a,n,d):
        packets.append(struct.unpack("<2I",u.mem_read(u.reg_read(UC_ARM_REG_R0),8)))
        u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def owner(u,a,n,d):
        owners.append(u.reg_read(UC_ARM_REG_R1))
    # Keep actual sample selectors, note adapters, dispatcher, choke and wrappers.
    # Only the final DSP queue handoff is replaced by packet capture.
    uc.hook_add(UC_HOOK_CODE,packet,None,0x080406A8,0x080406A9)
    uc.hook_add(UC_HOOK_CODE,owner,None,0x0803B9F8,0x0803B9F9)
    # Avoid cross-task parameter notifications in the static RAM fixture.
    uc.hook_add(UC_HOOK_CODE,lambda u,a,n,d:u.reg_write(UC_ARM_REG_PC,0x0803FC22|1),None,0x0803FC1C,0x0803FC1D)
    native_params=u32(uc,0x080408D4)
    for t in range(8): uc.mem_write(native_params+16*t+1,b"\x01")  # gated notes must receive note-off
    for t in range(8):
        pl=PLAYERS+PL_SZ*t;pat=u32(uc,pl+0x50)
        for step in range(32):
            uc.mem_write(pat+8*step,bytes([60,6,1,100,127,0xFF,0,0]))
        # Exercise the sequencer-only suppression that native preview bypasses.
        seq=u32(uc,pl+0x54);adapter=u32(uc,seq+8);router=u32(uc,adapter+4)
        stride=u32(uc,router+0x1A48);table=u32(uc,router+0x1A50)
        uc.mem_write(ptr(uc,u32(uc,table+stride*t),0),b"\x01")
    uc.mem_write(ptr(uc,eng+0xE4,0),b"\x01")
    for t in range(8):
        ch=ptr(uc,u32(uc,eng+0x9C),t);uc.mem_write(ch,b"\x00\x00\x00\x00")
    uc.mem_write(ptr(uc,u32(uc,eng+0xA0),0),b"\x00\x00")
    uc.mem_write(ptr(uc,C.TRANSPORT,0),b"\x00")
    uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0),b"\x01");scrub_on(uc)
    def ons():return [p for p in packets if p[0]>>20&15==9]
    for name,delta in (("first step",-100),("first step repeated",-1),("last step",100),("last step retrigger right",1),("last step retrigger right again",1)):
        packets.clear();owners.clear();knob(uc,0,delta)
        check(f"native preview {name}: eight real DSP note-on packets, preview ownership",len(ons())==8 and owners==[0]*8,(ons(),owners))
        check(f"  {name}: transport remains stopped",b8(uc,ptr(uc,C.TRANSPORT,0))==0)
    if os.environ["RH_BUILD"] >= "a0171":
        knob(uc,0,-1)  # move inside the chain before setting up running playback
        uc.mem_write(ptr(uc,C.TRANSPORT,0),b"\x01")
        packets.clear();owners.clear();knob(uc,0,-100)
        check("running to first step: stop then eight real preview note-on packets",b8(uc,ptr(uc,C.TRANSPORT,0))==0 and len(ons())==8 and owners==[0]*8,(ons(),owners))
        packets.clear();owners.clear();knob(uc,0,-1)
        check("held beginning: left retriggers first step without starting transport",b8(uc,ptr(uc,C.TRANSPORT,0))==0 and len(ons())==8 and owners==[0]*8,(ons(),owners))
        packets.clear();owners.clear();knob(uc,0,1)
        check("held beginning: right resumes playback without duplicate preview",b8(uc,ptr(uc,C.TRANSPORT,0))==1 and owners!=[0]*8,(b8(uc,ptr(uc,C.TRANSPORT,0)),owners,ons()))
    # Enter the held end from running playback too: real stop and real locate.
    packets.clear();owners.clear();uc.mem_write(ptr(uc,C.TRANSPORT,0),b"\x01")
    uc.mem_write(ptr(uc,u32(uc,eng+0x90),0),struct.pack("<I",84));knob(uc,0,1)
    check("running to last step: stop then eight real preview note-on packets",b8(uc,ptr(uc,C.TRANSPORT,0))==0 and len(ons())==8 and owners==[0]*8,(ons(),owners))
    packets.clear();scrub_off(uc)
    check("native preview release: real DSP note-off packets",len([p for p in packets if p[0]>>20&15==8])>=8,packets)


def step_mutate_fx_test():
    """Run the real Shift+Duplicate path with both native and packed step data."""
    import emu_stepmut as SM
    uc = ET.setup(open(sys.argv[2], "rb").read(), open(sys.argv[3], "rb").read())
    t = 2
    view(uc, CONT); uc.mem_write(CONT + 0x264, b"\x09"); SM.sel(uc, t)
    held(uc, BIT_CLEAR, True); pad(uc, 7); unpad(uc, 7); held(uc, BIT_CLEAR, False)
    pad(uc, 7); unpad(uc, 7)
    uc.mem_write(CONT + 0x264, b"\x00")
    check("Step Mutate fixture: FX track enabled", b8(uc, blk(uc) + 12) == t)
    pn = b8(uc, ptr(uc, u32(uc, SM.obj(uc, t) + 0x28), 0)) & 7
    def run(rec):
        SM.set_rec(uc, t, rec); SM.tap(uc, t)
    # A full dictionary: movement must transfer raw codes, never reallocate sets.
    model = {((pn + 1 + k // 32) % 8, k % 32): 1 << 16 | k << 1 for k in range(45)}
    model.update({(pn, 0): 1 << 3, (pn, 7): (1 << 5) | (1 << 9) | (3 << 16),
                  (pn, 16): 1 << 9, (pn, 31): (1 << 4) | (1 << 8)})
    p = SM.fill(uc, t, end=31, empty=(2, 5, 19))
    pats = u32(uc, SM.obj(uc, t) + 4)
    for (n, st) in model:
        if n != pn:
            uc.mem_write(pats + PAT_SZ * n + 8 * st + 2, b"\x01\x60")
    pk_encode(uc, t, model)
    before = SM.steps(uc, p)
    lane_before = {before[i][3]: SM.lanes(uc, p, i) for i in range(32)}
    run(SM.only(SM.MOVE))
    after = SM.steps(uc, p)
    check("FX Step Mutate moves steps across both pages", before != after and sorted(before) == sorted(after))
    check("FX Step Mutate carries every combination and random/repeat with its step",
          all(pk_read(uc, pn, i) == model.get((pn, after[i][3] - 10), 0) for i in range(32)),
          [(i, after[i][3] - 10, pk_read(uc, pn, i), model.get((pn, after[i][3] - 10), 0)) for i in range(32) if pk_read(uc, pn, i) != model.get((pn, after[i][3] - 10), 0)])
    check("FX Step Mutate still carries automation", all(SM.lanes(uc, p, i) == lane_before[after[i][3]] for i in range(32)))
    check("FX Step Mutate leaves other patterns intact at full dictionary capacity",
          all(pk_read(uc, n, i) == v for (n, i), v in model.items() if n != pn))
    out(uc)  # the deletion sweep must not erase assignments after the move
    check("FX assignments survive the next LED/sweep frame",
          all(pk_read(uc, pn, i) == model.get((pn, after[i][3] - 10), 0) for i in range(32)),
          [(i, after[i][3] - 10, pk_read(uc, pn, i), model.get((pn, after[i][3] - 10), 0)) for i in range(32) if pk_read(uc, pn, i) != model.get((pn, after[i][3] - 10), 0)])
    # Explicit sample-flip mutation: classify pink by FX assignments, not st[5].
    p = SM.fill(uc, t, end=31)
    uc.mem_write(p + 8 * 1 + 5, b"\x06")   # native sample flip, but a blue FX step
    model = {(pn, 0): 1 << 1, (pn, 16): (1 << 2) | (1 << 5) | (3 << 16), (pn, 31): 1 << 3}
    pk_encode(uc, t, model)
    uc.mem_write(TBL, bytes([0xFF]) * (7 * 16))
    for k in range(7):
        uc.mem_write(TBL + 7 * k, bytes([k, 0x33, 0, 0, 0, 0, 0]))
    run(SM.only(SM.SAMPLE, sample=0))  # All, Any, Pink only
    changed = {i: pk_read(uc, pn, i) for i in (0, 16, 31)}
    check("FX pink-only mutation changes assigned pads on both pages",
          all(changed[i] != model[pn, i] and changed[i] & 0xFFFF for i in changed), changed)
    check("FX sample mutation preserves random/repeat flags", changed[16] & (3 << 16) == 3 << 16)
    check("FX pink-only skips blue steps even with native sample flips",
          all(pk_read(uc, pn, i) == 0 for i in range(32) if i not in changed))
    check("FX sample mutation does not write sample flips", b8(uc, p + 8 + 5) == 6 and b8(uc, p + 5) == 0xFF)
    run(SM.only(SM.SAMPLE, sample=16))  # All steps
    check("FX all-steps sample mutation assigns Grid FX to blue steps",
          all(pk_read(uc, pn, i) & 0xFFFF for i in range(32)))
    prior = [pk_read(uc, pn, i) for i in range(32)]
    run(SM.only(SM.GATE, SM.VEL, SM.MICRO, SM.PROB))
    check("FX gate/velocity/microstep/probability mutations retain all FX",
          prior == [pk_read(uc, pn, i) for i in range(32)])
    uc.mem_write(TBL, bytes([0xFF]) * (7 * 16))
    run(SM.only(SM.SAMPLE, sample=0))
    check("FX mutation without valid replacement pads preserves assignments",
          prior == [pk_read(uc, pn, i) for i in range(32)])


def shift_controls_test():
    import emu_stepmut as SM
    uc = ET.setup(open(sys.argv[2], "rb").read(), open(sys.argv[3], "rb").read())
    t = 2
    view(uc, CONT); uc.mem_write(CONT + 0x264, b"\x09"); SM.sel(uc,t)
    held(uc,BIT_CLEAR,True); pad(uc,7); unpad(uc,7); held(uc,BIT_CLEAR,False); pad(uc,7); unpad(uc,7)
    uc.mem_write(CONT + 0x264,b"\x00")
    def native(k):
        call(uc,GETTER,0x10+t,(0x12,0x13,0x10)[k]); return uc.reg_read(UC_ARM_REG_R0)&127
    def get(k):
        return b8(uc,blk(uc)+23+k)&127
    original = [native(k) for k in range(3)]
    shift_ptr = ptr(uc,u32(uc,C.CTRL+0xC),0)
    def shift(on): uc.mem_write(shift_ptr,bytes([on])); held(uc,27,on)
    def turn(k,d): call(uc,LB["c_gx_tknob"],C.CTRL,k,d&0xFFFFFFFF)
    full = 141 if u32(uc,ptr(uc,u32(uc,C.CTRL+0x88),2))>>10&1 else 255
    shift(1); out(uc)
    check("Shift FX controls default to the original full routing",[get(k) for k in range(3)]==[127]*3)
    old_sends = [knob_k(uc,t,k) for k in range(8)]
    turn(0,-50); turn(1,-80); turn(2,-20)
    check("Shift K1-K3 change isolated saved values, preserving eight sends",[get(k) for k in range(3)]==[77,47,107]
          and [knob_k(uc,t,k) for k in range(8)]==old_sends,[get(k) for k in range(3)])
    o=out(uc)
    check("Shift K1/K2 match native reverb/delay colors and value brightness",
          o[60]==scl(palc(uc,0x141),(LVL_ZERO+77*(255-LVL_ZERO)//127)*full>>8)
          and o[61]==scl(palc(uc,0x139),(LVL_ZERO+47*(255-LVL_ZERO)//127)*full>>8))
    for k in range(4,8): turn(k,20)
    check("Shift K5-K8 reserved: dark and no send changes",list(o[64:68])==[0]*4
          and [knob_k(uc,t,k) for k in range(8)]==old_sends)
    shift(0); plain=out(uc); held(uc,BIT_CLEAR,True); clear=out(uc)
    check("holding Clear retains FX send colors",list(plain[60:68])==list(clear[60:68]))
    held(uc,BIT_CLEAR,False); shift(1)
    # Record native automation from mixer page 3, then run the actual player.
    view(uc,MIX); uc.mem_write(page_p(uc),b"\x01"); btn(uc,ID_DOWN)
    ko=u32(uc,CONT+0x1C4+4*t); rec=SM.obj(uc,t); pn=b8(uc,ptr(uc,u32(uc,rec+0x28),0))&7
    pat=u32(uc,rec+4)+PAT_SZ*pn
    uc.mem_write(pat+0x128,bytes([255])*(12*0xC0))
    uc.mem_write(ptr(uc,u32(uc,rec+0x28),1),b"\x07")
    uc.mem_write(ptr(uc,u32(uc,ko+0x2C),0),b"\x01")
    for k in range(3): knob(uc,k,-1)
    lanes = [bytes(uc.mem_read(pat+0x128+k*0xC0,0xC0)) for k in range(12)]
    check("Shift controls never record into any native automation lane",all(all(v==255 for v in lane) for lane in lanes))
    check("Shift controls leave native reverb/delay/mixer parameters unchanged",[native(k) for k in range(3)]==original)
    recorded=[get(k) for k in range(3)]
    uc.mem_write(ptr(uc,u32(uc,ko+0x2C),0),b"\x00")
    pl=PLAYERS+PL_SZ*t
    uc.mem_write(ptr(uc,u32(uc,pl+0x34),0),bytes(4))
    uc.mem_write(u32(uc,pl+0x4C),bytes([255])*24)
    for k in range(3):
        uc.mem_write(pat+0x128+(8+k)*0xC0+7*6,bytes([10+10*k]))
    stock_before=bytes(uc.mem_read(pat+0x128,12*0xC0))
    call(uc,0x08055324,pl,pn,7,0)
    check("native automation cannot change the separate Shift control values",[get(k) for k in range(3)]==recorded)
    check("native reverb/delay/level automation still plays independently",[native(k) for k in range(3)]==[10,20,30])
    # Clear requires 40 clicks, with left minimum and right default.
    held(uc,BIT_CLEAR,True); knob(uc,0,-39)
    check("Shift Clear does not reset before the native threshold",get(0)==recorded[0])
    knob(uc,0,-1); check("Shift Clear left reaches minimum",get(0)==0)
    o=out(uc); check("Shift Clear left uses native red completion cue",o[60]==scl(palc(uc,0x55),full))
    knob(uc,0,40); check("Shift Clear right restores full default",get(0)==127)
    cleared=bytes(uc.mem_read(pat+0x128+8*0xC0,0xC0))
    check("Shift Clear preserves all native automation byte-for-byte",bytes(uc.mem_read(pat+0x128,12*0xC0))==stock_before)
    held(uc,BIT_CLEAR,False); call(uc,C.BTN_RELEASE,C.CTRL,BIT_CLEAR)
    # Audition affects sequencer pads only; the live Grid FX view still plays.
    view(uc,CONT); uc.mem_write(CONT+0x264,b"\x00")
    events=[]
    def event(u,a,n,d):
        events.append((u.reg_read(UC_ARM_REG_R1),u.reg_read(UC_ARM_REG_R2)))
        u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE,event,None,GSET,GSET+1)
    uc.mem_write(TBL+7*5,bytes([1,0x33,0,0,0,0,0]))
    turn(3,-1); shift(0); events.clear(); pad(uc,21); unpad(uc,21)
    check("audition off: sequencer pad selects silently",not events,events)
    vt=u32(uc,MIX+0x15C); call(uc,u32(uc,vt),MIX+0x15C,5,100)
    check("audition off still permits live performance on Grid FX page",bool(events),events)
    call(uc,u32(uc,vt+4),MIX+0x15C,5)
    shift(1); turn(3,1); shift(0); events.clear(); pad(uc,21); unpad(uc,21)
    check("audition on: sequencer pad sounds again",bool(events),events)
    # Original native parameters are restored on leaving FX-track mode.
    uc.mem_write(CONT+0x264,b"\x09"); pad(uc,7); unpad(uc,7)
    check("disabling FX track does not restore or overwrite native automated parameters",[native(k) for k in range(3)]==[10,20,30])


def control_page_test():
    """page 2 of the FX track's knobs: K1-K3 the returns and blend, pads 17-24 their lanes, pad 25 the control, pad 32 audition"""
    import emu_stepmut as SM
    uc = ET.setup(open(sys.argv[2], "rb").read(), open(sys.argv[3], "rb").read())
    t = 2
    view(uc, CONT); uc.mem_write(CONT + 0x264, b"\x09"); SM.sel(uc, t)
    held(uc, BIT_CLEAR, True); pad(uc, 7); unpad(uc, 7); held(uc, BIT_CLEAR, False); pad(uc, 7); unpad(uc, 7)
    uc.mem_write(CONT + 0x264, b"\x00")
    full = 141 if u32(uc, ptr(uc, u32(uc, C.CTRL + 0x88), 2)) >> 10 & 1 else 255
    lvl = lambda v: (LVL_ZERO + v * (255 - LVL_ZERO) // FULL) * full >> 8          # noqa: E731
    colors = (palc(uc, 0x141), palc(uc, 0x139), GX_RGB)
    def get(k): return b8(uc, blk(uc) + 23 + k) & 127
    def audition_off(): return b8(uc, blk(uc) + 23) >> 7
    def lane(c):
        v = sum((b8(uc, blk(uc) + (4 + 4 * c if c < 2 else 13) + i) >> 7 & 1) << i for i in range(4))
        return v - 1 if v else None
    def stored(k): return b8(uc, blk(uc) + 4 + k) & 127
    def turn(k, d): call(uc, LB["c_gx_tknob"], C.CTRL, k, d & 0xFFFFFFFF)
    def tap(p): pad(uc, p); unpad(uc, p)
    stock_pads = []
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: stock_pads.append(u.reg_read(UC_ARM_REG_R1)), None, PREV["prev_pad"], PREV["prev_pad"] + 1)
    o = out(uc)
    check("page 1: Down dim white (page 2 below), Up dark",
          o[LED_DOWN] == scl(WHITE, 40 * full >> 8) and o[LED_UP] == 0, (hex(o[LED_DOWN]), hex(o[LED_UP])))
    g1 = list(o[16:32])
    shift_ptr = ptr(uc, u32(uc, C.CTRL + 0xC), 0)
    uc.mem_write(shift_ptr, b"\x01"); held(uc, 27, True)
    sends0 = [knob_k(uc, t, k) for k in range(8)]
    turn(0, -5)
    uc.mem_write(shift_ptr, b"\x00"); held(uc, 27, False)
    check("Shift does nothing: K1 on page 1 is still track 1's send", get(0) == 127 and knob_k(uc, t, 0) != sends0[0])
    turn(0, 5)
    btn(uc, ID_DOWN); o = out(uc)
    check("Down: page 2; Down lit amber, Up dim white", o[LED_DOWN] == scl(GX_RGB, full) and o[LED_UP] == scl(WHITE, 40 * full >> 8))
    check("page 2: pads 17-24 dim white (no lane taken), pad 25 the reverb return's green, pad 32 green (audition on), 26-31 dark",
          list(o[16:24]) == [scl(WHITE, 48 * full >> 8)] * 8 and o[24] == scl(colors[0], full) and o[31] == scl(0x00FF00, full)
          and list(o[25:31]) == [0] * 6, [hex(x) for x in o[16:32]])
    check("page 2: K1-K3 at full in their colours, K4-K8 dark",
          [o[LED_KNOB0 + k] for k in range(3)] == [scl(colors[k], lvl(127)) for k in range(3)] and list(o[LED_KNOB0 + 3:LED_KNOB0 + 8]) == [0] * 5)
    sends1 = [knob_k(uc, t, k) for k in range(8)]
    turn(0, -50); turn(1, -80); turn(2, -20); turn(3, -5); turn(5, 9)
    check("page 2: K1-K3 set the returns and blend; K4-K8 do nothing; the sends stay",
          [get(k) for k in range(3)] == [77, 47, 107] and not audition_off() and [knob_k(uc, t, k) for k in range(8)] == sends1,
          [get(k) for k in range(3)])
    stock_pads.clear(); pad(uc, 16)
    check("pad 17 takes track 1's lane for the reverb return; the stock never sees the pad", lane(0) == 0 and not stock_pads, (lane(0), stock_pads))
    pad(uc, 16); unpad(uc, 16)
    check("a second down report of the same press does nothing", lane(0) == 0)
    check("the lane keeps the control's value; track 1's send is kept in the project",
          abs(knob_send(0, knob_k(uc, t, 0)) - 77) <= 1 and stored(0) == knob_send(0, sends1[0]), (knob_k(uc, t, 0), stored(0), sends1[0]))
    o = out(uc)
    check("pad 17 bright green: the chosen control's lane", o[16] == scl(colors[0], full), hex(o[16]))
    k0 = knob_k(uc, t, 0); turn(0, 10)
    check("K1 on its lane: it turns the lane, the saved value stays", knob_k(uc, t, 0) == k0 + 10 and get(0) == 77, (knob_k(uc, t, 0), get(0)))
    ko = u32(uc, CONT + 0x1C4 + 4 * t); rec = SM.obj(uc, t); pn = b8(uc, ptr(uc, u32(uc, rec + 0x28), 0)) & 7
    pat = u32(uc, rec + 4) + PAT_SZ * pn
    uc.mem_write(pat + 0x128, bytes([255]) * (12 * 0xC0))
    uc.mem_write(ptr(uc, u32(uc, rec + 0x28), 1), b"\x07")
    uc.mem_write(ptr(uc, u32(uc, ko + 0x2C), 0), b"\x01")
    turn(0, -3)
    lanes = [bytes(uc.mem_read(pat + 0x128 + k * 0xC0, 0xC0)) for k in range(12)]
    check("Record + K1: the movement is recorded in track 1's lane, no other lane",
          any(v != 255 for v in lanes[0]) and all(all(v == 255 for v in x) for x in lanes[1:]))
    turn(1, -3)
    check("Record + K2 (no lane): nothing is recorded", bytes(uc.mem_read(pat + 0x128, 12 * 0xC0)) == b"".join(lanes))
    uc.mem_write(ptr(uc, u32(uc, ko + 0x2C), 0), b"\x00")
    pl = PLAYERS + PL_SZ * t
    uc.mem_write(ptr(uc, u32(uc, pl + 0x34), 0), bytes(4))
    uc.mem_write(u32(uc, pl + 0x4C), bytes([255]) * 24)
    uc.mem_write(pat + 0x128, bytes([255]) * (12 * 0xC0))
    uc.mem_write(pat + 0x128 + 7 * 6, bytes([64]))
    call(uc, 0x08055324, pl, pn, 7, 0)
    o = out(uc)
    check("playback of track 1's lane moves the reverb return (K1's light)", knob_k(uc, t, 0) == 64 and o[LED_KNOB0] == scl(colors[0], lvl(knob_send(0, 64))),
          (knob_k(uc, t, 0), hex(o[LED_KNOB0])))
    btn(uc, ID_UP); o = out(uc)
    check("Up: page 1, the Grid FX pads again", list(o[16:32]) == g1 and o[LED_UP] == 0)
    check("page 1: K1 shows track 1's kept send, not its lane", o[LED_KNOB0] == scl(GX_RGB, lvl(stored(0))), (hex(o[LED_KNOB0]), stored(0)))
    before = stored(0); turn(0, -4)
    check("page 1: K1 turns track 1's kept send; the lane does not move", stored(0) == before - 4 and knob_k(uc, t, 0) == 64 and lane(0) == 0)
    btn(uc, ID_DOWN); tap(24); o = out(uc)
    check("pad 25: the next control, the delay return (pink); pad 17 dim green, the other control's", o[24] == scl(colors[1], full)
          and o[16] == scl(colors[0], 48 * full >> 8), (hex(o[24]), hex(o[16])))
    tap(16)
    check("pad 17 for the delay return: it takes the lane from the reverb return, which keeps the lane's last value",
          lane(1) == 0 and lane(0) is None and get(0) == knob_send(0, 64) and abs(knob_send(0, knob_k(uc, t, 0)) - get(1)) <= 1, (lane(0), lane(1), get(0)))
    tap(16)
    check("pad 17 again: no lane; track 1's send is back on its knob", lane(1) is None and knob_send(0, knob_k(uc, t, 0)) == stored(0),
          (knob_k(uc, t, 0), stored(0)))
    tap(24); tap(18)
    check("pad 25 again: the blend; pad 19 gives it track 3's lane", lane(2) == 2 and lane(0) is None and lane(1) is None)
    tap(31); o = out(uc)
    check("pad 32: audition off, red", audition_off() == 1 and o[31] == scl(0xFF0000, full))
    pad(uc, 31); pad(uc, 31); unpad(uc, 31)
    check("pad 32 again: audition on (one change a press)", audition_off() == 0)
    check("the sends of the other tracks are not changed", [knob_k(uc, t, k) for k in (1, 3, 4, 5, 6, 7)] == [sends1[k] for k in (1, 3, 4, 5, 6, 7)])
    if R.get("mixer_shift"):
        view(uc, MIX); uc.mem_write(page_p(uc), b"\x01"); btn(uc, ID_DOWN)
        uc.mem_write(shift_ptr, b"\x01"); held(uc, 27, True)
        before = [knob_k(uc, t, k) for k in range(8)]; r0 = get(0)
        knob(uc, 0, -7); knob(uc, 2, -5); knob(uc, 4, 6)
        o = out(uc)
        check("sends page, Shift + K1: the reverb return; the sends stay", get(0) == r0 - 7 and knob_k(uc, t, 0) == before[0]
              and knob_k(uc, t, 4) == before[4], (get(0), r0))
        check("sends page, Shift + K3: the blend on its lane", knob_k(uc, t, 2) == before[2] - 5)
        check("sends page, Shift: K1-K3 in their colours, K4-K8 dark", o[LED_KNOB0] == scl(colors[0], lvl(get(0)))
              and list(o[LED_KNOB0 + 3:LED_KNOB0 + 8]) == [0] * 5, [hex(x) for x in o[LED_KNOB0:LED_KNOB0 + 8]])
        uc.mem_write(shift_ptr, b"\x00"); held(uc, 27, False)
        knob(uc, 1, -3)
        check("sends page without Shift: K2 is track 2's send", knob_k(uc, t, 1) == before[1] - 3)
        knob(uc, 1, 3)
    blend = knob_send(2, knob_k(uc, t, 2))
    view(uc, MIX); out(uc); view(uc, CONT); o = out(uc)
    check("away from the FX view and back: page 1", list(o[16:32]) == g1)
    uc.mem_write(CONT + 0x264, b"\x09"); tap(7)
    check("FX track off: the blend keeps its lane value, the lane choice is kept", b8(uc, blk(uc) + 12) == 0xFF and get(2) == blend and lane(2) == 2,
          (get(2), blend, lane(2)))
    if R.get("mixer_shift"):
        view(uc, MIX); uc.mem_write(page_p(uc), b"\x01"); btn(uc, ID_DOWN)
        uc.mem_write(shift_ptr, b"\x01"); held(uc, 27, True)
        knob(uc, 2, -4); o = out(uc)
        uc.mem_write(shift_ptr, b"\x00"); held(uc, 27, False)
        check("no FX track: Shift + K3 on the sends page sets the blend itself", get(2) == blend - 4 and lane(2) == 2
              and o[LED_KNOB0 + 2] == scl(colors[2], lvl(blend - 4)), (get(2), blend))
        blend -= 4
        view(uc, CONT); uc.mem_write(CONT + 0x264, b"\x09")
    tap(7); uc.mem_write(CONT + 0x264, b"\x00")
    check("FX track on again: track 3's lane holds the blend", b8(uc, blk(uc) + 12) == t and knob_send(2, knob_k(uc, t, 2)) == blend)
    if "c_gx_autodefaults" in LB:
        call(uc, LB["c_gx_autodefaults"])
        check("track reset on the FX track: no lanes taken, the three at full",
              [lane(c) for c in range(3)] == [None] * 3 and [get(k) for k in range(3)] == [127] * 3)


def recording_feedback_test():
    if 'c_gx_autored' not in LB:return
    import emu_stepmut as SM
    uc=ET.setup(open(sys.argv[2],'rb').read(),open(sys.argv[3],'rb').read());t=2
    view(uc,CONT);uc.mem_write(CONT+0x264,b'\x09');SM.sel(uc,t)
    held(uc,BIT_CLEAR,True);pad(uc,7);unpad(uc,7);held(uc,BIT_CLEAR,False);pad(uc,7);unpad(uc,7)
    uc.mem_write(CONT+0x264,b'\0')
    ko=u32(uc,CONT+0x1c4+4*t)
    def setp(st,i,v):uc.mem_write(ptr(uc,st,i),bytes([v]))
    setp(C.TRANSPORT,0,0);setp(C.TRANSPORT,1,1);setp(u32(uc,ko+0x2c),0,1)
    full=141 if u32(uc,ptr(uc,u32(uc,C.CTRL+0x88),2))>>10&1 else 255
    for k in range(8):knob(uc,k,-1)
    o=out(uc)
    want=[scl(palc(uc,0x55),(LVL_ZERO+knob_send(k,knob_k(uc,t,k))*(255-LVL_ZERO)//127)*full>>8) for k in range(8)]
    check('FX sends: all eight knobs use native red recording feedback at their value brightness',list(o[60:68])==want,
          ([hex(v) for v in o[60:68]],[hex(v) for v in want]))
    # The same native mask is used on Mixer send page 3.
    view(uc,MIX);uc.mem_write(page_p(uc),b'\x01');btn(uc,ID_DOWN)
    check('Mixer Grid FX send page uses the same eight recording indicators',list(out(uc)[60:68])==want)
    setp(C.TRANSPORT,1,0);setp(u32(uc,ko+0x2c),0,0)
    plain=out(uc)
    check('disarming Record restores ordinary FX send hues',list(plain[60:68])!=want)
    for a,v in ((0xe000ef90,0x73),(0xe000ed08,0x08010000),(0xe000ed94,0),(0xe000ed14,0)):
        uc.mem_write(a,struct.pack('<I',v))
    storage=ET.MAN['report']['storageshadow']
    call(uc,int(storage['labels']['c_sh_block'],16))
    uc.mem_write(int(storage['slot'],16)+22*4,struct.pack('<I',8))
    shift=ptr(uc,u32(uc,C.CTRL+0xc),0);uc.mem_write(shift,b'\x01');held(uc,27,True)
    setp(C.TRANSPORT,1,1)
    pre=[knob_k(uc,t,k) for k in range(3)]
    for k in range(3):knob(uc,k,-10)
    o=out(uc);b=blk(uc)
    want=[scl(palc(uc,0x55),(LVL_ZERO+(b8(uc,b+23+k)&127)*(255-LVL_ZERO)//127)*full>>8) for k in range(3)]
    noa3='automation3' not in ET.MAN['report']
    if R.get('control_page') and not R.get('mixer_shift'):check('no Shift page: Shift + K1-K3 on the sends page turn the sends of tracks 1-3',
                  all(knob_k(uc,t,k)<pre[k] for k in range(3)),(pre,[knob_k(uc,t,k) for k in range(3)]))
    elif noa3:check('Shift K1-K3 keep their own colours with Record armed: they record nothing; K5-K8 remain dark',
                  all(o[60+k]!=want[k] for k in range(3)) and list(o[64:68])==[0]*4)
    else:check('Shift K1-K3 turn red with Record armed; K5-K8 remain dark',list(o[60:63])==want and list(o[64:68])==[0]*4)
    setp(C.TRANSPORT,1,0)
    if not R.get('control_page') or R.get('mixer_shift'):check('Shift recording feedback clears when Record is disarmed',list(out(uc)[60:63])!=want)
    rec=SM.obj(uc,t);so=u32(uc,CONT+0x74+4*t)
    setp(u32(uc,so+T.HELDSTEP),1,17)
    uc.mem_write(so+T.PADS_DOWN,struct.pack('<I',1<<17));setp(C.TRANSPORT,1,1)
    knob(uc,0,-10)
    pn=b8(uc,ptr(uc,u32(uc,rec+0x28),0))&7
    if not noa3:
        import automation_bank_helpers as BH
        own=BH.read(uc,ET.MAN['report'],pn*192+17*6,1)[0]
        uc.mem_write(int(ET.MAN['report']['automation3']['state'],16)+36,struct.pack('<H',64))
        expected=scl(palc(uc,0x55),(LVL_ZERO+own*(255-LVL_ZERO)//127)*full>>8)
        check('held private lock LED shows its own value in red while playback value changes',out(uc)[60]==expected)
    uc.mem_write(shift,b'\0');held(uc,27,False)
    setp(u32(uc,ko+0x2c),0,1)
    knob(uc,1,-1)
    own=b8(uc,u32(uc,rec+4)+pn*PAT_SZ+0x128+192+17*6)
    call(uc,0x08031a38,0x20010e10,0x10+t,7,13)
    expected=scl(palc(uc,0x55),(LVL_ZERO+own*(255-LVL_ZERO)//127)*full>>8)
    actual=out(uc)[61]
    check('held send lock LED shows its own value in red instead of the changing live value',actual==expected,(own,hex(actual),hex(expected)))


def main():
    fw = open(sys.argv[2], "rb").read()
    ram = open(sys.argv[3], "rb").read()
    uc = ET.setup(fw, ram)
    got, wr = [], []

    def take(u, a, n, d):                                 # the next handler: noted, returns at once
        # Model the native controller's accepted-pad state even when this
        # older isolated test replaces its note/programming implementation.
        # FX now observes this same native state before its own side effects.
        if a in (PREV['prev_pad'],PREV['prev_padrel']):
            p=u.reg_read(UC_ARM_REG_R1)
            if p<32:
                mask=u32(u,C.CTRL+0x9c)
                mask=mask|(1<<p) if a==PREV['prev_pad'] else mask&~(1<<p)
                u.mem_write(C.CTRL+0x9c,struct.pack('<I',mask))
        got.append(a); u.reg_write(UC_ARM_REG_R0, 0); u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
    takes = {k: uc.hook_add(UC_HOOK_CODE, take, None, PREV[k], PREV[k] + 1)
             for k in ("prev_btn", "prev_knob", "prev_out", "prev_pad", "prev_padrel")}

    def wr16(u, a, n, d):
        if CUT <= u.reg_read(UC_ARM_REG_R2) < CUT + 8:
            wr.append((u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_R1), u.reg_read(UC_ARM_REG_R2)))
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE, wr16, None, WR16, WR16 + 1)

    def ready_byte():                                     # dspready's mode 0 upload, the upload itself skipped: the byte it sets
        import cthresh
        h = uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR)), None,
                        cthresh.UPLOAD, cthresh.UPLOAD + 1)
        base = int(ET.MAN["report"]["cthresh"]["slot"], 16) - 4
        before = bytes(uc.mem_read(base, 16))
        call(uc, DRUP0, 0)
        uc.hook_del(h)
        after = bytes(uc.mem_read(base, 16))
        hit = [base + i for i in range(16) if before[i] != after[i] and after[i] == 0xA0]
        check("dspready's upload sets one READY byte", len(hit) == 1, [hex(a) for a in hit])
        return hit[0] if hit else int(ET.MAN["report"]["cthresh"]["slot"], 16) + 1
    READY_AT = ready_byte()
    uc.mem_write(READY_AT, b"\x00")
    low = []
    uc.hook_add(UC_HOOK_MEM_READ, lambda u, acc, a, sz, v, d: low.append(a) if a < 0x08000000 else None)

    view(uc, MIX)
    uc.mem_write(page_p(uc), b"\x00")
    got.clear(); btn(uc, ID_DOWN)
    check("levels page: Down goes on to the stock", got == [PREV["prev_btn"]] and b8(uc, SLOT) == 0)
    uc.mem_write(page_p(uc), b"\x01")
    o = out(uc)
    check("pans page: Down lit as Up (it leads on to the sends)", o[LED_DOWN] == 0x111111)
    got.clear(); btn(uc, ID_DOWN)
    check("pans page: Down = the sends page, the stock not called", not got and b8(uc, SLOT) == 1)
    o = out(uc)
    check("sends page: a fresh project's sends all full, the knob lights full in GX_RGB, Down dark",
          sends(uc) != [FULL] * 8 or all(o[LED_KNOB0 + k] in (scl(GX_RGB, 255), scl(GX_RGB, 141)) for k in range(8)) and o[LED_DOWN] == 0,
          [hex(o[LED_KNOB0 + k]) for k in range(8)])
    got.clear(); knob(uc, 0, -127); knob(uc, 3, -27)
    s = sends(uc)
    check("sends page: K1 to 0, K4 down 27, in the project's block; the stock's knob not called",
          s[0] == 0 and s[3] == 100 and s[1] == FULL and PREV["prev_knob"] not in got, s)
    knob(uc, 3, 50)
    check("a send stops at 127", sends(uc)[3] == FULL)
    held(uc, BIT_CLEAR, True); knob(uc, 0, 1); held(uc, BIT_CLEAR, False)
    check("Clear + knob = full", sends(uc)[0] == FULL)
    knob(uc, 0, -127); knob(uc, 5, -64)
    o = out(uc)
    full = 255 if o[LED_KNOB0 + 1] == scl(GX_RGB, 255) else 141
    lv = lambda v: (LVL_ZERO + v * (255 - LVL_ZERO) // FULL) * full >> 8
    check("knob lights by the send", [o[LED_KNOB0 + k] for k in range(8)] == [scl(GX_RGB, lv(v)) for v in sends(uc)],
          ([hex(o[LED_KNOB0 + k]) for k in range(8)], sends(uc)))
    got.clear(); btn(uc, ID_DOWN)
    check("sends page: Down does nothing more", not got and b8(uc, SLOT) == 1)
    btn(uc, ID_UP)
    check("sends page: Up = back to the pans (the stock's page kept)", not got and b8(uc, SLOT) == 0 and b8(uc, page_p(uc)) == 1)
    got.clear(); knob(uc, 2, 5)
    check("pans page: the knob is the stock's", PREV["prev_knob"] in got)
    btn(uc, ID_DOWN); view(uc, CONT); out(uc)
    check("off the Mixer: the sends page closes", b8(uc, SLOT) == 0)
    view(uc, MIX)
    was = bytes(uc.mem_read(mode_p(uc), 1)), bytes(uc.mem_read(fxpage_p(uc), 1))
    uc.mem_write(mode_p(uc), b"\x07"); uc.mem_write(fxpage_p(uc), b"\x00")
    got.clear(); btn(uc, ID_DOWN)
    check("Grid FX on an effect page (pans store still 1): Down goes on to the stock", got == [PREV["prev_btn"]] and b8(uc, SLOT) == 0)
    uc.mem_write(fxpage_p(uc), b"\xff")
    got.clear(); btn(uc, ID_DOWN)
    check("Grid FX on the pans: Down = the sends page", not got and b8(uc, SLOT) == 1)
    uc.mem_write(fxpage_p(uc), b"\x00")                  # an effect held: the stock's page = its settings
    fx = [0, 0x102030, 0x204060, 0x0A0A0A, 0, 0, 0, 0]
    o = out(uc, up=0, knobs=fx)
    full = 141 if u32(uc, ptr(uc, u32(uc, C.CTRL + 0x88), 2)) >> 10 & 1 else 255
    want_up = sum(((0x204060 >> s & 0xFF) * full // 0x60) << s for s in (0, 8, 16))
    check("sends page, an effect held: Up lit in the effect's colour (the brightest of the stock's knob lights, at full)",
          o[LED_UP] == want_up, (hex(o[LED_UP]), hex(want_up)))
    got.clear(); btn(uc, ID_UP)
    check("sends page, an effect held: Up = its settings", not got and b8(uc, SLOT) == 2)
    o = out(uc)
    check("its settings after that Up: Down lit amber", o[LED_DOWN] == scl(GX_RGB, full), hex(o[LED_DOWN]))
    got.clear(); btn(uc, ID_DOWN)
    check("its settings: Down = back to the sends page, the stock not called", not got and b8(uc, SLOT) == 1)
    btn(uc, ID_UP); uc.mem_write(fxpage_p(uc), b"\xff"); out(uc)
    check("the effect let go: the shortcut ends", b8(uc, SLOT) == 0)
    uc.mem_write(fxpage_p(uc), b"\x00"); got.clear(); btn(uc, ID_DOWN)
    check("settings reached the stock's way: Down is the stock's", got == [PREV["prev_btn"]] and b8(uc, SLOT) == 0)
    uc.mem_write(fxpage_p(uc), b"\xff"); btn(uc, ID_DOWN)
    o = out(uc, up=0x111111)
    check("sends page, nothing held: Up keeps the stock's light", o[LED_UP] == 0x111111, hex(o[LED_UP]))
    btn(uc, ID_UP); uc.mem_write(mode_p(uc), was[0]); uc.mem_write(fxpage_p(uc), was[1]); view(uc, CONT)
    filter_layout=ET.MAN['report'].get('filter_cutoff',{})
    start=filter_layout.get('itcm_start',0)
    ranges = [(start, start + filter_layout.get('itcm_bytes', 0))]
    for feature in ('pitch_envelope_dsp', 'ring_mod_dsp'):
        layout = ET.MAN['report'].get(feature, {})
        if 'settings_itcm_start' in layout:
            start = layout['settings_itcm_start']
            ranges.append((start, start + layout['settings_itcm_bytes']))
    if R.get("cues"):
        ranges.append((int(R["cues"]["ram"], 16), int(R["cues"]["ram"], 16) + R["cues"].get("ram_len", 24)))
    unexpected = [a for a in low if not any(lo <= a < hi for lo, hi in ranges)]
    check("no unowned read below flash (a store followed one time too many)", not unexpected, [hex(a) for a in unexpected[:4]])

    wr.clear()
    for _ in range(300):
        out(uc)
    check("DSP not READY: nothing written", not wr)
    uc.mem_write(READY_AT, b"\xa0")
    for _ in range(200):
        out(uc)
    check("READY: nothing for 200 frames", not wr)
    for _ in range(8):
        out(uc)
    want = [(0, ((FULL - v) * 0x7FFF // FULL) << 16, CUT + t) for t, v in enumerate(sends(uc))]
    check("then one track a frame: core 0's X:CUT + t = the share around Grid FX", wr == want, (wr, want))
    wr.clear()
    for _ in range(16):
        out(uc)
    check("after: one track again every 8 frames", [w[2] - CUT for w in wr] == [0, 1], wr)
    view(uc, MIX); btn(uc, ID_DOWN); knob(uc, 7, -100); wr.clear(); out(uc)
    check("a changed send is written on the next frame", wr == [(0, ((FULL - 27) * 0x7FFF // FULL) << 16, CUT + 7)], wr)
    uc.mem_write(READY_AT, b"\x00"); out(uc); uc.mem_write(READY_AT, b"\xa0"); wr.clear()
    for _ in range(208):
        out(uc)
    check("READY again (the DSP restarted): all eight written again", sorted(w[2] - CUT for w in wr) == list(range(8)), wr)
    fx_track(uc, got, takes)
    fx_view()
    step_mutate_fx_test()
    if R.get("control_page"):
        control_page_test()
    else:
        shift_controls_test()
    recording_feedback_test()
    cold_start()
    irq_short()
    scrub_test()
    scrub_boundary_test()
    scrub_audio_test()
    scrub_chain_bounds_test()
    scrub_page_recovery_test()
    scrub_any_test()
    cue_test()
    cue2_test()
    cue3_test()
    cols_test()
    pass_test()
    tap_test()
    bar_punch_test()
    chase_test()
    sync_test()
    down_test()
    scrub_native_preview_test()
    print("ALL PASS" if not ET.FAILS else f"{len(ET.FAILS)} FAILED")
    sys.exit(1 if ET.FAILS else 0)


if __name__ == "__main__":
    main()
