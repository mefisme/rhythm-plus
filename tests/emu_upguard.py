"""Unicorn test of upguard.py on the RAM dump.
    python tests/emu_upguard.py STOCK.bin BUILT.bin RAM.bin      (RH_BUILD = the build's folder)
The two upload calls go through c_upw (the mark set during the upload, cleared after, its result kept); Stock+'s c_spw and fshape's c_flsw
write through c_dspw: the stock's 0x08031200 with the same words without the mark, nothing with it.
"""
import json
import os
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs  # noqa: E402
from emu_playfix import call, machine  # noqa: E402
from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2  # noqa: E402
import upguard as U  # noqa: E402

FAILS = []
MAN = json.loads((HERE / "firmware" / os.environ["RH_BUILD"] / "manifest.json").read_text())
R = MAN["report"]
G = R["upguard"]
FLAG = int(G["flag"], 16)
C_UPW, C_DSPW = int(G["labels"]["c_upw"], 16), int(G["labels"]["c_dspw"], 16)


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAILS.append(name)


def bl_at(fw, at):
    i = next(Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(fw[at - 0x08010000:at - 0x08010000 + 4], at))
    return i.mnemonic, int(i.op_str.lstrip("#"), 16)


def ret(u):
    u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))


def core(addr):
    """-> the cores c_dspw writes core 1's Y:addr to, in order"""
    if "route" not in G:
        return (1,)
    only0, both = ([(int(a, 16), int(b, 16)) for a, b in r] for r in G["route"])
    if any(lo <= addr < hi for lo, hi in only0):
        return (0,)
    if any(lo <= addr < hi for lo, hi in both):
        return (0, 1)
    return (1,)


def main():
    stock, fw, ram = (open(p, "rb").read() for p in sys.argv[1:4])
    for at in U.CALLS:
        check(f"{at:#x}: stock bl to the upload", bl_at(stock, at) == ("bl", U.UPLOAD))
        check(f"{at:#x}: bl c_upw", bl_at(fw, at) == ("bl", C_UPW))
    for (mod, lab, off), at in zip(U.WRITERS, G["writers"]):
        at = int(at, 16)
        check(f"{lab}: its write is bl c_dspw", at == int(R[mod]["labels"][lab], 16) + off and bl_at(fw, at) == ("bl", C_DSPW))

    uc = machine(fw, ram)
    seen, writes = [], []

    def upload(u, a, s, d):
        seen.append((u.mem_read(FLAG, 1)[0], u.reg_read(UC_ARM_REG_R0)))
        u.reg_write(UC_ARM_REG_R0, 0x1234)
        ret(u)

    def wr16(u, a, s, d):
        writes.append(tuple(u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)))
        ret(u)
    uc.hook_add(UC_HOOK_CODE, upload, None, U.UPLOAD, U.UPLOAD + 1)
    uc.hook_add(UC_HOOK_CODE, wr16, None, U.WR16, U.WR16 + 1)

    uc.mem_write(FLAG, b"\x00")
    call(uc, C_UPW, 5, 0, 0, 0)
    check("c_upw: the upload with the mark set, the slot passed", seen == [(1, 5)], f"{seen}")
    check("c_upw: the mark cleared after, the upload's result kept",
          uc.mem_read(FLAG, 1)[0] == 0 and uc.reg_read(UC_ARM_REG_R0) == 0x1234)

    spw, flsw = int(R["stockplus"]["labels"]["c_spw"], 16), int(R["fshape"]["labels"]["c_flsw"], 16)
    for mark in (0, 1):
        uc.mem_write(FLAG, bytes([mark]))
        writes.clear()
        call(uc, spw, 0x123456, 0x1E70)
        call(uc, flsw, 0x654321, 0x37328)
        want = [] if mark else [(core(0x1E70)[0], 0x123456 << 8 & 0xFFFFFFFF, 0x9E70), (0, 0x654321 << 8 & 0xFFFFFFFF, 0x37328)]
        check(f"mark {mark}: Stock+'s and fshape's writes {'dropped' if mark else 'as the stock writes them'}", writes == want,
              f"{[tuple(hex(x) for x in w) for w in writes]}")
    if "route" in G:
        only0, both = ([(int(a, 16), int(b, 16)) for a, b in r] for r in G["route"])
        uc.mem_write(FLAG, bytes([0]))
        bad = []
        edges = sorted({x for lo, hi in only0 + both for x in (lo - 1, lo, hi - 1, hi)})
        for addr in edges:
            writes.clear()
            call(uc, spw, 0x0ABCDE, addr)
            want = [(c, 0x0ABCDE << 8, 0x8000 | addr) for c in core(addr)]
            if writes != want:
                bad.append((hex(addr), [tuple(hex(x) for x in w) for w in writes]))
        check(f"route: core 1 Y words at the ranges' edges to core 1, core 0 only {only0} or both {both}", not bad, bad[:3])
        writes.clear()
        call(uc, flsw, 0x111111, 0x9E70)
        check("route: a core 0 word passes as it is", writes == [(0, 0x111111 << 8, 0x9E70)], writes)
        uc.mem_write(FLAG, bytes([1]))
        writes.clear()
        call(uc, spw, 0x0ABCDE, both[0][0])
        check("route: with the mark set, nothing to either core", writes == [], writes)
    print("ALL PASS" if not FAILS else f"FAILED: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
