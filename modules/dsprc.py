"""LZ + adaptive binary range coding for the DSP programs: Circuit Remix's dspz.py coder (MIT; its RH95, from CIRCUIT-HACKS' SC56 "DZ2"),
copied unchanged: LZMA's model with lc = lp = pb = 0, rep0 only, short rep, matched literals, a 4 KB window.  The stream starts with the
decoder's first four code bytes; the decoder reads bytes past the stream as 0xFF.  dsppack.c's RC decoder does the same as unpack_stream2."""
import hashlib
from pathlib import Path

CACHE = Path(__file__).resolve().parents[1] / "buildtmp" / "dsprc"
WIN_RC = 0x1000
MAXL_RC = 273
PBITS, PMOVE, PONE, PTOP = 11, 5, 1 << 11, 1 << 24
# probability indices: literals first (the literal loop adds nothing)
LIT, ISM, ISR, ISR0L = 0, 0x300, 0x30C, 0x318
MLEN, RLEN = 0x324, 0x324 + 274
SLOT = RLEN + 274
SPEC = SLOT + 256
ALIGN = SPEC + 114
NPROB = ALIGN + 16
NEXT_LIT = (0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 4, 5)


def _prices():
    P = []
    for i in range(PONE >> 4):
        w, bc = (i << 4) + 8, 0
        for _ in range(4):
            w = w * w; bc <<= 1
            while w >= 1 << 16: w >>= 1; bc += 1
        P.append((PBITS << 4) - 15 - bc)
    return P


_PT = _prices()


def _slot(d):
    if d < 4: return d
    n = d.bit_length() - 1
    return 2 * n + ((d >> (n - 1)) & 1)


def _lit_bits(byte, st, mbyte):
    """(index, bit) of a literal; matched (st >= 7) as LZMA's: offs = 0x100 while the bits agree with the match byte's."""
    offs = 0x100 if st >= 7 else 0
    m, sym, out = mbyte, 1, []
    for k in range(7, -1, -1):
        m <<= 1; bit = m & offs; b = (byte >> k) & 1
        out.append((LIT + offs + bit + sym, b))
        sym = sym << 1 | b
        offs = offs & bit if b else offs & ~bit
    return out


def _len_bits(o, l):
    l -= 2
    if l < 8: out, sub, nb, base = [(o, 0)], l, 3, o + 2
    elif l < 16: out, sub, nb, base = [(o, 1), (o + 1, 0)], l - 8, 3, o + 10
    else: out, sub, nb, base = [(o, 1), (o + 1, 1)], l - 16, 8, o + 18
    m = 1
    for j in range(nb - 1, -1, -1):
        b = (sub >> j) & 1; out.append((base + m, b)); m = m << 1 | b
    return out


def _dist_bits(l, d):
    """(index, bit) and ('D', value, n) for the direct bits."""
    sl, out, m = _slot(d), [], 1
    base = SLOT + 64 * min(l - 2, 3)
    for j in range(5, -1, -1):
        b = (sl >> j) & 1; out.append((base + m, b)); m = m << 1 | b
    if sl >= 4:
        nd = (sl >> 1) - 1; bse = (2 | (sl & 1)) << nd; rem = d - bse
        if sl < 14:
            o, m = SPEC + bse - sl - 1, 1
            for j in range(nd):
                b = (rem >> j) & 1; out.append((o + m, b)); m = m << 1 | b
        else:
            out.append(("D", rem >> 4, nd - 4)); m = 1
            for j in range(4):
                b = (rem >> j) & 1; out.append((ALIGN + m, b)); m = m << 1 | b
    return out


class _Enc:
    def __init__(s):
        s.low, s.rng, s.cache, s.csize, s.out = 0, 0xFFFFFFFF, 0, 1, bytearray()

    def _shift(s):
        if s.low < 0xFF000000 or s.low >= 1 << 32:
            c, t = s.low >> 32, s.cache
            while True:
                s.out.append((t + c) & 0xFF); t = 0xFF; s.csize -= 1
                if s.csize == 0: break
            s.cache = (s.low >> 24) & 0xFF
        s.csize += 1
        s.low = (s.low & 0x00FFFFFF) << 8

    def bits(s, P, seq):
        for t in seq:
            if t[0] == "D":
                v, n = t[1], t[2]
                for k in range(n - 1, -1, -1):
                    s.rng >>= 1
                    if (v >> k) & 1: s.low += s.rng
                    if s.rng < PTOP: s.rng = (s.rng << 8) & 0xFFFFFFFF; s._shift()
                continue
            i, b = t
            p = P[i]; bound = (s.rng >> PBITS) * p
            if b == 0: s.rng = bound; P[i] = p + ((PONE - p) >> PMOVE)
            else: s.low += bound; s.rng -= bound; P[i] = p - (p >> PMOVE)
            if s.rng < PTOP: s.rng = (s.rng << 8) & 0xFFFFFFFF; s._shift()

    def flush(s):
        for _ in range(5): s._shift()
        assert s.out[0] == 0
        return bytes(s.out[1:])


def _matches(raw):
    """At every position the (length, distance - 1) pairs of growing length, nearest first, inside the window."""
    n, heads, res = len(raw), {}, []
    for i in range(n):
        out = []
        if i + 2 <= n:
            key = raw[i] << 8 | raw[i + 1]
            ch = heads.get(key)
            if ch:
                bl_ = 1
                for k in range(len(ch) - 1, -1, -1):
                    j = ch[k]
                    if i - j > WIN_RC: break
                    l = 0
                    while l < MAXL_RC and i + l < n and raw[j + l] == raw[i + l]: l += 1
                    if l > bl_: bl_ = l; out.append((l, i - j - 1))
                    if l == MAXL_RC: break
                ch.append(i)
            else:
                heads[key] = [i]
        res.append(out)
    return res


def _pack2(raw: bytes) -> bytes:
    n = len(raw)
    cand = _matches(raw)
    P = [PONE // 2] * NPROB
    INF = 1 << 60
    for ps in range(2):
        Q = list(P) if ps else [PONE // 2] * NPROB                         # the prices of this pass (pass 0: every bit 1)
        def price(seq):
            c = 0
            for t in seq:
                if t[0] == "D": c += 16 * t[2]
                else: c += _PT[(Q[t[0]] if t[1] == 0 else PONE - Q[t[0]]) >> 4]
            return c
        def bp(i, b): return _PT[(Q[i] if b == 0 else PONE - Q[i]) >> 4]
        cost = [INF] * (n + 1); cost[0] = 0
        stt, rep, back = [0] * (n + 1), [0] * (n + 1), [None] * (n + 1)
        for i in range(n):
            c0 = cost[i]
            st, r0 = stt[i], rep[i]
            mb = raw[i - r0 - 1] if i - r0 - 1 >= 0 else 0
            pc = c0 + bp(ISM + st, 0) + price(_lit_bits(raw[i], st, mb))
            if pc < cost[i + 1]: cost[i + 1], stt[i + 1], rep[i + 1], back[i + 1] = pc, NEXT_LIT[st], r0, (i, 0, 1)
            if i > r0:
                lr, j = 0, i - r0 - 1
                while lr < MAXL_RC and i + lr < n and raw[j + lr] == raw[i + lr]: lr += 1
                if lr:
                    base = c0 + bp(ISM + st, 1) + bp(ISR + st, 1)
                    pc = base + bp(ISR0L + st, 0)
                    if pc < cost[i + 1]: cost[i + 1], stt[i + 1], rep[i + 1], back[i + 1] = pc, (9 if st < 7 else 11), r0, (i, 1, 1)
                    b2 = base + bp(ISR0L + st, 1)
                    for l in range(2, lr + 1):
                        pc = b2 + price(_len_bits(RLEN, l))
                        if pc < cost[i + l]: cost[i + l], stt[i + l], rep[i + l], back[i + l] = pc, (8 if st < 7 else 11), r0, (i, 2, l)
            base = c0 + bp(ISM + st, 1) + bp(ISR + st, 0)
            prevl = 1
            for l, d in cand[i]:
                for ll in range(max(2, prevl + 1), l + 1):
                    pc = base + price(_len_bits(MLEN, ll)) + price(_dist_bits(ll, d))
                    if pc < cost[i + ll]: cost[i + ll], stt[i + ll], rep[i + ll], back[i + ll] = pc, (7 if st < 7 else 10), d, (i, 3, ll)
                prevl = l
        ops, i = [], n
        while i > 0:
            b_ = back[i]; ops.append((b_[0], b_[1], b_[2], rep[i])); i = b_[0]
        ops.reverse()
        E, P, st, r0 = _Enc(), [PONE // 2] * NPROB, 0, 0
        for i, k, l, d in ops:
            if k == 0:
                mb = raw[i - r0 - 1] if i - r0 - 1 >= 0 else 0
                E.bits(P, [(ISM + st, 0)] + _lit_bits(raw[i], st, mb)); st = NEXT_LIT[st]
            elif k == 1:
                E.bits(P, [(ISM + st, 1), (ISR + st, 1), (ISR0L + st, 0)]); st = 9 if st < 7 else 11
            elif k == 2:
                E.bits(P, [(ISM + st, 1), (ISR + st, 1), (ISR0L + st, 1)] + _len_bits(RLEN, l)); st = 8 if st < 7 else 11
            else:
                E.bits(P, [(ISM + st, 1), (ISR + st, 0)] + _len_bits(MLEN, l) + _dist_bits(l, d)); st = 7 if st < 7 else 10; r0 = d
        out = E.flush()
    return out


def unpack_stream2(data: bytes, size: int) -> bytes:
    """The decoder as the ARM one (bytes past the stream read as 0xFF)."""
    pos = [4]
    def nb():
        b_ = data[pos[0]] if pos[0] < len(data) else 0xFF; pos[0] += 1; return b_
    code, rng = int.from_bytes(data[:4], "big"), 0xFFFFFFFF
    P = [PONE // 2] * NPROB
    def bit(i):
        nonlocal code, rng
        p = P[i]; bound = (rng >> PBITS) * p
        if code < bound: rng = bound; P[i] = p + ((PONE - p) >> PMOVE); b_ = 0
        else: code -= bound; rng -= bound; P[i] = p - (p >> PMOVE); b_ = 1
        if rng < PTOP: rng = (rng << 8) & 0xFFFFFFFF; code = ((code << 8) | nb()) & 0xFFFFFFFF
        return b_
    def direct(n):
        nonlocal code, rng
        v = 0
        for _ in range(n):
            rng >>= 1; v <<= 1
            if code >= rng: code -= rng; v |= 1
            if rng < PTOP: rng = (rng << 8) & 0xFFFFFFFF; code = ((code << 8) | nb()) & 0xFFFFFFFF
        return v
    def tr(base, n):
        m, v = 1, 0
        for j in range(n):
            b_ = bit(base + m); m = m << 1 | b_; v |= b_ << j
        return v, m - (1 << n)
    def dlen(o):
        if not bit(o): return 2 + tr(o + 2, 3)[1]
        if not bit(o + 1): return 10 + tr(o + 10, 3)[1]
        return 18 + tr(o + 18, 8)[1]
    out, st, r0 = bytearray(), 0, 0
    while len(out) < size:
        if not bit(ISM + st):
            offs, m, sym = (0x100, out[-r0 - 1], 1) if st >= 7 else (0, 0, 1)
            while sym < 0x100:
                m <<= 1; b0 = m & offs
                b_ = bit(LIT + offs + b0 + sym); sym = sym << 1 | b_
                offs = offs & b0 if b_ else offs & ~b0
            out.append(sym & 0xFF); st = NEXT_LIT[st]; continue
        if bit(ISR + st):
            if not bit(ISR0L + st): l, st = 1, (9 if st < 7 else 11)
            else: l, st = dlen(RLEN), (8 if st < 7 else 11)
        else:
            l = dlen(MLEN); st = 7 if st < 7 else 10
            sl = tr(SLOT + 64 * min(l - 2, 3), 6)[1]
            if sl < 4: r0 = sl
            else:
                nd = (sl >> 1) - 1; d = (2 | (sl & 1)) << nd
                if sl < 14: d += tr(SPEC + d - sl - 1, nd)[0]
                else: d += direct(nd - 4) << 4; d += tr(ALIGN, 4)[0]
                r0 = d
        for _ in range(l): out.append(out[-r0 - 1])
    return bytes(out[:size])


def pack(raw: bytes) -> bytes:
    """the stream, cached by the raw bytes' hash (the encoder takes seconds)"""
    f = CACHE / f"{hashlib.sha256(raw).hexdigest()}.rc"
    if f.exists():
        return f.read_bytes()
    out = _pack2(raw)
    assert unpack_stream2(out, len(raw)) == raw
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_bytes(out)
    return out
