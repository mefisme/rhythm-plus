"""Time stretch, the ARM side (MIT; Rhythm Plus): stretch.c on Sample mode's pads 9-17 and the LED task's output stage.

Pad 9 turns the selected track's stretch on / off, pad 10 is Own (the length the sample has at the tempo it is chosen at), pads 11-16
fit the sample to 1/4, 1/2, 1, 2, 4 or 8 bars at the tempo, pad 17 picks the whole sample or the part K2 / K3 play. On a Granular track pads 11-16 set Scan so the playhead crosses the region in
that length. Saved in the record's tail + BLK_OFF. The engine is core 0's (stretch_dsp.py, RH_STRETCH=1); its words go through
Granular's writer, so install after granular_bridge and granular_lifecycle. With trackreset's wipe, Clear + track turns the track's
stretch off (c_st_wipe at its page reset call, after Granular's).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / d) for d in ("modules", "builds", "tests", "remix/tools")]
import rhstate  # noqa: E402
import stepmut  # noqa: E402

SRC = ROOT / "modules" / "stretch.c"
BLK_OFF, BLK_LEN = 296, 28
SLOT_LEN = 96                                   # a multiple of 32: the slots below keep their alignment
LABELS = ("c_st_out", "c_st_pad")
SMP_VT = 0x08067D8C                             # Sample mode's subview: slot 0 its pad press


def install(img, report, base_addr):
    import rhbuild
    import rhrec
    import stretch_dsp
    import tmenu as T
    from thumb import bl as bl_ins
    assert "stretch" in report and "bridge" in report["granular"], "stretch_arm: after the engine and granular_bridge"
    assert rhstate.OFF["stretch"][1] == SLOT_LEN
    taken = ((192, 84), (384, 20), (404, 100), (748, 112))         # mutset's settings, smswitch, stepmut, mutset's scenes
    assert all(BLK_OFF + BLK_LEN <= o or o + n <= BLK_OFF for o, n in taken) and BLK_OFF + BLK_LEN <= rhrec.FREE_LEN
    kernel = report["granular"]["arm_kernel"]["labels"]
    bridge = report["granular"]["bridge"]
    lab = lambda k, n: int(report[k]["labels"][n], 16)
    prev = dict(PREV_PAD=int.from_bytes(img[SMP_VT - rhbuild.BASE:SMP_VT - rhbuild.BASE + 4], "little") & ~1,
                PREV_OUT=rhbuild.bl_target(img, T.OUT_CALL))
    wipe_site = int(report["trackreset"]["labels"]["c_trreset_pages_call"], 16) if report.get("trackreset", {}).get("wipe") else None
    if wipe_site:
        prev["PREV_WIPE"] = rhbuild.bl_target(img, wipe_site)
    base_addr = (base_addr + 3) & ~3
    defs = dict(prev, SLOT=rhstate.ST + rhstate.OFF["stretch"][0], SLOT_LEN=SLOT_LEN, BLK_OFF=BLK_OFF,
                C_RRT=lab("rhrec", "c_rrt"), C_RST=int(report["rhstate"]["labels"]["c_rst"], 16),
                C_READY=int(bridge["labels"]["c_gready"], 16), C_BUSY=int(bridge["labels"]["c_ggranular_busy"], 16),
                UPLOAD=int(bridge["upload"], 16), GSTATE=int(bridge["slot"], 16),
                C_WRITE=kernel["c_gr_dsp_write"], C_SCAN=kernel["c_gr_runtime_scan"], C_ROUTE=kernel["c_gr_route_word"], C_SREAD=kernel["c_gr_shared_read"], C_GSWITCH=kernel["c_gr_stretch_switch"],
                HOST_KEY=stretch_dsp.HOST_KEY, TGT_PART=stretch_dsp.TGT_PART)
    code, labels = stepmut.compile_c(base_addr, defs, src=SRC, name="stretch", prefix="c_st_", need=LABELS + (("c_st_wipe",) if wipe_site else ()))
    img += bytes([0xFF]) * (base_addr - rhbuild.BASE - len(img)) + code
    while len(img) % 4:
        img += bytes([0xFF])
    rhbuild.patch_word(img, SMP_VT, prev["PREV_PAD"] | 1, labels["c_st_pad"] | 1)
    rhbuild.patch(img, T.OUT_CALL, f"bl #{prev['PREV_OUT']:#x}", bl_ins(T.OUT_CALL, labels["c_st_out"]))
    if wipe_site:
        rhbuild.patch(img, wipe_site, f"bl #{prev['PREV_WIPE']:#x}", bl_ins(wipe_site, labels["c_st_wipe"]))
    report["stretch"].update(arm=dict(slot=hex(defs["SLOT"]), blk_off=BLK_OFF, blk_len=BLK_LEN, code=len(code),
                                      prev={k.lower(): hex(v) for k, v in prev.items()},
                                      labels={k: hex(v) for k, v in labels.items()}))
    return labels, code
