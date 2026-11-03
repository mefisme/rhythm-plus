"""Unicorn test of tmenu.py on a build with it (RH_BUILD, default a0012) and the RAM dump: tap / hold open and close, the menu following
the selection, buttons that close it, modifiers, pads 1-16 selecting without adding or removing steps, pads 17-32 taken and released,
the LED frame (track buttons, side buttons, pad 25, the knob's LED), the RGB after the output stage (the bar in the track's colour,
fine K2 / K3, the centre knobs, the stock's dimmed LEDs, red while Record is armed and a knob turns or a step is held), the held step's
and the playhead's pads while recording, a closed menu as the stock, and (stockplus builds) the Stock+ page: its page bits, K1-K4, the
bar, the knob lights and the words written to core 1; (fpage builds) K5 / K6 empty on Stock+, five values on pad 29's page, one knob each.

    python tests/emu_tmenu.py STOCK.bin BUILT.bin RAM.bin
"""
import json
import os
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
os.environ.setdefault("RH_BUILD", Path(sys.argv[2]).parent.name if len(sys.argv) > 2 else "a0021")   # the build of the image tested
os.environ.setdefault("RH_PROBES", "0")
MAN = json.loads((HERE / "firmware" / os.environ["RH_BUILD"] / "manifest.json").read_text())
SP = MAN["report"]["tmenu"].get("stockplus", False)
FP = MAN["report"]["tmenu"].get("fpage", False)
GRAN = MAN["report"]["tmenu"].get("gran", False)
DSPW = []                                                       # (gran) every DSP word write: (core, word << 8, address)
CLICK = MAN["report"]["tmenu"].get("click", False)
TWO = MAN["report"]["tmenu"].get("twoview", False)
SHL = MAN["report"]["tmenu"].get("shiftled", False)
BOUNCE = MAN["report"]["tmenu"].get("bounce", False)
PERPAGE = MAN["report"]["tmenu"].get("perpage", False)
SHAPES = MAN["report"]["tmenu"].get("shapes", False)
SHAPEBAR = MAN["report"]["tmenu"].get("shapebar", False)
FILTPAGE = MAN["report"]["tmenu"].get("filtpage", False)
K78W = MAN["report"]["tmenu"].get("k78white", False)
VOLPAGE = MAN["report"]["tmenu"].get("volpage", False)
VOLT = MAN["report"].get("pshape", {}).get("vol", False)
SB = "syncbar" in MAN["report"]
SB_RATES = tuple(MAN["report"]["syncbar"]["rates"]) if SB else ()   # this build's mirrored rates
SCANFX = MAN["report"]["tmenu"].get("scanfx", False)   # the scan on pad 28's K7 / K8, pad 27's K7 / K8 dark
SPN = MAN["report"]["tmenu"].get("spn") or (6 if SCANFX else 8)   # the pitch page's live knobs
PXRAND = MAN["report"]["tmenu"].get("pxrand", False)   # the pitch page's K7: fshape's random pitch (value 26)
GLIDE = MAN["report"]["tmenu"].get("glide", False)     # the pitch page's K8: fshape's glide time (value 27)
FADE = MAN["report"]["tmenu"].get("fade", False)       # the pitch page's Shift + K7: fshape's LFO fade-in (value 28)
FCLR = MAN["report"]["tmenu"].get("fclr", False)       # the filter page's K7 / K8: the Clear lights
MIXER = 0x2004E090                                 # the Mixer's view (vtable 0x08067918): one off the track views
os.environ["RH_STOCKPLUS"] = "1" if SP else "0"
os.environ["RH_TMCLICK"] = str(MAN["report"].get("tmenu", {}).get("tmclick", int(bool(MAN["report"].get("tmenu", {}).get("click")))))
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
os.environ["RH_PAGECLEAR"] = "1" if MAN["report"].get("tmenu", {}).get("pageclear") else "0"
os.environ["RH_TRACKRESET"] = "1" if MAN["report"].get("trackreset") else "0"
os.environ["RH_GRAIN"] = "1" if "grain" in MAN["report"] else "0"
os.environ["RH_PSHAPE"] = "1" if "pshape" in MAN["report"] else "0"
os.environ["RH_FSHAPE"] = "1" if "fshape" in MAN["report"] else "0"
import ourram  # noqa: E402,F401
with ourram.remix_imports():
    import stockplus as SPM  # noqa: E402
    import cthresh as TH  # noqa: E402
import countin as C  # noqa: E402
import rhbuild  # noqa: E402
import rhstate  # noqa: E402
import tmenu as T  # noqa: E402
import rpasm  # noqa: E402
rpasm.use()
T.PAD_PAGE0 = MAN["report"]["tmenu"].get("page0", T.PAD_PAGE0)
T.X_IDX = tuple(MAN["report"]["tmenu"].get("x_idx", T.X_IDX))
T.X_KNOBS = len(T.X_IDX)
_maps = MAN["report"]["tmenu"].get("maps")
if _maps:                                                       # this build's knob order (depthfirst)
    T.SP_MAP, T.F_MAP, T.V_MAP = tuple(_maps["sp"]), tuple(_maps["f"]), tuple(_maps["v"])
    T.SP_MIDK = tuple(k for k, i in enumerate(T.SP_MAP) if i in (0, 2, 7))
MIXPAGE = MAN["report"]["tmenu"].get("mixpage", False)
if MIXPAGE:                                                     # the mix page's eight knobs, as install set them
    T.apply_mixpage()
    T.V_MAP = tuple(_maps["v"])
NOCRUSH = bool(MAN["report"].get("stockplus", {}).get("no_crush"))
from emu_playfix import RAM, call, machine  # noqa: E402
from thumb import h, mov_reg, movt, movw, pop_list, push_list  # noqa: E402
from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3  # noqa: E402

LB = {k: int(v, 16) for k, v in MAN["report"]["tmenu"]["labels"].items()}
import stockplus_rp  # noqa: E402
if SB:
    import syncbar as SBM  # noqa: E402
    SPM.div_index = SBM.div_index                             # the models' synced steps in syncbar's order
FSHIFT = T.F_SHIFT2 if SB else T.F_SHIFT


def uiv(i, v):
    """(syncbar) value i as its knob shows it: a rate mirrored"""
    return SBM.mirror(v) if SB and i in SB_RATES else v


def turned(i, v, d):
    """value i stored after d clicks from v"""
    return uiv(i, max(0, min(16383, uiv(i, v) + d * 128)))


def clicks_to(i, cur, target):
    return (uiv(i, target) - uiv(i, cur)) // 128


def sync_pads(uc, t, i, v, page_rgb):
    """(syncbar) a synced rate's bar: one pad a step, the 2nd sweep in the page's colour; None when not synced"""
    u = uiv(i, v)
    if not (SB and i in SB_RATES) or SBM.step_of(u) is None:
        return None
    n = SBM.step_of(u)
    w = [0] * 8
    w[n & 7] = scl(page_rgb if n >= 8 else u32(uc, T.COLOURS + 4 * T.TRK_SLOTS[t]), 255 * dim_mul(uc) >> 8)
    return w
DEFS = stockplus_rp.defaults(MAN["report"].get("stockplus", {}).get("lfodef") or False)   # the 12 values' defaults in this build
C_RST = int(MAN["report"]["rhstate"]["labels"]["c_rst"], 16)
SLOT = int(MAN["report"]["tmenu"]["slot"], 16)
PREV_OUT = int(MAN["report"]["tmenu"]["prev_out"], 16)
PREV_LED = int(MAN["report"]["tmenu"]["prev_led"], 16)
PAGES = [int(c, 16) for c in MAN["report"]["tmenu"]["pages"]]
NP = len(PAGES)
PADMAP = MAN["report"]["tmenu"].get("padmap") or list(range(NP))   # the page on page pad j (T.PAD_PAGE0 + j); None = no page


def pp(page): return T.PAD_PAGE0 + PADMAP.index(page)


SPB = rhstate.ST + rhstate.OFF["stockplus"][0] if SP else None
SPL = {k: int(v, 16) for k, v in MAN["report"]["stockplus"]["labels"].items()} if SP else {}
FRAME, OUT = 0x2004FD00, 0x2004FA00
STUB = 0x2004FE00                                  # sets r5 (the track) from r3, then calls c_tmrec
DELAY = 0x08024150                                 # the RTOS delay(ms): it waits for ticks the emulation never makes
US_WAIT, MS_WAIT = 0x0802366C, 0x08024B90         # busy-waits on SysTick's counter, which the emulation never moves (the second returns r3)
FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAILS.append(name)


def u32(uc, a): return struct.unpack("<I", uc.mem_read(a, 4))[0]
def b8(uc, o): return uc.mem_read(SLOT + o, 1)[0]
def tick(uc, ms): uc.mem_write(C.HAL_TICK, struct.pack("<I", u32(uc, C.HAL_TICK) + ms))
def press(uc, bid): call(uc, C.BTN_ENTRY, C.CTRL, bid)
def release(uc, bid): call(uc, C.BTN_RELEASE, C.CTRL, bid)
def pad(uc, p, vel=100): call(uc, T.PP_ENTRY, C.CTRL, p, vel)
def unpad(uc, p): call(uc, T.PR_ENTRY, C.CTRL, p)
def knob(uc, k, d): call(uc, T.KN_ENTRY, C.CTRL, k, d & 0xFFFFFFFF)
def sel(uc): call(uc, LB["c_tmview"]); return uc.reg_read(UC_ARM_REG_R0)
def tap(uc, t): press(uc, t); tick(uc, 40); release(uc, t); tick(uc, 20)


def led(uc, head):
    uc.mem_write(FRAME, bytes(140))
    call(uc, head, C.CTRL, FRAME)
    return struct.unpack("<69H", uc.mem_read(FRAME, 138))


def out(uc, fn=None):
    uc.mem_write(OUT, bytes(69 * 4))
    call(uc, fn or LB["c_tmout"], C.CTRL, OUT, FRAME)
    return struct.unpack("<69I", uc.mem_read(OUT, 69 * 4))


def setup(fw, ram, built=True):
    uc = machine(fw, ram)
    from unicorn.arm_const import UC_ARM_REG_C1_C0_2, UC_ARM_REG_FPEXC
    uc.reg_write(UC_ARM_REG_C1_C0_2, uc.reg_read(UC_ARM_REG_C1_C0_2) | 0xF00000)
    uc.reg_write(UC_ARM_REG_FPEXC, 0x40000000)
    uc.mem_write(C.CTRL + 0x7C, struct.pack("<I", T.CONT))   # the track views on screen (the dump has none)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR)), None, US_WAIT, US_WAIT + 1)
    def ms_wait(u, a, n, d):
        u.reg_write(UC_ARM_REG_R0, u.reg_read(UC_ARM_REG_R3)); u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE, ms_wait, None, MS_WAIT, MS_WAIT + 1)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR)), None, DELAY, DELAY + 1)
    if GRAN:
        def wr16(u, a, n, d):
            DSPW.append((u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_R1), u.reg_read(UC_ARM_REG_R2)))
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
        uc.hook_add(UC_HOOK_CODE, wr16, None, 0x08031200, 0x08031201)
    if built:
        call(uc, C_RST)
    return uc


def pgb(uc):
    """(perpage) the project's page block: the record's tail + tmenu.PG_OFF"""
    import rhrec
    return u32(uc, rhrec.REC_OWNER) + rhrec.TAIL + T.PG_OFF


def ours(a):
    return rhstate.ST <= a < rhstate.HEAP_LIMIT or 0x20002B54 <= a < 0x20002B58


def ptr(uc, store, i):
    call(uc, C.PARAM_GET, store, i)
    return uc.reg_read(UC_ARM_REG_R0)


def kstore(uc, t): return u32(uc, C.CTRL + T.KSTORES + 4 * t)
def kval(uc, t, k): return uc.mem_read(ptr(uc, kstore(uc, t), k), 1)[0]
def kset(uc, t, k, v): uc.mem_write(ptr(uc, kstore(uc, t), k), bytes([v]))


def record(uc, rec, lane, value, track):
    """The automation message's recorder call, as at 0x0803655A: r0 rec, r1 lane, r2 value, r5 track."""
    a = STUB
    fn = LB["c_tmrec"] | 1
    code = (push_list([4, 5, 6], lr=True) + mov_reg(5, 3) + movw(4, fn & 0xFFFF) + movt(4, fn >> 16) + h(0x47A0)   # blx r4
            + pop_list([4, 5, 6], pc=True))
    uc.mem_write(a, bytes(code))
    call(uc, a, rec, lane, value, track)


def held_step(uc, t):
    so = u32(uc, T.CONT + T.STEPOBJ + 4 * t)
    return uc.mem_read(ptr(uc, u32(uc, so + 0x64), 1), 1)[0]


def fill(d, lg):
    return 0 if d <= 0 else 255 if d >= 1 << lg else (d << 8) >> lg


def scl(rgb, lvl):
    return sum((((rgb >> s) & 0xFF) * (lvl + 1) >> 8) << s for s in (0, 8, 16))


def tint(rgb, col):
    return scl(col, max(rgb & 0xFF, rgb >> 8 & 0xFF, rgb >> 16 & 0xFF))


def page_pads_want(uc, page, cyc):
    """Pads 25-32 after the output stage: pad 25, the separator, each page pad in its colour (full on the page shown, else dim), the
    rest dark."""
    m = dim_mul(uc)
    w = [cyc] + [0] * (T.PAD_PAGE0 - 25) + [0 if i is None else scl(PAGES[i], (255 if i == page else T.WHITE) * m >> 8) for i in PADMAP]
    return w + [0] * (8 - len(w))


def clear_red(uc):
    if MAN['report']['tmenu'].get('softclear'):
        return scl(u32(uc, T.COLOURS + 4 * 0x55), dim_mul(uc) - 1)
    return T.RED


def sel_rgb(uc, tc):
    """The selected track's number now: its colour, dark while bit BLINK_BIT of the tick is set."""
    if MAN['report']['tmenu'].get('trackpulse'):
        coefficient = u32(uc, T.COLOURS + 4 * 0x0A) & 255
        return scl(tc, 64 + ((255 - coefficient) * 192 >> 8))
    return 0 if u32(uc, C.HAL_TICK) >> T.BLINK_BIT & 1 else tc


def white_of(rgb):
    v = max(rgb & 0xFF, rgb >> 8 & 0xFF, rgb >> 16 & 0xFF)
    return v * 0x010101


def knob_lights(uc, shown):
    """The knob LEDs with no step held: the stock's codes; the shown knob's RGB the stock's, the others the page's colour at KNOB_LVL of the stock's
    brightness unless the stock's slot is red."""
    f = led(uc, PREV_LED)[T.LED_KNOB0:T.LED_KNOB0 + 8]
    so = out(uc, PREV_OUT)[T.LED_KNOB0:T.LED_KNOB0 + 8]
    fo = led(uc, HEAD)[T.LED_KNOB0:T.LED_KNOB0 + 8]
    o = out(uc)[T.LED_KNOB0:T.LED_KNOB0 + 8]
    kc = scl(PAGES[b8(uc, T.O_PAGE)], T.KNOB_LVL)
    want = [so[k] if k == shown or u32(uc, T.COLOURS + 4 * f[k]) == T.RED else tint(so[k], kc) for k in range(8)]
    return fo == f and list(o) == want, ([f"{x:06x}" for x in o], [f"{x:06x}" for x in want])


def dim_mul(uc):
    return T.DIM_MUL if u32(uc, ptr(uc, u32(uc, C.CTRL + T.O_DIM), T.P_DIM)) >> T.BIT_DIM & 1 else 256


def lane_addr(uc, t, k, step):
    rec = u32(uc, T.AUTO + T.AUTO_RECS + 4 * t)
    pat = uc.mem_read(ptr(uc, u32(uc, rec + T.REC_POS), 0), 1)[0]
    return u32(uc, rec + T.REC_PATS) + pat * T.PAT_SIZE + T.LANES + k * T.LANE_SIZE + step * T.MSTEPS


def want_bar(uc, t, k, step_val=None, red=False):
    """The 8 RGB words of row 4 the model expects for knob k of track t (step_val: a held step's own value; red: a recorded turn)."""
    v = kval(uc, t, k) if step_val is None else step_val
    v14 = v * 128 + (kval(uc, t, T.FINE[k]) if step_val is None else 0) if k in T.FINE else None
    return bar_rgb(uc, t, "fine" if k in T.FINE else "mid" if k in (0, 3) else "plain", v, v14, red)


def sp_index(k, shift=False):
    """Stock+ v2's value shown for knob k: K1-K4 their own; K5-K8 0-based 4..7, Shift 8..11; K6 the follow (9), Shift the type (5)."""
    if SHAPES:
        return T.FADE_V if FADE and shift and k == T.SP_RANDK - 1 else T.SP_MAP[k]
    if k < 4:
        return k
    if FP and k in T.SP_OWN:                               # (fpage) K5-K8 one value each, Shift or not
        return T.SP_OWN[k]
    if k == T.SP_K6:
        return T.SP_TYPE if shift else T.SP_FOLLOW
    return k + 4 if shift else k


def want_sp_bar(uc, t, k, shift=False):
    """Row 4 for Stock+'s knob k: SP_MIDS from the middle (the value >> 7), the others at 2048 a pad; Shift held on K5-K8: SHIFT_RGB."""
    i = sp_index(k, shift)
    v14 = shval(uc, t, i)
    w = sync_pads(uc, t, i, v14, PAGES[T.PAGE_SP])
    if w:
        return w
    v14 = uiv(i, v14)
    if SHAPEBAR and i in T.SHAPE_N:
        n = v14 * T.SHAPE_N[i] >> 14
        w = [0] * 8
        hi = PAGES[T.PAGE_SP] if SHAPEBAR == "page" else 0xFFFFFF
        w[n & 7] = scl(hi if n >= 8 else u32(uc, T.COLOURS + 4 * T.TRK_SLOTS[t]), 255 * dim_mul(uc) >> 8)
        return w
    kind = "mid" if i in T.SP_MIDS else "fine"
    if shift and k >= 4 and not FP:
        return bar_rgb(uc, t, kind, v14 >> 7, v14, col=T.SHIFT_RGB)
    return bar_rgb(uc, t, kind, v14 >> 7, v14)


def want_x_bar(uc, t, i):
    """(scanfx) row 4 for pad 28's value i: the shared bar code, the 2nd sweep in pad 28's colour"""
    v14 = shval(uc, t, i)
    w = sync_pads(uc, t, i, v14, PAGES[T.PAGE_X])
    if w:
        return w
    v14 = uiv(i, v14)
    return bar_rgb(uc, t, "mid" if i in T.SP_MIDS else "fine", v14 >> 7, v14)


def bar_rgb(uc, t, kind, v, v14, red=False, rest=0xFFFFFF, col=None):
    tc = T.RED if red else col if col is not None else u32(uc, T.COLOURS + 4 * T.TRK_SLOTS[t])
    m = dim_mul(uc)
    W = scl(T.RED if red else rest, T.WHITE * m >> 8)
    if kind == "fine":
        if v14 == 0:
            return [W] + [0] * 7
        lv = [fill(v14 - 2048 * i, 11) for i in range(8)]
        lv[0] = max(lv[0], T.MINF)
    elif kind == "mid":
        if v == 64:
            return [0, 0, 0, W, W, 0, 0, 0]
        lv = [0] * 8
        if v > 64:
            for j in range(4):
                lv[4 + j] = fill(v - 64 - 16 * j, 4)
        else:
            for j in range(4):
                lv[3 - j] = fill(64 - 16 * j - v, 4)
        for c in (3, 4):
            lv[c] = T.MARK if lv[c] == 0 else max(lv[c], T.MINF)
    else:
        if v == 0:
            return [W] + [0] * 7
        lv = [fill(v - 16 * i, 4) for i in range(8)]
        lv[0] = max(lv[0], T.MINF)
    return [scl(tc, x * m >> 8) for x in lv]


def spval(uc, t, k):
    call(uc, SPL["c_spval"], t, k)
    return uc.reg_read(UC_ARM_REG_R0)


def spb(uc): return uc.mem_read(SPB, 1)[0]


def shval(uc, t, k):
    """(shapes) the value the Stock+ page shows: the LFO's shape without K7's XOR; fshape's values (12 and up) through c_fsval"""
    if k >= 12:
        return flval(uc, t, k)
    return spval(uc, t, k) ^ (8192 if SHAPES and k == 6 else 0)


def bar_check(uc, head, s, k, name, step_val=None, red=False, sp=False, shift=False):
    led(uc, head)
    o = out(uc)
    w = want_sp_bar(uc, s, k, shift) if sp else want_bar(uc, s, k, step_val, red)
    check(name, list(o[16:24]) == w, ([f"{x:06x}" for x in o[16:24]], [f"{x:06x}" for x in w]))


def main():
    stock, fw, ram = (open(p, "rb").read() for p in sys.argv[1:4])
    head = rhbuild.bl_target(bytearray(fw), C.LED_CALLS[0])
    shead = rhbuild.bl_target(bytearray(stock), C.LED_CALLS[0])
    global HEAD, STOCK_CLR
    HEAD = head
    STOCK_CLR = stock_clear_rgb(stock, ram)

    uc, ref = setup(fw, ram), setup(stock, ram, built=False)
    s = sel(uc)
    check("the dump is in a track view", s < 8, s)
    other = (s + 1) % 8
    check("closed: the frame as the stock's", led(uc, head) == led(ref, shead))
    check("closed: the output stage's words as the stock's", out(uc) == out(uc, PREV_OUT))

    tap(uc, s); tap(ref, s)
    f = led(uc, head); o = out(uc)
    sf = led(ref, shead)
    check("tap on the selected track: open, sticky", b8(uc, T.O_OPEN) == 1 and b8(uc, T.O_STICKY) == 1)
    check("tracks not selected: white numbers (0x01)", all(f[32 + t] == T.COL_FULL for t in range(8) if t != s), f[32:40])
    check("the tracks' palette slots: the colours of their knob slots in the dump",
          all(u32(uc, T.COLOURS + 4 * T.TRK_SLOTS[t]) == u32(uc, T.COLOURS + 4 * (T.CODE_KNOB0 + 8 * t + k)) for t in range(8) for k in range(8)))
    tc = u32(uc, T.COLOURS + 4 * T.TRK_SLOTS[s])
    check(f"selected track: its colour {tc:06x} (flashing)", o[32 + s] == sel_rgb(uc, tc), f"{o[32 + s]:06x}")
    check("side buttons (LEDs 40-47): as the stock draws them", f[40:48] == sf[40:48], (f[40:48], sf[40:48]))
    check("pads 1-16: as the stock draws them", f[0:16] == sf[0:16], (f[0:16], sf[0:16]))
    check(f"pads 25 and 27-{26 + NP} white, pads 17-24 (the bar), 26 and {27 + NP}-32 dark in the frame", f[24] == T.COL_FULL and not any(f[25:T.PAD_PAGE0])
          and all(x == (0 if PADMAP[j] is None else T.COL_FULL) for j, x in enumerate(f[T.PAD_PAGE0:T.PAD_PAGE0 + NP])) and not any(f[16:24]) and not any(f[T.PAD_PAGE0 + NP:32]), f[16:32])
    dimw = scl(0xFFFFFF, T.WHITE * dim_mul(uc) >> 8)
    cyc = scl(tc, T.CYC_LVL)
    check(f"  after the output stage: pad 25 the track's colour at CYC_LVL ({cyc:06x}), pad 27 (the parameter editor, shown) full white,"
          f" 28-{26 + NP} dim in their pages' colours, 26 and the rest dark",
          list(o[24:32]) == page_pads_want(uc, 0, cyc) and o[T.PAD_PAGE0] == out(uc, PREV_OUT)[T.PAD_PAGE0], [f"{x:06x}" for x in o[24:32]])
    so = out(uc, PREV_OUT); o = out(uc)
    check("  the parameter editor: the other track numbers white as the stock's output", all(o[T.LED_TRK0 + t] == so[T.LED_TRK0 + t] == white_of(so[T.LED_TRK0 + t]) != 0
          for t in range(8) if t != s), [f"{x:06x}" for x in o[T.LED_TRK0:T.LED_TRK0 + 8]])
    tcs = [u32(uc, T.COLOURS + 4 * T.TRK_SLOTS[t]) for t in range(8)]
    lows = [scl(c, T.CYC_LVL) for c in tcs]
    check("  pad 25 at CYC_LVL: every channel of each of the 8 track colours kept (none drops to 0)",
          all((lo >> sh & 0xFF) >= 2 for c, lo in zip(tcs, lows) for sh in (0, 8, 16) if c >> sh & 0xFF), [f"{x:06x}" for x in lows])
    check("no knob turned: the bar (row 3) shows K1", list(o[16:24]) == want_bar(uc, s, 0),
          ([f"{x:06x}" for x in o[16:24]], [f"{x:06x}" for x in want_bar(uc, s, 0)]))
    ok, info = knob_lights(uc, 0)
    check("  knob LEDs: K1 (shown) the stock's (the track's colour), K2-K8 the page's colour at KNOB_LVL of the stock's brightness", ok, info)
    check("  K1's light in the track's colour", out(uc)[T.LED_KNOB0] != white_of(out(uc)[T.LED_KNOB0]), f"{out(uc)[T.LED_KNOB0]:06x}")
    code = led(uc, PREV_LED)[T.LED_KNOB0 + 1]
    keep = u32(uc, T.COLOURS + 4 * code)
    for rgb in (0x401008, 0x000000, T.RED):
        uc.mem_write(T.COLOURS + 4 * code, struct.pack("<I", rgb))
        ok, info = knob_lights(uc, 0)
        check(f"  the stock's colour of K2 set to {rgb:06x}: " + ("K2 the stock's red" if rgb == T.RED else "the others follow its brightness"), ok, info)
    uc.mem_write(T.COLOURS + 4 * code, struct.pack("<I", keep))
    check("other knob LEDs: as the stock draws them", f[T.LED_KNOB0 + 1:T.LED_KNOB0 + 8] == sf[T.LED_KNOB0 + 1:T.LED_KNOB0 + 8])
    w0 = out(uc)[T.LED_KNOB0]
    seen = []
    for _ in range(8):
        tick(uc, 64)
        led(uc, head); o = out(uc)
        seen.append((o[32 + s], sel_rgb(uc, tc), o[T.LED_KNOB0]))
    check("over 512 ms: the selected track flashes (its colour 256 ms, dark 256 ms), K1's LED solid",
          all(a == b and c == w0 for a, b, c in seen) and
          (all(a != 0 for a, b, c in seen) if MAN['report']['tmenu'].get('trackpulse') else {a for a, b, c in seen} == {0, tc}), [f"{a:06x}" for a, b, c in seen])
    tick(uc, 2000)
    led(uc, head)
    check("stays open after 2 s", b8(uc, T.O_OPEN) == 1)
    k1 = T.COLOURS + 4 * (T.CODE_KNOB0 + 8 * s)
    keep = u32(uc, k1)
    uc.mem_write(k1, struct.pack("<I", T.RED))             # the stock's K1 red (automation on the step)
    led(uc, head); o = out(uc)
    check("K1's slot red: the selected track and the bar keep the track's colour", o[32 + s] == sel_rgb(uc, tc) and list(o[16:24]) == want_bar(uc, s, 0),
          (f"{o[32 + s]:06x}", [f"{x:06x}" for x in o[16:24]]))
    uc.mem_write(k1, struct.pack("<I", keep))

    before = bytes(uc.mem_read(RAM, 0x60000))
    pad(uc, 20)
    after = bytes(uc.mem_read(RAM, 0x60000))
    changed = [hex(RAM + i) for i in range(len(after)) if after[i] != before[i] and not SLOT <= RAM + i < SLOT + 32]
    check("pad 21 pressed: taken, the stock untouched", changed == [] and u32(uc, SLOT + T.O_TAKEN) == 1 << 20, changed[:6])
    unpad(uc, 20)
    after2 = bytes(uc.mem_read(RAM, 0x60000))
    check("its release swallowed", u32(uc, SLOT + T.O_TAKEN) == 0 and [i for i in range(len(after2)) if after2[i] != before[i]
                                                                       and not SLOT <= RAM + i < SLOT + 32] == [])

    f0 = led(uc, head)
    pad(uc, 4)
    hs = held_step(uc, s)
    tick(uc, 100); unpad(uc, 4); tick(uc, 20)
    f1 = led(uc, head)
    check("pad 5 (no step) in the menu: selected while held, no step added", hs == 4 and f1[4] == f0[4] == 0x19 and held_step(uc, s) == 0xFF,
          (hs, hex(f0[4]), hex(f1[4])))

    for k, d in ((2, -9), (5, -7), (6, -20)):
        knob(uc, k, d)
        bar_check(uc, head, s, k, f"K{k + 1} turned: the bar its value {kval(uc, s, k)} in the track's colour")
    knob(uc, 1, 1)
    for v, fn in ((0, 0), (0, 4), (17, 100), (64, 0), (127, 127), (100, 64)):
        kset(uc, s, 1, v); kset(uc, s, T.FINE[1], fn)
        bar_check(uc, head, s, 1, f"K2 (Start) {v} fine {fn}: the bar from both")
    knob(uc, 2, 1)
    for v, fn in ((3, 0), (3, 8)):
        kset(uc, s, 2, v); kset(uc, s, T.FINE[2], fn)
        bar_check(uc, head, s, 2, f"K3 (Length) {v} fine {fn}: the bar from both")
    knob(uc, 0, 1)
    for v in (64, 65, 66, 80, 63, 62, 48, 0, 127):
        kset(uc, s, 0, v)
        bar_check(uc, head, s, 0, f"K1 at {v}: from the middle")
    knob(uc, 3, 1)
    for v in (64, 90, 30):
        kset(uc, s, 3, v)
        bar_check(uc, head, s, 3, f"K4 at {v}: from the middle")
    kset(uc, s, 3, 64)
    led(uc, head); o64 = out(uc)
    check("K4 at 64: pads 20 / 21 dim white, the rest dark", o64[19] == o64[20] == scl(0xFFFFFF, T.WHITE * dim_mul(uc) >> 8) and not any(o64[16:19])
          and not any(o64[21:24]), [f"{x:06x}" for x in o64[16:24]])

    dimp = ptr(uc, u32(uc, C.CTRL + T.O_DIM), T.P_DIM)
    w = u32(uc, dimp)
    for on in (0, 1):
        uc.mem_write(dimp, struct.pack("<I", w & ~(1 << T.BIT_DIM) | on << T.BIT_DIM))
        led(uc, head); od = out(uc)
        sw = out(uc, PREV_OUT)
        check(f"the stock's LEDs {'dimmed' if on else 'not dimmed'}: the centre white scaled as the stock's own white",
              od[19] == scl(0xFFFFFF, T.WHITE * (T.DIM_MUL if on else 256) >> 8) and sw[T.LED_TRK0 + other] == (0x8C8C8C if on else 0xFFFFFF),
              (f"{od[19]:06x}", f"{sw[T.LED_TRK0 + other]:06x}"))
        check(f"  the selected track's number at full brightness ({'dimmed' if on else 'not dimmed'})", od[T.LED_TRK0 + s] == sel_rgb(uc, tc), f"{od[T.LED_TRK0 + s]:06x}")
        check(f"  pad 25 the track's colour at CYC_LVL, not scaled by the stock's dim ({'dimmed' if on else 'not dimmed'})",
              od[24] == scl(tc, T.CYC_LVL), f"{od[24]:06x}")
    uc.mem_write(dimp, struct.pack("<I", w))

    kset(uc, s, 2, 90); kset(uc, s, T.FINE[2], 30)
    la = lane_addr(uc, s, 2, 4)
    l6 = lane_addr(uc, s, 6, 4)
    uc.mem_write(la, bytes([100]) + b"\xff" * 5)
    uc.mem_write(l6, bytes([0xFF, 0xFF, 0xFF, 0x40, 0xFF, 0xFF]))
    uc.mem_write(SLOT + T.O_KNOB, bytes([2 + 1]))
    pad(uc, 4)
    bar_check(uc, head, s, 2, "step 5 held, its own K3 value 100: the bar shows 100 in the track's colour", step_val=100)
    f = led(uc, head)
    fs = led(uc, PREV_LED)
    kn = f[T.LED_KNOB0:T.LED_KNOB0 + 8]
    check("step 5 held, own values on K3 (shown, microstep 0) and K7 (microstep 3 only): K3 and K7 red, the others as the stock draws them",
          kn[2] == kn[6] == T.COL_REC and all(kn[k] == fs[T.LED_KNOB0 + k] for k in (0, 1, 3, 4, 5, 7)), (kn, fs[T.LED_KNOB0:T.LED_KNOB0 + 8]))
    led(uc, head); o3 = out(uc)[T.LED_KNOB0 + 2]
    check("  K3 (shown) red after the output stage, not white", o3 & 0xFFFF == 0 and o3 != 0, f"{o3:06x}")
    uc.mem_write(SLOT + T.O_KNOB, bytes([6 + 1]))
    bar_check(uc, head, s, 6, "  K7 shown: the bar at 0x40 (its microstep 3)", step_val=0x40)
    lanes = bytes(uc.mem_read(la, 6)) + bytes(uc.mem_read(l6, 6))
    knob(uc, 2, 10)
    check("step 5 held, K3 +10: the stock's turn (the knob 90 -> 100, fine 30 -> 0 as the stock), no step's value written",
          kval(uc, s, 2) == 100 and kval(uc, s, T.FINE[2]) == 0 and bytes(uc.mem_read(la, 6)) + bytes(uc.mem_read(l6, 6)) == lanes,
          (kval(uc, s, 2), bytes(uc.mem_read(la, 6)).hex()))
    check("  the bar shows K3 again (the last knob turned)", b8(uc, T.O_KNOB) == 3)
    held = u32(uc, C.CTRL + T.HELD)
    uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", held | 1 << 23))
    f = led(uc, head)
    fs = led(uc, PREV_LED)
    check("Clear held, step 5 with own values: all 8 knob LEDs as the stock draws them", f[T.LED_KNOB0:T.LED_KNOB0 + 8] == fs[T.LED_KNOB0:T.LED_KNOB0 + 8],
          (f[T.LED_KNOB0:T.LED_KNOB0 + 8], fs[T.LED_KNOB0:T.LED_KNOB0 + 8]))
    uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", held))
    unpad(uc, 4)
    f = led(uc, head)
    fs = led(uc, PREV_LED)
    check("no step held: K7 as the stock draws it (not red)", f[T.LED_KNOB0 + 6] == fs[T.LED_KNOB0 + 6], (f[T.LED_KNOB0 + 6], fs[T.LED_KNOB0 + 6]))
    uc.mem_write(la, b"\xff" * 6)
    uc.mem_write(l6, b"\xff" * 6)

    uc.mem_write(SLOT + T.O_KNOB, b"\x00")
    seen = []
    before = bytes(uc.mem_read(RAM, 0x60000))
    for _ in range(9):
        pad(uc, T.PAD_KNOB); unpad(uc, T.PAD_KNOB)
        seen.append(b8(uc, T.O_KNOB))
    after = bytes(uc.mem_read(RAM, 0x60000))
    changed = [hex(RAM + i) for i in range(len(after)) if after[i] != before[i] and not SLOT <= RAM + i < SLOT + 32]
    check("pad 25 tapped 9 times from K1: K2 .. K8, K1, K2", seen == [2, 3, 4, 5, 6, 7, 8, 1, 2], seen)
    check("  the stock never sees pad 25", changed == [] and u32(uc, SLOT + T.O_TAKEN) == 0, changed[:6])
    bar_check(uc, head, s, 1, "  the bar shows K2")

    def page_pads(): o = out(uc); return [f"{x:06x}" for x in o[24:32]]
    full = scl(PAGES[NP - 1 if NP <= 2 else T.PAGE_SP], 255 * dim_mul(uc) >> 8)
    for p, i in ((PADMAP.index(1) + T.PAD_PAGE0 + 1, 1), (PADMAP.index(0) + T.PAD_PAGE0 + 1, 0))[2 - NP:]:
        before = bytes(uc.mem_read(RAM, 0x60000))
        pad(uc, p - 1); unpad(uc, p - 1)
        after = bytes(uc.mem_read(RAM, 0x60000))
        pg = range(pgb(uc), pgb(uc) + T.PG_LEN) if PERPAGE else range(0)
        changed = [hex(RAM + j) for j in range(len(after)) if after[j] != before[j] and not SLOT <= RAM + j < SLOT + 32 and RAM + j != SPB and RAM + j not in pg]
        led(uc, head); o = out(uc)
        want = page_pads_want(uc, i, cyc)
        check(f"pad {p} tapped: page {i}, its pad full in its colour, the other pages dim", b8(uc, T.O_PAGE) == i and list(o[24:32]) == want,
              (page_pads(), [f"{x:06x}" for x in want]))
        check(f"  the stock never sees pad {p}", changed == [] and u32(uc, SLOT + T.O_TAKEN) == 0, changed[:6])
        if SP:
            check(f"  Stock+'s page bits: {'the selected track' if i else 'none'}", spb(uc) == (1 << s if i else 0), hex(spb(uc)))
    for p in list(range(26, T.PAD_PAGE0 + 1)) + [T.PAD_PAGE0 + j + 1 for j, i in enumerate(PADMAP) if i is None] + list(range(T.PAD_PAGE0 + NP + 1, 33)):
        pad(uc, p - 1); unpad(uc, p - 1)
    check(f"pad 26{f' and {27 + NP}-32' if NP < 6 else ''} tapped: the page stays, nothing taken", b8(uc, T.O_PAGE) == 0 and u32(uc, SLOT + T.O_TAKEN) == 0, b8(uc, T.O_PAGE))
    if MAN["report"]["tmenu"].get("padmap"):
        got = []
        for j in range(NP):
            pad(uc, T.PAD_PAGE0); unpad(uc, T.PAD_PAGE0)
            pad(uc, T.PAD_PAGE0 + j); unpad(uc, T.PAD_PAGE0 + j)
            got.append(b8(uc, T.O_PAGE))
        check("pads 26-31: the editor, filter, mix, pitch, none (the page stays), FX",
              got == [0, T.PAGE_F, T.PAGE_V, T.PAGE_SP, 0, T.PAGE_X] and PADMAP == [0, T.PAGE_F, T.PAGE_V, T.PAGE_SP, None, T.PAGE_X], got)
        pad(uc, T.PAD_PAGE0); unpad(uc, T.PAD_PAGE0)
    if SP:
        pad(uc, pp(1)); unpad(uc, pp(1))
        tap(uc, s)
        check("on the Stock+ page, a tap on the selected track: the bits untouched until the frame (Stock+'s own page flip removed)",
              spb(uc) == 1 << s, hex(spb(uc)))
        led(uc, head)
        check("  closed with the tap: no Stock+ bit", b8(uc, T.O_OPEN) == 0 and spb(uc) == 0, (b8(uc, T.O_OPEN), hex(spb(uc))))
        tap(uc, s); led(uc, head)
        check("  opened again: the Stock+ page kept, its bit back", b8(uc, T.O_OPEN) == 1 and b8(uc, T.O_PAGE) == 1 and out(uc)[pp(1)] == full
              and spb(uc) == 1 << s, page_pads())
        pad(uc, T.PAD_PAGE0); unpad(uc, T.PAD_PAGE0)
    uc.mem_write(SLOT + T.O_KNOB, bytes([2]))

    for bid, name in ((16, "Record"), (23, "Clear")):
        press(uc, bid); release(uc, bid); led(uc, head)
        check(f"{name}: the menu stays open", b8(uc, T.O_OPEN) == 1)

    tap(uc, other); led(uc, head)
    check("tap on another track: selected, the menu follows", sel(uc) == other and b8(uc, T.O_OPEN) == 1, (sel(uc), b8(uc, T.O_OPEN)))
    tap(uc, other); led(uc, head)
    check("tap on the selected track again: closed", b8(uc, T.O_OPEN) == 0)

    if SP:
        uc = setup(fw, ram)
        tap(uc, s); led(uc, head)
        pad(uc, pp(1)); unpad(uc, pp(1))
        press(uc, 19)
        check("the Stock+ page, another button closes the menu: the page kept, no Stock+ bit at once", b8(uc, T.O_OPEN) == 0
              and b8(uc, T.O_PAGE) == 1 and spb(uc) == 0, (b8(uc, T.O_OPEN), b8(uc, T.O_PAGE), hex(spb(uc))))
        release(uc, 19); led(uc, head)
        tap(uc, other); led(uc, head); tap(uc, other); led(uc, head)
        if PERPAGE:
            check("  another track selected and opened: its own page (the parameter editor), no Stock+ bit",
                  b8(uc, T.O_OPEN) == 1 and sel(uc) == other and b8(uc, T.O_PAGE) == 0 and spb(uc) == 0, (b8(uc, T.O_PAGE), page_pads(), hex(spb(uc))))
        else:
            check("  another track selected and opened: the Stock+ page (one page for all tracks), that track's bit only",
                  b8(uc, T.O_OPEN) == 1 and sel(uc) == other and b8(uc, T.O_PAGE) == 1 and out(uc)[pp(1)] == full and spb(uc) == 1 << other,
                  (page_pads(), hex(spb(uc))))

    for bid in (8, 13, 15, 18, 20, 22, 26, 27, 28, 29, 30, 31):
        uc = setup(fw, ram)
        s = sel(uc)
        tap(uc, s); led(uc, head)
        opened = b8(uc, T.O_OPEN)
        press(uc, bid)
        closes = bid < T.CLOSE_END and bid not in T.KEEP
        check(f"button {bid}: the menu {'closes' if closes else 'stays open'}",
              opened == 1 and b8(uc, T.O_OPEN) == (0 if closes else 1), (opened, b8(uc, T.O_OPEN)))
        if CLICK and closes:
            release(uc, bid)
            # back on the track's view; the stock's press code held back (after a view change it waits on a task the emulator lacks)
            uc.mem_write(C.CTRL + 0x7C, struct.pack("<I", T.CONT))
            uc.mem_write(T.CONT + T.O_MODE, b"\0")
            prev = int(MAN["report"]["tmenu"]["prev_btn"], 16)
            hk = uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR)), None, prev, prev + 1)
            led(uc, head)
            tap(uc, s); led(uc, head)
            first = b8(uc, T.O_OPEN)
            tap(uc, s); led(uc, head)
            uc.hook_del(hk)
            if TWO:
                check("  then the selected track, the view as it was: the first tap opens, the second closes", sel(uc) == s and first == 1
                      and b8(uc, T.O_OPEN) == 0, (sel(uc), first, b8(uc, T.O_OPEN)))
            else:
                check("  then the selected track: the first tap the stock's only (closed), the second opens", sel(uc) == s and first == 0
                      and b8(uc, T.O_OPEN) == 1, (sel(uc), first, b8(uc, T.O_OPEN)))
        if bid == T.ID_SHIFT:
            fl = uc.mem_read(ptr(uc, u32(uc, C.CTRL + 0xC), 0), 1)[0]
            check("  button 27 is Shift: the stock's Shift flag (p0 of [ctrl + 0xC]) is 1", fl == 1, fl)
            ref = setup(stock, ram, built=False)
            tap(ref, s); press(ref, bid)
            for m in (uc, ref):
                kset(m, s, 1, 50); kset(m, s, T.FINE[1], 10)
                knob(m, 1, 3)
            got = (kval(uc, s, 1), kval(uc, s, T.FINE[1])); want = (kval(ref, s, 1), kval(ref, s, T.FINE[1]))
            check(f"  Shift + K2 +3 in the menu: as the stock's Shift turn (coarse, fine) {want}, the menu open",
                  got == want and want != (50, 10) and b8(uc, T.O_OPEN) == 1, (got, want))
            bar_check(uc, head, s, 1, "  the bar shows K2 with its fine value")

    uc = setup(fw, ram)                                   # fresh: the presses above filled a queue another task empties
    s = sel(uc)
    if BOUNCE:
        bounce(fw, ram, head)
    else:
        press(uc, s); tick(uc, 300)
        led(uc, head)
        check("hold 300 ms: open, not sticky", b8(uc, T.O_OPEN) == 1 and b8(uc, T.O_STICKY) == 0)
        release(uc, s); tick(uc, 10)
        led(uc, head)
        check("its release: closed", b8(uc, T.O_OPEN) == 0)
        press(uc, s); tick(uc, 100)
        led(uc, head)
        check("held 100 ms: still closed", b8(uc, T.O_OPEN) == 0)
        release(uc, s); tick(uc, 10); led(uc, head)
        check("released at 100 ms on the selected track: a tap, open", b8(uc, T.O_OPEN) == 1)
        press(uc, s); tick(uc, 400); led(uc, head); release(uc, s); tick(uc, 10); led(uc, head)
        check("a hold while open: closed on release", b8(uc, T.O_OPEN) == 0)

    if TWO:
        two_view(fw, ram, head)
    if SHL:
        shift_tan(stock, fw, ram, head)
    else:
        E_shift = C.CTRL + 0xC
        for o_ in (0xC, 0x10):
            uc.mem_write(u32(uc, u32(uc, E_shift) + o_), b"\x01")
        tap(uc, s); led(uc, head)
        check("Shift + tap: no menu", b8(uc, T.O_OPEN) == 0)
    if MAN["report"]["tmenu"].get("viewlock"):
        view_lock(stock, fw, ram, head)

    uc, ref = setup(fw, ram), setup(stock, ram, built=False)
    s = sel(uc)
    pad(uc, 4); unpad(uc, 4); pad(ref, 4); unpad(ref, 4)          # a step on pad 5, the menu closed
    a_, b_ = bytes(uc.mem_read(RAM, 0x60000)), bytes(ref.mem_read(RAM, 0x60000))
    diff = [hex(RAM + i) for i in range(len(a_)) if a_[i] != b_[i] and not ours(RAM + i)]
    check("menu closed: pad 5 adds a step as the stock", diff == [] and led(uc, head)[4] == 0x18, diff[:6])
    tap(uc, s); led(uc, head)
    pad(uc, 4); tick(uc, 100); unpad(uc, 4); tick(uc, 20)
    f = led(uc, head)
    check("menu open: pad 5 (a step) pressed and released, the step stays", b8(uc, T.O_OPEN) == 1 and f[4] == 0x18, hex(f[4]))
    tap(uc, s); led(uc, head)
    pad(uc, 4); unpad(uc, 4)
    check("menu closed again: pad 5 removes the step as the stock", b8(uc, T.O_OPEN) == 0 and led(uc, head)[4] == 0x19, hex(led(uc, head)[4]))

    uc, ref = setup(fw, ram), setup(stock, ram, built=False)
    for m in (uc, ref):
        pad(m, 20); knob(m, 2, 5)                       # (pad 21's release stops the stock in the emulation too)
    a_, b_ = bytes(uc.mem_read(RAM, 0x60000)), bytes(ref.mem_read(RAM, 0x60000))
    diff = [hex(RAM + i) for i in range(len(a_)) if a_[i] != b_[i] and not ours(RAM + i)]
    check("menu closed: pad 21 pressed and a knob turned as the stock", diff == [], diff[:6])

    uc = setup(fw, ram)
    s = sel(uc)
    tap(uc, s); led(uc, head)
    rec = u32(uc, T.AUTO + T.AUTO_RECS + 4 * s)
    def posp(): return ptr(uc, u32(uc, rec + T.REC_POS), 1)      # its two copies swap on a commit: the current one each time
    def playp(): return ptr(uc, C.TRANSPORT, 0)
    l5, l10 = lane_addr(uc, s, 2, 4), lane_addr(uc, s, 2, 9)

    def run(name, playing, held, value, want5, want10, track=None, menu=True):
        uc.mem_write(l5, b"\xff" * 6); uc.mem_write(l10, b"\xff" * 6)
        uc.mem_write(playp(), bytes([playing]))
        uc.mem_write(SLOT + T.O_OPEN, bytes([menu]))
        if held:
            pad(uc, 4)                                    # (the stock's press puts the position on step 5 too)
        uc.mem_write(posp(), b"\x09")                    # a playhead tick: the position on step 10
        record(uc, rec, 2, value, s if track is None else track)
        got = (uc.mem_read(l5, 6).hex(), uc.mem_read(l10, 6).hex(), uc.mem_read(posp(), 1)[0])
        if held:
            unpad(uc, 4)
        want = ((bytes([want5]) + b"\xff" * 5 if want5 is not None else b"\xff" * 6).hex(),
                (bytes([want10]) + b"\xff" * 5 if want10 is not None else b"\xff" * 6).hex(), 9)
        check(name, got == want, (got, want))

    run("Record, playing, step 5 held in the menu: K3's value into step 5 only, the playhead's step 10 untouched, the position back",
        1, True, 77, 77, None)
    check("  released while playing: the stock's held step stays 4 (its release needs the position on it), its pad is up",
          held_step(uc, s) == 4 and u32(uc, u32(uc, T.CONT + T.STEPOBJ + 4 * s) + T.PADS_DOWN) >> 4 & 1 == 0, held_step(uc, s))
    run("Record, playing, no step held (the stale one not counted): into the playhead's step 10 (the stock's)", 1, False, 66, None, 66)
    run("Record, stopped, step 5 held: not redirected (the stock's position, moved to step 10 here)", 0, True, 55, None, 55)
    run("Record, playing, step 5 held, the menu closed: the stock's (step 10)", 1, True, 44, None, 44, menu=False)
    other = (s + 1) % 8
    rec_o = u32(uc, T.AUTO + T.AUTO_RECS + 4 * other)
    lo = lane_addr(uc, other, 2, 9)
    uc.mem_write(lo, b"\xff" * 6)
    uc.mem_write(l5, b"\xff" * 6); uc.mem_write(playp(), b"\x01"); uc.mem_write(SLOT + T.O_OPEN, b"\x01")
    pad(uc, 4)
    uc.mem_write(ptr(uc, u32(uc, rec_o + T.REC_POS), 1), b"\x09")
    record(uc, rec_o, 2, 33, other)
    unpad(uc, 4)
    check("another track's recording while step 5 is held: the stock's (its step 10)",
          uc.mem_read(lo, 1)[0] == 33 and uc.mem_read(l5, 1)[0] == 0xFF, (uc.mem_read(lo, 1)[0], uc.mem_read(l5, 1)[0]))
    uc.mem_write(lo, b"\xff" * 6); uc.mem_write(playp(), b"\x00")

    uc = setup(fw, ram)
    s = sel(uc)
    tap(uc, s); led(uc, head)
    def armp(): return ptr(uc, C.TRANSPORT, 1)
    def setplay(playing, armed): uc.mem_write(ptr(uc, C.TRANSPORT, 0), bytes([playing])); uc.mem_write(armp(), bytes([armed]))
    setplay(0, 0)
    tick(uc, 1000)
    knob(uc, 4, 5)
    bar_check(uc, head, s, 4, "Record off, K5 turned: the bar in the track's colour")
    setplay(0, 1)
    tick(uc, 1000)
    bar_check(uc, head, s, 4, "Record armed, no turn for 1 s: the bar in the track's colour")
    knob(uc, 4, 5)
    bar_check(uc, head, s, 4, "Record armed, K5 turned: the bar red", red=True)
    tick(uc, T.TURN_MS - 20)
    bar_check(uc, head, s, 4, f"  {T.TURN_MS - 20} ms later: still red", red=True)
    tick(uc, 40)
    bar_check(uc, head, s, 4, f"  {T.TURN_MS + 20} ms after the turn: the track's colour")
    setplay(1, 1)
    knob(uc, 4, -3)
    bar_check(uc, head, s, 4, "Record armed, playing, K5 turned: red", red=True)
    setplay(1, 0)
    bar_check(uc, head, s, 4, "  Record off right after the turn: the track's colour")

    rec = u32(uc, T.AUTO + T.AUTO_RECS + 4 * s)
    def posp(): return ptr(uc, u32(uc, rec + T.REC_PLAY), 1)
    def pads(playing, armed, pos, held=True):
        setplay(playing, armed)
        if held:
            pad(uc, 4)
        uc.mem_write(posp(), bytes([pos]))
        f, fs = led(uc, head)[:16], led(uc, PREV_LED)[:16]
        if held:
            unpad(uc, 4)
        return f, fs
    f, fs = pads(1, 1, 9)
    check("Record, playing, step 5 held, the playhead on step 10: pad 5 red, pad 10 white, the other pads as the stock draws them",
          f[4] == T.COL_REC and f[9] == T.COL_FULL and all(f[i] == fs[i] for i in range(16) if i not in (4, 9)), (f, fs))
    f, fs = pads(1, 1, 4)
    check("  the playhead on step 5 (the held step): pad 5 red", f[4] == T.COL_REC and all(f[i] == fs[i] for i in range(16) if i != 4), (f, fs))
    f, fs = pads(1, 1, 20)
    check("  the playhead on step 21 (the other page): pad 5 red, no pad white", f[4] == T.COL_REC and all(f[i] == fs[i] for i in range(16) if i != 4),
          (f, fs))
    for name, args, want in (("Record off, playing", (1, 0, 9), T.COL_FULL), ("Record off, stopped", (0, 0, 9), T.COL_FULL),
                             ("Record armed, stopped", (0, 1, 9), T.COL_REC)):
        f, fs = pads(*args)
        check(f"  {name}, step 5 held: pad 5 {'red' if want == T.COL_REC else 'white'}, no playhead pad, the others as the stock draws them",
              f[4] == want and all(f[i] == fs[i] for i in range(16) if i != 4), (f, fs))
    f, fs = pads(1, 1, 9, False)
    check("  no step held: pads 1-16 as the stock draws them", f == fs, (f, fs))
    kset(uc, s, 2, 90)
    la = lane_addr(uc, s, 2, 4)
    uc.mem_write(la, bytes([100]) + b"\xff" * 5)
    uc.mem_write(SLOT + T.O_KNOB, bytes([2 + 1]))
    tick(uc, 1000)
    for playing, armed in ((0, 0), (0, 1), (1, 1)):
        setplay(playing, armed)
        pad(uc, 4)
        what = f"Record {'armed' if armed else 'off'}{', playing' if playing else ''}, step 5 held with its own K3 value 100, no turn"
        bar_check(uc, head, s, 2, f"{what}: {'red' if armed else 'the track colour'}", step_val=100, red=bool(armed))
        if armed:
            tick(uc, 3 * T.TURN_MS)
            bar_check(uc, head, s, 2, f"  still held {3 * T.TURN_MS} ms later: still red", step_val=100, red=True)
        unpad(uc, 4)
        bar_check(uc, head, s, 2, "  released: the knob's value in the track's colour")
    uc.mem_write(la, b"\xff" * 6)
    setplay(0, 0)
    if SP and SHAPES:
        stockplus_shapes(fw, ram, head)
    elif SP:
        stockplus_page(fw, ram, head)
    if FP:
        x_page(fw, ram, head)
        closed_knobs(fw, ram, head, stock)
    if FILTPAGE:
        filter_page(fw, ram, head)
    if VOLPAGE:
        vol_page(fw, ram, head)
    if PXRAND:
        px_rand(fw, ram, head)
    if SB:
        sync_bar(fw, ram, head)
    if NP > (T.PAGE_V + 1 if VOLPAGE else T.PAGE_F + 1 if FILTPAGE else 3 if FP else 2):
        test_pages(fw, ram, head)
    if PERPAGE:
        per_page(fw, ram, head)

    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED")


def flval(uc, t, i):
    call(uc, int(MAN["report"]["fshape"]["labels"]["c_fsval"], 16), t, i)
    return uc.reg_read(UC_ARM_REG_R0)


def want_fl_bar(uc, t, k, shift=False):
    """(filtpage) row 4 for the filter page's knob k: K7 / K8 the stock's bar (syncbar: Shift held, the type / follow); the shapes and the
    type one pad; K2 / K5 from the middle (syncbar: a synced rate one pad a step)"""
    lay = shift and k in FSHIFT
    if k >= 6 and not lay:
        return want_bar(uc, t, k)
    i = FSHIFT[k] if lay else T.F_MAP[k]
    v = flval(uc, t, i)
    col = u32(uc, T.COLOURS + 4 * T.SHIFT_BRT) if lay else None
    w = sync_pads(uc, t, i, v, PAGES[T.PAGE_F])
    if w:
        return w
    v = uiv(i, v)
    if i in T.F_SHN:
        n = v * T.F_SHN[i] >> 14
        w = [0] * 8
        base = col if col is not None else u32(uc, T.COLOURS + 4 * T.TRK_SLOTS[t])
        w[n & 7] = scl(PAGES[T.PAGE_F] if n >= 8 else base, 255 * dim_mul(uc) >> 8)
        return w
    return bar_rgb(uc, t, "mid" if i in T.F_MIDS else "fine", v >> 7, v, col=col)


def want_fl_lights(uc, t, shown, shift=False):
    """(filtpage) the knob LEDs on the filter page"""
    tc = u32(uc, T.COLOURS + 4 * T.TRK_SLOTS[t])
    tan = u32(uc, T.COLOURS + 4 * T.SHIFT_BRT)
    f = led(uc, PREV_LED)[T.LED_KNOB0:T.LED_KNOB0 + 8]
    so = out(uc, PREV_OUT)[T.LED_KNOB0:T.LED_KNOB0 + 8]
    w = []
    for k in range(8):
        if shift and k in FSHIFT:
            w.append(tan if k == shown else scl(tan, T.KNOB_LVL))
        elif k == shown:
            w.append(so[k] if k >= 6 and u32(uc, T.COLOURS + 4 * f[k]) == T.RED else tc)
        elif k < 6:
            v = uiv(T.F_MAP[k], flval(uc, t, T.F_MAP[k]))
            b = min(127, (abs(v - 8192) << 1 if T.F_MAP[k] in (13, 16) else v) >> 7)
            w.append(scl(PAGES[T.PAGE_F], ((T.STOCK_B[0] * b + T.STOCK_B[1]) >> 8) * T.KNOB_LVL >> 8))
        else:
            red = u32(uc, T.COLOURS + 4 * f[k]) == T.RED
            w.append(so[k] if red else tint(so[k], scl(0xFFFFFF if K78W else PAGES[T.PAGE_F], T.KNOB_LVL)))
    return w


def filter_page(fw, ram, head):
    """(filtpage) pad 29: fshape's values on K1-K6, the stock's K7 / K8, Shift + K1 / K4 Stock+'s type / follow, the lights and the
    bar, the record's block, the DSP words"""
    import fshape as FS
    import stockplus as SPM
    import cthresh as TH
    FL = {k: int(v, 16) for k, v in MAN["report"]["fshape"]["labels"].items()}
    uc = setup(fw, ram)
    s = sel(uc)
    def fl6(t=None): return [flval(uc, s if t is None else t, 12 + k) for k in range(6)]
    def sp12(): return [spval(uc, s, k) for k in range(12)]
    def stock8(): return [kval(uc, s, k) for k in range(8)]
    shf = ptr(uc, u32(uc, C.CTRL + 0xC), 0)
    def shift(on): uc.mem_write(shf, bytes([on]))
    tap(uc, s); led(uc, head)
    pad(uc, pp(T.PAGE_F)); unpad(uc, pp(T.PAGE_F)); led(uc, head)
    check("filter page: pad 29 shows it, no Stock+ bit", b8(uc, T.O_PAGE) == T.PAGE_F and spb(uc) == 0, (b8(uc, T.O_PAGE), spb(uc)))
    check("  a new project: the 6 values at their defaults", fl6() == list(FS.DEF) and all(fl6(t) == list(FS.DEF) for t in range(8)), fl6())
    sp0, st0 = sp12(), stock8()
    deltas = (3, 5, -3, 7, -9, 4)
    for k, d in enumerate(deltas):
        knob(uc, k, d)
    want = list(FS.DEF)
    for k, d in enumerate(deltas):
        want[T.F_MAP[k] - 12] = turned(T.F_MAP[k], want[T.F_MAP[k] - 12], d)
    check("  K1-K6 turned: env shape, amount, decay, LFO shape, rate, depth, 128 a click; Stock+ and the stock's knobs untouched",
          fl6() == want and sp12() == sp0 and stock8() == st0, (fl6(), want))
    check("  the other tracks keep their defaults", all(fl6(t) == list(FS.DEF) for t in range(8) if t != s))
    call(uc, int(MAN["report"]["rhrec"]["labels"]["c_rrt"], 16))
    tail = uc.reg_read(UC_ARM_REG_R0)
    vals = [list(FS.DEF) for _ in range(8)]
    vals[s] = want
    check("  the record's block: \"FL\", its check byte, the values XOR their defaults", bytes(uc.mem_read(tail + FS.BLK_OFF, FS.BLK_LEN)) == FS.block_bytes(vals))
    ref = setup(fw, ram)
    tap(ref, s); led(ref, head)
    for k, d in ((6, -20), (7, 9)):
        knob(uc, k, d)
        knob(ref, k, d)
    check("  K7 / K8 turned: the stock's K7 / K8 (the low-pass, the resonance) as on the parameter editor; ours untouched",
          [kval(uc, s, k) for k in (6, 7)] == [kval(ref, s, k) for k in (6, 7)] != [st0[6], st0[7]] and fl6() == want,
          ([kval(uc, s, k) for k in (6, 7)], [kval(ref, s, k) for k in (6, 7)], st0[6:]))
    if FCLR:
        blue, red = STOCK_CLR
        o = clr_turn(uc, 6, T.CLR_N - 1, keep=True)
        check(f"  Clear held, K7 {T.CLR_N - 1} clicks right: not blue yet", o[6] not in (blue, red), f"{o[6]:06x}")
        o = clr_turn(uc, 6, 1, keep=True)
        clr_turn(ref, 6, T.CLR_N)
        check(f"  K7's {T.CLR_N}th click right: K7 the stock's blue ({blue:06x}), the low-pass at the stock's default (as on the parameter editor)",
              o[6] == blue and kval(uc, s, 6) == kval(ref, s, 6), (f"{o[6]:06x}", kval(uc, s, 6), kval(ref, s, 6)))
        o = clr_turn(uc, 7, T.CLR_N, -1, keep=True)
        clr_turn(ref, 7, T.CLR_N, -1)
        check(f"  K8 {T.CLR_N} clicks left: K8 the stock's red ({red:06x}), the resonance as on the parameter editor, K7 still blue",
              o[7] == red and o[6] == blue and kval(uc, s, 7) == kval(ref, s, 7), ([f"{x:06x}" for x in o[6:]], kval(uc, s, 7), kval(ref, s, 7)))
        o = clr_turn(uc, 6, 0)
        lt = list(out(uc)[T.LED_KNOB0:T.LED_KNOB0 + 8])
        check("  Clear let go: no knob blue or red", blue not in lt and red not in lt, [f"{x:06x}" for x in lt])
        knob(uc, 6, -20)
        knob(ref, 6, -20)
    shift(1)
    t0, f0 = spval(uc, s, 5), spval(uc, s, 9)
    kt, kf = (k for k in FSHIFT)
    st7 = [kval(uc, s, k) for k in (6, 7)]
    kA, kE, kR = (T.F_MAP.index(i) for i in (13, 12, 16))   # the knobs of the amount, the env shape, the rate
    knob(uc, kt, 50); knob(uc, kf, 20); knob(uc, kA, 2)
    if SB:
        knob(uc, kE, 3)
    shift(0)
    check(f"  Shift + K{kt + 1}: Stock+'s filter type, Shift + K{kf + 1}: the pitch follow, 128 a click; Shift + K{kA + 1}: the amount 4 a click"
          + ("; the stock's K7 / K8 untouched" if SB else ""),
          spval(uc, s, 5) == min(16383, t0 + 50 * 128) and spval(uc, s, 9) == min(16383, f0 + 20 * 128) and fl6()[1] == want[1] + 8
          and (fl6()[3] == want[3] if SB else fl6()[0] == want[0] and fl6()[3] == want[3])
          and (not SB or [kval(uc, s, k) for k in (6, 7)] == st7), (spval(uc, s, 5), spval(uc, s, 9), fl6()))
    if SB:
        check(f"  Shift + K{kE + 1} right: the env shape on the same pad, 2nd sweep (+ 8192)", fl6()[0] == want[0] + 8192, fl6())
        shift(1); knob(uc, kE, 3); shift(0)
        check(f"  Shift + K{kE + 1} right again: nothing (already on the 2nd sweep)", fl6()[0] == want[0] + 8192, fl6())
        shift(1); knob(uc, kE, -1); shift(0)
        check(f"  Shift + K{kE + 1} left: back on the 1st sweep", fl6()[0] == want[0], fl6())
    clr_turn(uc, kE, T.CLR_N)
    clr_turn(uc, kR, T.CLR_N)
    check(f"  Clear + K{kE + 1}, Clear + K{kR + 1}: the env shape and the rate back to their defaults", fl6()[0] == FS.DEF[0] and fl6()[4] == FS.DEF[4], fl6())
    knob(uc, 0, 70); knob(uc, 3, 40); knob(uc, 4, -30)
    for sh in (0, 1):
        shift(sh)
        for k in range(8):
            uc.mem_write(SLOT + T.O_KNOB, bytes([k + 1]))
            led(uc, head)
            o = list(out(uc)[16:24])
            w = want_fl_bar(uc, s, k, bool(sh))
            check(f"  {'Shift + ' if sh else ''}K{k + 1} shown: the bar", o == w, ([f"{x:06x}" for x in o], [f"{x:06x}" for x in w]))
            led(uc, head)
            o = list(out(uc)[T.LED_KNOB0:T.LED_KNOB0 + 8])
            w = want_fl_lights(uc, s, k, bool(sh))
            check(f"    knob lights: K{k + 1} shown; K1-K6 the page's colour by value, K7 / K8 the stock's in {'white' if K78W else 'the page colour'}"
                  + (f"; K{list(FSHIFT)[0] + 1} / K{list(FSHIFT)[1] + 1} tan" if sh else ""), o == w, ([f"{x:06x}" for x in o], [f"{x:06x}" for x in w]))
    shift(0)
    seen = []
    uc.mem_write(SLOT + T.O_KNOB, bytes([1]))
    for _ in range(8):
        pad(uc, T.PAD_KNOB); unpad(uc, T.PAD_KNOB)
        seen.append(b8(uc, T.O_KNOB))
    check("  pad 25 tapped 8 times: K2 .. K8, K1", seen == [2, 3, 4, 5, 6, 7, 8, 1], seen)

    uc = setup(fw, ram)
    s = sel(uc)
    writes = []
    def wr(u, a, n, d):
        if u.reg_read(UC_ARM_REG_R0) == 1:
            writes.append((u.reg_read(UC_ARM_REG_R1) >> 8, u.reg_read(UC_ARM_REG_R2) & 0x7FFF))
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE, wr, None, TH.WR16, TH.WR16 + 1)
    def fw_(): return {y: x for x, y in writes if FS.FB <= y < FS.FB + 0x48}
    ready = int(MAN["report"]["cthresh"]["slot"], 16) + 1
    wait = rhstate.ST + rhstate.OFF["spwait"][0]
    bpm = uc.mem_read(ptr(uc, SPM.TEMPO, 0), 1)[0]
    tap(uc, s); led(uc, head)
    pad(uc, pp(T.PAGE_F)); unpad(uc, pp(T.PAGE_F))
    knob(uc, 1, 30); knob(uc, 2, -10); knob(uc, 5, 40)
    led(uc, head)
    check("filter page, core 1: not READY: no filter words", fw_() == {}, fw_())
    uc.mem_write(ready, bytes([TH.READY]))
    uc.mem_write(wait, bytes([SPM.SP_WAIT]))
    for _ in range(8):
        led(uc, head)
    want = {}
    for t in range(8):
        want.update(FS.words(fl6(t), t, bpm))
    got = fw_()
    bad = {hex(a): (hex(got.get(a, -1)), hex(w)) for a, w in want.items() if got.get(a) != w}
    check(f"  READY and Stock+'s wait done, 8 frames: every track's words (track {s + 1}'s with its values)", not bad, bad)
    del writes[:]
    knob(uc, 1, -50)
    led(uc, head)
    got = fw_()
    w1 = FS.words(fl6(), s, bpm)
    check("  K2 turned: the next frame track's words again with the new amount", all(got.get(a) == w for a, w in w1.items()), (got, w1))
    del writes[:]
    for _ in range(FS.ROUND * 8):
        led(uc, head)
    rounds = sorted({(y - FS.FB) & 7 for x, y in writes if FS.FB + FS.O_S <= y < FS.FB + FS.O_S + 8})
    check(f"  nothing changed, {FS.ROUND * 8} frames: each track once in the round", rounds == list(range(8)), rounds)
    v = 8192 - 128 - 512 * 3                                       # synced: division 3
    knob(uc, T.F_MAP.index(16), clicks_to(16, fl6()[4], v))
    v = fl6()[4]
    tp = ptr(uc, u32(uc, FS.SEQ + 0x90), 0)
    tk = u32(uc, tp) + 5
    uc.mem_write(tp, struct.pack("<I", tk))
    del writes[:]
    led(uc, head)
    ph = [x for x, y in writes if y == FS.FB + FS.O_P + s]
    check(f"  the rate synced (value {v}), the tick moved: the LFO's phase at the tick ({tk})", ph and ph[-1] == SPM.k3_phase(v, tk),
          (ph, SPM.k3_phase(v, tk)))
    del writes[:]
    led(uc, head)
    check("  the tick not moved: no phase written", not [1 for x, y in writes if y == FS.FB + FS.O_P + s])


def want_vl_bar(uc, t, k):
    """(volpage) row 4 for the movement page's knob k (K4-K8: K1's): the shape one pad, K2 from the middle"""
    i = T.V_MAP[k if k < T.V_KNOBS else 0]
    v = flval(uc, t, i)
    w = sync_pads(uc, t, i, v, PAGES[T.PAGE_V])
    if w:
        return w
    v = uiv(i, v)
    if i in T.V_SHN:
        n = v * T.V_SHN[i] >> 14
        w = [0] * 8
        w[n & 7] = scl(PAGES[T.PAGE_V] if n >= 8 else u32(uc, T.COLOURS + 4 * T.TRK_SLOTS[t]), 255 * dim_mul(uc) >> 8)
        return w
    return bar_rgb(uc, t, "mid" if i in T.V_MIDS else "fine", v >> 7, v)


def want_vl_lights(uc, t, shown):
    """(volpage) the knob LEDs on the movement page: K1-K3 by value (K2 from the middle), the shown one the track's colour, K4-K8 dark"""
    shown = shown if shown < T.V_KNOBS else 0
    w = []
    for k in range(8):
        if k >= T.V_KNOBS:
            w.append(0)
        elif k == shown:
            w.append(u32(uc, T.COLOURS + 4 * T.TRK_SLOTS[t]))
        else:
            v = uiv(T.V_MAP[k], flval(uc, t, T.V_MAP[k]))
            b = min(127, (abs(v - 8192) << 1 if T.V_MAP[k] in T.V_MIDS else v) >> 7)
            w.append(scl(PAGES[T.PAGE_V], ((T.STOCK_B[0] * b + T.STOCK_B[1]) >> 8) * T.KNOB_LVL >> 8))
    return w


def px_rand(fw, ram, head):
    """(pxrand) the pitch page's K7: fshape's value 26, its "PX" block, Clear + K7, K8 nothing (glide: value 27), c_fldsp's depth word
    (glide: and the glide's word; fade: Shift + K7 the LFO's fade-in, its "FI" block, its bar, its word, Clear + Shift + K7)"""
    import fshape as FS
    import stockplus as SPM
    import cthresh as TH
    uc = setup(fw, ram)
    s = sel(uc)
    writes = []
    def wr(u, a, n, d):
        if u.reg_read(UC_ARM_REG_R0) == 1:
            writes.append((u.reg_read(UC_ARM_REG_R1) >> 8, u.reg_read(UC_ARM_REG_R2) & 0x7FFF))
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE, wr, None, TH.WR16, TH.WR16 + 1)
    def px(t=None): return [flval(uc, s if t is None else t, FS.PX0 + k) for k in range(FS.NPX)]
    def sp12(): return [spval(uc, s, k) for k in range(12)]
    def rdw(): return {y - FS.RD: x for x, y in writes if FS.RD <= y < FS.RD + 8}
    def gkw(): return {y - FS.GK: x for x, y in writes if FS.GK <= y < FS.GK + 8}
    gtab = FS.glide_table()
    def gint(v): return gtab[v >> 7] + ((gtab[min(128, (v >> 7) + 1)] - gtab[v >> 7]) * (v & 127) >> 7)
    k7 = T.SP_MAP.index(FS.PX0)
    tap(uc, s); led(uc, head)
    pad(uc, pp(T.PAGE_SP)); unpad(uc, pp(T.PAGE_SP)); led(uc, head)
    check(f"pxrand: the pitch page's K{k7 + 1} = random pitch; a new project: 0 on every track",
          k7 == 6 and all(px(t) == [0, 0] for t in range(8)), [px(t) for t in range(8)])
    sp0 = sp12()
    knob(uc, k7, 40)
    check(f"  K{k7 + 1} 40 clicks: 40 x 128; Stock+'s values and the other tracks untouched",
          px() == [40 * 128, 0] and sp12() == sp0 and all(px(t) == [0, 0] for t in range(8) if t != s), (px(), sp12()))
    knob(uc, 7, 9)
    g = 9 * 128 if GLIDE else 0
    check("  K8 9 clicks: the glide time 9 x 128" if GLIDE else "  K8 turned: nothing", px() == [40 * 128, g] and sp12() == sp0, (px(), sp12()))
    call(uc, int(MAN["report"]["rhrec"]["labels"]["c_rrt"], 16))
    tail = uc.reg_read(UC_ARM_REG_R0)
    vb = b"".join(((((40 * 128, g)[k]) if t == s else 0) ^ FS.PXDEF[k]).to_bytes(2, "little") for t in range(8) for k in range(FS.NPX))
    vb = bytes([FS.PXMARK0, FS.PXMARK1, (sum(vb) & 0xFF) ^ FS.CHECK, 0]) + vb
    check(f"  the record's block at {FS.PXBLK_OFF}: \"PX\", its check byte, the values XOR their defaults",
          bytes(uc.mem_read(tail + FS.PXBLK_OFF, FS.PXBLK_LEN)) == vb)
    ready = int(MAN["report"]["cthresh"]["slot"], 16) + 1
    wait = rhstate.ST + rhstate.OFF["spwait"][0]
    led(uc, head)
    check("  core 1 not READY: no depth word", rdw() == {}, rdw())
    uc.mem_write(ready, bytes([TH.READY]))
    uc.mem_write(wait, bytes([SPM.SP_WAIT]))
    for _ in range(8):
        led(uc, head)
    d = 40 * 128
    want = {t: ((d * d) >> 10) * 3 if t == s else 0 for t in range(8)}
    check(f"  READY, 8 frames: each track's depth at Y:${FS.RD:X} + t, (d x d >> 10) x 3 (track {s + 1}: {want[s]:#x})", rdw() == want, rdw())
    if GLIDE:
        gw = {t: gint(g) if t == s else 0 for t in range(8)}
        check(f"  READY, 8 frames: each track's glide at Y:${FS.GK:X} + t from the table (track {s + 1}: {gw[s]:#x}, 0 elsewhere)", gkw() == gw, gkw())
    knob(uc, k7, 200)
    del writes[:]
    led(uc, head)
    top = ((16383 * 16383) >> 10) * 3
    check(f"  K{k7 + 1} to the top: 16383, the depth {top:#x} (12 semitones at most: {top <= 12 << 16})", px()[0] == 16383 and rdw().get(s) == top and top <= 12 << 16,
          (px(), rdw()))
    del writes[:]
    clr_turn(uc, k7, T.CLR_N)
    check(f"  Clear + K{k7 + 1}: back to 0, the depth 0", px() == [0, g] and rdw().get(s) == 0, (px(), rdw()))
    if GLIDE:
        knob(uc, 7, 200)
        del writes[:]
        led(uc, head)
        check(f"  K8 to the top: 16383, the glide {gint(16383):#x} (to 95 % in about {FS.GL_MAX:g} s)", px()[1] == 16383 and gkw().get(s) == gint(16383),
              (px(), gkw()))
        knob(uc, 7, -3)
        del writes[:]
        led(uc, head)
        check(f"  K8 3 clicks back: 16383 - 384, the glide from the table", px()[1] == 16383 - 384 and gkw().get(s) == gint(16383 - 384), (px(), gkw()))
        del writes[:]
        clr_turn(uc, 7, T.CLR_N)
        check("  Clear + K8: back to 0, the glide 0 (none)", px() == [0, 0] and gkw().get(s) == 0, (px(), gkw()))
    if FADE:
        def fd(t=None): return flval(uc, s if t is None else t, FS.FI0)
        def frw(): return {y - FS.FR: x for x, y in writes if FS.FR <= y < FS.FR + 8}
        ftab = FS.fade_table()
        def fint(v): return ftab[v >> 7] + ((ftab[min(128, (v >> 7) + 1)] - ftab[v >> 7]) * (v & 127) >> 7)   # c_spint, the 24-bit word
        shf = ptr(uc, u32(uc, C.CTRL + 0xC), 0)
        def shift(on): uc.mem_write(shf, bytes([1 if on else 0]))
        check("fade: a new project: the LFO's fade-in 0 on every track", all(fd(t) == 0 for t in range(8)), [fd(t) for t in range(8)])
        knob(uc, k7, 5)
        shift(True)
        knob(uc, k7, 12)
        del writes[:]
        check(f"  Shift + K{k7 + 1} 12 clicks: the fade-in 12 x 128 (Shift: no fine steps here); the random pitch kept",
              fd() == 12 * 128 and px() == [5 * 128, 0] and all(fd(t) == 0 for t in range(8) if t != s), (fd(), px()))
        bar_check(uc, head, s, k7, f"  Shift held, K{k7 + 1} shown: the bar shows the fade-in", sp=True, shift=True)
        shift(False)
        bar_check(uc, head, s, k7, f"  Shift let go: the bar shows the random pitch again", sp=True)
        call(uc, int(MAN["report"]["rhrec"]["labels"]["c_rrt"], 16))
        tail = uc.reg_read(UC_ARM_REG_R0)
        vb = b"".join(((12 * 128 if t == s else 0) ^ FS.FIDEF[0]).to_bytes(2, "little") for t in range(8))
        vb = bytes([FS.FIMARK0, FS.FIMARK1, (sum(vb) & 0xFF) ^ FS.CHECK, 0]) + vb
        check(f"  the record's block at {FS.FIBLK_OFF}: \"FI\", its check byte, the values XOR their defaults",
              bytes(uc.mem_read(tail + FS.FIBLK_OFF, FS.FIBLK_LEN)) == vb)
        for _ in range(8):
            led(uc, head)
        fw = frw()
        check(f"  the next frames: the track's fade step at Y:${FS.FR:X} + t from the table ({fint(12 * 128):#x}); the others in turn: {ftab[0]:#x} (none)",
              fw.get(s) == fint(12 * 128) and len(fw) > 1 and all(x == ftab[0] for t, x in fw.items() if t != s), fw)
        shift(True)
        knob(uc, k7, 200)
        del writes[:]
        led(uc, head)
        check(f"  Shift + K{k7 + 1} to the top: 16383, the step {fint(16383):#x} (a full fade in {FS.FD_MAX:g} s)", fd() == 16383 and frw().get(s) == fint(16383),
              (fd(), frw()))
        del writes[:]
        clr_turn(uc, k7, T.CLR_N)
        shift(False)
        check(f"  Clear + Shift + K{k7 + 1}: the fade-in back to 0 (step {ftab[0]:#x}: none); the random pitch kept",
              fd() == 0 and px() == [5 * 128, 0] and frw().get(s) == ftab[0], (fd(), px(), frw()))
        shift(True)
        knob(uc, k7, 7)
        shift(False)
        clr_turn(uc, k7, T.CLR_N)
        check(f"  Clear + K{k7 + 1} (no Shift): the random pitch back to 0; the fade-in kept", px() == [0, 0] and fd() == 7 * 128, (px(), fd()))


def vol_page(fw, ram, head):
    """(volpage) pad 30: fshape's values 18..20 on K1-K3, K4-K8 nothing, the lights and the bar, the "VL" block, the DSP words"""
    import fshape as FS
    import stockplus as SPM
    import cthresh as TH
    uc = setup(fw, ram)
    s = sel(uc)
    def vl8(t=None): return [flval(uc, s if t is None else t, FS.V1 + k) for k in range(FS.NV2)]
    def fl6(): return [flval(uc, s, 12 + k) for k in range(6)]
    def sp12(): return [spval(uc, s, k) for k in range(12)]
    def stock8(): return [kval(uc, s, k) for k in range(8)]
    shf = ptr(uc, u32(uc, C.CTRL + 0xC), 0)
    def shift(on): uc.mem_write(shf, bytes([on]))
    tap(uc, s); led(uc, head)
    pv = pp(T.PAGE_V)
    pad(uc, pv); unpad(uc, pv); led(uc, head)
    check("movement page: pad 30 shows it, no Stock+ bit", b8(uc, T.O_PAGE) == T.PAGE_V and spb(uc) == 0, (b8(uc, T.O_PAGE), spb(uc)))
    VD = list(MAN["report"]["fshape"]["vdefs"])
    nk = T.V_KNOBS
    check("  a new project: the 8 values at their defaults", all(vl8(t) == VD for t in range(8)), (vl8(), VD))
    sp0, st0, fl0 = sp12(), stock8(), fl6()
    deltas = (3, -5, 9, 6, 20, -7, 11, -13)[:nk]
    for k, d in enumerate(deltas):
        knob(uc, k, d)
    want = list(VD)
    for k, d in enumerate(deltas):
        want[T.V_MAP[k] - 18] = turned(T.V_MAP[k], want[T.V_MAP[k] - 18], d)
    kS, kR, kD = (T.V_MAP.index(i) for i in (18, 19, 20))   # the knobs of the vol shape, rate, depth
    check(f"  K1-K{nk} turned: " + ", ".join(FS.VNAMES[i - 18] for i in T.V_MAP) + ", 128 a click; Stock+, the filter page and the stock's knobs untouched",
          vl8() == want and sp12() == sp0 and stock8() == st0 and fl6() == fl0, (vl8(), want))
    check("  the other tracks keep their defaults", all(vl8(t) == VD for t in range(8) if t != s))
    kn0 = b8(uc, T.O_KNOB)
    if nk < 8:
        for k in range(nk, 8):
            knob(uc, k, 7)
        check(f"  K{nk + 1}-K8 turned: nothing (ours, Stock+, the filter page, the stock's knobs, the shown knob)",
              vl8() == want and sp12() == sp0 and stock8() == st0 and fl6() == fl0 and b8(uc, T.O_KNOB) == kn0, (vl8(), b8(uc, T.O_KNOB)))
    call(uc, int(MAN["report"]["rhrec"]["labels"]["c_rrt"], 16))
    tail = uc.reg_read(UC_ARM_REG_R0)
    vals = [list(VD) for _ in range(8)]
    vals[s] = want
    vb = b"".join((vals[t][k] ^ VD[k]).to_bytes(2, "little") for t in range(8) for k in range(FS.NV2))
    vb = bytes([FS.VMARK0, FS.VMARK1, (sum(vb) & 0xFF) ^ FS.CHECK, 0]) + vb
    check("  the record's block at 2: \"VL\", its check byte, the values XOR their defaults", bytes(uc.mem_read(tail + FS.VBLK_OFF, FS.VBLK_LEN)) == vb)
    shift(1)
    knob(uc, kR, 2)
    shift(0)
    check(f"  Shift + K{kR + 1}: the rate 4 a click" + (" (free: fine)" if SB else ""), vl8()[1] == turned(19, want[1], 2 / 32), vl8())
    clr_turn(uc, kR, T.CLR_N)
    check(f"  Clear + K{kR + 1}: the rate back to its default", vl8()[1] == VD[1], vl8())
    if MIXPAGE:
        for i in (24, 25):
            k = T.V_MAP.index(i)
            knob(uc, k, -20)
            clr_turn(uc, k, T.CLR_N)
            check(f"  K{k + 1} ({FS.VNAMES[i - 18]}) left, then Clear + K{k + 1}: back to the middle (no movement)", vl8()[i - 18] == 8192, vl8())
    knob(uc, 0, 40); knob(uc, 1, -30); knob(uc, 2, 50)
    for k in range(8):
        uc.mem_write(SLOT + T.O_KNOB, bytes([k + 1]))
        led(uc, head)
        o = list(out(uc)[16:24])
        w = want_vl_bar(uc, s, k)
        check(f"  K{k + 1} shown: the bar" + (" (K1's)" if k >= T.V_KNOBS else f" ({FS.VNAMES[T.V_MAP[k] - 18]})"), o == w,
              ([f"{x:06x}" for x in o], [f"{x:06x}" for x in w]))
        led(uc, head)
        o = list(out(uc)[T.LED_KNOB0:T.LED_KNOB0 + 8])
        w = want_vl_lights(uc, s, k)
        check(f"    knob lights: K1-K{nk} the page's colour by value, the shown one the track's" + (f", K{nk + 1}-K8 dark" if nk < 8 else ""), o == w,
              ([f"{x:06x}" for x in o], [f"{x:06x}" for x in w]))
    seen = []
    uc.mem_write(SLOT + T.O_KNOB, bytes([1]))
    for _ in range(4):
        pad(uc, T.PAD_KNOB); unpad(uc, T.PAD_KNOB)
        seen.append(b8(uc, T.O_KNOB))
    ws = [j % nk + 1 for j in range(1, 5)]
    check(f"  pad 25 tapped 4 times: {', '.join(f'K{j}' for j in ws)}", seen == ws, seen)

    uc = setup(fw, ram)
    s = sel(uc)
    writes, wall = [], []
    def wr(u, a, n, d):
        if u.reg_read(UC_ARM_REG_R0) == 1:
            writes.append((u.reg_read(UC_ARM_REG_R1) >> 8, u.reg_read(UC_ARM_REG_R2) & 0x7FFF))
        wall.append((u.reg_read(UC_ARM_REG_R0), (u.reg_read(UC_ARM_REG_R1) >> 8) & 0xFFFFFF, u.reg_read(UC_ARM_REG_R2)))
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE, wr, None, TH.WR16, TH.WR16 + 1)
    def vw(): return {y: x for x, y in writes if FS.VB <= y < FS.VB + FS.O_VX}
    ready = int(MAN["report"]["cthresh"]["slot"], 16) + 1
    wait = rhstate.ST + rhstate.OFF["spwait"][0]
    bpm = uc.mem_read(ptr(uc, SPM.TEMPO, 0), 1)[0]
    tap(uc, s); led(uc, head)
    pad(uc, pv); unpad(uc, pv)
    knob(uc, 0, 60); knob(uc, 2, 70)
    led(uc, head)
    check("movement page, core 1: not READY: no volume words", vw() == {}, vw())
    uc.mem_write(ready, bytes([TH.READY]))
    uc.mem_write(wait, bytes([SPM.SP_WAIT]))
    for _ in range(8):
        led(uc, head)
    want = {}
    for t in range(8):
        want.update(FS.vwords(vl8(t)[:3], t, bpm))
    got = vw()
    bad = {hex(a): (hex(got.get(a, -1)), hex(w)) for a, w in want.items() if got.get(a) != w}
    check(f"  READY, 8 frames: every track's rate, shape table and depth (track {s + 1}: shape {vl8()[0] >> 10}, its depth)", not bad, bad)
    if MIXPAGE:
        import mixmove as MM

        def mw():                                                  # {(core, address): word}: core 1's Y, core 0's Y ($8000 off), shared
            out = {}
            for c, w, adr in wall:
                if c == 1 and adr & 0x7FFF in range(FS.MB, FS.MB + 16):
                    out[(1, adr & 0x7FFF)] = w
                elif c == 0 and adr & 0x8000 and adr & 0x7FFF in range(MM.YD, MM.YD + 24):
                    out[(0, adr & 0x7FFF)] = w
            return out
        mt = T.V_MAP.index
        knob(uc, mt(23), 50); knob(uc, mt(24), 30); knob(uc, mt(25), -40); knob(uc, mt(22), clicks_to(22, vl8()[4], 8192) - 20)
        del wall[:]
        led(uc, head)
        w1 = FS.mwords(vl8(), s, bpm)
        got = mw()
        bad = {str(a): (hex(got.get(a, -1)), hex(w)) for a, w in w1.items() if got.get(a) != w}
        check(f"  the move (rate {vl8()[4]}, shape {vl8()[3] >> 10}): core 1's rate and table, core 0's pan / reverb / delay depths "
              f"({vl8()[5]}, {vl8()[6]}, {vl8()[7]})", not bad and w1[(0, MM.YD + MM.O_RD + s)] != 0 and w1[(0, MM.YD + MM.O_DD + s)] >= 0x800000, bad)
        knob(uc, mt(22), clicks_to(22, vl8()[4], 8192))
        del wall[:]
        led(uc, head)
        w1 = FS.mwords(vl8(), s, bpm)
        got = mw()
        check(f"  the move rate at the middle: rate 0 and the three depths 0 (no movement)", w1[(1, FS.MB + s)] == 0
              and all(got.get((0, MM.YD + o + s)) == 0 for o in (MM.O_PD, MM.O_RD, MM.O_DD)) and got.get((1, FS.MB + s)) == 0, got)
        v = 8192 - 128 - 512 * 3
        knob(uc, mt(22), clicks_to(22, vl8()[4], v))
        v = vl8()[4]
        tp = ptr(uc, u32(uc, FS.SEQ + 0x90), 0)
        tk = u32(uc, tp) + 11
        uc.mem_write(tp, struct.pack("<I", tk))
        del wall[:]
        led(uc, head)
        ph = [w for c, w, adr in wall if c == 0 and adr == MM.SH + 8 + s]
        check(f"  K{mt(22) + 1} synced (value {v}), the tick moved: the move LFO's phase at shared Y:${MM.SH + 8 + s:X} through core 0",
              ph and ph[-1] == SPM.k3_phase(v, tk) & 0xFFFFFF, (ph, SPM.k3_phase(v, tk)))
        uc.mem_write(SLOT + T.O_KNOB, bytes([mt(22) + 1]))
        led(uc, head)
        o, w = list(out(uc)[16:24]), want_vl_bar(uc, s, mt(22))
        check(f"  K{mt(22) + 1} synced shown: one pad, step {SBM.step_of(uiv(22, v))} (the rate bar)", o == w and sum(1 for x in o if x) == 1,
              ([f"{x:06x}" for x in o], [f"{x:06x}" for x in w]))
        shift(1); knob(uc, mt(22), 2); shift(0)
        check(f"  Shift + K{mt(22) + 1} right: the same pad on the triplets", SBM.step_of(uiv(22, vl8()[4])) == SBM.step_of(uiv(22, v)) + 8,
              (vl8()[4], v))
    for sh in (5, 12):
        knob(uc, T.V_MAP.index(18), (sh * 1024 + 512 - vl8()[0]) // 128)
        del writes[:]
        led(uc, head)
        w1 = FS.vwords(vl8()[:3], s, bpm)
        check(f"  K{T.V_MAP.index(18) + 1} to shape {sh + 1}: the table at Y:${w1[FS.VB + FS.O_VQ + s]:X}", all(vw().get(a) == w for a, w in w1.items()), (vw(), w1))
    knob(uc, T.V_MAP.index(19), clicks_to(19, vl8()[1], 8192))
    del writes[:]
    led(uc, head)
    w1 = FS.vwords(vl8()[:3], s, bpm)
    check(f"  K2 to the middle ({vl8()[1]}): rate 0 and depth 0 (the full level)", w1[FS.VB + FS.O_VR + s] == 0 and w1[FS.VB + FS.O_VD + s] == 0
          and all(vw().get(a) == w for a, w in w1.items()), (vw(), w1))
    v = 8192 - 128 - 512 * 2                                       # synced: division 2
    knob(uc, T.V_MAP.index(19), clicks_to(19, vl8()[1], v))
    v = vl8()[1]
    tp = ptr(uc, u32(uc, FS.SEQ + 0x90), 0)
    tk = u32(uc, tp) + 7
    uc.mem_write(tp, struct.pack("<I", tk))
    del writes[:]
    led(uc, head)
    ph = [x for x, y in writes if y == FS.VB + FS.O_VP + s]
    check(f"  K2 synced (value {v}), the tick moved: the volume LFO's phase at the tick ({tk})", ph and ph[-1] == SPM.k3_phase(v, tk),
          (ph, SPM.k3_phase(v, tk)))


def sync_bar(fw, ram, head):
    """(syncbar) a rate knob: synced right of the middle, one pad a step (straight, then triplets), Shift + turn between the sweeps,
    free left of it with Shift fine; the tables in syncbar's order; Stock+'s scan speed at 1 bar by default"""
    rb = MAN["report"]["syncbar"]
    bad = []
    for at in rb["tables"]:
        o = int(at, 16) - rhbuild.BASE
        ws = struct.unpack_from("<48I", fw, o)
        if list(ws) != [t[i] for t in (SPM.DIVS, SPM.KQ, SPM.PHQ) for i in SBM.PERM]:
            bad.append(at)
    check(f"sync bar: Stock+'s and fshape's sync tables in the new order ({', '.join(rb['tables'])})", len(rb["tables"]) == 2 and not bad, bad)
    uc = setup(fw, ram)
    s = sel(uc)
    tap(uc, s); led(uc, head)
    pg = T.PAGE_X if SCANFX else 1
    pad(uc, pp(pg)); unpad(uc, pp(pg))
    uc.mem_write(SLOT + T.O_KNOB, bytes([8]))
    led(uc, head)
    v7 = shval(uc, s, 7)
    check(f"  the scan speed (pad {pp(pg) + 1} K8) by default: 1 bar, pad 20 in the track's colour",
          SBM.step_of(uiv(7, v7)) == 3 and list(out(uc)[16:24]) == (want_x_bar(uc, s, 7) if SCANFX else want_sp_bar(uc, s, 7)),
          (v7, SBM.step_of(uiv(7, v7))))
    import fshape as FS
    pv = pp(T.PAGE_V)
    pad(uc, pv); unpad(uc, pv)
    kr = T.V_MAP.index(19)
    uc.mem_write(SLOT + T.O_KNOB, bytes([kr + 1]))
    def rate(): return flval(uc, s, 19)
    knob(uc, kr, clicks_to(19, rate(), 8192))
    shf = ptr(uc, u32(uc, C.CTRL + 0xC), 0)
    def shift(on): uc.mem_write(shf, bytes([on]))
    def bar(): led(uc, head); return list(out(uc)[16:24])
    tc = u32(uc, T.COLOURS + 4 * T.TRK_SLOTS[s])
    full = 255 * dim_mul(uc) >> 8
    def one(pad_, col): return [scl(col, full) if j == pad_ else 0 for j in range(8)]
    seen = []
    for c in range(1, 65):
        knob(uc, kr, 1)
        seen.append((SBM.step_of(uiv(19, rate())), bar()))
    ok = all(st == (c - 1) // 4 and b == one(st & 7, tc if st < 8 else PAGES[T.PAGE_V]) for c, (st, b) in enumerate(seen, 1))
    check("  K2 turned right from the middle, 64 clicks: 4 clicks a step, 8 bars .. 1/16 on pads 17-24 in the track's colour, then the "
          "triplets on pads 17-24 in the page's colour", ok, [(st, f"{b.index(max(b)) + 17}") for st, b in seen[::4]])
    knob(uc, kr, -200); knob(uc, kr, 64 + 4 * 3 + 1)                 # the far left, the middle, then 1 bar (step 3)
    w0 = rate()
    shift(1); knob(uc, kr, 2); shift(0)
    check("  at 1 bar, Shift + turn right: 1 bar T, the same pad (20) in the page's colour", SBM.step_of(uiv(19, rate())) == 11
          and bar() == one(3, PAGES[T.PAGE_V]), (SBM.step_of(uiv(19, rate())), bar()))
    shift(1); knob(uc, kr, 3); shift(0)
    check("  Shift + turn right again: nothing", SBM.step_of(uiv(19, rate())) == 11)
    knob(uc, kr, 4)
    check("  a plain turn right: on along the triplets (1/2 T, pad 21)", SBM.step_of(uiv(19, rate())) == 12 and bar() == one(4, PAGES[T.PAGE_V]))
    shift(1); knob(uc, kr, -1); shift(0)
    check("  Shift + turn left: back to the straight step (1/2, pad 21, the track's colour)", SBM.step_of(uiv(19, rate())) == 4
          and bar() == one(4, tc), (SBM.step_of(uiv(19, rate())), bar()))
    knob(uc, kr, -200); knob(uc, kr, 64 - 10)
    u0 = uiv(19, rate())
    shift(1); knob(uc, kr, -3); shift(0)
    check("  free (left of the middle), Shift + turn: fine, 4 a click; the bar from the middle", uiv(19, rate()) == u0 - 12
          and bar() == bar_rgb(uc, s, "mid", uiv(19, rate()) >> 7, uiv(19, rate())), (u0, uiv(19, rate())))
    check("  free left of the middle = the engine's free half (the stored value right of it)", rate() > 8192 + 128 and w0 != rate())
    pad(uc, pp(T.PAGE_F)); unpad(uc, pp(T.PAGE_F))
    kq = T.F_MAP.index(15)
    knob(uc, kq, (2 * 1638 + 800 - flval(uc, s, 15)) // 128)
    n = flval(uc, s, 15) * 10 >> 14
    v15 = flval(uc, s, 15)
    shift(1); knob(uc, kq, 2); shift(0)
    check(f"  the filter's LFO shape {n + 1} (10 shapes), Shift + turn right: nothing (no shape {n + 9})", n >= 2 and flval(uc, s, 15) == v15,
          (n, flval(uc, s, 15)))


def test_pages(fw, ram, head):
    uc = setup(fw, ram)
    s = sel(uc)
    tap(uc, s); led(uc, head)
    uc.mem_write(SLOT + T.O_KNOB, bytes([6]))
    for i in range((T.PAGE_G + 1 if GRAN else T.PAGE_V + 1 if VOLPAGE else T.PAGE_F + 1 if FILTPAGE else 3) if FP else 2, NP):
        if i not in PADMAP:
            continue
        pad(uc, pp(i)); unpad(uc, pp(i))
        led(uc, head); o = out(uc)
        so = out(uc, PREV_OUT)
        lights = [o[T.LED_TRK0 + t] for t in range(8) if t != s] + [o[T.LED_KNOB0 + k] for k in range(8) if k != 5]
        want = [tint(so[T.LED_TRK0 + t], PAGES[i]) for t in range(8) if t != s] + [
            so[T.LED_KNOB0 + k] if so[T.LED_KNOB0 + k] == T.RED else tint(so[T.LED_KNOB0 + k], scl(PAGES[i], T.KNOB_LVL))
            for k in range(8) if k != 5]
        shown = o[T.LED_KNOB0 + 5]
        check(f"test page on pad {pp(i) + 1}: page {i}, no Stock+ bit, the editor's knob (K6, the track's colour at full), the other track "
              f"numbers and knob lights {PAGES[i]:06x}", b8(uc, T.O_PAGE) == i and spb(uc) == 0 and b8(uc, T.O_KNOB) == 6 and lights == want
              and shown == (so[T.LED_KNOB0 + 5] if so[T.LED_KNOB0 + 5] == T.RED else u32(uc, T.COLOURS + 4 * T.TRK_SLOTS[s])),
              (b8(uc, T.O_PAGE), hex(spb(uc)), b8(uc, T.O_KNOB), [f"{x:06x}" for x in lights][:4], [f"{x:06x}" for x in want][:4]))
    code = led(uc, PREV_LED)[T.LED_KNOB0 + 5]
    keep = u32(uc, T.COLOURS + 4 * code)
    uc.mem_write(T.COLOURS + 4 * code, struct.pack("<I", T.RED))
    led(uc, head); o6 = out(uc)[T.LED_KNOB0 + 5]
    uc.mem_write(T.COLOURS + 4 * code, struct.pack("<I", keep))
    check("  the stock's K6 red on a test page: the shown knob stays red", o6 & 0xFFFF == 0 and o6 != 0, f"{o6:06x}")
    pad(uc, T.PAD_KNOB); unpad(uc, T.PAD_KNOB)
    check("  pad 25 on a test page: the editor's 8 knobs (K6 -> K7)", b8(uc, T.O_KNOB) == 7, b8(uc, T.O_KNOB))
    k0 = kval(uc, s, 0)
    knob(uc, 0, 2)
    check("  K1 on a test page: the stock's knob", kval(uc, s, 0) != k0)
    pad(uc, pp(1)); unpad(uc, pp(1))
    pad(uc, pp(3)); unpad(uc, pp(3))
    check("  Stock+, then test page 3: the editor's knob back (K1, the last turned)", b8(uc, T.O_KNOB) == 1, b8(uc, T.O_KNOB))
    pad(uc, T.PAD_PAGE0); unpad(uc, T.PAD_PAGE0)
    check("  test page 3 -> the parameter editor: nothing swapped", b8(uc, T.O_KNOB) == 1, b8(uc, T.O_KNOB))


def per_page(fw, ram, head):
    """(perpage) each track's page in the project's block: kept when another track is selected, read back from the block"""
    def blk(uc): return bytes(uc.mem_read(pgb(uc), T.PG_LEN))
    def ck(b): return (sum(b[2:T.PG_LEN]) & 0xFF) ^ 0xA5
    uc = setup(fw, ram)
    uc.mem_write(pgb(uc), bytes(T.PG_LEN))                  # a new project: the tail zeroed
    s = sel(uc)
    other, third = (s + 1) % 8, (s + 2) % 8
    tap(uc, s); led(uc, head)
    check("perpage: a new project, the menu opened: the parameter editor", b8(uc, T.O_PAGE) == 0, b8(uc, T.O_PAGE))
    pad(uc, pp(1)); unpad(uc, pp(1)); led(uc, head)
    b = blk(uc)
    want = bytearray(T.PG_LEN); want[0] = T.PG_MARK; want[2 + s] = T.PAGE_SP; want[1] = ck(want)
    check(f"  pad 27 on track {s + 1}: Stock+, the block made: its mark, check, track {s + 1} = 1", b8(uc, T.O_PAGE) == T.PAGE_SP and b == bytes(want)
          and spb(uc) == 1 << s, (b.hex(), bytes(want).hex()))
    tap(uc, other); led(uc, head)
    check(f"  track {other + 1} selected: its page (the parameter editor), no Stock+ bit, the block as it was",
          sel(uc) == other and b8(uc, T.O_OPEN) == 1 and b8(uc, T.O_PAGE) == 0 and spb(uc) == 0 and blk(uc) == bytes(want), (b8(uc, T.O_PAGE), hex(spb(uc))))
    pad(uc, pp(T.PAGE_X)); unpad(uc, pp(T.PAGE_X)); led(uc, head)
    want[2 + other] = T.PAGE_X; want[1] = ck(want)
    check(f"  pad 28 on track {other + 1}: the FX page, in the block", b8(uc, T.O_PAGE) == T.PAGE_X and blk(uc) == bytes(want), blk(uc).hex())
    uc = setup(fw, ram)                                     # (the emulation selects another track once a run)
    want[2 + third] = T.PAGE_SP; want[1] = ck(want)
    uc.mem_write(pgb(uc), bytes(want))                      # a project: track 1 Stock+, track 2 the FX page, track 3 Stock+
    tap(uc, s); led(uc, head)
    check(f"  a project loaded, the menu opened on track {s + 1}: Stock+", b8(uc, T.O_PAGE) == T.PAGE_SP and spb(uc) == 1 << s, b8(uc, T.O_PAGE))
    tap(uc, third); led(uc, head)
    check(f"  track {third + 1} selected, Stock+ in the project: Stock+ shown, its bit", sel(uc) == third and b8(uc, T.O_PAGE) == T.PAGE_SP
          and spb(uc) == 1 << third, (b8(uc, T.O_PAGE), hex(spb(uc))))
    want[2 + third] = T.PAGE_X; want[1] = ck(want)
    uc.mem_write(pgb(uc), bytes(want)); led(uc, head)
    check("  the project's block changed (a project loaded): the FX page at the next frame, no Stock+ bit",
          b8(uc, T.O_PAGE) == T.PAGE_X and spb(uc) == 0, (b8(uc, T.O_PAGE), hex(spb(uc))))
    bad = bytearray(want); bad[1] ^= 1
    uc.mem_write(pgb(uc), bytes(bad)); led(uc, head)
    check("  a wrong check byte: the parameter editor", b8(uc, T.O_PAGE) == 0, b8(uc, T.O_PAGE))
    bad = bytearray(want); bad[2 + third] = len(PAGES); bad[1] = ck(bad)
    uc.mem_write(pgb(uc), bytes(bad)); led(uc, head)
    check("  a page past the last: the parameter editor", b8(uc, T.O_PAGE) == 0, b8(uc, T.O_PAGE))
    tap(uc, third); led(uc, head)
    check("  closed: the page as the block says, nothing else", b8(uc, T.O_OPEN) == 0 and b8(uc, T.O_PAGE) == 0 and spb(uc) == 0)


def set_shift(uc, on):
    """the stock's Shift flag through its setter, so its listeners run (the button LEDs' tan)"""
    st = u32(uc, C.CTRL + 0xC)
    call(uc, 0x0803FD26, st, 0)
    uc.mem_write(uc.reg_read(UC_ARM_REG_R0), bytes([on]))
    call(uc, 0x0803FBEC, st)


def view_lock(stock, fw, ram, head):
    """(viewlock) Shift + Patterns runs the stock's View Lock toggle (as on the stock) and keeps the menu open; Patterns alone closes it"""
    calls = []

    def counted(fw_, built):
        u = setup(fw_, ram, built=built)
        u.hook_add(UC_HOOK_CODE, lambda u_, a, n, d: calls.append(a), None, VIEW_LOCK, VIEW_LOCK + 1)
        return u
    ref = counted(stock, False)
    tap(ref, 0); led(ref, rhbuild.bl_target(bytearray(stock), C.LED_CALLS[0]))
    shf = ptr(ref, u32(ref, C.CTRL + 0xC), 0)
    ref.mem_write(shf, bytes([1]))
    press(ref, T.ID_PATTERNS); release(ref, T.ID_PATTERNS)
    check("the stock: Shift + Patterns runs its View Lock toggle once", len(calls) == 1, calls)
    uc = counted(fw, True)
    s = sel(uc)
    tap(uc, s); led(uc, head)
    uc.mem_write(shf, bytes([1]))
    for k in (1, 2):
        calls.clear()
        press(uc, T.ID_PATTERNS); release(uc, T.ID_PATTERNS); led(uc, head)
        check(f"Shift + Patterns ({k}): the stock's View Lock toggle, the menu still open on track {s + 1}",
              len(calls) == 1 and b8(uc, T.O_OPEN) == 1 and sel(uc) == s, (calls, b8(uc, T.O_OPEN)))
    uc.mem_write(shf, bytes([0]))
    calls.clear()
    press(uc, T.ID_PATTERNS)
    check("Patterns without Shift: the menu closes, no View Lock toggle", b8(uc, T.O_OPEN) == 0 and not calls)

VIEW_LOCK = 0x080506D8                                   # the stock's View Lock toggle (ctrl_button_press, Shift + button 13)


def shift_tan(stock, fw, ram, head):
    """(shiftled) Shift: the track numbers in the stock's Shift tan (dim; the selected one lit), the stock's own codes and output stage"""
    ref = setup(stock, ram, built=False)
    set_shift(ref, 1)
    led(ref, rhbuild.bl_target(bytearray(stock), C.LED_CALLS[0]))
    so = out(ref, rhbuild.bl_target(bytearray(stock), T.OUT_CALL))
    sf = led(ref, rhbuild.bl_target(bytearray(stock), C.LED_CALLS[0]))
    dim_i = next(i for i in range(40, 69) if sf[i] == T.SHIFT_DIM)
    brt_i = next(i for i in range(40, 69) if sf[i] == T.SHIFT_BRT)
    dim, brt = so[dim_i], so[brt_i]
    for opened in (False, True):
        uc = setup(fw, ram)
        s = sel(uc)
        led(uc, head); plain = list(out(uc)[T.LED_TRK0:T.LED_TRK0 + 8])
        if opened:
            tap(uc, s); led(uc, head); plain = list(out(uc)[T.LED_TRK0:T.LED_TRK0 + 8])
        set_shift(uc, 1)
        led(uc, head); o = out(uc)
        want = [brt if t == s else dim for t in range(8)]
        name = "open" if opened else "closed"
        check(f"Shift, Track + {name}: the track numbers the stock's Shift tan ({dim:06x}, the selected {brt:06x}, as its buttons {dim_i} / {brt_i})",
              list(o[T.LED_TRK0:T.LED_TRK0 + 8]) == want and b8(uc, T.O_OPEN) == opened,
              ([f"{x:06x}" for x in o[T.LED_TRK0:T.LED_TRK0 + 8]], [f"{x:06x}" for x in want]))
        if opened and TWO:
            other = (s + 1) % 8
            u2 = setup(fw, ram)                           # the flag written straight: after its listeners the stock's press waits on a task
            tap(u2, s); led(u2, head)
            u2.mem_write(ptr(u2, u32(u2, C.CTRL + 0xC), 0), b"\x01")
            tap(u2, other); led(u2, head); o = out(u2)
            check("  Shift + a tap on another track with Track + open: that track's Track +, its number the lit tan",
                  sel(u2) == other and b8(u2, T.O_OPEN) == 1 and o[T.LED_TRK0 + other] == brt and o[T.LED_TRK0 + s] == dim,
                  (sel(u2), b8(u2, T.O_OPEN), f"{o[T.LED_TRK0 + other]:06x}"))
        uc.mem_write(ptr(uc, u32(uc, C.CTRL + 0xC), 0), b"\x00")       # (its listeners wait on a task the emulator lacks)
        led(uc, head)
        back = list(out(uc)[T.LED_TRK0:T.LED_TRK0 + 8])
        check("  the Shift flag clear: no track number tan", dim not in back and brt not in back, [f"{x:06x}" for x in back])


def two_view(fw, ram, head):
    """(twoview) a tap counts when the stock's press keeps the container's mode; Shift + a track = its plain press, then the menu"""
    def mode(m=None, page=None):
        if m is not None:
            uc.mem_write(T.CONT + T.O_MODE, bytes([m]))
        if page is not None:                              # the track's page 1 (0 Sample, 1 Note), where the stock's track press goes
            call(uc, C.PARAM_GET, u32(uc, T.CONT + 0x260), s)
            uc.mem_write(uc.reg_read(UC_ARM_REG_R0), bytes([page]))
        return uc.mem_read(T.CONT + T.O_MODE, 1)[0]
    prev = int(MAN["report"]["tmenu"]["prev_btn"], 16)
    for m, name in ((0, "Sample's page 1"), (1, "Note's page 1")):
        uc = setup(fw, ram)
        s = sel(uc)
        tap(uc, s); led(uc, head); tap(uc, s); led(uc, head)
        mode(m, m)
        tap(uc, s); led(uc, head)
        a_ = (mode(), b8(uc, T.O_OPEN))
        tap(uc, s); led(uc, head)
        check(f"twoview: mode {m} ({name}): a tap on the selected track opens, the next closes, the mode kept",
              a_ == (m, 1) and (mode(), b8(uc, T.O_OPEN)) == (m, 0), (a_, mode(), b8(uc, T.O_OPEN)))
    for m, pg, name in ((9, 0, "Sample mode, Sample's page 2"), (7, 1, "Expand, Note's page 2")):
        uc = setup(fw, ram)
        s = sel(uc)
        tap(uc, s); led(uc, head); tap(uc, s); led(uc, head)
        mode(m, pg)
        tap(uc, s); led(uc, head)
        a_ = (mode(), b8(uc, T.O_OPEN))
        tap(uc, s); led(uc, head)
        check(f"  mode {m} ({name}): a tap gives the stock's page 1 (mode {pg}) only, closed; the next tap opens",
              a_ == (pg, 0) and (mode(), b8(uc, T.O_OPEN)) == (pg, 1), (a_, mode(), b8(uc, T.O_OPEN)))
    uc = setup(fw, ram)
    s = sel(uc)
    other = (s + 1) % 8
    shf = ptr(uc, u32(uc, C.CTRL + 0xC), 0)
    seen = []
    hk = uc.hook_add(UC_HOOK_CODE, lambda u, a, n, d: seen.append(u.mem_read(shf, 1)[0]), None, prev, prev + 1)
    uc.mem_write(shf, b"\x01")
    tap(uc, other); led(uc, head)
    uc.hook_del(hk)
    check("  Shift + a tap on another track: the stock's press without Shift, Shift kept, that track selected, the menu open",
          seen[:1] == [0] and uc.mem_read(shf, 1)[0] == 1 and sel(uc) == other and b8(uc, T.O_OPEN) == 1, (seen, sel(uc), b8(uc, T.O_OPEN)))
    tap(uc, other); led(uc, head)
    check("  Shift + a tap again: still open (Shift always gives Track +)", b8(uc, T.O_OPEN) == 1)
    uc.mem_write(shf, b"\x00")
    tap(uc, other); led(uc, head)
    check("  a plain tap on it: closed", b8(uc, T.O_OPEN) == 0)
    uc.mem_write(shf, b"\x01")
    held = u32(uc, C.CTRL + T.HELD)
    uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", held | 1 << 23))
    tap(uc, other); led(uc, head)
    uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", held))
    check("  Shift + Clear + a tap: nothing of ours", b8(uc, T.O_OPEN) == 0)


def bounce(fw, ram, head):
    """(bounce) holds as the stock's: a held track never opens / closes the menu; another button held over it brings it back"""
    H = T.STOCK_HOLD
    def opened(): return b8(uc, T.O_OPEN)
    def let_go(bid):                                      # a held button's bit cleared: the stock's release after a hold (its bounce back
        w = u32(uc, C.CTRL + T.HELD)                      # waits on a task the emulator lacks)
        uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", w & ~(1 << bid)))
    uc = setup(fw, ram)
    s = sel(uc)
    other = (s + 1) % 8
    mom = MAN["report"]["tmenu"].get("momhold")
    press(uc, s); tick(uc, H - 30); led(uc, head)
    a_ = opened()
    tick(uc, 80); led(uc, head)
    b_ = opened()
    release(uc, s); tick(uc, 10); led(uc, head)
    if mom:
        check(f"momhold: the selected track held, Track + off: closed at {H - 30} ms, Track + at {H + 50} ms, off again on release (no tap)",
              a_ == 0 and b_ == 1 and opened() == 0, (a_, b_, opened()))
    else:
        check(f"bounce: the selected track held {H + 50} ms, Track + off: never opens (held, released)", b_ == 0 and opened() == 0, (b_, opened()))
    press(uc, s); tick(uc, H - 30); release(uc, s); tick(uc, 10); led(uc, head)
    check(f"  released at {H - 30} ms: a tap, Track + opens", opened() == 1)
    press(uc, s); tick(uc, H + 50); led(uc, head)
    a_ = opened()
    release(uc, s); tick(uc, 10); led(uc, head)
    if mom:
        check("  the selected track held with Track + on: the track view while held, Track + again on release", a_ == 0 and opened() == 1,
              (a_, opened()))
    else:
        check("  the selected track held with Track + on: still on after", opened() == 1)
    if mom:
        press(uc, s); tick(uc, H + 50); release(uc, s); tick(uc, 10); led(uc, head)
        check("  held past the hold time, released before the next frame: no flip, no tap (Track + still on)", opened() == 1)
        clear_bit = 1 << 23
        w = u32(uc, C.CTRL + T.HELD)
        uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", w | clear_bit))
        press(uc, s); tick(uc, H + 50); led(uc, head)
        a_ = opened()
        uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", u32(uc, C.CTRL + T.HELD) & ~clear_bit))
        release(uc, s); tick(uc, 10); led(uc, head)
        check("  Clear + the selected track held: no flip (the reset's own press)", a_ == 1 and opened() == 1, (a_, opened()))
    press(uc, other); tick(uc, H + 50); led(uc, head)
    a_ = (sel(uc), opened())
    let_go(other); tick(uc, 10); led(uc, head)
    check("  another track held with Track + on: its Track + while held, still on after the release (the stock puts the first track back)",
          a_ == (other, 1) and opened() == 1 and b8(uc, T.O_PTRK) == 0, (a_, opened()))
    for held_ms, want in ((H + 50, 1), (H - 30, 0)):
        uc = setup(fw, ram)
        tap(uc, s); led(uc, head)
        press(uc, 13)
        uc.mem_write(C.CTRL + 0x7C, struct.pack("<I", MIXER))   # the stock's view change (its press waits on a task here)
        tick(uc, held_ms); led(uc, head)
        a_ = opened()
        let_go(13)
        if want:
            uc.mem_write(C.CTRL + 0x7C, struct.pack("<I", T.CONT))   # the stock's bounce back after a hold
        tick(uc, 10); led(uc, head)
        b_ = opened()
        uc.mem_write(C.CTRL + 0x7C, struct.pack("<I", T.CONT)); tick(uc, 10); led(uc, head)
        what = "a hold: Track + back on release" if want else "a tap: the Mixer stays, Track + stays closed (also back on the track view)"
        check(f"  Track + on, button 13 (Mixer) held {held_ms} ms: closed while held; {what}", a_ == 0 and b_ == want and opened() == want,
              (a_, b_, opened()))
    uc = setup(fw, ram)
    s = sel(uc)
    press(uc, other); tick(uc, H + 50); led(uc, head)
    a_ = (sel(uc), opened())
    let_go(other); tick(uc, 10); led(uc, head)
    check("  Track + off, another track held: that track while held, Track + never opens, also after the release",
          a_ == (other, 0) and opened() == 0, (a_, opened()))


def clr_turn(uc, k, n, d=1, keep=False):
    """Clear held, knob k turned n times by d -> the knob lights with Clear held; then (not keep) Clear let go and a frame drawn"""
    held = u32(uc, C.CTRL + T.HELD)
    uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", held | 1 << 23))
    for _ in range(n):
        knob(uc, k, d)
    led(uc, HEAD)
    lights = list(out(uc)[T.LED_KNOB0:T.LED_KNOB0 + 8])
    if not keep:
        uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", held & ~(1 << 23)))
        led(uc, HEAD); out(uc)
    return lights


def stock_clear_rgb(stock, ram):
    """the stock's knob lights with Clear held: (CLR_N clicks right, CLR_N left), from its own track view and output stage"""
    ref = setup(stock, ram, built=False)
    sub = []
    hk = ref.hook_add(UC_HOOK_CODE, lambda u, a, n, d: sub.append(u.reg_read(UC_ARM_REG_R0)), None, 0x08058160, 0x08058161)
    knob(ref, 0, 1)
    ref.hook_del(hk)
    call(ref, 0x0803FC58, u32(ref, sub[0] + 0x20), 0)    # the view's Clear store (p0 bit 0)
    p = ref.reg_read(UC_ARM_REG_R0)
    ref.mem_write(p, bytes([ref.mem_read(p, 1)[0] | 1]))
    for _ in range(T.CLR_N):
        knob(ref, 0, 1); knob(ref, 1, -1)
    led(ref, rhbuild.bl_target(bytearray(stock), C.LED_CALLS[0]))
    o = out(ref, rhbuild.bl_target(bytearray(stock), T.OUT_CALL))
    return o[T.LED_KNOB0], o[T.LED_KNOB0 + 1]


def clear_keeps(uc, head, name):
    """(fpage) the page's knob lights with Clear held = without"""
    led(uc, head); before = list(out(uc)[T.LED_KNOB0:T.LED_KNOB0 + 8])
    a = C.CTRL + 0xA0
    w = u32(uc, a)
    uc.mem_write(a, struct.pack("<I", w | 1 << 23))
    led(uc, head); held = list(out(uc)[T.LED_KNOB0:T.LED_KNOB0 + 8])
    uc.mem_write(a, struct.pack("<I", w))
    check(f"  {name}: Clear held, the knob lights unchanged (not white)", held == before, ([f"{x:06x}" for x in held], [f"{x:06x}" for x in before]))


def closed_knobs(fw, ram, head, stock):
    """the menu closed by a button after the Stock+ page or pad 29's: every knob the stock's, no Stock+ value moved"""
    for page, name in ((T.PAGE_SP, "Stock+"), (T.PAGE_X, "pad 29's")):
        uc, ref = setup(fw, ram), setup(stock, ram, built=False)
        s = sel(uc)
        tap(uc, s); led(uc, head)
        pad(uc, pp(page)); unpad(uc, pp(page)); led(uc, head)
        tap(ref, s)
        for m in (uc, ref):
            press(m, 8); release(m, 8)
        led(uc, head)
        sp_before = [spval(uc, s, k) for k in range(12)]
        for k in range(8):
            for m in (uc, ref):
                knob(m, k, 3)
        led(uc, head)
        got = [kval(uc, s, k) for k in range(8)]
        want = [kval(ref, s, k) for k in range(8)]
        check(f"closed by the Samples button after {name} page: K1-K8 turned as the stock's, no Stock+ value moved",
              b8(uc, T.O_OPEN) == 0 and got == want and [spval(uc, s, k) for k in range(12)] == sp_before, (got, want))


def x_page(fw, ram, head):
    uc = setup(fw, ram)
    s = sel(uc)
    tc = u32(uc, T.COLOURS + 4 * T.TRK_SLOTS[s])
    pc = scl(PAGES[T.PAGE_X], T.KNOB_LVL)
    def sp12(): return [spval(uc, s, k) for k in range(12)]
    def stock_knobs(): return [kval(uc, s, k) for k in range(8)] + [kval(uc, s, T.FINE[k]) for k in T.FINE]
    def lights():
        led(uc, head)
        return list(out(uc)[T.LED_KNOB0:T.LED_KNOB0 + 8])
    def bar(i):
        v = spval(uc, s, i)
        led(uc, head)
        return list(out(uc)[16:24]) == (want_x_bar(uc, s, i) if SCANFX else bar_rgb(uc, s, "fine", v >> 7, v))
    tap(uc, s); led(uc, head)
    pad(uc, pp(T.PAGE_X)); unpad(uc, pp(T.PAGE_X)); led(uc, head)
    check("pad 29's page: shown, no Stock+ bit", b8(uc, T.O_PAGE) == T.PAGE_X and spb(uc) == 0, (b8(uc, T.O_PAGE), hex(spb(uc))))
    clear_keeps(uc, head, "pad 29's page")
    want, sk = sp12(), stock_knobs()
    names = {10: "the bitcrush", 5: "the filter type", 9: "the pitch follow", 4: "the ring's amount", 8: "the ring's frequency",
             11: "the scan's depth", 7: "the scan's speed"}
    deltas = {10: 20, 5: 100, 9: 7, 4: 9, 8: -11, 11: 9, 7: 6}
    nx, x0, x1 = T.X_KNOBS, T.X_IDX[0], T.X_IDX[1]
    XL = [k for k, i in enumerate(T.X_IDX) if i is not None]    # the live knobs
    dark = [k for k in range(8) if k not in XL]
    for k in XL:
        i = T.X_IDX[k]
        d = deltas[i]
        knob(uc, k, d)
        want[i] = turned(i, want[i], d)
        check(f"  K{k + 1} {d:+}: {names[i]} (Stock+ value {i}) 128 a click, the stock's knobs untouched, K{k + 1} shown",
              sp12() == want and stock_knobs() == sk and b8(uc, T.O_KNOB) == k + 1, (sp12(), want))
        check(f"    the bar: {names[i]}", bar(i))
        o = lights()
        wl = [tc if j == k else pc if j in XL else 0 for j in range(8)]
        check(f"    knob lights: K{k + 1} the track's colour, the page's knobs' others the page's, {', '.join(f'K{j + 1}' for j in dark)} dark",
              o == wl, [f"{x:06x}" for x in o])
    for k in dark:
        knob(uc, k, 4)
    check(f"  {', '.join(f'K{j + 1}' for j in dark)} turned: nothing (Stock+, the stock, the knob shown)",
          sp12() == want and stock_knobs() == sk and b8(uc, T.O_KNOB) == XL[-1] + 1, (sp12(), stock_knobs(), sk))
    shf = ptr(uc, u32(uc, C.CTRL + 0xC), 0)
    uc.mem_write(shf, bytes([1]))
    knob(uc, 1, 3)
    uc.mem_write(shf, bytes([0]))
    want[x1] += 12
    check("  Shift + K2 +3: 4 a click (fine)", sp12() == want, (sp12(), want))
    knob(uc, 0, -200)
    check("  K1 -200: held at 0", spval(uc, s, x0) == 0, spval(uc, s, x0))
    knob(uc, 0, 200)
    check("  K1 +200: held at 16383", spval(uc, s, x0) == 16383, spval(uc, s, x0))
    blue, red = STOCK_CLR
    knob(uc, 0, 7)
    before, plain = sp12(), lights()
    hx = lambda xs: [f"{x:06x}" for x in xs]
    o = clr_turn(uc, 0, T.CLR_N - 1, keep=True)
    check(f"  Clear held, K1 {T.CLR_N - 1} clicks right: nothing yet, the lights unchanged", sp12() == before and o == plain, (hx(o), hx(plain)))
    o = clr_turn(uc, 1, T.CLR_N, -1, keep=True)
    check(f"  K2 {T.CLR_N} clicks left: no value moved, K2 the stock's red ({red:06x}), K3-K8 unchanged",
          sp12() == before and o[1] == red and o[2:] == plain[2:], hx(o))
    o = clr_turn(uc, 0, 1, keep=True)
    check(f"  K1's {T.CLR_N}th click right: {names[x0]} at its default, K1 the stock's blue ({blue:06x}), K2 still red",
          spval(uc, s, x0) == DEFS[x0] and o[0] == blue and o[1] == red, (spval(uc, s, x0), hx(o)))
    o = clr_turn(uc, 1, T.CLR_N, keep=True)
    xr = [T.X_IDX[k] for k in XL[2:4]]
    check(f"  K2 {T.CLR_N} clicks right: {names[x1]} at its default, K2 blue, the others kept",
          spval(uc, s, x1) == DEFS[x1] and o[1] == blue and all(spval(uc, s, x) == want[x] for x in xr), (spval(uc, s, x1), hx(o)))
    o = clr_turn(uc, 0, 0)
    after = lights()
    check("  Clear let go: no knob blue or red", blue not in after and red not in after, hx(after))
    knob(uc, 0, 20)
    v = spval(uc, s, x0)
    clr_turn(uc, 0, T.CLR_N // 2 + 5); clr_turn(uc, 0, T.CLR_N // 2 + 5)
    check(f"  K1 {T.CLR_N // 2 + 5} clicks right twice, Clear let go between: the count starts again, kept ({v})", spval(uc, s, x0) == v, spval(uc, s, x0))
    clr_turn(uc, 0, 6, 7)
    check(f"  K1 six turns of 7 with Clear held (the count is of clicks): {names[x0]} at its default", spval(uc, s, x0) == DEFS[x0], spval(uc, s, x0))
    seen = []
    for _ in range(4):
        pad(uc, T.PAD_KNOB); unpad(uc, T.PAD_KNOB)
        seen.append(b8(uc, T.O_KNOB))
    want_seen = [XL[j % len(XL)] + 1 for j in range(1, 5)]
    check(f"  pad 25 tapped 4 times from K1: {', '.join(f'K{j}' for j in want_seen)}", seen == want_seen, seen)
    if SCANFX and SB:
        k8 = T.X_IDX.index(7)
        knob(uc, k8, clicks_to(7, spval(uc, s, 7), 8192) + 4 * 3 + 1)
        shift_ = lambda on: uc.mem_write(shf, bytes([on]))
        st0 = SBM.step_of(uiv(7, spval(uc, s, 7)))
        shift_(1); knob(uc, k8, 2); shift_(0)
        st1 = SBM.step_of(uiv(7, spval(uc, s, 7)))
        led(uc, head)
        check(f"  pad 28 K{k8 + 1} at 1 bar, Shift + turn right: 1 bar T on the same pad in pad 28's colour",
              (st0, st1) == (3, 11) and list(out(uc)[16:24]) == want_x_bar(uc, s, 7), (st0, st1))
        shift_(1); knob(uc, k8, -1); shift_(0)
        check(f"  Shift + K{k8 + 1} left: back to 1 bar", SBM.step_of(uiv(7, spval(uc, s, 7))) == 3)
    uc.mem_write(ptr(uc, C.TRANSPORT, 1), bytes([1]))
    kk = XL[2] if len(XL) > 2 else XL[1]
    knob(uc, kk, 1)
    check(f"  Record armed, K{kk + 1} turned: the bar in the track's colour (nothing records here)", bar(T.X_IDX[kk]))
    uc.mem_write(ptr(uc, C.TRANSPORT, 1), bytes([0]))
    pad(uc, T.PAD_PAGE0); unpad(uc, T.PAD_PAGE0); led(uc, head)
    k0, c0 = kval(uc, s, 0), spval(uc, s, 10)
    knob(uc, 0, 2)
    check("  pad 27: the parameter editor, K1 the stock's again", kval(uc, s, 0) != k0 and spval(uc, s, 10) == c0)


def stockplus_shapes(fw, ram, head):
    """(shapes) the Stock+ page with pshape: K1-K8 = SP_MAP's values, their lights and bar, c_spdsp's words with the shapes, the tables"""
    import pshape as PS
    import stretch as STR
    import voicefx as V
    SH = {k: int(v, 16) for k, v in MAN["report"]["pshape"]["labels"].items()}
    uc = setup(fw, ram)
    s = sel(uc)
    tc = u32(uc, T.COLOURS + 4 * T.TRK_SLOTS[s])
    def stock_knobs(): return [kval(uc, s, k) for k in range(8)] + [kval(uc, s, T.FINE[k]) for k in T.FINE]
    def page(): return [shval(uc, s, i) for i in T.SP_MAP]
    tap(uc, s); led(uc, head)
    pad(uc, pp(1)); unpad(uc, pp(1)); led(uc, head)
    check("shapes: pad 27 shows Stock+, the selected track's bit set", b8(uc, T.O_PAGE) == T.PAGE_SP and spb(uc) == 1 << s, hex(spb(uc)))
    want = [0 if i in (10, 6) or i >= 12 else DEFS[i] for i in T.SP_MAP]
    check("  K1-K8 at their defaults (both shapes 0)", page() == want, (page(), want))
    call(uc, SH["c_shval"], s, 6)
    r6 = uc.reg_read(UC_ARM_REG_R0)
    call(uc, SH["c_shval"], s, 10)
    check("  c_shval: value 6 without K7's XOR (0), value 10 as it is (0)", r6 == 0 and uc.reg_read(UC_ARM_REG_R0) == 0, (r6,))
    seen = []
    for _ in range(9):
        pad(uc, T.PAD_KNOB); unpad(uc, T.PAD_KNOB)
        seen.append(b8(uc, T.O_KNOB))
    check(f"  pad 25 tapped 9 times: K2 .. K{SPN}, K1, .. (none skipped)", seen == [j % SPN + 1 for j in range(1, 10)], seen)
    sk = stock_knobs()
    deltas = (3, 5, -3, 7, 2, 4, 9, -5)
    v0 = page()
    for k, d in enumerate(deltas):
        knob(uc, k, d)
    want = [turned(i, v, d) if k < SPN else v for k, (i, v, d) in enumerate(zip(T.SP_MAP, v0, deltas))]
    check(f"  K1-K8 turned: K1-K{SPN} 128 a click, " + (f"K{SPN + 1}-K8 nothing; " if SPN < 8 else "") + "the stock's knobs untouched",
          page() == want and stock_knobs() == sk and b8(uc, T.O_KNOB) == SPN, (page(), want))
    kL, kE = T.SP_MAP.index(6), T.SP_MAP.index(10)       # the knobs of the LFO's and the envelope's shape
    check("  the LFO's shape stored as it is shown (K7's XOR taken off)", spval(uc, s, 6) == want[kL] ^ 8192, spval(uc, s, 6))
    shf = ptr(uc, u32(uc, C.CTRL + 0xC), 0)
    uc.mem_write(shf, bytes([1]))
    knob(uc, kL, 2)
    uc.mem_write(shf, bytes([0]))
    if SB:
        n = want[kL] * 10 >> 14
        check(f"  Shift + K{kL + 1} right: the LFO shape {n + 1} -> {n + 9} on the same pad (2nd sweep)", shval(uc, s, 6) == (2 * (n + 8) + 1) * T.SB_N10,
              shval(uc, s, 6))
    else:
        check("  Shift + K4 +2: 4 a click (fine)", shval(uc, s, 6) == want[kL] + 8, shval(uc, s, 6))
    for k in (kE, kL):
        clr_turn(uc, k, T.CLR_N)
    check(f"  Clear + K{kE + 1}, Clear + K{kL + 1}: both shapes back to the first (0)", shval(uc, s, 10) == 0 and shval(uc, s, 6) == 0 and spval(uc, s, 6) == 8192,
          (shval(uc, s, 10), shval(uc, s, 6)))
    knob(uc, kE, 40); knob(uc, kL, 70)
    for k in range(8):
        uc.mem_write(SLOT + T.O_KNOB, bytes([k + 1]))
        ks = k if k < SPN else 0                            # a dark knob shown: K1
        bar_check(uc, head, s, ks, f"  K{k + 1} shown: the bar of K{ks + 1}, its value {shval(uc, s, T.SP_MAP[ks])}", sp=True)
        led(uc, head); o = out(uc)[T.LED_KNOB0:T.LED_KNOB0 + 8]
        wl = []
        for j in range(8):
            if j == ks:
                wl.append(tc)
                continue
            if j >= SPN:
                wl.append(0)
                continue
            v = uiv(T.SP_MAP[j], shval(uc, s, T.SP_MAP[j]))
            b = min(127, (abs(v - 8192) << 1 if j in T.SP_MIDK else v) >> 7)
            wl.append(scl(PAGES[T.PAGE_SP], ((T.STOCK_B[0] * b + T.STOCK_B[1]) >> 8) * T.KNOB_LVL >> 8))
        check(f"    knob lights: K{ks + 1} the track's colour, the others Stock+'s colour by their value" + (f", K{SPN + 1}-K8 dark" if SPN < 8 else ""), list(o) == wl,
              ([f"{x:06x}" for x in o], [f"{x:06x}" for x in wl]))
    if SHAPEBAR:
        full_w = scl(PAGES[T.PAGE_SP] if SHAPEBAR == "page" else 0xFFFFFF, 255 * dim_mul(uc) >> 8)
        for k, clicks in ((kE, 8), (kL, 13)):
            i = T.SP_MAP[k]
            nsh = T.SHAPE_N[i]
            clr_turn(uc, k, T.CLR_N)
            uc.mem_write(SLOT + T.O_KNOB, bytes([k + 1]))
            bad, pads, whites = [], [], []
            for _ in range(nsh + 2):
                led(uc, head)
                o = list(out(uc)[16:24])
                if o != want_sp_bar(uc, s, k):
                    bad.append(shval(uc, s, i))
                lit = [j for j in range(8) if o[j]]
                pads.append(lit[0] if len(lit) == 1 else None)
                whites.append(len(lit) == 1 and o[lit[0]] == full_w)
                knob(uc, k, clicks)
            want_p = [n % 8 for n in range(nsh)] + [(nsh - 1) % 8] * 2
            want_w = [n >= 8 for n in range(nsh)] + [True] * 2
            check(f"  shape bar K{k + 1}: {clicks} clicks a shape, all {nsh}: one pad lit, pads 17-24 in the track's colour, then {'Stock+ sky' if SHAPEBAR == 'page' else 'white'}; "
                  f"the last stays at the end", not bad and pads == want_p and whites == want_w, (bad, pads, whites))

    uc = setup(fw, ram)
    s = sel(uc)
    writes = []
    def wr(u, a, n, d):
        if u.reg_read(UC_ARM_REG_R0) == 1:
            writes.append((u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_R1), u.reg_read(UC_ARM_REG_R2)))
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE, wr, None, TH.WR16, TH.WR16 + 1)
    yb = int(MAN["report"]["pitchmod"]["y_base"], 16)
    vy = V.Y_BASE + 0x300
    bpm = uc.mem_read(ptr(uc, SPM.TEMPO, 0), 1)[0]
    steps = PS.step_table()
    def want_words(t):
        v = [spval(uc, t, k) for k in range(12)]
        u = list(v)
        v[10] = 0
        w = SPM.words2(v, t, k8sync=True, bpm=bpm)
        w[yb + SPM.PM.OFF_R + t] = SPM.k3_rate(v[2], bpm)
        if not w[yb + SPM.PM.OFF_R + t]:
            w[yb + SPM.PM.OFF_PH + t] = SPM.K3_MIDPH
        i, f = v[1] >> 7, v[1] & 127
        w[yb + SPM.PM.OFF_D + t] = steps[i] + ((steps[i + 1] - steps[i]) * f >> 7)
        del w[vy + V.DTYPE + t]
        w[STR.STRETCH + t] = PS.shape_index(u[10], PS.NE)
        w[PS.SHP_L + t] = PS.shape_index(u[6] ^ 8192, PS.NL)
        return {a: x & 0xFFFFFF for a, x in w.items()}
    RD = int(MAN["report"]["fshape"].get("rd", "0x10000"), 16) if "fshape" in MAN["report"] else 0x10000   # (px) fshape's depth words
    def trk(): return {y & 0x7FFF: x >> 8 for c, x, y in writes if y & 0x7FFF < PS.ENV_Y and not RD <= y & 0x7FFF < RD + 8}
    FB = int(MAN["report"]["fshape"]["fb"], 16) if "fshape" in MAN["report"] else 0x10000
    GK = int(MAN["report"]["fshape"].get("gk", "0x10000"), 16) if "fshape" in MAN["report"] else 0x10000   # (glide) fshape's glide words
    FR = int(MAN["report"]["fshape"].get("fr", "0x10000"), 16) if "fshape" in MAN["report"] else 0x10000   # (fade) fshape's fade words
    def tabs(): return [(y & 0x7FFF, x >> 8) for c, x, y in writes if (PS.ENV_Y <= y & 0x7FFF < FB or VOLT and PS.VOL_Y <= y & 0x7FFF < 0x2000)
                        and not GK <= y & 0x7FFF < GK + 8 and not FR <= y & 0x7FFF < FR + 16]
    def ok_for(tracks):
        g = trk()
        others = {a for t in range(8) if t not in tracks for a in want_words(t)} - {a for t in tracks for a in want_words(t)}
        bad = {hex(a): (hex(g.get(a, -1)), hex(w)) for t in tracks for a, w in want_words(t).items() if g.get(a) != w}
        return all(c == 1 and y & 0x8000 for c, x, y in writes) and not bad and not (others & set(g)), (bad, sorted(hex(a) for a in others & set(g)))
    ready = int(MAN["report"]["cthresh"]["slot"], 16) + 1
    wait = rhstate.ST + rhstate.OFF["spwait"][0]
    tap(uc, s); led(uc, head)
    pad(uc, pp(1)); unpad(uc, pp(1))
    for k, d in ((0, 21), (3, 50), (1, -9)):
        knob(uc, k, d)
    led(uc, head)
    check("shapes, core 1: no program upload seen, no words written (no tables either)", writes == [], len(writes))
    uc.mem_write(ready, bytes([TH.READY]))
    uc.mem_write(wait, bytes([SPM.SP_WAIT - 1]))
    led(uc, head)
    tw = PS.table_words(MAN["report"]["pshape"].get("v2", False), VOLT)
    want_t = [(PS.ENV_Y + i, w) for i, w in enumerate(tw) if w is not None]
    check(f"  READY, Stock+'s wait done in this frame: no track words yet, the first {PS.WPF} table words from Y:${PS.ENV_Y:X}",
          trk() == {} and tabs() == want_t[:PS.WPF], (trk(), tabs()[:6]))
    led(uc, head)
    rnd = uc.mem_read(SPB + 2, 1)[0]
    ok, info = ok_for({s, rnd})
    check(f"  the next frame: track {s + 1}'s words with its shapes (env {shval(uc, s, 10) * PS.NE >> 14}, LFO {shval(uc, s, 6) * PS.NL >> 14}) "
          f"and the decay as a step, the round's track {rnd + 1}", ok, info)
    check(f"  and the next {PS.WPF} table words", tabs() == want_t[:2 * PS.WPF], tabs()[:10])
    n = 1
    if MAN["report"]["pshape"].get("once"):
        while len(tabs()) < len(want_t) and n < 400:
            led(uc, head)
            n += 1
        for _ in range(300):
            led(uc, head)
        check(f"  {n} frames: every table word once in order ({len(want_t)}: {PS.NE} envelopes, {PS.NL} LFOs"
              + (f", {PS.NG} gates" if VOLT else "") + "), then none in 300 more frames",
              tabs() == want_t, (len(tabs()), n))
        uc.mem_write(ready, bytes([0]))
        led(uc, head)
        uc.mem_write(ready, bytes([TH.READY]))
        uc.mem_write(wait, bytes([SPM.SP_WAIT - 1]))
        del writes[:]
        led(uc, head)
        check(f"  a new program upload, Stock+'s wait done: the tables again from Y:${PS.ENV_Y:X}", tabs() == want_t[:PS.WPF], tabs()[:6])
        return
    while len(tabs()) < len(want_t) + PS.WPF and n < 400:
        led(uc, head)
        n += 1
    got_t = tabs()
    check(f"  {n} frames: every table word once in order ({len(want_t)}: {PS.NE} envelopes, {PS.NL} LFOs), then from the start again",
          got_t[:len(want_t)] == want_t and got_t[len(want_t):len(want_t) + PS.WPF] == want_t[:PS.WPF], (len(got_t), n))


def stockplus_page(fw, ram, head):
    uc = setup(fw, ram)
    s = sel(uc)
    tap(uc, s); led(uc, head)
    uc.mem_write(SLOT + T.O_KNOB, bytes([6]))
    pad(uc, pp(1)); unpad(uc, pp(1))
    check("Stock+ page, opened from the parameter editor on K6: Stock+'s own knob (none turned yet: K1)", b8(uc, T.O_KNOB) == 0, b8(uc, T.O_KNOB))
    bar_check(uc, head, s, 0, "  the bar shows Stock+'s K1", sp=True)
    seen = []
    for _ in range(9):
        pad(uc, T.PAD_KNOB); unpad(uc, T.PAD_KNOB)
        seen.append(b8(uc, T.O_KNOB))
    if FP:
        check("  pad 25 tapped 9 times: K2 .. K4, K7, K8, K1 .. K4 (K5 / K6 skipped)", seen == [2, 3, 4, 7, 8, 1, 2, 3, 4], seen)
    else:
        check("  pad 25 tapped 9 times: K2 .. K8, K1, K2 (Stock+'s eight knobs)", seen == [2, 3, 4, 5, 6, 7, 8, 1, 2], seen)
    pad(uc, T.PAD_PAGE0); unpad(uc, T.PAD_PAGE0)
    check("  back to the parameter editor: K6 again", b8(uc, T.O_KNOB) == 6, b8(uc, T.O_KNOB))
    pad(uc, T.PAD_PAGE0); unpad(uc, T.PAD_PAGE0)
    check("  pad 27 tapped again: nothing swapped (K6)", b8(uc, T.O_KNOB) == 6, b8(uc, T.O_KNOB))
    pad(uc, pp(1)); unpad(uc, pp(1))
    check(f"  Stock+ again: K{seen[-1]} (its own knob kept)", b8(uc, T.O_KNOB) == seen[-1], b8(uc, T.O_KNOB))
    uc = setup(fw, ram)
    s = sel(uc)
    tc = u32(uc, T.COLOURS + 4 * T.TRK_SLOTS[s])
    def setplay(playing, armed): uc.mem_write(ptr(uc, C.TRANSPORT, 0), bytes([playing])); uc.mem_write(ptr(uc, C.TRANSPORT, 1), bytes([armed]))
    def stock_knobs(): return [kval(uc, s, k) for k in range(8)] + [kval(uc, s, T.FINE[k]) for k in T.FINE]
    def sp4(): return [spval(uc, s, k) for k in range(4)]
    def sp12(): return [spval(uc, s, k) for k in range(12)]
    def sp_light(j, k, so, shift):
        """(fpage) knob j's light with knob k shown: K5 / K6 dark, K7 / K8 not shown the page's colour at KNOB_LVL of the stock's brightness of their value"""
        if j in T.SP_EMPTY:
            return 0
        if j == k:
            return tc
        if j >= 4:
            v = spval(uc, s, T.SP_OWN[j])
            b = min(127, (abs(v - 8192) << 1 if j == 7 else v) >> 7)
            return scl(PAGES[T.PAGE_SP], ((T.STOCK_B[0] * b + T.STOCK_B[1]) >> 8) * T.KNOB_LVL >> 8)
        return tint(so[j], scl(PAGES[T.PAGE_SP], T.KNOB_LVL))
    setplay(0, 0)
    tap(uc, s); led(uc, head)
    pad(uc, pp(1)); unpad(uc, pp(1)); led(uc, head)
    check("Stock+: pad 28 shows its page, the selected track's bit set", b8(uc, T.O_PAGE) == 1 and spb(uc) == 1 << s, hex(spb(uc)))
    check("  the 12 values at their defaults", sp12() == list(DEFS), sp12())
    sk = stock_knobs()
    for k, d in ((0, 5), (1, -3), (2, 2), (3, 7)):
        knob(uc, k, d)
    want = [DEFS[0] + 5 * 128, DEFS[1] - 3 * 128, DEFS[2] + 2 * 128, DEFS[3] + 7 * 128]
    check("  K1 +5, K2 -3, K3 +2, K4 +7: Stock+'s values 128 a click, the stock's knobs untouched", sp4() == want and stock_knobs() == sk,
          (sp4(), want))
    knob(uc, 3, -20)
    check("  K4 -20: held at 0", spval(uc, s, 3) == 0, spval(uc, s, 3))
    shf = ptr(uc, u32(uc, C.CTRL + 0xC), 0)                # the stock's Shift flag (its release stops the emulation)
    uc.mem_write(shf, bytes([1]))
    knob(uc, 1, 3)
    uc.mem_write(shf, bytes([0]))
    check("  Shift + K2 +3: 4 a click (fine)", spval(uc, s, 1) == 8192 - 3 * 128 + 12 and b8(uc, T.O_OPEN) == 1, spval(uc, s, 1))
    v = sp12()
    for k, d in ((4, 3), (5, 2), (6, -4), (7, 5)):
        knob(uc, k, d)
    want = list(v)
    want[4], want[9], want[6], want[7] = 3 * 128, 2 * 128, 8192 - 4 * 128, v[7] + 5 * 128
    if FP:
        want[4], want[9], want[6], want[8], want[11] = v[4], v[9], v[6], v[8], max(0, v[11] - 4 * 128)
    check(f"  K5 +3, K6 +2{' (nothing)' if FP else ''}, K7 -4{' (the scan depth)' if FP else ''}, K8 +5: Stock+'s values 128 a "
          "click, the stock's knobs untouched",
          sp12() == want
          and stock_knobs() == sk and b8(uc, T.O_KNOB) == 8, (sp12(), want))
    uc.mem_write(shf, bytes([1]))
    for k, d in ((4, 2), (5, 3), (6, 1), (7, 2)):
        knob(uc, k, d)
    kw = scl(T.SHIFT_RGB, T.KNOB_LVL)
    for k in range(8):
        uc.mem_write(SLOT + T.O_KNOB, bytes([k + 1]))
        bar_check(uc, head, s, k, f"  Shift held, K{k + 1} shown: the bar {'its second layer in white' if k >= 4 else 'as without Shift'} "
                  f"({sp_index(k, True)})", sp=True, shift=True)
        led(uc, PREV_LED); so = out(uc, PREV_OUT)[T.LED_KNOB0:T.LED_KNOB0 + 8]
        led(uc, head); o = out(uc)[T.LED_KNOB0:T.LED_KNOB0 + 8]
        wl = [sp_light(j, k, so, True) if FP else (T.SHIFT_RGB if j >= 4 else tc) if j == k
              else tint(so[j], kw if j >= 4 else scl(PAGES[T.PAGE_SP], T.KNOB_LVL)) for j in range(8)]
        check(f"    knob lights: K5-K8 white (K{k + 1} shown at full), K1-K4 as without Shift", list(o) == wl,
              ([f"{x:06x}" for x in o], [f"{x:06x}" for x in wl]))
    if not FP:
        uc.mem_write(SLOT + T.O_KNOB, bytes([5]))
        v8 = spval(uc, s, 8)
        knob(uc, 4, -(v8 // 128) - 1)
        bar_check(uc, head, s, 4, f"  Shift held, K5's second layer {spval(uc, s, 8)}: pad 17 the rest pad, dim white", sp=True, shift=True)
        knob(uc, 4, 1)
        bar_check(uc, head, s, 4, f"  Shift held, K5's second layer {spval(uc, s, 8)}: pad 17 white", sp=True, shift=True)
        knob(uc, 4, v8 // 128 - 1)
    uc.mem_write(shf, bytes([0]))
    if FP:
        want[11], want[7] = want[11] + 4, want[7] + 2 * 4
        check("  Shift + K5 +2, K6 +3: nothing; Shift + K7 +1, K8 +2: 4 a click (fine)", sp12() == want, (sp12(), want))
    else:
        want[8], want[5], want[10], want[11] = 8192 + 2 * 128, 3 * 128, 128, 2 * 128
        check("  Shift + K5 +2, K6 +3 (the type), K7 +1, K8 +2: their second layers 128 a click", sp12() == want, (sp12(), want))
    if FP:
        for k in (4, 5, 6, 7):
            o = clr_turn(uc, k, T.CLR_N, keep=k < 7)
        check("  Clear held, K5-K8 turned right: K7 / K8 the stock's blue, K5 / K6 dark", o[6] == o[7] == STOCK_CLR[0] and o[4] == o[5] == 0,
              [f"{x:06x}" for x in o])
    else:
        held = u32(uc, C.CTRL + T.HELD)
        uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", held | 1 << SPM.BIT_CLEAR))
        knob(uc, 5, 1); knob(uc, 6, 1)
        uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", held))
    if FP:
        want[11], want[7] = 0, DEFS[7]
        check(f"  Clear + K5-K8: K5 / K6 nothing, scan depth 0, scan speed its default ({DEFS[7]})", sp12() == want, (sp12(), want))
    else:
        for i in (5, 9, 6, 10):
            want[i] = DEFS[i]
        check("  Clear + K6, Clear + K7: both of their layers at the defaults", sp12() == want, (sp12(), want))
    if FP:
        v1 = spval(uc, s, 1)
        clr_turn(uc, 1, 3 * T.CLR_N, -1); clr_turn(uc, 1, T.CLR_N - 1)
        check(f"  Clear + K2 left, then {T.CLR_N - 1} clicks right: kept ({v1})", spval(uc, s, 1) == v1 and stock_knobs() == sk, spval(uc, s, 1))
        clr_turn(uc, 1, T.CLR_N)
    else:
        held = u32(uc, C.CTRL + T.HELD)
        uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", held | 1 << SPM.BIT_CLEAR))
        knob(uc, 1, 1)
        uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", held))
    check("  Clear + K2: its default (8192)", spval(uc, s, 1) == 8192 and stock_knobs() == sk, spval(uc, s, 1))
    for k, d in ((1, 9), (2, -30)):
        knob(uc, k, d)
    for k in range(8):
        uc.mem_write(SLOT + T.O_KNOB, bytes([k + 1]))
        bar_check(uc, head, s, k, f"  K{k + 1} shown: the bar its Stock+ value {spval(uc, s, sp_index(k))}", sp=True)
        led(uc, PREV_LED); so = out(uc, PREV_OUT)[T.LED_KNOB0:T.LED_KNOB0 + 8]
        led(uc, head); o = out(uc)[T.LED_KNOB0:T.LED_KNOB0 + 8]
        want = [sp_light(j, k, so, False) if FP else tc if j == k else tint(so[j], scl(PAGES[T.PAGE_SP], T.KNOB_LVL)) for j in range(8)]
        check(f"    knob lights: K{k + 1} the track's colour at full, the others Stock+'s colour at KNOB_LVL of Stock+'s brightness",
              list(o) == want, ([f"{x:06x}" for x in o], [f"{x:06x}" for x in want]))
    uc.mem_write(SLOT + T.O_KNOB, bytes([1]))
    if FP:
        sp_save = (spval(uc, s, 11), spval(uc, s, 7))
        call(uc, SPL["c_spput"], s, 11, 0)
        call(uc, SPL["c_spput"], s, 7, 8192)
        led(uc, head); o = out(uc)[T.LED_KNOB0:T.LED_KNOB0 + 8]
        check("  K7 at 0 (no scan depth) and K8 at the middle (stopped): both lit at the stock's dimmest, not dark",
              o[6] == sp_light(6, 0, None, False) != 0 and o[7] == sp_light(7, 0, None, False) != 0, [f"{x:06x}" for x in o[6:8]])
        call(uc, SPL["c_spput"], s, 11, sp_save[0])
        call(uc, SPL["c_spput"], s, 7, sp_save[1])
        clear_keeps(uc, head, "the Stock+ page")
    led(uc, head); o = out(uc)
    so = out(uc, PREV_OUT)
    want = [sel_rgb(uc, tc) if t == s else tint(so[T.LED_TRK0 + t], PAGES[T.PAGE_SP]) for t in range(8)]
    check(f"  track numbers: the selected one its colour, the others Stock+'s colour {PAGES[T.PAGE_SP]:06x}",
          list(o[T.LED_TRK0:T.LED_TRK0 + 8]) == want and all(w for t, w in enumerate(want) if t != s), ([f"{x:06x}" for x in o[T.LED_TRK0:T.LED_TRK0 + 8]], [f"{x:06x}" for x in want]))
    phases = []
    for _ in range(3):
        tick(uc, 256)
        f = led(uc, head); o = out(uc)
        phases.append((o[T.LED_TRK0 + s], o[40 + s], f[40 + s], led(uc, PREV_LED)[40 + s], sel_rgb(uc, tc)))
    check("  across 768 ms: the selected track's number flashing in its colour, LED 40 + track as the stock draws it (no Stock+ blink)",
          all(p[0] == p[4] and p[2] == p[3] != SPM.COL_BLINK for p in phases) and len({p[1] for p in phases}) == 1
          and (all(p[0] != 0 for p in phases) if MAN['report']['tmenu'].get('trackpulse') else {p[0] for p in phases} == {0, tc}), [f"{a:06x}/{b:06x}/{c:#x}/{d:#x}" for a, b, c, d, e in phases])

    setplay(0, 1)
    tick(uc, 1000)
    sk = stock_knobs()
    knob(uc, 0, 3)
    bar_check(uc, head, s, 0, "  Record armed, K1 turned: the bar in the track's colour (nothing records on Stock+)", sp=True)
    check("    the stock's knobs untouched", stock_knobs() == sk)
    pad(uc, 4)
    f = led(uc, head)
    bar_check(uc, head, s, 0, "  Record armed, step 5 held: the bar in the track's colour", sp=True)
    check("    the held step's pad white", f[4] == T.COL_FULL, hex(f[4]))
    unpad(uc, 4)
    setplay(0, 0)

    pad(uc, T.PAD_PAGE0); unpad(uc, T.PAD_PAGE0); led(uc, head)
    v = sp4()
    k0 = kval(uc, s, 0)
    knob(uc, 0, 2)
    check("pad 27 back to the parameter editor: no Stock+ bit, K1 the stock's again", spb(uc) == 0 and kval(uc, s, 0) != k0 and sp4() == v,
          (hex(spb(uc)), k0, kval(uc, s, 0)))
    other = (s + 1) % 8
    def vals(t): return [spval(uc, t, k) for k in range(12)]
    held = u32(uc, C.CTRL + T.HELD)
    uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", held | 1 << SPM.BIT_DUP))
    press(uc, s); release(uc, s); press(uc, other); release(uc, other)
    uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", held))
    check(f"Duplicate held, track {s + 1} then {other + 1}: Stock+'s values copied", vals(other) == vals(s) != list(DEFS), (vals(other), vals(s)))
    uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", held | 1 << SPM.BIT_CLEAR))
    press(uc, other); release(uc, other)
    if MAN['report'].get('trackreset'):
        check('first Clear + track press preserves Stock+ values', vals(other) == vals(s))
        press(uc, other); release(uc, other)
    uc.mem_write(C.CTRL + T.HELD, struct.pack("<I", held))
    check(f"Clear held + track {other + 1}: its Stock+ defaults, track {s + 1} kept", vals(other) == list(DEFS) and vals(s)[:4] == v,
          (vals(other), vals(s)))

    uc = setup(fw, ram)
    s = sel(uc)
    writes = []
    def wr(u, a, n, d):
        if u.reg_read(UC_ARM_REG_R0) == 1:                             # core 1's (core 0's: the granular, emu_grain.py)
            writes.append((u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_R1), u.reg_read(UC_ARM_REG_R2)))
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
    uc.hook_add(UC_HOOK_CODE, wr, None, TH.WR16, TH.WR16 + 1)
    yb = int(MAN["report"]["pitchmod"]["y_base"], 16)
    bpm = uc.mem_read(ptr(uc, SPM.TEMPO, 0), 1)[0]
    def want_words(t):
        """{Y address: word} c_spdsp writes for track t (v2, k8sync, k3sync)"""
        v = [spval(uc, t, k) for k in range(12)]
        if NOCRUSH:
            v[10] = 0                                                  # no bitcrusher: drive type 0 whatever value 10 holds
        w = SPM.words2(v, t, k8sync=True, bpm=bpm)
        w[yb + SPM.PM.OFF_R + t] = SPM.k3_rate(v[2], bpm)
        if not w[yb + SPM.PM.OFF_R + t]:
            w[yb + SPM.PM.OFF_PH + t] = SPM.K3_MIDPH
        return {a: x & 0xFFFFFF for a, x in w.items()}
    def got(): return {y & 0x7FFF: x >> 8 for c, x, y in writes if c == 1}
    def ok_for(tracks):
        g = got()
        others = {a for t in range(8) if t not in tracks for a in want_words(t)} - {a for t in tracks for a in want_words(t)}
        bad = {hex(a): (hex(g.get(a, -1)), hex(w)) for t in tracks for a, w in want_words(t).items() if g.get(a) != w}
        return all(c == 1 and y & 0x8000 for c, x, y in writes) and not bad and not (others & set(g)), (bad, sorted(hex(a) for a in others & set(g)))
    ready = int(MAN["report"]["cthresh"]["slot"], 16) + 1
    wait = rhstate.ST + rhstate.OFF["spwait"][0]
    tap(uc, s); led(uc, head)
    pad(uc, pp(1)); unpad(uc, pp(1))
    for _ in range(3):
        led(uc, head)
    check("core 1: no program upload seen, no words written", writes == [] and uc.mem_read(ready, 1)[0] == 0, len(writes))
    uc.mem_write(ready, bytes([TH.BLOCKED]))
    led(uc, head)
    check("  the mode 1 program: no words written", writes == [], len(writes))
    uc.mem_write(ready, bytes([TH.READY]))
    uc.mem_write(wait, bytes([SPM.SP_WAIT - 1]))
    led(uc, head)
    check(f"  READY, the wait {SPM.SP_WAIT - 1}: one more frame of waiting, nothing written", writes == [] and uc.mem_read(wait, 1)[0] == SPM.SP_WAIT,
          len(writes))
    led(uc, head)
    rnd = uc.mem_read(SPB + 2, 1)[0]
    ok, info = ok_for({rnd})
    check(f"  the next frame: the round's track {rnd + 1}, all its words (K1-K8 and the Shift layers), no other track's", ok, info)
    writes.clear()
    knob(uc, 0, 9); knob(uc, 3, 4)
    if FP:
        knob(uc, 4, 6); knob(uc, 5, -9); knob(uc, 6, 30); knob(uc, 7, -40)   # the ring's amount and frequency, the scan's depth and speed
    led(uc, head)
    rnd = uc.mem_read(SPB + 2, 1)[0]
    ok, info = ok_for({s, rnd})
    check(f"  K1 +9, K4 +4{', K5 +6, K6 -9, K7 +30, K8 -40' if FP else ''} on track {s + 1}: its words written with the round's track {rnd + 1}", ok, info)
    writes.clear()
    for _ in range(8):
        led(uc, head)
    a_words = [y & 0x7FFF for _, _, y in writes if y & 0x7FFF in range(yb + SPM.PM.OFF_A, yb + SPM.PM.OFF_A + 8)]
    ok, info = ok_for(set(range(8)))
    check("  8 frames: every track's words written once (the round)", sorted(a_words) == [yb + SPM.PM.OFF_A + t for t in range(8)] and ok,
          (sorted(hex(a) for a in a_words), info))
    if FP:
        pad(uc, pp(T.PAGE_X)); unpad(uc, pp(T.PAGE_X))
        for k, d in ((0, 40), (1, 100), (2, 7), (3, 12), (4, -20))[:T.X_KNOBS]:
            knob(uc, k, d)
        writes.clear()
        for _ in range(8):
            led(uc, head)
        ok, info = ok_for(set(range(8)))
        check(f"  pad 29's page, K1-K{T.X_KNOBS} turned on track {s + 1}: its words as the model's", ok, info)
        if NOCRUSH:
            import voicefx as V
            vd = V.Y_BASE + 0x300
            call(uc, SPL["c_spput"], s, 10, 12000)
            writes.clear()
            for _ in range(8):
                led(uc, head)
            g = got()
            check(f"  value 10 at 12000 on track {s + 1}: drive type 0, no bitcrush mask written",
                  g.get(vd + V.DTYPE + s) == 0 and vd + V.DMASK + s not in g, (g.get(vd + V.DTYPE + s), g.get(vd + V.DMASK + s)))


if __name__ == "__main__":
    main()
