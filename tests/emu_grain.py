"""Emulation of grain_rp.py and Track +'s granular page (tmenu gran, pageclear gran) on a built image (MIT; Circuit Rhythm 5706).

    python tests/emu_grain.py STOCK.bin BUILT.bin RAM.bin        (RH_BUILD = the build's folder, else BUILT's)

Checks the engine's words to core 0 (READY only; all after a change or a new upload, else two a frame; the model's values), pad 29 (on
for the selected track from another page, off / moved on the page, its light), the knobs (128 a click, Shift fine on K1-K4, Shift +
K5-K8 the second layer, the limits, Clear's default, the bar, the lights, the stock's knobs untouched), the note-on's note, the
project's block, and the resets (Clear + pad 29, Clear + pad 32 on the granular track and on another).
"""
import struct
import sys

import emu_tmenu as E
from emu_tmenu import T, C, check, b8, u32, led, out, pad, unpad, knob, tap, press, release, setup, sel, scl, call
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC
import grain_rp as GR
import granular0 as G
import rhbuild

GL = {k: int(v, 16) for k, v in E.MAN["report"]["grain"]["labels"].items()}
READY_AT = int(E.MAN["report"]["cthresh"]["slot"], 16) + 1
SHIFT_RGB, G_RGB = T.SHIFT_RGB, T.G_RGB
PAD_G = T.PAD_PAGE0 + T.PAGE_G                                     # pad 29 (0-based 28)


def c0_words():
    """{X address: word} of core 0's writes so far, the last of each; and the list in order"""
    ws = [(y, (x >> 8) & 0xFFFFFF) for c, x, y in E.DSPW if c == 0]
    return dict(ws), ws


def main():
    stock, fw, ram = (open(p, "rb").read() for p in sys.argv[1:4])
    head = rhbuild.bl_target(bytearray(fw), C.LED_CALLS[0])
    E.HEAD = head
    E.STOCK_CLR = E.stock_clear_rgb(stock, ram)
    blue, red = E.STOCK_CLR
    uc = setup(fw, ram)
    s = sel(uc)
    other = (s + 1) % 8
    tc = u32(uc, T.COLOURS + 4 * T.TRK_SLOTS[s])
    pc = scl(G_RGB, T.KNOB_LVL)

    def r0(): return uc.reg_read(E.UC_ARM_REG_R0)
    def val(k): call(uc, GL["c_grval"], 0, k); return r0()
    def vals(): return [val(k) for k in range(12)]
    def trk(): call(uc, GL["c_grtrk"]); return r0()
    def blk(): call(uc, GL["c_grblk"]); return r0()
    def frame(): led(uc, head)
    def shift(on): uc.mem_write(E.ptr(uc, u32(uc, C.CTRL + 0xC), 0), bytes([1 if on else 0]))
    def stock_knobs(): return [E.kval(uc, s, k) for k in range(8)] + [E.kval(uc, s, T.FINE[k]) for k in T.FINE]
    def want_words(t1):
        w = {G.GB + GR.IDX[k]: GR.model_engine(v, k) & 0xFFFFFF for k, v in enumerate(vals())}
        w[G.GB + G.P_KEY], w[G.GB + G.P_TRK] = G.KEY, t1
        return w

    # ---- the words to core 0
    check("no project block yet: off, the defaults", trk() == 0 and vals() == list(GR.DEF), (trk(), vals()))
    uc.mem_write(READY_AT, b"\x00")
    E.DSPW.clear(); frame(); frame()
    check("no program upload seen: nothing to core 0", c0_words()[1] == [], len(c0_words()[1]))
    uc.mem_write(READY_AT, bytes([GR.READY]))
    E.DSPW.clear(); frame()
    got, order = c0_words()
    check("READY: all the engine's words in one frame (the track last), as the model's", got == want_words(0) and
          order[-1][0] == G.GB + G.P_TRK and len(order) == GR.NW - 1, ({hex(a): hex(w) for a, w in got.items()}, len(order)))
    E.DSPW.clear(); frame()
    check("  the next frame: two words in turn", len(c0_words()[1]) == 2, len(c0_words()[1]))
    seen = set()
    for _ in range(GR.NW):
        E.DSPW.clear(); frame(); seen |= set(c0_words()[0])
    check(f"  {GR.NW} frames: every word again (the note none: no note word)", seen == set(want_words(0)), sorted(hex(a) for a in seen))
    uc.mem_write(READY_AT, b"\xB1")
    E.DSPW.clear(); frame()
    check("the mode 1 program: nothing to core 0", c0_words()[1] == [])
    uc.mem_write(READY_AT, bytes([GR.READY]))
    E.DSPW.clear(); frame()
    check("  READY again: all the words at once", len(c0_words()[1]) == GR.NW - 1, len(c0_words()[1]))

    # ---- pad 29
    tap(uc, s); frame()
    pad(uc, PAD_G); unpad(uc, PAD_G)
    E.DSPW.clear(); frame()
    got = c0_words()[0]
    check(f"pad 29 from the editor: the granular page, on for track {s + 1}, its words sent", b8(uc, T.O_PAGE) == T.PAGE_G and trk() == s + 1
          and got.get(G.GB + G.P_TRK) == s + 1 and got == want_words(s + 1), (b8(uc, T.O_PAGE), trk(), got.get(G.GB + G.P_TRK)))
    b = bytes(uc.mem_read(blk(), GR.BLK_LEN))
    check("  the project's block: Circuit Remix's (GP, check, track + 1, 12 values)", b == GR.model_block(s + 1, vals()), b.hex())
    m = E.dim_mul(uc)
    full, dim = scl(G_RGB, 255 * m >> 8), scl(G_RGB, T.WHITE * m >> 8)
    o = out(uc)
    check("  pad 29 full (shown, on)", o[PAD_G] == full, f"{o[PAD_G]:06x}")
    pad(uc, PAD_G); unpad(uc, PAD_G); frame(); o = out(uc)
    check("pad 29 again on the page: off, pad 29 dim, the page kept", trk() == 0 and o[PAD_G] == dim and b8(uc, T.O_PAGE) == T.PAGE_G,
          (trk(), f"{o[PAD_G]:06x}"))
    pad(uc, PAD_G); unpad(uc, PAD_G)
    check("  again: on", trk() == s + 1, trk())
    tap(uc, other); frame()
    check(f"track {other + 1} selected: the page kept, the granular still on track {s + 1}", b8(uc, T.O_PAGE) == T.PAGE_G and trk() == s + 1
          and sel(uc) == other, (b8(uc, T.O_PAGE), trk(), sel(uc)))
    o = out(uc)
    check("  pad 29 dim (the selected track is not the granular one)", o[PAD_G] == dim, f"{o[PAD_G]:06x}")
    pad(uc, PAD_G); unpad(uc, PAD_G); frame(); o = out(uc)
    check(f"  pad 29: the granular moved to track {other + 1}, pad 29 full", trk() == other + 1 and o[PAD_G] == full, (trk(), f"{o[PAD_G]:06x}"))
    pad(uc, PAD_G); unpad(uc, PAD_G); frame()
    s, other = other, s                                            # (the emulator cannot select an earlier track again: go on here)
    tc = u32(uc, T.COLOURS + 4 * T.TRK_SLOTS[s])
    pad(uc, T.PAD_PAGE0); unpad(uc, T.PAD_PAGE0); frame()
    check("the editor page: the granular stays as it was (off)", trk() == 0 and b8(uc, T.O_PAGE) == 0, trk())
    pad(uc, PAD_G); unpad(uc, PAD_G); frame()
    check(f"  pad 29 from the editor again: on for track {s + 1}", trk() == s + 1, trk())

    # ---- the knobs
    sk, want = stock_knobs(), vals()
    knob(uc, 0, 3); want[0] += 384
    check("K1 +3: the size 128 a click, K1 shown, the stock's knobs untouched", vals() == want and b8(uc, T.O_KNOB) == 1 and stock_knobs() == sk,
          (vals(), want))
    shift(True); knob(uc, 0, 3); shift(False); want[0] += 12
    check("Shift + K1 +3: 4 a click (fine)", vals() == want, vals()[0])
    shift(True); knob(uc, 4, 2); shift(False); want[8] += 256
    check("Shift + K5 +2: the fine pitch (value 8) 128 a click, the pitch kept", vals() == want, (vals()[4], vals()[8]))
    for k, v in ((5, 10), (6, -1)):
        shift(True); knob(uc, k, v); shift(False)
    want[9] = min(16383, want[9] + 1280); want[10] = max(0, want[10] - 128)
    check("Shift + K6 +10, Shift + K7 -1: the zone (held at 16383), the reverse chance (held at 0)", vals() == want, (vals()[9], vals()[10]))
    knob(uc, 7, -200); want[7] = 0
    check("K8 -200: the window held at 0", vals() == want, vals()[7])
    knob(uc, 7, 300); want[7] = 16383
    check("K8 +300: held at 16383", vals() == want, vals()[7])
    E.DSPW.clear(); frame()
    check("  the next frame: all the words, as the model's", c0_words()[0] == want_words(s + 1), {hex(a): hex(w) for a, w in c0_words()[0].items()})
    check("  the project's block follows", bytes(uc.mem_read(blk(), GR.BLK_LEN)) == GR.model_block(s + 1, vals()))
    check("  the stock's knobs untouched", stock_knobs() == sk, (stock_knobs(), sk))

    # the bar and the lights
    for k in range(8):
        uc.mem_write(E.SLOT + T.O_KNOB, bytes([k + 1]))
        for sh in (False, True):
            shift(sh)
            i = k + 4 if sh and k >= 4 else k
            v = val(i)
            frame(); o = out(uc)
            kind = "mid" if GR.BIP[i] else "fine"
            w = E.bar_rgb(uc, s, kind, v >> 7, v, col=SHIFT_RGB if sh and k >= 4 else None)
            check(f"K{k + 1} shown{', Shift' if sh else ''}: the bar value {i} ({v})", list(o[16:24]) == w,
                  ([f"{x:06x}" for x in o[16:24]], [f"{x:06x}" for x in w]))
            wl = [(SHIFT_RGB if sh and j >= 4 else tc) if j == k else (scl(SHIFT_RGB, T.KNOB_LVL) if sh and j >= 4 else pc) for j in range(8)]
            lights = list(o[T.LED_KNOB0:T.LED_KNOB0 + 8])
            check(f"  knob lights: K{k + 1} {'white' if sh and k >= 4 else 'the track colour'}, the others the page's"
                  f"{' (K5-K8 white)' if sh else ''}", lights == wl, [f"{x:06x}" for x in lights])
    shift(False)
    uc.mem_write(E.ptr(uc, C.TRANSPORT, 1), b"\x01")
    knob(uc, 1, 1); frame(); o = out(uc)
    uc.mem_write(E.ptr(uc, C.TRANSPORT, 1), b"\x00")
    check("Record armed, K2 turned: the bar in the track's colour (nothing records here)", list(o[16:24]) == E.bar_rgb(uc, s, "fine", val(1) >> 7, val(1)))

    # Clear + a knob
    knob(uc, 1, 20)
    E.clr_turn(uc, 1, T.CLR_N - 1, keep=True)
    check(f"Clear held, K2 {T.CLR_N - 1} clicks right: the density kept", val(1) != GR.DEF[1], val(1))
    o = E.clr_turn(uc, 1, 1, keep=True)
    check(f"  the {T.CLR_N}th click: its default ({GR.DEF[1]}), K2 the stock's blue", val(1) == GR.DEF[1] and o[1] == blue, (val(1), f"{o[1]:06x}"))
    o = E.clr_turn(uc, 2, T.CLR_N, -1, keep=True)
    check("  K3 left: nothing moved, K3 the stock's red", o[2] == red, f"{o[2]:06x}")
    E.clr_turn(uc, 0, 0)
    shift(True); knob(uc, 7, -200); shift(False)
    check("Shift + K8 -200: the gate 0 (always on, a drone)", val(11) == 0, val(11))
    shift(True); E.clr_turn(uc, 7, T.CLR_N); shift(False)
    check(f"Shift + Clear + K8 {T.CLR_N} right: the gate at its default ({GR.DEF[11]})", val(11) == GR.DEF[11], val(11))

    # ---- the note-on
    trig = []
    def hk(u, a, n, d):
        trig.append(True)
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE, hk, None, GR.TRIG, GR.TRIG + 1)
    msg = 0x2004FC00
    for t, note in ((s, 67), (other, 50)):
        uc.mem_write(msg, struct.pack("<Ii", t, (note - 60) << 16))
        E.DSPW.clear(); trig.clear()
        call(uc, GL["c_grnote"], msg)
        got = c0_words()[0]
        if t == s:
            check(f"note-on {note} on the granular track: the note to the engine (+7), then the stock's trigger",
                  got == {G.GB + G.P_NOTE: 7} and trig == [True], (got, trig))
        else:
            check(f"note-on {note} on another track: nothing to core 0, the stock's trigger", got == {} and trig == [True], (got, trig))

    # ---- the resets
    knob(uc, 0, 9); knob(uc, 3, -5)
    held = u32(uc, C.CTRL + T.HELD)
    uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", held | 1 << 23))
    pad(uc, PAD_G); unpad(uc, PAD_G)
    uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", held))
    check("Clear + pad 29: the 12 defaults, still on, the page kept", vals() == list(GR.DEF) and trk() == s + 1 and b8(uc, T.O_PAGE) == T.PAGE_G,
          (vals(), trk()))
    knob(uc, 0, 9)
    before = vals()
    call(uc, int(E.MAN["report"]["pageclear"]["labels"]["c_pcreset"], 16), other, 6)
    check(f"all pages reset on track {other + 1} (not granular): the granular's values kept", vals() == before, vals())
    uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", held | 1 << 23))
    pad(uc, 31); unpad(uc, 31)
    uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", held))
    check(f"Clear + pad 32 on track {s + 1} (the granular one): its defaults too", vals() == list(GR.DEF), vals())
    print("ALL PASS" if not E.FAILS else f"{len(E.FAILS)} FAILED")
    sys.exit(1 if E.FAILS else 0)


if __name__ == "__main__":
    main()
