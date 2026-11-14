"""Step Mutate (MIT): the stock's Shift + Duplicate Mutate on a track view, with settings for each track (stepmut.c).

Shift + tap Duplicate mutates the selected track's pattern from its start to its end step with that track's settings; Shift + hold
Duplicate (333 ms) opens the settings page, which a Duplicate press without Shift closes. The stock fires its Mutate on the press
(0x0804B620 sets bit 2 of the store 0x2003CED4; the track views' listener sends it to 0x08036394, which calls 0x08047E88 at
0x0803656C); the call is ours, and the mutate waits for Duplicate's release.
The page: targets on pads 1-3 (Note, Sample flip, Step movement), 9 (Velocity), 17-18 (Gate, Microsteps), 25-27 (Pattern speed,
Play mode, Probability); a tap turns a target on or off, a hold (400 ms) shows its settings on columns 5-8.
The settings: rhrec's tail + BLK_OFF, "SM", a check byte, 0, then 12 B a track (stepmut.c). Not ours: the defaults.
Compiled with zig cc (RH_ZIG, default buildtmp/zig-toolchain/ziglang/zig.exe). Install after mutset (the button, pad and output heads).
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / d) for d in ("modules", "builds", "tests", "remix/tools")]
import countin as C  # noqa: E402
import rhstate  # noqa: E402

SRC = ROOT / "modules" / "stepmut.c"
MUT_CALL, MUTATE = 0x0803656C, 0x08047E88
BLK_OFF, BLK_LEN = 404, 100
SLOT_LEN = 32
LABELS = ("c_sm_mut", "c_sm_btn", "c_sm_rel", "c_sm_pad", "c_sm_padrel", "c_sm_out", "c_sm_fxread", "c_sm_fxwrite", "c_sm_fxsample")


def _elf(data, origin, limit, prefix="c_sm_"):
    hdr = struct.unpack_from("<16sHHIIIIIHHHHHH", data)
    assert data[:4] == b"\x7fELF" and hdr[2] == 40
    secs = [struct.unpack_from("<10I", data, hdr[6] + i * hdr[11]) for i in range(hdr[12])]
    chunks, labels = [], {}
    for _, kind, flags, addr, off, size, link, _, _, ent in secs:
        if flags & 2 and size:
            assert kind != 8 and flags & 1 == 0, "stepmut.c: no writable data"
            assert origin <= addr and addr + size <= limit
            chunks.append((addr, data[off:off + size]))
        if kind == 2:
            st = secs[link]
            names = data[st[4]:st[4] + st[5]]
            for i in range(off, off + size, ent):
                n, v, _, info, _, idx = struct.unpack_from("<IIIBBH", data, i)
                n = names[n:].split(b"\0", 1)[0].decode()
                if idx and info & 15 == 2 and n.startswith(prefix):
                    labels[n] = v & ~1
    end = max(a + len(c) for a, c in chunks)
    code = bytearray(b"\xff" * (end - origin))
    for a, c in chunks:
        code[a - origin:a - origin + len(c)] = c
    return bytes(code), labels


def compile_c(origin, defs, src=SRC, name="stepmut", prefix="c_sm_", need=LABELS, max_code=0x4000):
    work = ROOT / "buildtmp" / name
    work.mkdir(parents=True, exist_ok=True)
    flags = [f"-D{k}={v:#x}" for k, v in sorted(defs.items())]
    key = hashlib.sha256(src.read_bytes() + json.dumps([origin] + flags).encode() + b"zig0.13-m7-Oz").hexdigest()
    meta, binf = work / f"{key[:16]}.json", work / f"{key[:16]}.bin"
    if meta.exists() and binf.exists():
        return binf.read_bytes(), {k: int(v, 16) for k, v in json.loads(meta.read_text()).items()}
    ld = work / f"{name}.ld"
    ld.write_text(f"SECTIONS {{ . = {origin:#x}; .text : {{ KEEP(*(.text*)) *(.rodata*) }} "
                  "/DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } }")
    zig = Path(os.environ.get("RH_ZIG", ROOT / "buildtmp/zig-toolchain/ziglang/zig.exe"))
    env = dict(os.environ, ZIG_GLOBAL_CACHE_DIR=str(work / "zig-global"), ZIG_LOCAL_CACHE_DIR=str(work / "zig-local"))
    elf = work / f"{name}.elf"
    args = [str(zig), "cc", "-I", str(ROOT / "modules"), "-target", "thumb-freestanding-eabi", "-mcpu=cortex_m7", "-mthumb", "-mfloat-abi=soft", "-Oz", "-g", "-fno-lto",
            "-ffreestanding", "-fno-builtin", "-fno-unwind-tables", "-fno-asynchronous-unwind-tables", "-fno-stack-protector",
            "-nostdlib", "-Wall", "-Werror", *flags, str(src), f"-Wl,-T,{ld}", f"-Wl,--entry={need[0]}", "-o", str(elf)]
    res = subprocess.run(args, env=env, capture_output=True, text=True)
    if res.returncode:
        raise SystemExit(f"{src.name}: " + res.stdout + res.stderr)
    code, labels = _elf(elf.read_bytes(), origin, origin + max_code, prefix)
    assert set(need) <= set(labels), labels
    binf.write_bytes(code)
    meta.write_text(json.dumps({k: hex(v) for k, v in labels.items()}))
    return code, labels


def install(img, report, base_addr):
    import rhbuild
    import rhrec
    import tmenu as T
    from thumb import b_w as bw_ins, bl as bl_ins
    assert "mutset" in report and "tmenu" in report and "stepmut" in rhstate.OFF, "stepmut: after mutset, ourram's slot"
    assert rhstate.OFF["stepmut"][1] >= SLOT_LEN
    taken = ((192, 84), (384, 20), (748, 112))                      # mutset's settings, smswitch, mutset's scenes
    assert all(BLK_OFF + BLK_LEN <= o or o + n <= BLK_OFF for o, n in taken) and BLK_OFF + BLK_LEN <= rhrec.FREE_LEN
    lab = lambda k, n: int(report[k]["labels"][n], 16)
    prev = dict(PREV_BTN=rhbuild.bw_target(img, C.BTN_ENTRY), PREV_REL=rhbuild.bw_target(img, C.BTN_RELEASE),
                PREV_PAD=rhbuild.bw_target(img, T.PP_ENTRY), PREV_PADREL=rhbuild.bw_target(img, T.PR_ENTRY),
                PREV_OUT=rhbuild.bl_target(img, T.OUT_CALL))
    base_addr = (base_addr + 3) & ~3
    defs = dict(prev, SLOT=rhstate.ST + rhstate.OFF["stepmut"][0], TM_SLOT=int(report["tmenu"]["slot"], 16), TM_OPEN=T.O_OPEN, TM_STICKY=T.O_STICKY,
                TM_PTRK=T.O_PTRK, TM_SHOP=T.O_SHOP, TM_BACK=T.O_BACK, TM_ARM=T.O_ARM, TM_ARM_OFF=T.ARM_OFF, BLK_OFF=BLK_OFF,
                C_RRT=lab("rhrec", "c_rrt"), C_CIOK=lab("countin", "c_ciok"))
    if os.environ.get("RH_STEPMUT_OFFLOAD") == "1": defs['OFFLOAD']=1
    code, labels = compile_c(base_addr, defs)
    img += bytes([0xFF]) * (base_addr - rhbuild.BASE - len(img)) + code
    while len(img) % 4:
        img += bytes([0xFF])
    rhbuild.patch(img, C.BTN_ENTRY, f"b.w #{prev['PREV_BTN']:#x}", bw_ins(C.BTN_ENTRY, labels["c_sm_btn"]))
    rhbuild.patch(img, C.BTN_RELEASE, f"b.w #{prev['PREV_REL']:#x}", bw_ins(C.BTN_RELEASE, labels["c_sm_rel"]))
    rhbuild.patch(img, T.PP_ENTRY, f"b.w #{prev['PREV_PAD']:#x}", bw_ins(T.PP_ENTRY, labels["c_sm_pad"]))
    rhbuild.patch(img, T.PR_ENTRY, f"b.w #{prev['PREV_PADREL']:#x}", bw_ins(T.PR_ENTRY, labels["c_sm_padrel"]))
    rhbuild.patch(img, T.OUT_CALL, f"bl #{prev['PREV_OUT']:#x}", bl_ins(T.OUT_CALL, labels["c_sm_out"]))
    rhbuild.patch(img, MUT_CALL, f"bl #{MUTATE:#x}", bl_ins(MUT_CALL, labels["c_sm_mut"]))
    report["stepmut"] = dict(slot=hex(defs["SLOT"]), blk_off=BLK_OFF, blk_len=BLK_LEN, code=len(code),
                             offload=bool(defs.get('OFFLOAD')),
                             prev={k.lower(): hex(v) for k, v in prev.items()}, labels={k: hex(v) for k, v in labels.items()})
    return labels, code
