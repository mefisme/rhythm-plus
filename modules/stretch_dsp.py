"""Time stretch engine on DSP core 0: `tools/stretch_block.py` in DSP56300 code, one track a call.

st_block runs one 32-sample block of the track whose state is X:(r7..), with the globals G_* set; its words
go to Y:OUT. State, scratch and tables use core 0 X/Y words the ledger lists as free. st_block uses a, b,
x, y, r0-r7, n0-n7 (r7 = the track's state) and needs m0-m7 linear. Only the eight valid multiply pairs
are used; `voicefx.check` rejects the others.
"""
import re

import stretch_block as M

AT = 0x3000                     # P: inside the ledger's largest free core 0 block, $2D6D..$3FDF
ST_X, ST_STRIDE = 0x5000, 64    # X: per-track state
SCR, SCR_N = 0x5200, 1728       # X: candidate words of the search
TSCR, TSCR_N = 0x58C0, 768      # X: template words of the search
LB, LB_N = 0x5BC0, 136          # X: one head's words for a block
SB = 0x5C48                     # X: 129 words of one hit-analysis block
GT = 0x5CD0                     # X: gain tables, hop (49 words) then hit (4)
GT_LOCK = GT + M.HOP_BLOCKS + 1
OUT, TMP = 0x1460, 0x1480       # Y: the block's output, one head's samples
TPLC, TPLF = 0x14A0, 0x14D0     # Y: template words (48, 192)
OFFC, OFFF = 0x1590, 0x15C0     # Y: search offsets (48, 192)
GV = 0x1680                     # Y: globals
NC_POINTS, NF_POINTS = M.TL // M.CDEC, M.TL // M.FDEC
COARSE_PER_STAGE = 31            # stages 2-5 hold every coarse candidate
assert 4 * COARSE_PER_STAGE >= 2 * M.DELTA // M.CSTEP + 1
RATE_MAX = 4 << 24              # one head's block copy fits LB
LIFE = 0x675331

(G_S, G_N, G_REV, G_LOOP, G_PTAB, G_SPI, G_SPF, G_RTI, G_RTF, G_TRK, G_OWN, G_CI, G_CN, G_V, G_RUN,
 G_LI, G_LF, G_TG, G_LO, G_HI, G_BC, G_NC, G_B0, G_B1, G_B2, G_BF, G_FLO, G_FHI, G_SPAN, G_K,
 G_E, G_T0, G_T1, G_T2, G_T3, G_HN, G_G0, G_STEP, G_T4, G_T5, G_Q0, G_Q1, G_Q2, G_SEEN, G_INIT, G_TGT, G_WHL, G_AT) = range(48)
GV_WORDS = 48                   # G_Q0..Q2: the scan's block energy (the search keeps its best in G_B0..B2)
INIT_KEY = 0x675349             # G_INIT holds it once the gain tables are in X
HOST_KEY = 0x675354             # word 15 of a track's host parameters: this track stretches
H_SPD, H_TGT = 0, 2                  # host parameter words: speed Q20, or a length in samples (0 = the speed word); Granular's
                                     # knob pushes never write words 0, 2 and 15
SSD_CHUNK = 8                        # points between st_ssd's early-stop tests
TGT_PART = 1 << 22                   # in word 2: fit the region (start to end), not the whole sample
SPEED_MIN = 1 << 22                  # 0.25 in Q24; a length's speed stays in SPEED_MIN .. RATE_MAX
READER_LEAD = 0x180                  # core 1's native reader fills its ring this far ahead of its output
RESUME_GAP = 8                       # blocks without the engine after which it resumes where the native reader is
RESUME_MIN = 0x100                   # a resume this close to the start starts at 0 (a new note)
(S_LIFE, S_EPOCH, S_SERIAL, S_PI, S_PF, S_NH) = range(6)
S_H = 6                         # 3 heads x (position int, position frac, gain at fade start, gain at fade end)
(S_FJ, S_TAB, S_TOS, S_FLOOR, S_NON) = range(18, 23)
S_ONS = 23                      # 4 hits
S_SCAN = 27                     # the next analysis block's first index
S_EH = 28                       # 4 energies
(S_NEH, S_TOP, S_LAST, S_STG, S_KEEP, S_STI, S_STF, S_TABN) = range(32, 40)
S_FRM = 40                      # the frame of the engine's last block
STATE_WORDS = 41


def g(k):
    return f"y:>${GV + k:x}"


def sx(k):
    return f"x:(r7+${k:x})"


def acc_load(acc, k):
    """acc = the 56-bit value at globals k (bits 0-23), k + 1 (24-47), k + 2 (48-55)."""
    return [f"move {g(k + 1)},{acc}", f"move {g(k)},{acc}0", f"move {g(k + 2)},{acc}2"]


def acc_save(acc, k):
    return [f"move {acc}2,{g(k + 2)}", f"move {acc}1,{g(k + 1)}", f"move {acc}0,{g(k)}"]


def own_test(skip):
    """Falls through when this track owns the search."""
    return [f"move {g(G_OWN)},a", f"move {g(G_TRK)},b", "add #>$1,b", "cmp b,a", ("jcc", "ne", skip)]


def copy_items():
    """st_copy: X:(r5).. = G_CN half-level words from region index G_CI. Outside the region: 0 for a
    one-shot, the region again for a loop. Reverse reads the region from its end."""
    return [
        ("label", "st_copy"),
        ("label", "stc_next"), f"move {g(G_CN)},a", "tst a", ("jcc", "le", "stc_done"),
        f"move {g(G_CI)},a", f"move {g(G_LOOP)},b", "tst b", ("jcc", "ne", "stc_wrap"),
        "tst a", ("jcc", "ge", "stc_inside"),
        "neg a", f"move {g(G_CN)},x0", "cmp x0,a", "tgt x0,a", "move a1,x1", "clr a",
        "do x1,${stc_z0:x}", "move a,x:(r5)+", ("label", "stc_z0"), ("jmp", "stc_adv"),
        ("label", "stc_inside"), f"move {g(G_N)},x0", "cmp x0,a", ("jcc", "lt", "stc_run"),
        f"move {g(G_CN)},x1", "clr a", "do x1,${stc_z1:x}", "move a,x:(r5)+", ("label", "stc_z1"), ("jmp", "stc_done"),
        ("label", "stc_wrap"), f"move {g(G_N)},x0",
        ("label", "stc_wneg"), "tst a", ("jcc", "ge", "stc_wbig"), "add x0,a", ("jmp", "stc_wneg"),
        ("label", "stc_wbig"), "cmp x0,a", ("jcc", "lt", "stc_wok"), "sub x0,a", ("jmp", "stc_wbig"),
        ("label", "stc_wok"), f"move a1,{g(G_CI)}",
        ("label", "stc_run"), f"move {g(G_N)},b", "sub a,b", f"move {g(G_CN)},x0", "cmp x0,b", "tgt x0,b", f"move b1,{g(G_RUN)}",
        f"move {g(G_REV)},b", "tst b", ("jcc", "ne", "stc_rev"),
        f"move {g(G_S)},x0", "add x0,a", f"move a1,{g(G_V)}", ("jsr", "st_fwd"), ("jmp", "stc_ran"),
        ("label", "stc_rev"), f"move {g(G_S)},b", f"move {g(G_N)},x0", "add x0,b", "sub a,b", "sub #>$1,b", f"move b1,{g(G_V)}",
        ("jsr", "st_back"),
        ("label", "stc_ran"), f"move {g(G_RUN)},x1",
        ("label", "stc_adv"), f"move {g(G_CI)},a", "add x1,a", f"move a1,{g(G_CI)}",
        f"move {g(G_CN)},a", "sub x1,a", f"move a1,{g(G_CN)}", ("jmp", "stc_next"),
        ("label", "stc_done"), "rts",
        # st_page: r4 = the physical word of virtual G_V; x0 = its offset in the page
        ("label", "st_page"), f"move {g(G_V)},a", "move a1,y1", "lsr #12,a", "move a1,x0", "lsr a", f"move {g(G_PTAB)},x1",
        "add x1,a", "move a1,r4", "nop", "move y:(r4),b", "btst #$0,x0", ("jcc", "cs", "stp_odd"), "lsr #12,b",
        ("label", "stp_odd"), "and #>$fff,b", "asl #12,b,b", "move y1,a", "and #>$fff,a", "move a1,x0", "add x0,b",
        "move b1,r4", "rts",
    ] + [it for name, up in (("st_fwd", True), ("st_back", False)) for it in (
        # G_RUN words from virtual G_V up or down, page by page, halved into X:(r5)+
        ("label", name), f"move {g(G_RUN)},a", f"move a1,{g(G_T3)}",
        ("label", f"{name}_pg"), f"move {g(G_T3)},a", "tst a", ("jcc", "le", f"{name}_x"), ("jsr", "st_page"),
        *(["move #>$1000,b", "sub x0,b"] if up else ["move x0,b", "add #>$1,b"]),
        f"move {g(G_T3)},x1", "cmp x1,b", "tgt x1,b", "move b1,n4", "nop",
        f"do n4,${{{name}_cp:x}}", f"move y:(r4){'+' if up else '-'},a", "asr a", "move a1,x:(r5)+", ("label", f"{name}_cp"),
        f"move {g(G_V)},a", "move n4,x0", ("add x0,a" if up else "sub x0,a"), f"move a1,{g(G_V)}",
        f"move {g(G_T3)},a", "sub x0,a", f"move a1,{g(G_T3)}", ("jmp", f"{name}_pg"),
        ("label", f"{name}_x"), "rts")]


def scan_items():
    """st_scan: one hit-analysis block at X:(r7+S_SCAN) (stretch_block.Track.scan)."""
    eh = [sx(S_EH + k) for k in range(4)]
    return [
        ("label", "st_scan"), f"move {sx(S_SCAN)},a", f"move a1,{g(G_T0)}", "sub #>$1,a", f"move a1,{g(G_CI)}",
        f"move #>${M.OBLK + 1:x},a", f"move a1,{g(G_CN)}", f"move #>${SB:x},r5", ("jsr", "st_copy"),
        f"move #>${SB:x},r0", "clr b", "move x:(r0)+,x0", "move #$0,y0", f"do #${M.OBLK:x},${{scn_sum:x}}",
        "mac y0,y0,b x:(r0)+,a", "sub x0,a a1,x0", "move a1,y0", ("label", "scn_sum"), "mac y0,y0,b",
        *acc_save("b", G_Q0), "asr #7,b,b", f"move b1,{g(G_E)}",          # e = (2 sum) >> 31: bits 31-54 land in b1
        f"move {sx(S_TOP)},a", "cmp b,a", "tlt b,a", f"move a1,{sx(S_TOP)}",
        # a hit: 4 energies before it, 2e > 3 x their sum + 2 floor, 10e >= the loudest, far from the last, room in the list
        f"move {sx(S_NEH)},a", "cmp #>$4,a", ("jcc", "ne", "scn_hist"),
        f"move {eh[0]},a", f"move {eh[1]},x0", "add x0,a", f"move {eh[2]},x0", "add x0,a", f"move {eh[3]},x0", "add x0,a",
        "tfr a,b", "asl a", "add b,a", f"add #>${2 * M.OFLOOR:x},a", f"move {g(G_E)},b", "asl b", "cmp a,b", ("jcc", "le", "scn_hist"),
        f"move {g(G_E)},a", "asl #3,a,a", f"move {g(G_E)},x0", "add x0,a", "add x0,a", f"move {sx(S_TOP)},x0", "cmp x0,a",
        ("jcc", "lt", "scn_hist"),
        f"move {g(G_T0)},a", f"move {sx(S_LAST)},x0", "sub x0,a", f"cmp #>${M.OGAP:x},a", ("jcc", "le", "scn_hist"),
        f"move {sx(S_NON)},a", f"cmp #>${M.NONSETS:x},a", ("jcc", "ge", "scn_hist"),
        # where: the first k whose running sum reaches 1/8 of the block's (a = the threshold, the sum in G_T1..T3)
        *acc_load("a", G_Q0), "asr #3,a,a", "clr b", *acc_save("b", G_T1), f"move #>${SB:x},r0", "move #>$0,r1",
        ("label", "scn_k"), "move x:(r0)+,x0", "move x:(r0),b", "sub x0,b", "move b1,x0",
        *acc_load("b", G_T1), "mac x0,x0,b", *acc_save("b", G_T1),
        "cmp a,b", ("jcc", "ge", "scn_found"), "move (r1)+", ("jmp", "scn_k"),
        ("label", "scn_found"), "move r1,a", f"move {g(G_T0)},x0", "add x0,a", "sub #>$10,a", "tst a", ("jcc", "ge", "scn_pos"), "clr a",
        ("label", "scn_pos"), f"move {sx(S_NON)},b", "move b1,n0", f"move #>${S_ONS:x},b", "move r7,x0", "add x0,b", "move b1,r0",
        "nop", "move a1,x:(r0+n0)", f"move {sx(S_NON)},b", "add #>$1,b", f"move b1,{sx(S_NON)}",
        f"move {g(G_T0)},a", f"move a1,{sx(S_LAST)}",
        # the last four energies
        ("label", "scn_hist"), f"move {g(G_E)},y0", f"move {sx(S_NEH)},a", "cmp #>$4,a", ("jcc", "lt", "scn_app"),
        f"move {eh[1]},x0", f"move x0,{eh[0]}", f"move {eh[2]},x0", f"move x0,{eh[1]}", f"move {eh[3]},x0", f"move x0,{eh[2]}",
        f"move y0,{eh[3]}", ("jmp", "scn_next"),
        ("label", "scn_app"), "move a1,n0", f"move #>${S_EH:x},b", "move r7,x0", "add x0,b", "move b1,r0", "nop",
        "move y0,x:(r0+n0)", "add #>$1,a", f"move a1,{sx(S_NEH)}",
        ("label", "scn_next"), f"move {sx(S_SCAN)},a", f"add #>${M.OBLK:x},a", f"move a1,{sx(S_SCAN)}", "rts"]


def head_items():
    return [
        # st_gain: a1 = the gain of head X:(r6..) at fade block min(G_K, its table's last)
        ("label", "st_gain"), f"move {sx(S_TABN)},x0", f"move {g(G_K)},a", "cmp x0,a", "tgt x0,a", "move a1,n0",
        f"move {sx(S_TAB)},r0", "nop", "move x:(r0+n0),y0",
        "move x:(r6+$3),a", "move x:(r6+$2),x0", "sub x0,a", "move a1,x1", "mpy x1,y0,a", "add x0,a", "rts",
        # st_splice: a new head at (G_T0, G_T1), fading in by table r1 (last index n1); the others fade out from their gains now
        ("label", "st_splice"), f"move {sx(S_FJ)},a", f"move a1,{g(G_K)}",
        f"move #>${S_H:x},a", "move r7,x0", "add x0,a", "move a1,r6", "move a1,r2", "move #>$4,n6", "move #>$4,n2",
        "move #>$0,r3", f"move {sx(S_NH)},a", "tst a", ("jcc", "le", "spl_new"),
        "do a1,${spl_each:x}", ("jsr", "st_gain"), "tst a", ("jcc", "le", "spl_drop"),
        "move x:(r6),x0", "move x0,x:(r2)", "move x:(r6+$1),x0", "move x0,x:(r2+$1)", "move a1,x:(r2+$2)", "clr a",
        "move a,x:(r2+$3)", "move (r2)+n2", "move (r3)+",
        ("label", "spl_drop"), "move (r6)+n6", ("label", "spl_each"),
        ("label", "spl_new"), f"move {g(G_T0)},x0", "move x0,x:(r2)", f"move {g(G_T1)},x0", "move x0,x:(r2+$1)",
        "clr b", "move b,x:(r2+$2)", "move #>$7fffff,b", "move b,x:(r2+$3)", "move r3,a", "add #>$1,a", f"move a1,{sx(S_NH)}",
        "clr a", f"move a1,{sx(S_FJ)}", f"move r1,{sx(S_TAB)}", f"move n1,{sx(S_TABN)}", "rts"]


def search_items():
    best_max = ["move #>$7f,a2", "move #>$ffffff,a1", "move #>$ffffff,a0", *acc_save("a", G_B0)]

    def seed(off, tpl, n):
        """the best starts as candidate G_K's sum + 1: st_ssd stops early from the first candidate, and the first lowest still wins"""
        return [*best_max, f"move #>${off:x},r2", f"move #>${tpl:x},r6", f"move #>${n:x},n7", ("jsr", "st_ssd"), "move #>$0,y1", "move #>$1,y0", "add y,b",
                *acc_save("b", G_B0), f"move {g(G_K)},x0", f"move x0,{g(G_BF)}"]
    fine_run = ["move #>$1,a", f"move a1,{g(G_T4)}", f"move #>${OFFF:x},r1", f"move #>${TPLF:x},n1", f"move #>${NF_POINTS:x},n5",
                ("jsr", "st_cands")]
    L = [
        # st_ssd: b = 2 x the squared difference from the template at candidate G_K (offsets r2, template r6, n7 points, a multiple
        # of SSD_CHUNK); it stops once b passes G_B0..2 (the sum only grows, so the candidate cannot win: the result is the same)
        ("label", "st_ssd"), f"move {g(G_K)},a", f"move {g(G_LO)},x0", "sub x0,a", f"add #>${SCR:x},a", "move a1,r3", "clr b",
        "move n7,a", f"asr #{SSD_CHUNK.bit_length() - 1},a,a", f"move a1,{g(G_T3)}",
        ("label", "ssd_k"), f"do #${SSD_CHUNK:x},${{ssd_c:x}}",
        "move y:(r2)+,n3", "move y:(r6)+,a", "move x:(r3+n3),x0", "sub x0,a", "move a1,x0", "mac x0,x0,b", ("label", "ssd_c"),
        *acc_load("a", G_B0), "cmp a,b", ("jcc", "gt", "ssd_x"),
        f"move {g(G_T3)},a", "sub #>$1,a", f"move a1,{g(G_T3)}", ("jcc", "gt", "ssd_k"),
        ("label", "ssd_x"), "rts",
        # st_best: b below the best: it becomes the best, G_K its candidate (G_BF)
        ("label", "st_best"), *acc_load("a", G_B0), "cmp a,b", ("jcc", "ge", "bst_x"),
        *acc_save("b", G_B0), f"move {g(G_K)},x0", f"move x0,{g(G_BF)}", ("label", "bst_x"), "rts",
        # st_cands: candidates G_T0..G_T1 (step G_T4) with offsets r1, template n1, points n5
        ("label", "st_cands"), f"move {g(G_T0)},a", f"move {g(G_T1)},x0", "cmp x0,a", ("jcc", "gt", "cnd_x"),
        f"move a1,{g(G_K)}", "move r1,r2", "move n1,r6", "move n5,n7", ("jsr", "st_ssd"), ("jsr", "st_best"),
        f"move {g(G_T0)},a", f"move {g(G_T4)},x0", "add x0,a", f"move a1,{g(G_T0)}", ("jmp", "st_cands"),
        ("label", "cnd_x"), "rts",
        # st_stage: search stage X:(r7+S_STG) - 1
        ("label", "st_stage"), f"move {sx(S_STG)},a", "sub #>$1,a",
        ("jcc", "eq", "stg0"), "cmp #>$1,a", ("jcc", "eq", "stg1"),
        "cmp #>$6,a", ("jcc", "lt", "stg_coarse"), "cmp #>$6,a", ("jcc", "eq", "stg6"), ("jmp", "stg7"),
        # stage 0: the offsets (rate at most 2x), the template, the window [lo, hi]
        ("label", "stg0"), f"move {g(G_RTI)},a", f"move {g(G_RTF)},a0", "clr b", f"move #>${M.RATE_SEARCH_MAX >> 24:x},b1",
        "cmp b,a", "tgt b,a", "move a1,y1", "move a0,y0"]
    for tab, dec, n in ((OFFC, M.CDEC, NC_POINTS), (OFFF, M.FDEC, NF_POINTS)):
        L += ["move y1,a", "move y0,a0", f"asl #{dec.bit_length() - 1},a,a", "clr b", "move #>$800000,b0", f"move #>${tab:x},r0",
              f"do #${n:x},${{off_{tab:x}:x}}", "move b1,y:(r0)+", "add a,b", ("label", f"off_{tab:x}")]
    L += [f"move y:>${OFFF + NF_POINTS - 1:x},a", "add #>$1,a", f"move a1,{g(G_CN)}", f"move {g(G_LI)},a", f"move a1,{g(G_CI)}",
          f"move #>${TSCR:x},r5", ("jsr", "st_copy")]
    for off, tpl, n in ((OFFC, TPLC, NC_POINTS), (OFFF, TPLF, NF_POINTS)):
        L += [f"move #>${off:x},r2", f"move #>${tpl:x},r6", f"move #>${TSCR:x},r0",
              f"do #${n:x},${{tpl_{tpl:x}:x}}", "move y:(r2)+,n0", "nop", "move x:(r0+n0),x0", "move x0,y:(r6)+", ("label", f"tpl_{tpl:x}")]
    L += [f"move {g(G_TG)},a", f"sub #>${M.DELTA:x},a", f"move {sx(S_FLOOR)},x0", "cmp x0,a", "tlt x0,a", f"move a1,{g(G_LO)}",
          "move a1,x0", f"move {g(G_TG)},a", f"add #>${M.DELTA:x},a", "cmp x0,a", "tlt x0,a", f"move a1,{g(G_HI)}",
          "sub x0,a", "move a1,b", "asr #3,b,b", "add #>$1,b", f"move b1,{g(G_NC)}",
          f"move y:>${OFFF + NF_POINTS - 1:x},x0", "add x0,a", "add #>$1,a", f"move a1,{g(G_SPAN)}", "rts",
          # stage 1: the candidate words
          ("label", "stg1"), f"move {g(G_SPAN)},a", f"move a1,{g(G_CN)}", f"move {g(G_LO)},a", f"move a1,{g(G_CI)}",
          f"move #>${SCR:x},r5", ("jsr", "st_copy"), "rts",
          # stages 2-5: coarse candidates lo + 8m, m = C (stage - 2) .. min(that + C - 1, NC - 1), C = COARSE_PER_STAGE
          ("label", "stg_coarse"), "sub #>$2,a", "move a1,x1", "tst a", ("jcc", "ne", "stc_m0"),
          # the seed: the coarse candidate nearest the lead head
          f"move {g(G_LI)},a", f"move {g(G_LO)},x0", "sub x0,a", "add #>$4,a", "clr b", "cmp b,a", "tlt b,a", "and #>$fffff8,a",
          f"move {g(G_NC)},b", "sub #>$1,b", "asl #3,b,b", "cmp b,a", "tgt b,a",
          "add x0,a", f"move a1,{g(G_K)}", *seed(OFFC, TPLC, NC_POINTS),
          ("label", "stc_m0"), f"move #>${COARSE_PER_STAGE:x},x0", "mpy x1,x0,b", "asr b", "move b0,b",
          f"move b1,{g(G_T2)}", f"add #>${COARSE_PER_STAGE:x},b", f"move {g(G_NC)},x0", "cmp x0,b", "tgt x0,b", "sub #>$1,b",
          "asl #3,b,b", f"move {g(G_LO)},x0", "add x0,b", f"move b1,{g(G_T1)}",
          f"move {g(G_T2)},a", "asl #3,a,a", "add x0,a", f"move a1,{g(G_T0)}", f"move #>${M.CSTEP:x},a", f"move a1,{g(G_T4)}",
          f"move #>${OFFC:x},r1", f"move #>${TPLC:x},n1", f"move #>${NC_POINTS:x},n5", ("jsr", "st_cands"),
          f"move {g(G_BF)},x0", f"move x0,{g(G_BC)}", "rts",
          # stage 6: the fine window around the coarse best, its first 8 candidates
          ("label", "stg6"),
          f"move {g(G_BC)},a", f"sub #>${M.FRANGE:x},a", f"move {g(G_LO)},x0", "cmp x0,a", "tlt x0,a", f"move a1,{g(G_FLO)}",
          f"move {g(G_BC)},a", f"add #>${M.FRANGE:x},a", f"move {g(G_HI)},x0", "cmp x0,a", "tgt x0,a", f"move a1,{g(G_FHI)}",
          f"move {g(G_FLO)},a", f"move a1,{g(G_T0)}", "add #>$7,a", f"move {g(G_FHI)},x0", "cmp x0,a", "tgt x0,a", f"move a1,{g(G_T1)}",
          f"move {g(G_BC)},x0", f"move x0,{g(G_K)}", *seed(OFFF, TPLF, NF_POINTS), ("jmp", "fine_run"),
          # stage 7: the rest, then keep the running head or start at the best
          ("label", "stg7"), f"move {g(G_FLO)},a", "add #>$8,a", f"move a1,{g(G_T0)}", f"move {g(G_FHI)},a", f"move a1,{g(G_T1)}",
          *fine_run,
          "clr a", f"move a1,{sx(S_KEEP)}", f"move {g(G_LI)},a", f"move {g(G_LO)},x0", "cmp x0,a", ("jcc", "lt", "stf_start"),
          f"move {g(G_HI)},x0", "cmp x0,a", ("jcc", "gt", "stf_start"), f"move a1,{g(G_K)}",
          # the running head keeps on unless its sum passes the best + 1 / 1024: that limit in G_B0..2 lets st_ssd stop early
          *acc_load("b", G_B0), "tfr b,a", "asr #10,a,a", "add b,a", *acc_save("a", G_B0),
          f"move #>${OFFF:x},r2", f"move #>${TPLF:x},r6", f"move #>${NF_POINTS:x},n7", ("jsr", "st_ssd"), *acc_load("a", G_B0),
          "cmp a,b", ("jcc", "gt", "stf_start"), "move #>$1,a", f"move a1,{sx(S_KEEP)}",
          ("label", "stf_start"), f"move {g(G_BF)},a", f"move a1,{sx(S_STI)}", f"move {g(G_LF)},a", f"move a1,{sx(S_STF)}", "rts",
          ("label", "fine_run"), *fine_run, "rts"]
    return L


def block_items():
    heads_base = [f"move #>${S_H:x},a", "move r7,x0", "add x0,a"]
    speed = [f"move {g(G_SPI)},a", f"move {g(G_SPF)},a0"]
    rate = [f"move {g(G_RTI)},a", f"move {g(G_RTF)},a0"]
    pos_b = [f"move {sx(S_PI)},b", f"move {sx(S_PF)},b0"]
    return [
        # st_restart: a new note (stretch_block.Track.restart)
        ("label", "st_restart"), *own_test("rst_own"), "clr a", f"move a1,{g(G_OWN)}",
        ("label", "rst_own"), "clr a",
        *[f"move a1,{sx(k)}" for k in (S_PI, S_PF, S_H, S_H + 1, S_FLOOR, S_NON, S_NEH, S_TOP, S_STG, S_KEEP)],
        "move #>$7fffff,a", f"move a1,{sx(S_H + 2)}", f"move a1,{sx(S_H + 3)}", "move #>$1,a", f"move a1,{sx(S_NH)}",
        f"move #>${M.OBLK:x},a", f"move a1,{sx(S_SCAN)}",
        f"move #>${M.HOP_BLOCKS:x},a", f"move a1,{sx(S_FJ)}", f"move a1,{sx(S_TOS)}", f"move a1,{sx(S_TABN)}",
        f"move #>${GT:x},a", f"move a1,{sx(S_TAB)}", f"move #>${-M.OGAP - 1 & 0xFFFFFF:x},a", f"move a1,{sx(S_LAST)}", "rts",
        # st_at: after st_restart, start at region index G_AT (stretch_block.Track.restart(at))
        ("label", "st_at"), f"move {g(G_AT)},x0",
        *[w for k in (S_PI, S_H, S_FLOOR, S_SCAN, S_LAST) for w in (f"move {sx(k)},a", "add x0,a", f"move a1,{sx(k)}")], "rts",

        ("label", "st_block"),
        # a one-shot long past its end: silence, nothing moves
        f"move {g(G_LOOP)},a", "tst a", ("jcc", "ne", "blk_loop"),
        f"move {sx(S_PI)},a", f"move {g(G_N)},x0", "sub x0,a", f"cmp #>${M.ONESHOT_TAIL:x},a", ("jcc", "le", "blk_scan"),
        "clr a", f"move #>${OUT:x},r0", "rep #$20", "move a,y:(r0)+", "rts",
        # a loop past its end with no search running: every index back by the length
        ("label", "blk_loop"), f"move {sx(S_STG)},a", "tst a", ("jcc", "ne", "blk_scan"),
        f"move {sx(S_PI)},a", f"move {g(G_N)},x0", "cmp x0,a", ("jcc", "lt", "blk_scan"),
        *[s for k in (S_PI, S_FLOOR, S_SCAN, S_LAST) for s in (f"move {sx(k)},a", "sub x0,a", f"move a1,{sx(k)}")],
        f"move #>${S_H:x},a", "move r7,x1", "add x1,a", "move a1,r0", "move #>$4,n0", f"move {sx(S_NH)},a", "do a1,${blk_rh:x}",
        "move x:(r0),a", "sub x0,a", "move a1,x:(r0)+n0", ("label", "blk_rh"),
        f"move #>${S_ONS:x},a", "move r7,x1", "add x1,a", "move a1,r0", f"move {sx(S_NON)},a", "tst a", ("jcc", "le", "blk_scan"),
        "do a1,${blk_ro:x}", "move x:(r0),a", "sub x0,a", "move a1,x:(r0)+", ("label", "blk_ro"),
        # hits known up to P + LOOKAHEAD
        ("label", "blk_scan"), f"move {sx(S_SCAN)},a", f"move {sx(S_PI)},x0", "sub x0,a", f"cmp #>${M.LOOKAHEAD:x},a",
        ("jcc", "ge", "blk_hit"), ("jsr", "st_scan"), ("jmp", "blk_scan"),
        # a hit before P + 32 speed: a head starts so that the hit lands on its sample
        ("label", "blk_hit"), f"move {sx(S_NON)},a", "tst a", ("jcc", "le", "blk_search"),
        *speed, "asl #5,a,a", *pos_b, "add a,b", f"move {sx(S_ONS)},x0", "move b1,a", "cmp x0,a", ("jcc", "le", "blk_search"),
        f"move {sx(S_PI)},a", f"move {sx(S_PF)},a0", "clr b", f"move {sx(S_ONS)},b1",
        f"move {g(G_SPI)},y1", f"move {g(G_SPF)},y0", "move #>$0,r1",
        ("label", "blk_k"), "cmp b,a", ("jcc", "ge", "blk_kd"), "add y,a", "move (r1)+", ("jmp", "blk_k"),
        ("label", "blk_kd"), "tfr b,a", f"move {g(G_RTI)},y1", f"move {g(G_RTF)},y0", "move r1,b", "tst b", ("jcc", "eq", "blk_ks"),
        "do b1,${blk_kl:x}", "sub y,a", ("label", "blk_kl"),
        ("label", "blk_ks"), "tst a", ("jcc", "ge", "blk_kp"), "clr a",
        ("label", "blk_kp"), f"move a1,{g(G_T0)}", f"move a0,{g(G_T1)}",
        f"move #>${GT_LOCK:x},r1", f"move #>${M.LOCK_BLOCKS:x},n1", ("jsr", "st_splice"),
        f"move {sx(S_ONS)},a", f"add #>${M.HOLD:x},a", f"move a1,{sx(S_FLOOR)}",
        *[s for k in range(M.NONSETS - 1) for s in (f"move {sx(S_ONS + k + 1)},x0", f"move x0,{sx(S_ONS + k)}")],
        f"move {sx(S_NON)},a", "sub #>$1,a", f"move a1,{sx(S_NON)}",
        f"move #>${M.HOP_BLOCKS:x},a", f"move a1,{sx(S_TOS)}",
        *own_test("blk_render"), "clr a", f"move a1,{g(G_OWN)}", f"move a1,{sx(S_STG)}", ("jmp", "blk_render"),
        # the search starts SEARCH_STAGES blocks before its splice, when the scratch is free
        ("label", "blk_search"), f"move {sx(S_STG)},a", "tst a", ("jcc", "ne", "blk_step"),
        f"move {sx(S_TOS)},a", f"cmp #>${M.SEARCH_STAGES:x},a", ("jcc", "gt", "blk_step"),
        f"move {g(G_OWN)},a", "tst a", ("jcc", "ne", "blk_step"),
        f"move {g(G_TRK)},a", "add #>$1,a", f"move a1,{g(G_OWN)}", f"move #>${M.SEARCH_STAGES:x},a", f"move a1,{sx(S_TOS)}",
        f"move {sx(S_NH)},a", "sub #>$1,a", "asl #2,a,a", f"add #>${S_H:x},a", "move r7,x0", "add x0,a", "move a1,r0",
        *rate, "asl #8,a,a", "move x:(r0),b", "move x:(r0+$1),b0", "add a,b", f"move b1,{g(G_LI)}", f"move b0,{g(G_LF)}",
        *speed, "asl #8,a,a", *pos_b, "add a,b", f"move b1,{g(G_TG)}", "move #>$1,a", f"move a1,{sx(S_STG)}",
        ("label", "blk_step"), f"move {sx(S_STG)},a", "tst a", ("jcc", "eq", "blk_due"),
        *own_test("blk_lost"), f"move {sx(S_STG)},a",
        f"cmp #>${M.SEARCH_STAGES:x},a", ("jcc", "gt", "blk_due"), ("jsr", "st_stage"),
        f"move {sx(S_STG)},a", "add #>$1,a", f"move a1,{sx(S_STG)}",
        ("jmp", "blk_due"),
        ("label", "blk_lost"), "clr a", f"move a1,{sx(S_STG)}",           # the scratch went to another track
        ("label", "blk_due"), f"move {sx(S_TOS)},a", "tst a", ("jcc", "gt", "blk_render"),
        f"move {sx(S_STG)},a", f"cmp #>${M.SEARCH_STAGES + 1:x},a", ("jcc", "lt", "blk_render"),
        "clr a", f"move a1,{sx(S_STG)}", f"move a1,{g(G_OWN)}", f"move #>${M.HOP_BLOCKS:x},a", f"move a1,{sx(S_TOS)}",
        f"move {sx(S_KEEP)},a", "tst a", ("jcc", "ne", "blk_render"),
        f"move {sx(S_STI)},a", f"move a1,{g(G_T0)}", f"move {sx(S_STF)},a", f"move a1,{g(G_T1)}",
        f"move #>${GT:x},r1", f"move #>${M.HOP_BLOCKS:x},n1", ("jsr", "st_splice"),
        # every head into Y:OUT
        ("label", "blk_render"), *heads_base, "move a1,r6", f"move {sx(S_NH)},a", f"move a1,{g(G_HN)}", "tst a", ("jcc", "gt", "blk_head"),
        "clr a", f"move #>${OUT:x},r0", "rep #$20", "move a,y:(r0)+",
        ("label", "blk_head"), f"move {g(G_HN)},a", "tst a", ("jcc", "le", "blk_done"),
        f"move {sx(S_FJ)},a", f"move a1,{g(G_K)}", ("jsr", "st_gain"), f"move a1,{g(G_G0)}",
        f"move {sx(S_FJ)},a", "add #>$1,a", f"move a1,{g(G_K)}", ("jsr", "st_gain"), f"move {g(G_G0)},x0", "sub x0,a",
        "asr #5,a,a", f"move a1,{g(G_STEP)}",
        # this head's words: ((frac + 31 rate) >> 24) + 2 from its position
        *rate, "tfr a,b", "asl #5,a,a", "sub b,a", "clr b", "move x:(r6+$1),b0", "add b,a", "add #>$2,a", f"move a1,{g(G_CN)}",
        "move x:(r6),a", f"move a1,{g(G_CI)}", f"move #>${LB:x},r5", "move r6,x0", f"move x0,{g(G_T2)}", ("jsr", "st_copy"),
        f"move {g(G_T2)},r6",
        # its samples: h0 + (h1 - h0) f between the half-level words
        f"move #>${TMP:x},r4", "clr a", "move x:(r6+$1),a0", f"move #>${LB:x},a1", f"move {g(G_RTI)},y1", f"move {g(G_RTF)},y0",
        "do #$20,${blk_ip:x}", "move a1,r0", "move a0,b", "lsr b x:(r0)+,x0", "move b1,x1", "move x:(r0),b", "sub x0,b",
        "move b1,x0", "mpy x1,x0,b x:-(r0),x0", "add x0,b", "add y,a b1,y:(r4)+", ("label", "blk_ip"),
        # OUT = sample x gain for the first head, OUT += it for the others; the gain moves by its step
        f"move #>${TMP:x},r4", f"move #>${OUT:x},r0", f"move {g(G_G0)},a", f"move {g(G_STEP)},x0", "move y:(r4)+,y0",
        f"move {g(G_HN)},b", f"move {sx(S_NH)},x1", "cmp x1,b", ("jcc", "ne", "blk_acc"),
        "do #$20,${blk_g1:x}", "move a1,x1", "mpy x1,y0,b y:(r4)+,y0", "add x0,a b1,y:(r0)+", ("label", "blk_g1"), ("jmp", "blk_gd"),
        ("label", "blk_acc"),
        "do #$20,${blk_gn:x}", "move a1,x1", "mpy x1,y0,b y:(r0),y1", "add y1,b y:(r4)+,y0", "add x0,a b1,y:(r0)+",
        ("label", "blk_gn"), ("label", "blk_gd"),
        *rate, "asl #5,a,a", "move x:(r6),b", "move x:(r6+$1),b0", "add a,b", "move b1,x:(r6)", "move b0,x:(r6+$1)",
        "move #>$4,n6", f"move {g(G_HN)},a", "sub #>$1,a", f"move a1,{g(G_HN)}", "move (r6)+n6", ("jmp", "blk_head"),
        # the fade moves on; at its end only the heads it fades to stay
        ("label", "blk_done"), f"move {sx(S_FJ)},a", "add #>$1,a", f"move a1,{sx(S_FJ)}", f"move {sx(S_TABN)},x0", "cmp x0,a",
        ("jcc", "lt", "blk_adv"),
        *heads_base, "move a1,r6", "move a1,r2", "move #>$4,n6", "move #>$4,n2", "move #>$0,r3",
        f"move {sx(S_NH)},a", "do a1,${blk_keep:x}", "move x:(r6+$3),a", "tst a", ("jcc", "le", "blk_kx"),
        "move x:(r6),x0", "move x0,x:(r2)", "move x:(r6+$1),x0", "move x0,x:(r2+$1)", "move a1,x:(r2+$2)", "move a1,x:(r2+$3)",
        "move (r2)+n2", "move (r3)+", ("label", "blk_kx"), "move (r6)+n6", ("label", "blk_keep"),
        f"move r3,{sx(S_NH)}", f"move #>${M.HOP_BLOCKS:x},a", f"move a1,{sx(S_FJ)}", f"move a1,{sx(S_TABN)}",
        f"move #>${GT:x},a", f"move a1,{sx(S_TAB)}",
        # P += 32 speed; one block nearer the splice
        ("label", "blk_adv"), *speed, "asl #5,a,a", *pos_b, "add a,b", f"move b1,{sx(S_PI)}", f"move b0,{sx(S_PF)}",
        f"move {sx(S_TOS)},a", "sub #>$1,a", f"move a1,{sx(S_TOS)}", "rts"]


def entry_items(control, snapshot, state, smp, pages, pstride, trk_buf, route_key, audio_key, params, positions):
    """st_entry: every stretch track's block, after core 1's acknowledgement and before Granular's.

    A track stretches when word 15 of its host parameters (X:state + 256 t) holds HOST_KEY, its route
    control (Y:control + 4 t) is on and core 1's snapshot (Y:snapshot + 8 t) is ready for this frame.
    A length (host word 2) sets the speed to the sample's length / it, so the whole sample lasts that long (with
    TGT_PART: the region from start to end); the loop
    follows the track's play mode (Y:params + 32 t + 1: 2 = Loop). Its 32 words go to the track's buffer for the next block and the snapshot is marked as audio, as
    Granular's producer does. A search scratch whose track did not run is released. When the engine did not run the track
    in the last RESUME_GAP blocks, it starts where core 1's native reader is (Y:positions + t, less READER_LEAD), so it
    turns on in place."""
    snap_r3 = [f"move {g(G_TRK)},a", "asl #3,a,a", f"add #>${snapshot:x},a", "move a1,r3", "nop"]
    ctrl_r2 = [f"move {g(G_TRK)},a", "asl #2,a,a", f"add #>${control:x},a", "move a1,r2"]
    ready = ["move y:(r3),a", f"cmp #>${route_key:x},a", ("jcc", "ne", "ent_next"),
             "move y:(r3+$1),a", "move y:(r2+$1),x0", "cmp x0,a", ("jcc", "ne", "ent_next"),
             "move y:(r3+$2),a", "move y:(r2+$2),x0", "cmp x0,a", ("jcc", "ne", "ent_next")]
    return [
        ("label", "st_entry"), f"move {g(G_INIT)},a", f"cmp #>${INIT_KEY:x},a", ("jcc", "eq", "ent_go"),
        "move #>${tbl:x},r0", f"move #>${GT:x},r1", f"do #${len(tables()):x},${{ent_tab:x}}", "move p:(r0)+,x0", "move x0,x:(r1)+",
        ("label", "ent_tab"), "clr a", f"move a1,{g(G_OWN)}", f"move #>${INIT_KEY:x},a", f"move a1,{g(G_INIT)}",
        ("label", "ent_go"), "clr a", f"move a1,{g(G_SEEN)}", f"move a1,{g(G_TRK)}",
        ("label", "ent_trk"),
        f"move {g(G_TRK)},a", "asl #8,a,a", f"add #>${state:x},a", "move a1,r0", "nop",
        "move x:(r0+$f),a", f"cmp #>${HOST_KEY:x},a", ("jcc", "ne", "ent_next"),
        f"move x:(r0+${H_TGT:x}),a", f"move a1,{g(G_TGT)}", "tst a", ("jcc", "gt", "ent_ctl"),
        f"move x:(r0+${H_SPD:x}),a", "tst a", ("jcc", "le", "ent_next"), "move a1,x0", "clr a", "move x0,a0", "asl #4,a,a",
        "clr b", f"move #>${RATE_MAX >> 24:x},b1", "cmp b,a", "tgt b,a", f"move a1,{g(G_SPI)}", f"move a0,{g(G_SPF)}",
        ("label", "ent_ctl"),
        f"move {g(G_TRK)},a", "asl #5,a,a", f"add #>${params + 1:x},a", "move a1,r1", "nop",
        "move y:(r1),a", "asr a", "and #>$1,a", f"move a1,{g(G_LOOP)}",
        *ctrl_r2, *snap_r3,
        "move y:(r2),a", f"cmp #>${route_key:x},a", ("jcc", "ne", "ent_next"), *ready,
        # the source: slot 0-127, a region of 8 words or more inside the slot's sample, read backwards when end < start
        "move y:(r3+$3),a", "tst a", ("jcc", "lt", "ent_next"), "cmp #>$80,a", ("jcc", "ge", "ent_next"), f"move a1,{g(G_T5)}",
        "clr b", f"move b1,{g(G_REV)}", "move y:(r3+$4),a", "move y:(r3+$5),b", "sub a,b", ("jcc", "ge", "ent_fwd"),
        "neg b", "move y:(r3+$5),a", "move #>$1,x0", f"move x0,{g(G_REV)}",
        ("label", "ent_fwd"), "cmp #>$8,b", ("jcc", "lt", "ent_next"), f"move a1,{g(G_S)}", f"move b1,{g(G_N)}",
        f"move {g(G_T5)},a", "asl #2,a,a", f"add #>${smp:x},a", "move a1,r1", "nop",
        f"move {g(G_S)},a", "move x:(r1),x0", "cmp x0,a", ("jcc", "lt", "ent_next"),
        "move x:(r1+$1),a", "tst a", ("jcc", "le", "ent_next"), f"move a1,{g(G_WHL)}", "add x0,a", "move a1,x1",
        f"move {g(G_S)},a", f"move {g(G_N)},x0", "add x0,a", "cmp x1,a", ("jcc", "gt", "ent_next"),
        f"move {g(G_T5)},x0", f"move #>${pstride:x},x1", "mpy x1,x0,b", "asr b", "move b0,b", f"add #>${pages:x},b",
        f"move b1,{g(G_PTAB)}",
        # a length T: speed = N / T = 8 q, q = N / 4T with 23 fraction bits (N, 4T halved alike until 4T fits), SPEED_MIN .. RATE_MAX;
        # N the whole sample, or with TGT_PART the region
        f"move {g(G_TGT)},b", "tst b", ("jcc", "le", "ent_rate"), f"move {g(G_WHL)},a",
        f"jclr #{TGT_PART.bit_length() - 1},b1,${{ent_wh:x}}", f"move {g(G_N)},a",
        ("label", "ent_wh"), f"and #>${TGT_PART - 1:x},b", "asl #2,b,b", "move #>$7fffff,x0",
        "cmp x0,b", ("jcc", "le", "ent_d1"), "asr b", "asr a", "move b1,b", "move a1,a",
        ("label", "ent_d1"), "cmp x0,b", ("jcc", "le", "ent_d2"), "asr b", "asr a", "move b1,b", "move a1,a",
        ("label", "ent_d2"), "cmp b,a", ("jcc", "ge", "ent_max"),
        "move b1,x0", "andi #$fe,ccr", "rep #$18", "div x0,a", "move a0,x1", "clr a", "move x1,a0",
        "clr b", f"move #>${SPEED_MIN >> 3:x},b0", "cmp b,a", "tlt b,a", "asl #3,a,a", ("jmp", "ent_spd"),
        ("label", "ent_max"), "clr a", f"move #>${RATE_MAX >> 24:x},a1",
        ("label", "ent_spd"), f"move a1,{g(G_SPI)}", f"move a0,{g(G_SPF)}",
        ("label", "ent_rate"),
        # the rate: the Q15 increment as a Q24 position step, at most RATE_MAX
        "move y:(r3+$6),a", "tst a", ("jcc", "le", "ent_next"), "asr #15,a,a", "clr b", f"move #>${RATE_MAX >> 24:x},b1",
        "cmp b,a", "tgt b,a", f"move a1,{g(G_RTI)}", f"move a0,{g(G_RTF)}",
        # run on; a new note restarts at 0; a track not run in the last RESUME_GAP blocks (or a new epoch) resumes
        f"move {g(G_TRK)},a", "asl #6,a,a", f"add #>${ST_X:x},a", "move a1,r7", "nop",
        "clr a", f"move a1,{g(G_AT)}",
        f"move {sx(S_LIFE)},a", f"cmp #>${LIFE:x},a", ("jcc", "ne", "ent_res"),
        "move y:(r3+$2),a", f"move {sx(S_FRM)},x0", "sub x0,a", "move a1,a", "tst a", ("jcc", "le", "ent_res"),
        f"cmp #>${RESUME_GAP:x},a", ("jcc", "gt", "ent_res"),
        "move y:(r3+$1),a", f"move {sx(S_EPOCH)},x0", "cmp x0,a", ("jcc", "ne", "ent_res"),
        "move y:(r3+$7),a", f"move {sx(S_SERIAL)},x0", "cmp x0,a", ("jcc", "eq", "ent_run"), ("jmp", "ent_rst"),
        # the index the native reader plays: forward POS - S - lead, reverse S + N - 1 - POS - lead; a loop wraps
        ("label", "ent_res"), f"move {g(G_TRK)},a", f"add #>${positions:x},a", "move a1,r1", "nop", "move y:(r1),a",
        f"move {g(G_REV)},b", "tst b", ("jcc", "ne", "ent_rv"),
        f"move {g(G_S)},x0", "sub x0,a", ("jmp", "ent_ld"),
        ("label", "ent_rv"), "move a1,x0", f"move {g(G_S)},a", f"move {g(G_N)},x1", "add x1,a", "sub x0,a", "sub #>$1,a",
        ("label", "ent_ld"), f"sub #>${READER_LEAD:x},a", f"move {g(G_N)},x0", f"move {g(G_LOOP)},b", "tst b", ("jcc", "eq", "ent_cl"),
        "tst a", ("jcc", "ge", "ent_w1"), "add x0,a",
        ("label", "ent_w1"), "cmp x0,a", ("jcc", "lt", "ent_cl"), "sub x0,a",
        ("label", "ent_cl"), "tst a", ("jcc", "ge", "ent_c1"), "clr a",
        ("label", "ent_c1"), "cmp x0,a", ("jcc", "le", "ent_c2"), "tfr x0,a",
        ("label", "ent_c2"), f"cmp #>${RESUME_MIN:x},a", ("jcc", "ge", "ent_set"), "clr a",
        ("label", "ent_set"), f"move a1,{g(G_AT)}",
        ("label", "ent_rst"), ("jsr", "st_restart"), f"move {g(G_AT)},a", "tst a", ("jcc", "eq", "ent_r0"), ("jsr", "st_at"),
        ("label", "ent_r0"), *snap_r3,
        f"move #>${LIFE:x},a", f"move a1,{sx(S_LIFE)}", "move y:(r3+$1),a", f"move a1,{sx(S_EPOCH)}",
        "move y:(r3+$7),a", f"move a1,{sx(S_SERIAL)}",
        ("label", "ent_run"), "move y:(r3+$2),a", f"move a1,{sx(S_FRM)}", ("jsr", "st_block"),
        *own_test("ent_out"), "move #>$1,a", f"move a1,{g(G_SEEN)}",
        # the words into the track's buffer for the next block, then audio for core 1 if the snapshot still holds
        ("label", "ent_out"), "movep y:<<$ffffd0,b", "asl #5,b,b", f"move {g(G_TRK)},a", "asl #6,a,a", f"add #>${trk_buf:x},a",
        "add b,a", "move a1,r1", f"move #>${OUT:x},r0", "do #$20,${ent_cp:x}", "move y:(r0)+,x0", "move x0,y:(r1)+",
        ("label", "ent_cp"), *ctrl_r2, *snap_r3, *ready,
        f"move #>${audio_key:x},a", "move a,y:(r3)",
        ("label", "ent_next"), f"move {g(G_TRK)},a", "add #>$1,a", f"move a1,{g(G_TRK)}", "cmp #>$8,a", ("jcc", "lt", "ent_trk"),
        f"move {g(G_SEEN)},a", "tst a", ("jcc", "ne", "ent_x"), f"move a1,{g(G_OWN)}",
        ("label", "ent_x"), "rts",
        ("label", "tbl"), ("words", tables())]


def items(entry=None):
    """entry: entry_items' keyword arguments, or None for the engine alone (the emulator tests)."""
    return copy_items() + scan_items() + head_items() + search_items() + block_items() + (entry_items(**entry) if entry else [])


def report(words, labels, at=AT):
    """The build report's entry: where the engine is and every region it owns."""
    regions = [("p", at, len(words), "engine and gain tables"), ("x", ST_X, 8 * ST_STRIDE, "track state"),
               ("x", SCR, SCR_N, "search candidates"), ("x", TSCR, TSCR_N, "search template"), ("x", LB, LB_N, "head words"),
               ("x", SB, M.OBLK + 1, "hit analysis words"), ("x", GT, len(tables()), "gain tables"),
               ("y", OUT, 32, "block output"), ("y", TMP, 32, "head samples"), ("y", TPLC, NC_POINTS, "coarse template"),
               ("y", TPLF, NF_POINTS, "fine template"), ("y", OFFC, NC_POINTS, "coarse offsets"), ("y", OFFF, NF_POINTS, "fine offsets"),
               ("y", GV, GV_WORDS, "globals")]
    return dict(at=hex(at), words=len(words), entry=hex(labels["st_entry"]), host_key=hex(HOST_KEY),
                regions=[dict(space=s, start=hex(a), words=n, owner=o) for s, a, n, o in regions])


def tables():
    return M.G_HOP + M.G_LOCK


LA_FORBIDDEN = re.compile(r"(brk|do\b|dor\b|enddo|rep\b|rts|rti|jmp|jsr|bra\b|bsr|j[a-z]{2}\b|b[a-z]{2}\b|js[a-z]{2}\b)")


def check_loop_ends(its):
    """The DSP56300 does not allow a break, jump, return, rep or loop as the last instruction of a DO loop; the emulator
    runs such code, the device does not."""
    ends = {it[1]: i for i, it in enumerate(its) if isinstance(it, tuple) and it[0] == "label"}
    for i, it in enumerate(its):
        if isinstance(it, str) and it.startswith("do "):
            j = ends[re.search(r"\{(\w+):x\}", it).group(1)] - 1
            while isinstance(its[j], tuple) and its[j][0] == "label":
                j -= 1
            last = its[j]
            assert isinstance(last, str) and not LA_FORBIDDEN.match(last), (it, last)


STACK_MAX = 7                   # system stack words the engine may use from the call of st_entry, a DO taking 2


def stack_depth(its, top="st_entry"):
    """The deepest system stack use of `top`: 1 a call, 2 an open DO. dsptool counts calls only and has no limit; the
    device's stack has 15 words, shared with the stock code under the engine and its interrupts."""
    ends = {it[1]: i for i, it in enumerate(its) if isinstance(it, tuple) and it[0] == "label"}
    open_do = [0] * len(its)
    for i, it in enumerate(its):
        if isinstance(it, str) and it.startswith("do "):
            for k in range(i + 1, ends[re.search(r"\{(\w+):x\}", it).group(1)]):
                open_do[k] += 2
    starts = sorted(ends[n] for n in {it[1] for it in its if isinstance(it, tuple) and it[0] == "jsr"} | {top})
    memo = {}

    def below(name):
        if name not in memo:
            s = ends[name]
            stop = min([x for x in starts if x > s], default=len(its))
            memo[name] = max([open_do[p] for p in range(s, stop)] +
                             [open_do[p] + 1 + below(its[p][1]) for p in range(s, stop)
                              if isinstance(its[p], tuple) and its[p][0] == "jsr"])
        return memo[name]
    return 1 + below(top)


# instruction kinds A0220's engine ran on the unit; dsptool runs some kinds the device does not (brkgt stalled A0225)
PROVEN = frozenset("add and andi asl asr btst clr cmp div do jclr jcs jeq jge jgt jle jlt jmp jne jsr lsr mac move movep "
                   "mpy neg nop rep rts sub tfr tgt tlt tst".split())


def check_proven(words, at):
    import os
    import subprocess
    import tempfile
    import rhdsp
    with tempfile.TemporaryDirectory() as d:
        fn = os.path.join(d, "e.bin")
        with open(fn, "wb") as f:
            f.write(b"".join(w.to_bytes(3, "big") for w in words))
        out = subprocess.run([rhdsp.TOOL, "dis", fn, hex(at)], capture_output=True, text=True, check=True).stdout
    used = {m.group(1) for line in out.splitlines() for m in [re.match(r"[0-9a-f]{6}:\s+(?:[0-9a-f]{6} ?)+\s+(\S+)", line)] if m}
    assert used and used <= PROVEN, sorted(used - PROVEN)


def code(at=AT, entry=None):
    import core0
    import voicefx
    check_loop_ends(items(entry))
    assert entry is None or stack_depth(items(entry)) <= STACK_MAX, stack_depth(items(entry))
    words, labels = core0.asm_at(items(entry), at)
    voicefx.check(words[:labels['tbl'] - at] if 'tbl' in labels else words, at)        # the table is data
    check_proven(words[:labels['tbl'] - at] if 'tbl' in labels else words, at)
    return words, labels
