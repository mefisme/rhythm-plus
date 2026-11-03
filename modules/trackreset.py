"""Confirmed per-track reset, current-pattern automation only (MIT; Rhythm Plus).

Clear + track arms red without forwarding the press; release and press the same
track with Clear still held to confirm. Clear release, a pad, or another button
cancels. Load snapshots follow Remix: 25 parameter bytes and selected sample.
Sound knobs/fine values and Stock+ use defaults; other parameters use the snapshot.
Notes and sample flips remain. No settings of another track or pattern are cleared.
"""
import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import (Asm, movw, movt, mov_reg, movs_imm, cmp_imm, cmp_reg,
                   ldr_imm, ldrb_imm, str_imm, strb_imm, adds_imm8, adds_reg,
                   subs_imm8, subs_reg, lsls_imm, lsls_reg, lsrs_imm, muls,
                   orrs_reg, tst_reg, bics_reg, b, b_w, b_cond, bl, raw, h,
                   push_list, pop_list, ldr_sp, str_sp)
import countin as C
import rhstate

SIZE, PHOTO, TAG = 220, 12, 0xC3
LOAD, RESEND = 0x080379AE, 0x08031A10
RELEASE, RELEASE_CONT = 0x0803DDB0, 0x0803DDB4
OUT_CALL = 0x0803E802
TRK_COLOURS = (0x43, 0x2F, 0x47, 0x4B, 0x37, 0x25, 0x12, 0x3B)


def install(img, report, base_addr, viewsync=False, softclear=False):
    import rhbuild
    assert rhstate.OFF['trackreset'][1] == SIZE
    slot = rhstate.ST + rhstate.OFF['trackreset'][0]
    prevbtn = rhbuild.bw_target(img, C.BTN_ENTRY)
    prevled = rhbuild.bl_target(img, C.LED_CALLS[0])
    prevout = rhbuild.bl_target(img, OUT_CALL)
    prevload = rhbuild.bw_target(img, LOAD)
    prevpad = rhbuild.bw_target(img, 0x0803D7FE)
    pcreset = int(report['pageclear']['labels']['c_pcreset'], 16)
    rst = int(report['rhstate']['labels']['c_rst'], 16)
    head = bytes(img[RELEASE-rhbuild.BASE:RELEASE-rhbuild.BASE+4])
    a = Asm(base_addr)
    E = a.emit
    def imm(r, v): E(movw, r, v & 65535); E(movt, r, v >> 16)
    def ret(regs): E(pop_list, regs, pc=True)
    # Stable slot pointer, zero when the shared reservation is unavailable.
    a.label('c_trstate')
    E(push_list, [4], lr=True); E(bl, rst); E(cmp_imm, 0, 0)
    E(b_cond, 'state_x', 'eq'); imm(0, slot)
    a.label('state_x'); ret([4])

    a.label('c_trphoto')
    E(push_list, [4, 5, 6, 7], lr=True)
    E(bl, 'c_trstate'); E(cmp_imm, 0, 0); E(b_cond, 'photo_x', 'eq')
    E(mov_reg, 7, 0); E(ldrb_imm, 0, 7, 0); E(cmp_imm, 0, TAG)
    E(b_cond, 'photo_x', 'eq')
    E(mov_reg, 6, 7); E(adds_imm8, 6, PHOTO); E(movs_imm, 4, 0)
    a.label('photo_track'); E(movs_imm, 5, 0)
    a.label('photo_param')
    E(mov_reg, 0, 4); E(adds_imm8, 0, 0x10); E(mov_reg, 1, 5); E(bl, 0x08046410)
    E(strb_imm, 0, 6, 0); E(adds_imm8, 6, 1)
    E(adds_imm8, 5, 1); E(cmp_imm, 5, 25); E(b_cond, 'photo_param', 'lo')
    E(mov_reg, 0, 4); E(bl, 'c_trsample')
    E(movs_imm, 1, 0); E(bl, C.PARAM_GET); E(ldrb_imm, 0, 0, 0)
    E(strb_imm, 0, 6, 0); E(adds_imm8, 6, 1)
    E(adds_imm8, 4, 1); E(cmp_imm, 4, 8); E(b_cond, 'photo_track', 'lo')
    E(movs_imm, 0, TAG); E(strb_imm, 0, 7, 0)
    a.label('photo_x'); ret([4, 5, 6, 7])
    a.label('c_trsample')
    E(movw, 1, 0x190); E(muls, 0, 1); imm(1, 0x200470D4)
    E(adds_reg, 0, 0, 1); E(ldr_imm, 0, 0, 0x60); E(raw, h(0x4770))

    # r0 target track. Restore non-knob settings, then reset pages and all 12 lanes.
    a.label('c_trreset')
    E(push_list, [4, 5, 6, 7], lr=True); E(mov_reg, 4, 0)
    E(bl, 'c_trphoto'); imm(7, slot)
    E(ldrb_imm, 0, 7, 0); E(cmp_imm, 0, TAG); E(b_cond, 'reset_x', 'ne')
    E(movs_imm, 0, 26); E(muls, 0, 4); E(adds_imm8, 0, PHOTO); E(adds_reg, 7, 7, 0)
    E(movs_imm, 5, 0)
    a.label('reset_param')
    E(cmp_imm, 5, 6); E(b_cond, 'reset_write', 'lo')
    E(cmp_imm, 5, 15); E(b_cond, 'reset_next', 'ls')
    a.label('reset_write')
    imm(0, 0x20010E10); E(mov_reg, 1, 4); E(adds_imm8, 1, 0x10)
    E(mov_reg, 2, 5); E(adds_reg, 3, 7, 5); E(ldrb_imm, 3, 3, 0); E(bl, 0x08031A38)
    if viewsync:
        E(mov_reg, 0, 4); E(mov_reg, 1, 5)
        E(adds_reg, 2, 7, 5); E(ldrb_imm, 2, 2, 0)
        E(bl, int(report['pageclear']['labels']['c_pcsync'], 16))
    a.label('reset_next')
    E(adds_imm8, 5, 1); E(cmp_imm, 5, 25); E(b_cond, 'reset_param', 'lo')
    E(mov_reg, 0, 4); E(bl, 'c_trsample'); E(mov_reg, 6, 0)
    E(movs_imm, 1, 0); E(bl, 0x0803FD26)
    E(ldrb_imm, 1, 7, 25); E(strb_imm, 1, 0, 0)
    E(mov_reg, 0, 6); E(bl, 0x0803FBEC)
    E(mov_reg, 0, 4); E(movs_imm, 1, 6); E(bl, pcreset)
    imm(0, 0x2003D380); E(lsls_imm, 1, 4, 2); E(adds_reg, 0, 0, 1); E(ldr_imm, 4, 0, 0)
    E(ldr_imm, 0, 4, 0x40); E(movs_imm, 1, 0); E(bl, C.PARAM_GET)
    E(mov_reg, 6, 0); E(ldrb_imm, 7, 6, 0)
    E(movs_imm, 0, 0); E(strb_imm, 0, 6, 0); E(movs_imm, 5, 8)
    a.label('reset_lane')
    E(mov_reg, 0, 4); E(mov_reg, 1, 5); E(bl, 0x08047CA8)
    E(adds_imm8, 5, 1); E(cmp_imm, 5, 12); E(b_cond, 'reset_lane', 'lo')
    E(strb_imm, 7, 6, 0)
    a.label('reset_x'); ret([4, 5, 6, 7])

    # Button wrapper consumes protected track presses before Stock+ or Track + sees them.
    a.label('c_trbtn')
    E(push_list, [0, 1, 4, 5, 6, 7], lr=True)
    E(mov_reg, 5, 1); E(bl, 'c_trstate'); E(cmp_imm, 0, 0)
    E(b_cond, 'btn_pass', 'eq'); E(mov_reg, 4, 0)
    E(cmp_imm, 5, 8); E(b_cond, 'btn_cancel', 'hs')
    imm(0, C.CTRL + 0xA0); E(ldr_imm, 6, 0, 0)
    E(lsls_imm, 0, 6, 8); E(b_cond, 'btn_cancel', 'pl')
    E(lsls_imm, 0, 6, 7); E(b_cond, 'btn_cancel', 'mi')  # Duplicate
    imm(0, C.CTRL); E(ldr_imm, 0, 0, 0x7C); imm(1, 0x20048B9C)
    E(cmp_reg, 0, 1); E(b_cond, 'btn_cancel', 'ne')
    from thumb import ldrb_w
    E(ldrb_w, 0, 0, 0x264); E(cmp_imm, 0, 8); E(b_cond, 'btn_cancel', 'eq')
    E(movs_imm, 6, 1); E(lsls_reg, 6, 5)
    E(ldr_imm, 0, 4, 8); E(tst_reg, 0, 6); E(b_cond, 'btn_taken', 'ne')
    E(orrs_reg, 0, 6); E(str_imm, 0, 4, 8)
    E(ldrb_imm, 0, 4, 1); E(cmp_imm, 0, 0); E(b_cond, 'btn_arm', 'eq')
    E(mov_reg, 1, 5); E(adds_imm8, 1, 1); E(cmp_reg, 0, 1)
    E(b_cond, 'btn_drop', 'ne')
    E(ldrb_imm, 0, 4, 2); E(cmp_imm, 0, 0); E(b_cond, 'btn_taken', 'eq')
    E(mov_reg, 0, 5); E(bl, 'c_trreset')
    E(mov_reg, 0, 5); E(adds_imm8, 0, 1); E(strb_imm, 0, 4, 3)
    imm(0, C.HAL_TICK); E(ldr_imm, 0, 0, 0); E(str_imm, 0, 4, 4)
    a.label('btn_drop')
    E(movs_imm, 0, 0); E(strb_imm, 0, 4, 1); E(strb_imm, 0, 4, 2)
    E(b, 'btn_taken')
    a.label('btn_arm')
    E(mov_reg, 0, 5); E(adds_imm8, 0, 1); E(strb_imm, 0, 4, 1)
    E(movs_imm, 0, 0); E(strb_imm, 0, 4, 2); E(strb_imm, 0, 4, 3)
    a.label('btn_taken'); ret([0, 1, 4, 5, 6, 7])
    a.label('btn_cancel')
    E(movs_imm, 0, 0); E(strb_imm, 0, 4, 1); E(strb_imm, 0, 4, 2)
    a.label('btn_pass')
    E(raw, C.popw([0, 1, 4, 5, 6, 7], lr=True)); E(b_w, prevbtn)

    a.label('c_trrelease')
    E(push_list, [0, 1, 4, 5], lr=True); E(mov_reg, 5, 1)
    E(bl, 'c_trstate'); E(cmp_imm, 0, 0); E(b_cond, 'release_pass', 'eq')
    E(mov_reg, 4, 0); E(cmp_imm, 5, 23); E(b_cond, 'release_track', 'ne')
    E(movs_imm, 0, 0); E(strb_imm, 0, 4, 1); E(strb_imm, 0, 4, 2)
    a.label('release_track')
    E(cmp_imm, 5, 8); E(b_cond, 'release_pass', 'hs')
    E(ldr_imm, 0, 4, 8); E(movs_imm, 1, 1); E(lsls_reg, 1, 5)
    E(tst_reg, 0, 1); E(b_cond, 'release_pass', 'eq')
    E(bics_reg, 0, 1); E(str_imm, 0, 4, 8)
    E(ldrb_imm, 0, 4, 1); E(adds_imm8, 5, 1); E(cmp_reg, 0, 5)
    E(b_cond, 'release_done', 'ne'); E(movs_imm, 0, 1); E(strb_imm, 0, 4, 2)
    a.label('release_done'); ret([0, 1, 4, 5])
    a.label('release_pass')
    E(raw, C.popw([0, 1, 4, 5], lr=True)); E(raw, head); E(b_w, RELEASE_CONT)

    a.label('c_trload')
    E(push_list, [0, 1, 2, 3], lr=True)
    E(bl, 'c_trstate'); E(cmp_imm, 0, 0); E(b_cond, 'load_x', 'eq')
    E(movs_imm, 1, 0); E(str_imm, 1, 0, 0); E(str_imm, 1, 0, 8)
    a.label('load_x')
    E(raw, C.popw([0, 1, 2, 3], lr=True)); E(b_w, prevload)
    a.label('c_trled')
    E(push_list, [0, 1, 4], lr=True); E(bl, prevled); E(bl, 'c_trphoto')
    ret([0, 1, 4])

    a.label('c_trpad')
    E(push_list, [0, 1, 2, 3], lr=True)
    E(bl, 'c_trstate'); E(cmp_imm, 0, 0); E(b_cond, 'pad_x', 'eq')
    E(movs_imm, 1, 0); E(strb_imm, 1, 0, 1); E(strb_imm, 1, 0, 2)
    a.label('pad_x')
    E(raw, C.popw([0, 1, 2, 3], lr=True)); E(b_w, prevpad)

    if softclear:
        a.label('c_trred')
        E(push_list, [4], lr=True)
        imm(4, 0x20003974 + 4 * 0x55); E(ldr_imm, 4, 4, 0)
        imm(0, C.CTRL + 0x88); E(ldr_imm, 0, 0, 0)
        E(movs_imm, 1, 2); E(bl, C.PARAM_GET); E(ldr_imm, 0, 0, 0)
        E(lsls_imm, 0, 0, 21)
        E(mov_reg, 0, 4); E(b_cond, 'red_x', 'pl')
        E(movs_imm, 1, 140)
        E(bl, int(report['tmenu']['labels']['c_tmscl'], 16))
        a.label('red_x'); ret([4])

    # Last RGB overlay: confirmation works with Track + both open and closed.
    a.label('c_trout')
    E(push_list, [0, 1, 2, 4, 5, 6], lr=True)
    E(mov_reg, 5, 1); E(bl, prevout); E(bl, 'c_trstate')
    E(cmp_imm, 0, 0); E(b_cond, 'out_x', 'eq'); E(mov_reg, 4, 0)
    imm(0, C.CTRL + 0xA0); E(ldr_imm, 0, 0, 0); E(lsls_imm, 0, 0, 8)
    E(b_cond, 'out_armed', 'mi')
    E(movs_imm, 0, 0); E(strb_imm, 0, 4, 1); E(strb_imm, 0, 4, 2)
    a.label('out_armed')
    E(ldrb_imm, 6, 4, 1); E(cmp_imm, 6, 0); E(b_cond, 'out_flash', 'eq')
    if softclear: E(bl, 'c_trred')
    else: imm(0, 0xFF0000)
    E(b, 'out_store')
    a.label('out_flash')
    E(ldrb_imm, 6, 4, 3); E(cmp_imm, 6, 0); E(b_cond, 'out_x', 'eq')
    imm(0, C.HAL_TICK); E(ldr_imm, 0, 0, 0); E(ldr_imm, 1, 4, 4)
    E(subs_reg, 0, 0, 1); E(movw, 1, 384); E(cmp_reg, 0, 1)
    E(b_cond, 'out_finish', 'hs')
    E(lsls_imm, 0, 0, 25); E(movw, 0, 0)
    E(b_cond, 'out_store', 'mi')
    if softclear: E(bl, 'c_trred')
    else: imm(0, 0xFF0000)
    E(b, 'out_store')
    a.label('out_finish')
    E(movs_imm, 0, 0); E(strb_imm, 0, 4, 3)
    # Palette colour for the target track, one frame before normal drawing resumes.
    E(mov_reg, 1, 6); E(subs_imm8, 1, 1)
    for t, colour in enumerate(TRK_COLOURS):
        E(cmp_imm, 1, t); E(b_cond, f'out_colour{t}', 'ne')
        imm(0, 0x20003974 + 4 * colour); E(ldr_imm, 0, 0, 0)
        E(b, 'out_store'); a.label(f'out_colour{t}')
    a.label('out_store')
    E(adds_imm8, 6, 31); E(lsls_imm, 6, 6, 2); E(adds_reg, 5, 5, 6)
    E(str_imm, 0, 5, 0)
    a.label('out_x'); ret([0, 1, 2, 4, 5, 6])
    code, labels = a.assemble()
    img += bytes([255]) * (base_addr-rhbuild.BASE-len(img)) + code
    while len(img) % 4: img.append(255)
    rhbuild.patch(img, C.BTN_ENTRY, f'b.w #{prevbtn:#x}', b_w(C.BTN_ENTRY, labels['c_trbtn']))
    rhbuild.patch(img, RELEASE, 'push {r3, r4, r5, lr}|mov r4, r0', b_w(RELEASE, labels['c_trrelease']))
    rhbuild.patch(img, LOAD, f'b.w #{prevload:#x}', b_w(LOAD, labels['c_trload']))
    rhbuild.patch(img, 0x0803D7FE, f'b.w #{prevpad:#x}', b_w(0x0803D7FE, labels['c_trpad']))
    for c in C.LED_CALLS:
        rhbuild.patch(img, c, f'bl #{prevled:#x}', bl(c, labels['c_trled']))
    rhbuild.patch(img, OUT_CALL, f'bl #{prevout:#x}', bl(OUT_CALL, labels['c_trout']))
    report['trackreset'] = dict(viewsync=viewsync, softclear=softclear, slot=hex(slot), size=SIZE, prev_btn=hex(prevbtn), prev_out=hex(prevout),
        labels={k: hex(v) for k, v in labels.items() if k.startswith('c_')})
    return labels, code
