"""Run the real ARM upload of a dsppack build and of its reference build; both DSP cores must get the same bytes.

    python tests/emu_dsppack.py a0257 a0256
"""
import json, random, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / p) for p in ('modules', 'tests', 'remix/tools')]
import rhdsp, rhdsp1  # noqa: F401  (ours first: they read dsppack images)
import dsppack as P, dspzip as Z
from emu_playfix import machine, SENT, STACK
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *

DISPATCH = 0x08031110
MOCKED = (0x08046538, 0x0802b69c, 0x0802366c, 0x08046534, 0x08023416, 0x080312cc, 0x08031338, 0x0803136c, 0x080311da)
RAMDUMP = (ROOT / 'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes()


def read(n):
    d = ROOT / 'firmware' / n
    return (d / f'rhythmplus-{n.upper()}.bin').read_bytes(), json.loads((d / 'manifest.json').read_text())['report']


def call(u, fn, *args, limit=60_000_000):
    sp = STACK + 0xF0000
    for i, a in enumerate(args):
        u.reg_write(UC_ARM_REG_R0 + i, a)
    for r in range(4, 12):
        u.reg_write(UC_ARM_REG_R4 + r - 4, 0x1110 + r)
    u.reg_write(UC_ARM_REG_SP, sp); u.reg_write(UC_ARM_REG_LR, SENT | 1)
    u.emu_start(fn | 1, SENT, count=limit)
    assert u.reg_read(UC_ARM_REG_PC) == SENT, f'{fn:#x}: stopped at {u.reg_read(UC_ARM_REG_PC):#x}'
    assert [u.reg_read(UC_ARM_REG_R4 + r - 4) for r in range(4, 12)] == [0x1110 + r for r in range(4, 12)]
    assert u.reg_read(UC_ARM_REG_SP) == sp


class Rig:
    """an image on the RAM dump: every SPI byte grouped by core select; DMA lands at the next WAIT"""
    def __init__(self, image):
        self.u = u = machine(image, RAMDUMP, mclass=True)
        self.groups, self.pending, self.chunks = [], [], []
        def ret(v=0):
            u.reg_write(UC_ARM_REG_R0, v); u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
        def hook(uc, a, n, d):
            x, y = uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1)
            assert not uc.reg_read(UC_ARM_REG_PRIMASK)
            assert uc.reg_read(UC_ARM_REG_SP) % 8 == 0, hex(a)
            if a == Z.WAIT:
                if self.pending:
                    p, sz, before = self.pending.pop()
                    assert bytes(uc.mem_read(p, sz)) == before, 'DMA source changed before completion'
                    self.groups[-1][1].extend(before)
                ret()
            elif a == Z.SELECT:
                assert not self.pending; self.groups.append([x, bytearray()]); ret()
            elif a == Z.SPI:
                assert not self.pending and 0 < y <= 510 and y % 3 == 0
                self.pending.append((x, y, bytes(uc.mem_read(x, y)))); self.chunks.append(y); ret()
            elif a == Z.END:
                assert not self.pending and self.groups[-1][0] == x; ret()
            else:
                ret()
        for a in (Z.WAIT, Z.SELECT, Z.SPI, Z.END) + MOCKED:
            u.hook_add(UC_HOOK_CODE, hook, None, a, a + 1)

    def upload(self, mode):
        self.groups.clear(); self.chunks.clear()
        call(self.u, DISPATCH, mode, 0, 0, 0)
        return [(c, bytes(b)) for c, b in self.groups]


def preview_only(a, b, mode):
    """a build without pvloop against one with it: only the preview player's words in core 1's block differ, and they are the stock's"""
    import pvloop as PV
    stock = (ROOT / 'remix/stock/circuitrhythm-firmware-5706-STOCK.bin').read_bytes()
    o1 = rhdsp1.BLK1 - rhdsp1.BASE
    room = set(range(PV.A1, PV.E1)) | set(range(PV.A2, PV.E2)) | {PV.CALL_PV, PV.CALL_ENV}
    allowed = {(rhdsp1.where(stock, k) - o1) // 3 for k in room}
    assert [c for c, _ in a] == [c for c, _ in b]
    changed = 0
    for (c, x), (_, y) in zip(a, b):
        if x == y:
            continue
        assert c == 1 and len(x) == len(y) and x[:6] == stock[o1:o1 + 6], 'only core 1 block differs'
        diff = {k // 3 for k in range(0, len(x), 3) if x[k:k + 3] != y[k:k + 3]}
        assert diff <= allowed, sorted(diff - allowed)[:5]
        assert all(x[3 * k:3 * k + 3] == stock[o1 + 3 * k:o1 + 3 * k + 3] for k in diff), 'not the stock words'
        changed += 1
    assert changed or mode, "mode 0 sends the preview player"


def main():
    name, ref = (sys.argv[1:3] + ['a0257', 'a0256'][len(sys.argv[1:3]):])[:2]
    image, rep = read(name); old, _ = read(ref)
    assert P.is_packed(image)
    raw0, raw1 = P.raw_streams(image)
    mine, theirs = Rig(image), Rig(old)
    # Every send is what the stock sender sends for an unpacked block, or one of the two packed programs.
    expect = []
    L = rep['dsppack']['labels']
    def send(uc, a, n, d):
        blk, core = uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1)
        if a == P.SEND:
            o = blk - P.BASE; cnt = int.from_bytes(image[o + 1:o + 3], 'big')
            expect.append((core, bytes(image[o:o + 3 * (cnt + 2)])))
        elif a == int(L['c_hz_core0'], 16):
            expect.append((core, raw0))
        elif blk == P.BLK1:
            expect.append((core, raw1))
    for at in (P.SEND, int(L['c_hz_core0'], 16), int(L['c_hz_core1'], 16)):
        mine.u.hook_add(UC_HOOK_CODE, send, None, at, at + 1)
    ref_raws = P.raw_streams(old) if P.is_packed(old) else None
    same = ref_raws == (raw0, raw1) or (ref_raws is None and 'dspzip' in read(ref)[1] and Z.raw_stream(old) == raw0
                                        and rhdsp1.words(old) == rhdsp1.words(image))
    no_preview = not same and 'pvloop' in read(ref)[1] and 'pvloop' not in rep and 'endfade' not in rep
    for mode in (0, 1, 0):
        expect.clear()
        a, b = mine.upload(mode), theirs.upload(mode)
        assert a == expect, f'mode {mode}: a send is not the block or program it should be'
        assert [c for c, _ in a] == [c for c, _ in b], f'mode {mode}: other cores or order than {ref}'
        if same:
            assert a == b, f'mode {mode}: the DSP gets other bytes than {ref}'
        elif no_preview:
            preview_only(a, b, mode)
    first = a
    sent0 = [g for c, g in a if c == 0]; sent1 = [g for c, g in a if c == 1]
    assert raw0 in sent0 and raw1 in sent1
    print(f'PASS mode 0, 1, 0: every send is its block or its unpacked program ({sum(len(g) for _, g in a)} bytes), cores in the order of {ref}')
    if same:
        print(f'PASS every byte to both cores equals {ref}')
    elif no_preview:
        print(f'PASS every byte to both cores equals {ref} except the preview player, which is the stock one')
    else:
        print(f'NOTE the DSP programs differ from {ref} on purpose; their tests are the DSP suites')
    d = rep['dsppack']
    print(f"PASS core 0 {d['core0']['raw_bytes']} B from {d['core0']['packed_bytes']}, core 1 {d['core1']['raw_bytes']} B "
          f"from {d['core1']['packed_bytes']}; {d['hole_bytes']} B of flash free in {len(d['holes'])} holes")

    # Warm reloads: only the ring (and a range-coded build's ITCM work areas) may change; the rest of ITCM and SRAM stay.
    u = mine.u; ring = int(rep['dspzip']['ring'], 16)
    rc = 'rc' in d
    work = (P.PROBS, P.WINDOW + 0x1000) if rc else (0, 0)
    rng = random.Random(257)
    itcm = rng.randbytes(0x4000); u.mem_write(0, itcm)
    sram = bytearray(u.mem_read(0x20000000, 0x50000))
    block = int(rep['rhstate']['block'], 16)
    for k in range(block + 4, 0x2004f760):
        sram[k - 0x20000000] = rng.randrange(256)
    u.mem_write(0x20000000, bytes(sram))
    for _ in range(3):
        assert mine.upload(0) == first
        after = bytes(u.mem_read(0x20000000, 0x50000)); lo = ring - 0x20000000
        now = bytes(u.mem_read(0, 0x4000))
        assert now[:work[0]] == itcm[:work[0]] and now[work[1]:] == itcm[work[1]:]
        assert after[:lo] == sram[:lo] and after[lo + P.WIN:] == sram[lo + P.WIN:]
    assert P.WIN in mine.chunks
    areas = f', and ITCM {work[0]:#x}-{work[1]:#x} (the decoder work areas)' if rc else ''
    print(f'PASS three warm reloads: only the 240-byte ring changes{areas}; ITCM and all other SRAM stay')

    # The decoder on edge cases: overlapping matches, the ring wrap, long runs, random literals, short last chunks.
    L = d['labels']; dirat = P.BLK1
    saved = bytes(u.mem_read(dirat, 0x10000))
    pats = [bytes(3), bytes(240), bytes(243), b'abc' * 265, bytes(range(240)) * 6, rng.randbytes(1500), b'a' * 1599,
            (b'aaaabbbbccc' + rng.randbytes(19)) * 48, bytes(range(256)) * 3]
    if rc:
        import dsprc
        pats += [rng.randbytes(5001), (b"xyz" + rng.randbytes(3)) * 1400, bytes(range(256)) * 21]   # past the 4 KB window
    for pay in pats:
        at = 0x08001000
        if rc:
            s = dsprc._pack2(pay) + P.RC_PAD
            assert dsprc.unpack_stream2(s, len(pay)) == pay
            u.mem_write(at, s)
            u.mem_write(dirat, struct.pack('<4s6I', P.MAGIC_RC, at, 0, at, len(pay), 0, 0))
        else:
            llb, db, (t,) = P.pack([pay]); tab, doff = P.tables(llb, db); s = P.bitstream(t, llb, db)
            assert P.unpack(s, tab, doff, len(pay)) == pay
            u.mem_write(at, tab + s)
            u.mem_write(dirat, struct.pack('<4s6I', P.MAGIC, at, doff, at + len(tab), len(pay), 0, 0))
        mine.groups.clear(); call(u, int(L['c_hz_core0'], 16), 0, 0)
        assert len(mine.groups) == 1 and bytes(mine.groups[0][1]) == pay, len(pay)
    u.mem_write(dirat, saved)
    print('PASS decoder edge cases: overlap, 240-byte wrap, long runs, random literals, partial last chunks' + (', past the 4 KB window' if rc else ''))

    # No ring, no sending: core 1 stops before it selects the core.
    rst = int(rep['rhstate']['labels']['c_rst'], 16)
    h = u.hook_add(UC_HOOK_CODE, lambda uc, a, n, _: (uc.reg_write(UC_ARM_REG_R0, 0),
                   uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))), None, rst, rst + 1)
    mine.groups.clear()
    try:
        call(u, int(L['c_hz_core1'], 16), P.BLK1, 1, limit=20000)
        raise AssertionError('core 1 returned without its ring')
    except AssertionError as e:
        assert 'stopped at' in str(e), e
    assert not mine.groups
    u.hook_del(h)
    print('PASS without its RAM the decoder waits and never sends packed bytes as program words')
    print('LIMIT boot time and SPI timing on the unit are not emulated')
    print('ALL PASS')


if __name__ == '__main__':
    main()
