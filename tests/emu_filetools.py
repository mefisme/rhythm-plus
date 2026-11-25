"""Unicorn test of filetools on a build with it and the RAM dump: Duplicate copies a project or a sample, Clear deletes a pack,
and their lights. The storage task's calls are a fake card; the stock's views and stores are the dump's.

    python tests/emu_filetools.py STOCK.bin BUILT.bin RAM.bin
"""
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("RH_BUILD", Path(sys.argv[2]).parent.name if len(sys.argv) > 2 else "a0260")
import emu_tmenu as ET  # noqa: E402
from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_SP  # noqa: E402

check, u32, call = ET.check, ET.u32, ET.call
REP = ET.MAN["report"]["filetools"]
L = {k: int(v, 16) for k, v in REP["labels"].items()}
PREV = {k: int(v, 16) for k, v in REP["prev"].items()}
CTRL, HELD, VIEW = ET.C.CTRL, ET.C.CTRL + 0xA0, ET.C.CTRL + 0x7C
PROJ, PROJ_VT, SR, SR_VT, PACKS, PACKS_VT = 0x2004DA10, 0x080679CC, 0x2004DC90, 0x08067A08, 0x2004D7FC, 0x08067954
TRANSPORT, PARAM_NEW, COLOURS = 0x200122B0, 0x0803FC6C, 0x20003974
SM = 0x20043DC0
CLEAR, DUP = 1 << 23, 1 << 24
SESS = 0x29484
FN = dict(size=0x08045FCE, read=0x08046054, write=0x0804607A, delete=0x08046098, exists=0x08045FB4, lock=0x0802EF6A, unlock=0x0802EF98,
          dsp=0x080314D6, refresh=0x08039FB4, reload=0x0803A0D8, feed=0x08026DD6)
OUT = ET.OUT
HOLD = REP.get("hold_source", False)          # the source green, kept only while Duplicate is held
disk, log, px = {}, [], []
dsp_free = [0x100000]
px_status = [0]


def w32(uc, a, v): uc.mem_write(a, struct.pack("<I", v))
def ret(u, v=0): u.reg_write(UC_ARM_REG_R0, v); u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
def it(u, a): k, s, p = struct.unpack("<III", u.mem_read(a, 12)); return (k, s, p & 0xFF)


def p_new(uc, store, p):
    call(uc, PARAM_NEW, store, p)
    return uc.reg_read(UC_ARM_REG_R0)


def setb(uc, store, p, v, off=0): uc.mem_write(p_new(uc, store, p) + off, bytes([v]))
def getb(uc, store, p, off=0): return uc.mem_read(p_new(uc, store, p) + off, 1)[0]


def hooks(uc):
    def h(u, a, n, d):
        r = [u.reg_read(UC_ARM_REG_R0 + i) for i in range(4)]
        sp = u.reg_read(UC_ARM_REG_SP)
        if a == FN["size"]: f = disk.get(it(u, r[0])); ret(u, len(f) if f else 0); return
        if a == FN["exists"]: log.append(("resel", it(u, r[0])[2])); ret(u, 1); return
        if a in (FN["read"], FN["write"]):
            k = it(u, r[0]); off, buf, cnt = r[1], r[2], r[3]; done = u32(u, sp + 8)
            if a == FN["read"]:
                f = disk.get(k)
                if f is None: ret(u, 4); return
                part = bytes(f[off:off + cnt]); u.mem_write(buf, part); w32(u, done, len(part))
            else:
                assert k[2] != 0, "a write on the internal pack"
                f = disk.setdefault(k, bytearray()) if off else disk.__setitem__(k, bytearray()) or disk[k]
                f[off:off + cnt] = u.mem_read(buf, cnt); w32(u, done, cnt)
                log.append(("write", k))
            ret(u, 0); return
        if a == FN["delete"]:
            k = it(u, r[0]); log.append(("delete", k)); assert k[2] != 0, "a delete on the internal pack"
            if k[0] == 1:
                for x in [x for x in disk if x[2] == k[2]]: del disk[x]
            else: disk.pop(k, None)
            ret(u, 0); return
        if a == FN["lock"]: log.append(("lock",)); ret(u); return
        if a == FN["unlock"]: log.append(("unlock",)); ret(u); return
        if a == FN["dsp"]: ret(u, dsp_free[0] << 8); return
        if a == FN["refresh"]: log.append(("refresh", r[1])); ret(u); return
        if a == FN["reload"]: log.append(("reload", r[1])); ret(u); return
        if a == FN["feed"]: log.append(("feed",)); ret(u); return
        if a == C_PX:
            q = bytes(u.mem_read(r[0], 32)); px.append((q[4] & 0x3F, q[6], q[8], q[9], q[10], q[11]))
            st = px_status[0] if q[11] == 0 else 0
            u.mem_write(r[0] + 6, bytes((st >> s) & 15 for s in range(28, -4, -4)) + bytes(7) + b"\x01"); ret(u, r[0] + 22); return
        if a in STOCKPAD: log.append(("stock", STOCKPAD[a], r[1])); ret(u); return
        if a == PREV_OUT: ret(u); return
    for a in list(FN.values()) + [C_PX, PREV_OUT] + list(STOCKPAD):
        uc.hook_add(UC_HOOK_CODE, h, None, a, a + 1)


C_PX = int(ET.MAN["report"]["storageshadow"]["labels"]["c_sh_pxmidi"], 16) & ~1
PREV_OUT = int(REP["prev_out"], 16)
STOCKPAD = {PREV["prev_proj"]: "proj", PREV["prev_smp"]: "smp", PREV["prev_pack"]: "pack"}


def tap(uc, fn, view, pad): log.clear(); px.clear(); call(uc, L[fn], view, pad, 100, 0)
def hold(uc, bits): w32(uc, HELD, (u32(uc, HELD) & ~(CLEAR | DUP)) | bits)
def tick(uc, ms): w32(uc, ET.C.HAL_TICK, u32(uc, ET.C.HAL_TICK) + ms)


def frame(uc, v):
    w32(uc, VIEW, v)
    uc.mem_write(OUT, struct.pack("<32I", *([0x0A0B0C] * 32)))
    call(uc, L["c_ft_out"], 0, OUT, 0, 0)
    return list(struct.unpack("<32I", uc.mem_read(OUT, 128)))


def rgb(uc, code): return u32(uc, COLOURS + 4 * code)
def reddish(c): return (c >> 16) & 0xFF > 0 and c & 0xFFFF == 0
def whiteish(c): return all((c >> s) & 255 for s in (0, 8, 16)) and c != 0x0A0B0C
def greenish(c): return (c >> 8) & 255 > 0 and c & 0xFF00FF == 0
def source(uc, c): return greenish(c) if HOLD else whiteish(c)
FT = int(REP["slot"], 16)
SMP_OK = 11 if REP.get("gap") else 5                                    # the sample source's "chosen" byte in the state


def again(uc, fn, view, slot, off):
    """(HOLD) the source chosen again: a copy forgets it"""
    if HOLD and not uc.mem_read(FT + off, 1)[0]:
        call(uc, L[fn], view, slot, 100, 0)


def projects(uc):
    pstore = u32(uc, PROJ + 0x20)
    check("the dump's Projects view is the stock's", u32(uc, PROJ) == PROJ_VT and u32(uc, PACKS) == PACKS_VT)
    setb(uc, u32(uc, PACKS + 0x10), 0, 3)                                  # pack 3 loaded
    setb(uc, pstore, 11, 5)                                                 # project 5 loaded
    for s in (2, 5, 9):
        disk[(2, s, 3)] = bytearray(bytes([s]) * SESS)
    setb(uc, pstore, 16, 0x43, 2)                                           # slot 2's colour
    hold(uc, 0)
    tap(uc, "c_ft_projpad", PROJ, 2)
    check("projects: without Duplicate a pad is the stock's", log == [("stock", "proj", 2)], log)
    hold(uc, DUP); setb(uc, TRANSPORT, 0, 1)
    tap(uc, "c_ft_projpad", PROJ, 2)
    check("projects: while it plays, Duplicate + pad does nothing", not log and not px, log)
    setb(uc, TRANSPORT, 0, 0)
    tap(uc, "c_ft_projpad", PROJ, 7)
    check("projects: an empty slot is no source", not any(e[0] == "write" for e in log) and not px)
    tap(uc, "c_ft_projpad", PROJ, 2)
    o = frame(uc, PROJ)
    check("projects: Duplicate + a project chooses it; its pad " + ("pulses green" if HOLD else "pulses white"), source(uc, o[2]) and o[7] == 0x0A0B0C, hex(o[2]))
    tap(uc, "c_ft_projpad", PROJ, 7)
    check("projects: Duplicate + an empty slot copies the project at once", disk.get((2, 7, 3)) == disk[(2, 2, 3)], log[:4])
    check("projects: the Plus file first, then the project, then the slot's older Plus files", [p[5] for p in px] == [0, 1] and px[0][1:5] == (3, 2, 3, 7), px)
    check("projects: the shared buffer is locked and freed; the watchdog fed; the storage task back on pack 3",
          log.count(("lock",)) == 1 == log.count(("unlock",)) and ("feed",) in log and log[-1] == ("resel", 3), log[-3:])
    used = u32(uc, p_new(uc, pstore, 12))
    check("projects: the copy is in the stock's list with the source's colour", used >> 7 & 1 and getb(uc, pstore, 16 + 1, 3) == 0x43, hex(used))
    o = frame(uc, PROJ)
    tick(uc, 150); o2 = frame(uc, PROJ)
    check("projects: the copy's pad pulses green", (o[7] >> 8) & 255 < (o2[7] >> 8) & 255 and (o2[7] >> 8) & 255 > 0, (hex(o[7]), hex(o2[7])))
    tick(uc, 1000)
    check("projects: then its own light again", frame(uc, PROJ)[7] == 0x0A0B0C)
    if HOLD:
        check("projects: after a copy the source is forgotten: its pad has its own light", frame(uc, PROJ)[2] == 0x0A0B0C and not uc.mem_read(FT + 1, 1)[0])
    again(uc, "c_ft_projpad", PROJ, 2, 1)
    before = bytes(disk[(2, 9, 3)])
    tap(uc, "c_ft_projpad", PROJ, 9)
    o = frame(uc, PROJ)
    check("projects: a slot with a project is asked first: no write, its pad pulses red", bytes(disk[(2, 9, 3)]) == before and not px and reddish(o[9]), hex(o[9]))
    hold(uc, 0); frame(uc, PROJ); hold(uc, DUP)
    if HOLD:
        check("projects: letting go of Duplicate forgets the source: no light", frame(uc, PROJ)[2] == 0x0A0B0C)
        tap(uc, "c_ft_projpad", PROJ, 9)
        check("projects: Duplicate again: a tap chooses a new source, nothing is copied", bytes(disk[(2, 9, 3)]) == before and source(uc, frame(uc, PROJ)[9]))
        tap(uc, "c_ft_projpad", PROJ, 9); tap(uc, "c_ft_projpad", PROJ, 2)
    tap(uc, "c_ft_projpad", PROJ, 9)
    check("projects: letting go of Duplicate forgets the question", bytes(disk[(2, 9, 3)]) == before)
    tap(uc, "c_ft_projpad", PROJ, 9)
    check("projects: the same pad again writes", disk[(2, 9, 3)] == disk[(2, 2, 3)])
    again(uc, "c_ft_projpad", PROJ, 2, 1)
    tap(uc, "c_ft_projpad", PROJ, 5)
    check("projects: the loaded project is never written", disk[(2, 5, 3)][0] == 5 and not px and reddish(frame(uc, PROJ)[5]))
    px_status[0] = 4
    tap(uc, "c_ft_projpad", PROJ, 12)
    check("projects: a missing Plus file stops the copy before the project is written", (2, 12, 3) not in disk and len(px) == 1)
    px_status[0] = 0
    if not HOLD:
        setb(uc, u32(uc, PACKS + 0x10), 0, 4)                              # another pack loaded
        tap(uc, "c_ft_projpad", PROJ, 1)
        check("projects: to another pack: pack 3's project into pack 4", disk.get((2, 1, 4)) == disk[(2, 2, 3)] and px[0][1:5] == (3, 2, 4, 1), px)
        check("projects: the source does not show in another pack", frame(uc, PROJ)[2] == 0x0A0B0C)
    again(uc, "c_ft_projpad", PROJ, 2, 1)
    hold(uc, DUP)
    setb(uc, u32(uc, PACKS + 0x10), 0, 0)                                  # the internal pack loaded
    tap(uc, "c_ft_projpad", PROJ, 3)
    check("projects: nothing is written to the internal pack", not any(k[2] == 0 for k in disk) and not px)
    setb(uc, u32(uc, PACKS + 0x10), 0, 3)
    tap(uc, "c_ft_projpad", PROJ, 2)
    check("projects: Duplicate + the source again forgets it", not source(uc, frame(uc, PROJ)[2]))
    disk[(2, 4, 0)] = bytearray(b"\x44" * SESS)
    setb(uc, u32(uc, PACKS + 0x10), 0, 0)
    tap(uc, "c_ft_projpad", PROJ, 4)
    setb(uc, u32(uc, PACKS + 0x10), 0, 3)
    tap(uc, "c_ft_projpad", PROJ, 20)
    check("projects: a project of the internal pack is copied to the card", disk.get((2, 20, 3)) == disk[(2, 4, 0)] and px[0][1] == 0)
    if HOLD:
        setb(uc, u32(uc, PACKS + 0x10), 0, 0); call(uc, L["c_ft_projpad"], PROJ, 4, 100, 0); setb(uc, u32(uc, PACKS + 0x10), 0, 3)
    uc.mem_write(PROJ + 0x36, b"\x01")
    tap(uc, "c_ft_projpad", PROJ, 0)
    check("projects: page 2's pad 1 is slot 33", disk.get((2, 32, 3)) == disk[(2, 4, 0)])
    uc.mem_write(PROJ + 0x36, b"\x00")
    hold(uc, 0)


def samples(uc):
    check("the dump's Sample Rec view is the stock's", u32(uc, SR) == SR_VT)
    smstate = u32(uc, SM + 0x20)
    setb(uc, smstate, 1, 0)
    disk[(4, 3, 3)] = bytearray(b"\x33" * 9000)
    disk[(4, 21, 3)] = bytearray(b"\x21" * 100)
    uc.mem_write(SR + 0xC, b"\x00")
    hold(uc, DUP)
    tap(uc, "c_ft_smppad", SR, 3)
    check("samples: Duplicate + a sample chooses it; its pad " + ("pulses green" if HOLD else "pulses white"), source(uc, frame(uc, SR)[3]))
    uc.mem_write(SR + 0xC, b"\x01")
    tap(uc, "c_ft_smppad", SR, 4)
    check("samples: Duplicate + an empty slot (page 2, pad 5 = slot 20) copies it", disk.get((4, 20, 3)) == disk[(4, 3, 3)])
    check("samples: the stock's routines take the new slot into the sound chip", ("refresh", 20) in log and ("reload", 20) in log and not any(e[0] == "delete" for e in log), log[-4:])
    if HOLD and not uc.mem_read(FT + SMP_OK, 1)[0]:
        uc.mem_write(SR + 0xC, b"\x00"); call(uc, L["c_ft_smppad"], SR, 3, 100, 0); uc.mem_write(SR + 0xC, b"\x01")
    tap(uc, "c_ft_smppad", SR, 5)
    check("samples: a slot with a sample is asked first", disk[(4, 21, 3)][0] == 0x21 and reddish(frame(uc, SR)[5]))
    tap(uc, "c_ft_smppad", SR, 5)
    check("samples: the same pad again: the old file deleted, the sample copied", disk[(4, 21, 3)] == disk[(4, 3, 3)] and ("delete", (4, 21, 3)) in log)
    dsp_free[0] = 0xE00000 - 0x400 - 100
    if HOLD and not uc.mem_read(FT + SMP_OK, 1)[0]:
        uc.mem_write(SR + 0xC, b"\x00"); call(uc, L["c_ft_smppad"], SR, 3, 100, 0); uc.mem_write(SR + 0xC, b"\x01")
    tap(uc, "c_ft_smppad", SR, 6)
    check("samples: no room in the sound chip's memory: nothing written", (4, 22, 3) not in disk and reddish(frame(uc, SR)[6]))
    dsp_free[0] = 0x100000
    setb(uc, smstate, 1, 1)
    if HOLD and not uc.mem_read(FT + SMP_OK, 1)[0]:
        uc.mem_write(SR + 0xC, b"\x00"); call(uc, L["c_ft_smppad"], SR, 3, 100, 0); uc.mem_write(SR + 0xC, b"\x01")
    tap(uc, "c_ft_smppad", SR, 7)
    check("samples: while the stock saves or deletes a sample: nothing written", (4, 23, 3) not in disk)
    setb(uc, smstate, 1, 0)
    setb(uc, u32(uc, PACKS + 0x10), 0, 0)
    tap(uc, "c_ft_smppad", SR, 8)
    check("samples: nothing is written to the internal pack", (4, 24, 0) not in disk and not any(e[0] in ("write", "delete") for e in log))
    setb(uc, u32(uc, PACKS + 0x10), 0, 3)
    hold(uc, 0)
    tap(uc, "c_ft_smppad", SR, 8)
    check("samples: without Duplicate a pad is the stock's", log == [("stock", "smp", 8)])


def packs(uc):
    lst, card = u32(uc, PACKS + 0x14), u32(uc, PACKS + 0xC)
    setb(uc, card, 0, getb(uc, card, 0) | 1)
    setb(uc, u32(uc, PACKS + 0x10), 0, 3)
    for p in range(32):
        setb(uc, lst, p, 0x20 + p if p in (0, 3, 6, 7, 9) else 0xFF)
    for p in (6, 7, 9):
        disk[(4, 1, p)] = bytearray(b"s"); disk[(2, 1, p)] = bytearray(b"p")
    hold(uc, 0)
    tap(uc, "c_ft_packpad", PACKS, 6)
    check("packs: without Clear a pad is the stock's", log == [("stock", "pack", 6)])
    hold(uc, CLEAR)
    o = frame(uc, PACKS)
    cue = rgb(uc, 0x54)
    check("packs: Clear held: every pack that can go is dim red", all(o[p] == cue for p in (6, 7, 9)), [hex(o[p]) for p in (6, 7, 9)])
    check("packs: the loaded pack keeps its light; the internal pack and empty slots are dark", o[3] == 0x0A0B0C and o[0] == 0 and o[1] == 0 and o[31] == 0)
    tap(uc, "c_ft_packpad", PACKS, 6)
    o = frame(uc, PACKS)
    check("packs: one tap: nothing deleted, the pad pulses red", (4, 1, 6) in disk and reddish(o[6]) and o[6] != cue and o[7] == cue, hex(o[6]))
    tap(uc, "c_ft_packpad", PACKS, 7)
    check("packs: a tap on another pack asks about that one instead", (4, 1, 6) in disk and (4, 1, 7) in disk and reddish(frame(uc, PACKS)[7]))
    hold(uc, 0); frame(uc, PACKS); hold(uc, CLEAR)
    tap(uc, "c_ft_packpad", PACKS, 7)
    check("packs: letting go of Clear forgets the question", (4, 1, 7) in disk)
    tap(uc, "c_ft_packpad", PACKS, 7)
    check("packs: the second tap deletes the whole pack", not any(k[2] == 7 for k in disk) and ("delete", (1, 0, 7)) in log and log[-1] == ("resel", 3), log)
    check("packs: the slot is empty in the stock's list", getb(uc, lst, 7) == 0xFF)
    hold(uc, 0)
    o1 = frame(uc, PACKS); tick(uc, 150); o2 = frame(uc, PACKS); tick(uc, 150); o3 = frame(uc, PACKS)
    check("packs: then the pad pulses red", reddish(o2[7]) and (o2[7] >> 16) > (o1[7] >> 16) and (o3[7] >> 16) < (o2[7] >> 16), (hex(o1[7]), hex(o2[7]), hex(o3[7])))
    tick(uc, 1000)
    check("packs: three pulses, then the slot's own light", frame(uc, PACKS)[7] == 0x0A0B0C)
    hold(uc, CLEAR); tap(uc, "c_ft_packpad", PACKS, 9); hold(uc, 0)
    still = [frame(uc, PACKS) for _ in range(3) if not tick(uc, 400)]
    check("packs: Clear let go: no pad keeps a red or pulsing light", all(f == [0x0A0B0C] * 32 for f in still), [hex(x) for x in still[0][:12]])
    hold(uc, CLEAR); tap(uc, "c_ft_packpad", PACKS, 9)
    check("packs: and the pack asked about before Clear was let go is not deleted by one tap", (4, 1, 9) in disk)
    hold(uc, 0); frame(uc, PACKS)
    hold(uc, CLEAR)
    for p in (3, 0, 12):
        tap(uc, "c_ft_packpad", PACKS, p); tap(uc, "c_ft_packpad", PACKS, p)
    check("packs: the loaded pack, the internal pack and an empty slot are never deleted", not any(e[0] == "delete" for e in log) and (4, 1, 6) in disk)
    setb(uc, TRANSPORT, 0, 1)
    tap(uc, "c_ft_packpad", PACKS, 9); tap(uc, "c_ft_packpad", PACKS, 9)
    o = frame(uc, PACKS)
    check("packs: while it plays: no red pads, nothing deleted", (4, 1, 9) in disk and o[9] == 0x0A0B0C)
    setb(uc, TRANSPORT, 0, 0)
    sh = u32(uc, CTRL + 0xC)
    setb(uc, sh, 0, getb(uc, sh, 0) | 1)
    tap(uc, "c_ft_packpad", PACKS, 9)
    check("packs: Shift + Clear: the stock's", log == [("stock", "pack", 9)])
    setb(uc, sh, 0, getb(uc, sh, 0) & ~1)
    hold(uc, 0)


def buttons(uc):
    """Slot 8 of each view: the buttons the stock lights (bit 0 Clear, bit 1 Duplicate)."""
    stock = dict(proj=0x0804F54A, smp=0x08069758, pack=0x0804E0A6)
    for name, view, vt, add in (("proj", PROJ, PROJ_VT, 2), ("smp", SR, SR_VT, 2), ("pack", PACKS, PACKS_VT, 1)):
        call(uc, stock[name], view); want = uc.reg_read(UC_ARM_REG_R0) & 0xFF
        hook = u32(uc, vt + 0x20) & ~1
        if REP.get("buttons"):
            call(uc, hook, view); got = uc.reg_read(UC_ARM_REG_R0) & 0xFF
            check(f"buttons: {name} lights the stock's buttons and {'Duplicate' if add == 2 else 'Clear'}",
                  hook == L[f"c_ft_{name}use"] and got == want | add, (hex(hook), want, got))
        else:
            check(f"buttons: {name} keeps the stock's slot 8", hook == stock[name])


def main():
    stock, fw, ram = (Path(a).read_bytes() for a in sys.argv[1:4])
    uc = ET.setup(fw, ram)
    hooks(uc)
    setb(uc, TRANSPORT, 0, 0)
    projects(uc)
    samples(uc)
    packs(uc)
    buttons(uc)
    print("ALL PASS" if not ET.FAILS else f"{len(ET.FAILS)} FAILED")


if __name__ == "__main__":
    main()
