"""The count-in at the external MIDI clock's tempo (MIT; Circuit Rhythm 5706).

countin times its clicks from p0 of the tempo store, the project's tempo; with an external clock running that stays the old tempo.  Its one
tempo read (`movw/movt r0, TEMPO; movs r1, #0; bl c_cinew`) goes to c_cibpm instead.  The stock writes the measured BPM to the tempo store
only while playing, so c_cibpm measures it itself, as the stock's clock tick does (0x08032898):
  * the clock [0x200126E8] (vtable 0x08068EFC): byte + 0x54 bit 1 = an external clock is there (0x08032D38); + 0x64 = the clock's ms
    counter; + 0x7C = the filter of the last 49 pulse times;
  * the filter 0x08046D28(filter, now) -> pulses per ms * 2^32 (0 when a gap or now - the last pulse is over 1600 ms; it writes nothing);
    BPM = that * 2500 / 2^32.
When that BPM is 40..240 it is used, else fixedrec's c_frbpm (the project's tempo).  Install after countin and fixedrec.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import (Asm, add_sp_imm, adds_reg, b_cond, bl, cmp_imm, cmp_reg, ldr_imm, ldrb_imm, ldrb_w, lsls_imm, lsrs_imm, movt,  # noqa: E402
                   movw, muls, pop_list, push_list)
import countin  # noqa: E402
import fixedrec  # noqa: E402

FILTER = 0x08046D28
O_FLAGS, O_NOW, O_PULSES = 0x54, 0x64, 0x7C
EXT_BIT = 1
BPM_MIN, BPM_MAX = 40, 240


def find_read(img, report):
    """The `bl c_cinew` of countin's tempo read."""
    import capstone
    import rh_fw
    lab = {k: int(v, 16) for k, v in report["countin"]["labels"].items()}
    lo = int(report["countin"]["base"], 16)
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    ins = list(md.disasm(bytes(img[lo - rh_fw.APP_BASE:lo - rh_fw.APP_BASE + 0x400]), lo))
    want = [f"movw r0, #{countin.TEMPO & 0xFFFF:#x}", f"movt r0, #{countin.TEMPO >> 16:#x}", "movs r1, #0", f"bl #{lab['c_cinew']:#x}"]
    hits = [ins[k + 3].address for k in range(len(ins) - 3) if [f"{x.mnemonic} {x.op_str}" for x in ins[k:k + 4]] == want]
    assert len(hits) == 1, hits
    return hits[0], lab["c_cinew"]


def arm_code(base, c_frbpm):
    a = Asm(base)
    E = a.emit

    def imm32(rd, v):
        E(movw, rd, v & 0xFFFF)
        E(movt, rd, v >> 16)

    a.label("c_cibpm")                                    # r0 = the tempo store, r1 = 0 -> r0 = BPM
    E(push_list, [0, 1, 4], lr=True)
    imm32(4, fixedrec.CLOCK)
    E(ldr_imm, 0, 4, 0)
    imm32(1, fixedrec.CLOCK_VT)
    E(cmp_reg, 0, 1)
    E(b_cond, "cb_fb", "ne")
    E(ldrb_w, 0, 4, O_FLAGS)
    E(lsls_imm, 0, 0, 31 - EXT_BIT)
    E(b_cond, "cb_fb", "pl")                              # no external clock
    for k in range(2):                                    # twice: a pulse can land between reading now and the filter
        E(ldr_imm, 0, 4, O_PULSES)
        E(ldr_imm, 1, 4, O_NOW)
        E(bl, FILTER)
        E(cmp_imm, 0, 0)
        E(b_cond, "cb_got", "ne")
    E(b_cond, "cb_fb", "eq")
    a.label("cb_got")
    E(lsrs_imm, 0, 0, 16)
    E(movw, 1, 2500)
    E(muls, 0, 1)
    E(movw, 1, 0x8000)
    E(adds_reg, 0, 0, 1)
    E(lsrs_imm, 0, 0, 16)                                 # round(rate * 2500 / 2^32)
    E(cmp_imm, 0, BPM_MIN)
    E(b_cond, "cb_fb", "lo")
    E(cmp_imm, 0, BPM_MAX)
    E(b_cond, "cb_fb", "hi")
    E(add_sp_imm, 8)
    E(pop_list, [4], pc=True)
    a.label("cb_fb")
    E(pop_list, [0, 1])
    E(bl, c_frbpm)
    E(ldrb_imm, 0, 0, 0)
    E(pop_list, [4], pc=True)
    return a.assemble()


def install(img, report, base_addr):
    import rh_fw
    import rhbuild
    c_frbpm = int(report["fixedrec"]["labels"]["c_frbpm"], 16)
    site, c_cinew = find_read(img, report)
    code, labels = arm_code(base_addr, c_frbpm)
    img += bytes([0xFF]) * (base_addr - rh_fw.APP_BASE - len(img)) + code
    while len(img) % 4:
        img += bytes([0xFF])
    rhbuild.patch(img, site, f"bl #{c_cinew:#x}", bl(site, labels["c_cibpm"]))
    report["cibpm"] = dict(site=hex(site), labels={k: hex(v) for k, v in labels.items() if k.startswith("c_")})
    return labels, code
