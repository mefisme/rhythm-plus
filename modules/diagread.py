"""Read-only remote diagnostics over USB SysEx (MIT; from Circuit Remix's tools/rdiag.py by Ghillermo, its framing and command numbers).

Commands: 1 ping, 2 mem (flash / RAM), 4 info and 5 read (the storage task's content API), 3 dspr (DSP words). Commands 6 and 9 (the
SD and DSP writes) are not built: they get the unknown-command reply. dspr reads mapped DSP memory only, after core 1's start.
"""
from pathlib import Path
import os
import struct
import sys
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import rdiag as RD
import rhbuild
import rhstate
import cthresh as TH
from thumb import (Asm, b, b_cond, b_w, bl, cmp_imm, cmp_reg, ldr_imm, ldrb_imm, lsls_imm, lsrs_imm, mov_reg, movs_imm, movt, movw,
                   adds_imm8, adds_reg, subs_imm8, subs_reg, pop_list, push_list, raw, h, str_imm, strb_imm, add_sp_imm, sub_sp_imm,
                   orrs_reg, str_sp)

CMDS = ((1, "rc_ping"), (2, "rc_mem"), (4, "rc_info"), (5, "rc_read"), (3, "rc_dspr"))
VERSION = RD.VERSION + 0x10 + 0x02                      # the host tool's dsp=2 reply: DSP reads with the 16-bit accessors
WAIT_FRAMES = 200                                       # dspr waits this many LED frames after core 1's READY


def ready_wait_address():
    if os.environ.get('RH_GRANULAR_CURRENT_ARM')=='1':
        from granular_bridge import ready_wait_address as bridge_wait_address
        return bridge_wait_address(current=True)
    offset = rhstate.OFF['spwait'][0] if 'spwait' in rhstate.OFF else rhstate.OFF['smswitch'][0]+2
    return rhstate.ST+offset


PX_HOLD = h(0xE7FE) + h(0xE7FE)                       # rc_ext until storageshadow points it at c_sh_pxmidi


def arm_code(base, router_ptr, itcm=False, plus=False):
    a = Asm(base)
    E = a.emit
    zc = [0]

    def bc(target, cond):
        zc[0] += 1
        n = f"_r{zc[0]}"
        E(b_cond, n, RD.INV[cond]); E(b, target); a.label(n)

    def imm32(rd, v):
        E(movw, rd, v & 0xFFFF); E(movt, rd, v >> 16)

    # ---- c_rdin: the hooked entry (r0 = port, r1 = msg {buf, len}, r2)
    a.label("c_rdin")
    E(push_list, [0, 1, 2, 4, 5, 6, 7], lr=True)
    E(ldr_imm, 4, 1, 0); E(ldr_imm, 5, 1, 4)                                   # r4 = buf, r5 = len
    E(cmp_imm, 5, 8); bc("ri_fwd", "lo")
    for i, v in enumerate(RD.SIG):
        E(ldrb_imm, 3, 4, i); E(cmp_imm, 3, v); bc("ri_fwd", "ne")
    E(mov_reg, 6, 0)                                                           # r6 = port
    E(bl, "c_rdcmd")
    E(pop_list, [0, 1, 2, 4, 5, 6, 7], pc=True)                                # swallowed
    a.label("ri_fwd")
    E(raw, RD.popw([0, 1, 2, 4, 5, 6, 7], lr=True))
    E(raw, RD.PROLOGUE)
    E(b_w, RD.HOOK_CONT)

    # ---- c_g32 (r0 = ptr) -> r0 = u32 from 8 nibbles; clobbers r1-r3
    a.label("c_g32")
    E(movs_imm, 1, 0); E(movs_imm, 2, 8)
    a.label("g32_l")
    E(ldrb_imm, 3, 0, 0); E(adds_imm8, 0, 1); E(lsls_imm, 1, 1, 4)
    E(lsls_imm, 3, 3, 28); E(lsrs_imm, 3, 3, 28); E(orrs_reg, 1, 3)
    E(subs_imm8, 2, 1); E(b_cond, "g32_l", "ne")
    E(mov_reg, 0, 1); E(raw, h(0x4770))

    # ---- c_p32 (r0 = ptr, r1 = value) -> 8 nibbles, r0 = ptr + 8; clobbers r2, r3
    a.label("c_p32")
    E(movs_imm, 2, 8)
    a.label("p32_l")
    E(lsrs_imm, 3, 1, 28); E(strb_imm, 3, 0, 0); E(adds_imm8, 0, 1); E(lsls_imm, 1, 1, 4)
    E(subs_imm8, 2, 1); E(b_cond, "p32_l", "ne")
    E(raw, h(0x4770))

    # ---- c_pbytes (r0 = dst, r1 = src, r2 = n) -> 2 nibbles per byte, r0 = dst end; clobbers r1-r3
    a.label("c_pbytes")
    E(cmp_imm, 2, 0); E(b_cond, "pb_x", "eq")
    a.label("pb_l")
    E(ldrb_imm, 3, 1, 0); E(adds_imm8, 1, 1)
    E(push_list, [3]); E(lsrs_imm, 3, 3, 4); E(strb_imm, 3, 0, 0); E(pop_list, [3])
    E(lsls_imm, 3, 3, 28); E(lsrs_imm, 3, 3, 28); E(strb_imm, 3, 0, 1); E(adds_imm8, 0, 2)
    E(subs_imm8, 2, 1); E(b_cond, "pb_l", "ne")
    a.label("pb_x"); E(raw, h(0x4770))

    # ---- c_rdcmd (r4 = buf, r5 = len, r6 = port): the reply is written over buf; r7 = write pointer
    a.label("c_rdcmd")
    E(cmp_imm, 5, RD.PAD - 4); E(b_cond, "rc_go", "hs"); E(raw, h(0x4770))     # not padded: no reply
    a.label("rc_go")
    E(push_list, [4, 5, 6, 7], lr=True)
    E(sub_sp_imm, 40); E(mov_reg, 7, 13)                                       # frame: [0] cb [4] ctx [8] &done [12] done [16..27] item [32] msg
    E(movs_imm, 0, 0)
    for o in range(0, 40, 4):
        E(str_imm, 0, 7, o)
    E(ldrb_imm, 0, 4, 4); E(movs_imm, 1, 0x40); E(orrs_reg, 1, 0); E(strb_imm, 1, 4, 4)   # cmd | 0x40 (r0 = cmd)
    E(push_list, [0]); E(mov_reg, 0, 4); E(adds_imm8, 0, 6); E(mov_reg, 1, 0); E(pop_list, [0])   # r1 = payload pointer
    for cmd, lab in CMDS:
        E(cmp_imm, 0, cmd); bc(lab, "eq")
    if plus:                                                                   # 0x20-0x2F: Plus files, c_sh_pxmidi(buf, len, port) -> end
        E(cmp_imm, 0, 0x20); bc("rc_unk", "lo"); E(cmp_imm, 0, 0x2F); bc("rc_unk", "hi")
        E(mov_reg, 0, 4); E(mov_reg, 1, 5); E(mov_reg, 2, 6); E(bl, "rc_ext"); E(b, "rc_send")
        a.label("rc_unk")
    E(mov_reg, 0, 1); imm32(1, 0xFFFFFFFF); E(bl, "c_p32"); E(b, "rc_send")   # unknown command: status -1

    a.label("rc_ping")
    E(mov_reg, 0, 1); imm32(1, VERSION); E(bl, "c_p32")
    E(mov_reg, 1, 6); E(bl, "c_p32"); E(b, "rc_send")

    def item_from(off):                          # the item {kind, idx, pack} from buf[off..off+2] into the frame; pack 0x7F -> 0xFF
        E(ldrb_imm, 0, 4, off); E(str_imm, 0, 7, 16)
        E(ldrb_imm, 0, 4, off + 1); E(str_imm, 0, 7, 20)
        E(ldrb_imm, 0, 4, off + 2); E(cmp_imm, 0, 0x7F)
        zc[0] += 1
        n = f"_pk{zc[0]}"
        E(b_cond, n, "ne"); E(movs_imm, 0, 0xFF); a.label(n); E(strb_imm, 0, 7, 24)

    def item_ptr(rd):
        E(mov_reg, rd, 7); E(adds_imm8, rd, 16)

    def raw_ptr(rd):
        E(mov_reg, rd, 4); E(adds_imm8, rd, RD.RAW)

    def clamp_n(off, rd):                        # rd = min(buf[off], NMAX)
        E(ldrb_imm, rd, 4, off); E(cmp_imm, rd, RD.NMAX)
        zc[0] += 1
        n = f"_cl{zc[0]}"
        E(b_cond, n, "ls"); E(movs_imm, rd, RD.NMAX); a.label(n)

    # mem: addr = g32(buf + 6), n = buf[14]
    a.label("rc_mem")
    E(mov_reg, 0, 4); E(adds_imm8, 0, 6); E(bl, "c_g32"); E(push_list, [0])   # [sp] = addr
    clamp_n(14, 2); E(pop_list, [1])                                           # r1 = addr, r2 = n
    E(adds_reg, 3, 1, 2)                                                       # r3 = end
    for k, (lo, hi) in enumerate((RD.FLASH, RD.RAM) + (((0x100,0x4000),) if itcm else ())):
        imm32(0, lo); E(cmp_reg, 1, 0); bc(f"mm_n{k}", "lo")
        imm32(0, hi); E(cmp_reg, 3, 0); bc(f"mm_n{k}", "hi")
        if itcm and lo==0x100:
            imm32(0,0xe000ef90); E(ldr_imm,0,0,0); E(cmp_imm,0,0x73); bc(f"mm_n{k}","ne")
        E(b, "mm_ok")
        a.label(f"mm_n{k}")
    E(mov_reg, 0, 4); E(adds_imm8, 0, 6); E(movs_imm, 1, 1); E(bl, "c_p32"); E(b, "rc_send")
    a.label("mm_ok")
    E(push_list, [1, 2])
    E(mov_reg, 0, 4); E(adds_imm8, 0, 6); E(movs_imm, 1, 0); E(bl, "c_p32")
    E(pop_list, [1, 2]); E(bl, "c_pbytes"); E(b, "rc_send")

    # info: exists, size
    a.label("rc_info")
    item_from(6)
    item_ptr(0); E(bl, RD.EXISTS); E(mov_reg, 1, 0); E(mov_reg, 0, 4); E(adds_imm8, 0, 6); E(bl, "c_p32"); E(push_list, [0])
    item_ptr(0); E(bl, RD.SIZE); E(mov_reg, 1, 0); E(pop_list, [0]); E(bl, "c_p32"); E(b, "rc_send")

    # read: item, off = g32(buf + 9), n = buf[17] -> status, done, bytes
    a.label("rc_read")
    item_from(6)
    E(mov_reg, 0, 4); E(adds_imm8, 0, 9); E(bl, "c_g32"); E(mov_reg, 1, 0)   # r1 = offset
    clamp_n(17, 3); E(str_imm, 3, 7, 36)                                       # n kept at [36]
    E(mov_reg, 0, 7); E(adds_imm8, 0, 12); E(str_imm, 0, 7, 8)                 # &done
    item_ptr(0); raw_ptr(2)
    E(bl, RD.READ)
    E(mov_reg, 1, 0); E(mov_reg, 0, 4); E(adds_imm8, 0, 6); E(bl, "c_p32")
    E(ldr_imm, 1, 7, 12); E(bl, "c_p32")
    raw_ptr(1); E(ldr_imm, 2, 7, 12); E(ldr_imm, 3, 7, 36); E(cmp_reg, 2, 3)
    zc[0] += 1
    E(b_cond, f"_dn{zc[0]}", "ls"); E(mov_reg, 2, 3); a.label(f"_dn{zc[0]}")
    E(bl, "c_pbytes"); E(b, "rc_send")

    # dspr: core = buf[6] (0 / 1), addr = g32(buf + 7), n = buf[15] (1..NR) -> status 0, n words as 6 nibbles; else status 1
    a.label("rc_dspr")
    E(cmp_imm, 5, 17); bc("ds_bad", "lo")                                      # the request through byte 15 and F7
    imm32(0, rhstate.ST); E(ldr_imm, 0, 0, 0); imm32(1, rhstate.MAGIC); E(cmp_reg, 0, 1); bc("ds_bad", "ne")
    imm32(0, rhstate.ST + rhstate.OFF["cthresh"][0] + 1); E(ldrb_imm, 0, 0, 0); E(cmp_imm, 0, TH.READY); bc("ds_bad", "ne")
    wait = ready_wait_address()
    imm32(0, wait); E(ldrb_imm, 0, 0, 0); E(cmp_imm, 0, WAIT_FRAMES); bc("ds_bad", "lo")
    E(ldrb_imm, 0, 4, 6); E(str_imm, 0, 7, 28); E(cmp_imm, 0, 1); bc("ds_bad", "hi")   # [28] = core
    E(mov_reg, 0, 4); E(adds_imm8, 0, 7); E(bl, "c_g32"); E(str_imm, 0, 7, 16); E(mov_reg, 2, 0)   # [16] = addr
    E(ldrb_imm, 1, 4, 15); E(cmp_imm, 1, 0); bc("ds_bad", "eq")
    E(cmp_imm, 1, RD.NR); E(b_cond, "dr_nr", "ls"); E(movs_imm, 1, RD.NR)
    a.label("dr_nr"); E(str_imm, 1, 7, 20)                                     # [20] = n
    E(subs_imm8, 1, 1); E(adds_reg, 1, 1, 2)                                   # r1 = the last address: both in one bank
    E(ldr_imm, 3, 7, 28)
    imm32(0, 0x30000); E(cmp_reg, 2, 0); E(b_cond, "dr_sh", "hs")
    imm32(0, 0x8000); E(cmp_reg, 2, 0); E(b_cond, "dr_y", "hs")
    E(cmp_imm, 3, 0); E(b_cond, "dr_x1", "ne"); imm32(0, 0x6000); E(b, "dr_end")
    a.label("dr_x1"); imm32(0, 0x3000); E(b, "dr_end")
    a.label("dr_y"); E(cmp_imm, 3, 0); E(b_cond, "dr_y1", "ne"); imm32(0, 0xC000); E(b, "dr_end")
    a.label("dr_y1"); imm32(0, 0xA000); E(b, "dr_end")
    a.label("dr_sh"); imm32(0, 0x38000)
    a.label("dr_end"); E(cmp_reg, 1, 0); bc("ds_bad", "hs")
    E(cmp_reg, 1, 2); bc("ds_bad", "lo")                                       # a wrap past the top
    E(mov_reg, 0, 4); E(adds_imm8, 0, 6); E(movs_imm, 1, 0); E(bl, "c_p32"); E(str_imm, 0, 7, 24)
    a.label("dr_l")
    E(ldr_imm, 0, 7, 20); E(cmp_imm, 0, 0); bc("dr_x", "eq"); E(subs_imm8, 0, 1); E(str_imm, 0, 7, 20)
    E(ldr_imm, 0, 7, 28); E(ldr_imm, 1, 7, 16)
    E(movs_imm, 2, 1); E(lsls_imm, 2, 2, 16); E(cmp_reg, 1, 2); E(b_cond, "dr_w", "hs")
    E(bl, "c_d16r"); E(b, "dr_got")
    a.label("dr_w")
    E(bl, RD.DSP_READ)
    a.label("dr_got"); E(lsrs_imm, 1, 0, 8)
    E(ldr_imm, 0, 7, 16); E(adds_imm8, 0, 1); E(str_imm, 0, 7, 16)
    E(ldr_imm, 0, 7, 24); E(lsls_imm, 1, 1, 8); E(bl, "c_p32"); E(subs_imm8, 0, 2); E(str_imm, 0, 7, 24)   # 6 nibbles
    E(b, "dr_l")
    a.label("dr_x")
    E(ldr_imm, 0, 7, 24); E(b, "rc_send")
    a.label("ds_bad")
    E(mov_reg, 0, 4); E(adds_imm8, 0, 6); E(movs_imm, 1, 1); E(bl, "c_p32"); E(b, "rc_send")

    # ---- c_d16r (r0 = core, r1 = addr < 0x10000) -> r0 = word << 8: the 16-bit read under the DSP service's lock; the cached write
    #      address dropped (the DSP's pointer moved)
    a.label("c_d16r")
    E(push_list, [4, 5, 6], lr=True); E(sub_sp_imm, 8)
    E(mov_reg, 4, 0); E(mov_reg, 5, 1)
    imm32(6, RD.DSP_WADDR); E(mov_reg, 0, 6); E(adds_imm8, 0, 4); E(str_sp, 0, 0); E(mov_reg, 1, 0)
    E(bl, RD.DSP_LOCK)
    E(mov_reg, 0, 4); E(mov_reg, 1, 5); E(bl, RD.DSP_RD16); E(mov_reg, 5, 0)
    E(movw, 0, 0xFFFF); E(str_imm, 0, 6, 0)
    E(mov_reg, 0, 13); E(bl, RD.DSP_UNLOCK)
    E(mov_reg, 0, 5); E(add_sp_imm, 8); E(pop_list, [4, 5, 6], pc=True)

    # r0 = end of the payload: F7, then send {buf, end + 1 - buf} to the port it came from
    a.label("rc_send")
    E(movs_imm, 1, 0xF7); E(strb_imm, 1, 0, 0); E(adds_imm8, 0, 1); E(subs_reg, 0, 0, 4)
    E(str_imm, 4, 7, 32); E(str_imm, 0, 7, 36)
    imm32(0, router_ptr); E(ldr_imm, 0, 0, 0)                                  # r0 = the router
    E(movs_imm, 1, 1); E(raw, h(0x40B1))                                       # lsls r1, r6 -> mask = 1 << port
    E(mov_reg, 2, 7); E(adds_imm8, 2, 32)
    E(bl, RD.ROUTER)
    E(add_sp_imm, 40); E(pop_list, [4, 5, 6, 7], pc=True)
    if plus:
        a.label("rc_ext"); E(raw, PX_HOLD)
    return a.assemble()


def install(img, report, base_addr):
    B = rhbuild.BASE
    assert bytes(img[RD.HOOK - B:RD.HOOK - B + 4]) == RD.PROLOGUE, img[RD.HOOK - B:RD.HOOK - B + 4].hex()
    router_ptr = struct.unpack_from("<I", img, RD.ROUTER_LIT - B)[0]
    heads = [(RD.DSP_READ, "push {r2, r3, r4, r5, r6, lr}|mov r5, r1"), (RD.DSP_RD16, "push {r3, r4, r5, lr}|mov r4, r0"),
             (RD.DSP_LOCK, "push {r4, lr}|mov r4, r0"), (RD.DSP_UNLOCK, "ldr r2, [r0]|ldrexb r1, [r2]|ldrb r3, [r2, #1]")]
    for fn, head in heads:
        n = 8 if fn == RD.DSP_UNLOCK else 4
        assert "|".join(rhbuild.disasm(bytes(img[fn - B:fn - B + n]), fn)) == head, hex(fn)
    itcm=os.environ.get('RH_DIAG_ITCM_READ')=='1'
    plus=os.environ.get('RH_PLUS_USB')=='1'
    code, labels = arm_code(base_addr, router_ptr,itcm,plus)
    img += bytes([0xFF]) * (base_addr - B - len(img)) + code
    while len(img) % 4:
        img.append(0xFF)
    img[RD.HOOK - B:RD.HOOK - B + 4] = b_w(RD.HOOK, labels["c_rdin"])
    report["rdiag"] = dict(hook=hex(RD.HOOK), router_ptr=hex(router_ptr), version=hex(VERSION), dsp=2, readonly=True, mapped_ram_only=True,
                           itcm_read=itcm,**({'plus_usb':True} if plus else {}),
                           writes_disabled=[6, 9], max_dsp_words=RD.NR, guard=hex(labels["rc_dspr"]), dsp_wait=hex(ready_wait_address()),
                           labels={k: hex(v) for k, v in labels.items() if k.startswith("c_") or k.startswith("rc_") or k == "ds_bad"})
    return labels, code
