"""The pattern mutate and its settings page on the Patterns view (MIT; Rhythm Plus, Circuit Rhythm 5706).

The stock (read in the emulator): the Patterns view (0x2004D87C, on screen when [ctrl + 0x7C] is it) has 8 columns = the tracks, 4 rows;
its pad press / release are slots 0 / 1 of its vtable 0x080678A0; Duplicate (button 24) sets bit 24 of [ctrl + 0xA0] and nothing else
with Shift held there (its LED dark); Shift + Patterns (13) = View Lock. The track advance (0x08034BDC) picks the next pattern at a
pattern end into [sp + 1] (forced [sp + 0x18] or the last [sp + 2] -> the first r8, else + 1) and reads it at 0x08034E06; [sp] = the
track, fp = 0 the play, 1 the look-ahead, [sp + 0x44] = a scene change; the chains: PARAM_GET([engine + 0x9C], t) -> first, last.
Ours:
  * Shift + Duplicate held for HOLD_MS on the Patterns view (Clear not held) opens the page; on the page a Duplicate press closes it;
    Duplicate always goes on to the stock;
  * on the page: columns 3-6 (COLS) are the settings for all tracks, a value a row, Down (19) / Up (20) = values 5-8 / 1-4; a pad picks
    its value; the track buttons switch a track's mutate on / off; Record, Play, Clear and Shift as the stock's; Shift + Patterns
    nothing (no View Lock); any other button closes the page and does its job; leaving the Patterns view closes it;
  * the lights (after the output stage): a setting column in its colour of the probability view's gradient (palette codes GRAD0 +
    column), the chosen value full, the other values DIM, no value dark; Length as a bar by Length type (Same as the chain: VDIM;
    Exact: full to the value; Random: the value full, the others DIM; randfill: HALF to it); the track buttons on full / off VDIM in
    the track's colour; the arrow to the other values white; Duplicate pulsing green (mutate: in PULSE); closed with
    Shift held, Duplicate dim Shift tan (mutate: lit while it is down).
  * (mutate) a shorter Shift + Duplicate press, the page closed: each track that is on gets a list (Length type: the chain's length,
    Length, or 1 .. Length at random; each slot a random pattern of the pool: the patterns with a hit from their first to their last
    step, or all 8); When = On the tap: the list plays from the next pattern end and loops; Every chain end: the track waits for its
    chain's end, and a new list is made when it enters a list's last slot. With Clear held: the tracks that are on lose their lists
    (clearall: every track).
    The hook at 0x08034E06 answers the list's next slot (the look-ahead the same, nothing changed; forced = slot 1); a scene change, a
    pattern pad (not with Clear or Duplicate held) end the track's list; the first pattern end after that, a pattern outside the chain
    goes to the first. Closed on the Patterns view, the track buttons of the tracks with a list soft green; (listpads) their pads:
    the pattern playing as the stock lights it, the list's other patterns the track's colour at memlvl, the rest dark (dimrest:
    restlvl, a pad to tap back to the chain) (the page:
    pagebyte, the stock's byte, and none of it for a page past 1; else read as a store, as A0099 does).
    (scenecut) a Mixer pad press or release that changes the scenes asked for ([engine + 0xA0] item 0: first, last; item 1: asked) ends every
    list at once (the Mixer's pads 17-32 = scenes 1-16, playing or stopped).
The settings in the project's record (rhrec's tail + BLK_OFF): "MT", the check byte (the sum of + 4 .. BLK_LEN - 1, XOR CHECK), 0;
+ 4 Length - 1 XOR 3 (zero = 4), + 5 Length type, + 6 Pool, + 7 When, + 8 the tracks off (bit t); + 9 + 9 t: track t's list (its
length, 0 = none, then 8 patterns); + 81 the tracks that renew (Every chain end). A block without the marks or with a wrong check byte
reads as the defaults; the first change makes it ours. The record is written with interrupts off (the sequencer writes it too).
RAM, slot "mutset": + 0 flags, + 1 the page (0 / 1), + 4 Duplicate's press (uwTick), + 8 the pads pressed on the page (bit p),
+ 12 .. 16 the settings as drawn; (mutate) + 17 the tracks whose list just ended (bit t), + 20 + t the slot playing (0xFF = before
slot 1), + 28 the random state.
Install after tmenu (its output stage) and the button chain's other heads.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import (Asm, adds_imm8, adds_reg, subs_imm8, ands_reg, b, b_cond, b_w, bics_reg, bl, cmp_imm, cmp_reg, eors_reg, h, ldr_imm, ldr_sp,  # noqa: E402
                   ldrb_imm, ldrb_reg, ldrb_w, lsls_imm, lsls_reg, lsrs_imm, lsrs_reg, mov_reg, movs_imm, movt, movw, muls, orrs_reg,
                   pop_list, push_list, raw, str_imm, str_sp, strb_imm, strb_reg, strb_w, sub_sp_imm, add_sp_imm, subs_reg, tst_reg)
import countin as C  # noqa: E402
import rhstate  # noqa: E402

PV, PV_VT = 0x2004D87C, 0x080678A0
O_VIEW, O_HELD, BIT_CLEAR = 0x7C, 0xA0, 23
ID_DUP, ID_DOWN, ID_UP, ID_PATTERNS = 24, 19, 20, 13
KEEP = (16, C.ID_PLAY, 23, 27)                            # Record, Play, Clear, Shift: the page stays open
LED_TRK0, LED_DOWN, LED_UP, LED_DUP = 32, 51, 52, 56
COLOURS = 0x20003974
TRK_SLOTS = (0x43, 0x2F, 0x47, 0x4B, 0x37, 0x25, 0x12, 0x3B)  # the tracks' palette slots (tmenu's)
GRAD0 = 0x76                                              # the probability view's 8 codes (0x0805761E: palette 0x08062AB0 + 2 (0x2D + k))
GREEN = GRAD0 + 7
PULSE = GRAD0 + 3                                         # (mutate) Duplicate on the page: column 4's colour, not the stock's green
SHIFT_DIM, SHIFT_BRT = 0x2C, 0x2B                         # the stock's tan for a button with a Shift job: dim, lit
HOLD_MS = 0x14D                                           # the stock's hold (333 ms)
DIM, HALF, VDIM, PULSE_LO, SOFT, MEMBER = 48, 128, 16, 40, 160, 112   # of 255
DUP_DIM = 80                                              # (greendup) Duplicate's green with Shift held, not pressed; of 255
O_RTIME, O_RMASK, RED_MS = 2, 18, 384                    # (pclrv) the deleted lists' red flash (as trackreset's): its start (+ 2 / + 3), its tracks
DIMW = 70                                                 # of 255: Rhythm Plus's dim white (tmenu's rest pads)
CLR_RED = 0x55                                            # the stock's red (Clear's), palette code
FRAME_PULSE = 0x0A                                        # palette word 0x0A's low byte: the stock LED frame's pulse (tmenu trackpulse)
WHITE = 0x8C8C8C                                          # the stock's lit arrow
FL_OPEN, FL_DUP, FL_HELD = 1, 2, 4
FL_HIDE = 8                                               # (hidepause) a mutate while stopped: the paused pad drawn as the list's until a play
HI = 200                                                  # the out words' offset for the buttons' LEDs (str reaches 124)
O_FL, O_PAGE, O_T0, O_PADS, O_VALS = 0, 1, 4, 8, 12
O_EXIT, O_POS, O_RNG = 17, 20, 28
SLOT_LEN, SLOT_MUT = 20, 32

COLS = (2, 3, 4, 5)                                       # Length, Length type, Pool, When
NVAL = (8, 3, 2, 2)
LEN_X = 3                                                 # Length - 1 XOR 3: a zero block = Length 4
BLK_OFF, BLK_LEN = 192, 84                                # in the record's tail (Remix's sckn / drumarp room)
MARK0, MARK1, CHECK = ord("M"), ord("T"), 0x5A
B_VAL, B_OFF, B_LISTS, B_RENEW = 4, 8, 9, 81
LIST_LEN = 9
B_VAL2, O_VAL2 = 82, 19                                   # the page 2 settings: the block's byte, its copy in the slot
AM_MASK = 3                                               # (amount) bits 0-1: Amount 0 All, 1 Most, 2 Some, 3 A little
AM_COL = 3                                                # (amount) page 2, column 4
AM_CODES = (7, 5, 3, 1)                                   # (amount) the meter's pads, top to bottom: gradient codes, GRAD0 +
NR_BIT, NR_COL = 2, 4                                     # (norep) bit 2: Repeats Off (0 = On); page 2, column 5
K1_BIT, K1_COL = 3, 5                                     # (keep1) bit 3: Keep slot 1 On (0 = Off); page 2, column 6
NR_TRIES = 16                                             # (norep) picks before a repeat is taken (a pool too small for no repeats)
BIT_DUPH = 24                                             # Duplicate held, in [ctrl + 0xA0]
ENG, PARAM_GET = 0x2003C380, 0x0803FC58
CHAINS = ENG + 0x9C
NEXT_SITE = 0x08034E06
SCMSG_VT = 0x08068B18                                     # the scene commands' handler (obj 0x2003D2FC): r1 = [obj + 0x70] save scene r2,
                                                          # [obj + 0x68] r2 = 1 paste scene [obj + 0x65] to r3, r2 = 2 clear scene r3
SCMSG_VT2 = 0x08068B24                                    # its second base's slot (0x2003D300, the Mixer's sends): r0 - 4, then the same
SC_REC = 0x40 - 0x29110                                   # scene s's record: tail + SC_REC + 40 s; its bytes + 2, + 3 of each track and + 34 .. 39 spare
SC_TOFF, SC_TLEN, SC_LEN, SC_CHECK = 748, 7, 29, 0xA5     # 7 more bytes a scene in the tail; 28 B of lists (a track: length 4 bits, 8 x 3 bits) + check
SEEK_SITE = 0x08034330                                    # the seek (0x080342E0) reads the chain's first: r8 = the track, r9 = the time in it
O_PV_SHIFT, O_PV_LOCK = 0x2C, 0x30                      # [PV + 0x2C] / [PV + 0x30]: item 0 = Shift held / View Lock on (0x0804E77C)
O_PV_PADS, PAD_LOCK = 0x44, 0x10                          # [PV + 0x44 + 4 t] -> track t's pad states (byte p); 0x10 = View Lock's white
O_PV_PAGE = 0x6C                                          # the byte [PV + 0x6C]: the Patterns view's page (0 / 1); pagebyte: read so
O_PLAYING = 0x30                                          # [engine + 0x30 + 4 t]: track t's playing store (item 0: its pattern)
O_RUN = 0x28                                              # [engine + 0x28]: item 0 = the clock running (0 = stopped)
O_SCASK = 0xA0                                            # [engine + 0xA0]: item 0 the scenes asked for (first, last), item 1 asked
MIX_VT = 0x08067918                                       # the Mixer view's vtable: slots 0 / 1 = its pad press / release
STEPS0, TRK_STRIDE, PAT_STRIDE = 0x2E4, 0x5140, 0xA28     # the patterns in the record: R + STEPS0 + TRK_STRIDE t + PAT_STRIDE p
P_LAST, P_FIRST, MAX_STEP = 0x100, 0x101, 31              # a step: 8 B, its velocity at + 3 (0 = no hit)
LCG_A, LCG_C = 1664525, 1013904223


def ldrb_sp(rt, off): return h(0xF89D) + h(rt << 12 | off)
def strb_sp(rt, off): return h(0xF88D) + h(rt << 12 | off)
CPSID, CPSIE = h(0xB672), h(0xB662)


def arm_code(base, L, randfill=False, mutate=False, listpads=False, scenecut=False, pagebyte=False, dimrest=False, clearall=False,
             liststart=False, scenesave=False, greendup=False, pageclr=False, shiftstock=False, shiftpads=False, pclrv=False,
             scenefix=False, stocktrk=False, cleardark=False, memlvl=MEMBER, clrnone=False, restlvl=VDIM, amount=False,
             norep=False, keep1=False, hidepause=False, vlock=False):
    a = Asm(base)
    E = a.emit
    SLOT = rhstate.ST + rhstate.OFF["mutset"][0]
    nfar = [0]
    inv = dict(eq="ne", ne="eq", lo="hs", hs="lo", hi="ls", ls="hi", mi="pl", pl="mi")

    def imm32(rd, v):
        E(movw, rd, v & 0xFFFF)
        E(movt, rd, (v >> 16) & 0xFFFF)

    def far(target, cond):
        nfar[0] += 1
        skip = f"msf{nfar[0]}"
        E(b_cond, skip, inv[cond])
        E(b, target)
        a.label(skip)

    def farw(target, cond):
        """far, by b.w (past 2 KB)"""
        nfar[0] += 1
        skip = f"msf{nfar[0]}"
        E(b_cond, skip, inv[cond])
        E(b_w, target)
        a.label(skip)

    def on_pv(no):
        """branch to `no` unless the Patterns view is on the screen; clobbers r0, r1"""
        imm32(0, C.CTRL)
        E(ldr_imm, 0, 0, O_VIEW)
        imm32(1, PV)
        E(cmp_reg, 0, 1)
        far(no, "ne")

    def held_clear(rd):
        """flags: ne when Clear is held; clobbers rd"""
        imm32(rd, C.CTRL + O_HELD)
        E(ldr_imm, rd, rd, 0)
        E(lsrs_imm, rd, rd, BIT_CLEAR)
        E(movs_imm, 3, 1)
        E(ands_reg, rd, 3)

    def crit_in():
        """interrupts off (the stock's own critical sections hold PRIMASK only for a few instructions, never around our calls)"""
        E(raw, CPSID)

    def crit_out():
        E(raw, CPSIE)

    # ---- c_mtsum(r0 = the block) -> r1 = its check byte; r0 kept, clobbers r2, r3
    a.label("c_mtsum")
    E(movs_imm, 1, 0)
    E(movs_imm, 2, B_VAL)
    a.label("ms_sl")
    E(ldrb_reg, 3, 0, 2)
    E(adds_reg, 1, 1, 3)
    E(adds_imm8, 2, 1)
    E(cmp_imm, 2, BLK_LEN)
    E(b_cond, "ms_sl", "lo")
    E(movs_imm, 2, 0xFF)
    E(ands_reg, 1, 2)
    E(movs_imm, 2, CHECK)
    E(eors_reg, 1, 2)
    E(raw, bytes([0x70, 0x47]))                           # bx lr

    # ---- c_mtblk() -> r0 = our block in the record when it is ours, else 0; clobbers r1-r3
    a.label("c_mtblk")
    E(push_list, [4], lr=True)
    E(bl, L["c_rrt"])
    E(cmp_imm, 0, 0)
    E(b_cond, "mk_x", "eq")
    E(adds_imm8, 0, BLK_OFF)
    E(ldrb_imm, 1, 0, 0)
    E(cmp_imm, 1, MARK0)
    E(b_cond, "mk_n", "ne")
    E(ldrb_imm, 1, 0, 1)
    E(cmp_imm, 1, MARK1)
    E(b_cond, "mk_n", "ne")
    E(bl, "c_mtsum")
    E(ldrb_imm, 2, 0, 2)
    E(cmp_reg, 1, 2)
    E(b_cond, "mk_x", "eq")
    a.label("mk_n")
    E(movs_imm, 0, 0)
    a.label("mk_x")
    E(pop_list, [4], pc=True)

    # ---- c_mtw() -> r0 = our block, made ours (zeroed, marked) when it is not, else 0 (no record); clobbers r1-r3
    a.label("c_mtw")
    E(push_list, [4], lr=True)
    E(bl, "c_mtblk")
    E(cmp_imm, 0, 0)
    E(b_cond, "mw_x", "ne")
    E(bl, L["c_rrt"])
    E(cmp_imm, 0, 0)
    E(b_cond, "mw_x", "eq")
    E(adds_imm8, 0, BLK_OFF)
    E(movs_imm, 1, 0)
    E(movs_imm, 2, 0)
    a.label("mw_z")
    E(strb_reg, 1, 0, 2)
    E(adds_imm8, 2, 1)
    E(cmp_imm, 2, BLK_LEN)
    E(b_cond, "mw_z", "lo")
    E(movs_imm, 1, MARK0)
    E(strb_imm, 1, 0, 0)
    E(movs_imm, 1, MARK1)
    E(strb_imm, 1, 0, 1)
    E(bl, "c_mtfix")
    a.label("mw_x")
    E(pop_list, [4], pc=True)

    # ---- c_mtfix(r0 = the block): its check byte again; r0 kept, clobbers r1-r3
    a.label("c_mtfix")
    E(push_list, [4], lr=True)
    E(bl, "c_mtsum")
    E(strb_imm, 1, 0, 2)
    E(pop_list, [4], pc=True)

    # ---- c_mtvals(): the settings into the slot's + 12 .. 16 (Length 0-7, Length type, Pool, When, the tracks off); clobbers r0-r3
    a.label("c_mtvals")
    E(push_list, [4], lr=True)
    imm32(4, SLOT)
    E(bl, "c_mtblk")
    E(cmp_imm, 0, 0)
    E(b_cond, "mv_d", "eq")
    for k in range(5):
        E(ldrb_imm, 1, 0, B_VAL + k)
        E(strb_imm, 1, 4, O_VALS + k)
    if amount:
        E(raw, ldrb_w(1, 0, B_VAL2))
        E(strb_imm, 1, 4, O_VAL2)
    E(b, "mv_x")
    a.label("mv_d")
    for k in range(5):
        E(strb_imm, 0, 4, O_VALS + k)
    if amount:
        E(strb_imm, 0, 4, O_VAL2)
    a.label("mv_x")
    E(ldrb_imm, 1, 4, O_VALS)
    E(movs_imm, 2, LEN_X)
    E(eors_reg, 1, 2)
    E(strb_imm, 1, 4, O_VALS)
    E(pop_list, [4], pc=True)

    if mutate:
        mutate_code(a, E, L, SLOT, imm32, far, held_clear, crit_in, crit_out, scenesave=scenesave, amount=amount, norep=norep,
                    keep1=keep1, hidepause=hidepause)
    assert mutate or not (listpads or scenecut)
    assert listpads or not (pagebyte or dimrest)
    assert mutate or not (clearall or liststart or pageclr or shiftstock)
    assert shiftstock or not shiftpads
    assert not pclrv or (shiftpads and pageclr and listpads and greendup)
    assert scenecut or not scenesave
    assert scenesave or not scenefix
    assert pclrv or not stocktrk
    assert pclrv or not cleardark
    assert 0 < restlvl < memlvl < 256
    assert pclrv or not clrnone
    assert mutate or not amount
    assert amount or not norep
    assert norep or not keep1
    assert (mutate and listpads) or not hidepause
    assert (mutate and listpads and dimrest) or not vlock
    if scenesave:
        scene_code(a, E, L, SLOT, imm32, far, crit_in, crit_out, scenefix)
    if liststart:
        # ---- c_mtseek (the seek at 0x08034330, for `ldrb r4, [r0]; ldr r0, [r5]`): r4 = the start pattern; at the chain's start
        # (Play) a track with a list starts on its slot 1; clobbers r0-r3
        a.label("c_mtseek")
        E(push_list, [6], lr=True)
        E(ldrb_imm, 4, 0, 0)
        E(mov_reg, 0, 9)
        E(cmp_imm, 0, 0)
        E(b_cond, "sk_x", "ne")
        E(mov_reg, 6, 8)
        E(cmp_imm, 6, 8)
        E(b_cond, "sk_x", "hs")
        E(bl, "c_mtblk")
        E(cmp_imm, 0, 0)
        E(b_cond, "sk_x", "eq")
        E(movs_imm, 1, LIST_LEN)
        E(muls, 1, 6)
        E(adds_reg, 0, 0, 1)
        E(ldrb_imm, 1, 0, B_LISTS)
        E(cmp_imm, 1, 0)
        E(b_cond, "sk_x", "eq")
        E(ldrb_imm, 4, 0, B_LISTS + 1)
        E(movs_imm, 1, 7)
        E(ands_reg, 4, 1)
        imm32(1, SLOT)
        E(adds_reg, 1, 1, 6)
        E(movs_imm, 2, 0)
        E(strb_imm, 2, 1, O_POS)
        a.label("sk_x")
        E(ldr_imm, 0, 5, 0)
        E(pop_list, [6], pc=True)
    if clearall:
        # ---- c_mtclall(): every track loses its list (Clear + Shift + Duplicate); clobbers r0-r3
        a.label("c_mtclall")
        E(push_list, [4], lr=True)
        E(movs_imm, 4, 0)
        a.label("mca_l")
        E(mov_reg, 0, 4)
        E(bl, "c_mtcl")
        E(adds_imm8, 4, 1)
        E(cmp_imm, 4, 8)
        E(b_cond, "mca_l", "lo")
        E(pop_list, [4], pc=True)
    if scenecut:
        # ---- c_mxsig() -> r0 = the scenes asked for: first | last << 8 | asked << 16; clobbers r1-r3
        a.label("c_mxsig")
        E(push_list, [4], lr=True)
        imm32(0, ENG + O_SCASK)
        E(ldr_imm, 0, 0, 0)
        E(movs_imm, 1, 0)
        E(bl, PARAM_GET)
        E(ldrb_imm, 4, 0, 0)
        E(ldrb_imm, 1, 0, 1)
        E(lsls_imm, 1, 1, 8)
        E(orrs_reg, 4, 1)
        imm32(0, ENG + O_SCASK)
        E(ldr_imm, 0, 0, 0)
        E(movs_imm, 1, 1)
        E(bl, PARAM_GET)
        E(ldrb_imm, 0, 0, 0)
        E(lsls_imm, 0, 0, 16)
        E(orrs_reg, 0, 4)
        E(pop_list, [4], pc=True)

        # ---- c_mxpad / c_mxpr (the Mixer's slots 0 / 1: r0 = view, r1 = pad, r2 = velocity): the stock's, then a new scene asked for
        #      (the stock asks at the release) ends the lists
        for name, prev in (("c_mxpad", "prev_mix"), ("c_mxpr", "prev_mixr")):
            a.label(name)
            E(push_list, [3, 4, 5, 6, 7], lr=True)
            E(mov_reg, 4, 0)
            E(mov_reg, 5, 1)
            E(mov_reg, 6, 2)
            E(bl, "c_mxsig")
            E(mov_reg, 7, 0)
            E(mov_reg, 0, 4)
            E(mov_reg, 1, 5)
            E(mov_reg, 2, 6)
            E(bl, L[prev])
            E(mov_reg, 4, 0)
            E(bl, "c_mxsig")
            E(cmp_reg, 0, 7)
            E(b_cond, f"{name}_x", "eq")
            E(lsrs_imm, 1, 0, 16)
            E(b_cond, f"{name}_c", "ne")                  # a scene asked for
            E(eors_reg, 0, 7)
            E(lsls_imm, 0, 0, 16)
            E(b_cond, f"{name}_x", "eq")                  # only the asked flag fell
            a.label(f"{name}_c")
            if scenesave:                                 # stopped: the asked scene's lists now (playing: at its start)
                imm32(0, ENG + O_RUN)
                E(ldr_imm, 0, 0, 0)
                E(movs_imm, 1, 0)
                E(bl, PARAM_GET)
                E(ldrb_imm, 0, 0, 0)
                E(cmp_imm, 0, 0)
                E(b_cond, f"{name}_cl", "ne")
                E(bl, "c_mxsig")
                E(lsls_imm, 7, 0, 24)
                E(lsrs_imm, 7, 7, 24)
                E(movs_imm, 5, 0)
                a.label(f"{name}_ld")
                E(mov_reg, 0, 7)
                E(mov_reg, 1, 5)
                E(movs_imm, 2, 0)
                E(bl, "c_scget")
                E(adds_imm8, 5, 1)
                E(cmp_imm, 5, 8)
                E(b_cond, f"{name}_ld", "lo")
                E(b, f"{name}_x")
                a.label(f"{name}_cl")
            E(movs_imm, 5, 0)
            a.label(f"{name}_l")
            E(mov_reg, 0, 5)
            E(bl, "c_mtcl")
            E(adds_imm8, 5, 1)
            E(cmp_imm, 5, 8)
            E(b_cond, f"{name}_l", "lo")
            a.label(f"{name}_x")
            E(mov_reg, 0, 4)
            E(pop_list, [3, 4, 5, 6, 7], pc=True)

    # ---- c_msbtn (a head of the button chain: r0 = ctrl, r1 = id)
    a.label("c_msbtn")
    E(push_list, [0, 1, 2, 3, 4], lr=True)
    E(bl, L["c_ciok"])
    E(cmp_imm, 0, 0)
    far("mb_go", "eq")
    on_pv("mb_go")
    imm32(4, SLOT)
    E(ldr_sp, 1, 4)
    E(ldrb_imm, 0, 4, O_FL)
    E(cmp_imm, 1, ID_DUP)
    E(b_cond, "mb_nd", "ne")
    E(lsls_imm, 2, 0, 31)
    E(b_cond, "mb_dc", "pl")
    E(movs_imm, 1, FL_OPEN)                               # Duplicate on the page: it closes; its release does nothing
    E(bics_reg, 0, 1)
    E(movs_imm, 1, FL_DUP | FL_HELD)
    E(orrs_reg, 0, 1)
    E(strb_imm, 0, 4, O_FL)
    E(b, "mb_go")
    a.label("mb_dc")
    E(bl, L["c_cishift"])
    E(cmp_imm, 0, 0)
    far("mb_go", "eq")                                    # Duplicate without Shift: the stock's only
    imm32(0, C.HAL_TICK)
    E(ldr_imm, 0, 0, 0)
    E(str_imm, 0, 4, O_T0)
    E(ldrb_imm, 0, 4, O_FL)
    E(movs_imm, 1, FL_HELD)
    E(bics_reg, 0, 1)
    E(movs_imm, 1, FL_DUP)
    E(orrs_reg, 0, 1)
    E(strb_imm, 0, 4, O_FL)
    E(b, "mb_go")
    a.label("mb_nd")
    E(lsls_imm, 2, 0, 31)
    if pclrv:
        E(b_cond, "mb_op", "mi")
        E(cmp_imm, 1, 8)                                  # closed: Clear + the button of a track with a list ends the list
        far("mb_go", "hs")
        held_clear(2)
        far("mb_go", "eq")
        nolist = "mb_sw" if clrnone else "mb_go"          # clrnone: Clear + a track with no list does nothing
        E(bl, "c_mtblk")
        E(cmp_imm, 0, 0)
        far(nolist, "eq")
        E(ldr_sp, 1, 4)
        E(movs_imm, 2, LIST_LEN)
        E(muls, 2, 1)
        E(adds_reg, 2, 2, 0)
        E(ldrb_imm, 2, 2, B_LISTS)
        E(cmp_imm, 2, 0)
        far(nolist, "eq")
        E(mov_reg, 0, 1)
        E(bl, "c_mtcl")
        E(ldr_sp, 1, 4)
        E(movs_imm, 0, 1)
        E(lsls_reg, 0, 1)
        E(bl, "c_msmark")
        E(b, "mb_sw")
        a.label("mb_op")
    else:
        far("mb_go", "pl")                                # the page closed
    E(cmp_imm, 1, 8)
    E(b_cond, "mb_trk", "lo")
    E(movs_imm, 2, 1)
    E(cmp_imm, 1, ID_DOWN)
    E(b_cond, "mb_pg", "eq")
    E(movs_imm, 2, 0)
    E(cmp_imm, 1, ID_UP)
    E(b_cond, "mb_pg", "eq")
    for k in KEEP:
        E(cmp_imm, 1, k)
        far("mb_go", "eq")
    E(cmp_imm, 1, ID_PATTERNS)
    E(b_cond, "mb_cl", "ne")
    E(bl, L["c_cishift"])
    E(cmp_imm, 0, 0)
    E(b_cond, "mb_sw", "ne")                              # Shift + Patterns: no View Lock here
    E(ldrb_imm, 0, 4, O_FL)
    a.label("mb_cl")
    E(movs_imm, 1, FL_OPEN)                               # another button: the page closes, the button does its job
    E(bics_reg, 0, 1)
    E(strb_imm, 0, 4, O_FL)
    E(b, "mb_go")
    a.label("mb_trk")
    if pageclr:                                           # Clear + a track button: that track's list ends (its on / off kept)
        held_clear(0)
        E(b_cond, "mb_tg", "eq")
        E(mov_reg, 0, 1)
        E(bl, "c_mtcl")
        if pclrv:
            E(ldr_sp, 1, 4)
            E(movs_imm, 0, 1)
            E(lsls_reg, 0, 1)
            E(bl, "c_msmark")
        E(b, "mb_sw")
        a.label("mb_tg")
    if mutate:
        E(movs_imm, 3, 1)
        E(lsls_reg, 3, 1)
        E(movs_imm, 0, B_OFF)
        E(movs_imm, 1, 0)
        E(movs_imm, 2, 0)
        E(bl, "c_mtbits")
    else:
        E(bl, "c_mtw")
        E(cmp_imm, 0, 0)
        E(b_cond, "mb_sw", "eq")
        E(ldr_sp, 1, 4)
        E(movs_imm, 2, 1)
        E(lsls_reg, 2, 1)
        E(ldrb_imm, 3, 0, B_OFF)
        E(eors_reg, 3, 2)
        E(strb_imm, 3, 0, B_OFF)
        E(bl, "c_mtfix")
    E(b, "mb_sw")
    a.label("mb_pg")
    E(strb_imm, 2, 4, O_PAGE)
    a.label("mb_sw")
    E(pop_list, [0, 1, 2, 3, 4], pc=True)
    a.label("mb_go")
    E(raw, C.popw([0, 1, 2, 3, 4], lr=True))
    E(b_w, L["prev_btn"])

    # ---- c_msrel (a head of the button release: r0 = ctrl, r1 = id): Duplicate's release ends its press; the page's buttons swallowed
    a.label("c_msrel")
    E(push_list, [0, 1, 2, 3, 4], lr=True)
    E(bl, L["c_ciok"])
    E(cmp_imm, 0, 0)
    E(b_cond, "mr_go", "eq")
    imm32(4, SLOT)
    E(ldr_sp, 1, 4)
    E(ldrb_imm, 0, 4, O_FL)
    E(cmp_imm, 1, ID_DUP)
    E(b_cond, "mr_nd", "ne")
    if mutate:
        E(movs_imm, 2, FL_OPEN | FL_DUP | FL_HELD)
        E(ands_reg, 2, 0)
        E(cmp_imm, 2, FL_DUP)
        E(b_cond, "mr_dc", "ne")
        held_clear(2)                                     # a shorter Shift + Duplicate press, the page closed
        E(b_cond, "mr_mu", "eq")
        E(bl, "c_mtclred" if pclrv else "c_mtclall" if clearall else "c_mtclon")
        E(b, "mr_dr")
        a.label("mr_mu")
        E(bl, "c_mtdo")
        a.label("mr_dr")
        E(ldrb_imm, 0, 4, O_FL)
        a.label("mr_dc")
    E(movs_imm, 2, FL_DUP | FL_HELD)
    E(bics_reg, 0, 2)
    E(strb_imm, 0, 4, O_FL)
    E(b, "mr_go")
    a.label("mr_nd")
    E(lsls_imm, 2, 0, 31)
    E(b_cond, "mr_go", "pl")
    E(cmp_imm, 1, 8)
    E(b_cond, "mr_sw", "lo")
    E(cmp_imm, 1, ID_DOWN)
    E(b_cond, "mr_sw", "eq")
    E(cmp_imm, 1, ID_UP)
    E(b_cond, "mr_go", "ne")
    a.label("mr_sw")
    E(pop_list, [0, 1, 2, 3, 4], pc=True)
    a.label("mr_go")
    E(raw, C.popw([0, 1, 2, 3, 4], lr=True))
    E(b_w, L["prev_rel"])

    # ---- c_mspad (the Patterns view's slot 0: r0 = view, r1 = pad, r2 = velocity): on the page, a setting's pad picks its value
    a.label("c_mspad")
    E(push_list, [4, 5, 6, 7], lr=True)
    imm32(4, SLOT)
    E(ldrb_imm, 3, 4, O_FL)
    E(lsls_imm, 3, 3, 31)
    far("mp_cl" if mutate else "mp_st", "pl")
    E(cmp_imm, 1, 32)
    far("mp_st", "hs")
    E(ldr_imm, 2, 4, O_PADS)
    E(movs_imm, 3, 1)
    E(lsls_reg, 3, 1)
    E(orrs_reg, 2, 3)
    E(str_imm, 2, 4, O_PADS)
    if pclrv:                                             # Clear held (the mutate's preview): the pad does nothing
        held_clear(2)
        far("mp_x", "ne")
    E(movs_imm, 5, 7)
    E(ands_reg, 5, 1)                                     # r5 = the column
    E(lsrs_imm, 6, 1, 3)
    E(ldrb_imm, 2, 4, O_PAGE)
    E(lsls_imm, 2, 2, 2)
    E(orrs_reg, 6, 2)                                     # r6 = the value
    if amount:                                            # page 2, column 4: Amount (the row)
        E(ldrb_imm, 2, 4, O_PAGE)
        E(cmp_imm, 2, 0)
        E(b_cond, "mp_p1", "eq")
        E(cmp_imm, 5, AM_COL)
        E(b_cond, "mp_p1", "ne")
        E(movs_imm, 0, B_VAL2)
        E(movs_imm, 1, AM_MASK)
        E(movs_imm, 2, 3)
        E(ands_reg, 2, 6)
        E(movs_imm, 3, 0)
        E(bl, "c_mtbits")
        E(b, "mp_x")
        a.label("mp_p1")
    if norep:                                             # page 2, column 5: Repeats (row 1 On, row 2 Off)
        E(ldrb_imm, 2, 4, O_PAGE)
        E(cmp_imm, 2, 0)
        E(b_cond, "mp_q1", "eq")
        E(cmp_imm, 5, NR_COL)
        E(b_cond, "mp_q1", "ne")
        E(movs_imm, 2, 3)
        E(ands_reg, 6, 2)
        E(cmp_imm, 6, 2)
        E(b_cond, "mp_x", "hs")
        E(movs_imm, 0, B_VAL2)
        E(movs_imm, 1, 1 << NR_BIT)
        E(lsls_imm, 2, 6, NR_BIT)
        E(movs_imm, 3, 0)
        E(bl, "c_mtbits")
        E(b, "mp_x")
        a.label("mp_q1")
    if keep1:                                             # page 2, column 6: Keep slot 1 (row 1 Off, row 2 On)
        E(ldrb_imm, 2, 4, O_PAGE)
        E(cmp_imm, 2, 0)
        E(b_cond, "mp_k1", "eq")
        E(cmp_imm, 5, K1_COL)
        E(b_cond, "mp_k1", "ne")
        E(movs_imm, 2, 3)
        E(ands_reg, 6, 2)
        E(cmp_imm, 6, 2)
        E(b_cond, "mp_x", "hs")
        E(movs_imm, 0, B_VAL2)
        E(movs_imm, 1, 1 << K1_BIT)
        E(lsls_imm, 2, 6, K1_BIT)
        E(movs_imm, 3, 0)
        E(bl, "c_mtbits")
        E(b, "mp_x")
        a.label("mp_k1")
    for k, (c, n) in enumerate(zip(COLS, NVAL)):
        E(cmp_imm, 5, c)
        E(b_cond, f"mp_c{k}", "ne")
        E(cmp_imm, 6, n)
        E(b_cond, "mp_x", "hs")
        E(movs_imm, 7, B_VAL + k)
        if k == 0:
            E(movs_imm, 2, LEN_X)
            E(eors_reg, 6, 2)
        E(b, "mp_w")
        a.label(f"mp_c{k}")
    E(b, "mp_x")
    a.label("mp_w")
    if mutate:
        E(mov_reg, 0, 7)
        E(movs_imm, 1, 0xFF)
        E(mov_reg, 2, 6)
        E(movs_imm, 3, 0)
        E(bl, "c_mtbits")
    else:
        E(bl, "c_mtw")
        E(cmp_imm, 0, 0)
        E(b_cond, "mp_x", "eq")
        E(strb_reg, 6, 0, 7)
        E(bl, "c_mtfix")
    a.label("mp_x")
    E(pop_list, [4, 5, 6, 7], pc=True)
    if mutate:
        a.label("mp_cl")                                  # the page closed: a pattern pad ends its track's list
        E(cmp_imm, 1, 32)
        E(b_cond, "mp_st", "hs")
        E(mov_reg, 5, 0)
        E(mov_reg, 6, 1)
        E(mov_reg, 7, 2)
        imm32(0, C.CTRL + O_HELD)
        E(ldr_imm, 0, 0, 0)
        E(lsrs_imm, 0, 0, BIT_CLEAR)
        E(movs_imm, 3, 1 | 1 << (BIT_DUPH - BIT_CLEAR))
        E(tst_reg, 0, 3)
        E(b_cond, "mp_rs", "ne")                          # Clear + pad, Duplicate + pad: the stock's, the list kept
        if vlock:                                         # View Lock + Shift + pad: the stock's view pick, the list kept
            imm32(0, PV + O_PV_LOCK)
            E(ldr_imm, 0, 0, 0)
            E(movs_imm, 1, 0)
            E(bl, PARAM_GET)
            E(ldrb_imm, 0, 0, 0)
            E(cmp_imm, 0, 0)
            E(b_cond, "mp_vl", "eq")
            imm32(0, PV + O_PV_SHIFT)
            E(ldr_imm, 0, 0, 0)
            E(movs_imm, 1, 0)
            E(bl, PARAM_GET)
            E(ldrb_imm, 0, 0, 0)
            E(cmp_imm, 0, 0)
            E(b_cond, "mp_rs", "ne")
            a.label("mp_vl")
        E(movs_imm, 0, 7)
        E(ands_reg, 0, 6)
        E(bl, "c_mtcl")
        a.label("mp_rs")
        E(mov_reg, 0, 5)
        E(mov_reg, 1, 6)
        E(mov_reg, 2, 7)
    a.label("mp_st")
    E(raw, C.popw([4, 5, 6, 7], lr=True))
    E(b_w, L["prev_pad"])

    # ---- c_mspr (slot 1: r0 = view, r1 = pad): a pad pressed on the page: its release swallowed
    a.label("c_mspr")
    E(push_list, [4], lr=True)
    imm32(4, SLOT)
    E(cmp_imm, 1, 32)
    E(b_cond, "mq_st", "hs")
    E(ldr_imm, 2, 4, O_PADS)
    E(movs_imm, 3, 1)
    E(lsls_reg, 3, 1)
    E(tst_reg, 2, 3)
    E(b_cond, "mq_st", "eq")
    E(bics_reg, 2, 3)
    E(str_imm, 2, 4, O_PADS)
    E(pop_list, [4], pc=True)
    a.label("mq_st")
    E(raw, C.popw([4], lr=True))
    E(b_w, L["prev_pr"])

    # ---- c_msout (the LED task's output stage: r0 = ctrl, r1 = out RGB words, r2 = frame): the chain, then the hold and the page
    a.label("c_msout")
    E(push_list, [3, 4, 5, 6, 7], lr=True)
    E(mov_reg, 5, 1)
    E(bl, L["prev_out"])
    E(bl, L["c_ciok"])
    E(cmp_imm, 0, 0)
    far("mo_x", "eq")
    imm32(4, SLOT)
    on_pv("mo_off")
    E(ldrb_imm, 0, 4, O_FL)
    E(movs_imm, 1, FL_DUP | FL_HELD)
    E(ands_reg, 1, 0)
    E(cmp_imm, 1, FL_DUP)
    E(b_cond, "mo_nh", "ne")
    held_clear(1)
    E(b_cond, "mo_nh", "ne")                              # Clear + Shift + Duplicate: never the page
    imm32(1, C.HAL_TICK)
    E(ldr_imm, 1, 1, 0)
    E(ldr_imm, 2, 4, O_T0)
    E(subs_reg, 1, 1, 2)
    E(movw, 2, HOLD_MS)
    E(cmp_reg, 1, 2)
    E(b_cond, "mo_nh", "lo")
    E(movs_imm, 1, FL_OPEN | FL_HELD)                     # held: the page opens
    E(orrs_reg, 0, 1)
    E(strb_imm, 0, 4, O_FL)
    E(movs_imm, 1, 0)
    E(strb_imm, 1, 4, O_PAGE)
    a.label("mo_nh")
    E(ldrb_imm, 0, 4, O_FL)
    E(lsls_imm, 0, 0, 31)
    E(b_cond, "mo_pg", "mi")
    if shiftstock:                                        # Shift held: the stock's track buttons (shiftpads: the list pads kept); Duplicate ours
        E(bl, L["c_cishift"])
        E(cmp_imm, 0, 0)
        E(b_cond, "mo_sh", "ne")
        if not stocktrk:                                  # stocktrk: the stock's track buttons; the lists' green only with Clear held
            E(bl, "c_msgreen")
        if listpads:
            E(bl, "c_mslist")
        if pclrv:
            held_clear(0)
            far("mo_x", "eq")
            E(bl, "c_mscltb")
        E(b, "mo_x")
        a.label("mo_sh")
        if shiftpads and listpads:
            E(bl, "c_mslist")
        if pclrv:
            held_clear(0)
            E(b_cond, "mo_sd", "eq")
            E(bl, "c_mscltb")
            a.label("mo_sd")
    else:
        if mutate:
            E(bl, "c_msgreen")
        if listpads:
            E(bl, "c_mslist")
        E(bl, L["c_cishift"])
        E(cmp_imm, 0, 0)
        E(b_cond, "mo_x", "eq")
    if greendup:                                          # closed, Shift held: Duplicate green, dim; down, full
        if pclrv:                                         # Clear held too: red (a tap ends every list)
            held_clear(0)
            E(b_cond, "mo_gr", "eq")
            imm32(0, COLOURS + 4 * CLR_RED)
            E(ldr_imm, 0, 0, 0)
            E(b, "mo_dl")
            a.label("mo_gr")
        imm32(0, COLOURS + 4 * GREEN)
        E(ldr_imm, 7, 0, 0)
        E(mov_reg, 0, 7)
        E(ldrb_imm, 1, 4, O_FL)
        E(lsls_imm, 1, 1, 31 - 1)                         # mi: FL_DUP, Shift + Duplicate down
        E(b_cond, "mo_dl", "mi")
        E(movs_imm, 1, DUP_DIM)
        E(bl, L["c_tmscl"])
        a.label("mo_dl")
    else:
        if mutate:
            E(ldrb_imm, 1, 4, O_FL)
            E(lsls_imm, 1, 1, 31 - 1)                     # mi: FL_DUP, Shift + Duplicate down
            imm32(0, COLOURS + 4 * SHIFT_BRT)
            E(b_cond, "mo_dl", "mi")
        imm32(0, COLOURS + 4 * SHIFT_DIM)                 # closed, Shift held: Duplicate has a Shift job here
        if mutate:
            a.label("mo_dl")
        E(ldr_imm, 0, 0, 0)
    E(mov_reg, 1, 5)
    E(adds_imm8, 1, HI)
    E(str_imm, 0, 1, 4 * LED_DUP - HI)
    E(b, "mo_x")
    a.label("mo_off")                                     # off the Patterns view: the page closed
    E(ldrb_imm, 0, 4, O_FL)
    E(movs_imm, 1, FL_OPEN)
    E(bics_reg, 0, 1)
    E(strb_imm, 0, 4, O_FL)
    E(b, "mo_x")
    a.label("mo_pg")
    if pclrv:                                             # the page, Clear held: the Patterns view with the lists (the preview)
        held_clear(0)
        E(b_cond, "mo_pd", "eq")
        E(bl, "c_mslist")
        E(bl, "c_mscltb")
        imm32(0, COLOURS + 4 * GREEN)                     # Duplicate: the page's green pulse (still on the page)
        E(ldr_imm, 7, 0, 0)
        E(mov_reg, 0, 7)
        imm32(1, C.CTRL + O_HELD)
        E(ldr_imm, 1, 1, 0)
        E(lsrs_imm, 1, 1, BIT_DUPH + 1)
        E(b_cond, "mo_pw", "cs")
        imm32(2, COLOURS + 4 * FRAME_PULSE)
        E(ldrb_imm, 2, 2, 0)
        E(movw, 1, 255)
        E(subs_reg, 1, 1, 2)
        E(movs_imm, 2, 192)
        E(muls, 1, 2)
        E(lsrs_imm, 1, 1, 8)
        E(adds_imm8, 1, 64)
        E(bl, L["c_tmscl"])
        a.label("mo_pw")
        E(mov_reg, 1, 5)
        E(adds_imm8, 1, HI)
        E(str_imm, 0, 1, 4 * LED_DUP - HI)
        E(b, "mo_x")
        a.label("mo_pd")
    E(bl, "c_msdraw")
    a.label("mo_x")
    if pclrv:
        on_pv("mo_xx")
        E(bl, "c_msred")
        a.label("mo_xx")
    E(pop_list, [3, 4, 5, 6, 7], pc=True)

    if pclrv:
        # ---- c_msmark(r0 = tracks, bit t): their lists just deleted, their buttons red for RED_MS; clobbers r0-r3
        a.label("c_msmark")
        E(push_list, [4], lr=True)
        imm32(3, SLOT)
        E(ldrb_imm, 1, 3, O_RMASK)
        E(orrs_reg, 1, 0)
        E(strb_imm, 1, 3, O_RMASK)
        imm32(1, C.HAL_TICK)
        E(ldr_imm, 1, 1, 0)
        E(strb_imm, 1, 3, O_RTIME)
        E(lsrs_imm, 1, 1, 8)
        E(strb_imm, 1, 3, O_RTIME + 1)
        E(pop_list, [4], pc=True)

        # ---- c_msred (r5 = the out RGB words): the buttons of the tracks just deleted red; clobbers r0-r3
        a.label("c_msred")
        E(push_list, [4], lr=True)
        imm32(4, SLOT)
        E(ldrb_imm, 0, 4, O_RMASK)
        E(cmp_imm, 0, 0)
        E(b_cond, "mr2_x", "eq")
        imm32(1, C.HAL_TICK)
        E(ldr_imm, 1, 1, 0)
        E(ldrb_imm, 2, 4, O_RTIME)
        E(ldrb_imm, 3, 4, O_RTIME + 1)
        E(lsls_imm, 3, 3, 8)
        E(orrs_reg, 2, 3)
        E(subs_reg, 1, 1, 2)
        E(lsls_imm, 1, 1, 16)
        E(lsrs_imm, 1, 1, 16)
        E(movw, 2, RED_MS)
        E(cmp_reg, 1, 2)
        E(b_cond, "mr2_on", "lo")
        E(movs_imm, 0, 0)
        E(strb_imm, 0, 4, O_RMASK)
        E(b, "mr2_x")
        a.label("mr2_on")
        E(lsls_imm, 3, 1, 25)                             # bit 6 of the time: dark (a 64 ms flash)
        imm32(1, COLOURS + 4 * CLR_RED)
        E(ldr_imm, 1, 1, 0)
        E(cmp_imm, 3, 0)
        E(b_cond, "mr2_d", "pl")
        E(movs_imm, 1, 0)
        a.label("mr2_d")
        E(mov_reg, 2, 5)
        E(adds_imm8, 2, 4 * LED_TRK0)
        for t in range(8):
            E(movs_imm, 3, 1 << t)
            E(tst_reg, 0, 3)
            E(b_cond, f"mr2_{t}", "eq")
            E(str_imm, 1, 2, 4 * t)
            a.label(f"mr2_{t}")
        a.label("mr2_x")
        E(pop_list, [4], pc=True)

        # ---- c_mtclred(): every list ends (Clear + Shift + Duplicate), the tracks that had one red; clobbers r0-r3
        a.label("c_mtclred")
        E(push_list, [4], lr=True)
        E(movs_imm, 4, 0)
        E(bl, "c_mtblk")
        E(cmp_imm, 0, 0)
        E(b_cond, "mcr_c", "eq")
        for t in range(8):
            E(raw, ldrb_w(1, 0, B_LISTS + LIST_LEN * t))
            E(cmp_imm, 1, 0)
            E(b_cond, f"mcr_{t}", "eq")
            E(movs_imm, 1, 1 << t)
            E(orrs_reg, 4, 1)
            a.label(f"mcr_{t}")
        a.label("mcr_c")
        E(bl, "c_mtclall")
        E(mov_reg, 0, 4)
        E(bl, "c_msmark")
        E(pop_list, [4], pc=True)

        # ---- c_mscltb (r5 = the out RGB words): Clear held, the track buttons of the tracks with a list green, the others dim white
        #      (cleardark: dark); clobbers r0-r3, r6, r7
        a.label("c_mscltb")
        E(push_list, [4], lr=True)
        if cleardark:
            E(movs_imm, 4, 0)
        else:
            imm32(0, 0xFFFFFF)
            E(movs_imm, 1, DIMW)
            E(bl, L["c_tmscl"])
            E(mov_reg, 4, 0)
        E(bl, "c_mtblk")
        E(mov_reg, 6, 0)
        imm32(0, COLOURS + 4 * GREEN)
        E(ldr_imm, 7, 0, 0)
        E(mov_reg, 2, 5)
        E(adds_imm8, 2, 4 * LED_TRK0)
        for t in range(8):
            E(mov_reg, 1, 4)
            E(cmp_imm, 6, 0)
            E(b_cond, f"mt_c{t}", "eq")
            E(raw, ldrb_w(0, 6, B_LISTS + LIST_LEN * t))
            E(cmp_imm, 0, 0)
            E(b_cond, f"mt_c{t}", "eq")
            E(mov_reg, 1, 7)
            a.label(f"mt_c{t}")
            E(str_imm, 1, 2, 4 * t)
        E(pop_list, [4], pc=True)

    def scl(lvl):
        """r0 = r7 at lvl of 255; clobbers r1-r3"""
        E(mov_reg, 0, 7)
        E(movs_imm, 1, lvl)
        E(bl, L["c_tmscl"])

    if mutate:
        # ---- c_msgreen (r5 = the out RGB words): the track buttons of the tracks with a list soft green; clobbers r0-r3, r6, r7
        a.label("c_msgreen")
        E(push_list, [3], lr=True)
        E(bl, "c_mtblk")
        E(cmp_imm, 0, 0)
        E(b_cond, "mg_x", "eq")
        E(mov_reg, 6, 0)
        imm32(0, COLOURS + 4 * GREEN)
        E(ldr_imm, 7, 0, 0)
        scl(SOFT)
        E(mov_reg, 7, 0)
        E(mov_reg, 2, 5)
        E(adds_imm8, 2, 4 * LED_TRK0)
        for t in range(8):
            E(raw, ldrb_w(0, 6, B_LISTS + LIST_LEN * t))
            E(cmp_imm, 0, 0)
            E(b_cond, f"mg_{t}", "eq")
            E(str_imm, 7, 2, 4 * t)
            a.label(f"mg_{t}")
        a.label("mg_x")
        E(pop_list, [3], pc=True)

    if listpads:
        # ---- c_mslist (r5 = the out RGB words): the pads of the tracks with a list; r4 kept, clobbers r0-r3, r6, r7
        a.label("c_mslist")
        if dimrest:                                       # [sp] = the page's first pattern, [sp + 4] = the list's patterns (bit p),
            E(push_list, [0, 1, 2, 3, 4], lr=True)        # [sp + 8] = the colour of the pads not in the list
        else:
            E(push_list, [2, 3, 4], lr=True)
        if vlock:                                         # [sp + 12] = View Lock on (r3 is not kept)
            imm32(0, PV + O_PV_LOCK)
            E(ldr_imm, 0, 0, 0)
            E(movs_imm, 1, 0)
            E(bl, PARAM_GET)
            E(ldrb_imm, 0, 0, 0)
            E(str_sp, 0, 12)
        if hidepause:                                     # the clock running: the paused pads back (FL_HIDE ends)
            imm32(0, ENG + O_RUN)
            E(ldr_imm, 0, 0, 0)
            E(movs_imm, 1, 0)
            E(bl, PARAM_GET)
            E(ldrb_imm, 0, 0, 0)
            E(cmp_imm, 0, 0)
            E(b_cond, "ml2_h", "eq")
            imm32(1, SLOT)
            E(ldrb_imm, 0, 1, O_FL)
            E(movs_imm, 2, FL_HIDE)
            E(bics_reg, 0, 2)
            E(strb_imm, 0, 1, O_FL)
            a.label("ml2_h")
        E(bl, "c_mtblk")
        E(cmp_imm, 0, 0)
        (farw if vlock else far)("ml2_x", "eq")
        E(mov_reg, 6, 0)
        imm32(0, PV + O_PV_PAGE)
        if pagebyte:
            E(ldrb_imm, 0, 0, 0)
            E(cmp_imm, 0, 1)
            (farw if vlock else far)("ml2_x", "hi")
        else:
            E(ldr_imm, 0, 0, 0)
            E(movs_imm, 1, 0)
            E(bl, PARAM_GET)
            E(ldrb_imm, 0, 0, 0)
        E(lsls_imm, 0, 0, 2)
        E(str_sp, 0, 0)
        for t in range(8):
            o = B_LISTS + LIST_LEN * t
            E(raw, ldrb_w(0, 6, o))
            E(cmp_imm, 0, 0)
            far(f"ml2_n{t}", "eq")
            E(mov_reg, 4, 6)
            E(adds_imm8, 4, o)
            E(movs_imm, 1, 0)
            a.label(f"ml2_m{t}")
            E(ldrb_reg, 3, 4, 0)
            E(movs_imm, 2, 1)
            E(lsls_reg, 2, 3)
            E(orrs_reg, 1, 2)
            E(subs_imm8, 0, 1)
            E(b_cond, f"ml2_m{t}", "ne")
            E(str_sp, 1, 4)
            imm32(0, ENG + O_PLAYING + 4 * t)
            E(ldr_imm, 0, 0, 0)
            E(movs_imm, 1, 0)
            E(bl, PARAM_GET)
            E(ldrb_imm, 4, 0, 0)                          # r4 = the pattern playing
            if hidepause:                                 # FL_HIDE: none (the paused pad drawn as the list's)
                imm32(0, SLOT)
                E(ldrb_imm, 0, 0, O_FL)
                E(lsls_imm, 0, 0, 31 - 3)
                E(b_cond, f"ml2_p{t}", "pl")
                E(movs_imm, 4, 0xFF)
                a.label(f"ml2_p{t}")
            imm32(0, COLOURS + 4 * TRK_SLOTS[t])
            E(ldr_imm, 0, 0, 0)
            E(movs_imm, 1, memlvl)
            E(bl, L["c_tmscl"])
            E(mov_reg, 7, 0)
            if dimrest:
                imm32(0, COLOURS + 4 * TRK_SLOTS[t])
                E(ldr_imm, 0, 0, 0)
                E(movs_imm, 1, restlvl)
                E(bl, L["c_tmscl"])
                E(str_sp, 0, 8)
            for r in range(4):
                E(ldr_sp, 2, 0)
                E(adds_imm8, 2, r)
                E(cmp_reg, 2, 4)
                E(b_cond, f"ml2_k{t}{r}", "eq")           # the pattern playing: the stock's light
                if vlock:                                 # View Lock's white pad: the stock's
                    E(ldr_sp, 0, 12)
                    E(cmp_imm, 0, 0)
                    E(b_cond, f"ml2_v{t}{r}", "eq")
                    imm32(0, PV + O_PV_PADS + 4 * t)
                    E(ldr_imm, 0, 0, 0)
                    E(ldrb_reg, 0, 0, 2)
                    E(lsls_imm, 0, 0, 31 - 4)
                    E(b_cond, f"ml2_k{t}{r}", "mi")
                    a.label(f"ml2_v{t}{r}")
                E(ldr_sp, 3, 4)
                if dimrest:
                    E(ldr_sp, 0, 8)
                else:
                    E(movs_imm, 0, 0)
                E(lsrs_reg, 3, 2)
                E(lsls_imm, 3, 3, 31)
                E(b_cond, f"ml2_w{t}{r}", "pl")
                E(mov_reg, 0, 7)
                a.label(f"ml2_w{t}{r}")
                E(str_imm, 0, 5, 4 * (8 * r + t))
                a.label(f"ml2_k{t}{r}")
            a.label(f"ml2_n{t}")
        a.label("ml2_x")
        E(pop_list, [0, 1, 2, 3, 4] if dimrest else [2, 3, 4], pc=True)

    # ---- c_msdraw (r4 = our slot, r5 = the out RGB words): the page's lights; clobbers r0-r3, r6, r7
    a.label("c_msdraw")
    E(push_list, [3], lr=True)
    E(bl, "c_mtvals")

    for t in range(8):                                    # the track buttons
        imm32(0, COLOURS + 4 * TRK_SLOTS[t])
        E(ldr_imm, 7, 0, 0)
        E(ldrb_imm, 0, 4, O_VALS + 4)
        E(lsls_imm, 0, 0, 31 - t)
        E(b_cond, f"md_t{t}", "pl")
        scl(VDIM)
        E(mov_reg, 7, 0)
        a.label(f"md_t{t}")
        E(mov_reg, 0, 5)
        E(adds_imm8, 0, 4 * LED_TRK0)
        E(str_imm, 7, 0, 4 * t)
    if pageclr:                                           # Clear held: the tracks with a list green, the others dark
        held_clear(0)
        E(b_cond, "md_cx", "eq")
        E(bl, "c_mtblk")
        E(mov_reg, 6, 0)
        imm32(0, COLOURS + 4 * GREEN)
        E(ldr_imm, 7, 0, 0)
        E(mov_reg, 2, 5)
        E(adds_imm8, 2, 4 * LED_TRK0)
        for t in range(8):
            E(movs_imm, 1, 0)
            E(cmp_imm, 6, 0)
            E(b_cond, f"md_c{t}", "eq")
            E(raw, ldrb_w(0, 6, B_LISTS + LIST_LEN * t))
            E(cmp_imm, 0, 0)
            E(b_cond, f"md_c{t}", "eq")
            E(mov_reg, 1, 7)
            a.label(f"md_c{t}")
            E(str_imm, 1, 2, 4 * t)
        a.label("md_cx")
    E(movs_imm, 0, 0)
    for c in range(8):                                    # the columns without a setting: dark
        if c in COLS:
            continue
        for r in range(4):
            E(str_imm, 0, 5, 4 * (8 * r + c))
    for k, (c, n) in enumerate(zip(COLS, NVAL)):
        imm32(0, COLOURS + 4 * (GRAD0 + c))
        E(ldr_imm, 7, 0, 0)                               # r7 = the column's colour
        scl(DIM)
        E(mov_reg, 6, 0)                                  # r6 = DIM of it
        for r in range(4):
            lab = f"md_{c}{r}"
            E(ldrb_imm, 2, 4, O_PAGE)
            E(lsls_imm, 2, 2, 2)
            E(adds_imm8, 2, r)                            # r2 = the value of this pad
            E(ldrb_imm, 3, 4, O_VALS + k)                 # r3 = the value chosen
            if k == 0:
                E(ldrb_imm, 1, 4, O_VALS + 1)             # Length type
                E(cmp_imm, 1, 0)
                E(b_cond, f"{lab}e", "ne")
                scl(VDIM)                                 # Same as the chain: the column not used
                E(b, f"{lab}w")
                a.label(f"{lab}e")
                E(mov_reg, 0, 6)
                E(cmp_reg, 2, 3)
                E(b_cond, f"{lab}w", "hi")                # past the Length: DIM
                E(mov_reg, 0, 7)
                E(cmp_imm, 1, 1)
                E(b_cond, f"{lab}w", "eq")                # Exact: the bar full
                E(cmp_reg, 2, 3)
                E(b_cond, f"{lab}w", "eq")                # Random: the Length full
                if randfill:
                    scl(HALF)
                else:
                    E(mov_reg, 0, 6)
            else:
                E(movs_imm, 0, 0)
                E(cmp_imm, 2, n)
                E(b_cond, f"{lab}w", "hs")                # no value here: dark
                E(mov_reg, 0, 6)
                E(cmp_reg, 2, 3)
                E(b_cond, f"{lab}w", "ne")
                E(mov_reg, 0, 7)
            a.label(f"{lab}w")
            E(str_imm, 0, 5, 4 * (8 * r + c))
    if amount:                                            # page 2, column 4: the Amount meter, lit from the bottom up to the value
        E(ldrb_imm, 0, 4, O_PAGE)
        E(cmp_imm, 0, 0)
        E(b_cond, "md_am", "eq")
        for r in range(4):
            imm32(0, COLOURS + 4 * (GRAD0 + AM_CODES[r]))
            E(ldr_imm, 7, 0, 0)
            E(mov_reg, 0, 7)
            E(ldrb_imm, 1, 4, O_VAL2)
            E(lsls_imm, 1, 1, 30)
            E(lsrs_imm, 1, 1, 30)
            E(cmp_imm, 1, r)
            E(b_cond, f"md_a{r}", "ls")
            scl(DIM)
            a.label(f"md_a{r}")
            E(str_imm, 0, 5, 4 * (8 * r + AM_COL))
        if norep:                                         # column 5: Repeats On / Off, the chosen full
            imm32(0, COLOURS + 4 * GREEN)
            E(ldr_imm, 7, 0, 0)
            scl(DIM)
            E(mov_reg, 6, 0)
            E(ldrb_imm, 1, 4, O_VAL2)
            E(lsrs_imm, 1, 1, NR_BIT)
            E(lsls_imm, 1, 1, 31)                         # mi: Off
            E(mov_reg, 0, 7)
            E(mov_reg, 2, 6)
            E(b_cond, "md_nr", "pl")
            E(mov_reg, 0, 6)
            E(mov_reg, 2, 7)
            a.label("md_nr")
            E(str_imm, 0, 5, 4 * (8 * 0 + NR_COL))
            E(str_imm, 2, 5, 4 * (8 * 1 + NR_COL))
        if keep1:                                         # column 6: Keep slot 1 Off / On, the chosen full (r6 = DIM, r7 = full)
            E(ldrb_imm, 1, 4, O_VAL2)
            E(lsrs_imm, 1, 1, K1_BIT)
            E(lsls_imm, 1, 1, 31)                         # mi: On
            E(mov_reg, 0, 7)
            E(mov_reg, 2, 6)
            E(b_cond, "md_k1", "pl")
            E(mov_reg, 0, 6)
            E(mov_reg, 2, 7)
            a.label("md_k1")
            E(str_imm, 0, 5, 4 * (8 * 0 + K1_COL))
            E(str_imm, 2, 5, 4 * (8 * 1 + K1_COL))
        a.label("md_am")
    imm32(1, WHITE)
    E(movs_imm, 2, 0)
    E(mov_reg, 3, 5)
    E(adds_imm8, 3, HI)
    E(ldrb_imm, 0, 4, O_PAGE)
    E(cmp_imm, 0, 0)
    E(b_cond, "md_p1", "ne")
    E(str_imm, 1, 3, 4 * LED_DOWN - HI)
    E(str_imm, 2, 3, 4 * LED_UP - HI)
    E(b, "md_d")
    a.label("md_p1")
    E(str_imm, 2, 3, 4 * LED_DOWN - HI)
    E(str_imm, 1, 3, 4 * LED_UP - HI)
    a.label("md_d")
    imm32(0, COLOURS + 4 * (PULSE if mutate and not greendup else GREEN))
    E(ldr_imm, 7, 0, 0)
    E(mov_reg, 0, 7)
    if greendup:                                          # Duplicate green, pulsing as the track buttons (the stock frame's pulse); held, full
        imm32(1, C.CTRL + O_HELD)
        E(ldr_imm, 1, 1, 0)
        E(lsrs_imm, 1, 1, BIT_DUPH + 1)
        E(b_cond, "md_g", "cs")
        imm32(2, COLOURS + 4 * FRAME_PULSE)
        E(ldrb_imm, 2, 2, 0)
        E(movw, 1, 255)
        E(subs_reg, 1, 1, 2)
        E(movs_imm, 2, 192)
        E(muls, 1, 2)
        E(lsrs_imm, 1, 1, 8)
        E(adds_imm8, 1, 64)
        E(bl, L["c_tmscl"])
    else:
        imm32(1, C.HAL_TICK)
        E(ldr_imm, 1, 1, 0)
        E(lsrs_imm, 1, 1, 10)                             # carry = bit 9: about one pulse a second
        E(b_cond, "md_g", "cs")
        scl(PULSE_LO)
    a.label("md_g")
    E(mov_reg, 1, 5)
    E(adds_imm8, 1, HI)
    E(str_imm, 0, 1, 4 * LED_DUP - HI)
    E(pop_list, [3], pc=True)
    return a.assemble()


def keep1_on(E, imm32, SLOT, skip, reg=1):
    """on to `skip` unless Keep slot 1 is On; clobbers r<reg>"""
    imm32(reg, SLOT)
    E(ldrb_imm, reg, reg, O_VAL2)
    E(lsrs_imm, reg, reg, K1_BIT + 1)
    E(b_cond, skip, "cc")


def norep_check(a, E, imm32, SLOT):
    """(c_mtgen's pick, r0 = the pattern, r3 = picks left, r6 = the slot, r5 = the list's length, the stack as c_mtgen's) Repeats
    Off: the pick again (mg2_rt) when it is the slot before's, the next slot's (a kept chain slot) or, for the last slot, slot 1's;
    after NR_TRIES picks the pick stays; clobbers r1, r2"""
    imm32(1, SLOT)
    E(ldrb_imm, 1, 1, O_VAL2)
    E(lsrs_imm, 1, 1, NR_BIT + 1)
    E(b_cond, "nr_ok", "cc")                              # Repeats On
    E(subs_imm8, 3, 1)
    E(b_cond, "nr_ok", "mi")                              # no picks left: take it
    E(cmp_imm, 6, 0)
    E(b_cond, "nr_p0", "eq")
    E(mov_reg, 1, 13)
    E(adds_reg, 1, 1, 6)
    E(ldrb_imm, 2, 1, 0)                                  # the slot before (list + 1 + slot - 1)
    E(cmp_reg, 0, 2)
    E(b_cond, "mg2_rt", "eq")
    E(b, "nr_nx")
    a.label("nr_p0")                                      # slot 1: the last slot, when it keeps the chain's pattern (the list loops)
    E(cmp_imm, 5, 1)
    E(b_cond, "nr_nx", "ls")
    E(movs_imm, 2, 1)
    E(subs_reg, 2, 5, 2)
    E(raw, ldrb_sp(1, 9))
    E(cmp_reg, 2, 1)
    E(b_cond, "nr_nx", "hs")
    E(raw, ldrb_sp(1, 11))
    E(lsrs_reg, 1, 2)
    E(lsls_imm, 1, 1, 31)
    E(b_cond, "nr_nx", "mi")
    E(raw, ldrb_sp(1, 10))
    E(adds_reg, 2, 2, 1)
    E(cmp_reg, 0, 2)
    E(b_cond, "mg2_rt", "eq")
    a.label("nr_nx")
    E(adds_imm8, 6, 1)                                    # r6 = the next slot (put back below)
    E(cmp_reg, 6, 5)
    E(b_cond, "nr_w", "lo")
    E(cmp_imm, 5, 1)
    E(b_cond, "nr_ok1", "ls")
    E(raw, ldrb_sp(2, 1))                                 # the last slot: slot 1
    E(b, "nr_cmp")
    a.label("nr_w")
    E(raw, ldrb_sp(1, 9))
    E(cmp_reg, 6, 1)
    E(b_cond, "nr_ok1", "hs")                             # the next slot is random: checked when it is picked
    E(raw, ldrb_sp(1, 11))
    E(lsrs_reg, 1, 6)
    E(lsls_imm, 1, 1, 31)
    E(b_cond, "nr_ok1", "mi")
    E(raw, ldrb_sp(2, 10))
    E(adds_reg, 2, 2, 6)                                  # the next slot keeps the chain's pattern
    a.label("nr_cmp")
    E(subs_imm8, 6, 1)
    E(cmp_reg, 0, 2)
    E(b_cond, "mg2_rt", "eq")
    E(b, "nr_ok")
    a.label("nr_ok1")
    E(subs_imm8, 6, 1)
    a.label("nr_ok")


def amount_mask(a, E, imm32, SLOT, keep1=False):
    """(c_mtgen, r5 = the list's length, r6 = the slot, the stack as c_mtgen's) [sp + 11] = the slots that change: Amount All, every
    slot; else (c x k + 2) / 4 of the c = min(length, chain's length) chain slots (k = 3 Most, 2 Some, 1 A little; at least 1), at random;
    clobbers r0-r3, r6"""
    E(movs_imm, 1, 0xFF)
    E(raw, strb_sp(1, 11))
    E(ldrb_imm, 0, 6, O_VAL2)
    E(lsls_imm, 0, 0, 30)
    E(lsrs_imm, 0, 0, 30)
    E(cmp_imm, 0, 0)
    E(b_cond, "am_x", "eq")
    E(movs_imm, 1, 4)
    E(subs_reg, 0, 1, 0)                                  # r0 = k
    E(raw, ldrb_sp(3, 9))
    E(cmp_reg, 3, 5)
    E(b_cond, "am_c", "ls")
    E(mov_reg, 3, 5)
    a.label("am_c")                                       # r3 = c
    if keep1:                                             # Keep slot 1 (a list of 2 or more): the chain slots after slot 1
        E(cmp_imm, 5, 2)
        E(b_cond, "am_k", "lo")
        keep1_on(E, imm32, SLOT, "am_k", reg=1)
        E(subs_imm8, 3, 1)
        a.label("am_k")
    E(muls, 0, 3)
    E(adds_imm8, 0, 2)
    E(lsrs_imm, 0, 0, 2)
    E(cmp_imm, 0, 0)
    E(b_cond, "am_m", "ne")
    E(movs_imm, 0, 1)
    a.label("am_m")                                       # r0 = the slots that change
    E(cmp_reg, 0, 3)
    E(b_cond, "am_x", "hs")
    E(push_list, [4, 5])
    E(mov_reg, 4, 0)
    E(mov_reg, 5, 3)
    E(movs_imm, 6, 0)
    E(movs_imm, 3, 0)
    a.label("am_l")
    E(bl, "c_mtrand")
    E(lsrs_imm, 0, 0, 16)
    E(muls, 0, 5)
    E(lsrs_imm, 0, 0, 16)
    E(movs_imm, 1, 1)
    E(lsls_reg, 1, 0)
    E(tst_reg, 6, 1)
    E(b_cond, "am_l", "ne")
    E(orrs_reg, 6, 1)
    E(adds_imm8, 3, 1)
    E(cmp_reg, 3, 4)
    E(b_cond, "am_l", "lo")
    E(pop_list, [4, 5])
    if keep1:
        E(cmp_imm, 5, 2)
        E(b_cond, "am_s", "lo")
        keep1_on(E, imm32, SLOT, "am_s", reg=1)
        E(lsls_imm, 6, 6, 1)
        a.label("am_s")
    E(raw, strb_sp(6, 11))
    a.label("am_x")


def mutate_code(a, E, L, SLOT, imm32, far, held_clear, crit_in, crit_out, scenesave=False, amount=False, norep=False,
                keep1=False, hidepause=False):
    # ---- c_mtbits(r0 = offset in the block, r1 = bits cleared, r2 = bits set, r3 = bits flipped): the block made ours; clobbers r0-r3
    a.label("c_mtbits")
    E(push_list, [3, 4, 5, 6, 7], lr=True)
    E(mov_reg, 4, 0)
    E(mov_reg, 5, 1)
    E(mov_reg, 6, 2)
    E(mov_reg, 7, 3)
    crit_in()
    E(bl, "c_mtw")
    E(cmp_imm, 0, 0)
    E(b_cond, "mb2_x", "eq")
    E(ldrb_reg, 1, 0, 4)
    E(bics_reg, 1, 5)
    E(orrs_reg, 1, 6)
    E(eors_reg, 1, 7)
    E(strb_reg, 1, 0, 4)
    E(bl, "c_mtfix")
    a.label("mb2_x")
    crit_out()
    E(pop_list, [3, 4, 5, 6, 7], pc=True)

    # ---- c_mtlist(r0 = the track, r1 = its list, LIST_LEN B): into the block; clobbers r0-r3
    a.label("c_mtlist")
    E(push_list, [3, 4, 5, 6, 7], lr=True)
    E(mov_reg, 4, 0)
    E(mov_reg, 5, 1)
    crit_in()
    E(bl, "c_mtw")
    E(cmp_imm, 0, 0)
    E(b_cond, "ml_x", "eq")
    E(mov_reg, 6, 0)
    E(movs_imm, 1, LIST_LEN)
    E(muls, 1, 4)
    E(adds_imm8, 1, B_LISTS)
    E(adds_reg, 1, 6, 1)
    E(movs_imm, 2, 0)
    a.label("ml_l")
    E(ldrb_reg, 3, 5, 2)
    E(strb_reg, 3, 1, 2)
    E(adds_imm8, 2, 1)
    E(cmp_imm, 2, LIST_LEN)
    E(b_cond, "ml_l", "lo")
    E(mov_reg, 0, 6)
    E(bl, "c_mtfix")
    a.label("ml_x")
    crit_out()
    E(pop_list, [3, 4, 5, 6, 7], pc=True)

    # ---- c_mtcl(r0 = the track): its list and its renew bit gone (a block that is ours only); clobbers r0-r3
    a.label("c_mtcl")
    E(push_list, [3, 4, 5, 6, 7], lr=True)
    E(mov_reg, 4, 0)
    crit_in()
    E(bl, "c_mtblk")
    E(cmp_imm, 0, 0)
    E(b_cond, "mc_x", "eq")
    E(mov_reg, 6, 0)
    E(movs_imm, 1, LIST_LEN)
    E(muls, 1, 4)
    E(adds_imm8, 1, B_LISTS)
    E(adds_reg, 5, 6, 1)
    E(ldrb_imm, 2, 5, 0)
    E(movs_imm, 3, 0)
    E(strb_imm, 3, 5, 0)
    E(movs_imm, 7, 1)
    E(lsls_reg, 7, 4)
    E(raw, ldrb_w(3, 6, B_RENEW))
    E(bics_reg, 3, 7)
    E(raw, strb_w(3, 6, B_RENEW))
    E(cmp_imm, 2, 0)
    E(b_cond, "mc_f", "eq")
    imm32(3, SLOT)                                        # a list ended: the next pattern end brings the track into its chain
    E(ldrb_imm, 1, 3, O_EXIT)
    E(orrs_reg, 1, 7)
    E(strb_imm, 1, 3, O_EXIT)
    a.label("mc_f")
    E(mov_reg, 0, 6)
    E(bl, "c_mtfix")
    a.label("mc_x")
    crit_out()
    E(pop_list, [3, 4, 5, 6, 7], pc=True)

    # ---- c_mtrand() -> r0 = the next random word; clobbers r1, r2
    a.label("c_mtrand")
    imm32(0, SLOT)
    E(ldr_imm, 1, 0, O_RNG)
    imm32(2, LCG_A)
    E(muls, 1, 2)
    imm32(2, LCG_C)
    E(adds_reg, 1, 1, 2)
    E(str_imm, 1, 0, O_RNG)
    E(mov_reg, 0, 1)
    E(raw, bytes([0x70, 0x47]))

    # ---- c_mtpool(r0 = the track) -> r0 = its patterns with a hit from the first to the last step (bit p); clobbers r1-r3
    a.label("c_mtpool")
    E(push_list, [3, 4, 5, 6, 7], lr=True)
    E(mov_reg, 4, 0)
    E(movs_imm, 6, 0)
    E(bl, L["c_rrt"])
    E(cmp_imm, 0, 0)
    E(b_cond, "mq2_x", "eq")
    imm32(1, rhrec_tail() - STEPS0)
    E(subs_reg, 0, 0, 1)
    imm32(1, TRK_STRIDE)
    E(muls, 1, 4)
    E(adds_reg, 5, 0, 1)                                  # r5 = pattern 1 of the track
    E(movs_imm, 4, 0)
    a.label("mq2_p")
    E(raw, ldrb_w(1, 5, P_FIRST))
    E(raw, ldrb_w(2, 5, P_LAST))
    E(cmp_reg, 1, 2)
    E(b_cond, "mq2_o", "ls")
    E(mov_reg, 3, 1)
    E(mov_reg, 1, 2)
    E(mov_reg, 2, 3)
    a.label("mq2_o")
    E(cmp_imm, 2, MAX_STEP)
    E(b_cond, "mq2_s", "ls")
    E(movs_imm, 2, MAX_STEP)
    a.label("mq2_s")
    E(lsls_imm, 3, 1, 3)
    E(adds_reg, 3, 3, 5)
    E(ldrb_imm, 3, 3, 3)
    E(cmp_imm, 3, 0)
    E(b_cond, "mq2_h", "ne")
    E(adds_imm8, 1, 1)
    E(cmp_reg, 1, 2)
    E(b_cond, "mq2_s", "ls")
    E(b, "mq2_n")
    a.label("mq2_h")
    E(movs_imm, 3, 1)
    E(lsls_reg, 3, 4)
    E(orrs_reg, 6, 3)
    a.label("mq2_n")
    E(movw, 3, PAT_STRIDE)
    E(adds_reg, 5, 5, 3)
    E(adds_imm8, 4, 1)
    E(cmp_imm, 4, 8)
    E(b_cond, "mq2_p", "lo")
    a.label("mq2_x")
    E(mov_reg, 0, 6)
    E(pop_list, [3, 4, 5, 6, 7], pc=True)

    # ---- c_mtgen(r0 = the track, r1 = its chain's length, (amount) r2 = its chain's first): a new list by the settings into the block;
    #      clobbers r0-r3. The stack: + 0 the list, + 9 the chain's length, + 10 its first, + 11 (amount) the slots that change (bit i)
    a.label("c_mtgen")
    E(push_list, [3, 4, 5, 6, 7], lr=True)
    E(sub_sp_imm, 12)
    E(mov_reg, 4, 0)
    E(mov_reg, 5, 1)
    E(movs_imm, 0, 0)
    for o in (0, 4, 8):
        E(str_sp, 0, o)
    if amount:
        E(raw, strb_sp(1, 9))
        E(raw, strb_sp(2, 10))
    E(bl, "c_mtvals")
    imm32(6, SLOT)
    E(movs_imm, 7, 0xFF)
    E(ldrb_imm, 0, 6, O_VALS + 2)
    E(cmp_imm, 0, 0)
    E(b_cond, "mg2_pl", "ne")                             # Pool All
    E(mov_reg, 0, 4)
    E(bl, "c_mtpool")
    E(mov_reg, 7, 0)
    a.label("mg2_pl")
    E(cmp_imm, 7, 0)
    if norep:
        far("mg2_w", "eq")                                # no pattern with a hit: no list
    else:
        E(b_cond, "mg2_w", "eq")
    E(ldrb_imm, 1, 6, O_VALS + 1)
    E(ldrb_imm, 0, 6, O_VALS)
    E(adds_imm8, 0, 1)                                    # r0 = Length
    E(cmp_imm, 1, 0)
    E(b_cond, "mg2_c", "eq")
    E(cmp_imm, 1, 1)
    E(b_cond, "mg2_r", "ne")
    E(mov_reg, 5, 0)
    E(b, "mg2_c")
    a.label("mg2_r")
    E(push_list, [4], lr=False)
    E(mov_reg, 4, 0)
    E(bl, "c_mtrand")
    E(lsrs_imm, 0, 0, 16)
    E(muls, 0, 4)
    E(lsrs_imm, 0, 0, 16)
    E(adds_imm8, 0, 1)
    E(mov_reg, 5, 0)
    E(pop_list, [4])
    a.label("mg2_c")
    E(cmp_imm, 5, 1)
    E(b_cond, "mg2_c1", "hs")
    E(movs_imm, 5, 1)
    a.label("mg2_c1")
    E(cmp_imm, 5, 8)
    E(b_cond, "mg2_c8", "ls")
    E(movs_imm, 5, 8)
    a.label("mg2_c8")
    if amount:
        amount_mask(a, E, imm32, SLOT, keep1)
    E(mov_reg, 0, 13)
    E(strb_imm, 5, 0, 0)
    E(movs_imm, 6, 0)
    a.label("mg2_l")
    if keep1:                                             # Keep slot 1 (a list of 2 or more): slot 1 the chain's first
        E(cmp_imm, 6, 0)
        E(b_cond, "mg2_k1", "ne")
        E(cmp_imm, 5, 2)
        E(b_cond, "mg2_k1", "lo")
        keep1_on(E, imm32, SLOT, "mg2_k1")
        E(raw, ldrb_sp(0, 10))
        E(b, "mg2_st")
        a.label("mg2_k1")
    if amount:                                            # a slot of the chain that does not change: the chain's pattern
        E(raw, ldrb_sp(1, 9))
        E(cmp_reg, 6, 1)
        E(b_cond, "mg2_rn", "hs")
        E(raw, ldrb_sp(1, 11))
        E(lsrs_reg, 1, 6)
        E(lsls_imm, 1, 1, 31)
        E(b_cond, "mg2_rn", "mi")
        E(raw, ldrb_sp(0, 10))
        E(adds_reg, 0, 0, 6)
        E(b, "mg2_st")
    a.label("mg2_rn")
    if norep:
        E(movs_imm, 3, NR_TRIES)
        a.label("mg2_rt")
    E(bl, "c_mtrand")
    E(lsrs_imm, 0, 0, 29)
    E(movs_imm, 1, 1)
    E(lsls_reg, 1, 0)
    E(tst_reg, 1, 7)
    E(b_cond, "mg2_rt" if norep else "mg2_rn", "eq")
    if norep:
        norep_check(a, E, imm32, SLOT)
    a.label("mg2_st")
    E(mov_reg, 1, 13)
    E(adds_reg, 1, 1, 6)
    E(strb_imm, 0, 1, 1)
    E(adds_imm8, 6, 1)
    E(cmp_reg, 6, 5)
    E(b_cond, "mg2_l", "lo")
    a.label("mg2_w")
    E(mov_reg, 0, 4)
    E(mov_reg, 1, 13)
    E(bl, "c_mtlist")
    E(add_sp_imm, 12)
    E(pop_list, [3, 4, 5, 6, 7], pc=True)

    # ---- c_mtgx(r0 = the track, r1 = its chain's first, r2 = last): its slot before slot 1, a new list; clobbers r0-r3
    a.label("c_mtgx")
    E(push_list, [4], lr=True)
    E(mov_reg, 4, 0)
    imm32(3, SLOT)
    E(adds_reg, 3, 3, 4)
    E(movs_imm, 0, 0xFF)
    E(strb_imm, 0, 3, O_POS)
    E(cmp_reg, 2, 1)
    E(b_cond, "mx_o", "hs")
    E(mov_reg, 3, 1)
    E(mov_reg, 1, 2)
    E(mov_reg, 2, 3)
    a.label("mx_o")
    if amount:
        E(mov_reg, 3, 1)
    E(subs_reg, 1, 2, 1)
    E(adds_imm8, 1, 1)
    if amount:
        E(mov_reg, 2, 3)
    E(mov_reg, 0, 4)
    E(bl, "c_mtgen")
    E(pop_list, [4], pc=True)

    # ---- c_mtdo(): the mutate: On the tap, a list now for each track that is on; Every chain end, their renew bits; clobbers r0-r3
    a.label("c_mtdo")
    E(push_list, [3, 4, 5, 6, 7], lr=True)
    imm32(4, SLOT)
    E(ldr_imm, 0, 4, O_RNG)
    imm32(1, C.HAL_TICK)
    E(ldr_imm, 1, 1, 0)
    E(eors_reg, 0, 1)
    E(str_imm, 0, 4, O_RNG)
    if hidepause:                                         # stopped: the paused pads hidden until a play
        imm32(0, ENG + O_RUN)
        E(ldr_imm, 0, 0, 0)
        E(movs_imm, 1, 0)
        E(bl, PARAM_GET)
        E(ldrb_imm, 0, 0, 0)
        E(cmp_imm, 0, 0)
        E(b_cond, "md2_r", "ne")
        E(ldrb_imm, 0, 4, O_FL)
        E(movs_imm, 1, FL_HIDE)
        E(orrs_reg, 0, 1)
        E(strb_imm, 0, 4, O_FL)
        a.label("md2_r")
    E(bl, "c_mtvals")
    E(movs_imm, 5, 0)
    a.label("md2_l")
    E(ldrb_imm, 0, 4, O_VALS + 4)
    E(lsrs_reg, 0, 5)
    E(lsls_imm, 0, 0, 31)
    E(b_cond, "md2_n", "mi")                              # the track is off
    E(movs_imm, 6, 1)
    E(lsls_reg, 6, 5)
    E(ldrb_imm, 0, 4, O_VALS + 3)
    E(cmp_imm, 0, 0)
    E(b_cond, "md2_a", "ne")
    imm32(0, CHAINS)
    E(ldr_imm, 0, 0, 0)
    E(mov_reg, 1, 5)
    E(bl, PARAM_GET)
    E(ldrb_imm, 1, 0, 0)
    E(ldrb_imm, 2, 0, 1)
    E(mov_reg, 0, 5)
    E(bl, "c_mtgx")
    E(movs_imm, 0, B_RENEW)
    E(mov_reg, 1, 6)
    E(movs_imm, 2, 0)
    E(movs_imm, 3, 0)
    E(bl, "c_mtbits")
    E(b, "md2_n")
    a.label("md2_a")
    E(movs_imm, 0, B_RENEW)
    E(movs_imm, 1, 0)
    E(mov_reg, 2, 6)
    E(movs_imm, 3, 0)
    E(bl, "c_mtbits")
    a.label("md2_n")
    E(adds_imm8, 5, 1)
    E(cmp_imm, 5, 8)
    E(b_cond, "md2_l", "lo")
    E(pop_list, [3, 4, 5, 6, 7], pc=True)

    # ---- c_mtclon(): the tracks that are on lose their lists (Clear + Shift + Duplicate); clobbers r0-r3
    a.label("c_mtclon")
    E(push_list, [3, 4, 5], lr=True)
    E(bl, "c_mtvals")
    imm32(4, SLOT)
    E(movs_imm, 5, 0)
    a.label("mo2_l")
    E(ldrb_imm, 0, 4, O_VALS + 4)
    E(lsrs_reg, 0, 5)
    E(lsls_imm, 0, 0, 31)
    E(b_cond, "mo2_n", "mi")
    E(mov_reg, 0, 5)
    E(bl, "c_mtcl")
    a.label("mo2_n")
    E(adds_imm8, 5, 1)
    E(cmp_imm, 5, 8)
    E(b_cond, "mo2_l", "lo")
    E(pop_list, [3, 4, 5], pc=True)

    # ---- c_mtnext (the track advance at 0x08034E06, in place of `ldrb.w r2, [sp, #1]`): [sp, #1] and r2 = the next pattern
    F = 24
    a.label("c_mtnext")
    E(push_list, [3, 4, 5, 6, 7], lr=True)
    E(raw, ldrb_sp(4, F))
    E(raw, ldrb_sp(5, F + 1))                             # r5 = the stock's choice
    E(cmp_imm, 4, 8)
    far("nx_x", "hs")
    E(bl, "c_mtblk")
    E(cmp_imm, 0, 0)
    far("nx_x", "eq")
    E(mov_reg, 6, 0)                                      # r6 = the block
    E(raw, ldrb_sp(0, F + 0x44))
    E(cmp_imm, 0, 0)
    E(b_cond, "nx_ns", "eq")
    if scenesave:                                         # a scene change: the new scene's list (the look-ahead only peeks), else the chain
        E(ldr_sp, 0, F + 0x48)
        E(mov_reg, 1, 4)
        E(mov_reg, 2, 11)
        E(bl, "c_scget")
        E(cmp_imm, 0, 8)
        far("nx_x", "hs")
        E(mov_reg, 5, 0)
        E(b, "nx_x")
    else:
        E(mov_reg, 0, 11)                                 # a scene change: the play ends the list
        E(cmp_imm, 0, 0)
        far("nx_x", "ne")
        E(mov_reg, 0, 4)
        E(bl, "c_mtcl")
        E(b, "nx_x")
    a.label("nx_ns")
    E(movs_imm, 0, LIST_LEN)
    E(muls, 0, 4)
    E(adds_imm8, 0, B_LISTS)
    E(adds_reg, 7, 6, 0)                                  # r7 = the track's list
    E(ldrb_imm, 0, 7, 0)
    E(cmp_imm, 0, 0)
    far("nx_has", "ne")
    imm32(1, SLOT)                                        # no list
    E(ldrb_imm, 2, 1, O_EXIT)
    E(movs_imm, 3, 1)
    E(lsls_reg, 3, 4)
    E(tst_reg, 2, 3)
    E(b_cond, "nx_arm", "eq")
    E(mov_reg, 0, 11)
    E(cmp_imm, 0, 0)
    E(b_cond, "nx_ef", "ne")
    E(bics_reg, 2, 3)
    E(strb_imm, 2, 1, O_EXIT)
    a.label("nx_ef")                                      # a list just ended: a pattern outside the chain goes to the first
    E(raw, ldrb_sp(0, F + 0x18))
    E(cmp_imm, 0, 0)
    E(b_cond, "nx_arm", "ne")
    E(mov_reg, 0, 8)
    E(cmp_reg, 5, 0)
    E(b_cond, "nx_f1", "lo")
    E(raw, ldrb_sp(1, F + 2))
    E(cmp_reg, 5, 1)
    E(b_cond, "nx_arm", "ls")
    a.label("nx_f1")
    E(mov_reg, 5, 8)
    a.label("nx_arm")                                     # Every chain end, waiting: the chain's end starts a list
    E(raw, ldrb_w(0, 6, B_RENEW))
    E(lsrs_reg, 0, 4)
    E(lsls_imm, 0, 0, 31)
    far("nx_x", "pl")
    E(ldrb_imm, 0, 6, B_VAL + 3)
    E(cmp_imm, 0, 0)
    far("nx_x", "eq")
    E(raw, ldrb_sp(0, F + 0x18))
    E(cmp_imm, 0, 0)
    far("nx_x", "ne")
    E(mov_reg, 0, 8)
    E(cmp_reg, 5, 0)
    E(b_cond, "nx_ce", "eq")
    E(mov_reg, 0, 11)
    E(cmp_imm, 0, 0)
    far("nx_x", "ne")
    E(raw, ldrb_sp(1, F + 2))
    E(cmp_reg, 5, 1)
    far("nx_x", "ne")
    E(mov_reg, 0, 4)                                      # the play enters the chain's last: the list comes after it
    E(mov_reg, 1, 8)
    E(raw, ldrb_sp(2, F + 2))
    E(bl, "c_mtgx")
    E(b, "nx_x")
    a.label("nx_ce")
    E(mov_reg, 0, 4)
    E(mov_reg, 1, 8)
    E(raw, ldrb_sp(2, F + 2))
    E(bl, "c_mtgx")
    E(ldrb_imm, 0, 7, 0)
    E(cmp_imm, 0, 0)
    far("nx_x", "eq")
    a.label("nx_has")                                     # r0 = the list's length
    imm32(1, SLOT)
    E(adds_reg, 1, 1, 4)
    E(ldrb_imm, 2, 1, O_POS)
    E(raw, ldrb_sp(3, F + 0x18))
    E(cmp_imm, 3, 0)
    E(b_cond, "nx_rs", "ne")                              # forced (a play start): slot 1
    E(adds_imm8, 2, 1)
    E(cmp_reg, 2, 0)
    E(b_cond, "nx_ch", "lo")
    a.label("nx_rs")
    E(movs_imm, 2, 0)
    a.label("nx_ch")
    E(adds_reg, 3, 7, 2)
    E(ldrb_imm, 5, 3, 1)
    E(movs_imm, 3, 7)
    E(ands_reg, 5, 3)
    E(mov_reg, 3, 11)
    E(cmp_imm, 3, 0)
    E(b_cond, "nx_x", "ne")                               # the look-ahead: nothing changed
    E(strb_imm, 2, 1, O_POS)
    E(adds_imm8, 2, 1)
    E(cmp_reg, 2, 0)
    E(b_cond, "nx_x", "ne")
    E(ldrb_imm, 0, 6, B_VAL + 3)                          # the list's last slot, Every chain end, renewing: the next list now
    E(cmp_imm, 0, 0)
    E(b_cond, "nx_x", "eq")
    E(raw, ldrb_w(0, 6, B_RENEW))
    E(lsrs_reg, 0, 4)
    E(lsls_imm, 0, 0, 31)
    E(b_cond, "nx_x", "pl")
    E(mov_reg, 0, 4)
    E(mov_reg, 1, 8)
    E(raw, ldrb_sp(2, F + 2))
    E(bl, "c_mtgx")
    a.label("nx_x")
    E(raw, strb_sp(5, F + 1))
    E(mov_reg, 2, 5)
    E(pop_list, [3, 4, 5, 6, 7], pc=True)


def scene_code(a, E, L, SLOT, imm32, far, crit_in, crit_out, scenefix=False):
    """a mutate a scene: its 8 lists packed in 29 B, 22 in the scene's record (spare bytes), 7 in the tail"""
    # ---- c_scad(r0 = scene, r1 = byte 0..28, r2 = the tail) -> r0 = its address; clobbers r3
    a.label("c_scad")
    E(push_list, [4], lr=True)
    E(cmp_imm, 1, 22)
    E(b_cond, "sa_t", "hs")
    E(movs_imm, 3, 40)
    E(muls, 3, 0)
    imm32(0, -SC_REC)
    E(subs_reg, 0, 2, 0)
    E(adds_reg, 0, 0, 3)
    E(cmp_imm, 1, 16)
    E(b_cond, "sa_m", "hs")
    E(lsrs_imm, 3, 1, 1)
    E(lsls_imm, 3, 3, 2)
    E(adds_reg, 0, 0, 3)
    E(lsls_imm, 3, 1, 31)
    E(lsrs_imm, 3, 3, 31)
    E(adds_reg, 0, 0, 3)
    E(adds_imm8, 0, 2)
    E(pop_list, [4], pc=True)
    a.label("sa_m")
    E(adds_reg, 0, 0, 1)
    E(adds_imm8, 0, 34 - 16)
    E(pop_list, [4], pc=True)
    a.label("sa_t")
    E(movs_imm, 3, SC_TLEN)
    E(muls, 3, 0)
    E(adds_reg, 0, 2, 3)
    E(adds_reg, 0, 0, 1)
    imm32(3, SC_TOFF - 22)
    E(adds_reg, 0, 0, 3)
    E(pop_list, [4], pc=True)

    # ---- c_scput(r0 = buf, r1 = bit, r2 = bits, r3 = value): the value's low bits from that bit up; clobbers r1-r3
    a.label("c_scput")
    E(push_list, [4, 5, 6, 7], lr=True)
    a.label("sp_l")
    E(cmp_imm, 2, 0)
    E(b_cond, "sp_x", "eq")
    E(lsrs_imm, 4, 1, 3)
    E(ldrb_reg, 5, 0, 4)
    E(lsls_imm, 6, 1, 29)
    E(lsrs_imm, 6, 6, 29)
    E(movs_imm, 7, 1)
    E(lsls_reg, 7, 6)
    E(bics_reg, 5, 7)
    E(lsrs_imm, 3, 3, 1)
    E(b_cond, "sp_z", "lo")
    E(orrs_reg, 5, 7)
    a.label("sp_z")
    E(strb_reg, 5, 0, 4)
    E(adds_imm8, 1, 1)
    E(subs_imm8, 2, 1)
    E(b, "sp_l")
    a.label("sp_x")
    E(pop_list, [4, 5, 6, 7], pc=True)

    # ---- c_scbits(r0 = buf, r1 = bit, r2 = bits) -> r0 = the value; clobbers r1-r3
    a.label("c_scbits")
    E(push_list, [4, 5, 6, 7], lr=True)
    E(movs_imm, 3, 0)
    E(movs_imm, 7, 0)
    a.label("sb_l")
    E(cmp_reg, 7, 2)
    E(b_cond, "sb_x", "hs")
    E(lsrs_imm, 4, 1, 3)
    E(ldrb_reg, 5, 0, 4)
    E(lsls_imm, 6, 1, 29)
    E(lsrs_imm, 6, 6, 29)
    E(lsrs_reg, 5, 6)
    E(lsls_imm, 5, 5, 31)
    E(lsrs_imm, 5, 5, 31)
    E(lsls_reg, 5, 7)
    E(orrs_reg, 3, 5)
    E(adds_imm8, 1, 1)
    E(adds_imm8, 7, 1)
    E(b, "sb_l")
    a.label("sb_x")
    E(mov_reg, 0, 3)
    E(pop_list, [4, 5, 6, 7], pc=True)

    # ---- c_scsum(r0 = scene, r1 = buf) -> r0 = the check byte of its 28 B; clobbers r2, r3
    a.label("c_scsum")
    E(push_list, [4], lr=True)
    E(movs_imm, 2, 0)
    a.label("ss_l")
    E(ldrb_reg, 3, 1, 2)
    E(adds_reg, 0, 0, 3)
    E(adds_imm8, 2, 1)
    E(cmp_imm, 2, SC_LEN - 1)
    E(b_cond, "ss_l", "lo")
    E(lsls_imm, 0, 0, 24)
    E(lsrs_imm, 0, 0, 24)
    E(movs_imm, 2, SC_CHECK)
    E(eors_reg, 0, 2)
    E(pop_list, [4], pc=True)

    # ---- c_scrd(r0 = scene, r1 = buf) -> r0 = 1 when the scene holds lists (buf = its 29 B), else 0; clobbers r1-r3
    a.label("c_scrd")
    E(push_list, [4, 5, 6, 7], lr=True)
    E(mov_reg, 4, 0)
    E(mov_reg, 5, 1)
    E(cmp_imm, 4, 16)
    E(b_cond, "sr_n", "hs")
    E(bl, L["c_rrt"])
    E(cmp_imm, 0, 0)
    E(b_cond, "sr_n", "eq")
    E(mov_reg, 6, 0)
    E(movs_imm, 7, 0)
    a.label("sr_l")
    E(mov_reg, 0, 4)
    E(mov_reg, 1, 7)
    E(mov_reg, 2, 6)
    E(bl, "c_scad")
    E(ldrb_imm, 0, 0, 0)
    E(strb_reg, 0, 5, 7)
    E(adds_imm8, 7, 1)
    E(cmp_imm, 7, SC_LEN)
    E(b_cond, "sr_l", "lo")
    E(mov_reg, 0, 4)
    E(mov_reg, 1, 5)
    E(bl, "c_scsum")
    E(ldrb_imm, 1, 5, SC_LEN - 1)
    E(cmp_reg, 0, 1)
    E(b_cond, "sr_n", "ne")
    E(movs_imm, 0, 1)
    E(pop_list, [4, 5, 6, 7], pc=True)
    a.label("sr_n")
    E(movs_imm, 0, 0)
    E(pop_list, [4, 5, 6, 7], pc=True)

    # ---- c_scwr(r0 = scene, r1 = buf, r2 = 1 lists / 0 none): the scene's 29 B (none: zeros); clobbers r0-r3
    a.label("c_scwr")
    E(push_list, [4, 5, 6, 7], lr=True)
    E(mov_reg, 4, 0)
    E(mov_reg, 5, 1)
    E(cmp_imm, 4, 16)
    E(b_cond, "sw_x", "hs")
    E(cmp_imm, 2, 0)
    E(b_cond, "sw_v", "ne")
    E(movs_imm, 2, 0)
    E(movs_imm, 3, 0)
    a.label("sw_z")
    E(strb_reg, 3, 5, 2)
    E(adds_imm8, 2, 1)
    E(cmp_imm, 2, SC_LEN)
    E(b_cond, "sw_z", "lo")
    E(b, "sw_w")
    a.label("sw_v")
    E(mov_reg, 0, 4)
    E(mov_reg, 1, 5)
    E(bl, "c_scsum")
    E(strb_imm, 0, 5, SC_LEN - 1)
    a.label("sw_w")
    E(bl, L["c_rrt"])
    E(cmp_imm, 0, 0)
    E(b_cond, "sw_x", "eq")
    E(mov_reg, 6, 0)
    E(movs_imm, 7, 0)
    a.label("sw_l")
    E(mov_reg, 0, 4)
    E(mov_reg, 1, 7)
    E(mov_reg, 2, 6)
    E(bl, "c_scad")
    E(ldrb_reg, 1, 5, 7)
    E(strb_imm, 1, 0, 0)
    E(adds_imm8, 7, 1)
    E(cmp_imm, 7, SC_LEN)
    E(b_cond, "sw_l", "lo")
    a.label("sw_x")
    E(pop_list, [4, 5, 6, 7], pc=True)

    # ---- c_scsave(r0 = scene): the tracks' lists into the scene; clobbers r0-r3
    a.label("c_scsave")
    E(push_list, [4, 5, 6, 7], lr=True)
    E(sub_sp_imm, 32)
    E(mov_reg, 4, 0)
    E(movs_imm, 0, 0)
    for o in range(0, 32, 4):
        E(str_sp, 0, o)
    E(movs_imm, 7, 0)
    E(bl, "c_mtblk")
    E(cmp_imm, 0, 0)
    E(b_cond, "sv_w", "eq")
    E(mov_reg, 6, 0)
    E(movs_imm, 5, 0)
    a.label("sv_t")
    E(movs_imm, 0, LIST_LEN)
    E(muls, 0, 5)
    E(adds_reg, 0, 0, 6)
    E(ldrb_imm, 3, 0, B_LISTS)                            # the length
    E(cmp_imm, 3, 8)
    E(b_cond, "sv_n", "hi")
    E(orrs_reg, 7, 3)
    E(push_list, [0, 3])
    E(movs_imm, 1, 28)
    E(muls, 1, 5)
    E(movs_imm, 2, 4)
    E(raw, h(0xA802))                                     # add r0, sp, #8
    E(bl, "c_scput")
    E(pop_list, [0, 3])
    E(movs_imm, 1, 0)                                     # slot j (r1) of r3
    a.label("sv_j")
    E(cmp_reg, 1, 3)
    E(b_cond, "sv_n", "hs")
    E(push_list, [0, 1, 3])
    E(adds_reg, 2, 0, 1)
    E(ldrb_imm, 3, 2, B_LISTS + 1)
    E(movs_imm, 2, 7)
    E(ands_reg, 3, 2)
    E(movs_imm, 2, 3)
    E(muls, 2, 1)
    E(movs_imm, 1, 28)
    E(muls, 1, 5)
    E(adds_reg, 1, 1, 2)
    E(adds_imm8, 1, 4)
    E(movs_imm, 2, 3)
    E(raw, h(0xA803))                                     # add r0, sp, #12
    E(bl, "c_scput")
    E(pop_list, [0, 1, 3])
    E(adds_imm8, 1, 1)
    E(b, "sv_j")
    a.label("sv_n")
    E(adds_imm8, 5, 1)
    E(cmp_imm, 5, 8)
    E(b_cond, "sv_t", "lo")
    a.label("sv_w")
    E(mov_reg, 0, 4)
    E(mov_reg, 1, 13)
    E(mov_reg, 2, 7)
    E(bl, "c_scwr")
    E(add_sp_imm, 32)
    E(pop_list, [4, 5, 6, 7], pc=True)

    # ---- c_sccopy(r0 = from, r1 = to): a scene's lists into another (none: none); clobbers r0-r3
    a.label("c_sccopy")
    E(push_list, [4, 5, 6, 7], lr=True)
    E(sub_sp_imm, 32)
    E(mov_reg, 4, 0)
    E(mov_reg, 5, 1)
    E(cmp_reg, 4, 5)
    E(b_cond, "sc_x", "eq")
    E(mov_reg, 1, 13)
    E(bl, "c_scrd")
    E(mov_reg, 2, 0)
    E(mov_reg, 0, 5)
    E(mov_reg, 1, 13)
    E(bl, "c_scwr")
    a.label("sc_x")
    E(add_sp_imm, 32)
    E(pop_list, [4, 5, 6, 7], pc=True)

    # ---- c_scclr(r0 = scene): no lists in the scene; clobbers r0-r3
    a.label("c_scclr")
    E(push_list, [4], lr=True)
    E(sub_sp_imm, 32)
    E(mov_reg, 1, 13)
    E(movs_imm, 2, 0)
    E(bl, "c_scwr")
    E(add_sp_imm, 32)
    E(pop_list, [4], pc=True)

    # ---- c_scget(r0 = scene, r1 = track, r2 = peek) -> r0 = the scene's slot 1 for the track, 0xFF = none (no lists in the scene, or
    #      none for the track); not peek: the list becomes the track's (slot 1 playing), none ends the track's list; clobbers r1-r3
    a.label("c_scget")
    E(push_list, [4, 5, 6, 7], lr=True)
    E(sub_sp_imm, 32)
    E(mov_reg, 4, 0)
    E(mov_reg, 5, 1)
    E(mov_reg, 6, 2)
    E(mov_reg, 1, 13)
    E(bl, "c_scrd")
    E(cmp_imm, 0, 0)
    E(b_cond, "sg_no", "eq")
    E(mov_reg, 0, 13)
    E(movs_imm, 1, 28)
    E(muls, 1, 5)
    E(movs_imm, 2, 4)
    E(bl, "c_scbits")
    E(mov_reg, 7, 0)
    E(cmp_imm, 7, 0)
    E(b_cond, "sg_no", "eq")
    E(cmp_imm, 7, 8)
    E(b_cond, "sg_no", "hi")
    E(mov_reg, 0, 13)
    E(movs_imm, 1, 28)
    E(muls, 1, 5)
    E(adds_imm8, 1, 4)
    E(movs_imm, 2, 3)
    E(cmp_imm, 6, 0)
    E(b_cond, "sg_ld", "eq")
    E(bl, "c_scbits")
    E(b, "sg_x")
    a.label("sg_ld")
    E(bl, "c_mtw")
    E(cmp_imm, 0, 0)
    E(b_cond, "sg_ff", "eq")
    E(mov_reg, 6, 0)                                      # r6 = the block, r4 = the track's list
    E(movs_imm, 4, LIST_LEN)
    E(muls, 4, 5)
    E(adds_imm8, 4, B_LISTS)
    E(adds_reg, 4, 4, 6)
    crit_in()
    E(strb_imm, 7, 4, 0)
    E(movs_imm, 7, 0)
    a.label("sg_j")
    E(movs_imm, 2, 3)
    E(muls, 2, 7)
    E(movs_imm, 1, 28)
    E(muls, 1, 5)
    E(adds_reg, 1, 1, 2)
    E(adds_imm8, 1, 4)
    E(movs_imm, 2, 3)
    E(mov_reg, 0, 13)
    E(bl, "c_scbits")
    E(adds_reg, 3, 4, 7)
    E(strb_imm, 0, 3, 1)
    E(adds_imm8, 7, 1)
    E(cmp_imm, 7, 8)
    E(b_cond, "sg_j", "lo")
    E(mov_reg, 0, 6)
    E(bl, "c_mtfix")
    crit_out()
    imm32(1, SLOT)
    E(adds_reg, 1, 1, 5)
    E(movs_imm, 2, 0)
    E(strb_imm, 2, 1, O_POS)
    E(ldrb_imm, 0, 4, 1)
    E(b, "sg_x")
    a.label("sg_no")
    E(cmp_imm, 6, 0)
    E(b_cond, "sg_ff", "ne")
    E(mov_reg, 0, 5)
    E(bl, "c_mtcl")
    a.label("sg_ff")
    E(movs_imm, 0, 0xFF)
    a.label("sg_x")
    E(add_sp_imm, 32)
    E(pop_list, [4, 5, 6, 7], pc=True)

    # ---- c_scmsg (the scene commands' handler, slot 1 of 0x08068B14: r0 = obj, r1 = the command, r2, r3, [sp]): ours, then the stock's
    if scenefix:
        a.label("c_scmsg2")                               # slot 0 of 0x08068B24: r0 = obj + 4
        E(subs_imm8, 0, 4)
    a.label("c_scmsg")
    E(push_list, [4, 5, 6, 7], lr=True)
    E(sub_sp_imm, 12)
    E(mov_reg, 4, 0)
    E(mov_reg, 5, 1)
    E(mov_reg, 6, 2)
    E(mov_reg, 7, 3)
    E(ldr_sp, 0, 32)
    E(str_sp, 0, 0)
    E(ldr_imm, 0, 4, 0x70)
    E(cmp_reg, 5, 0)
    E(b_cond, "sm_c", "ne")
    E(lsls_imm, 0, 6, 24)                                 # save scene r2
    E(lsrs_imm, 0, 0, 24)
    E(bl, "c_scsave")
    E(b, "sm_go")
    a.label("sm_c")
    E(ldr_imm, 0, 4, 0x68)
    E(cmp_reg, 5, 0)
    E(b_cond, "sm_go", "ne")
    E(lsls_imm, 1, 7, 24)
    E(lsrs_imm, 1, 1, 24)
    E(cmp_imm, 6, 1)
    E(b_cond, "sm_cl", "ne")
    E(raw, ldrb_w(0, 4, 0x65))                            # paste: the copied scene into r3
    E(bl, "c_sccopy")
    E(b, "sm_go")
    a.label("sm_cl")
    E(cmp_imm, 6, 2)
    E(b_cond, "sm_go", "ne")
    E(mov_reg, 0, 1)                                      # clear scene r3
    E(bl, "c_scclr")
    a.label("sm_go")
    E(mov_reg, 0, 4)
    E(mov_reg, 1, 5)
    E(mov_reg, 2, 6)
    E(mov_reg, 3, 7)
    E(bl, L["prev_scmsg"])
    E(add_sp_imm, 12)
    E(pop_list, [4, 5, 6, 7], pc=True)


def rhrec_tail():
    import rhrec
    return rhrec.TAIL


def install(img, report, base_addr, randfill=False, mutate=False, listpads=False, scenecut=False, pagebyte=False, dimrest=False,
            clearall=False, liststart=False, scenesave=False, greendup=False, pageclr=False, shiftstock=False, shiftpads=False,
            pclrv=False, scenefix=False, stocktrk=False, cleardark=False, memlvl=MEMBER, clrnone=False, restlvl=VDIM,
            amount=False, norep=False, keep1=False, hidepause=False, vlock=False):
    import rhbuild
    import rhrec
    import tmenu as T
    BASE = rhbuild.BASE
    u32 = lambda a: int.from_bytes(img[a - BASE:a - BASE + 4], "little")
    need = SLOT_MUT if mutate else SLOT_LEN
    assert "tmenu" in report and "mutset" in rhstate.OFF and rhstate.OFF["mutset"][1] >= need, "mutset: after tmenu, ourram's slot"
    used = ((2, 132), (136, 36), (172, 20), (384, 20), (420, 100), (530, 10), (548, 200))   # the tail blocks of fshape, tmenu, Stock+
    assert all(BLK_OFF + BLK_LEN <= o or o + n <= BLK_OFF for o, n in used) and BLK_OFF + BLK_LEN <= rhrec.FREE_LEN
    assert B_LISTS + LIST_LEN * 8 <= B_RENEW < B_VAL2 < BLK_LEN
    assert all(SC_TOFF + 16 * SC_TLEN <= o or o + n <= SC_TOFF for o, n in used + ((BLK_OFF, BLK_LEN),))
    assert SC_TOFF + 16 * SC_TLEN <= rhrec.FREE_LEN and 16 + 6 + SC_TLEN == SC_LEN
    ci = {k: int(v, 16) for k, v in report["countin"]["labels"].items()}
    L = dict(c_ciok=ci["c_ciok"], c_cishift=ci["c_cishift"], c_tmscl=int(report["tmenu"]["labels"]["c_tmscl"], 16),
             c_rrt=int(report["rhrec"]["labels"]["c_rrt"], 16),
             prev_btn=rhbuild.bw_target(img, C.BTN_ENTRY), prev_rel=rhbuild.bw_target(img, C.BTN_RELEASE),
             prev_out=rhbuild.bl_target(img, T.OUT_CALL), prev_pad=u32(PV_VT) & ~1, prev_pr=u32(PV_VT + 4) & ~1,
             prev_mix=u32(MIX_VT) & ~1, prev_mixr=u32(MIX_VT + 4) & ~1, prev_scmsg=u32(SCMSG_VT) & ~1)
    base_addr = (base_addr + 3) & ~3
    code, labels = arm_code(base_addr, L, randfill=randfill, mutate=mutate, listpads=listpads, scenecut=scenecut, pagebyte=pagebyte,
                            dimrest=dimrest, clearall=clearall, liststart=liststart, scenesave=scenesave, greendup=greendup,
                            pageclr=pageclr, shiftstock=shiftstock, shiftpads=shiftpads, pclrv=pclrv, scenefix=scenefix, stocktrk=stocktrk, cleardark=cleardark, memlvl=memlvl, clrnone=clrnone, restlvl=restlvl, amount=amount, norep=norep, keep1=keep1,
                            hidepause=hidepause, vlock=vlock)
    img += bytes([0xFF]) * (base_addr - BASE - len(img)) + code
    while len(img) % 4:
        img += bytes([0xFF])
    from thumb import bl as bl_ins, b_w as bw_ins
    rhbuild.patch(img, C.BTN_ENTRY, f"b.w #{L['prev_btn']:#x}", bw_ins(C.BTN_ENTRY, labels["c_msbtn"]))
    rhbuild.patch(img, C.BTN_RELEASE, f"b.w #{L['prev_rel']:#x}", bw_ins(C.BTN_RELEASE, labels["c_msrel"]))
    rhbuild.patch(img, T.OUT_CALL, f"bl #{L['prev_out']:#x}", bl_ins(T.OUT_CALL, labels["c_msout"]))
    rhbuild.patch_word(img, PV_VT, L["prev_pad"] | 1, labels["c_mspad"] | 1)
    rhbuild.patch_word(img, PV_VT + 4, L["prev_pr"] | 1, labels["c_mspr"] | 1)
    if mutate:
        rhbuild.patch(img, NEXT_SITE, "ldrb.w r2, [sp, #1]", bl_ins(NEXT_SITE, labels["c_mtnext"]))
    if scenesave:
        rhbuild.patch_word(img, SCMSG_VT, L["prev_scmsg"] | 1, labels["c_scmsg"] | 1)
    if scenefix:
        rhbuild.patch_word(img, SCMSG_VT2, (L["prev_scmsg"] - 4) | 1, labels["c_scmsg2"] | 1)
    if liststart:
        rhbuild.patch(img, SEEK_SITE, "ldrb r4, [r0]|ldr r0, [r5]", bl_ins(SEEK_SITE, labels["c_mtseek"]))
    if scenecut:
        rhbuild.patch_word(img, MIX_VT, L["prev_mix"] | 1, labels["c_mxpad"] | 1)
        rhbuild.patch_word(img, MIX_VT + 4, L["prev_mixr"] | 1, labels["c_mxpr"] | 1)
    report["mutset"] = dict(slot=hex(rhstate.ST + rhstate.OFF["mutset"][0]), hold_ms=HOLD_MS, blk_off=BLK_OFF, blk_len=BLK_LEN,
                            **({"randfill": True} if randfill else {}), **({"mutate": True} if mutate else {}), **({"listpads": True} if listpads else {}), **({"scenecut": True} if scenecut else {}), **({"pagebyte": True} if pagebyte else {}), **({"dimrest": True} if dimrest else {}), **({"clearall": True} if clearall else {}),
                            **({"liststart": True} if liststart else {}), **({"scenesave": True} if scenesave else {}),
                            **({"greendup": True} if greendup else {}), **({"pageclr": True} if pageclr else {}),
                            **({"shiftstock": True} if shiftstock else {}), **({"shiftpads": True} if shiftpads else {}),
                            **({"pclrv": True} if pclrv else {}), **({"scenefix": True} if scenefix else {}),
                            **({"stocktrk": True} if stocktrk else {}), **({"cleardark": True} if cleardark else {}),
                            **({"memlvl": memlvl} if memlvl != MEMBER else {}), **({"clrnone": True} if clrnone else {}),
                            **({"restlvl": restlvl} if restlvl != VDIM else {}), **({"amount": True} if amount else {}),
                            **({"norep": True} if norep else {}), **({"keep1": True} if keep1 else {}),
                            **({"hidepause": True} if hidepause else {}), **({"vlock": True} if vlock else {}),
                            labels={k: hex(v) for k, v in labels.items() if k.startswith("c_")})
    return labels, code
