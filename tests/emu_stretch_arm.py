"""Unicorn test of stretch.c (stretch_arm.py) on a build with it: Sample mode's pads 9-17, the record's block, the engine's words through
Granular's writer, the lights, the tempo, the reach of the whole sample or its K2 / K3 part, and a Granular track's Scan.

    python tests/emu_stretch_arm.py STOCK.bin BUILT.bin RAM.bin
"""
import json
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("RH_BUILD", Path(sys.argv[2]).parent.name if len(sys.argv) > 2 else "a0233")
import emu_tmenu as ET  # noqa: E402  (ourram's layout from the build's manifest)
from emu_tmenu import C, T, call, check, ptr, u32  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stretch_dsp as D  # noqa: E402
from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2  # noqa: E402

REP = ET.MAN["report"]
R = REP["stretch"]["arm"]
LB = {k: int(v, 16) for k, v in R["labels"].items()}
SLOT, BLK_OFF = int(R["slot"], 16), R["blk_off"]
BR = REP["granular"]["bridge"]
KER = REP["granular"]["arm_kernel"]["labels"]
GSTATE = int(BR["slot"], 16)
RRT = int(REP["rhrec"]["labels"]["c_rrt"], 16)
SMP_VT, SMP_PAD, MODE_SMP = 0x08067D8C, 0x08057DA8, 9
TEMPO_GET, TEMPO = 0x0803FC6C, 0x20012788
OUT, FRAME = 0x2004FA00, 0x2004FD00
NARROW = 0x08031268                                     # the stock's narrow host read: (0, host) -> the word << 8
SMP_LEN = 0x0804A4E4                                    # the stock's length of a sample (its number)
PLAYERS, PLAYER_SZ, KSTORES = 0x200470D4, 0x190, 0x1F4
ROUTE_KEY, GR_KEY = 0x674E31, 0x6A7A4B
GR_ON_RGB, GR_OFF_RGB = 0x35DF74, 0xFF3040                # Granular's editor: its on / off pad
WHITE, AMBER = 0xFFFFFF, 0xFFA020
COLOURS, CLR_CUE, CLR_RED = 0x20003974, 0x54, 0x55
RGB = (0xFFC866, 0xE6D166, 0xCCDA66, 0xB3E466, 0x99ED66, 0x80F666, 0x66FF66)
QUARTERS = (1, 2, 4, 8, 16, 32)
ON, PART = 0x80, 0x08
LENS = {}                                               # sample number -> its length, else 0
PLUS = [0x1500]
SNAP = {}                                               # host address -> the word the narrow read returns, else core 1's inactive
SNAP_HOST = 0xAB20                                      # the snapshot's first word, 8 a track; word 7 the note's serial
STOCK = []


def scl(rgb, lvl): return sum((((rgb >> s) & 0xFF) * (lvl + 1) >> 8) << s for s in (0, 8, 16))
def blk(uc): call(uc, RRT); return uc.reg_read(UC_ARM_REG_R0) + BLK_OFF
def sel(uc, t): uc.mem_write(ptr(uc, u32(uc, T.CONT + 0x25C), 0), bytes([t]))
def pad(uc, p): STOCK.clear(); call(uc, u32(uc, SMP_VT) & ~1, 0x2004D36C, p, 100)


def off_red(uc, full, lo):
    """pad 9's stretch off: Granular's off with off_match, else the stock red dimmed"""
    if REP["stretch"]["arm"].get("scan_lock", {}).get("off_match"):
        return scl(GR_OFF_RGB, full)
    return scl(u32(uc, COLOURS + 4 * CLR_RED), lo)


def tempo(uc, bpm):
    call(uc, TEMPO_GET, TEMPO, 0)
    uc.mem_write(uc.reg_read(UC_ARM_REG_R0), bytes([bpm]))


def page(uc, on):
    uc.mem_write(C.CTRL + 0x7C, struct.pack("<I", T.CONT))
    uc.mem_write(T.CONT + 0x264, bytes([MODE_SMP if on else 0]))


def out(uc):
    ET.DSPW.clear()
    uc.mem_write(OUT, bytes(69 * 4))
    call(uc, LB["c_st_out"], C.CTRL, OUT, FRAME)
    return struct.unpack("<69I", uc.mem_read(OUT, 69 * 4))


def writes():
    """(word, value) of each write through Granular's writer: ('c', k) a route word, ('p', k) a host parameter word, with the track"""
    w = []
    for _, v, host in ET.DSPW:
        if 0xAB00 <= host < 0xAB20:
            w.append((("c", (host - 0xAB00) % 4), (host - 0xAB00) // 4, v >> 8))
        elif 0xAB60 <= host < 0xABE0:
            w.append((("p", (host - 0xAB60) % 16), (host - 0xAB60) // 16, v >> 8))
    return w


def sample(uc, t, n, length):
    """the track's sample is number n, of length samples"""
    uc.mem_write(ptr(uc, u32(uc, PLAYERS + PLAYER_SZ * t + 0x60), 0), bytes([n]))
    LENS[n] = length


def knobs(uc, t, start, length):
    """K2 / K3 with their fine parts: 0 .. 16383"""
    st = u32(uc, C.CTRL + KSTORES + 4 * t)
    for k, v in ((1, start), (2, length)):
        uc.mem_write(ptr(uc, st, k), bytes([v >> 7]))
        uc.mem_write(ptr(uc, st, k + 13), bytes([v & 127]))


def tick(uc, ms):
    uc.mem_write(0x20006F3C, struct.pack("<I", ms))


def rec(uc, t):
    b = bytes(uc.mem_read(blk(uc), 28))
    ok = b[:2] == b"ST" and b[3] == 1 and b[2] == (sum(b[4:]) & 0xFF) ^ 0x5A
    return ok, b[4 + 3 * t] | b[5 + 3 * t] << 8 | b[6 + 3 * t] << 16


def on_words(t, spd, tgt):
    return [(("p", 0), t, spd), (("p", 2), t, tgt), (("p", 15), t, D.HOST_KEY), (("c", 3), t, 2), (("c", 0), t, ROUTE_KEY)]


def sweeps(uc, o, position, locked):
    """Frames of 8-9 ms against a running clock. Core 0's playhead moves s^2 / 2^19 samples a sample (measured), held at the start
    while field 13 bit 15 is set. Each sweep must end where the clock crosses its boundary."""
    n = 96000
    call(uc, C.PARAM_GET, 0x200122B0, 0)
    uc.mem_write(uc.reg_read(UC_ARM_REG_R0), b"\x01")

    def run(frames, bpm_of, lens, tap=None, turn=None, notes=(), size=n):
        ms, ticks, d, hold, ends, lock6, gone = 5000, 0.0, 0.0, False, [], 0, None
        call(uc, KER["c_gr_runtime_scan"], GSTATE, o, 0xFFFFFFFF)
        s = uc.reg_read(UC_ARM_REG_R0) - 1024
        uc.mem_write(position, struct.pack("<I", 0))
        tick(uc, ms); out(uc); out(uc)
        s = next((v for kind, track, v in reversed(writes()) if track == o and kind == ("p", 6)), s)   # the last Scan word sent
        for i in range(frames):
            bpm = bpm_of(i)
            tempo(uc, bpm)
            dms = 8 + (i % 4 == 0)
            t_prev, d_prev = ticks, d
            ticks += dms * bpm * 24 / 60000
            if not hold:
                d += s * s / (1 << 19) * dms * 48
            L = lens(i) * 24
            if gone is not None:                          # a note's sweep: one length at the tempo of each moment
                g_prev, gone = gone, gone + dms * bpm / (lens(i) * 60000)
                if gone >= 1:
                    f = (1 - g_prev) / (gone - g_prev)
                    ends.append(((d_prev + f * (d - d_prev)) - size) / size * lens(i) * 60000 / bpm)
                    gone = None
            elif not notes and int(ticks // L) > int(t_prev // L):
                f = (int(ticks // L) * L - t_prev) / (ticks - t_prev)
                ends.append(((d_prev + f * (d - d_prev)) - size) / size * lens(i) * 60000 / bpm)    # ms early (-) or late (+)
            ms += dms
            tick(uc, ms)
            uc.mem_write(position, struct.pack("<I", int(ticks)))
            if tap is not None and i == tap[0]:
                pad(uc, tap[1])
            if turn is not None and i == turn:
                call(uc, KER["c_gr_runtime_scan"], GSTATE, o, 1100)
            if i in notes:                                # core 1 counts the note; core 0 restarts the playhead
                SNAP[SNAP_HOST + 8 * o + 7] = SNAP.get(SNAP_HOST + 8 * o + 7, 0) + 1
                d, gone = 0.0, 0.0
            out(uc)
            if not locked:                                # Granular sends its Scan knob
                call(uc, KER["c_gr_runtime_scan"], GSTATE, o, 0xFFFFFFFF)
                s = uc.reg_read(UC_ARM_REG_R0) - 1024
            for kind, track, v in writes():
                if track == o and kind == ("p", 6):
                    s, lock6 = v, lock6 + 1
                elif track == o and kind == ("p", 13):
                    hold = bool(v >> 15 & 1)
                    if hold:
                        d = 0.0
        return ends, lock6

    worst = lambda e: max(abs(x) for x in e)  # noqa: E731
    rnd = lambda e: [round(x, 1) for x in e]  # noqa: E731
    steady, _ = run(900, lambda i: 97, lambda i: 4)
    change, _ = run(900, lambda i: 97 if i < 380 else 131, lambda i: 4)
    print(f"  1-bar sweeps, ms from the bar: steady 97 BPM {rnd(steady)}, 97 -> 131 BPM {rnd(change)}")
    if not locked:
        tempo(uc, 120); out(uc)
        return
    check("Scan lock: 1-bar sweeps at 97 BPM end within 3 ms of the bar", worst(steady) < 3, rnd(steady))
    check("Scan lock: a tempo change mid-bar (97 -> 131): every sweep still ends within 3 ms of the bar", worst(change) < 3, rnd(change))
    pad(uc, 13)                                           # 2 bars
    two, _ = run(1500, lambda i: 103, lambda i: 8)
    check("Scan lock: 2-bar sweeps at 103 BPM end within 3 ms of the boundary", worst(two) < 3, rnd(two))
    pad(uc, 12)                                           # 1 bar, then 2 bars tapped a third into a 2-bar cycle
    tapped, _ = run(2000, lambda i: 97, lambda i: 4 if i <= 400 else 8, tap=(400, 13))
    check("Scan lock: 2 bars tapped mid-cycle: one longer sweep, then every sweep ends on the boundary", worst(tapped[-2:]) < 3, rnd(tapped))
    pad(uc, 12)
    config = GSTATE + 168 + o                             # Retrigger on: each note restarts the playhead (field 13 bit 0)
    old = bytes(uc.mem_read(config, 1))
    uc.mem_write(config, bytes([old[0] | 8]))
    timed, _ = run(2200, lambda i: 97 if i < 900 else 128, lambda i: 4, notes=(100, 550, 1000, 1450, 1900))
    _, noted = run(60, lambda i: 97, lambda i: 4)
    uc.mem_write(config, old)
    check("Scan lock: notes that restart the playhead: each note's 1-bar sweep ends one bar after it, across 97 -> 128 BPM",
          len(timed) == 5 and worst(timed) < 3, rnd(timed))
    if REP["granular"].get("scan_each"):                  # each sample: a note's own region sets the sweep
        setting, w = GSTATE + 292 + o, SNAP_HOST + 8 * o
        s0 = uc.mem_read(setting, 1)[0]
        uc.mem_write(setting, bytes([s0 | 16]))
        tags = REP["stretch"]["arm"]["scan_lock"].get("each_tags")
        SNAP.update({w: 0x674331 if tags else 0x674E31, w + 4: 1000, w + 5: 1000 + 48000})   # core 0's "seen" tag
        short, _ = run(900, lambda i: 97, lambda i: 4, size=48000)
        SNAP[w + 5] = 1000 + 150000
        if tags:
            SNAP[w] = 0x674732                                    # the native voice has ended; the region stays
        long_, _ = run(900, lambda i: 97, lambda i: 4, size=150000)
        uc.mem_write(setting, bytes([s0]))
        followed, _ = run(900, lambda i: 97, lambda i: 4, size=150000)
        for k in (w, w + 4, w + 5):
            SNAP.pop(k)
        check("Scan length each sample: a 48,000 and a 150,000 sample note both sweep once a bar, within 3 ms"
              + (" (core 0's seen and ended tags)" if tags else ""),
              worst(short) < 3 and worst(long_) < 3, (rnd(short), rnd(long_)))
        check("Scan length track sample: the same 150,000 note sweeps at the track sample's speed (not on the bar)",
              worst(followed) > 100, rnd(followed))
    _, before = run(150, lambda i: 97, lambda i: 4)
    call(uc, KER["c_gr_runtime_scan"], GSTATE, o, 1100)
    _, after = run(150, lambda i: 97, lambda i: 4)
    check("Scan lock: Scan turned by hand is free: no Scan words from the lock", before > 100 and after <= 1, (before, after))
    pad(uc, 12)                                           # 1 bar chosen again, the Scan before it 1100
    tempo(uc, 120); out(uc)
    gscan = SLOT + 36 + 2 * o                             # State.gscan[o]: RAM only, 0 after a power-up
    call(uc, KER["c_gr_runtime_scan"], GSTATE, o, 0xFFFFFFFF)
    pad_scan = uc.reg_read(UC_ARM_REG_R0)
    assert struct.unpack("<H", uc.mem_read(gscan, 2))[0] == pad_scan
    uc.mem_write(gscan, b"\0\0")
    _, loaded = run(150, lambda i: 120, lambda i: 4)
    taken = struct.unpack("<H", uc.mem_read(gscan, 2))[0]
    call(uc, KER["c_gr_runtime_scan"], GSTATE, o, 1100)
    uc.mem_write(gscan, b"\0\0")
    _, turned = run(150, lambda i: 120, lambda i: 4)
    check("Scan lock after a load: the saved pad with its own Scan takes charge again; a Scan turned by hand stays free",
          loaded > 100 and taken == pad_scan and turned <= 1 and struct.unpack("<H", uc.mem_read(gscan, 2))[0] == 0, (loaded, taken, turned))
    call(uc, KER["c_gr_runtime_scan"], GSTATE, o, pad_scan)
    out(uc)


def main():
    uc = ET.setup(Path(sys.argv[2]).read_bytes(), Path(sys.argv[3]).read_bytes())

    def narrow(u, a, n, d):
        u.reg_write(UC_ARM_REG_R0, SNAP.get(u.reg_read(UC_ARM_REG_R1), 0x674531) << 8)
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE, narrow, None, NARROW, NARROW + 1)

    def smp_len(u, a, n, d):
        u.reg_write(UC_ARM_REG_R0, LENS.get(u.reg_read(UC_ARM_REG_R0), 0))
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE, smp_len, None, SMP_LEN, SMP_LEN + 1)

    def stock_pad(u, a, n, d):
        STOCK.append(u.reg_read(UC_ARM_REG_R1))
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE, stock_pad, None, SMP_PAD, SMP_PAD + 1)
    plus_gate = REP["storageshadow"].get("pack_files") == 2
    if plus_gate:                                       # the project's Plus settings: loaded unless PLUS[0] = 0
        def plus_ok(u, a, n, d):
            u.reg_write(UC_ARM_REG_R0, PLUS[0])
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
        at = int(REP["storageshadow"]["labels"]["c_sh_autobank"], 16)
        uc.hook_add(UC_HOOK_CODE, plus_ok, None, at, at + 1)
    if not ET.GRAN:
        def wr16(u, a, n, d):
            ET.DSPW.append((u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_R1), u.reg_read(UC_ARM_REG_R2)))
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
        uc.hook_add(UC_HOOK_CODE, wr16, None, 0x08031200, 0x08031201)
    uc.mem_write(int(BR["ready"], 16), bytes([0xA0]))
    uc.mem_write(int(BR["wait"], 16), bytes([200]))
    uc.mem_write(int(BR["upload"], 16), bytes([0]))
    uc.mem_write(blk(uc), bytes(28))
    t, o = 2, 5
    sample(uc, t, 10, 0)
    sample(uc, o, 11, 0)
    knobs(uc, t, 0, 16383)
    knobs(uc, o, 0, 16383)
    sel(uc, t)
    tempo(uc, 120)
    page(uc, False)
    f = out(uc)
    check("a new project: no track stretches, nothing written", writes() == [], writes())

    pad(uc, 8)
    ok, r = rec(uc, t)
    check("pad 9: the track's stretch on with Follow at this tempo, in the record's block \"ST\"", ok and r == ON | 1200 << 8 and STOCK == [], (ok, hex(r)))
    check("pad 9: the other tracks stay off", all(rec(uc, k)[1] == 0 for k in range(8) if k != t))
    out(uc)
    check("the next frame: speed 1 (Q20), no length, the key, route word 3 = 2 (the native reader in Loop), the route last", writes() == on_words(t, 1 << 20, 0), writes())
    seen = []
    for _ in range(8):
        out(uc)
        seen += writes()
    check("in 8 frames the track's words are all sent once more", seen == on_words(t, 1 << 20, 0), seen)
    tempo(uc, 150)
    out(uc)
    check("tempo 150: Follow's speed 150 / 120, only its words 0 and 2", [w for w in writes() if w[1] == t][:2] == [(("p", 0), t, (1500 << 20) // 1200), (("p", 2), t, 0)], writes())
    tempo(uc, 120)
    out(uc)

    page(uc, True)
    dimmed = u32(uc, ptr(uc, u32(uc, C.CTRL + 0x88), 2)) >> 10 & 1
    full = 141 if dimmed else 255
    lo, half = 48 * full >> 8, 128 * full >> 8
    f = out(uc)
    want = [scl(0x66FF66, full), scl(WHITE, full)] + [scl(RGB[1 + k], lo) for k in range(6)]
    check("Sample mode, no sample length: pad 9 green, pad 10 white, every length in the gradient, dim", list(f[8:16]) == want,
          [hex(v) for v in f[8:16]])
    sample(uc, t, 10, 48000)
    f = out(uc)
    cue = scl(u32(uc, COLOURS + 4 * CLR_CUE), full)
    want = [scl(0x66FF66, full), scl(WHITE, full)] + [scl(RGB[1 + k], lo) for k in range(4)] + [cue, cue]
    check("a sample of 48,000 samples at 120, no note played: 4 and 8 bars are out of reach (more than 4 x slower), dim red",
          list(f[8:16]) == want, [hex(v) for v in f[8:16]])
    pad(uc, 15)
    check("pad 16 out of reach: no change", rec(uc, t)[1] == ON | 1200 << 8)
    pad(uc, 10)
    check("pad 11: 1/4 bar", rec(uc, t)[1] == ON | 1 | 1200 << 8, hex(rec(uc, t)[1]))
    f = out(uc)
    check("its words: no speed, the length 24,000 samples", [w for w in writes() if w[1] == t][:2] == [(("p", 0), t, 0), (("p", 2), t, 24000)], writes())
    check("pad 11 full", f[10] == scl(RGB[1], full), hex(f[10]))
    pad(uc, 13)
    out(uc)
    check("pad 14 (2 bars): the length 192,000 samples", [w for w in writes() if w[1] == t][:2] == [(("p", 0), t, 0), (("p", 2), t, 192000)], writes())
    tempo(uc, 96)
    out(uc)
    check("tempo 96: 2 bars are 240,000 samples", [w for w in writes() if w[1] == t][:2] == [(("p", 0), t, 0), (("p", 2), t, 240000)], writes())
    tempo(uc, 120)
    out(uc)

    knobs(uc, t, 8192, 16383)
    f = out(uc)
    want = [scl(0x66FF66, full), scl(WHITE, full)] + [scl(RGB[1 + k], full if k == 3 else lo) for k in range(4)] + [cue, cue]
    check("the whole sample: K2 at the middle changes no light", list(f[8:16]) == want, [hex(v) for v in f[8:16]])
    pad(uc, 9)
    check("pad 10: the part fits, the choice kept", rec(uc, t)[1] == ON | PART | 4 | 1200 << 8 and STOCK == [], hex(rec(uc, t)[1]))
    f = out(uc)
    check("its words: the length 192,000 samples with the part's bit", [w for w in writes() if w[1] == t][:2] ==
          [(("p", 0), t, 0), (("p", 2), t, 192000 | D.TGT_PART)], writes())
    want = [scl(0x66FF66, full), scl(AMBER, full)] + [scl(RGB[1 + k], lo) for k in range(3)] + [cue] * 3
    check("the part from the middle (24,000 samples): 2, 4 and 8 bars dim red, pad 10 amber", list(f[8:16]) == want, [hex(v) for v in f[8:16]])
    pad(uc, 14)
    check("pad 15 (4 bars) out of reach of the part: no change", rec(uc, t)[1] == ON | PART | 4 | 1200 << 8, hex(rec(uc, t)[1]))
    pad(uc, 12)
    out(uc)
    check("pad 13 (1 bar): the length 96,000 samples with the part's bit", [w for w in writes() if w[1] == t][:2] ==
          [(("p", 0), t, 0), (("p", 2), t, 96000 | D.TGT_PART)], writes())
    knobs(uc, t, 8192, 4095)
    f = out(uc)
    check("K3 at a quarter: the part 12,000 samples, 1 bar dim red", f[12] == cue and f[11] == scl(RGB[2], lo), [hex(v) for v in f[8:17]])
    pad(uc, 9)
    pad(uc, 13)
    check("pad 10 again: the whole sample; pad 14: 2 bars", rec(uc, t)[1] == ON | 4 | 1200 << 8, hex(rec(uc, t)[1]))
    f = out(uc)
    check("its words: 192,000 samples, no part's bit; pad 10 white", [w for w in writes() if w[1] == t][:2] ==
          [(("p", 0), t, 0), (("p", 2), t, 192000)] and f[9] == scl(WHITE, full), (writes(), hex(f[9])))
    pad(uc, 13)
    check("pad 14, the lit length, again: Follow at this tempo", rec(uc, t)[1] == ON | 1200 << 8, hex(rec(uc, t)[1]))
    f = out(uc)
    check("Follow: speed 1, no length; no length lit", [w for w in writes() if w[1] == t][:2] == [(("p", 0), t, 1 << 20), (("p", 2), t, 0)]
          and f[13] == scl(RGB[4], lo), (writes(), hex(f[13])))
    pad(uc, 13)
    out(uc)
    knobs(uc, t, 0, 16383)

    serial = SNAP_HOST + 8 * t + 7
    SNAP[serial] = 0x1D7
    SNAP[SNAP_HOST + 8 * t] = 0x674E31                 # the note sounds
    pad(uc, 8)
    check("pad 9 again: off, the length kept", rec(uc, t)[1] == 4 | 1200 << 8, hex(rec(uc, t)[1]))
    tick(uc, 1000)
    f = out(uc)
    drain = [(("p", 0), t, 1 << 20), (("p", 2), t, 0), (("c", 3), t, 4)]
    check("off: the note plays on at speed 1, route word 3 = 4 (core 1's own reader runs unheard)",
          [w for w in writes() if w[1] == t] == drain, writes())
    seen = []
    for ms in (1010, 1500, 9000):
        tick(uc, ms)
        out(uc)
        seen += [w for w in writes() if w[1] == t]
    check("off: the same note: nothing more, however long", seen == [], seen)
    if json.loads((Path(sys.argv[2]).parent / "manifest.json").read_text())["report"]["granular"].get("stretch_drain_idle"):
        SNAP[SNAP_HOST + 8 * t] = 0x674531
        tick(uc, 9000)
        out(uc)
        back = [w for w in writes() if w[1] == t]
        check("off, the voice silent: the route goes back at once, with no next note", (("c", 0), t, 0) in back and (("c", 3), t, 1) in back, back)
        SNAP[SNAP_HOST + 8 * t] = 0x674E31
    pad(uc, 8)
    out(uc)
    check("on again while draining: the kept length (2 bars), all the words again, word 3 = 2",
          [w for w in writes() if w[1] == t] == on_words(t, 0, 192000), writes())
    if json.loads((Path(sys.argv[2]).parent / "manifest.json").read_text())["report"]["granular"].get("stretch_handoff"):
        uc.mem_write(GSTATE + 477, bytes([1 << t]))
        seen = []
        for _ in range(9):
            out(uc)
            seen += [w for w in writes() if w[1] == t]
        uc.mem_write(GSTATE + 477, b"\0")
        check("while Granular fades the track out to take it: stretch writes nothing to it", seen == [], seen)
    pad(uc, 8)
    out(uc)
    check("off again: the drain words again", [w for w in writes() if w[1] == t] == drain, writes())
    SNAP[serial] = 0x1D8
    tick(uc, 9001)
    out(uc)
    check("the next note: word 3 = 3, core 1 fades back to its own reader", [w for w in writes() if w[1] == t] == [(("c", 3), t, 3)], writes())
    tick(uc, 9010)
    out(uc)
    check("off: nothing more before 10 ms", [w for w in writes() if w[1] == t] == [], writes())
    pad(uc, 8)
    out(uc)
    check("on again while fading: all the words again, word 3 = 2", [w for w in writes() if w[1] == t] == on_words(t, 0, 192000), writes())
    pad(uc, 8)
    out(uc)
    SNAP[serial] = 0x1D9
    tick(uc, 9020)
    out(uc)
    first = [w for w in writes() if w[1] == t]
    out(uc)
    check("off again, then the next note: word 3 = 3 again, nothing more in the same ms",
          first == [(("c", 3), t, 3)] and [w for w in writes() if w[1] == t] == [], (first, writes()))
    tick(uc, 9030)
    out(uc)
    check("10 ms later: the route off, then Granular's own words 0, 2 and 15", [w for w in writes() if w[1] == t] ==
          [(("c", 0), t, 0), (("c", 3), t, 1), (("p", 0), t, t + 1), (("p", 2), t, 0), (("p", 15), t, GR_KEY)], writes())
    check("off: pad 9 red, the kept length half", f[8] == off_red(uc, full, lo) and f[13] == scl(RGB[4], half),
          (hex(f[8]), hex(f[13])))
    seen = []
    for _ in range(9):
        out(uc)
        seen += writes()
    check("off: nothing more is written", seen == [], seen)
    tempo(uc, 90)
    pad(uc, 8)
    check("on again: the kept length (2 bars)", rec(uc, t)[1] == ON | 4 | 1200 << 8, hex(rec(uc, t)[1]))
    pad(uc, 13)
    check("the bright length again at tempo 90: Follow, the tempo taken", rec(uc, t)[1] == ON | 900 << 8, hex(rec(uc, t)[1]))
    pad(uc, 8)
    tempo(uc, 100)
    pad(uc, 8)
    check("off and on with Follow kept, at tempo 100: Follow takes 100", rec(uc, t)[1] == ON | 1000 << 8, hex(rec(uc, t)[1]))
    tempo(uc, 90)
    pad(uc, 12)
    pad(uc, 12)
    out(uc)
    check("Follow at the tempo it took: speed 1", [w for w in writes() if w[1] == t][:2] == [(("p", 0), t, 1 << 20), (("p", 2), t, 0)], writes())
    tempo(uc, 120)

    pad(uc, 0)
    check("pad 1: the stock's handler", STOCK == [0], STOCK)
    first = 20 if REP["granular"].get("scan_each") else 17       # pads 18-20 copy Granular's settings
    pad(uc, first)
    check(f"pad {first + 1}: the stock's handler", STOCK == [first], STOCK)
    page(uc, False)
    out(uc)
    uc.mem_write(OUT, bytes(69 * 4))
    call(uc, int(R["prev"]["prev_out"], 16), C.CTRL, OUT, FRAME)
    a = struct.unpack("<69I", uc.mem_read(OUT, 69 * 4))
    b = out(uc)
    check("not Sample mode: the lights as the rest of the chain drew them", a == b)

    uc.mem_write(int(BR["upload"], 16), bytes([1]))
    sel(uc, o)
    pad(uc, 8)
    out(uc)
    check("a sample upload running: nothing written", writes() == [], writes())
    uc.mem_write(int(BR["upload"], 16), bytes([0]))
    out(uc)
    check("after it: the other track's words", writes()[-5:] == on_words(o, 1 << 20, 0) or any(w[1] == o for w in writes()), writes())

    # a Granular track: the length pads set Scan
    call(uc, KER["c_gr_runtime_mode"], GSTATE, o, 1)
    out(uc)
    call(uc, KER["c_gr_route_word"], GSTATE, o)
    route = uc.reg_read(UC_ARM_REG_R0)
    check("track 6 turns Granular: Granular's words 0, 2 and 15 back, then Granular's own route word 3", [w for w in writes() if w[1] == o] ==
          [(("p", 0), o, o + 1), (("p", 2), o, 0), (("p", 15), o, GR_KEY), (("c", 3), o, route)] and route in (0, 1), (route, writes()))
    # Granular's first setup, with track 1 stretching (stretch's tags) and track t on stretch here
    stretched = u32(uc, SLOT) & 0xFF
    SNAP.update({SNAP_HOST + 8 * k: 0x674732 for k in range(8)})
    SNAP[SNAP_HOST] = 0x674132
    flags = lambda: u32(uc, GSTATE + 184)
    ET.DSPW.clear()
    for _ in range(40):
        call(uc, KER["c_gr_runtime_frame"], GSTATE, 1, 0)
    w = writes()
    check("Granular's first setup with track 1 showing stretch's tags: it runs (another track's acknowledgement)",
          stretched >> t & 1 and not stretched >> o & 1 and flags() & 2, (hex(stretched), hex(flags())))
    check("its setup leaves the stretched track's route words and words 0, 2 and 15", not [x for x in w if x[1] == t and
          (x[0][0] == "c" or x[0][1] in (0, 2, 15))] and any(x[1] == t and x[0] == ("p", 1) for x in w), [x for x in w if x[1] == t])
    word3 = 0 if json.loads((Path(sys.argv[2]).parent / "manifest.json").read_text())["report"]["granular"].get("oneshot_scan") else 1
    check("its setup writes another track's route words", ((("c", 3), 3, word3) in w) and ((("c", 0), 3, 0) in w), w[:12])
    SNAP.clear()
    sample(uc, o, 11, 96000)
    page(uc, True)
    out(uc)
    out(uc)
    pad(uc, 12)
    call(uc, KER["c_gr_runtime_scan"], GSTATE, o, 0xFFFFFFFF)
    scan = uc.reg_read(UC_ARM_REG_R0)
    import math
    want = 1024 + math.isqrt((1 << 19) * 96000 // 96000)
    check(f"Granular: pad 13 (1 bar = 96,000 samples, the region 96,000): Scan {want} (sixteenths)", scan == want, scan)
    f = out(uc)
    red = off_red(uc, full, lo)
    check("Granular: pad 9 red (stretch off), pad 10 dark, pad 13 full, pad 17 Granular's green",
          f[8] == red and f[9] == 0 and f[12] == scl(RGB[3], full) and f[16] == scl(GR_ON_RGB, full),
          [hex(v) for v in f[8:17]])
    if REP["granular"].get("scan_each"):
        config, setting = GSTATE + 168 + o, GSTATE + 292 + o
        cv = lambda: uc.mem_read(config, 1)[0]  # noqa: E731
        sv = lambda: uc.mem_read(setting, 1)[0]  # noqa: E731
        c0, s0 = cv(), sv()
        uc.mem_write(config, bytes([c0 & ~32 & ~8])); uc.mem_write(setting, bytes([s0 & ~16]))
        f = out(uc)
        triggered = f[17] == scl(WHITE, full) and f[18] == 0 and f[19] == scl(WHITE, full)
        pad(uc, 17); pad(uc, 18); f = out(uc)
        textured = cv() & 32 and cv() & 8 and f[17] == scl(AMBER, full) and f[18] == scl(0x9EFF59, full)
        pad(uc, 18); pad(uc, 19); f = out(uc)
        back = not cv() & 8 and sv() & 16 and f[18] == scl(0x9EFF59, full // 4) and f[19] == scl(AMBER, full)
        uc.mem_write(config, bytes([cv() & ~32])); pad(uc, 18)
        guarded = not cv() & 8
        check("Sample mode pads 18-20 as Granular's settings: Textured / Triggered, Retrigger (Textured only), Scan length",
              triggered and textured and back and guarded, (triggered, textured, back, guarded, [hex(v) for v in f[16:20]]))
        if REP["stretch"]["arm"]["scan_lock"].get("off_match") and not REP["stretch"]["arm"]["scan_lock"].get("sample_hide"):
            on = cv()
            uc.mem_write(config, bytes([on & ~3 & ~32])); s1 = sv()
            pad(uc, 17); pad(uc, 19); f = out(uc)
            check("Granular off: Sample mode pads 18-20 shown and set ahead (Textured, Scan length)",
                  cv() & 32 and not cv() & 3 and sv() == s1 ^ 16 and f[17] == scl(AMBER, full) and STOCK == [],
                  (hex(cv()), hex(sv()), [hex(v) for v in f[17:20]], STOCK))
            uc.mem_write(config, bytes([on])); uc.mem_write(setting, bytes([s1]))
        if REP["stretch"]["arm"]["scan_lock"].get("sample_hide"):
            on = cv()
            uc.mem_write(config, bytes([on & ~3 | 32])); a = out(uc)[17:20]
            uc.mem_write(config, bytes([on & ~3 & ~32 | 8])); uc.mem_write(setting, bytes([sv() ^ 16])); b = out(uc)[17:20]
            before = (cv(), sv()); passed = []
            for k in (17, 18, 19):
                pad(uc, k); passed += STOCK
            check("Granular off: Sample mode pads 18-20 not drawn, presses go to the stock, no setting changes",
                  a == b and passed == [17, 18, 19] and (cv(), sv()) == before, ([hex(v) for v in a], [hex(v) for v in b], passed))
            uc.mem_write(config, bytes([on])); uc.mem_write(setting, bytes([sv() ^ 16]))
        uc.mem_write(config, bytes([c0])); uc.mem_write(setting, bytes([s0]))
    tempo(uc, 60)
    out(uc)
    call(uc, KER["c_gr_runtime_scan"], GSTATE, o, 0xFFFFFFFF)
    scan2 = uc.reg_read(UC_ARM_REG_R0)
    want2 = 1024 + math.isqrt((1 << 19) * 96000 // 192000)
    check(f"Granular: tempo 60: Scan follows ({want2})", scan2 == want2, scan2)
    call(uc, KER["c_gr_runtime_scan"], GSTATE, o, 1100)
    tempo(uc, 120)
    out(uc)
    call(uc, KER["c_gr_runtime_scan"], GSTATE, o, 0xFFFFFFFF)
    check("Granular: Scan turned by hand: it no longer follows", uc.reg_read(UC_ARM_REG_R0) == 1100, uc.reg_read(UC_ARM_REG_R0))
    pad(uc, 12)
    call(uc, KER["c_gr_runtime_scan"], GSTATE, o, 0xFFFFFFFF)
    check("Granular: pad 13 again sets Scan", uc.reg_read(UC_ARM_REG_R0) == want, uc.reg_read(UC_ARM_REG_R0))
    if R.get("clock_lock"):
        call(uc, C.PARAM_GET, u32(uc, 0x2003C410), 0)
        position = uc.reg_read(UC_ARM_REG_R0)
        home = lambda: [v >> 15 & 1 for (kind, track, v) in writes() if kind == ("p", 13) and track == o]   # noqa: E731

        def at(ticks):
            uc.mem_write(position, struct.pack("<I", ticks))
            out(uc)
            return home()
        at(100); at(100)
        inside, cross, after, still = at(150), at(193), at(200), at(200)
        check("Granular clock: pad 13 (1 bar = 96 ticks): no restart inside a bar, a restart on crossing bar 3, released next frame",
              inside == [] and cross == [1] and after == [0] and still == [], (inside, cross, after, still))
        restart, freed = at(0), at(5)
        check("Granular clock: playback from the start restarts the sweep", restart == [1] and freed == [0], (restart, freed))
        call(uc, KER["c_gr_runtime_scan"], GSTATE, o, 1100)
        check("Granular clock: Scan turned by hand: no restarts", 1 not in at(300) + at(400), home())
        call(uc, KER["c_gr_runtime_scan"], GSTATE, o, want)
        sweeps(uc, o, position, bool(R.get("scan_lock")))
    pad(uc, 12)
    call(uc, KER["c_gr_runtime_scan"], GSTATE, o, 0xFFFFFFFF)
    back = uc.reg_read(UC_ARM_REG_R0)
    f = out(uc)
    check("Granular: the chosen pad again: Scan back to 1100, the pad dim, no Scan length kept",
          back == 1100 and f[12] == scl(RGB[3], lo) and not rec(uc, o)[1] & 0x70, (back, hex(f[12]), hex(rec(uc, o)[1])))
    out(uc)
    call(uc, KER["c_gr_runtime_scan"], GSTATE, o, 0xFFFFFFFF)
    check("Granular: released: Scan no longer follows", uc.reg_read(UC_ARM_REG_R0) == 1100, uc.reg_read(UC_ARM_REG_R0))

    # pad 17: Granular on / off; Granular and stretch turn each other off
    def granular_on():
        call(uc, KER["c_gr_stretch_switch"], GSTATE, o, 0xFFFFFFFF)
        return uc.reg_read(UC_ARM_REG_R0)
    before = rec(uc, o)[1]
    pad(uc, 12)
    r0 = rec(uc, o)[1] & ~ON
    check("Granular: pad 13: Scan's 1 bar in its own bits (4-6), stretch's untouched",
          r0 & 0x70 == 3 << 4 and rec(uc, o)[1] & ~0x70 == before & ~0x70, (hex(before), hex(rec(uc, o)[1])))
    STOCK.clear()
    pad(uc, 8)
    check("Granular on, pad 9: Granular off, stretch on with the kept length", not granular_on() and rec(uc, o)[1] == ON | r0 and STOCK == [],
          (granular_on(), hex(rec(uc, o)[1]), STOCK))
    f = out(uc)
    check("Granular off: pad 17 Granular's red", f[16] == scl(GR_OFF_RGB, full), hex(f[16]))
    pad(uc, 16)
    check("pad 17: Granular on, stretch off, the length kept", granular_on() and rec(uc, o)[1] == r0 and STOCK == [],
          (granular_on(), hex(rec(uc, o)[1]), STOCK))
    pad(uc, 16)
    check("pad 17 again: Granular off, stretch stays off", not granular_on() and rec(uc, o)[1] == r0, (granular_on(), hex(rec(uc, o)[1])))
    pad(uc, 8)
    pad(uc, 16)
    f = out(uc)
    call(uc, KER["c_gr_runtime_scan"], GSTATE, o, 0xFFFFFFFF)
    scan3 = uc.reg_read(UC_ARM_REG_R0)
    check("pad 9 then pad 17: Granular on again: pad 13 still chosen, Scan where it was", granular_on() and f[12] == scl(RGB[3], full)
          and scan3 == want and rec(uc, o)[1] & 0x70 == 3 << 4, (hex(f[12]), scan3, hex(rec(uc, o)[1])))

    if plus_gate:
        PLUS[0] = 0
        before = (granular_on(), rec(uc, o)[1])
        f = out(uc)
        pad(uc, 16)
        check("Plus file missing: pad 17 dark and does nothing", f[16] == 0 and (granular_on(), rec(uc, o)[1]) == before and STOCK == [],
              (hex(f[16]), before, granular_on(), STOCK))
        PLUS[0] = 0x1500

    print("FAILED: " + ", ".join(ET.FAILS) if ET.FAILS else "ALL PASS")
    return 1 if ET.FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
