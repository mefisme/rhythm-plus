"""A0039 protected resets: real built ARM code, stock default comparison and scope guards."""
import sys
import struct
from pathlib import Path
import emu_tmenu as E
PV = E.MAN['report']['pageclear'].get('page_values', [[0, 1, 2, 3, 11, 7], [10, 5, 9, 4, 8]])
FILT = E.MAN['report']['pageclear'].get('filt', False)
FSP = (5, 9) if FILT else ()                       # (filt) Stock+'s filter type and pitch follow: on the filter page
FXV, ALLV = set(PV[1]), set(PV[0]) | set(PV[1]) | set(FSP)
VOL = E.MAN['report']['pageclear'].get('vol', False)
PX = E.MAN['report']['pageclear'].get('px', False)   # the pitch page and Clear All reset fshape's random pitch (values 26, 27)
PXN = ('random pitch, glide and LFO fade-in' if E.MAN['report'].get('fshape', {}).get('fade') else
       'random pitch and glide' if E.MAN['report'].get('fshape', {}).get('glide') else 'random pitch')


def main():
    if E.MAN['report']['pageclear'].get('scanfx'):
        E.check('scanfx: Clear + pad 28 resets the ring and the scan (4, 8, 11, 7), pad 27 not the scan', PV == [[0, 1, 2, 3, 10, 6], [4, 8, 11, 7]], PV)
    stock, fw, ram = map(lambda p: Path(p).read_bytes(), sys.argv[1:4])
    uc, ref = E.setup(fw, ram), E.setup(stock, ram, built=False)
    s = E.sel(uc)
    def values(u, t):
        result = []
        for i in range(25):
            E.call(u, 0x08046410, 0x10 + t, i)
            result.append(u.reg_read(E.UC_ARM_REG_R0) & 255)
        return result
    def setv(u, t, i, v): E.call(u, 0x08031A38, 0x20010E10, 0x10 + t, i, v)
    def spvals(): return [E.spval(uc, s, i) for i in range(12)]
    def seedsp():
        for i in range(12): E.call(uc, E.SPL['c_spput'], s, i, 2048)
    def push(p): E.pad(uc, p); E.unpad(uc, p)
    FSL = {k: int(v, 16) for k, v in E.MAN['report']['fshape']['labels'].items()} if FILT else {}
    FDEF = E.MAN['report']['fshape']['defs'] if FILT else []
    def flvals(): return [E.call(uc, FSL['c_fsval'], s, 12 + k) or uc.reg_read(E.UC_ARM_REG_R0) for k in range(6)]
    def seedfl():
        for k in range(6): E.call(uc, FSL['c_fsput'], s, 12 + k, 3000)
    VDEF = E.MAN['report']['fshape']['vdefs'] if VOL else []
    def vlvals(): return [E.call(uc, FSL['c_fsval'], s, 18 + k) or uc.reg_read(E.UC_ARM_REG_R0) for k in range(8)]
    def seedvl():
        for k in range(8): E.call(uc, FSL['c_fsput'], s, 18 + k, 3000)
    PXDEF = E.MAN['report']['fshape']['pxdefs'] if PX else []
    if PX and E.MAN['report']['fshape'].get('fade'):
        PXDEF = PXDEF + E.MAN['report']['fshape']['fidefs']
    def pxvals(): return [E.call(uc, FSL['c_fsval'], s, 26 + k) or uc.reg_read(E.UC_ARM_REG_R0) for k in range(len(PXDEF))]
    def seedpx():
        for k in range(len(PXDEF)): E.call(uc, FSL['c_fsput'], s, 26 + k, 3000)
    def clear(on):
        a = E.C.CTRL + 0xA0
        w = E.u32(uc, a)
        uc.mem_write(a, struct.pack('<I', w | (1 << 23) if on else w & ~(1 << 23)))
    for u in (uc, ref):
        for i in range(6, 16): setv(u, s, i, 23)
    # Independent stock reference: sustained right turn with Clear, all eight knobs.
    sub = []
    hook = ref.hook_add(E.UC_HOOK_CODE, lambda u, a, n, d: sub.append(u.reg_read(E.UC_ARM_REG_R0)), None, 0x08058160, 0x08058161)
    E.knob(ref, 0, 1)
    ref.hook_del(hook)
    E.call(ref, E.C.PARAM_GET, E.u32(ref, sub[0] + 0x20), 0)
    ref.mem_write(ref.reg_read(E.UC_ARM_REG_R0), b'\x01')
    for k in range(8):
        for _ in range(48): E.knob(ref, k, 1)
    expected = values(ref, s)[6:16]
    E.tap(uc, s); E.led(uc, E.LB['c_tmled']); E.tick(uc, 1000)
    seedsp()
    rec = E.u32(uc, E.T.AUTO + E.T.AUTO_RECS + 4 * s)
    pats = E.u32(uc, rec + 4)
    E.call(uc, E.C.PARAM_GET, E.u32(uc, rec + 0x28), 0)
    pat = uc.mem_read(uc.reg_read(E.UC_ARM_REG_R0), 1)[0]
    lanes = pats + pat * E.T.PAT_SIZE + E.T.LANES
    uc.mem_write(lanes, bytes([31]) * (8 * E.T.LANE_SIZE))
    uc.mem_write(lanes + 8 * E.T.LANE_SIZE, bytes([41]) * (4 * E.T.LANE_SIZE))
    other = pats + ((pat + 1) % 8) * E.T.PAT_SIZE
    other_before = bytes(uc.mem_read(other, E.T.PAT_SIZE))
    othertrack = values(uc, (s + 1) % 8)
    before = values(uc, s)
    clear(False); push(31)
    E.check('pad 32 without Clear: values and automation unchanged', values(uc, s) == before and uc.mem_read(lanes, 1)[0] == 31)
    E.led(uc, E.LB['c_tmled'])
    E.check('pad 32 hidden without Clear', E.out(uc)[31] == 0)
    clear(True)
    reset_rgb = E.T.RED
    if E.MAN['report']['tmenu'].get('resetcue'):
        reset_rgb = E.scl(E.u32(uc, E.T.COLOURS + 4 * 0x54), E.dim_mul(uc) - 1)
    E.led(uc, E.LB['c_tmled'])
    lights = []
    for _ in range(4):
        lights.append(E.out(uc)[31]); E.tick(uc, 64)
    E.check('pad 32 steady with Clear held' if E.MAN['report']['tmenu'].get('steadyreset') else 'pad 32 flashes red only while Clear held', set(lights) == ({reset_rgb} if E.MAN['report']['tmenu'].get('steadyreset') else {0, E.T.RED}), lights)
    push(25)
    got = values(uc, s)
    if E.MAN['report']['tmenu'].get('resetcue'):
        E.led(uc, E.LB['c_tmled']); f = E.out(uc)
        want = E.page_pads_want(uc, 0, f[24])
        want[E.T.PAD_PAGE0 - 24] = E.clear_red(uc)
        want[-1] = reset_rgb
        E.check('per-page clear flashes only its own page', list(f[24:32]) == want)
    E.check('page 1 defaults match stock Clear + right (including fine values)', got[6:16] == expected, (got[6:16], expected))
    E.check('page 1 clears all eight sound lanes of current pattern', bytes(uc.mem_read(lanes, 8 * E.T.LANE_SIZE)) == bytes([255]) * (8 * E.T.LANE_SIZE))
    E.check('remaining four automation lanes unchanged', bytes(uc.mem_read(lanes + 8 * E.T.LANE_SIZE, 4 * E.T.LANE_SIZE)) == bytes([41]) * (4 * E.T.LANE_SIZE))
    E.check('page 1 leaves other parameters and Stock+ alone', got[:6] + got[16:] == before[:6] + before[16:] and spvals() == [2048] * 12)
    E.check('other pattern and track unchanged', bytes(uc.mem_read(other, E.T.PAT_SIZE)) == other_before and values(uc, (s + 1) % 8) == othertrack)
    shown = E.b8(uc, E.T.O_PAGE)
    push(E.pp(1))
    E.check(f'the Stock+ page resets only its {len(PV[0])} values; page stays selected', spvals() == [E.DEFS[i] if i in PV[0] else 2048 for i in range(12)] and E.b8(uc, E.T.O_PAGE) == shown, spvals())
    if PX:
        seedsp(); seedpx()
        push(E.pp(1))
        E.check(f'the pitch page (pad {E.pp(1) + 1}) resets the {PXN} too', pxvals() == PXDEF, pxvals())
        seedpx()
    seedsp()
    stock_before = values(uc, s)
    push(E.pp(2))
    E.check('FX page resets only its values', spvals() == [E.DEFS[i] if i in FXV else 2048 for i in range(12)], spvals())
    E.check('FX reset keeps stock knobs and sample parameters', values(uc, s) == stock_before)
    if FILT:
        seedsp(); seedfl()
        check0 = flvals() == [3000] * 6
        push(E.pp(3))
        E.check(f"the filter page (pad {E.pp(3) + 1}) resets its 6 values and Stock+'s filter type / pitch follow only", check0 and flvals() == FDEF
                and spvals() == [E.DEFS[i] if i in FSP else 2048 for i in range(12)] and values(uc, s) == stock_before, (flvals(), spvals()))
        seedfl()
    if VOL:
        seedsp(); seedvl()
        check0 = vlvals() == [3000] * 8
        push(E.pp(4))
        E.check(f"the movement page (pad {E.pp(4) + 1}) resets its 8 values only", check0 and vlvals() == VDEF and flvals() == [3000] * 6
                and spvals() == [2048] * 12 and values(uc, s) == stock_before, (vlvals(), flvals()))
        seedvl()
    if None in E.PADMAP:
        seedsp(); seedfl(); seedvl()
        st0 = values(uc, s)
        push(E.T.PAD_PAGE0 + E.PADMAP.index(None))
        E.check(f"Clear + pad {E.T.PAD_PAGE0 + E.PADMAP.index(None) + 1} (no page): nothing reset", spvals() == [2048] * 12 and flvals() == [3000] * 6
                and vlvals() == [3000] * 8 and values(uc, s) == st0, (spvals(), flvals(), vlvals()))
        seedfl(); seedvl()
    if PX:
        E.check(f'the FX, filter, mix and empty pads keep the {PXN}', pxvals() == [3000] * len(PXDEF), pxvals())
    seedsp()
    uc.mem_write(lanes, bytes([37]) * (8 * E.T.LANE_SIZE))
    E.pad(uc, 4)  # A held step must not reduce reset scope to that step.
    E.call(uc, E.C.PARAM_GET, E.u32(uc, rec + 0x40), 0)
    heldflag = uc.reg_read(E.UC_ARM_REG_R0)
    uc.mem_write(heldflag, b'\x01')
    E.call(uc, E.LB['c_tmview'])
    push(31)
    E.check('all-pages reset restores the 11 Stock+ controls to defaults', [v for i, v in enumerate(spvals()) if i != 6] == [(v if i in ALLV else 2048) for i, v in enumerate(E.DEFS) if i != 6], spvals())
    if FILT:
        E.check("all-pages reset: the filter page's values too", flvals() == FDEF, flvals())
    if VOL:
        E.check("all-pages reset: the movement page's values too", vlvals() == VDEF, vlvals())
    if PX:
        E.check(f"all-pages reset: the {PXN} too", pxvals() == PXDEF, pxvals())
    E.check('all-pages reset clears whole current pattern even with step held', bytes(uc.mem_read(lanes, 8 * E.T.LANE_SIZE)) == bytes([255]) * (8 * E.T.LANE_SIZE) and uc.mem_read(heldflag, 1)[0] == 1)
    E.check('reset leaves menu open and selected page unchanged', E.b8(uc, E.T.O_OPEN) == 1 and E.b8(uc, E.T.O_PAGE) == shown)
    if E.MAN['report']['tmenu'].get('steadyreset'):
        start = E.u32(uc, E.C.HAL_TICK)
        feedback = []
        for dt in range(0, 384, 64):
            uc.mem_write(E.C.HAL_TICK, struct.pack('<I', start + dt))
            E.led(uc, E.LB['c_tmled']); frame = E.out(uc); feedback.append(frame[31])
            if E.MAN['report']['tmenu'].get('resetcue'):
                want = E.clear_red(uc) if dt % 128 == 0 else 0
                E.check(f'Clear All: every page flashes together at {dt} ms', list(frame[E.T.PAD_PAGE0:E.T.PAD_PAGE0 + E.NP]) == [0 if i is None else want for i in E.PADMAP])
        E.check('pad 32 flashes three times only after press', feedback == [E.clear_red(uc), 0] * 3, feedback)
        uc.mem_write(E.C.HAL_TICK, struct.pack('<I', start + 384))
        E.led(uc, E.LB['c_tmled'])
        E.check('pad 32 returns steady while Clear remains held', E.out(uc)[31] == reset_rgb)
        if E.MAN['report']['tmenu'].get('resetcue'):
            f = E.out(uc)
            E.check('Clear All: page colours return after feedback', list(f[24:32]) == E.page_pads_want(uc, shown, f[24])[:-1] + [reset_rgb])
    clear(False); E.tick(uc, 1000); E.led(uc, E.LB['c_tmled'])
    E.check('pad 32 hidden again after Clear release and feedback', E.out(uc)[31] == 0)
    print('ALL PASS' if not E.FAILS else f'{len(E.FAILS)} FAILED')
    if E.FAILS: raise SystemExit(1)


if __name__ == '__main__': main()
