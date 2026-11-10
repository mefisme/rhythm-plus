"""Protected Track + page reset (MIT; Rhythm Plus 5706).

Clear + pads 26/27/28 resets stock / movers / FX values of the selected track.
Stock reset also deletes the eight sound lanes of the current pattern, even with
a step held. Clear + pad 32 does all three. No sample, mixer or FX-send reset.
The remaining colour-test pages alias the stock editor and reset those same values.
gran: Clear + pad 29 resets the granular's 12 values (grain_rp); pad 32 too when the track is the granular one.
filt: Clear + pad 29 resets the filter page (fshape's 6 values, Stock+'s filter type and pitch follow); pad 28 the ring only; pad 32 all.
vol: Clear + pad 30 resets the movement page (fshape's values 18..25); pad 32 too.
scanfx: the scan's depth and speed (11, 7) reset with pad 28, not pad 27.
pageorder: the page on each pad as tmenu's PADMAP_ORDER (pad 30 none: Clear + pad 30 nothing).
px: the pitch page and Clear All also reset fshape's random pitch (values 26, 27); fade: and the LFO's fade-in (value 28).
"""
import struct
import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
from thumb import (Asm, movw, movt, push_list, pop_list, mov_reg, movs_imm, cmp_reg, subs_imm8,
                   cmp_imm, b_cond, b, bl, ldr_imm, ldrb_imm, str_imm,
                   strb_imm, lsls_imm, adds_reg, adds_imm8, raw, h)
import countin as C
import rhstate
import stockplus_rp

FIRST, RESET = 25, 31
OFF = rhstate.OFF.get('pageclear', (0, 0))[0]
FLASH_MS, FLASH_SHIFT = 384, 6
PAGE_VALUES = ((0, 1, 2, 3, 11, 7), (10, 5, 9, 4, 8))
GRAN_PAGE = 3                                  # (gran) pad 29: the granular page
BITCRUSH = 10                                  # Stock+'s value 10 (nocrush: not on the FX page)
SHAPES = (10, 6)                               # (shapes) the Stock+ page's envelope and LFO shapes (pshape)
FILT_PAGE, FILT_SP, FX_RING = 3, (5, 9), (4, 8)  # (filt) pad 29; its Stock+ values (type, follow); pad 28's (the ring)
VOL_PAGE = 4                                    # (vol) pad 30: the movement page
PADMAP_ORDER = (0, FILT_PAGE, VOL_PAGE, 1, None, 2)  # (pageorder) the page on pads 26-31; None = no page


def install(img, report, base_addr, viewsync=False, nocrush=False, gran=False, shapes=False, filt=False, vol=False, scanfx=False, pageorder=False, px=False, fade=False, soundonly=False):
    import rhbuild
    assert rhstate.OFF['pageclear'][1] == 8
    default_table = struct.unpack_from('<I', img, 0x0805884C - rhbuild.BASE)[0]
    assert rhbuild.BASE <= default_table < rhbuild.BASE + len(img)
    defaults = stockplus_rp.defaults(report['stockplus'].get('lfodef') or False)
    lab = lambda k: int(report['stockplus']['labels'][k], 16)
    a = Asm(base_addr)
    E = a.emit
    def imm(r, v):
        E(movw, r, v & 65535); E(movt, r, v >> 16)

    if viewsync:
        # r0 track, r1 engine parameter index, r2 value: stock control stores.
        # Sound/fine IDs and mixer IDs are the stock's generic-setter mapping.
        a.label('c_pcsync')
        E(push_list, [4, 5], lr=True)
        E(mov_reg, 4, 0)
        E(cmp_imm, 1, 6); E(b_cond, 'sync_done', 'lo')
        E(cmp_imm, 1, 16); E(b_cond, 'sync_mixer', 'hs')
        E(cmp_imm, 1, 14); E(b_cond, 'sync_sound', 'hs')
        from thumb import subs_imm8
        E(subs_imm8, 1, 6)
        a.label('sync_sound')
        E(lsls_imm, 0, 4, 4); E(adds_reg, 1, 1, 0)
        E(b, 'sync_write')
        a.label('sync_mixer')
        for index, generic in ((16, 0x91), (17, 0x99), (18, 0x80), (19, 0x88)):
            E(cmp_imm, 1, index); E(b_cond, f'sync_next{index}', 'ne')
            E(movs_imm, 1, generic); E(adds_reg, 1, 1, 4)
            E(b, 'sync_write'); a.label(f'sync_next{index}')
        E(b, 'sync_done')
        a.label('sync_write')
        imm(0, 0x20011998); E(bl, 0x08038A08)
        a.label('sync_done'); E(pop_list, [4, 5], pc=True)

    # r0 track. Stock's default table, including K2/K3 fine values.
    a.label('c_pcstock')
    E(push_list, [4, 5, 6, 7], lr=True)
    E(mov_reg, 4, 0)
    E(movs_imm, 5, 6)
    a.label('ps_value')
    imm(0, 0x20010E10)
    E(mov_reg, 1, 4); E(adds_imm8, 1, 0x10)
    E(mov_reg, 2, 5)
    imm(3, default_table); E(adds_reg, 3, 3, 5); E(ldrb_imm, 3, 3, 0)
    if viewsync:
        E(mov_reg, 6, 3)
    E(bl, 0x08031A38)
    if viewsync:
        E(mov_reg, 0, 4); E(mov_reg, 1, 5); E(mov_reg, 2, 6); E(bl, 'c_pcsync')
    E(adds_imm8, 5, 1); E(cmp_imm, 5, 16); E(b_cond, 'ps_value', 'lo')
    if viewsync:
        # Stock reset also resets pitch's cached value and K4's half-step accumulator
        # (0x08058160). The generic setter alone does not reset that accumulator.
        imm(0, 0x20048B9C + 0x1C4)
        E(lsls_imm, 1, 4, 2); E(adds_reg, 0, 0, 1); E(ldr_imm, 0, 0, 0)
        E(mov_reg, 6, 0); E(adds_imm8, 6, 0x4E)
        imm(1, default_table + 6); E(ldrb_imm, 1, 1, 0); E(strb_imm, 1, 6, 0)
        E(ldr_imm, 0, 0, 0x64); E(movs_imm, 1, 0); E(strb_imm, 1, 0, 0)
    imm(0, 0x2003D2FC + 0x84)
    E(lsls_imm, 1, 4, 2); E(adds_reg, 0, 0, 1); E(ldr_imm, 4, 0, 0)
    # Force whole-lane clear rather than held-step clear, then restore the store.
    E(ldr_imm, 0, 4, 0x40); E(movs_imm, 1, 0); E(bl, C.PARAM_GET)
    E(mov_reg, 6, 0); E(ldrb_imm, 7, 6, 0)
    E(movs_imm, 0, 0); E(strb_imm, 0, 6, 0)
    E(movs_imm, 5, 0)
    a.label('ps_lane')
    E(mov_reg, 0, 4); E(mov_reg, 1, 5); E(bl, 0x08047CA8)
    E(adds_imm8, 5, 1); E(cmp_imm, 5, 8); E(b_cond, 'ps_lane', 'lo')
    E(strb_imm, 7, 6, 0)
    E(pop_list, [4, 5, 6, 7], pc=True)

    # r0 track, r1 page (0 stock, 1 movers, 2 FX, 6 all).
    a.label('c_pcreset')
    E(push_list, [4, 5, 6, 7], lr=True)
    E(mov_reg, 4, 0); E(mov_reg, 5, 1)
    if gran:
        gl = lambda k: int(report['grain']['labels'][k], 16)                 # noqa: E731
        E(cmp_imm, 5, GRAN_PAGE); E(b_cond, 'pc_ng', 'ne')
        E(bl, gl('c_grreset'))                                               # the granular page: its 12 defaults
        E(pop_list, [4, 5, 6, 7], pc=True)
        a.label('pc_ng')
    if filt:
        fl = lambda k: int(report['fshape']['labels'][k], 16)               # noqa: E731
        E(cmp_imm, 5, FILT_PAGE); E(b_cond, 'pc_nf', 'ne')
        E(bl, 'pc_filt')
        E(pop_list, [4, 5, 6, 7], pc=True)
        a.label('pc_filt')                                                   # r4 = the track: the filter page's defaults
        E(push_list, [], lr=True)
        E(mov_reg, 0, 4); E(bl, fl('c_flreset'))
        for index in FILT_SP:
            E(mov_reg, 0, 4); E(movs_imm, 1, index); E(movw, 2, defaults[index]); E(bl, lab('c_spput'))
        E(mov_reg, 0, 4); E(bl, lab('c_spdirty'))
        E(pop_list, [], pc=True)
        a.label('pc_nf')
    fl = lambda k: int(report['fshape']['labels'][k], 16)
    assert not px or ((vol or soundonly) and report['fshape'].get('px'))
    assert not fade or (px and report['fshape'].get('fade'))
    if vol:
        assert filt and report['fshape'].get('vol')
        E(cmp_imm, 5, VOL_PAGE); E(b_cond, 'pc_nv', 'ne')
        E(mov_reg, 0, 4); E(bl, fl('c_vlreset'))
        E(pop_list, [4, 5, 6, 7], pc=True)
        a.label('pc_nv')
    E(cmp_imm, 5, 0); E(b_cond, 'pc_stock', 'eq')
    E(cmp_imm, 5, 3); E(b_cond, 'pc_stock', 'hs')
    E(b, 'pc_sp')
    a.label('pc_stock')
    E(mov_reg, 0, 4); E(bl, 'c_pcstock')
    a.label('pc_sp')
    page_values = (PAGE_VALUES[0], tuple(i for i in PAGE_VALUES[1] if i != BITCRUSH)) if nocrush else PAGE_VALUES
    if shapes:
        assert nocrush
        page_values = (page_values[0] + SHAPES, page_values[1])
    if filt:
        assert shapes and 'fshape' in report
        page_values = (page_values[0], FX_RING)
    if scanfx:
        assert filt or soundonly
        if soundonly:
            page_values = (tuple(i for i in page_values[0] if i not in FILT_SP), FX_RING)
        scan = (11, 7)
        page_values = (tuple(i for i in page_values[0] if i not in scan), page_values[1] + scan)
    for page, indices in enumerate(page_values, 1):
        E(cmp_imm, 5, page); E(b_cond, f'pc_do{page}', 'eq')
        E(cmp_imm, 5, 6); E(b_cond, f'pc_next{page}', 'ne')
        a.label(f'pc_do{page}')
        for index in indices:
            E(mov_reg, 0, 4); E(movs_imm, 1, index); E(movw, 2, defaults[index]); E(bl, lab('c_spput'))
        if px and page == 1:
            E(mov_reg, 0, 4); E(bl, fl('c_pxreset'))
            if fade:
                E(mov_reg, 0, 4); E(bl, fl('c_fireset'))
        E(mov_reg, 0, 4); E(bl, lab('c_spdirty'))
        a.label(f'pc_next{page}')
    if filt:
        E(cmp_imm, 5, 6); E(b_cond, 'pc_fx', 'ne')
        E(bl, 'pc_filt')
        if vol:
            E(mov_reg, 0, 4); E(bl, fl('c_vlreset'))
        a.label('pc_fx')
    if gran:
        E(cmp_imm, 5, 6); E(b_cond, 'pc_x', 'ne')
        E(bl, gl('c_grtrk')); E(subs_imm8, 0, 1)
        E(cmp_reg, 0, 4); E(b_cond, 'pc_x', 'ne')
        E(bl, gl('c_grreset'))                                               # all pages of the granular track: its values too
        a.label('pc_x')
    E(pop_list, [4, 5, 6, 7], pc=True)

    # r0 pad index, r1 selected track. Returns 1 if Clear consumes a page press.
    a.label('c_pcpress')
    E(push_list, [4, 5], lr=True)
    E(mov_reg, 4, 0); E(mov_reg, 5, 1)
    imm(0, C.CTRL + 0xA0); E(ldr_imm, 0, 0, 0)
    E(lsls_imm, 0, 0, 8); E(b_cond, 'pp_no', 'pl')
    E(cmp_imm, 4, FIRST); E(b_cond, 'pp_no', 'lo')
    E(cmp_imm, 4, RESET); E(b_cond, 'pp_no', 'hi')
    E(mov_reg, 0, 5); E(mov_reg, 1, 4)
    # page index = pad - FIRST (all reset is page 6).
    from thumb import subs_imm8
    E(subs_imm8, 1, FIRST)
    if pageorder:
        assert (filt and vol or soundonly) and scanfx
        for j, pg in enumerate((0, None, None, 1, None, 2) if soundonly else PADMAP_ORDER):
            if pg == j:
                continue
            E(cmp_imm, 1, j); E(b_cond, f'pp_pm{j}', 'ne')
            if pg is None:
                E(b, 'pp_no')
            else:
                E(movs_imm, 1, pg); E(b, 'pp_pmx')
            a.label(f'pp_pm{j}')
        a.label('pp_pmx')
    E(bl, 'c_pcreset')
    imm(0, rhstate.ST + OFF)
    imm(1, C.HAL_TICK); E(ldr_imm, 1, 1, 0); E(str_imm, 1, 0, 0)
    E(adds_imm8, 4, 1); E(strb_imm, 4, 0, 4)
    E(movs_imm, 0, 1); E(pop_list, [4, 5], pc=True)
    a.label('pp_no')
    E(movs_imm, 0, 0); E(pop_list, [4, 5], pc=True)
    code, labels = a.assemble()
    img += bytes([255]) * (base_addr - rhbuild.BASE - len(img)) + code
    while len(img) % 4: img.append(255)
    report['pageclear'] = dict(viewsync=viewsync, gran=gran, shapes=shapes, filt=filt, vol=vol, scanfx=scanfx, padmap=[0,None,None,1,None,2] if soundonly else list(PADMAP_ORDER) if pageorder else None, px=px, fade=fade, page_values=[list(v) for v in page_values], slot=hex(rhstate.ST + OFF), default_table=hex(default_table),
        labels={k: hex(v) for k, v in labels.items() if k.startswith('c_')})
    return labels, code
