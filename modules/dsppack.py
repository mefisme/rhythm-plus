"""Both DSP programs packed with LZ + Huffman (tables in flash), or with RH_DSP_RC=1 range-coded (dsprc.py; its probabilities and
4 KB window in the ITCM's free 0x1500-0x3ADF while a block is sent), into the flash their stock blocks used.

Runs last in a build, when no step changes DSP words any more. The decoder keeps dspzip's 240-byte ring, which is
also the SPI staging buffer, so it needs no more RAM. Core 0's mode 0 stream (dspzip's) and core 1's mode 0 block
are sent from the packed copies; every other block uses the stock sender.
"""
import hashlib, heapq, os, struct, zlib
from pathlib import Path

BASE = 0x08010000
TABLE = 0x08031658                          # the stock's upload table: core 0 mode 0, core 0 mode 1, core 1 mode 0, core 1 mode 1
BLK1 = 0x080101F0                           # core 1's mode 0 block
SEND = 0x080310B0                           # the stock sender (block, core)
WIN = 240                                   # the ring: 80 words, one SPI chunk
MINL, LMAX = 3, 34                          # match lengths; symbols 256.. are lengths MINL..LMAX
NLL, ND = 256 + LMAX - MINL + 1, WIN        # literal/length and offset alphabets
MAXBITS = 15
MAGIC = b'HZD1'                             # the directory at BLK1
MAGIC_RC = b'RCD1'                          # the same directory for range-coded streams (no tables)
PROBS, WINDOW = 0x1500, 0x2400              # ITCM: 1,738 halfword probabilities, the last 4 KB sent; the guard at 0x3AE0 above
RC_PAD = b'\xff' * 4                        # the decoder reads up to 4 bytes past a stream
ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- the packer
def _matches(raw):
    """best[i] = [(length, offset)] at i: the longest match for each offset tried, offsets up to WIN"""
    n = len(raw); heads = {}; out = [None] * n
    for i in range(n):
        found = []
        chain = heads.get(raw[i:i + MINL]) if i + MINL <= n else None
        if chain:
            best = MINL - 1
            for j in reversed(chain):
                if i - j > WIN:
                    break
                ln = 0
                while ln < LMAX and i + ln < n and raw[j + ln] == raw[i + ln]:
                    ln += 1
                if ln > best:
                    best = ln; found.append((ln, i - j))
                    if ln == LMAX:
                        break
        out[i] = found
        heads.setdefault(raw[i:i + MINL], []).append(i)
    return out


def _lengths(counts, limit=MAXBITS):
    """Huffman code lengths for counts (0 = unused), no code longer than limit"""
    c = [x for x in counts]
    while True:
        live = [(x, k) for k, x in enumerate(c) if x]
        bits = [0] * len(c)
        if len(live) == 1:
            bits[live[0][1]] = 1; return bits
        heap = [(x, k, (k,)) for x, k in live]; heapq.heapify(heap); tie = len(c)
        while len(heap) > 1:
            a = heapq.heappop(heap); b = heapq.heappop(heap)
            for s in a[2] + b[2]:
                bits[s] += 1
            heapq.heappush(heap, (a[0] + b[0], tie, a[2] + b[2])); tie += 1
        if max(bits) <= limit:
            return bits
        c = [(x + 1) // 2 if x else 0 for x in c]


def _codes(bits):
    """canonical codes: shorter first, then by symbol"""
    code, codes = 0, [None] * len(bits)
    for ln in range(1, MAXBITS + 1):
        for s, b in enumerate(bits):
            if b == ln:
                codes[s] = (code, ln); code += 1
        code <<= 1
    return codes


def _parse(raw, cands, llbits, dbits):
    """the cheapest tokens for these code lengths: [(literal,)] or [(length, offset)]"""
    n = len(raw); INF = 1 << 60
    cost = [INF] * (n + 1); cost[n] = 0; pick = [None] * n
    lc = lambda s: llbits[s] or 20
    dc = lambda o: dbits[o - 1] or 20
    for i in range(n - 1, -1, -1):
        c, p = lc(raw[i]) + cost[i + 1], None
        for ln, off in cands[i]:
            for m in range(MINL, ln + 1):
                mc = lc(256 + m - MINL) + dc(off) + cost[i + m]
                if mc < c:
                    c, p = mc, (m, off)
        cost[i], pick[i] = c, p
    toks, i = [], 0
    while i < n:
        if pick[i]:
            toks.append(pick[i]); i += pick[i][0]
        else:
            toks.append((raw[i],)); i += 1
    return toks


def _count(streams):
    ll, d = [0] * NLL, [0] * ND
    for toks in streams:
        for t in toks:
            if len(t) == 1:
                ll[t[0]] += 1
            else:
                ll[256 + t[0] - MINL] += 1; d[t[1] - 1] += 1
    return ll, d


def pack(raws, rounds=3):
    """-> (llbits, dbits, [token lists]) with one table pair shared by all streams"""
    cands = [_matches(r) for r in raws]
    llbits = [9] * 256 + [12] * (NLL - 256); dbits = [8] * ND
    for _ in range(rounds):
        toks = [_parse(r, c, llbits, dbits) for r, c in zip(raws, cands)]
        ll, d = _count(toks)
        llbits, dbits = _lengths(ll), _lengths(d)
    return llbits, dbits, toks


def _table(bits, wide):
    count = [0] * (MAXBITS + 1)
    for b in bits:
        if b:
            count[b] += 1
    syms = [s for ln in range(1, MAXBITS + 1) for s, b in enumerate(bits) if b == ln]
    return struct.pack('<16H', *count) + (struct.pack(f'<{len(syms)}H', *syms) if wide else bytes(syms))


def tables(llbits, dbits):
    """flash tables: ll counts[16] (u16), ll symbols (u16), d counts[16] (u16), d symbols (u8); -> (bytes, d offset)"""
    a = _table(llbits, True)
    return a + _table(dbits, False), len(a)


def bitstream(toks, llbits, dbits):
    llc, dc = _codes(llbits), _codes(dbits)
    out, acc, nb = bytearray(), 0, 0
    def put(code, ln):
        nonlocal acc, nb
        for k in range(ln - 1, -1, -1):           # a code's top bit first; bytes fill from bit 0
            acc |= ((code >> k) & 1) << nb; nb += 1
            if nb == 8:
                out.append(acc); acc, nb = 0, 0
    for t in toks:
        if len(t) == 1:
            put(*llc[t[0]])
        else:
            put(*llc[256 + t[0] - MINL]); put(*dc[t[1] - 1])
    if nb:
        out.append(acc)
    return bytes(out)


DIR_LEN = 28                                # magic, tables, d offset, core 0 bits / bytes, core 1 bits / bytes


def is_packed(img):
    return bytes(img[BLK1 - BASE:BLK1 - BASE + 4]) in (MAGIC, MAGIC_RC)


def raw_streams(img):
    """(core 0's mode 0 stream, core 1's mode 0 block) as sent, from a packed image"""
    magic, tab, doff, b0, n0, b1, n1 = struct.unpack_from('<4s6I', img, BLK1 - BASE)
    if magic == MAGIC_RC:
        import dsprc
        return (dsprc.unpack_stream2(bytes(img[b0 - BASE:b1 - BASE]), n0),
                dsprc.unpack_stream2(bytes(img[b1 - BASE:b1 - BASE + 4 * n1]), n1))
    assert magic == MAGIC
    t = bytes(img[tab - BASE:b0 - BASE])
    return unpack(img[b0 - BASE:], t, doff, n0), unpack(img[b1 - BASE:], t, doff, n1)


def install(img, report):
    import core0, dspzip, rhbuild, stepmut
    from thumb import bl
    assert struct.unpack_from('<I', img, TABLE - BASE + 8)[0] == BLK1
    raw0 = dspzip.raw_stream(img)
    n1 = int.from_bytes(img[BLK1 - BASE + 1:BLK1 - BASE + 3], 'big')
    raw1 = bytes(img[BLK1 - BASE:BLK1 - BASE + 3 * (n1 + 2)])
    lo, hi = BLK1, dspzip.BLK0 + 3 * (core0.N0 + 2)                # both stock blocks, one after the other
    assert BLK1 + len(raw1) <= dspzip.BLK0
    rc = os.environ.get('RH_DSP_RC') == '1'
    if rc:
        import dsprc
        tab, doff = b'', 0
        s0, s1 = dsprc.pack(raw0) + RC_PAD, dsprc.pack(raw1) + RC_PAD
        assert dsprc.NPROB * 2 <= WINDOW - PROBS and WINDOW + dsprc.WIN_RC <= 0x3AE0
    else:
        llbits, dbits, (t0, t1) = pack([raw0, raw1])
        tab, doff = tables(llbits, dbits)
        s0, s1 = bitstream(t0, llbits, dbits), bitstream(t1, llbits, dbits)
    z = report['dspzip']
    d0up, dz, d1up = (int(x, 16) for x in (report['core0']['labels']['c_d0up'], report['core0']['labels']['c_dz'],
                                           report['pitchmod']['labels']['c_d1up']))
    defs = dict(DIR=BLK1, RING=int(z['ring'], 16), WAIT=dspzip.WAIT, SELECT=dspzip.SELECT, SPI=dspzip.SPI, END=dspzip.END,
                SEND=SEND, BLK1=BLK1, C_RST=int(report['rhstate']['labels']['c_rst'], 16))
    if rc:
        defs.update(RC=1, PROBS=PROBS, WINDOW=WINDOW)
    origin = BLK1 + DIR_LEN
    code, labels = stepmut.compile_c(origin, defs, src=ROOT / 'modules/dsppack.c', name='dsppack', prefix='c_hz_',
                                     need=('c_hz_core0', 'c_hz_core1'), max_code=0x800 if rc else 0x400)
    at_tab = (origin + len(code) + 3) & ~3
    at0 = at_tab + len(tab); at1 = at0 + len(s0); end = at1 + len(s1)
    assert end <= hi, 'the packed programs do not fit'
    body = struct.pack('<4s6I', MAGIC_RC if rc else MAGIC, at_tab, doff, at0, len(raw0), at1, len(raw1))
    img[lo - BASE:hi - BASE] = (body + code).ljust(at_tab - lo, b'\xff') + tab + s0 + s1 + b'\xff' * (hi - end)
    # core 0: dspzip's c_d0up sends its loader block, then our stream
    def is_bl(x):
        h1, h2 = struct.unpack_from('<HH', img, x - BASE)
        return h1 & 0xF800 == 0xF000 and h2 & 0xD000 == 0xD000
    calls = [x for x in range(d0up, dz, 2) if is_bl(x) and rhbuild.bl_target(img, x) == dz]
    assert len(calls) == 1
    rhbuild.patch(img, calls[0], f'bl #{dz:#x}', bl(calls[0], labels['c_hz_core0']))
    # core 1: pitchmod's c_d1up sends its block first, then its own blocks
    assert rhbuild.bl_target(img, d1up + 4) == SEND
    rhbuild.patch(img, d1up + 4, f'bl #{SEND:#x}', bl(d1up + 4, labels['c_hz_core1']))
    # dspzip's decoder and the rest of its stream are no longer used
    holes = [(end, hi)]
    loader = int(z['loader'], 16)
    img[dz - BASE:loader - BASE] = b'\xff' * (loader - dz); holes.append((dz, loader))
    if 'rest' in z:
        r = int(z['rest'], 16)
        img[r - BASE:r - BASE + z['rest_bytes']] = b'\xff' * z['rest_bytes']; holes.append((r, r + z['rest_bytes']))
    assert raw_streams(img) == (raw0, raw1)
    report['dsppack'] = dict(dir=hex(BLK1), labels={k: hex(v) for k, v in labels.items()}, code_bytes=len(code), table_bytes=len(tab),
                             core0=dict(raw_bytes=len(raw0), packed_bytes=len(s0), raw_sha256=hashlib.sha256(raw0).hexdigest()),
                             core1=dict(raw_bytes=len(raw1), packed_bytes=len(s1), raw_sha256=hashlib.sha256(raw1).hexdigest()),
                             holes=[[hex(a), hex(b), b - a] for a, b in holes], hole_bytes=sum(b - a for a, b in holes),
                             **({'rc': dict(probs=hex(PROBS), window=hex(WINDOW))} if rc else {}))
    return labels


def unpack(bits_, tab, doff, size):
    """the reference decoder (the ARM one does the same)"""
    def cnt(o):
        return struct.unpack_from('<16H', tab, o)
    llcount, dcount = cnt(0), cnt(doff)
    llsym = struct.unpack_from(f'<{sum(llcount)}H', tab, 32)
    dsym = tab[doff + 32:doff + 32 + sum(dcount)]
    pos = 0
    def bit():
        nonlocal pos
        b = (bits_[pos >> 3] >> (pos & 7)) & 1; pos += 1; return b
    def dec(count):
        code = first = index = 0
        for ln in range(1, MAXBITS + 1):
            code |= bit(); c = count[ln]
            if code - first < c:
                return index + code - first
            index += c; first += c; first <<= 1; code <<= 1
        raise ValueError('bad code')
    out = bytearray()
    while len(out) < size:
        s = llsym[dec(llcount)]
        if s < 256:
            out.append(s); continue
        ln, off = s - 256 + MINL, dsym[dec(dcount)] + 1
        for _ in range(ln):
            out.append(out[-off])
    assert len(out) == size
    return bytes(out)
