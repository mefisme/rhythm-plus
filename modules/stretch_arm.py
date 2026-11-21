"""Time stretch, the ARM side (MIT; Rhythm Plus): stretch.c on Sample mode's pads 9-17 and the LED task's output stage.

Pad 9 turns the selected track's stretch on / off, pad 10 is Own (the length the sample has at the tempo it is chosen at), pads 11-16
fit the sample to 1/4, 1/2, 1, 2, 4 or 8 bars at the tempo, pad 17 picks the whole sample or the part K2 / K3 play. On a Granular track pads 11-16 set Scan so the playhead crosses the region in
that length. Saved in the record's tail + BLK_OFF. The engine is core 0's (stretch_dsp.py, RH_STRETCH=1); its words go through
Granular's writer, so install after granular_bridge and granular_lifecycle. With trackreset's wipe, Clear + track turns the track's
stretch off (c_st_wipe at its page reset call, after Granular's).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / d) for d in ("modules", "builds", "tests", "remix/tools")]
import rhstate  # noqa: E402
import stepmut  # noqa: E402

SRC = ROOT / "modules" / "stretch.c"
BLK_OFF, BLK_LEN = 296, 28
SLOT_LEN = 96                                   # a multiple of 32: the slots below keep their alignment
LOCK_OFF = 93                                   # State.lock: the tracks the Scan lock drives, read by Granular
LOCK_RAM = 0x3400                               # ITCM: the lock's words, above the DSP unpacker's window (0x2400-0x33FF)
LABELS = ("c_st_out", "c_st_pad")
SMP_VT = 0x08067D8C                             # Sample mode's subview: slot 0 its pad press


def install(img, report, base_addr=None):
    """base_addr None: into dsppack's first flash hole (after filetools), else appended there"""
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
    hole = base_addr is None
    if hole:
        holes = report["dsppack"]["holes"]
        base_addr, end = (int(x, 16) for x in holes[0][:2])
    base_addr = (base_addr + 3) & ~3
    defs = dict(prev, SLOT=rhstate.ST + rhstate.OFF["stretch"][0], SLOT_LEN=SLOT_LEN, BLK_OFF=BLK_OFF,
                C_RRT=lab("rhrec", "c_rrt"), C_RST=int(report["rhstate"]["labels"]["c_rst"], 16),
                C_READY=int(bridge["labels"]["c_gready"], 16), C_BUSY=int(bridge["labels"]["c_ggranular_busy"], 16),
                UPLOAD=int(bridge["upload"], 16), GSTATE=int(bridge["slot"], 16),
                C_WRITE=kernel["c_gr_dsp_write"], C_SCAN=kernel["c_gr_runtime_scan"], C_ROUTE=kernel["c_gr_route_word"], C_SREAD=kernel["c_gr_shared_read"], C_GSWITCH=kernel["c_gr_stretch_switch"],
                HOST_KEY=stretch_dsp.HOST_KEY, TGT_PART=stretch_dsp.TGT_PART)
    if os.environ.get("RH_PACK_FILES") == "2":
        defs["C_PLUSOK"] = int(report["storageshadow"]["labels"]["c_sh_autobank"], 16)
    if os.environ.get("RH_SCAN_CLOCK") == "1":
        assert os.environ.get("RH_GRANULAR_SCAN_HOME") == "1"
        defs.update(CLOCK_LOCK=1, SCAN_DEFAULT_STEP=64, C_GRESTART=kernel["c_gr_runtime_restart"])
    if os.environ.get("RH_SCAN_LOCK") == "1":
        assert "CLOCK_LOCK" in defs and os.environ.get("RH_GRANULAR_SCAN_CENTRE") == "1"
        defs.update(SCAN_LOCK=1, LOCK_OFF=LOCK_OFF, LOCK_RAM=LOCK_RAM, C_GWORD=kernel["c_gr_runtime_word"])
    if os.environ.get("RH_GRANULAR_SCAN_EACH") == "1":
        assert "SCAN_LOCK" in defs
        defs.update(SCAN_EACH=1, C_GVIEW=kernel["c_gr_runtime_sample_view"], C_GSPAD=kernel["c_gr_runtime_sample_pad"])
        if os.environ.get("RH_GRANULAR_SCAN_EACH_TAGS") == "1":
            defs.update(EACH_TAGS=1)
        if os.environ.get("RH_GRANULAR_SAMPLE_HIDE") == "1":
            assert "EACH_TAGS" in defs
            defs.update(SAMPLE_HIDE=1)
        if os.environ.get("RH_STRETCH_OFF_MATCH") == "1":
            assert "EACH_TAGS" in defs
            defs.update(OFF_MATCH=1)
    if os.environ.get("RH_STRETCH_DRAIN_IDLE") == "1":
        defs["DRAIN_IDLE"] = 1
    if os.environ.get("RH_GRANULAR_STRETCH_HANDOFF") == "1":
        defs["C_GHANDOFF"] = kernel["c_gr_stretch_handoff"]
    code, labels = stepmut.compile_c(base_addr, defs, src=SRC, name="stretch", prefix="c_st_", need=LABELS + (("c_st_wipe",) if wipe_site else ()),
                                     **(dict(max_code=end - base_addr) if hole else {}))
    if hole:
        o = base_addr - rhbuild.BASE
        assert all(b == 0xFF for b in img[o:o + len(code)])
        img[o:o + len(code)] = code
        after = (base_addr + len(code) + 3) & ~3
        holes[0] = [hex(after), holes[0][1], end - after]
    else:
        img += bytes([0xFF]) * (base_addr - rhbuild.BASE - len(img)) + code
        while len(img) % 4:
            img += bytes([0xFF])
    rhbuild.patch_word(img, SMP_VT, prev["PREV_PAD"] | 1, labels["c_st_pad"] | 1)
    rhbuild.patch(img, T.OUT_CALL, f"bl #{prev['PREV_OUT']:#x}", bl_ins(T.OUT_CALL, labels["c_st_out"]))
    if wipe_site:
        rhbuild.patch(img, wipe_site, f"bl #{prev['PREV_WIPE']:#x}", bl_ins(wipe_site, labels["c_st_wipe"]))
    report["stretch"].update(arm=dict(slot=hex(defs["SLOT"]), blk_off=BLK_OFF, blk_len=BLK_LEN, code=len(code), **({"at": hex(base_addr)} if hole else {}),
                                      prev={k.lower(): hex(v) for k, v in prev.items()},
                                      labels={k: hex(v) for k, v in labels.items()}))
    if "CLOCK_LOCK" in defs:
        report["stretch"]["arm"]["clock_lock"] = dict(position=hex(0x2003C410), restart=hex(defs["C_GRESTART"]))
    if "SCAN_LOCK" in defs:
        report["stretch"]["arm"]["scan_lock"] = dict(ram=hex(LOCK_RAM), lock_byte=LOCK_OFF, word=hex(defs["C_GWORD"]),
                                                     **({"each_sample": True} if "SCAN_EACH" in defs else {}),
                                                     **({"each_tags": True} if "EACH_TAGS" in defs else {}),
                                                     **({"sample_hide": True} if "SAMPLE_HIDE" in defs else {}),
                                                     **({"off_match": True} if "OFF_MATCH" in defs else {}))
    return labels, code
