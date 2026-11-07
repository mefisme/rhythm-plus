"""No DSP writes of ours while the stock uploads a sample (MIT; Circuit Rhythm 5706).

The stock's sample upload 0x08053E8C(slot) streams the PCM to core 0's host port without the DSP lock, the port held in its stream mode
between the chunks while the next chunk is read; a word written then by another task lands in the stream. Its two callers (the pack load
0x08053E24 and the single sample 0x080460B8) call c_upw instead, which marks the upload in our RAM slot around the call. Stock+'s c_spw and
fshape's c_flsw call c_dspw in place of 0x08031200: it drops the word while the mark is set (their rounds write every word again).
route = (core 0 only, both) ([(first, end)] of core 1 Y addresses, c0fx.routes()): a core 1 Y word there goes to core 0's Y at the same
address, or to both cores.
Install after stockplus and fshape; needs ourram's slot (RH_UPGUARD=1).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import Asm, b, b_cond, b_w, bl, bx_lr, cmp_imm, cmp_reg, ldr_sp, ldrb_imm, movs_imm, movt, movw, pop_list, push_list, strb_imm  # noqa: E402

UPLOAD = 0x08053E8C
CALLS = (0x08053E74, 0x080460BA)                         # bl UPLOAD in the pack load and the single sample load
WR16 = 0x08031200
WRITERS = (("stockplus", "c_spw", 16), ("fshape", "c_flsw", 8))   # (module, label, the bl WR16's offset in it)


def flag():
    import rhstate
    assert "upguard" in rhstate.OFF, "upguard needs ourram's slot (RH_UPGUARD=1)"
    return rhstate.ST + rhstate.OFF["upguard"][0]


def arm_code(base, route=None):
    f = flag()
    a = Asm(base)
    E = a.emit
    # ---- c_upw(r0-r3 = the upload's): the mark set around 0x08053E8C -> its r0
    a.label("c_upw")
    E(push_list, [4, 5, 6], lr=True)
    E(movw, 4, f & 0xFFFF); E(movt, 4, f >> 16)
    E(movs_imm, 5, 1)
    E(strb_imm, 5, 4, 0)
    E(bl, UPLOAD)
    E(movs_imm, 5, 0)
    E(strb_imm, 5, 4, 0)
    E(pop_list, [4, 5, 6], pc=True)
    # ---- c_dspw(r0 = core, r1 = word << 8, r2 = address): 0x08031200's, nothing while the mark is set; (route) a routed core 1 Y address
    #      to core 0 or to both; clobbers r3 as well
    a.label("c_dspw")
    E(movw, 3, f & 0xFFFF); E(movt, 3, f >> 16)
    E(ldrb_imm, 3, 3, 0)
    E(cmp_imm, 3, 0)
    E(b_cond, "dw_x", "ne")
    if route:
        only0, both = route
        E(cmp_imm, 0, 1)
        E(b_cond, "dw_go", "ne")
        for k, (lo, hi) in enumerate(only0):
            E(movw, 3, 0x8000 | lo)
            E(cmp_reg, 2, 3)
            E(b_cond, f"dw_n{k}", "lo")
            E(movw, 3, 0x8000 | hi)
            E(cmp_reg, 2, 3)
            E(b_cond, "dw_c0", "lo")
            a.label(f"dw_n{k}")
        for k, (lo, hi) in enumerate(both):
            E(movw, 3, 0x8000 | lo)
            E(cmp_reg, 2, 3)
            E(b_cond, f"dw_b{k}", "lo")
            E(movw, 3, 0x8000 | hi)
            E(cmp_reg, 2, 3)
            E(b_cond, f"dw_b{k}", "hs")
            E(push_list, [0, 1, 2], lr=True)
            E(movs_imm, 0, 0)
            E(bl, WR16)
            E(ldr_sp, 1, 4)
            E(ldr_sp, 2, 8)
            E(movs_imm, 0, 1)
            E(bl, WR16)
            E(pop_list, [0, 1, 2], pc=True)
            a.label(f"dw_b{k}")
        E(b, "dw_go")
        a.label("dw_c0")
        E(movs_imm, 0, 0)
        a.label("dw_go")
    E(b_w, WR16)
    a.label("dw_x")
    E(bx_lr)
    return a.assemble()


def install(img, report, base_addr, route=None):
    import rh_fw
    import rhbuild
    code, labels = arm_code(base_addr, route)
    img += bytes([0xFF]) * (base_addr - rh_fw.APP_BASE - len(img)) + code
    while len(img) % 4:
        img += bytes([0xFF])
    for at in CALLS:
        rhbuild.patch(img, at, f"bl #{UPLOAD:#x}", bl(at, labels["c_upw"]))
    sites = []
    for mod, lab, off in WRITERS:
        at = int(report[mod]["labels"][lab], 16) + off
        rhbuild.patch(img, at, f"bl #{WR16:#x}", bl(at, labels["c_dspw"]))
        sites.append(hex(at))
    report["upguard"] = dict(flag=hex(flag()), labels={k: hex(v) for k, v in labels.items() if k.startswith("c_")},
                             calls=[hex(x) for x in CALLS], writers=sites,
                             **({"route": [[[hex(x), hex(y)] for x, y in r] for r in route]} if route else {}))
    return labels, code
