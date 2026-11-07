"""Track + (the track menu) and its automation viewer/editor, the knob bar (MIT; Circuit Rhythm 5706).

With pageclear=True (A0039): move pages to pads 26-31; Clear + page calls
pageclear.py to reset that page; pad 32 resets all pages only with Clear held.
Pad 32 flashes red while Clear is held, with short feedback after a reset.
The older pad numbers below describe builds without this flag.

  * a tap on the selected track's button (the track views, not Sidechain; no Shift / Clear / Duplicate held): the menu opens and stays open;
    a tap on it again closes it; a tap on another track selects it (the stock's) and the menu follows the selected track; (click) after
    a button that closes the menu, the first press of a track is the stock's only, the next on the same track counts; (twoview, in
    place of click's rule, as the stock's two-view buttons) a tap counts only when the stock's press left the container's mode as it was
    (a press that changes the view gives its first view), and Shift + a track (the stock ignores it) = its plain press, then the menu open;
    (bounce, in place of the HOLD_MS menu) as the stock's views: a press is a hold past STOCK_HOLD; a held track never opens or closes
    the menu (the stock shows that track while held and puts the earlier one back); another button held past STOCK_HOLD with the menu
    open closes it while held and opens it again on its release when the stock is back on a track view;
    (shiftled) while the stock's Shift flag is set, the track numbers in the stock's Shift tan, the selected one lit, open or closed;
  * a track's button held for HOLD_MS: the menu while it stays held, closed on its release;
  * any other button but Record, Play, Clear, Duplicate and Shift (ids 8-26, the stock's press switch): the menu closes and the button does its job;
    (viewlock) Shift + Patterns (View Lock) keeps the menu open;
    (momhold, with bounce) the selected track's button held past STOCK_HOLD shows the other view while held (closed: the menu; open:
    the stock's view) and gives back the view it started from on release, with no tap;
  * while open: pads 1-16 are the stock's steps, pressed with the step page's select flag set (p0 of the store [step object + 0x34], the
    step object [CONT + 0x74 + 4 t]): a press selects the step while held and never adds or removes one; pads 17-32 never reach the stock
    (their releases neither); pad 25 the track's colour at CYC_LVL (it picks the knob among the page's: K1-K8 on the parameter editor,
    K1-K4 on Stock+; Stock+ keeps its own knob, the other pages share one); pad 26 dark (a separator); pads 27-32 the pages,
    one for all tracks: 27 the parameter editor, 28 Stock+ (with stockplus), the rest reserved (dark, nothing; with testpages: 29-32
    test pages that act as the parameter editor, in TEST_RGB); each page pad in its page's colour (PAGE_RGB), full on the page shown,
    dim on the others; the page kept until power-off (the parameter editor at power-on);
  * (perpage) each track keeps its page: track t's page in the project's block (rhrec's tail + PG_OFF: "P", a check byte, a byte a track),
    written on a page pad; each LED frame the selected track's page comes from the block (a new project or a bad block: the parameter
    editor), so a track change and a project load show the track's own page;
  * the page's colour (white on the parameter editor) on the lights the menu draws white: the track numbers not selected, and the
    knob LEDs not on the bar at KNOB_LVL of their brightness; off the parameter editor the shown knob is the track's colour at full
    (not the stock's dim, not Stock+'s value), so it stands out by brightness on every track; the stock's red beats both; the bar's
    rest pads (0, the middle) always dim white;
  * (shapes, with pshape) the Stock+ page's K1-K8 = SP_MAP's values, one each, all eight here (c_shval / c_shput: the LFO's shape
    without K7's XOR): env shape, amount, decay, LFO shape, rate, depth, scan depth, scan speed; each lit by its value (SP_MIDK from
    the middle), the shown one in the track's colour; pshape's c_shframe each LED frame;
  * (filt, with fshape) pad 29 (PAGE_F) the filter page: K1-K6 fshape's values 12..17 (env shape, amount, decay, LFO shape, rate,
    depth), Shift + K1 / K4 Stock+'s filter type (5) / pitch follow (9) at 128 a click, K7 / K8 the stock's own K7 / K8 (the low-pass,
    the resonance: the turn goes to the stock); lights as Stock+'s (K2 / K5 from the middle), K7 / K8 the stock's brightness in the
    page's colour (k78white: white), Shift held K1 / K4 the stock's Shift tan and the bar tan when it shows them; the bar one pad a
    shape / filter type; nothing of ours records there; c_flframe each LED frame;
  * (vol, with filt and fshape's vol) pad 30 (PAGE_V) the movement page: K1-K3 fshape's values 18..20 (vol shape: the 10 LFOs and 6
    gates, rate, depth), Shift fine; K4-K8 dark, their turns reach nothing, pad 25 picks K1-K3; lit as the filter page's (K2 from the
    middle); the bar one pad a shape; nothing records there;
  * (syncbar, with filt) one bar language: the rate knobs (SB_RATES) through syncbar's c_uval / c_uput (synced right of the middle,
    free left of it); synced: the bar one pad a step as the shapes (step n: pad 17 + n % 8, 8-15 the page's colour); Shift + turn on
    a shape knob or a synced rate: right = the same pad on the 2nd sweep, left = on the 1st (nothing when already there or no shape
    there); the free half and the other knobs Shift fine; the filter page's type / follow on Shift + K7 / K8 (F_SHIFT2);
  * (depthfirst) each group's amount or depth first, so its first knob is heard with the defaults: Stock+ and the filter page K1 env
    amount, K2 env shape, K3 decay, K4 LFO depth, K5 LFO shape, K6 LFO rate (DF_SP_MAP / DF_F_MAP); pad 30 K1 vol depth, K2 shape,
    K3 rate (DF_V_MAP); the knobs lit from the middle by their value (MID_VALUES), not by their place;
  * (scanfx) the scan on pad 28: K7 depth, K8 speed, K3-K6 dark (X_SCAN, None = dark); pad 27's K7 / K8 dark and swallowed;
  * (pageorder) the page pads: 26 editor, 27 filter, 28 mix, 29 pitch (Stock+), 30 sample (none yet: dark), 31 FX (PADMAP_ORDER);
    the pages keep their numbers, only their pads move;
  * (mixpage) the mix page's eight knobs (DF_V_MAP_M): K1 vol depth, K2 vol shape, K3 vol rate, K4 pan depth, K5 move shape, K6 move
    rate, K7 / K8 reverb / delay send depth from the middle (fshape move, mixmove);
  * (pxrand) the pitch page's K7: the random pitch's depth (fshape's value 26); K8 dark; (glide) K8 the glide time (value 27);
    (fade) Shift + K7 the pitch LFO's fade-in (value 28, 128 a click), the bar shows it while Shift is held on K7;
  * (fclr, with syncbar) the filter page's K7 / K8 with Clear held: their turns counted as our knobs' (O_CLRR / O_CLRL), so the
    stock's reset (right) and automation delete (left) show the blue / red light there too;
  * (shapebar) K1 / K4 shown: the bar one pad for the shape n, pad 17 + n % 8, full in the track's colour (n 0-7) or white (n 8-15; shapebar "page": the page's colour);
  * (stockplus, v2 with k6swap / k8sync / k3sync) the Stock+ page: tools/stockplus.py's page bit (bit t of byte 0 of its slot) set for
    the selected track while the menu is open on it, clear otherwise (written each LED frame, on a page pad and when a button closes
    the menu), so its knobs are Stock+'s only there; the bar shows the shown knob's Stock+ value, Shift held: K5-K8's second layer (K6:
    the pitch follow, Shift: the filter type); SP_MIDS from the middle (K1, K3, K8), the rest 2048 a pad; no red there (Stock+
    does not record), the held step's pad white; Shift held: K5-K8's lights SHIFT_RGB (the shown one full, the others at KNOB_LVL), the
    bar SHIFT_RGB when it shows K5-K8;
  * (fpage) pad 29's page (X_RGB), one Stock+ value a knob: K1 the bitcrush (10), K2 the filter type (5: stock / 24 dB / comb in
    thirds), K3 the pitch follow (9), K4 the ring's amount (4), K5 its frequency (8); K6-K8 do nothing there, their LEDs dark; nothing records there;
    (nocrush) no bitcrush: K1-K4 the filter type, the pitch follow, the ring's amount and frequency, K5-K8 dark;
    (gran) pad 29 (PAGE_G, G_RGB) the granular page (grain_rp's values, one set): a tap from another page shows it and puts the granular
    on the selected track, a tap on it takes the granular off that track (or moves it there from another); the pad full only while
    shown with the granular on the selected track; K1-K8 values 0-7, Shift + K5-K8 values 8-11 (128 a click), Shift + K1-K4 fine;
    Clear as pad 28's; all eight knobs lit (Shift: K5-K8 white); nothing records there.  The Stock+ page keeps the movers, one value a knob, no Shift layers:
    K1-K4 Stock+'s own, K5 / K6 empty (their turns reach neither Stock+ nor the stock, pad 25 skips them, their LEDs dark), K7 the
    scan's depth (11), K8 its speed (7, from the middle).  The knobs written here (pad 29's K1-K5, Stock+'s K7 / K8) go through
    stockplus's c_spput and are pushed: 128 a click, Shift 4 (fine); Clear held, as the stock's: CLR_N clicks right = its default
    (Stock+'s, with stockplus_rp's LFO speeds) and the knob blue, CLR_N left = red and nothing else, till Clear is let go (Stock+'s K1-K4 too); the shown knob's LED the track's colour, the others the page's (Stock+'s K7 / K8 at KNOB_LVL of the stock's brightness of their value, never dark);
  * row 3 = the knob bar of the selected track: the last knob turned or picked with pad 25 (K1 before any), parameter k of the store [ctrl + 0x1F4 + 4 t] (what its
    LED shows), in the track's colour (its palette slot TRK_SLOTS[t]; the stock recolours the knob LEDs' slots, K1's red for automation)
    scaled after the stock's output stage,
    16 values a pad; K2 / K3 with their Shift fine parameters 14 / 15 (v * 128 + fine, 2048 a pad); K1 and K4 (the stock's centre knobs)
    from the middle: exactly at 64 pads 20 / 21 dim white, else the empty middle pad dim (the marker) and a fill on them at least MINF;
    a held step with its own value of that knob (its automation: lane k of the pattern shown, the first of its 6 microsteps not 0xFF): that value;
    Record armed and a knob turned in the last TURN_MS, or a step held: red;
    at rest (0, or 64 on K1 / K4) the rest pads dim white (red with the bar), above 0 pad 17 at least MINF;
  * knob turns are always the stock's (step automation records only with Record armed, as the stock); pad 25 shows the next knob (K8 -> K1);
  * Record armed, playing, a step held in the menu: the stock's recorder writes into the held step instead of the playhead's step;
    stopped, or no step held, or the menu closed: the stock's recording;
  * a held step's pad in the menu: white, red with Record armed; playing with Record armed, the playhead's pad white (on the held
    step's page);
  * the track buttons' numbers in the page's colour, the selected one flashing in its colour at full brightness (not the stock's
    dim; dark while bit BLINK_BIT of the tick is set), so Track + never looks like the stock's view; while a
    step is held, the LED of every knob with automation on that step (any microstep not 0xFF) red; the bar's knob LED as the stock
    draws it (the track's colour), the others in the page's colour at the same brightness, any of them red when the stock's slot is ff0000 (automation on the held step, or recorded with Record armed); while
    Clear is held, the knob LEDs are the stock's (with fpage: not on Stock+'s and pad 29's pages, which keep their own);
  * hooks: a new head of the button chain (the press: its track, whether it was the selected one, the time; other buttons close), the
    controller's pad press / release 0x0803D7FE / 0x0803D896 and knob 0x0803DDE0 entries (their first two instructions), a new head of the
    LED task's chain (the hold, the release, the frame), the LED task's call of the output stage 0x0803E802 (the RGB of the bar and the
    selected track) and the automation message's call of the recorder 0x0803655A: the release is seen as the button's bit gone from
    [ctrl + 0xA0], so a tap shorter than a frame still counts.
RAM, slot "tmenu": + 0 open, + 1 sticky, + 2 the pressed track + 1 (0 none), + 3 it was the selected track, + 4 the press (HAL tick),
+ 8 the last knob turned + 1 (0 none), + 9 the held step's value, + 10 the page (0 = pad 27, the parameter editor), + 11 the other
knob + 1 (Stock+'s or the other pages'; swapped with + 8 when the page changes to or from Stock+), + 12 the pads
taken (bit p), + 16 the last knob turn (HAL tick),
+ 20 the selected track, + 21 1: the bar shows a held step's own value, + 22 the dim white pads of the bar (bit p), + 23 the
value shown, + 24..31 the bar's pads (0..255 of its colour).
Install before errled.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import (Asm, add_sp_imm, adds_imm3, adds_imm8, adds_reg, ands_reg, b, b_cond, b_w, bl, bics_reg, cmp_imm, cmp_reg, eors_reg, h,  # noqa: E402
                   ldr_imm, ldr_sp, ldrb_imm, ldrb_reg, ldrb_w, ldrh_imm, lsls_imm, lsls_reg, lsrs_imm, lsrs_reg, mov_reg, movs_imm, movt, movw, muls, orrs_reg,
                   pop_list, push_list, raw, str_imm, str_sp, strb_imm, strb_w, strh_w_imm, sub_sp_imm, subs_imm8, subs_reg, tst_reg)
import countin as C  # noqa: E402
import rhstate  # noqa: E402

CTRL, HELD, KSTORES = C.CTRL, 0xA0, 0x1F4
MODS = (1 << 23) | (1 << 24)                              # Clear, Duplicate
ANY_BTN = 0xFFFFFF00                                     # the held bits of every button but the tracks'
ID_SHIFT = 27                                           # the stock's case 27 -> 0x0804B352 sets the Shift flag (p0 of [ctrl + 0xC])
ID_PATTERNS = 13                                        # (viewlock) Shift + 13 = the stock's View Lock toggle 0x080506D8: a flag, no view change
KEEP = (16, C.ID_PLAY, 23, 24, ID_SHIFT)                # Record, Play, Clear, Duplicate, Shift: the menu stays open
CLOSE_END = 28                                          # ids 28-31 do nothing in the stock's press switch
CONT, CONT_VT, O_MODE, MODE_SC = 0x20048B9C, 0x080678DC, 0x264, 8
STEPOBJ, O_SELFLAG = 0x74, 0x34                          # [CONT + 0x74 + 4 t] the step object; p0 of its store + 0x34: presses select
SELTRK = 0x0805800E                                      # (container) -> the selected track
PP_ENTRY, PP_HEAD, PP_CONT = 0x0803D7FE, "push {r4, r5, r6, lr}|mov r6, r0", 0x0803D802
PR_ENTRY, PR_HEAD, PR_CONT = 0x0803D896, "push {r3, r4, r5, lr}|mov r4, r0", 0x0803D89A
KN_ENTRY, KN_HEAD, KN_CONT = 0x0803DDE0, "push {r4, r5, r6, lr}|mov r4, r0", 0x0803DDE4
OUT_CALL = 0x0803E802                                    # the LED task's bl of the output stage (ctrl, out RGB words, frame)
REC_CALL, RECORDER = 0x0803655A, 0x08047D82              # the automation message's bl of the recorder (r0 rec, r1 lane, r2 value; r5 the track)
COLOURS, CODE_KNOB0 = 0x20003974, 0xE9                    # the colour table (0xRRGGBB words); track t's knobs: codes 0xE9 + 8 t + k
TRK_SLOTS = (0x43, 0x2F, 0x47, 0x4B, 0x37, 0x25, 0x12, 0x3B)  # the tracks' palette slots: their knob slots' colour when the stock leaves them
O_DIM, P_DIM, BIT_DIM = 0x88, 2, 10                      # the stock's dimmed LEDs: bit 10 of p2 of [ctrl + 0x88]
DIM_MUL = 141                                            # dimmed, the output stage gives each channel c * 141 >> 8
HOLD_MS = 250
STOCK_HOLD = 0x14D                                       # the stock's hold: 333 ms (0x0803DEBC's timer sets [ctrl + 0x1BA])
LED_TRK0, LED_KNOB0, ROW3, BAR, PAD_KNOB = 32, 60, 16, 16, 24  # pads 17-32 the menu's; the bar pads 17-24; pad 25 picks the knob
PAD_PAGE0, PAGE_SP = 26, 1                               # pads 27 / 28: the parameter editor, Stock+
PAGE_RGB = (0xFFFFFF, 0x59D6FF)                          # the pages' colours (65 % saturation, hues between the tracks'): the parameter editor white, Stock+ sky
TEST_RGB = (0xFFC859, 0x9EFF59, 0x7559FF, 0xFF59C2)       # (testpages) pads 29-32: amber, lime, violet, rose at 65 % saturation
TEST_RGB2 = (0x9EFF59, 0x59FFA8, 0xE5B2FF)                # (pagecols) pads 29-31: lime, mint (65 %), pale lilac (30 %): hues and whiteness apart from the tracks'
PAGE_X, X_RGB = 2, 0xFFC859                               # (fpage) pad 29: Stock+'s K6 / K7 values, one knob each, amber
X_FL = (4, 8)                                             # (filtpage) pad 28's K1 / K2: the ring's amount / frequency (the filter on pad 29)
X_SCAN = X_FL + (None,) * 4 + (11, 7)                    # (scanfx) pad 28's K7 / K8: the scan's depth / speed; None = dark
SP_SCANK = 6                                              # (scanfx) pad 27's knobs: K1-K6
SP_RANDK, RAND_V = 7, 26                                  # (pxrand) the pitch page's knobs K1-K7; K7 = fshape's random pitch depth
SP_GLIDEK, GLIDE_V = 8, 27                                # (glide) K8 = fshape's glide time
FADE_V = 28                                               # (fade) Shift + K7 = fshape's LFO fade-in
FADE = [False]                                            # set by install(fade=True)
FADETAN = [False]                                         # (fadetan) Shift held: the pitch page's K7 tan, as the filter page's Shift knobs
FCLR = [False]                                            # set by install(fclr=True)
X_IDX = (10, 5, 9, 4, 8)                                  # (fpage) pad 29's K1-K5: bitcrush, filter type, pitch follow, ring amount / frequency (nocrush: no bitcrush, the rest from K1)
X_KNOBS = len(X_IDX)
SP_OWN = {6: 11, 7: 7}                                    # (fpage) Stock+'s K7 / K8 written here: the scan's depth / speed
SP_EMPTY = (4, 5)                                         # (fpage) Stock+'s K5 / K6: nothing (yet)
SP_MAP = (10, 0, 1, 6, 2, 3, 11, 7)                       # (shapes) Stock+'s K1-K8: env shape, amount, decay, LFO shape, rate, depth, scan depth, speed
SP_MIDK = tuple(k for k, i in enumerate(SP_MAP) if i in (0, 2, 7))   # (shapes) the knobs lit from the middle
DEPTHFIRST = [False]                                       # (depthfirst) set by install for this build
SHAPE_N = {10: 16, 6: 10}                                  # (shapebar) Stock+ value -> its shape count (pshape.NE / NL)
PAGE_F = 3                                                 # (filt) pad 29: the filter page (fshape)
F_MAP = (12, 13, 14, 15, 16, 17)                           # (filt) its K1-K6: fshape's values; K7 / K8 the stock's
F_SHIFT = {0: 5, 3: 9}                                     # (filt) Shift + K1 / K4: Stock+'s filter type, pitch follow
F_SHN = {12: 16, 15: 10, 5: 3}                             # (filt) the bar's one-pad values: the shapes, the filter type
F_MIDS = (13, 16)                                          # (filt) from the middle: the amount, the rate
PAGE_V = 4                                                 # (vol) pad 30: the movement page (fshape's vol)
V_MAP = (18, 19, 20)                                       # (vol) its K1-K3: vol shape, rate, depth
V_KNOBS, V_SHN, V_MIDS = len(V_MAP), {18: 16}, (19,)
PADMAP_ORDER = (0, PAGE_F, PAGE_V, PAGE_SP, None, PAGE_X)  # (pageorder) the page on pads 26-31 (page0 + j); None = no page
F_SHIFT2 = {6: 5, 7: 9}                                    # (syncbar) Shift + K7 / K8: the filter type, the pitch follow
SB_RATES, SB_SYNC0, SB_HALF = (2, 7, 16, 19), 8192 + 128, 8 * 512   # (syncbar) the rates; the first synced value; a sweep of steps
SB_SHAPES = {10: 16, 6: 10, 12: 16, 15: 10, 18: 16}        # (syncbar) the shape knobs' values -> their shape count
SB_N10 = 819                                               # (syncbar) a 10-shape knob's shape k at (2 k + 1) x 819
DF_SP_MAP = (0, 10, 1, 3, 6, 2, 11, 7)                     # (depthfirst) Stock+'s K1-K8: amount, env shape, decay, depth, LFO shape, rate, scan depth, speed
DF_F_MAP = (13, 12, 14, 17, 15, 16)                        # (depthfirst) the filter page's K1-K6, the same order
DF_V_MAP = (20, 18, 19)                                    # (depthfirst) pad 30's K1-K3: vol depth, shape, rate
MID_VALUES = (0, 2, 7, 13, 16, 19)                         # (depthfirst) the values lit from the middle: the amounts, the rates
DF_V_MAP_M = (20, 18, 19, 23, 21, 22, 24, 25)              # (mixpage) the mix page's K1-K8
PAGE_G, G_RGB = 3, 0xC259FF                               # (gran) pad 29: the granular page (grain_rp), lilac
SHIFT_RGB = 0xFFFFFF                                     # Stock+'s second layers (K5-K8) while Shift is held
KNOB_LVL = 64                                            # of 255: the knob LEDs not on the bar, in the page's colour
STOCK_B = (0x1CC, 0x1A00)                                # the stock's knob brightness (0x08052122): (b x [0] + [1]) >> 16 of full, b = 0..127


def scl_py(rgb, lvl):
    return sum((((rgb >> sh) & 0xFF) * (lvl + 1) >> 8) << sh for sh in (0, 8, 16))
PAGE_KNOBS, SP_KNOBS = 8, 8                              # the knobs pad 25 picks among: the parameter editor's, Stock+'s
SP_K6, SP_TYPE, SP_FOLLOW = 5, 5, 9                      # Stock+ v2 (k6swap): K6 = the pitch follow (value 9), Shift + K6 = the filter type (5)
SP_MIDS = (0, 2, 7)                                      # Stock+'s values shown from the middle: K1, K3 (k3sync), K8 (k8sync)

BLINK_BIT = 8                                            # the selected track's flash: 256 ms on, 256 ms off
CYC_LVL = 26                                             # pad 25: the track's colour x 27 / 256, each channel of each track's colour >= 2
COL_FULL, COL_REC = 0x01, 0x55                          # white; red (ff0000)
FINE = {1: 14, 2: 15}                                    # K2 / K3: their Shift fine parameters
MARK, MINF, WHITE = 41, 77, 0x46                         # of 255: the middle marker, the least fill on a middle pad, the centre's white
O_OPEN, O_STICKY, O_PTRK, O_PSEL, O_PTICK, O_KNOB, O_TAKEN = 0, 1, 2, 3, 4, 8, 12
PSEL_FLIP = 2                                            # (momhold) O_PSEL while the held selected track shows the other view
O_SEL, O_RED, O_WHT, O_V, O_BAR = 20, 21, 22, 23, 24
O_AV, O_PAGE, O_KNOB2, O_KTICK = 9, 10, 11, 16
PG_OFF, PG_LEN, PG_MARK = 530, 10, 0x50                  # (perpage) the project's block in rhrec's tail (the end of trkcopy's room): "P", a check byte, track t's page at + 2 + t
O_CLRR, O_CLRL = 36, 44                                  # (fpage) Clear held: K1-K8's turn right / left so far, 0..CLR_N; 0 when Clear is let go
CLR_N, CLR_RIGHT, CLR_LEFT = 40, 0x0E, 0x55              # the stock's (0x08058160 / 0x080586E6): CLR_N clicks; the knob's light code when done
SHIFT_DIM, SHIFT_BRT = 0x2C, 0x2B                         # (shiftled) the stock's tan for buttons with a Shift job: dim, lit
O_BACK, O_BTICK = 35, 52                                 # (bounce) the button held over an open menu + 1 (0 none); its press (HAL tick)
O_PMODE, O_SHOP = 33, 34                                 # (twoview) the container's mode at the track's press; Shift + a track pressed
O_ARM, ARM_OFF = 32, 0xFF                               # (click) the track pressed last + 1; 0 none yet (the selected one counts), ARM_OFF after another button
TURN_MS = 500                                           # Record armed: the bar red this long after a knob turn
HELDSTEP, PADS_DOWN = 0x64, 0xC0                         # p1 of the step object's store + 0x64: the held step 0-31, 0xFF none; [+ 0xC0]: steps whose pad is down (bit)
AUTO, AUTO_VT, AUTO_RECS = 0x2003D2FC, 0x08068B14, 0x84  # the automation owner; [AUTO + 0x84 + 4 t] track t's recorder object
REC_PATS, REC_POS = 4, 0x28                              # [rec + 4] its 8 patterns; p0 of the store [rec + 0x28] the pattern shown
REC_PLAY = 0xC                                           # p1 of the store [rec + 0xC]: the playhead's step ([rec + 0x28] stays on a held step)
PAT_SIZE, LANES, LANE_SIZE, MSTEPS = 0xA28, 0x128, 0xC0, 6   # lane k = knob k; a step's value at microstep 0, 0xFF none
RED = 0xFF0000


def arm_code(base, L, heads, sp=None, pages=PAGE_RGB[:1], fpage=False, defs=None, click=False, twoview=False, shiftled=False,
             bounce=False, pageclear=False, steadyreset=False, resetcue=False, stepmarker=False, trackpulse=False, steppage=False, softclear=False,
             viewlock=False, momhold=False, x_idx=X_IDX, gran=None, perpage=False, shapes=None, shapebar=False, filt=None, k78white=False, vol=None, sb=None, scanfx=False, padmap=None, spn=None):
    X_IDX, X_KNOBS = x_idx, len(x_idx)
    PADMAP = tuple(padmap) if padmap else tuple(range(len(pages)))
    PADOF = {pg: j for j, pg in enumerate(PADMAP) if pg is not None}   # a page's pad: page0 + PADOF[page]
    XDARK = [k for k, i in enumerate(X_IDX) if i is None]
    XLIVE = [k for k, i in enumerate(X_IDX) if i is not None]
    assert not XDARK or XDARK == list(range(XDARK[0], XDARK[-1] + 1)), "pad 28's dark knobs: one run"
    SPN = spn or (SP_SCANK if scanfx else 8)              # the pitch page's live knobs
    FSH = F_SHIFT2 if sb else F_SHIFT
    vdefs = {min(V_MAP) + j: v for j, v in enumerate(vol["defs"][:V_KNOBS]) if v} if vol else {}   # defs by value, not knob
    gdefs = {i: v for i, v in enumerate(gran["defs"]) if v} if gran else {}
    fdefs = {**{i: v for i, v in (defs or {}).items() if i in FSH.values()},
             **{min(F_MAP) + j: v for j, v in enumerate(filt["defs"]) if v}} if filt else {}
    VAL = sb["c_uval"] if sb else filt["c_fsval"] if filt else shapes["c_shval"] if shapes else sp["c_spval"] if sp else None
    def kd(d):                                            # (syncbar) a page's defaults as the knob shows them: the rates mirrored
        if not sb:
            return d
        import syncbar as SB
        return {**d, **{i: SB.mirror(d.get(i, 0)) for i in SB_RATES}}
    kdefs, kfdefs, kvdefs = kd(defs or {}), kd(fdefs), kd(vdefs)
    O = rhstate.OFF["tmenu"][0]
    assert not click or rhstate.OFF["tmenu"][1] > O_ARM, "click needs RH_TMCLICK"
    assert not twoview or rhstate.OFF["tmenu"][1] > O_SHOP, "twoview needs RH_TMCLICK"
    assert not bounce or rhstate.OFF["tmenu"][1] >= O_BTICK + 4, "bounce needs RH_TMCLICK=3"
    assert bounce or not momhold, "momhold builds on bounce"
    assert not fpage or rhstate.OFF["tmenu"][1] >= O_CLRL + 8, "fpage needs RH_TMCLICK=2"
    assert not fpage or (sp and len(pages) > PAGE_X)
    page0 = 25 if pageclear else PAD_PAGE0
    npages = len(pages)
    a = Asm(base)
    E = a.emit
    _label, used = a.label, set()

    def label(name):                                      # Asm keeps the last of two same labels: fail instead
        assert name not in used, f"label {name} twice"
        used.add(name)
        _label(name)
    a.label = label

    def imm32(rd, v):
        E(movw, rd, v & 0xFFFF)
        E(movt, rd, v >> 16)

    def ldb(rt, rn, off): E(ldrb_w, rt, rn, O + off)
    def stb(rt, rn, off): E(strb_w, rt, rn, O + off)
    def ldw(rt, rn, off): E(raw, h(0xF8D0 | rn) + h(rt << 12 | (O + off)))
    def stw(rt, rn, off): E(raw, h(0xF8C0 | rn) + h(rt << 12 | (O + off)))

    inv = dict(eq="ne", ne="eq", lo="hs", hs="lo", hi="ls", ls="hi", lt="ge", ge="lt", le="gt", gt="le", pl="mi", mi="pl")

    nfar = [0]

    def far(target, cond):                                # b<cond> beyond +-256
        nfar[0] += 1
        skip = f"far{nfar[0]}"
        E(b_cond, skip, inv[cond])
        E(b, target)
        a.label(skip)

    # ---- c_tmview() -> r0 = the selected track in the track views (not Sidechain), else 8; clobbers r1-r3
    a.label("c_tmview")
    E(push_list, [4], lr=True)
    imm32(0, CTRL)
    E(ldr_imm, 1, 0, 0x7C)
    imm32(0, CONT)
    E(cmp_reg, 0, 1)
    E(b_cond, "vw_n", "ne")
    E(ldr_imm, 1, 0, 0)
    imm32(2, CONT_VT)
    E(cmp_reg, 1, 2)
    E(b_cond, "vw_n", "ne")
    E(ldrb_w, 1, 0, O_MODE)
    E(cmp_imm, 1, MODE_SC)
    E(b_cond, "vw_n", "eq")
    E(bl, SELTRK)
    E(cmp_imm, 0, 8)
    E(b_cond, "vw_x", "lo")
    a.label("vw_n")
    E(movs_imm, 0, 8)
    a.label("vw_x")
    E(pop_list, [4], pc=True)

    # ---- c_tmfill(r0 = the value above a pad's start, signed; r1 = log2 of a pad's values) -> r0 = its level 0..255; clobbers r2
    a.label("c_tmfill")
    E(cmp_imm, 0, 0)
    E(b_cond, "fl_0", "le")
    E(movs_imm, 2, 1)
    E(lsls_reg, 2, 1)
    E(cmp_reg, 0, 2)
    E(b_cond, "fl_f", "ge")
    E(lsls_imm, 0, 0, 8)
    E(lsrs_reg, 0, 1)
    E(raw, h(0x4770))
    a.label("fl_f")
    E(movs_imm, 0, 255)
    E(raw, h(0x4770))
    a.label("fl_0")
    E(movs_imm, 0, 0)
    E(raw, h(0x4770))

    # ---- c_tmscl(r0 = 0xRRGGBB, r1 = level 0..255) -> r0 = each channel * (level + 1) / 256; clobbers r1-r3
    a.label("c_tmscl")
    E(push_list, [5], lr=True)
    E(adds_imm8, 1, 1)
    E(movs_imm, 5, 0xFF)
    E(mov_reg, 2, 0)
    E(ands_reg, 2, 5)
    E(muls, 2, 1)
    E(lsrs_imm, 2, 2, 8)
    for sh in (8, 16):
        E(lsrs_imm, 3, 0, sh)
        E(ands_reg, 3, 5)
        E(muls, 3, 1)
        E(lsrs_imm, 3, 3, 8)
        E(lsls_imm, 3, 3, sh)
        E(orrs_reg, 2, 3)
    E(mov_reg, 0, 2)
    E(pop_list, [5], pc=True)

    # ---- c_tmtint(r0 = 0xRRGGBB, r1 = colour) -> r0 = the colour at r0's brightest channel; clobbers r1-r3
    a.label("c_tmtint")
    E(push_list, [4], lr=True)
    E(mov_reg, 4, 1)
    E(movs_imm, 3, 0xFF)
    E(mov_reg, 1, 0)
    E(ands_reg, 1, 3)
    for sh in (8, 16):
        E(lsrs_imm, 2, 0, sh)
        E(ands_reg, 2, 3)
        E(cmp_reg, 2, 1)
        E(b_cond, f"tn_{sh}", "ls")
        E(mov_reg, 1, 2)
        a.label(f"tn_{sh}")
    E(mov_reg, 0, 4)
    E(bl, "c_tmscl")
    E(pop_list, [4], pc=True)

    if sp:
        # ---- c_tmsp(r0 = our block) -> r0 = our block: stockplus's page bits from the menu (the selected track's while open on Stock+);
        #      clobbers r1-r3
        a.label("c_tmsp")
        E(push_list, [4], lr=True)
        E(mov_reg, 4, 0)
        E(movs_imm, 0, 0)
        ldb(1, 4, O_OPEN)
        E(cmp_imm, 1, 0)
        E(b_cond, "sq_w", "eq")
        ldb(1, 4, O_PAGE)
        E(cmp_imm, 1, PAGE_SP)
        E(b_cond, "sq_z", "ne")
        E(bl, "c_tmview")
        E(cmp_imm, 0, 8)
        E(b_cond, "sq_z", "hs")
        E(movs_imm, 1, 1)
        E(lsls_reg, 1, 0)
        E(mov_reg, 0, 1)
        E(b, "sq_w")
        a.label("sq_z")
        E(movs_imm, 0, 0)
        a.label("sq_w")
        E(strb_w, 0, 4, rhstate.OFF["stockplus"][0])
        E(mov_reg, 0, 4)
        E(pop_list, [4], pc=True)

    if perpage:
        # ---- c_tmpgp -> r0 = the project's page block, 0 without the record; c_tmpgck(r0 = block) -> r0 = its check byte (r1-r3)
        a.label("c_tmpgp")
        E(push_list, [], lr=True)
        E(bl, L["c_rrt"])
        E(cmp_imm, 0, 0)
        E(b_cond, "pg_px", "eq")
        E(movw, 1, PG_OFF)
        E(adds_reg, 0, 0, 1)
        a.label("pg_px")
        E(pop_list, [], pc=True)
        a.label("c_tmpgck")
        E(movs_imm, 1, 0)
        E(movs_imm, 2, 2)
        a.label("pg_ck")
        E(ldrb_reg, 3, 0, 2)
        E(adds_reg, 1, 1, 3)
        E(adds_imm8, 2, 1)
        E(cmp_imm, 2, PG_LEN)
        E(b_cond, "pg_ck", "lo")
        E(movs_imm, 0, 0xA5)
        E(eors_reg, 0, 1)
        E(lsls_imm, 0, 0, 24)
        E(lsrs_imm, 0, 0, 24)
        E(raw, h(0x4770))                                 # bx lr
        # ---- c_tmpgget(r0 = track) -> r0 = its page (0 with no valid block, 0xFF without the record); r1-r3
        a.label("c_tmpgget")
        E(push_list, [4, 5], lr=True)
        E(mov_reg, 4, 0)
        E(bl, "c_tmpgp")
        E(cmp_imm, 0, 0)
        E(b_cond, "pg_gn", "eq")
        E(mov_reg, 5, 0)
        E(ldrb_imm, 1, 5, 0)
        E(cmp_imm, 1, PG_MARK)
        E(b_cond, "pg_g0", "ne")
        E(bl, "c_tmpgck")
        E(ldrb_imm, 1, 5, 1)
        E(cmp_reg, 0, 1)
        E(b_cond, "pg_g0", "ne")
        E(adds_reg, 5, 5, 4)
        E(ldrb_imm, 0, 5, 2)
        E(cmp_imm, 0, npages)
        E(b_cond, "pg_gx", "lo")
        a.label("pg_g0")
        E(movs_imm, 0, 0)
        E(b, "pg_gx")
        a.label("pg_gn")
        E(movs_imm, 0, 0xFF)
        a.label("pg_gx")
        E(pop_list, [4, 5], pc=True)
        # ---- c_tmpgset(r0 = track, r1 = page): into the project's block (a new block when its mark or check is wrong); r0-r3
        a.label("c_tmpgset")
        E(push_list, [4, 5, 6], lr=True)
        E(mov_reg, 4, 0)
        E(mov_reg, 6, 1)
        E(bl, "c_tmpgp")
        E(cmp_imm, 0, 0)
        E(b_cond, "pg_sx", "eq")
        E(mov_reg, 5, 0)
        E(ldrb_imm, 1, 5, 0)
        E(cmp_imm, 1, PG_MARK)
        E(b_cond, "pg_si", "ne")
        E(bl, "c_tmpgck")
        E(ldrb_imm, 1, 5, 1)
        E(cmp_reg, 0, 1)
        E(b_cond, "pg_ss", "eq")
        a.label("pg_si")
        E(movs_imm, 1, PG_MARK)
        E(strb_imm, 1, 5, 0)
        E(movs_imm, 1, 0)
        for i in range(2, PG_LEN):
            E(strb_imm, 1, 5, i)
        a.label("pg_ss")
        E(adds_reg, 0, 5, 4)
        E(strb_imm, 6, 0, 2)
        E(mov_reg, 0, 5)
        E(bl, "c_tmpgck")
        E(strb_imm, 0, 5, 1)
        a.label("pg_sx")
        E(pop_list, [4, 5, 6], pc=True)

    # ---- c_tmbtn (the head of the button chain: r0 = ctrl, r1 = id): a track's press -> its track, selected, time; other buttons close
    a.label("c_tmbtn")
    E(push_list, [0, 1, 2, 4, 5, 6, 7], lr=True)          # 8 words
    E(mov_reg, 5, 1)
    E(bl, L["c_rst"])
    E(cmp_imm, 0, 0)
    E(b_cond, "bt_x", "eq")
    E(mov_reg, 4, 0)
    E(cmp_imm, 5, 8)
    E(b_cond, "bt_t", "lo")
    E(cmp_imm, 5, CLOSE_END)
    E(b_cond, "bt_x", "hs")
    for k in KEEP + ((21,) if steppage else ()):
        E(cmp_imm, 5, k)
        E(b_cond, "bt_x", "eq")
    if viewlock:
        E(cmp_imm, 5, ID_PATTERNS)
        E(b_cond, "bt_nv", "ne")
        imm32(0, CTRL)
        E(ldr_imm, 0, 0, 0xC)
        E(movs_imm, 1, 0)
        E(bl, C.PARAM_GET)
        E(ldrb_imm, 0, 0, 0)
        E(cmp_imm, 0, 0)
        E(b_cond, "bt_x", "ne")                           # Shift + Patterns: View Lock, the menu stays open
        a.label("bt_nv")
    if bounce:
        ldb(0, 4, O_OPEN)
        E(cmp_imm, 0, 0)
        E(b_cond, "bt_bk", "eq")
        E(adds_imm3, 0, 5, 1)                             # held over the open menu: back to it after a hold
        imm32(1, C.HAL_TICK)
        E(ldr_imm, 1, 1, 0)
        stw(1, 4, O_BTICK)
        a.label("bt_bk")
        stb(0, 4, O_BACK)
    E(movs_imm, 0, 0)
    stb(0, 4, O_OPEN)
    stb(0, 4, O_PTRK)
    if click:
        E(movs_imm, 0, ARM_OFF)
        stb(0, 4, O_ARM)
    if sp:
        E(mov_reg, 0, 4)
        E(bl, "c_tmsp")
    E(b, "bt_x")
    a.label("bt_t")
    imm32(0, CTRL)
    E(ldr_imm, 0, 0, 0xC)
    E(movs_imm, 1, 0)
    E(bl, C.PARAM_GET)
    E(ldrb_imm, 0, 0, 0)
    E(cmp_imm, 0, 0)
    E(b_cond, "bt_sh" if twoview else "bt_x", "ne")       # Shift held
    imm32(0, CTRL + HELD)
    E(ldr_imm, 0, 0, 0)
    imm32(1, MODS)
    E(tst_reg, 0, 1)
    E(b_cond, "bt_x", "ne")                               # Clear or Duplicate held
    E(bl, "c_tmview")
    if click and not twoview:                             # the second click in a row on a track: its press counts
        E(adds_imm3, 1, 5, 1)
        ldb(2, 4, O_ARM)
        stb(1, 4, O_ARM)
        E(cmp_imm, 0, 8)
        E(b_cond, "bt_x", "hs")
        E(movs_imm, 3, 0)
        E(cmp_imm, 2, 0)
        E(b_cond, "bt_a", "ne")
        E(cmp_reg, 0, 5)
        E(b, "bt_c")
        a.label("bt_a")
        E(cmp_reg, 1, 2)
        a.label("bt_c")
    else:
        E(cmp_imm, 0, 8)
        E(b_cond, "bt_x", "hs")
        E(movs_imm, 3, 0)
        E(cmp_reg, 0, 5)
    E(b_cond, "bt_s", "ne")
    E(movs_imm, 3, 1)
    a.label("bt_s")
    stb(3, 4, O_PSEL)
    if twoview:
        imm32(0, CONT)
        E(ldrb_w, 0, 0, O_MODE)
        stb(0, 4, O_PMODE)
    E(adds_imm3, 0, 5, 1)
    stb(0, 4, O_PTRK)
    imm32(0, C.HAL_TICK)
    E(ldr_imm, 0, 0, 0)
    stw(0, 4, O_PTICK)
    a.label("bt_x")
    E(raw, C.popw([0, 1, 2, 4, 5, 6, 7], lr=True))
    E(b_w, L["prev_btn"])
    if twoview:
        a.label("bt_sh")                                  # Shift + a track (the stock ignores it): its plain press, then the menu
        imm32(0, CTRL + HELD)
        E(ldr_imm, 0, 0, 0)
        imm32(1, MODS)
        E(tst_reg, 0, 1)
        E(b_cond, "bt_x", "ne")
        imm32(0, CTRL)
        E(ldr_imm, 0, 0, 0xC)
        E(movs_imm, 1, 0)
        E(bl, C.PARAM_GET)
        E(mov_reg, 6, 0)                                  # r6 = the Shift flag
        E(movs_imm, 1, 0)
        E(strb_imm, 1, 6, 0)
        E(movs_imm, 1, 1)
        stb(1, 4, O_SHOP)
        E(ldr_sp, 0, 0)
        E(ldr_sp, 1, 4)
        E(ldr_sp, 2, 8)
        E(bl, L["prev_btn"])
        E(movs_imm, 1, 1)
        E(strb_imm, 1, 6, 0)
        E(str_sp, 0, 0)
        E(pop_list, [0, 1, 2, 4, 5, 6, 7], pc=True)

    # ---- c_tmpad (the controller's pad press, its first two instructions: r0 = ctrl, r1 = pad, r2 = velocity), menu open:
    #      pads 1-16 through the stock with the select flag set; pads 17-32 taken
    def to_go(cond):                                      # (gran) pp_go is past a b<cond>'s reach
        if gran or padmap:
            far("pp_go", cond)
        else:
            E(b_cond, "pp_go", cond)
    a.label("c_tmpad")
    E(push_list, [0, 1, 2, 4, 5], lr=True)                # [sp] r0, [sp + 4] r1, [sp + 8] r2
    E(cmp_imm, 1, 32)
    to_go("hs")
    E(mov_reg, 4, 1)
    E(bl, L["c_rst"])
    E(cmp_imm, 0, 0)
    to_go("eq")
    ldb(1, 0, O_OPEN)
    E(cmp_imm, 1, 0)
    to_go("eq")
    E(cmp_imm, 4, ROW3)
    E(b_cond, "pp_sel", "lo")
    if pageclear:
        E(bl, "c_tmview")
        E(cmp_imm, 0, 8)
        far("pp_tk_reload", "hs")
        E(mov_reg, 1, 0)
        E(mov_reg, 0, 4)
        E(bl, L["pcpress"])
        E(cmp_imm, 0, 0)
        E(b_cond, "pp_continue", "eq")
        a.label("pp_tk_reload")
        E(bl, L["c_rst"])
        E(b, "pp_tk")
        a.label("pp_continue")
        E(bl, L["c_rst"])
    E(cmp_imm, 4, PAD_KNOB)
    E(b_cond, "pp_kc", "eq")
    E(mov_reg, 1, 4)
    E(subs_imm8, 1, page0)
    E(cmp_imm, 1, npages)
    E(b_cond, "pp_tk", "hs")                              # the bar's pads, pad 26, the reserved pages: nothing
    if padmap:
        for j, pg in enumerate(PADMAP):
            if pg == j:
                continue
            E(cmp_imm, 1, j)
            E(b_cond, f"pp_pm{j}", "ne")
            if pg is None:
                E(b, "pp_tk")
            else:
                E(movs_imm, 1, pg)
                E(b, "pp_pmx")
            a.label(f"pp_pm{j}")
        a.label("pp_pmx")                                 # r1 = the pad's page
    if sp:
        E(movs_imm, 3, 0)                                 # r3 = how many of the page shown and the new one are Stock+
        ldb(2, 0, O_PAGE)
        E(cmp_imm, 2, PAGE_SP)
        E(b_cond, "pp_o", "ne")
        E(adds_imm8, 3, 1)
        a.label("pp_o")
        E(cmp_imm, 1, PAGE_SP)
        E(b_cond, "pp_n", "ne")
        E(adds_imm8, 3, 1)
        a.label("pp_n")
        E(cmp_imm, 3, 1)
        E(b_cond, "pp_ps", "ne")
        ldb(2, 0, O_KNOB)                                 # to or from Stock+: its own knob shown, the other kept
        ldb(3, 0, O_KNOB2)
        stb(3, 0, O_KNOB)
        stb(2, 0, O_KNOB2)
        a.label("pp_ps")
    if gran:
        E(cmp_imm, 1, PAGE_G)
        E(b_cond, "pp_gn", "ne")
        E(push_list, [0, 1])
        E(bl, "c_tmview")
        E(cmp_imm, 0, 8)
        E(b_cond, "pp_gx", "hs")
        E(adds_imm3, 5, 0, 1)                             # r5 = the selected track + 1
        E(ldr_sp, 1, 0)
        ldb(1, 1, O_PAGE)
        E(cmp_imm, 1, PAGE_G)
        E(b_cond, "pp_gs", "ne")                          # from another page: the granular on this track
        E(bl, gran["c_grtrk"])
        E(cmp_reg, 0, 5)
        E(b_cond, "pp_gs", "ne")                          # on the page, another track's: moved to this one
        E(movs_imm, 5, 0)                                 # on the page, this track's: off
        a.label("pp_gs")
        E(mov_reg, 0, 5)
        E(bl, gran["c_grset"])
        a.label("pp_gx")
        E(pop_list, [0, 1])
        a.label("pp_gn")
    stb(1, 0, O_PAGE)
    if perpage:
        E(push_list, [0, 1])
        ldb(0, 0, O_SEL)
        E(bl, "c_tmpgset")
        E(pop_list, [0, 1])
    if sp:
        E(bl, "c_tmsp")
    E(b, "pp_tk")
    a.label("pp_kc")
    ldb(1, 0, O_KNOB)                                     # pad 25: the bar shows the page's next knob (its last -> K1)
    E(cmp_imm, 1, 0)
    E(b_cond, "pp_k1", "ne")
    E(movs_imm, 1, 1)
    a.label("pp_k1")
    E(adds_imm8, 1, 1)
    E(movs_imm, 2, PAGE_KNOBS)
    if sp:
        ldb(3, 0, O_PAGE)
        E(cmp_imm, 3, PAGE_SP)
        E(b_cond, "pp_kn", "ne")
        E(movs_imm, 2, SPN if shapes else SP_KNOBS)
        if fpage and not shapes:
            E(cmp_imm, 1, SP_EMPTY[0] + 1)
            E(b_cond, "pp_kn", "ne")
            E(movs_imm, 1, SP_EMPTY[-1] + 2)               # K5 -> K7
        a.label("pp_kn")
        if fpage:
            E(cmp_imm, 3, PAGE_X)
            E(b_cond, "pp_kf", "ne")
            E(movs_imm, 2, X_KNOBS)
            if XDARK:
                E(cmp_imm, 1, XDARK[0] + 1)
                E(b_cond, "pp_kf", "ne")
                E(movs_imm, 1, XDARK[-1] + 2)             # past the dark knobs
            a.label("pp_kf")
        if vol:
            E(cmp_imm, 3, PAGE_V)
            E(b_cond, "pp_kv", "ne")
            E(movs_imm, 2, V_KNOBS)
            a.label("pp_kv")
    E(cmp_reg, 1, 2)
    E(b_cond, "pp_k8", "ls")
    E(movs_imm, 1, 1)
    a.label("pp_k8")
    stb(1, 0, O_KNOB)
    a.label("pp_tk")
    ldw(2, 0, O_TAKEN)
    E(movs_imm, 3, 1)
    E(lsls_reg, 3, 4)
    E(orrs_reg, 2, 3)
    stw(2, 0, O_TAKEN)
    E(pop_list, [0, 1, 2, 4, 5], pc=True)                 # the stock never sees it
    a.label("pp_sel")
    E(bl, "c_tmview")
    E(cmp_imm, 0, 8)
    (far("pp_go", "hs") if padmap else E(b_cond, "pp_go", "hs"))
    E(lsls_imm, 0, 0, 2)
    imm32(1, CONT + STEPOBJ)
    E(raw, h(0x5808))                                     # ldr r0, [r1, r0]: the step object
    E(ldr_imm, 0, 0, O_SELFLAG)
    E(movs_imm, 1, 0)
    E(bl, C.PARAM_GET)
    E(mov_reg, 4, 0)                                      # r4 = its select flag
    E(ldrb_imm, 5, 4, 0)                                  # r5 = the flag as it was
    E(movs_imm, 0, 1)
    E(strb_imm, 0, 4, 0)
    E(ldr_sp, 0, 0)
    E(ldr_sp, 1, 4)
    E(ldr_sp, 2, 8)
    E(bl, "pp_orig")
    E(strb_imm, 5, 4, 0)
    E(pop_list, [0, 1, 2, 4, 5], pc=True)
    a.label("pp_go")
    E(raw, C.popw([0, 1, 2, 4, 5], lr=True))
    a.label("pp_orig")
    E(raw, heads[PP_ENTRY])
    E(b_w, PP_CONT)

    # ---- c_tmrel (the controller's pad release, its first two instructions: r0 = ctrl, r1 = pad): a taken pad's release, swallowed
    a.label("c_tmrel")
    E(push_list, [0, 1, 2, 3, 4], lr=True)
    E(cmp_imm, 1, 32)
    E(b_cond, "pr_go", "hs")
    E(mov_reg, 4, 1)
    E(bl, L["c_rst"])
    E(cmp_imm, 0, 0)
    E(b_cond, "pr_go", "eq")
    ldw(2, 0, O_TAKEN)
    E(movs_imm, 3, 1)
    E(lsls_reg, 3, 4)
    E(tst_reg, 2, 3)
    E(b_cond, "pr_go", "eq")
    E(bics_reg, 2, 3)
    stw(2, 0, O_TAKEN)
    E(pop_list, [0, 1, 2, 3, 4], pc=True)
    a.label("pr_go")
    E(raw, C.popw([0, 1, 2, 3, 4], lr=True))
    E(raw, heads[PR_ENTRY])
    E(b_w, PR_CONT)

    # ---- c_tmheld(r0 = track) -> r0 = its held step 0-31 (0xFF none); clobbers r1-r3
    #      the stock's held step counts only while its pad is down: its release keeps it when the playhead moved the position
    a.label("c_tmheld")
    E(push_list, [4], lr=True)
    E(lsls_imm, 0, 0, 2)
    imm32(1, CONT + STEPOBJ)
    E(raw, h(0x5808))                                     # ldr r0, [r1, r0]: the step object
    E(mov_reg, 4, 0)
    E(ldr_imm, 0, 4, HELDSTEP)
    E(movs_imm, 1, 1)
    E(bl, C.PARAM_GET)
    E(ldrb_imm, 0, 0, 0)
    E(cmp_imm, 0, 32)
    E(b_cond, "hd_x", "hs")
    E(mov_reg, 1, 4)
    E(adds_imm8, 1, PADS_DOWN)
    E(ldr_imm, 1, 1, 0)
    E(lsrs_reg, 1, 0)
    E(lsls_imm, 1, 1, 31)
    E(b_cond, "hd_x", "ne")
    E(movs_imm, 0, 0xFF)
    a.label("hd_x")
    E(pop_list, [4], pc=True)

    # ---- c_tmlane(r1 = track, r2 = knob, r3 = step) -> r0 = its byte in the pattern shown (lane = knob, microstep 0), 0 if not found;
    #      r1 = the track's recorder object; clobbers r2, r3
    a.label("c_tmlane")
    E(push_list, [4, 5, 6, 7], lr=True)
    E(sub_sp_imm, 4)
    E(mov_reg, 4, 1)
    E(mov_reg, 5, 2)
    E(mov_reg, 6, 3)
    imm32(1, AUTO)
    E(ldr_imm, 0, 1, 0)
    imm32(2, AUTO_VT)
    E(cmp_reg, 0, 2)
    E(b_cond, "ln_0", "ne")
    E(adds_imm8, 1, AUTO_RECS)
    E(lsls_imm, 0, 4, 2)
    E(raw, h(0x5808))                                     # ldr r0, [r1, r0]: the recorder object
    E(mov_reg, 7, 0)
    E(ldr_imm, 0, 0, REC_POS)
    E(movs_imm, 1, 0)
    E(bl, C.PARAM_GET)
    E(ldrb_imm, 0, 0, 0)
    E(cmp_imm, 0, 8)
    E(b_cond, "ln_0", "hs")
    E(movw, 1, PAT_SIZE)
    E(muls, 0, 1)
    E(ldr_imm, 1, 7, REC_PATS)
    E(adds_reg, 0, 0, 1)
    E(movs_imm, 1, LANE_SIZE)
    E(muls, 1, 5)
    E(adds_reg, 0, 0, 1)
    E(movs_imm, 1, MSTEPS)
    E(muls, 1, 6)
    E(adds_reg, 0, 0, 1)
    E(movw, 1, LANES)
    E(adds_reg, 0, 0, 1)
    E(mov_reg, 1, 7)
    E(b, "ln_x")
    a.label("ln_0")
    E(movs_imm, 0, 0)
    a.label("ln_x")
    E(add_sp_imm, 4)
    E(pop_list, [4, 5, 6, 7], pc=True)

    def sweep_jump(p, val):
        """(syncbar) in own_knob's Shift branch (r6 = track, r7 = value's index): a shape knob or a synced rate -> r2 = the same pad on
        the other sweep (the turn's sign: right = the 2nd), then {p}_fw; already there: {p}_sw; else on to the fine click"""
        groups = {16: [i for i, n in SB_SHAPES.items() if n == 16], 10: [i for i, n in SB_SHAPES.items() if n == 10], "r": list(SB_RATES)}
        for g, idx in groups.items():
            for i in idx:
                E(cmp_imm, 7, i)
                far(f"{p}_j{g}", "eq")
        E(b, f"{p}_jx")
        for g in groups:
            a.label(f"{p}_j{g}")
            E(mov_reg, 0, 6)
            E(mov_reg, 1, 7)
            E(bl, val)                                    # r0 = the value as the knob shows it
            E(ldr_sp, 1, 8)                               # the turn
            if g == "r":
                E(movw, 2, SB_SYNC0)
                E(cmp_reg, 0, 2)
                far(f"{p}_jx", "lt")                      # the middle or free: fine
                E(subs_reg, 2, 0, 2)                      # r2 = the distance into the synced half
                E(movw, 3, SB_HALF)
                E(cmp_imm, 1, 0)
                E(b_cond, f"{p}_jrl", "lt")
                E(cmp_reg, 2, 3)
                far(f"{p}_sw", "hs")                      # already on the triplets
                E(adds_reg, 2, 0, 3)
                E(b, f"{p}_fw")
                a.label(f"{p}_jrl")
                E(cmp_reg, 2, 3)
                far(f"{p}_sw", "lo")                      # already on the straight steps
                E(subs_reg, 2, 0, 3)
                E(b, f"{p}_fw")
            elif g == 16:
                E(movw, 3, 8192)
                E(cmp_imm, 1, 0)
                E(b_cond, f"{p}_j6l", "lt")
                E(cmp_reg, 0, 3)
                far(f"{p}_sw", "hs")
                E(adds_reg, 2, 0, 3)
                E(b, f"{p}_fw")
                a.label(f"{p}_j6l")
                E(cmp_reg, 0, 3)
                far(f"{p}_sw", "lo")
                E(subs_reg, 2, 0, 3)
                E(b, f"{p}_fw")
            else:
                E(movs_imm, 2, 10)
                E(muls, 0, 2)
                E(lsrs_imm, 0, 0, 14)                     # r0 = the shape n
                E(cmp_imm, 1, 0)
                E(b_cond, f"{p}_j0l", "lt")
                E(adds_imm8, 0, 8)
                E(cmp_imm, 0, 10)
                far(f"{p}_sw", "hs")                      # no shape on the 2nd sweep there
                E(b, f"{p}_j0k")
                a.label(f"{p}_j0l")
                E(cmp_imm, 0, 8)
                far(f"{p}_sw", "lo")
                E(subs_imm8, 0, 8)
                a.label(f"{p}_j0k")
                E(lsls_imm, 0, 0, 1)
                E(adds_imm8, 0, 1)
                E(movw, 2, SB_N10)
                E(muls, 2, 0)                             # r2 = (2 k + 1) x 819: inside shape k
                E(b, f"{p}_fw")
        a.label(f"{p}_jx")

    def clr_count(p):
        """r0 = our slot, r5 = the knob, the delta at sp + 8: with Clear held, the turn counted as own_knob counts it; clobbers r1-r3"""
        imm32(1, CTRL + HELD)
        E(ldr_imm, 1, 1, 0)
        E(lsls_imm, 1, 1, 31 - 23)
        E(b_cond, f"{p}_x", "pl")
        E(ldr_sp, 1, 8)
        E(adds_reg, 3, 0, 5)                              # r3 = the slot + the knob
        E(cmp_imm, 1, 0)
        E(b_cond, f"{p}_l", "le")
        ldb(2, 3, O_CLRR)
        E(adds_reg, 2, 2, 1)
        E(cmp_imm, 2, CLR_N)
        E(b_cond, f"{p}_r", "ls")
        E(movs_imm, 2, CLR_N)
        a.label(f"{p}_r")
        stb(2, 3, O_CLRR)
        E(cmp_imm, 2, CLR_N)
        E(b_cond, f"{p}_x", "ne")
        E(movs_imm, 2, 0)
        stb(2, 3, O_CLRL)
        E(b, f"{p}_x")
        a.label(f"{p}_l")
        ldb(2, 3, O_CLRL)
        E(subs_reg, 2, 2, 1)
        E(cmp_imm, 2, CLR_N)
        E(b_cond, f"{p}_m", "ls")
        E(movs_imm, 2, CLR_N)
        a.label(f"{p}_m")
        stb(2, 3, O_CLRL)
        E(cmp_imm, 2, CLR_N)
        E(b_cond, f"{p}_x", "ne")
        E(movs_imm, 2, 0)
        stb(2, 3, O_CLRR)
        a.label(f"{p}_x")

    def own_knob(p, val, put, dirty, dfs, layer2=False, coarse=(), sweep=False):
        """an own-value page's knob: r0 = our slot, r5 = the knob, r7 = the value's index; val / put / dirty as Stock+'s"""
        a.label(f"{p}_wr")                                  # r7 = the value's index
        E(mov_reg, 4, 0)
        E(adds_imm3, 1, 5, 1)
        stb(1, 4, O_KNOB)
        imm32(1, C.HAL_TICK)
        E(ldr_imm, 1, 1, 0)
        stw(1, 4, O_KTICK)
        E(bl, "c_tmview")
        E(cmp_imm, 0, 8)
        far(f"{p}_sw", "hs")
        E(mov_reg, 6, 0)                                  # r6 = the track
        imm32(0, CTRL + HELD)
        E(ldr_imm, 0, 0, 0)
        E(lsls_imm, 0, 0, 31 - 23)
        far(f"{p}_nc", "pl")
        E(ldr_sp, 1, 8)                                   # Clear held, as the stock: CLR_N clicks right = the default, left nothing
        E(adds_reg, 3, 4, 5)                              # r3 = the slot + the knob
        E(cmp_imm, 1, 0)
        far(f"{p}_cl", "le")
        ldb(0, 3, O_CLRR)
        E(cmp_imm, 0, CLR_N)
        far(f"{p}_sw", "eq")
        E(adds_reg, 0, 0, 1)
        E(cmp_imm, 0, CLR_N)
        E(b_cond, f"{p}_cr", "ls")
        E(movs_imm, 0, CLR_N)
        a.label(f"{p}_cr")
        stb(0, 3, O_CLRR)
        E(cmp_imm, 0, CLR_N)
        far(f"{p}_sw", "ne")
        E(movs_imm, 0, 0)
        stb(0, 3, O_CLRL)
        E(movs_imm, 2, 0)
        for i, v in dfs.items():
            E(cmp_imm, 7, i)
            E(b_cond, f"{p}_fd{i}", "ne")
            E(movw, 2, v)
            a.label(f"{p}_fd{i}")
        E(b, f"{p}_fw")
        a.label(f"{p}_cl")
        ldb(0, 3, O_CLRL)
        E(cmp_imm, 0, CLR_N)
        far(f"{p}_sw", "eq")
        E(subs_reg, 0, 0, 1)
        E(cmp_imm, 0, CLR_N)
        E(b_cond, f"{p}_cm", "ls")
        E(movs_imm, 0, CLR_N)
        a.label(f"{p}_cm")
        stb(0, 3, O_CLRL)
        E(cmp_imm, 0, CLR_N)
        far(f"{p}_sw", "ne")
        E(movs_imm, 0, 0)
        stb(0, 3, O_CLRR)
        E(b, f"{p}_sw")                                     # no automation here to delete
        a.label(f"{p}_nc")
        E(mov_reg, 0, 6)
        E(bl, sp["c_spshift"])
        E(movs_imm, 5, 128)
        E(cmp_imm, 0, 0)
        E(b_cond, f"{p}_fs", "eq")
        E(movs_imm, 5, 4)                                 # r5 = a click: Shift fine
        if sweep:
            sweep_jump(p, val)
        if layer2:
            E(cmp_imm, 7, 8)
            E(b_cond, f"{p}_fs", "lo")
            E(movs_imm, 5, 128)                           # Shift + K5-K8: their second layer, 128 a click
        for i in coarse:
            E(cmp_imm, 7, i)
            E(b_cond, f"{p}_c{i}", "ne")
            E(movs_imm, 5, 128)                           # a Shift layer: 128 a click
            a.label(f"{p}_c{i}")
        a.label(f"{p}_fs")
        E(mov_reg, 0, 6)
        E(mov_reg, 1, 7)
        E(bl, val)
        E(ldr_sp, 1, 8)                                   # the delta
        E(muls, 1, 5)
        E(adds_reg, 2, 0, 1)
        E(b_cond, f"{p}_fh", "pl")
        E(movs_imm, 2, 0)
        a.label(f"{p}_fh")
        E(movw, 0, 16383)
        E(cmp_reg, 2, 0)
        E(b_cond, f"{p}_fw", "le")
        E(mov_reg, 2, 0)
        a.label(f"{p}_fw")
        E(mov_reg, 0, 6)
        E(mov_reg, 1, 7)
        E(bl, put)
        E(mov_reg, 0, 6)
        E(bl, dirty)
        a.label(f"{p}_sw")
        E(pop_list, [0, 1, 2, 4, 5, 6, 7], pc=True)       # neither Stock+ nor the stock sees it

    # ---- c_tmknob (the controller's knob entry, its first two instructions: r0 = ctrl, r1 = knob, r2 = delta): K1-K8 -> the last knob
    a.label("c_tmknob")
    E(push_list, [0, 1, 2, 4, 5, 6, 7], lr=True)          # 8 words
    E(cmp_imm, 1, 8)
    far("kn_go", "hs")
    E(mov_reg, 5, 1)
    E(bl, L["c_rst"])
    E(cmp_imm, 0, 0)
    far("kn_go", "eq")
    if sp:
        E(cmp_imm, 5, SP_KNOBS)
        E(b_cond, "kn_sp", "lo")
        ldb(1, 0, O_PAGE)
        E(cmp_imm, 1, PAGE_SP)
        far("kn_go", "eq")                            # Stock+'s K5-K8 (nothing yet): the bar stays
        a.label("kn_sp")
    if fpage:
        ldb(1, 0, O_OPEN)
        E(cmp_imm, 1, 0)
        far("kn_nf", "eq")                                # closed: the stock's knobs
        ldb(1, 0, O_PAGE)
        E(cmp_imm, 1, PAGE_SP)
        E(b_cond, "kn_ns", "ne")
        if shapes:                                        # all eight here, one value each (SP_MAP)
            if scanfx:
                E(cmp_imm, 5, SPN)
                far("kn_sw", "hs")
            E(movs_imm, 7, SP_MAP[0])
            for k in range(1, 8):
                E(cmp_imm, 5, k)
                E(b_cond, f"kn_m{k}", "ne")
                E(movs_imm, 7, SP_MAP[k])
                a.label(f"kn_m{k}")
            if FADE[0]:
                E(cmp_imm, 5, SP_RANDK - 1)
                far("kn_wr", "ne")
                E(push_list, [0])
                E(bl, sp["c_spshift"])
                E(mov_reg, 1, 0)
                E(pop_list, [0])
                E(cmp_imm, 1, 0)
                far("kn_wr", "eq")
                E(movs_imm, 7, FADE_V)                    # Shift + K7: the LFO's fade-in
            E(b, "kn_wr")
        else:
            for k in SP_EMPTY:
                E(cmp_imm, 5, k)
                far("kn_sw", "eq")                        # Stock+'s K5 / K6: nothing
            for k, i in SP_OWN.items():
                E(movs_imm, 7, i)
                E(cmp_imm, 5, k)
                E(b_cond, "kn_wr", "eq")
            imm32(1, CTRL + HELD)
            E(ldr_imm, 1, 1, 0)
            E(lsls_imm, 1, 1, 31 - 23)
            far("kn_nf", "pl")                            # Stock+'s K1-K4: its own, with Clear held ours (K = its value)
            E(mov_reg, 7, 5)
            E(b, "kn_wr")
        a.label("kn_ns")
        if gran:
            E(cmp_imm, 1, PAGE_G)
            far("kn_g", "eq")
        if filt:
            E(cmp_imm, 1, PAGE_F)
            far("kn_fl", "eq")
        if vol:
            E(cmp_imm, 1, PAGE_V)
            far("kn_vl", "eq")
        E(cmp_imm, 1, PAGE_X)
        far("kn_nf", "ne")
        E(cmp_imm, 5, X_KNOBS)
        far("kn_sw", "hs")
        for k in XDARK:
            E(cmp_imm, 5, k)
            far("kn_sw", "eq")
        E(movs_imm, 7, X_IDX[0])
        for k in XLIVE[1:]:
            E(cmp_imm, 5, k)
            E(b_cond, f"kn_fi{k}", "ne")
            E(movs_imm, 7, X_IDX[k])
            a.label(f"kn_fi{k}")
        own_knob("kn", sb["c_uval"] if sb else shapes["c_shval"] if shapes else sp["c_spval"],
                 sb["c_uput"] if sb else shapes["c_shput"] if shapes else sp["c_spput"], sp["c_spdirty"], kdefs, sweep=bool(sb),
                 coarse=(FADE_V,) if FADE[0] else ())
        if gran:
            a.label("kn_g")                               # the granular page: K1-K8 values 0-7, Shift + K5-K8 values 8-11
            E(mov_reg, 4, 0)
            E(mov_reg, 7, 5)
            E(cmp_imm, 5, 4)
            E(b_cond, "kg_lo", "lo")
            E(bl, sp["c_spshift"])
            E(cmp_imm, 0, 0)
            E(b_cond, "kg_lo", "eq")
            E(adds_imm8, 7, 4)
            a.label("kg_lo")
            E(mov_reg, 0, 4)
            own_knob("kg", gran["c_grval"], gran["c_grput"], gran["c_grdirty"], gdefs, layer2=True)
        if filt:
            a.label("kn_fl")                              # the filter page: K1-K6 fshape's, Shift + K1 / K4 (syncbar: K7 / K8) Stock+'s type / follow
            if sb:
                E(cmp_imm, 5, 6)
                far("kf_lo", "lo")
                E(push_list, [0])
                E(bl, sp["c_spshift"])
                E(mov_reg, 1, 0)
                E(pop_list, [0])
                E(cmp_imm, 1, 0)
                if FCLR[0]:
                    E(b_cond, "kf_s2", "ne")
                    clr_count("kc")
                    E(b, "kn_nf")                         # K7 / K8: the stock's low-pass and resonance
                    a.label("kf_s2")
                else:
                    far("kn_nf", "eq")                    # K7 / K8: the stock's low-pass and resonance
                E(movs_imm, 7, FSH[6])
                E(cmp_imm, 5, 6)
                E(b_cond, "kf_ns", "eq")
                E(movs_imm, 7, FSH[7])
                E(b, "kf_ns")
                a.label("kf_lo")
            else:
                E(cmp_imm, 5, 6)
                far("kn_nf", "hs")                        # K7 / K8: the stock's low-pass and resonance
            E(movs_imm, 7, F_MAP[0])
            for k in range(1, 6):
                E(cmp_imm, 5, k)
                E(b_cond, f"kf_m{k}", "ne")
                E(movs_imm, 7, F_MAP[k])
                a.label(f"kf_m{k}")
            if not sb:
                E(push_list, [0])
                E(bl, sp["c_spshift"])
                E(mov_reg, 1, 0)
                E(pop_list, [0])
                E(cmp_imm, 1, 0)
                E(b_cond, "kf_ns", "eq")
                for k, i in F_SHIFT.items():
                    E(cmp_imm, 5, k)
                    E(b_cond, f"kf_s{k}", "ne")
                    E(movs_imm, 7, i)
                    a.label(f"kf_s{k}")
            a.label("kf_ns")
            own_knob("kf", sb["c_uval"] if sb else filt["c_fsval"], sb["c_uput"] if sb else filt["c_fsput"], sp["c_spdirty"], kfdefs,
                     coarse=tuple(FSH.values()), sweep=bool(sb))
        if vol:
            a.label("kn_vl")                              # the movement page: K1-K3 fshape's, K4-K8 nothing
            E(cmp_imm, 5, V_KNOBS)
            far("kn_sw", "hs")
            E(movs_imm, 7, V_MAP[0])
            for k in range(1, V_KNOBS):
                E(cmp_imm, 5, k)
                E(b_cond, f"kv_m{k}", "ne")
                E(movs_imm, 7, V_MAP[k])
                a.label(f"kv_m{k}")
            own_knob("kv", sb["c_uval"] if sb else filt["c_fsval"], sb["c_uput"] if sb else filt["c_fsput"], sp["c_spdirty"], kvdefs, sweep=bool(sb))
        a.label("kn_nf")
    E(adds_imm3, 1, 5, 1)
    stb(1, 0, O_KNOB)
    imm32(1, C.HAL_TICK)
    E(ldr_imm, 1, 1, 0)
    stw(1, 0, O_KTICK)
    a.label("kn_go")
    E(raw, C.popw([0, 1, 2, 4, 5, 6, 7], lr=True))
    E(raw, heads[KN_ENTRY])
    E(b_w, KN_CONT)

    # ---- c_tmown(r0 = a step's byte from c_tmlane) -> r0 = its own value: the first of its microsteps not 0xFF, else 0xFF; clobbers r1, r2
    # ---- c_tmkred(r0 = track, r1 = frame): the held step's knobs with their own value red; clobbers r0-r3
    a.label("c_tmown")
    E(push_list, [4], lr=True)
    E(movs_imm, 2, 0)
    a.label("ow_m")
    E(ldrb_reg, 1, 0, 2)
    E(cmp_imm, 1, 0xFF)
    E(b_cond, "ow_x", "ne")
    E(adds_imm8, 2, 1)
    E(cmp_imm, 2, MSTEPS)
    E(b_cond, "ow_m", "lo")
    a.label("ow_x")
    E(mov_reg, 0, 1)
    E(pop_list, [4], pc=True)

    a.label("c_tmkred")
    E(push_list, [3, 4, 5, 6, 7], lr=True)
    E(mov_reg, 4, 0)
    E(mov_reg, 5, 1)
    E(bl, "c_tmheld")
    E(cmp_imm, 0, 32)
    E(b_cond, "kr_x", "hs")
    E(mov_reg, 6, 0)                                      # r6 = the held step
    E(movs_imm, 7, 0)
    a.label("kr_k")
    E(mov_reg, 1, 4)
    E(mov_reg, 2, 7)
    E(mov_reg, 3, 6)
    E(bl, "c_tmlane")
    E(cmp_imm, 0, 0)
    E(b_cond, "kr_n", "eq")
    E(bl, "c_tmown")
    E(cmp_imm, 0, 0xFF)
    E(b_cond, "kr_n", "eq")
    E(movs_imm, 0, COL_REC)
    E(lsls_imm, 1, 7, 1)
    E(adds_reg, 1, 5, 1)
    E(strh_w_imm, 0, 1, 2 * LED_KNOB0)
    a.label("kr_n")
    E(adds_imm8, 7, 1)
    E(cmp_imm, 7, 8)
    E(b_cond, "kr_k", "lo")
    a.label("kr_x")
    E(pop_list, [3, 4, 5, 6, 7], pc=True)

    # ---- c_tmrec (the recorder's call: r0 = rec, r1 = lane, r2 = value; the caller's r5 = the track): menu open on that track, playing and
    #      a step held -> the recorder writes into the held step (p1 of [rec + 0x28] for this call only), else the stock's position
    a.label("c_tmrec")
    E(push_list, [0, 1, 2, 4, 5, 6, 7], lr=True)          # 8 words
    E(movs_imm, 7, 0)                                     # r7 = the position byte to put back (0 none)
    E(bl, L["c_rst"])
    E(cmp_imm, 0, 0)
    E(b_cond, "rc_go", "eq")
    ldb(0, 0, O_OPEN)
    E(cmp_imm, 0, 0)
    E(b_cond, "rc_go", "eq")
    E(bl, "c_tmview")
    E(cmp_reg, 0, 5)
    E(b_cond, "rc_go", "ne")
    imm32(0, C.TRANSPORT)
    E(movs_imm, 1, 0)
    E(bl, C.PARAM_GET)
    E(ldrb_imm, 0, 0, 0)
    E(cmp_imm, 0, 0)
    E(b_cond, "rc_go", "eq")                              # stopped: the stock's (the held step is the position already)
    E(mov_reg, 0, 5)
    E(bl, "c_tmheld")
    E(cmp_imm, 0, 32)
    E(b_cond, "rc_go", "hs")
    E(mov_reg, 6, 0)                                      # r6 = the held step
    E(ldr_sp, 0, 0)
    E(ldr_imm, 0, 0, REC_POS)
    E(movs_imm, 1, 1)
    E(bl, C.PARAM_GET)
    E(mov_reg, 7, 0)                                      # r7 = the position's step byte
    E(ldrb_imm, 4, 7, 0)                                  # r4 = the playhead's step
    E(strb_imm, 6, 7, 0)
    a.label("rc_go")
    E(ldr_sp, 0, 0)
    E(ldr_sp, 1, 4)
    E(ldr_sp, 2, 8)
    E(bl, RECORDER)
    E(cmp_imm, 7, 0)
    E(b_cond, "rc_x", "eq")
    E(strb_imm, 4, 7, 0)                                  # the playhead's step back, before the next tick reads it
    a.label("rc_x")
    E(pop_list, [0, 1, 2, 4, 5, 6, 7], pc=True)

    if stepmarker:
        # Stock Velocity/Gate selected-position marker: table entries 1/3 of
        # the stock step renderer (0x0805CF24), not a new clock or selection.
        a.label("c_tmposition")
        E(push_list, [4, 5, 6, 7], lr=True)
        E(mov_reg, 4, 0); E(mov_reg, 5, 1)
        imm32(0, C.TRANSPORT); E(movs_imm, 1, 0); E(bl, C.PARAM_GET)
        E(ldrb_imm, 0, 0, 0); E(cmp_imm, 0, 0)
        E(b_cond, "position_x", "ne")
        imm32(0, CONT + STEPOBJ)
        E(lsls_imm, 1, 4, 2); E(adds_reg, 0, 0, 1); E(ldr_imm, 4, 0, 0)
        E(ldr_imm, 0, 4, 0x18); E(movs_imm, 1, 1); E(bl, C.PARAM_GET)
        E(ldrb_imm, 6, 0, 0); E(cmp_imm, 6, 32)
        E(b_cond, "position_x", "hs")
        E(ldr_imm, 0, 4, 0x60); E(movs_imm, 1, 0); E(bl, C.PARAM_GET)
        E(ldrb_imm, 0, 0, 0); E(lsrs_imm, 1, 6, 4); E(cmp_reg, 0, 1)
        E(b_cond, "position_x", "ne")
        E(mov_reg, 0, 4); E(adds_imm8, 0, 0x74)
        E(lsls_imm, 1, 6, 1); E(adds_reg, 0, 0, 1); E(ldrh_imm, 0, 0, 0)
        E(lsls_imm, 0, 0, 30)                    # stock step-present flag, bit 1
        E(movw, 1, 2)
        E(b_cond, "position_empty", "pl")
        E(movs_imm, 1, 6)
        a.label("position_empty")
        imm32(0, L["step_palette"])
        E(adds_reg, 0, 0, 1); E(ldrh_imm, 1, 0, 0)
        E(mov_reg, 0, 6); E(movs_imm, 2, 15); E(ands_reg, 0, 2)
        E(lsls_imm, 0, 0, 1); E(raw, h(0x5229))
        a.label("position_x")
        E(pop_list, [4, 5, 6, 7], pc=True)

    # ---- c_tmrpad(r0 = track, r1 = frame): a held step's pad white, red with Record armed; playing with Record armed, the playhead's
    #      pad white (the held step's page only: the held step is on the page shown); clobbers r0-r3
    a.label("c_tmrpad")
    E(push_list, [3, 4, 5, 6, 7], lr=True)
    E(mov_reg, 4, 0)
    E(mov_reg, 5, 1)
    if stepmarker:
        E(bl, "c_tmposition")
        E(mov_reg, 0, 4)
    E(bl, "c_tmheld")
    E(cmp_imm, 0, 32)
    E(b_cond, "rp_x", "hs")
    E(mov_reg, 6, 0)                                      # r6 = the held step
    E(movs_imm, 7, COL_FULL)                              # r7 = its pad's code
    if sp:
        E(bl, L["c_rst"])
        ldb(0, 0, O_PAGE)
        E(cmp_imm, 0, PAGE_SP)
        E(b_cond, "rp_h", "eq")                           # the Stock+ page: nothing records
        if fpage:
            E(cmp_imm, 0, PAGE_X)
            E(b_cond, "rp_h", "eq")
        if gran:
            E(cmp_imm, 0, PAGE_G)
            E(b_cond, "rp_h", "eq")
        if filt:
            E(cmp_imm, 0, PAGE_F)
            E(b_cond, "rp_h", "eq")
        if vol:
            E(cmp_imm, 0, PAGE_V)
            E(b_cond, "rp_h", "eq")
    imm32(0, C.TRANSPORT)
    E(movs_imm, 1, 1)
    E(bl, C.PARAM_GET)
    E(ldrb_imm, 0, 0, 0)
    E(cmp_imm, 0, 0)
    E(b_cond, "rp_h", "eq")                               # Record not armed
    E(movs_imm, 7, COL_REC)
    imm32(0, C.TRANSPORT)
    E(movs_imm, 1, 0)
    E(bl, C.PARAM_GET)
    E(ldrb_imm, 0, 0, 0)
    E(cmp_imm, 0, 0)
    E(b_cond, "rp_h", "eq")                               # stopped
    imm32(1, AUTO)
    E(ldr_imm, 0, 1, 0)
    imm32(2, AUTO_VT)
    E(cmp_reg, 0, 2)
    E(b_cond, "rp_h", "ne")
    E(adds_imm8, 1, AUTO_RECS)
    E(lsls_imm, 0, 4, 2)
    E(raw, h(0x5808))                                     # ldr r0, [r1, r0]: the recorder object
    E(ldr_imm, 0, 0, REC_PLAY)
    E(movs_imm, 1, 1)
    E(bl, C.PARAM_GET)
    E(ldrb_imm, 0, 0, 0)                                  # r0 = the playhead's step
    E(mov_reg, 1, 0)
    E(eors_reg, 1, 6)
    E(lsrs_imm, 1, 1, 4)
    E(b_cond, "rp_h", "ne")                               # another page (or none)
    E(movs_imm, 1, 15)
    E(ands_reg, 0, 1)
    E(lsls_imm, 0, 0, 1)
    E(movs_imm, 1, COL_FULL)
    E(raw, h(0x5229))                                     # strh r1, [r5, r0]
    a.label("rp_h")
    E(mov_reg, 0, 6)
    E(movs_imm, 1, 15)
    E(ands_reg, 0, 1)
    E(lsls_imm, 0, 0, 1)
    E(mov_reg, 1, 7)
    E(raw, h(0x5229))                                     # strh r1, [r5, r0]
    a.label("rp_x")
    E(pop_list, [3, 4, 5, 6, 7], pc=True)

    # ---- c_tmled (a head of the LED task's chain: r0 = ctrl, r1 = frame): open / close from the press, then the menu over the frame
    a.label("c_tmled")
    E(push_list, [3, 4, 5, 6, 7], lr=True)
    E(mov_reg, 5, 1)
    E(bl, L["prev_led"])
    if gran:
        E(bl, gran["c_grframe"])
    if shapes:
        E(bl, shapes["c_shframe"])
    if filt:
        E(bl, filt["c_flframe"])
    E(bl, L["c_rst"])
    E(cmp_imm, 0, 0)
    E(b_cond, "ld_x0", "eq")
    E(mov_reg, 4, 0)
    E(bl, "c_tmview")
    E(mov_reg, 6, 0)                                      # r6 = the selected track
    if bounce:
        ldb(0, 4, O_BACK)
        E(cmp_imm, 0, 0)
        E(b_cond, "ld_nb", "eq")
        E(subs_imm8, 0, 1)
        imm32(1, CTRL + HELD)
        E(ldr_imm, 1, 1, 0)
        E(lsrs_reg, 1, 0)
        E(lsls_imm, 1, 1, 31)
        E(b_cond, "ld_nb", "mi")                          # still held
        E(movs_imm, 0, 0)
        stb(0, 4, O_BACK)
        imm32(0, C.HAL_TICK)
        E(ldr_imm, 0, 0, 0)
        ldw(1, 4, O_BTICK)
        E(subs_reg, 0, 0, 1)
        E(movw, 1, STOCK_HOLD)
        E(cmp_reg, 0, 1)
        E(b_cond, "ld_nb", "lo")                          # a tap: the button's view, the menu closed (the stock's first view)
        E(cmp_imm, 6, 8)
        E(b_cond, "ld_nb", "hs")
        E(movs_imm, 0, 1)
        stb(0, 4, O_OPEN)                                 # a hold, the stock back on a track view: the menu again
        stb(0, 4, O_STICKY)
        a.label("ld_nb")
    E(cmp_imm, 6, 8)
    E(b_cond, "ld_v", "lo")
    E(movs_imm, 0, 0)                                     # not a track view: closed, the press forgotten
    stb(0, 4, O_OPEN)
    stb(0, 4, O_PTRK)
    if twoview:
        stb(0, 4, O_SHOP)
    if sp:
        E(mov_reg, 0, 4)
        E(bl, "c_tmsp")
    a.label("ld_x0")
    E(b, "ld_x")
    a.label("ld_v")
    if twoview:
        ldb(0, 4, O_SHOP)
        E(cmp_imm, 0, 0)
        E(b_cond, "ld_ns", "eq")
        E(movs_imm, 0, 0)
        stb(0, 4, O_SHOP)
        E(movs_imm, 0, 1)
        stb(0, 4, O_OPEN)                                 # Shift + a track: open on it
        stb(0, 4, O_STICKY)
        a.label("ld_ns")
    ldb(7, 4, O_PTRK)
    E(cmp_imm, 7, 0)
    E(b_cond, "ld_d", "eq")
    E(subs_imm8, 7, 1)                                    # r7 = the pressed track
    imm32(0, C.HAL_TICK)
    E(ldr_imm, 0, 0, 0)
    ldw(1, 4, O_PTICK)
    E(subs_reg, 0, 0, 1)                                  # r0 = how long since the press
    imm32(1, CTRL + HELD)
    E(ldr_imm, 1, 1, 0)
    E(lsrs_reg, 1, 7)
    E(lsls_imm, 1, 1, 31)
    E(b_cond, "ld_up", "eq")
    if bounce:
        if momhold:
            ldb(1, 4, O_PSEL)
            E(cmp_imm, 1, 1)
            E(b_cond, "ld_d", "ne")                       # another track, or flipped already
            E(movw, 1, STOCK_HOLD)
            E(cmp_reg, 0, 1)
            E(b_cond, "ld_d", "lo")
            E(movs_imm, 1, PSEL_FLIP)
            stb(1, 4, O_PSEL)
            ldb(1, 4, O_OPEN)                             # the selected track held: the other view while held
            E(movs_imm, 0, 1)
            E(eors_reg, 1, 0)
            stb(1, 4, O_OPEN)
            stb(0, 4, O_STICKY)
        E(b, "ld_d")                                      # still held: the stock's (that track while held)
    else:
        E(cmp_imm, 0, HOLD_MS)                            # still held
        E(b_cond, "ld_d", "lo")
        E(movs_imm, 0, 1)
        stb(0, 4, O_OPEN)
        E(movs_imm, 0, 0)
        stb(0, 4, O_STICKY)
        E(b, "ld_d")
    a.label("ld_up")
    E(movs_imm, 1, 0)                                     # released
    stb(1, 4, O_PTRK)
    if momhold:
        ldb(1, 4, O_PSEL)
        E(cmp_imm, 1, PSEL_FLIP)
        E(b_cond, "ld_upn", "ne")
        ldb(1, 4, O_OPEN)                                 # the end of the flip: the view it started from
        E(movs_imm, 0, 1)
        E(eors_reg, 1, 0)
        stb(1, 4, O_OPEN)
        stb(0, 4, O_STICKY)
        E(b, "ld_d")
        a.label("ld_upn")
    if bounce:
        E(movw, 1, STOCK_HOLD)
        E(cmp_reg, 0, 1)
        E(b_cond, "ld_d", "hs")                           # a hold: the stock puts the earlier track back, the menu as it was
    else:
        E(cmp_imm, 0, HOLD_MS)
        E(b_cond, "ld_long", "hs")
    ldb(1, 4, O_PSEL)                                     # a tap: on the selected track it opens / closes the menu
    E(cmp_imm, 1, 0)
    E(b_cond, "ld_d", "eq")
    if twoview:
        imm32(0, CONT)
        E(ldrb_w, 0, 0, O_MODE)
        ldb(1, 4, O_PMODE)
        E(cmp_reg, 0, 1)
        E(b_cond, "ld_d", "ne")                           # the press changed the view: its first view only
    ldb(1, 4, O_OPEN)
    E(movs_imm, 0, 1)
    E(eors_reg, 1, 0)
    stb(1, 4, O_OPEN)
    stb(0, 4, O_STICKY)
    E(b, "ld_d")
    a.label("ld_long")
    ldb(1, 4, O_STICKY)                                   # the end of a hold: closed
    E(cmp_imm, 1, 0)
    E(b_cond, "ld_d", "ne")
    stb(1, 4, O_OPEN)

    a.label("ld_d")
    if perpage:                                           # the selected track's page, as the project holds it
        E(mov_reg, 0, 6)
        E(bl, "c_tmpgget")
        E(cmp_imm, 0, 0xFF)
        E(b_cond, "ld_pg", "eq")
        E(mov_reg, 1, 0)
        ldb(2, 4, O_PAGE)
        E(cmp_reg, 1, 2)
        E(b_cond, "ld_pg", "eq")
        if sp:
            E(movs_imm, 3, 0)
            E(cmp_imm, 2, PAGE_SP)
            E(b_cond, "ld_pgo", "ne")
            E(adds_imm8, 3, 1)
            a.label("ld_pgo")
            E(cmp_imm, 1, PAGE_SP)
            E(b_cond, "ld_pgn", "ne")
            E(adds_imm8, 3, 1)
            a.label("ld_pgn")
            E(cmp_imm, 3, 1)
            E(b_cond, "ld_pgs", "ne")
            ldb(2, 4, O_KNOB)                             # to or from Stock+: its own knob shown, the other kept
            ldb(3, 4, O_KNOB2)
            stb(3, 4, O_KNOB)
            stb(2, 4, O_KNOB2)
            a.label("ld_pgs")
        stb(1, 4, O_PAGE)
        a.label("ld_pg")
    if sp:
        E(mov_reg, 0, 4)
        E(bl, "c_tmsp")
    ldb(0, 4, O_OPEN)
    E(cmp_imm, 0, 0)
    E(b_cond, "ld_o", "ne")
    E(b, "ld_x")
    a.label("ld_o")
    stb(6, 4, O_SEL)
    E(movs_imm, 1, COL_FULL)
    for t in range(8):
        E(strh_w_imm, 1, 5, 2 * (LED_TRK0 + t))
    E(movs_imm, 0, 0)
    E(lsls_imm, 1, 6, 1)
    E(adds_reg, 1, 5, 1)
    E(strh_w_imm, 0, 1, 2 * LED_TRK0)                     # the selected track: its colour after the output stage
    for p in range(ROW3, 32):
        E(strh_w_imm, 0, 5, 2 * p)
    E(movs_imm, 0, COL_FULL)
    E(strh_w_imm, 0, 5, 2 * PAD_KNOB)
    for i in PADOF.values():
        E(strh_w_imm, 0, 5, 2 * (page0 + i))           # the pages not shown: dim after the output stage
    E(mov_reg, 0, 6)
    E(mov_reg, 1, 5)
    E(bl, "c_tmrpad")
    ldb(7, 4, O_KNOB)
    E(cmp_imm, 7, 0)
    E(b_cond, "ld_k", "eq")
    E(subs_imm8, 7, 1)                                    # r7 = the knob (K1 before any turn)
    a.label("ld_k")
    if gran:
        ldb(0, 4, O_PAGE)
        E(cmp_imm, 0, PAGE_G)
        E(b_cond, "ld_ng", "ne")
        E(movs_imm, 0, 0)
        stb(0, 4, O_WHT)
        stb(0, 4, O_RED)
        E(cmp_imm, 7, 4)
        E(b_cond, "ld_gl", "lo")
        E(bl, sp["c_spshift"])
        E(cmp_imm, 0, 0)
        E(b_cond, "ld_gl", "eq")
        E(adds_imm8, 7, 4)                                # Shift + K5-K8: values 8-11
        a.label("ld_gl")
        E(mov_reg, 0, 6)
        E(mov_reg, 1, 7)
        E(bl, gran["c_grval"])
        E(mov_reg, 6, 0)                                  # r6 = the value, 0..16383
        E(lsrs_imm, 0, 6, 7)
        stb(0, 4, O_V)
        for i, m in enumerate(gran["bip"]):
            if m:
                E(cmp_imm, 7, i)
                far("ld_bi", "eq")
        E(b, "ld_fl")
        a.label("ld_ng")
    if fpage:
        ldb(0, 4, O_PAGE)
        E(cmp_imm, 0, PAGE_X)
        E(b_cond, "ld_nf", "ne")
        E(movs_imm, 0, 0)
        stb(0, 4, O_WHT)
        stb(0, 4, O_RED)
        E(movs_imm, 1, X_IDX[0])                          # (the shown knob past the page's: K1)
        for k in XLIVE[1:]:
            E(cmp_imm, 7, k)
            E(b_cond, f"ld_fk{k}", "ne")
            E(movs_imm, 1, X_IDX[k])
            a.label(f"ld_fk{k}")
        E(mov_reg, 7, 1)                                  # r7 = the Stock+ value
        if scanfx:
            E(b, "ld_sv")
        else:
            E(mov_reg, 0, 6)
            E(bl, sp["c_spval"])
            E(mov_reg, 6, 0)
            E(lsrs_imm, 0, 6, 7)
            stb(0, 4, O_V)
            E(b, "ld_fl")
        a.label("ld_nf")
    if filt:
        ldb(0, 4, O_PAGE)
        E(cmp_imm, 0, PAGE_F)
        far("ld_nfl", "ne")
        E(movs_imm, 0, 0)
        stb(0, 4, O_WHT)
        stb(0, 4, O_RED)
        if sb:
            E(cmp_imm, 7, 6)
            far("ld_flo", "lo")
            E(push_list, [7])
            E(bl, sp["c_spshift"])
            E(pop_list, [7])
            E(cmp_imm, 0, 0)
            far("ld_ed", "eq")                            # K7 / K8: the stock's bar
            E(cmp_imm, 7, 6)
            E(b_cond, "ld_f8", "ne")
            E(movs_imm, 7, FSH[6])
            E(b, "ld_sv")
            a.label("ld_f8")
            E(movs_imm, 7, FSH[7])
            E(b, "ld_sv")
            a.label("ld_flo")
        else:
            E(cmp_imm, 7, 6)
            far("ld_ed", "hs")                            # K7 / K8: the stock's bar
        E(mov_reg, 1, 7)
        E(movs_imm, 7, F_MAP[0])
        for k in range(1, 6):
            E(cmp_imm, 1, k)
            E(b_cond, f"ld_fm{k}", "ne")
            E(movs_imm, 7, F_MAP[k])
            a.label(f"ld_fm{k}")
        if not sb:
            E(push_list, [1])
            E(bl, sp["c_spshift"])
            E(mov_reg, 2, 0)
            E(pop_list, [1])
            E(cmp_imm, 2, 0)
            E(b_cond, "ld_flv", "eq")
            for k, i in F_SHIFT.items():
                E(cmp_imm, 1, k)
                E(b_cond, f"ld_fs{k}", "ne")
                E(movs_imm, 7, i)
                a.label(f"ld_fs{k}")
        a.label("ld_flv")
        E(b, "ld_sv")
        a.label("ld_nfl")
    if vol:
        ldb(0, 4, O_PAGE)
        E(cmp_imm, 0, PAGE_V)
        far("ld_nvl", "ne")
        E(movs_imm, 0, 0)
        stb(0, 4, O_WHT)
        stb(0, 4, O_RED)
        E(mov_reg, 1, 7)
        E(movs_imm, 7, V_MAP[0])                          # (K4-K8 shown: K1)
        for k in range(1, V_KNOBS):
            E(cmp_imm, 1, k)
            E(b_cond, f"ld_vm{k}", "ne")
            E(movs_imm, 7, V_MAP[k])
            a.label(f"ld_vm{k}")
        E(b, "ld_sv")
        a.label("ld_nvl")
    if sp:
        ldb(0, 4, O_PAGE)
        E(cmp_imm, 0, PAGE_SP)
        (far("ld_ed", "ne") if filt else E(b_cond, "ld_ed", "ne"))
        E(movs_imm, 0, 0)
        stb(0, 4, O_WHT)
        stb(0, 4, O_RED)
        if shapes:
            if FADE[0]:
                E(cmp_imm, 7, SP_RANDK - 1)
                E(b_cond, "ld_fz", "ne")
                E(bl, sp["c_spshift"])
                E(cmp_imm, 0, 0)
                E(b_cond, "ld_fz", "eq")
                E(movs_imm, 7, FADE_V)                    # Shift held on K7: the LFO's fade-in
                E(b, "ld_sv")
                a.label("ld_fz")
            E(mov_reg, 1, 7)
            E(movs_imm, 7, SP_MAP[0])
            for k in range(1, SPN):
                E(cmp_imm, 1, k)
                E(b_cond, f"ld_m{k}", "ne")
                E(movs_imm, 7, SP_MAP[k])
                a.label(f"ld_m{k}")
            E(b, "ld_sv")
        E(cmp_imm, 7, 4)
        E(b_cond, "ld_sv", "lo")                          # K1-K4: values 0-3
        if fpage:
            for k, i in SP_OWN.items():
                E(cmp_imm, 7, k)
                E(b_cond, f"ld_so{k}", "ne")
                E(movs_imm, 7, i)                         # K5 / K6: one value each, with or without Shift
                E(b, "ld_sv")
                a.label(f"ld_so{k}")
        E(bl, sp["c_spshift"])
        E(cmp_imm, 0, 0)
        E(b_cond, "ld_sm", "eq")
        E(cmp_imm, 7, SP_K6)
        E(b_cond, "ld_s2", "ne")
        E(movs_imm, 7, SP_TYPE)                           # Shift + K6: the filter type
        E(b, "ld_sv")
        a.label("ld_s2")
        E(adds_imm8, 7, 4)                                # Shift + K5 / K7 / K8: their second layer (8, 10, 11)
        E(b, "ld_sv")
        a.label("ld_sm")
        E(cmp_imm, 7, SP_K6)
        E(b_cond, "ld_sv", "ne")
        E(movs_imm, 7, SP_FOLLOW)                         # K6: the pitch follow
        a.label("ld_sv")                                  # r7 = the value's index, 0..11 (filt: 0..17)
        E(mov_reg, 0, 6)
        E(mov_reg, 1, 7)
        E(bl, VAL)
        E(mov_reg, 6, 0)                                  # r6 = its Stock+ value, 0..16383
        E(lsrs_imm, 0, 6, 7)
        stb(0, 4, O_V)
        if sb:
            for i in SB_RATES:
                E(cmp_imm, 7, i)
                E(b_cond, "ld_rt", "eq")
            E(b, "ld_rn")
            a.label("ld_rt")
            E(movw, 1, SB_SYNC0)
            E(cmp_reg, 6, 1)
            E(b_cond, "ld_rn", "lt")                      # the middle or free: from the middle
            E(subs_reg, 0, 6, 1)
            E(lsrs_imm, 0, 0, 9)
            E(cmp_imm, 0, 15)
            E(b_cond, "ld_sb", "ls")
            E(movs_imm, 0, 15)
            E(b, "ld_sb")
            a.label("ld_rn")
            E(lsrs_imm, 0, 6, 7)
        if shapebar and filt:
            shn = {**SHAPE_N, **F_SHN, **(V_SHN if vol else {})}
            for i in shn:
                E(cmp_imm, 7, i)
                E(b_cond, f"ld_sh{i}", "eq")
            E(b, "ld_sn")
            for i, n in shn.items():
                a.label(f"ld_sh{i}")
                if n == 16:
                    E(lsrs_imm, 0, 6, 10)
                else:
                    E(movs_imm, 0, n)
                    E(muls, 0, 6)
                    E(lsrs_imm, 0, 0, 14)
                E(b, "ld_sb")
        elif shapebar:
            (ve, ne), (vl, nl) = SHAPE_N.items()
            assert ne == 16
            E(cmp_imm, 7, ve)
            E(b_cond, "ld_se", "eq")
            E(cmp_imm, 7, vl)
            E(b_cond, "ld_sn", "ne")
            E(movs_imm, 0, nl)
            E(muls, 0, 6)
            E(lsrs_imm, 0, 0, 14)
            E(b, "ld_sb")
            a.label("ld_se")
            E(lsrs_imm, 0, 6, 10)
        if shapebar:
            a.label("ld_sb")                              # r0 = the shape n
            E(movs_imm, 1, 0)
            for i in range(8):
                stb(1, 4, O_BAR + i)
            E(movs_imm, 2, 7)
            E(ands_reg, 2, 0)                             # r2 = its pad
            E(movw, 3, O + O_BAR)
            E(adds_reg, 3, 3, 4)
            E(movs_imm, 1, 255)
            E(raw, h(0x5400 | 2 << 6 | 3 << 3 | 1))       # strb r1, [r3, r2]
            E(lsls_imm, 0, 0, 28)
            far("ld_x", "pl")
            E(movs_imm, 1, 1)
            E(lsls_reg, 1, 2)
            stb(1, 4, O_WHT)                              # n 8-15: white
            E(b, "ld_x")
            a.label("ld_sn")
        for i in SP_MIDS + (F_MIDS if filt else ()) + (V_MIDS if vol else ()):
            E(cmp_imm, 7, i)
            far("ld_bi", "eq")
        E(b, "ld_fl")                                     # the others: 2048 a pad
        a.label("ld_ed")
    imm32(0, CTRL + HELD)
    E(ldr_imm, 0, 0, 0)
    E(lsls_imm, 0, 0, 31 - 23)
    E(b_cond, "ld_kl", "mi")                              # Clear held: the stock's knob LEDs (its clear colours)
    E(mov_reg, 0, 6)
    E(mov_reg, 1, 5)
    E(bl, "c_tmkred")
    a.label("ld_kl")
    E(movs_imm, 0, 0)
    stb(0, 4, O_WHT)
    stb(0, 4, O_RED)
    E(mov_reg, 0, 6)                                      # a held step with its own value of this knob -> O_RED, the value O_AV
    E(bl, "c_tmheld")
    E(cmp_imm, 0, 32)
    E(b_cond, "au_x", "hs")
    E(mov_reg, 3, 0)
    E(mov_reg, 1, 6)
    E(mov_reg, 2, 7)
    E(bl, "c_tmlane")
    E(cmp_imm, 0, 0)
    E(b_cond, "au_x", "eq")
    E(bl, "c_tmown")
    E(cmp_imm, 0, 0xFF)
    E(b_cond, "au_x", "eq")
    stb(0, 4, O_AV)
    E(movs_imm, 0, 1)
    stb(0, 4, O_RED)
    a.label("au_x")
    imm32(0, CTRL + KSTORES)
    E(lsls_imm, 1, 6, 2)
    E(adds_reg, 0, 0, 1)
    E(ldr_imm, 6, 0, 0)                                   # r6 = the selected track's knob store
    E(mov_reg, 0, 6)
    E(mov_reg, 1, 7)
    E(bl, C.PARAM_GET)
    E(ldrb_imm, 0, 0, 0)
    ldb(1, 4, O_RED)
    E(cmp_imm, 1, 0)
    E(b_cond, "ld_kv", "eq")
    ldb(0, 4, O_AV)                                       # the held step's own value
    a.label("ld_kv")
    stb(0, 4, O_V)
    E(cmp_imm, 7, 0)
    far("ld_bi", "eq")
    E(cmp_imm, 7, 3)
    far("ld_bi", "eq")
    E(cmp_imm, 7, 1)
    far("ld_fn", "eq")
    E(cmp_imm, 7, 2)
    far("ld_fn", "eq")
    ldb(6, 4, O_V)                                        # 16 values a pad
    for i in range(8):
        E(mov_reg, 0, 6)
        if i:
            E(subs_imm8, 0, 16 * i)
        E(movs_imm, 1, 4)
        E(bl, "c_tmfill")
        stb(0, 4, O_BAR + i)
    E(b, "ld_z")

    a.label("ld_fn")                                      # K2 / K3: v * 128 + fine, 2048 a pad
    E(mov_reg, 0, 6)
    E(mov_reg, 1, 7)
    E(adds_imm8, 1, FINE[1] - 1)
    E(bl, C.PARAM_GET)
    E(ldrb_imm, 1, 0, 0)
    ldb(2, 4, O_RED)
    E(cmp_imm, 2, 0)
    E(b_cond, "ld_fv", "eq")
    E(movs_imm, 1, 0)                                     # a step's value has no fine part
    a.label("ld_fv")
    ldb(6, 4, O_V)
    E(lsls_imm, 6, 6, 7)
    E(adds_reg, 6, 6, 1)
    a.label("ld_fl")
    for i in range(8):
        E(mov_reg, 0, 6)
        if i:
            E(movs_imm, 1, i)
            E(lsls_imm, 1, 1, 11)
            E(subs_reg, 0, 0, 1)
        E(movs_imm, 1, 11)
        E(bl, "c_tmfill")
        stb(0, 4, O_BAR + i)
    E(b, "ld_z")

    a.label("ld_bi")                                      # K1 / K4: from the middle
    ldb(6, 4, O_V)
    E(movs_imm, 0, 0)
    for i in range(8):
        stb(0, 4, O_BAR + i)
    E(cmp_imm, 6, 64)
    far("ld_lo", "lo")
    far("ld_hi", "ne")
    E(movs_imm, 0, (1 << 3) | (1 << 4))                   # exactly the centre: pads 28 / 29 dim white
    stb(0, 4, O_WHT)
    E(b, "ld_x")
    a.label("ld_hi")
    for j in range(4):                                    # right of the middle: v - 64
        E(mov_reg, 0, 6)
        E(subs_imm8, 0, 64 + 16 * j)
        E(movs_imm, 1, 4)
        E(bl, "c_tmfill")
        stb(0, 4, O_BAR + 4 + j)
    E(b, "ld_m")
    a.label("ld_lo")
    for j in range(4):                                    # left of the middle: 64 - v
        E(movs_imm, 0, 64 - 16 * j)
        E(subs_reg, 0, 0, 6)
        E(movs_imm, 1, 4)
        E(bl, "c_tmfill")
        stb(0, 4, O_BAR + 3 - j)
    a.label("ld_m")
    for p in (3, 4):                                      # the middle pads: empty -> the marker, a fill at least MINF
        ldb(0, 4, O_BAR + p)
        E(cmp_imm, 0, 0)
        E(b_cond, f"ld_m{p}f", "ne")
        E(movs_imm, 0, MARK)
        E(b, f"ld_m{p}s")
        a.label(f"ld_m{p}f")
        E(cmp_imm, 0, MINF)
        E(b_cond, f"ld_m{p}s", "hs")
        E(movs_imm, 0, MINF)
        a.label(f"ld_m{p}s")
        stb(0, 4, O_BAR + p)
    E(b, "ld_x")
    a.label("ld_z")                                       # r6 = the value: 0 -> pad 25 at rest, else at least MINF
    E(cmp_imm, 6, 0)
    E(b_cond, "ld_zf", "ne")
    E(movs_imm, 0, 1)
    stb(0, 4, O_WHT)
    E(b, "ld_x")
    a.label("ld_zf")
    ldb(0, 4, O_BAR)
    E(cmp_imm, 0, MINF)
    E(b_cond, "ld_x", "hs")
    E(movs_imm, 0, MINF)
    stb(0, 4, O_BAR)
    a.label("ld_x")
    if shiftled:
        imm32(0, CTRL)
        E(ldr_imm, 0, 0, 0xC)
        E(movs_imm, 1, 0)
        E(bl, C.PARAM_GET)
        E(ldrb_imm, 0, 0, 0)
        E(cmp_imm, 0, 0)
        E(b_cond, "ld_xs", "eq")
        imm32(0, CONT)
        E(bl, SELTRK)
        E(movs_imm, 1, SHIFT_DIM)                         # Shift: the track numbers tan, as the stock's buttons with a Shift job
        for t in range(8):
            E(strh_w_imm, 1, 5, 2 * (LED_TRK0 + t))
        E(cmp_imm, 0, 8)
        E(b_cond, "ld_xs", "hs")
        E(lsls_imm, 0, 0, 1)
        E(adds_reg, 0, 5, 0)
        E(movs_imm, 1, SHIFT_BRT)
        E(strh_w_imm, 1, 0, 2 * LED_TRK0)
        a.label("ld_xs")
    E(pop_list, [3, 4, 5, 6, 7], pc=True)

    # ---- c_tmout (the LED task's call of the output stage: r0 = ctrl, r1 = the RGB words out, r2 = frame): the menu's colours over them
    a.label("c_tmout")
    E(push_list, [4, 5, 6, 7], lr=True)
    E(sub_sp_imm, 36)                                    # 5 words + 36: the calls below see an 8-byte aligned stack
    E(mov_reg, 4, 0)
    E(mov_reg, 5, 1)
    E(str_sp, 2, 12)                                      # [sp + 12] = the frame
    E(bl, L["prev_out"])
    E(mov_reg, 0, 4)
    E(adds_imm8, 0, O_DIM)
    E(ldr_imm, 0, 0, 0)
    E(movs_imm, 1, P_DIM)
    E(bl, C.PARAM_GET)
    E(ldr_imm, 0, 0, 0)
    E(lsrs_imm, 0, 0, BIT_DIM)
    E(movs_imm, 1, 1)
    E(ands_reg, 0, 1)
    E(cmp_imm, 0, 0)
    E(b_cond, "ou_d1", "ne")
    E(movs_imm, 0, 1)
    E(lsls_imm, 0, 0, 8)
    E(b, "ou_d")
    a.label("ou_d1")
    E(movs_imm, 0, DIM_MUL)
    a.label("ou_d")
    E(str_sp, 0, 0)                                       # [sp] = our levels' factor / 256: 256, or DIM_MUL with the stock's LEDs dimmed
    E(bl, L["c_rst"])
    E(cmp_imm, 0, 0)
    far("ou_x", "eq")
    E(mov_reg, 4, 0)
    if fpage:
        imm32(0, CTRL + HELD)
        E(ldr_imm, 0, 0, 0)
        E(lsls_imm, 0, 0, 31 - 23)
        E(b_cond, "ou_hc", "mi")
        E(movs_imm, 0, 0)
        for o in (O_CLRR, O_CLRR + 4, O_CLRL, O_CLRL + 4):
            stw(0, 4, o)
        a.label("ou_hc")
    ldb(0, 4, O_OPEN)
    E(cmp_imm, 0, 0)
    far("ou_x", "eq")
    ldb(6, 4, O_SEL)
    imm32(0, int.from_bytes(bytes(TRK_SLOTS[:4]), "little"))
    E(cmp_imm, 6, 4)
    E(b_cond, "ou_t4", "lo")
    imm32(0, int.from_bytes(bytes(TRK_SLOTS[4:]), "little"))
    a.label("ou_t4")
    E(movs_imm, 1, 3)
    E(ands_reg, 1, 6)
    E(lsls_imm, 1, 1, 3)
    E(lsrs_reg, 0, 1)
    E(movs_imm, 1, 0xFF)
    E(ands_reg, 0, 1)                                     # r0 = the track's palette slot
    E(lsls_imm, 0, 0, 2)
    imm32(1, COLOURS)
    E(raw, h(0x5808))                                     # ldr r0, [r1, r0]
    E(mov_reg, 7, 0)                                      # r7 = the track's colour
    E(str_sp, 0, 28)                                      # [sp + 28] = the track's colour
    E(str_sp, 0, 4)                                       # [sp + 4] = the bar's colour: the track's, red while recording knob turns
    imm32(0, pages[0])
    imm32(2, scl_py(pages[0], KNOB_LVL))
    ldb(1, 4, O_PAGE)
    for i in range(1, npages):
        E(cmp_imm, 1, i)
        E(b_cond, f"ou_g{i}", "ne")
        imm32(0, pages[i])
        imm32(2, scl_py(pages[i], KNOB_LVL))
        a.label(f"ou_g{i}")
    E(str_sp, 0, 20)                                      # [sp + 20] = the page's colour
    E(str_sp, 2, 24)                                      # [sp + 24] = the page's colour at KNOB_LVL
    imm32(0, 0xFFFFFF)
    E(str_sp, 0, 8)                                       # [sp + 8] = the rest pads' colour: white, red as the bar
    if sp:
        ldb(0, 4, O_PAGE)
        E(cmp_imm, 0, PAGE_SP)
        E(b_cond, "ou_tc", "eq")                          # the Stock+ page: nothing records
        if fpage:
            E(cmp_imm, 0, PAGE_X)
            E(b_cond, "ou_tc", "eq")
        if gran:
            E(cmp_imm, 0, PAGE_G)
            E(b_cond, "ou_tc", "eq")
        if filt:
            E(cmp_imm, 0, PAGE_F)
            E(b_cond, "ou_tc", "eq")
        if vol:
            E(cmp_imm, 0, PAGE_V)
            E(b_cond, "ou_tc", "eq")
    imm32(0, C.TRANSPORT)
    E(movs_imm, 1, 1)
    E(bl, C.PARAM_GET)
    E(ldrb_imm, 0, 0, 0)
    E(cmp_imm, 0, 0)
    E(b_cond, "ou_tc", "eq")                              # Record not armed
    ldb(0, 4, O_SEL)
    E(bl, "c_tmheld")
    E(cmp_imm, 0, 32)
    E(b_cond, "ou_rd", "lo")                              # a step held: red until it is let go
    imm32(0, C.HAL_TICK)
    E(ldr_imm, 0, 0, 0)
    ldw(1, 4, O_KTICK)
    E(subs_reg, 0, 0, 1)
    E(movw, 1, TURN_MS)
    E(cmp_reg, 0, 1)
    E(b_cond, "ou_tc", "hs")
    a.label("ou_rd")
    imm32(0, RED)
    E(str_sp, 0, 4)
    E(str_sp, 0, 8)
    a.label("ou_tc")
    if sp:
        E(movs_imm, 0, 0)
        E(str_sp, 0, 32)                                  # [sp + 32] = 1: Shift held on the Stock+ page
        ldb(0, 4, O_PAGE)
        if gran:
            E(cmp_imm, 0, PAGE_SP)
            E(b_cond, "ou_spg", "eq")
            E(cmp_imm, 0, PAGE_G)
            E(b_cond, "ou_sw", "ne")
            E(bl, sp["c_spshift"])
            E(cmp_imm, 0, 0)
            E(b_cond, "ou_sw", "eq")
            ldb(0, 4, O_KNOB)
            E(cmp_imm, 0, 5)
            E(b_cond, "ou_sw", "lo")
            imm32(0, SHIFT_RGB)
            E(str_sp, 0, 4)
            E(b, "ou_sw")
            a.label("ou_spg")
        if filt:
            E(cmp_imm, 0, PAGE_F)
            E(b_cond, "ou_fsn", "ne")
            E(bl, sp["c_spshift"])
            E(cmp_imm, 0, 0)
            E(b_cond, "ou_sw", "eq")
            ldb(0, 4, O_KNOB)
            k1, k2 = (k + 1 for k in FSH)
            E(cmp_imm, 0, k1)
            E(b_cond, "ou_ft", "eq")
            E(cmp_imm, 0, k2)
            E(b_cond, "ou_sw", "ne")
            a.label("ou_ft")
            imm32(0, COLOURS + 4 * SHIFT_BRT)
            E(ldr_imm, 0, 0, 0)
            E(str_sp, 0, 4)                               # Shift + K1 / K4 shown: the stock's Shift tan
            E(b, "ou_sw")
            a.label("ou_fsn")
        E(cmp_imm, 0, PAGE_SP)
        E(b_cond, "ou_sw", "ne")
        E(bl, sp["c_spshift"])
        E(cmp_imm, 0, 0)
        E(b_cond, "ou_sw", "eq")
        E(movs_imm, 0, 1)
        E(str_sp, 0, 32)
        ldb(0, 4, O_KNOB)
        E(cmp_imm, 0, 9 if fpage else 5)                  # O_KNOB is the knob + 1: K5-K8 show a second layer (fpage: none)
        E(b_cond, "ou_sw", "lo")
        imm32(0, SHIFT_RGB)
        E(str_sp, 0, 4)
        a.label("ou_sw")
    for i in range(8):
        ldb(0, 4, O_WHT)
        E(movs_imm, 1, 1 << i)
        E(tst_reg, 0, 1)
        E(b_cond, f"ou_c{i}", "eq")
        E(ldr_sp, 0, 8)
        if shapebar:
            ldb(1, 4, O_BAR + i)                          # a white pad with a level (the shape bar): that level
            E(cmp_imm, 1, 0)
            if shapebar == "page":
                E(b_cond, f"ou_w{i}", "eq")
                E(ldr_sp, 0, 20)
                E(b, f"ou_s{i}")
                a.label(f"ou_w{i}")
            else:
                E(b_cond, f"ou_s{i}", "ne")
        E(movs_imm, 1, WHITE)
        E(b, f"ou_s{i}")
        a.label(f"ou_c{i}")
        E(ldr_sp, 0, 4)
        ldb(1, 4, O_BAR + i)
        a.label(f"ou_s{i}")
        E(ldr_sp, 2, 0)
        E(muls, 1, 2)
        E(lsrs_imm, 1, 1, 8)
        E(bl, "c_tmscl")
        E(str_imm, 0, 5, 4 * (BAR + i))
    for i in range(npages):                               # each page pad its page's colour: full on the page shown, else dim
        ldb(0, 4, O_PAGE)
        E(movs_imm, 1, WHITE)
        E(cmp_imm, 0, i)
        E(b_cond, f"ou_p{i}", "ne")
        E(movs_imm, 1, 0xFF)
        a.label(f"ou_p{i}")
        if gran and i == PAGE_G:
            E(cmp_imm, 1, 0xFF)
            E(b_cond, "ou_gp", "ne")
            E(bl, gran["c_grtrk"])
            ldb(1, 4, O_SEL)
            E(adds_imm8, 1, 1)
            E(cmp_reg, 0, 1)
            E(b_cond, "ou_gf", "eq")
            E(movs_imm, 1, WHITE)                         # shown, the granular off on this track: dim
            E(b, "ou_gp")
            a.label("ou_gf")
            E(movs_imm, 1, 0xFF)
            a.label("ou_gp")
        imm32(0, pages[i])
        E(ldr_sp, 2, 0)
        E(muls, 1, 2)
        E(lsrs_imm, 1, 1, 8)
        E(bl, "c_tmscl")
        if i in PADOF:
            E(str_imm, 0, 5, 4 * (page0 + PADOF[i]))
    for j, pg in enumerate(PADMAP):
        if pg is None:
            E(movs_imm, 0, 0)
            E(str_imm, 0, 5, 4 * (page0 + j))             # a pad with no page: dark
    if pageclear:
        # Red reset pad only while Clear is held; selected page flashes after reset.
        imm32(0, CTRL + HELD)
        E(ldr_imm, 0, 0, 0)
        E(lsls_imm, 0, 0, 8)
        E(b_cond, "ou_pcend", "pl")
        if not steadyreset:
            imm32(0, C.HAL_TICK)
            E(ldr_imm, 0, 0, 0)
            E(lsls_imm, 0, 0, 25)                       # legacy idle blink
            E(movw, 0, 0)
            E(b_cond, "ou_pcstore", "mi")
        if resetcue:
            # Same dim-red palette entry and global brightness as Sample mode reset.
            imm32(0, COLOURS + 4 * 0x54)
            E(ldr_imm, 0, 0, 0)
            E(ldr_sp, 1, 0); E(subs_imm8, 1, 1)
            E(bl, "c_tmscl")
        else:
            imm32(0, RED)
        a.label("ou_pcstore")
        E(str_imm, 0, 5, 4 * 31)
        a.label("ou_pcend")
        imm32(0, L["pcslot"])
        E(ldrb_imm, 1, 0, 4)
        E(cmp_imm, 1, 0)
        E(b_cond, "ou_pcflashend", "eq")
        E(ldr_imm, 0, 0, 0)
        imm32(2, C.HAL_TICK)
        E(ldr_imm, 2, 2, 0)
        E(subs_reg, 0, 2, 0)
        E(movw, 2, 384)
        E(cmp_reg, 0, 2)
        E(b_cond, "ou_pcflashend", "hs")
        E(subs_imm8, 1, 1)
        E(lsls_imm, 1, 1, 2)
        E(adds_reg, 1, 5, 1)
        E(lsls_imm, 0, 0, 25)
        E(movw, 0, 0)
        E(b_cond, "ou_pcfstore", "mi")
        if softclear:
            E(str_sp, 1, 16)                   # scratch before knob-index use
            imm32(0, COLOURS + 4 * 0x55); E(ldr_imm, 0, 0, 0)
            E(ldr_sp, 1, 0); E(subs_imm8, 1, 1); E(bl, "c_tmscl")
            E(ldr_sp, 1, 16)
        else:
            imm32(0, RED)
        a.label("ou_pcfstore")
        E(str_imm, 0, 1, 0)
        if resetcue:
            # The all-pages action flashes every page as well as its own reset pad.
            E(mov_reg, 2, 5); E(adds_imm8, 2, 4 * 31)
            E(cmp_reg, 1, 2)
            E(b_cond, "ou_pcflashend", "ne")
            for i in PADOF.values():
                E(str_imm, 0, 5, 4 * (page0 + i))
        a.label("ou_pcflashend")
    E(mov_reg, 0, 7)                                      # pad 25: the track's colour, at its lowest (not scaled by the stock's dim)
    E(movs_imm, 1, CYC_LVL)
    E(bl, "c_tmscl")
    E(str_imm, 0, 5, 4 * PAD_KNOB)
    if shiftled:
        imm32(0, CTRL)
        E(ldr_imm, 0, 0, 0xC)
        E(movs_imm, 1, 0)
        E(bl, C.PARAM_GET)
        E(ldrb_imm, 0, 0, 0)
        E(cmp_imm, 0, 0)
        E(b_cond, "ou_ns", "eq")
        E(movs_imm, 7, LED_TRK0 + 8)
        E(b, "ou_ts")                                     # Shift: the track numbers as the frame's tan
        a.label("ou_ns")
    E(mov_reg, 0, 7)                                      # the selected track: its colour at full brightness, also when the stock dims,
    if trackpulse:
        # Palette 0x0A is the stock LED frame's grayscale pulse coefficient.
        # White step selection uses its complement in 0x0803E3A4.
        imm32(2, COLOURS + 4 * 0x0A); E(ldrb_imm, 2, 2, 0)
        E(movw, 1, 255); E(subs_reg, 1, 1, 2)
        E(movs_imm, 2, 192); E(muls, 1, 2); E(lsrs_imm, 1, 1, 8)
        E(adds_imm8, 1, 64); E(bl, "c_tmscl")
    else:
        imm32(2, C.HAL_TICK)                                  # dark every other BLINK_BIT period
        E(ldr_imm, 2, 2, 0)
        E(lsls_imm, 2, 2, 31 - BLINK_BIT)
        E(b_cond, "ou_bl", "pl")
        E(movs_imm, 0, 0)
    a.label("ou_bl")
    E(adds_imm8, 6, LED_TRK0)
    E(lsls_imm, 1, 6, 2)
    E(raw, h(0x5068))                                     # str r0, [r5, r1]
    E(movs_imm, 7, LED_TRK0)                              # the other track numbers: the page's colour at their brightness
    a.label("ou_tl")
    E(cmp_reg, 7, 6)
    E(b_cond, "ou_tn", "eq")
    E(lsls_imm, 1, 7, 2)
    E(raw, h(0x5868))                                     # ldr r0, [r5, r1]
    E(ldr_sp, 1, 20)
    E(bl, "c_tmtint")
    E(lsls_imm, 1, 7, 2)
    E(raw, h(0x5068))                                     # str r0, [r5, r1]
    a.label("ou_tn")
    E(adds_imm8, 7, 1)
    E(cmp_imm, 7, LED_TRK0 + 8)
    E(b_cond, "ou_tl", "lo")
    if shiftled:
        a.label("ou_ts")
    if gran:
        ldb(0, 4, O_PAGE)
        E(cmp_imm, 0, PAGE_G)
        E(b_cond, "ou_ng", "ne")
        ldb(7, 4, O_KNOB)
        E(subs_imm8, 7, 1)                                # r7 = the shown knob (none: K1)
        E(cmp_imm, 7, 7)
        E(b_cond, "ou_g0", "ls")
        E(movs_imm, 7, 0)
        a.label("ou_g0")
        E(bl, sp["c_spshift"])
        E(str_sp, 0, 16)                                  # [sp + 16] = Shift held
        E(mov_reg, 6, 5)
        E(adds_imm8, 6, 4 * LED_KNOB0)
        for k in range(8):
            E(ldr_sp, 0, 24)
            if k >= 4:
                E(ldr_sp, 1, 16)
                E(cmp_imm, 1, 0)
                E(b_cond, f"ou_gc{k}", "eq")
                imm32(0, scl_py(SHIFT_RGB, KNOB_LVL))
                a.label(f"ou_gc{k}")
            E(cmp_imm, 7, k)
            E(b_cond, f"ou_gw{k}", "ne")
            E(ldr_sp, 0, 28)
            if k >= 4:
                E(ldr_sp, 1, 16)
                E(cmp_imm, 1, 0)
                E(b_cond, f"ou_gw{k}", "eq")
                imm32(0, SHIFT_RGB)
            a.label(f"ou_gw{k}")
            E(str_imm, 0, 6, 4 * k)
        E(b, "ou_cf")
        a.label("ou_ng")
    if fpage:
        ldb(0, 4, O_PAGE)
        E(cmp_imm, 0, PAGE_X)
        E(b_cond, "ou_nf", "ne")
        ldb(7, 4, O_KNOB)
        E(subs_imm8, 7, 1)                                # r7 = the shown knob (none or past the page's: K1)
        E(cmp_imm, 7, X_KNOBS - 1)
        E(b_cond, "ou_f0", "ls")
        E(movs_imm, 7, 0)
        a.label("ou_f0")
        E(mov_reg, 6, 5)
        E(adds_imm8, 6, 4 * LED_KNOB0)
        for k in range(8):
            if k < X_KNOBS and X_IDX[k] is not None:
                E(ldr_sp, 0, 24)
                E(cmp_imm, 7, k)
                E(b_cond, f"ou_fw{k}", "ne")
                E(ldr_sp, 0, 28)
                a.label(f"ou_fw{k}")
            else:
                E(movs_imm, 0, 0)
            E(str_imm, 0, 6, 4 * k)
        E(b, "ou_cf")
        a.label("ou_nf")
    imm32(0, CTRL + HELD)
    E(ldr_imm, 0, 0, 0)
    E(lsls_imm, 0, 0, 31 - 23)
    if fpage:                                             # Clear held: the stock's knob LEDs, but Stock+'s and pad 29's pages keep theirs
        E(b_cond, "ou_cl", "pl")
        ldb(0, 4, O_PAGE)
        E(cmp_imm, 0, PAGE_SP)
        E(b_cond, "ou_cl", "eq")
        E(cmp_imm, 0, PAGE_X)
        E(b_cond, "ou_cl", "eq")
        if filt:
            E(cmp_imm, 0, PAGE_F)
            E(b_cond, "ou_cl", "eq")
        if vol:
            E(cmp_imm, 0, PAGE_V)
            E(b_cond, "ou_cl", "eq")
        E(b, "ou_x")
        a.label("ou_cl")
    else:
        E(b_cond, "ou_x", "mi")                           # Clear held: the stock's knob LEDs
    ldb(7, 4, O_KNOB)
    E(cmp_imm, 7, 0)
    E(b_cond, "ou_k", "eq")
    E(subs_imm8, 7, 1)
    a.label("ou_k")                                       # r7 = the shown knob: the track's colour; the others the page's
    if vol:
        ldb(0, 4, O_PAGE)
        E(cmp_imm, 0, PAGE_V)
        E(b_cond, "ou_vk0", "ne")
        E(cmp_imm, 7, V_KNOBS)
        E(b_cond, "ou_vk0", "lo")
        E(movs_imm, 7, 0)                                 # the movement page with K4-K8 shown: K1
        a.label("ou_vk0")
    if scanfx:
        ldb(0, 4, O_PAGE)
        E(cmp_imm, 0, PAGE_SP)
        E(b_cond, "ou_sk0", "ne")
        E(cmp_imm, 7, SPN)
        E(b_cond, "ou_sk0", "lo")
        E(movs_imm, 7, 0)                                 # pad 27 with K7 / K8 shown: K1
        a.label("ou_sk0")
    E(movs_imm, 1, 0)
    a.label("ou_kl")
    E(str_sp, 1, 16)                                      # [sp + 16] = the knob
    if fpage and filt:
        ldb(0, 4, O_PAGE)
        E(cmp_imm, 0, PAGE_SP)
        E(b_cond, "ou_ksp", "eq")
        if vol:
            E(cmp_imm, 0, PAGE_V)
            far("ou_nvl", "ne")
            E(lsls_imm, 0, 1, 2)
            E(adds_reg, 0, 5, 0)
            E(adds_imm8, 0, 4 * LED_KNOB0)
            E(mov_reg, 6, 0)                              # r6 = its RGB word
            E(cmp_imm, 1, V_KNOBS)
            E(b_cond, "ou_vk", "lo")
            E(movs_imm, 2, 0)                             # K4-K8: dark
            E(str_imm, 2, 6, 0)
            E(b, "ou_kn")
            a.label("ou_vk")
            E(cmp_reg, 1, 7)
            far("ou_kd", "eq")
            E(movs_imm, 2, V_MAP[0])
            for k in range(1, V_KNOBS):
                E(cmp_imm, 1, k)
                E(b_cond, f"ou_vi{k}", "ne")
                E(movs_imm, 2, V_MAP[k])
                a.label(f"ou_vi{k}")
            E(b, "ou_kmx")
            a.label("ou_nvl")
        E(cmp_imm, 0, PAGE_F)
        far("ou_kd", "ne")
        if not sb:
            E(cmp_imm, 1, 6)
            far("ou_kd", "hs")                            # the filter page's K7 / K8: the stock's lights
        E(lsls_imm, 0, 1, 2)
        E(adds_reg, 0, 5, 0)
        E(adds_imm8, 0, 4 * LED_KNOB0)
        E(mov_reg, 6, 0)                                  # r6 = its RGB word
        E(bl, sp["c_spshift"])
        E(ldr_sp, 1, 16)
        E(cmp_imm, 0, 0)
        E(b_cond, "ou_fk", "eq")
        for k in FSH:
            E(cmp_imm, 1, k)
            E(b_cond, "ou_fq", "eq")
        E(b, "ou_fk")
        a.label("ou_fq")                                  # Shift held: K1 / K4 (syncbar: K7 / K8) the stock's Shift tan, full when shown
        imm32(0, COLOURS + 4 * SHIFT_BRT)
        E(ldr_imm, 0, 0, 0)
        E(cmp_reg, 1, 7)
        E(b_cond, "ou_fz", "eq")
        E(movs_imm, 1, KNOB_LVL)
        E(bl, "c_tmscl")
        a.label("ou_fz")
        E(str_imm, 0, 6, 0)
        E(b, "ou_kn")
        a.label("ou_fk")
        if sb:
            E(cmp_imm, 1, 6)
            far("ou_kd", "hs")                            # K7 / K8 without Shift: the stock's lights
        E(cmp_reg, 1, 7)
        far("ou_kd", "eq")
        E(movs_imm, 2, F_MAP[0])
        for k in range(1, 6):
            E(cmp_imm, 1, k)
            E(b_cond, f"ou_fi{k}", "ne")
            E(movs_imm, 2, F_MAP[k])
            a.label(f"ou_fi{k}")
        E(b, "ou_kmx")
        a.label("ou_ksp")
    if fpage:
        if not filt:
            ldb(0, 4, O_PAGE)
            E(cmp_imm, 0, PAGE_SP)
            E(b_cond, "ou_kd", "ne")
        E(lsls_imm, 0, 1, 2)
        E(adds_reg, 0, 5, 0)
        E(adds_imm8, 0, 4 * LED_KNOB0)                    # r0 = its RGB word
        if not shapes:
            E(cmp_imm, 1, SP_EMPTY[0])
            E(b_cond, "ou_kd", "lo")
            E(cmp_imm, 1, SP_EMPTY[-1])
            E(b_cond, "ou_ke", "hi")
            E(movs_imm, 2, 0)                             # K5 / K6: dark
            E(str_imm, 2, 0, 0)
            E(b, "ou_kn")
            a.label("ou_ke")
        if scanfx:
            E(cmp_imm, 1, SPN)
            E(b_cond, "ou_ks", "lo")
            E(movs_imm, 2, 0)                             # K7 / K8: dark
            E(str_imm, 2, 0, 0)
            E(b, "ou_kn")
            a.label("ou_ks")
        if FADETAN[0]:
            E(cmp_imm, 1, SP_RANDK - 1)
            E(b_cond, "ou_fn", "ne")
            E(mov_reg, 6, 0)
            E(bl, sp["c_spshift"])
            E(ldr_sp, 1, 16)
            E(cmp_imm, 0, 0)
            E(b_cond, "ou_fr", "eq")
            imm32(0, COLOURS + 4 * SHIFT_BRT)
            E(ldr_imm, 0, 0, 0)
            E(cmp_reg, 1, 7)
            E(b_cond, "ou_fw", "eq")                      # Shift held: K7 the stock's Shift tan, full when shown
            E(movs_imm, 1, KNOB_LVL)
            E(bl, "c_tmscl")
            a.label("ou_fw")
            E(str_imm, 0, 6, 0)
            E(b, "ou_kn")
            a.label("ou_fr")
            E(mov_reg, 0, 6)
            a.label("ou_fn")
        E(cmp_reg, 1, 7)
        E(b_cond, "ou_kd", "eq")
        E(mov_reg, 6, 0)                                  # a knob not shown: the page's colour at KNOB_LVL of the stock's brightness of its value
        if shapes:
            E(movs_imm, 2, SP_MAP[0])
            for k in range(1, 8):
                E(cmp_imm, 1, k)
                E(b_cond, f"ou_ki{k}", "ne")
                E(movs_imm, 2, SP_MAP[k])
                a.label(f"ou_ki{k}")
        else:
            for k, i in SP_OWN.items():
                E(cmp_imm, 1, k)
                E(b_cond, f"ou_ki{k}", "ne")
                E(movs_imm, 2, i)
                a.label(f"ou_ki{k}")
        if filt:
            a.label("ou_kmx")                             # r2 = the value's index
        E(mov_reg, 1, 2)
        ldb(0, 4, O_SEL)
        if DEPTHFIRST[0]:
            E(push_list, [2])
            E(bl, VAL)
            E(pop_list, [2])
            for i in MID_VALUES:
                E(cmp_imm, 2, i)
                E(b_cond, "ou_km", "eq")
            E(ldr_sp, 2, 16)
            E(b, "ou_kv")
            a.label("ou_km")
            E(ldr_sp, 2, 16)
        else:
            E(bl, VAL)
            E(ldr_sp, 2, 16)
        if DEPTHFIRST[0]:
            pass
        elif shapes:
            for k in SP_MIDK:
                E(cmp_imm, 2, k)
                E(b_cond, "ou_km", "eq")
            E(b, "ou_kv")
            a.label("ou_km")
        else:
            E(cmp_imm, 2, 7)
            E(b_cond, "ou_kv", "ne")
        E(movw, 1, 8192)                                  # K8 (the scan's speed): from the middle, as Stock+ lights it
        E(subs_reg, 0, 0, 1)
        E(b_cond, "ou_ka", "ge")
        E(raw, h(0x4240))                                 # rsbs r0, r0, #0
        a.label("ou_ka")
        E(lsls_imm, 0, 0, 1)
        a.label("ou_kv")
        E(lsrs_imm, 1, 0, 7)
        E(cmp_imm, 1, 127)
        E(b_cond, "ou_kc", "ls")
        E(movs_imm, 1, 127)
        a.label("ou_kc")
        E(movw, 2, STOCK_B[0])                            # the stock's brightness of b = 0..127: ~10 % .. 100 %
        E(muls, 1, 2)
        E(movw, 2, STOCK_B[1])
        E(adds_reg, 1, 1, 2)
        E(lsrs_imm, 1, 1, 8)
        E(movs_imm, 2, KNOB_LVL)
        E(muls, 1, 2)
        E(lsrs_imm, 1, 1, 8)
        E(ldr_sp, 0, 20)
        E(bl, "c_tmscl")
        E(str_imm, 0, 6, 0)
        E(b, "ou_kn")
        a.label("ou_kd")
    E(cmp_reg, 1, 7)
    E(b_cond, "ou_ko", "ne")
    ldb(0, 4, O_PAGE)
    E(cmp_imm, 0, 0)
    E(b_cond, "ou_kn", "eq")                              # the parameter editor: the shown knob as the stock draws it
    a.label("ou_ko")
    E(lsls_imm, 0, 1, 1)
    E(ldr_sp, 2, 12)
    E(adds_reg, 0, 0, 2)
    E(adds_imm8, 0, 2 * LED_KNOB0)
    E(ldrh_imm, 0, 0, 0)                                  # its code in the frame
    E(lsls_imm, 0, 0, 2)
    imm32(2, COLOURS)
    E(raw, h(0x5810))                                     # ldr r0, [r2, r0]
    imm32(2, RED)
    E(cmp_reg, 0, 2)
    E(b_cond, "ou_kn", "eq")                              # red (automation): the stock's light
    E(lsls_imm, 1, 1, 2)
    E(adds_reg, 6, 5, 1)
    E(adds_imm8, 6, 4 * LED_KNOB0)                        # r6 = its RGB word
    E(ldr_sp, 1, 16)
    E(cmp_reg, 1, 7)
    E(b_cond, "ou_kt", "ne")
    E(ldr_sp, 0, 28)                                      # the shown knob off the parameter editor: the track's colour at full
    if sp:
        E(cmp_imm, 1, 8 if fpage else 4)
        E(b_cond, "ou_kw", "lo")
        E(ldr_sp, 2, 32)
        E(cmp_imm, 2, 0)
        E(b_cond, "ou_kw", "eq")
        imm32(0, SHIFT_RGB)
    E(b, "ou_kw")
    a.label("ou_kt")
    E(ldr_imm, 0, 6, 0)
    E(ldr_sp, 2, 24)
    if filt and k78white:
        ldb(3, 4, O_PAGE)
        E(cmp_imm, 3, PAGE_F)
        E(b_cond, "ou_k7w", "ne")
        imm32(2, scl_py(0xFFFFFF, KNOB_LVL))              # the filter page's K7 / K8: white, as the stock's knobs
        a.label("ou_k7w")
    if sp:
        E(cmp_imm, 1, 8 if fpage else 4)
        E(b_cond, "ou_kp", "lo")
        E(ldr_sp, 3, 32)
        E(cmp_imm, 3, 0)
        E(b_cond, "ou_kp", "eq")
        imm32(2, scl_py(SHIFT_RGB, KNOB_LVL))
        a.label("ou_kp")
    E(mov_reg, 1, 2)
    E(bl, "c_tmtint")                                     # the page's colour at KNOB_LVL of the stock's brightness
    a.label("ou_kw")
    E(str_imm, 0, 6, 0)
    a.label("ou_kn")
    E(ldr_sp, 1, 16)
    E(adds_imm8, 1, 1)
    E(cmp_imm, 1, 8)
    (far("ou_kl", "lo") if shapes else E(b_cond, "ou_kl", "lo"))
    if fpage:
        a.label("ou_cf")                                  # Stock+'s and pad 29's pages: a knob Clear has done in the stock's colour
        ldb(0, 4, O_PAGE)
        E(cmp_imm, 0, PAGE_SP)
        E(b_cond, "ou_cg", "eq")
        if gran:
            E(cmp_imm, 0, PAGE_G)
            E(b_cond, "ou_cg", "eq")
        if filt:
            E(cmp_imm, 0, PAGE_F)
            E(b_cond, "ou_cg", "eq")
        if vol:
            E(cmp_imm, 0, PAGE_V)
            E(b_cond, "ou_cg", "eq")
        E(cmp_imm, 0, PAGE_X)
        E(b_cond, "ou_x", "ne")
        a.label("ou_cg")
        E(movs_imm, 7, 0)
        a.label("ou_cj")
        E(adds_reg, 3, 4, 7)
        E(movs_imm, 6, CLR_LEFT)
        ldb(0, 3, O_CLRL)
        E(cmp_imm, 0, CLR_N)
        E(b_cond, "ou_cq", "eq")
        E(movs_imm, 6, CLR_RIGHT)
        ldb(0, 3, O_CLRR)
        E(cmp_imm, 0, CLR_N)
        E(b_cond, "ou_cz", "ne")
        a.label("ou_cq")
        E(lsls_imm, 6, 6, 2)
        imm32(2, COLOURS)
        E(raw, h(0x5990))                                 # ldr r0, [r2, r6]
        E(ldr_sp, 1, 0)
        E(subs_imm8, 1, 1)                                # dimmed with the stock's LEDs, as the stock's
        E(bl, "c_tmscl")
        E(lsls_imm, 1, 7, 2)
        E(adds_reg, 1, 1, 5)
        E(adds_imm8, 1, 4 * LED_KNOB0)
        E(str_imm, 0, 1, 0)
        a.label("ou_cz")
        E(adds_imm8, 7, 1)
        E(cmp_imm, 7, 8)
        E(b_cond, "ou_cj", "lo")
    a.label("ou_x")
    E(add_sp_imm, 36)
    E(pop_list, [4, 5, 6, 7], pc=True)
    return a.assemble()


def apply_mixpage():
    """(mixpage) the mix page's eight knobs: their order, shapes, rates and the values lit from the middle (install; the tests)"""
    global V_MAP, V_KNOBS, V_SHN, V_MIDS, SB_RATES, SB_SHAPES, MID_VALUES
    V_MAP, V_KNOBS = DF_V_MAP_M, len(DF_V_MAP_M)
    V_SHN, V_MIDS = {18: 16, 21: 16}, (19, 22, 24, 25)
    SB_RATES, SB_SHAPES = SB_RATES + (22,), {**SB_SHAPES, 21: 16}
    MID_VALUES = MID_VALUES + (22, 24, 25)


def install(img, report, base_addr, stockplus=False, testpages=False, fpage=False, click=False, twoview=False, shiftled=False,
            bounce=False, pageclear=False, steadyreset=False, resetcue=False, stepmarker=False, trackpulse=False, steppage=False, softclear=False,
            viewlock=False, momhold=False, nocrush=False, gran=False, perpage=False, pagecols=False, shapes=False, shapebar=False, filtpage=False, k78white=False, volpage=False, syncbar=False, depthfirst=False, scanfx=False, pageorder=False, mixpage=False, pxrand=False, glide=False, fade=False, fclr=False, fadetan=False):
    import rh_fw
    global SP_MAP, F_MAP, V_MAP, SP_MIDK
    if depthfirst:
        assert shapes and filtpage and syncbar, "depthfirst: the Stock+ shapes page, the filter page, syncbar"
        SP_MAP, F_MAP, V_MAP = DF_SP_MAP, DF_F_MAP, DF_V_MAP
        SP_MIDK = tuple(k for k, i in enumerate(SP_MAP) if i in MID_VALUES)
        assert sorted(SP_MAP) == sorted(DF_SP_MAP) and sorted(F_MAP) == list(range(12, 18)) and sorted(V_MAP) == [18, 19, 20]
    DEPTHFIRST[0] = depthfirst
    if mixpage:
        assert depthfirst and volpage and report["fshape"].get("move") and "mixmove" in report, "mixpage: depthfirst, fshape's move, mixmove"
        apply_mixpage()
        assert sorted(V_MAP) == list(range(18, 26))
    assert not scanfx or (depthfirst and filtpage), "scanfx: the depth-first order, the filter page"
    if pxrand:
        assert scanfx and report["fshape"].get("px") and SP_MAP[SP_RANDK - 1] == 11, "pxrand: the scan on FX, fshape's px"
        SP_MAP = SP_MAP[:SP_RANDK - 1] + (RAND_V,) + SP_MAP[SP_RANDK:]
    if glide:
        assert pxrand and report["fshape"].get("glide") and SP_MAP[SP_GLIDEK - 1] == 7, "glide: pxrand, fshape's glide"
        SP_MAP = SP_MAP[:SP_GLIDEK - 1] + (GLIDE_V,) + SP_MAP[SP_GLIDEK:]
    spn = SP_GLIDEK if glide else SP_RANDK if pxrand else None
    assert not fade or (glide and report["fshape"].get("fade")), "fade: glide, fshape's fade"
    FADE[0] = fade
    assert not fadetan or fade, "fadetan: fade"
    FADETAN[0] = fadetan
    assert not fclr or (syncbar and filtpage), "fclr: the filter page with syncbar"
    FCLR[0] = fclr
    assert not pageorder or (scanfx and volpage and pageclear), "pageorder: the scan on FX, the mix page, pageclear"
    padmap = list(PADMAP_ORDER) if pageorder else None
    assert not pageorder or report["pageclear"].get("padmap") == padmap, "pageclear's pads in the same order"
    xi = list(X_SCAN if scanfx else X_FL if filtpage else X_IDX[1:] if nocrush else X_IDX)
    import rhbuild
    B = rh_fw.APP_BASE
    L = dict(c_rst=int(report["rhstate"]["labels"]["c_rst"], 16), prev_btn=rhbuild.bw_target(img, C.BTN_ENTRY),
             prev_led=rhbuild.bl_target(img, C.LED_CALLS[0]), prev_out=rhbuild.bl_target(img, OUT_CALL))
    assert all(rhbuild.bl_target(img, c) == L["prev_led"] for c in C.LED_CALLS)
    heads = {e: bytes(img[e - B:e - B + 4]) for e in (PP_ENTRY, PR_ENTRY, KN_ENTRY)}
    sp = {k: int(report["stockplus"]["labels"][k], 16) for k in ("c_spval", "c_spshift", "c_spput", "c_spdirty")} if stockplus else None
    assert not stockplus or all(report["stockplus"].get(o) for o in ("v2", "k6swap", "k8sync", "k3sync")), "Track + shows Stock+ v2's values"

    assert not stockplus or report["stockplus"].get("no_flip"), "Stock+ through stockplus_rp (its page flip removed)"
    assert stockplus or not testpages
    tests = TEST_RGB2 if pagecols else TEST_RGB[1:] if fpage else TEST_RGB
    assert not pagecols or fpage
    pages = PAGE_RGB + ((X_RGB,) if fpage else ()) + (tests if testpages else ()) if stockplus else PAGE_RGB[:1]
    sh = None
    if shapes:
        assert stockplus and fpage and "pshape" in report, "shapes: Stock+'s page with pshape"
        sh = {k: int(v, 16) for k, v in report["pshape"]["labels"].items()}
    if shapebar:
        assert shapebar in (True, "page")
        import pshape
        assert shapes and SHAPE_N == {pshape.I_ENV: pshape.NE, pshape.I_LFO: pshape.NL} and set(SP_MAP) >= {pshape.I_ENV, pshape.I_LFO}
    fl = None
    if filtpage:
        assert shapes and shapebar and testpages and pagecols and nocrush and not gran and "fshape" in report, "filtpage: pad 29 with fshape"
        fl = dict({k: int(v, 16) for k, v in report["fshape"]["labels"].items()}, defs=report["fshape"]["defs"])
    assert filtpage or not k78white
    sbl = None
    if syncbar:
        assert filtpage and "syncbar" in report and report["syncbar"]["rates"] == list(SB_RATES), "syncbar: the filter page, syncbar"
        assert {**SHAPE_N, **F_SHN, **V_SHN} == {**SB_SHAPES, 5: F_SHN[5]}
        sbl = {k: int(v, 16) for k, v in report["syncbar"]["labels"].items()}
    vo = None
    if volpage:
        assert filtpage and report["fshape"].get("vol") and len(pages) > PAGE_V, "volpage: pad 30 with fshape's vol"
        vo = dict(defs=report["fshape"]["vdefs"])
    g = None
    if gran:
        import grain_rp as GR
        assert stockplus and fpage and testpages and "grain" in report, "gran: pad 29's page, with Stock+, fpage, testpages and grain_rp"
        g = dict({k: int(v, 16) for k, v in report["grain"]["labels"].items()}, defs=GR.DEF, bip=GR.BIP)
        pages = pages[:PAGE_G] + (G_RGB,) + pages[PAGE_G + 1:]
    import stockplus as SPM
    defs = {i: v for i, v in enumerate(SPM.DEFU8) if v}   # the 12 values' defaults (0 when not listed), with stockplus_rp's LFO speeds
    for k, v in (report["stockplus"].get("lfodef", {}) if stockplus else {}).items():
        defs[int(k)] = v
    if shapes:
        defs.pop(6, None)                                 # (shapes) the LFO's shape: 0, without K7's XOR (pshape.c_shput)
    if perpage:
        import rhrec
        rhrec.check_layout()
        assert rhrec.REUSE[0] + rhrec.REUSE[1] >= PG_OFF + PG_LEN and all(o + n <= PG_OFF for o, n in rhrec.OFF54.values())
        L['c_rrt'] = int(report['rhrec']['labels']['c_rrt'], 16)
    if pageclear:
        L['pcpress'] = int(report['pageclear']['labels']['c_pcpress'], 16)
        L['pcslot'] = int(report['pageclear']['slot'], 16)
    if stepmarker:
        L['step_palette'] = int.from_bytes(img[0x0805D548 - B:0x0805D548 - B + 4], 'little')
        assert int.from_bytes(img[L['step_palette'] - B + 2:L['step_palette'] - B + 4], 'little') == 0x1B
        assert int.from_bytes(img[L['step_palette'] - B + 6:L['step_palette'] - B + 8], 'little') == 0x1A
    code, labels = arm_code(base_addr, L, heads, sp, pages, fpage, defs, click, twoview, shiftled, bounce, pageclear, steadyreset, resetcue, stepmarker, trackpulse, steppage, softclear, viewlock, momhold, xi, g, perpage, sh, shapebar, fl, k78white, vo, sbl, scanfx, padmap, spn=spn)
    img += bytes([0xFF]) * (base_addr - B - len(img)) + code
    while len(img) % 4:
        img += bytes([0xFF])
    for e, head, lab in ((PP_ENTRY, PP_HEAD, "c_tmpad"), (PR_ENTRY, PR_HEAD, "c_tmrel"), (KN_ENTRY, KN_HEAD, "c_tmknob")):
        rhbuild.patch(img, e, head, b_w(e, labels[lab]))
    rhbuild.patch(img, C.BTN_ENTRY, f"b.w #{L['prev_btn']:#x}", b_w(C.BTN_ENTRY, labels["c_tmbtn"]))
    for c in C.LED_CALLS:
        rhbuild.patch(img, c, f"bl #{L['prev_led']:#x}", bl(c, labels["c_tmled"]))
    rhbuild.patch(img, OUT_CALL, f"bl #{L['prev_out']:#x}", bl(OUT_CALL, labels["c_tmout"]))
    rhbuild.patch(img, REC_CALL, f"bl #{RECORDER:#x}", bl(REC_CALL, labels["c_tmrec"]))
    report["tmenu"] = dict(slot=hex(rhstate.ST + rhstate.OFF["tmenu"][0]), prev_btn=hex(L["prev_btn"]), prev_led=hex(L["prev_led"]),
                           prev_out=hex(L["prev_out"]), stockplus=bool(stockplus), fpage=fpage, click=click, twoview=twoview, shiftled=shiftled, bounce=bounce, pageclear=pageclear, steadyreset=steadyreset, resetcue=resetcue, stepmarker=stepmarker, trackpulse=trackpulse, steppage=steppage, softclear=softclear, viewlock=viewlock, momhold=momhold, page0=25 if pageclear else PAD_PAGE0,
                           x_idx=xi, gran=bool(gran), perpage=perpage, pagecols=pagecols, shapes=shapes, shapebar=shapebar,
                           filtpage=filtpage, k78white=k78white, volpage=volpage, syncbar=syncbar,
                           depthfirst=depthfirst, scanfx=scanfx, padmap=padmap, mixpage=mixpage, pxrand=pxrand, glide=glide, fade=fade, fclr=fclr, spn=spn, **({"fadetan": True} if fadetan else {}), maps=dict(sp=list(SP_MAP), f=list(F_MAP), v=list(V_MAP)),
                           tmclick={36: 1, 52: 2, 56: 3}.get(rhstate.OFF["tmenu"][1], 0), pages=[hex(c) for c in pages], labels={k: hex(v) for k, v in labels.items() if k.startswith("c_")})
    return labels, code
