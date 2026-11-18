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
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP  # noqa: E402

R = ET.MAN["report"]["gfxmix"]
LB = {k: int(v, 16) for k, v in R["labels"].items()}
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
def knob(uc, k, d): call(uc, T.KN_ENTRY, C.CTRL, k, d & 0xFFFFFFFF)
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
    uc.mem_write(sh, b"\x01"); btn(uc, 17)
    check("Shift + Play pressed: held back from the stock", b8(uc, SLOT + O_SCR) == 1 and btns == [], btns)
    check("  Shift up in the stock while it scrubs (no Shift pages)", b8(uc, ptr(uc, u32(uc, C.CTRL + 0xC), 0)) == 0)
    o = out(uc)
    check("  K1 green while held", o[LED_KNOB0] & 0xFFFFFF in (scl(0x00FF00, 255), scl(0x00FF00, 141)), hex(o[LED_KNOB0]))
    knob(uc, 0, 2); knob(uc, 0, -5)
    check("  K1 +2, then -5: the stock's locate at step 13, then step 6", locs == [72, 30], locs)
    uc.mem_write(pos, struct.pack("<I", 84)); knob(uc, 0, 3)
    check("  K1 +3 from step 15 of 16: the song's last step", locs[-1] == 90, locs)
    uc.mem_write(pos, struct.pack("<I", 84 + 96 * 3)); knob(uc, 0, 1)
    check("  the position three loops on: still inside the song", locs[-1] == 90, locs)
    rel(17); uc.mem_write(sh, b"\x00")
    check("  let go after a turn: nothing to the stock", btns == [] and rels == [] and b8(uc, SLOT + O_SCR) == 0, (btns, rels))
    uc.mem_write(pos, struct.pack("<I", 3))
    uc.mem_write(sh, b"\x01"); btn(uc, 17); knob(uc, 0, -1)
    check("  back past the song's start: 0", locs[-1] == 0, locs)
    rel(17)
    btn(uc, 17); uc.mem_write(sh, b"\x00"); locs.clear(); rel(17)
    check("Shift + Play tapped (Shift let go first): the stock's Shift + Play and its release",
          [x for x, _ in btns] == [17] and [x for x, _ in rels] == [17] and locs == [], (btns, rels, locs))
    tr = ptr(uc, 0x200122B0, 0)
    uc.mem_write(tr, b"\x00"); uc.mem_write(pos, struct.pack("<I", 30))
    uc.mem_write(sh, b"\x01"); btn(uc, 17); knob(uc, 0, 3); rel(17); uc.mem_write(sh, b"\x00")
    locs.clear(); btns.clear(); rels.clear()
    start = uc.hook_add(UC_HOOK_CODE, lambda u, a_, n, d: u.mem_write(tr, b"\x01"), None, PREV["prev_btn"], PREV["prev_btn"] + 1)
    uc.mem_write(sh, b"\x01"); btn(uc, 17); uc.mem_write(sh, b"\x00"); rel(17); uc.hook_del(start)
    check("a stopped scrub (step 6 + 3), then a Shift + Play tap that starts it: from the scrub's place", locs == [8 * 6], locs)
    uc.mem_write(tr, b"\x00")
    view(uc, CONT); t = b8(uc, ptr(uc, u32(uc, CONT + 0x25C), 0)) & 7
    tp = ptr(uc, u32(uc, ENG + 0x30 + 4 * t), 1); so = u32(uc, CONT + 0x74 + 4 * t); pgp = ptr(uc, u32(uc, so + 0x60), 0)
    uc.mem_write(pgp, b"\x00"); uc.mem_write(tp, bytes([20]))
    uc.mem_write(sh, b"\x01"); btn(uc, 17); out(uc)
    check("scrubbing, the track's playhead on step 21: its page 2 shown", b8(uc, ptr(uc, u32(uc, so + 0x60), 0)) & 1 == 1)
    o = out(uc)
    check("  the playhead's pad (pad 5 of page 2) white", o[4] & 0xFFFFFF in (WHITE, scl(WHITE, 141)), hex(o[4]))
    wr = []
    hw = uc.hook_add(UC_HOOK_MEM_WRITE, lambda u, acc, ad, sz, v, d: wr.append(ad), None, u32(uc, so + 0x60), u32(uc, so + 0x60) + 0x20)
    for _ in range(5):
        out(uc)
    uc.hook_del(hw)
    check("  five more frames on that page: the page store not written again", wr == [], [hex(x) for x in wr])
    rel(17); uc.mem_write(sh, b"\x00")
    btns.clear(); rels.clear(); uc.mem_write(sh, b"\x01"); btn(uc, 17)
    uc.mem_write(HAL_TICK, struct.pack("<I", u32(uc, HAL_TICK) + 300)); rel(17); uc.mem_write(sh, b"\x00")
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
    rel = lambda: call(uc, C.BTN_RELEASE, C.CTRL, 17)
    def hold():
        uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0), b"\x01"); btn(uc, 17)
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
    hold(); rel(); uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0),b"\x00")
    check("Shift + Play tap resumes from the held last step", taps == [1] and b8(uc,ptr(uc,C.TRANSPORT,0)) == 1 and u32(uc,ptr(uc,u32(uc,eng+0x90),0)) == 90, (b8(uc,ptr(uc,C.TRANSPORT,0)),u32(uc,ptr(uc,u32(uc,eng+0x90),0))))
    if os.environ["RH_BUILD"] >= "a0171":
        tap_sh = ptr(uc,u32(uc,C.CTRL+0xC),0)
        tap_tr = ptr(uc,C.TRANSPORT,0)
        taps.clear();hold();knob(uc,0,-100);rel();uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0),b"\x00")
        tap_sh = ptr(uc,u32(uc,C.CTRL+0xC),0)
        tap_tr = ptr(uc,C.TRANSPORT,0)
        hold();rel();uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0),b"\x00")
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
    uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0),b"\x01"); btn(uc,17)
    knob(uc,0,1)
    check("stopped scrub: sound on by default, all eight stock note dispatchers called", notes == [(objs[t],48+t,90+t) for t in range(8)], notes)
    check("  stock sample selector called at each track's located step", samples == [(PLAYERS+PL_SZ*t,0,2) for t in range(8)], samples)
    check("  audition leaves transport stopped", b8(uc,ptr(uc,C.TRANSPORT,0)) == 0)
    o=out(uc)
    check("scrub: K1 and K2 green, K3-K8 dark", o[60] == o[61] and o[60] != 0 and list(o[62:68]) == [0]*6, o[60:68])
    for v in (CONT,MIX):
        view(uc,v)
        for k in range(2,8): knob(uc,k,1); knob(uc,k,-1)
    check("K3-K8 disabled on track and mixer views", turns == [], turns)
    knob(uc,1,-1)
    check("K2 left: all audition notes released at once", offs == [(objs[t],48+t,0) for t in range(8)], offs)
    notes.clear(); samples.clear(); knob(uc,0,1)
    check("K2 off: K1 still locates silently", notes == [] and samples == [])
    o=out(uc)
    check("K2 off: red LED, other knobs still dark", o[61] == scl(0xFF0000,255) or o[61] == scl(0xFF0000,141), o[60:68])
    knob(uc,1,1); knob(uc,0,-1)
    check("K2 right: audition resumes on the next K1 turn", len(notes)==8, notes)
    offs.clear(); uc.mem_write(HAL_TICK,struct.pack("<I",u32(uc,HAL_TICK)+120)); out(uc)
    check("no turn for 120 ms: all preview notes released", len(offs)==8, offs)
    offs.clear(); notes.clear(); knob(uc,0,1); call(uc,C.BTN_RELEASE,C.CTRL,17)
    check("release Play: preview notes released", len(notes)==8 and len(offs)==8, (notes,offs))
    view(uc,CONT); knob(uc,2,1)
    check("after scrub: K3 returns to its normal handler", len(turns)==1, turns)
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
    uc.mem_write(sh,b"\x01");btn(uc,17);knob(uc,1,-1)
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
    call(uc,C.BTN_RELEASE,C.CTRL,17)


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
    uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0),b"\x01");btn(uc,17)
    bad=[]
    for st in list(range(16,32))+list(range(30,14,-1)):
        # Reproduce a native page reset between scrub steps, with real store writes.
        call(uc,0x0803FD26,pg,0);uc.mem_write(uc.reg_read(UC_ARM_REG_R0),b"\x00");call(uc,0x0803FBEC,pg)
        uc.mem_write(step_ptr,bytes([st]));out(uc)
        want=second if st>=16 else first
        if b8(uc,ptr(uc,pg,0)) != st>>4 or drawn[-1] != want:
            bad.append(st+1)
    check("all steps 17-32 forward and backward: recover native page reset and draw correct page in the same frame",bad==[],bad)
    call(uc,C.BTN_RELEASE,C.CTRL,17)


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
    uc.mem_write(ptr(uc,u32(uc,C.CTRL+0xC),0),b"\x01");btn(uc,17)
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
    packets.clear();call(uc,C.BTN_RELEASE,C.CTRL,17)
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
    check("no read below the flash (a store followed one time too many)", not low, [hex(a) for a in low[:4]])

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
    scrub_native_preview_test()
    print("ALL PASS" if not ET.FAILS else f"{len(ET.FAILS)} FAILED")
    sys.exit(1 if ET.FAILS else 0)


if __name__ == "__main__":
    main()
