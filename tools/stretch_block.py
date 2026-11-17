"""Block model of the core 0 stretch engine: version E of stretch_model in the DSP's own arithmetic.

Words are 24-bit integers; the engine reads each sample word at half level (w >> 1), as core 1's sample
reader gives it. Gains are Q23, positions and steps Q24 (the DSP's a1:a0). One `block()` makes 32 output
words. Splices start at block edges. A search takes SEARCH_STAGES blocks before its splice and only one
track searches at a time (tracks run in order 0..7). `modules/stretch_dsp.py` must give the same words.
"""
from __future__ import annotations

import math

BLK = 32
ONE = 0x7FFFFF
HOP_BLOCKS = 48                     # 1,536 samples
LOCK_BLOCKS = 3                     # 96 samples
DELTA, TL = 480, 384                # search window ±DELTA, samples compared
CSTEP, CDEC = 8, 8                  # coarse: candidates 8 apart, every 8th sample
FDEC, FRANGE = 2, 7                 # fine: every 2nd sample, ±7 around the coarse best
HOLD = 480                          # searches start at least this far past the last hit
OBLK, OGAP = 128, 2400              # hit analysis block, minimum distance between hits
OFLOOR = 42                         # hit floor in the analysis energy's units
NONSETS = 4
SEARCH_STAGES = 8                   # template, 2 copies, 3 coarse, 2 fine
RATE_SEARCH_MAX = 2 << 24           # search offsets use at most 2x
LOOKAHEAD = BLK * 4 + 2 * OBLK      # hits are known this far past the playhead
ONESHOT_TAIL = 1 << 16              # a one-shot stops this far past its end (positions stay inside 24 bits)


def gain_table(nb):
    return [round(math.sin(0.5 * math.pi * j / nb) ** 2 * ONE) for j in range(nb + 1)]


G_HOP, G_LOCK = gain_table(HOP_BLOCKS), gain_table(LOCK_BLOCKS)


def mul(a, b):
    """DSP fractional multiply, truncated: a1 of mpy a,b."""
    return (a * b) >> 23


def offsets(rate, dec):
    r = min(rate, RATE_SEARCH_MAX)
    return [((1 << 23) + i * r) >> 24 for i in range(0, TL, dec)]


class Search:
    owner = None                    # the track that holds the one search scratch


class Track:
    def __init__(self, x, speed, rate, loop=False):
        """x: the region's words in playback order; speed, rate: Q24; loop: reads wrap at the region's end."""
        self.x, self.n, self.loop = x, len(x), loop
        self.speed, self.rate = speed, rate
        self.restart()
        self.stats = dict(splices=0, locks=0, kept=0, delayed=0)

    def restart(self, at=0):
        """at: the region index to start from (a resume in place), 0 for a new note."""
        if Search.owner is self:
            Search.owner = None
        self.P = at << 24
        self.heads = [[at << 24, ONE, ONE]]          # [position Q24, gain at fade start, gain at fade end]
        self.fj, self.table = HOP_BLOCKS, G_HOP      # blocks into the fade, its table
        self.to_splice = HOP_BLOCKS
        self.floor = at
        self.onsets = []
        self.scan_at, self.e_hist, self.top, self.last_on = at + OBLK, [], 0, at - OGAP - 1
        self.stage = None

    def h(self, i):
        """The half-level word at region index i."""
        if self.loop:
            return self.x[i % self.n] >> 1
        return self.x[i] >> 1 if 0 <= i < self.n else 0

    def scan(self):
        """One analysis block: energy of the first difference, against the 4 blocks before and the loudest."""
        base = self.scan_at
        v = [self.h(base + k) - self.h(base + k - 1) for k in range(OBLK)]
        total = sum(d * d for d in v)
        e = total >> 30
        self.top = max(self.top, e)
        hist = self.e_hist
        if (len(hist) == 4 and 2 * e > 3 * sum(hist) + 2 * OFLOOR and 10 * e >= self.top
                and base - self.last_on > OGAP and len(self.onsets) < NONSETS):
            th, run, k = (2 * total) >> 3, 0, 0
            for k, d in enumerate(v):
                run += 2 * d * d
                if run >= th:
                    break
            self.onsets.append(max(0, base + k - 16))
            self.last_on = base
        self.e_hist = (hist + [e])[-4:]
        self.scan_at += OBLK

    def read(self, pos):
        i, f = pos >> 24, (pos & 0xFFFFFF) >> 1
        a = self.h(i)
        return a + mul(self.h(i + 1) - a, f)

    def gains(self, j):
        g = self.table[min(j, len(self.table) - 1)]
        return [c + mul(t - c, g) for _, c, t in self.heads]

    def splice(self, start, table):
        g = self.gains(self.fj)
        self.heads = [[h[0], gi, 0] for h, gi in zip(self.heads, g) if gi > 0] + [[start, 0, ONE]]
        assert len(self.heads) <= 3
        self.fj, self.table = 0, table
        self.stats["splices"] += 1

    def ssd2(self, c, offs, tmpl):
        """Twice the squared difference from the template, as the DSP's mac sums it."""
        return sum(2 * (t - self.h(c + o)) ** 2 for o, t in zip(offs, tmpl))

    def search(self, lead, target):
        oc, of = offsets(self.rate, CDEC), offsets(self.rate, FDEC)
        li = lead >> 24
        tc = [self.h(li + o) for o in oc]
        tf = [self.h(li + o) for o in of]
        T = target >> 24
        lo = max(T - DELTA, self.floor)
        hi = max(T + DELTA, lo)
        best, bc = None, lo
        for c in range(lo, hi + 1, CSTEP):
            v = self.ssd2(c, oc, tc)
            if best is None or v < best:
                best, bc = v, c
        best, bf = None, lo
        for c in range(max(lo, bc - FRANGE), min(hi, bc + FRANGE) + 1):
            v = self.ssd2(c, of, tf)
            if best is None or v < best:
                best, bf = v, c
        keep = lo <= li <= hi and self.ssd2(li, of, tf) <= best + (best >> 10)
        return keep, (bf << 24) | (lead & 0xFFFFFF)

    def rebase(self):
        """A loop moves every region index back by its length once the playhead passes the end."""
        n = self.n
        self.P -= n << 24
        for hd in self.heads:
            hd[0] -= n << 24
        self.onsets = [o - n for o in self.onsets]
        self.floor -= n
        self.scan_at -= n
        self.last_on -= n

    def block(self):
        if not self.loop and (self.P >> 24) - self.n > ONESHOT_TAIL:
            return [0] * BLK
        if self.loop and self.stage is None and (self.P >> 24) >= self.n:
            self.rebase()
        while self.scan_at < (self.P >> 24) + LOOKAHEAD:
            self.scan()
        P0, P1 = self.P, self.P + BLK * self.speed
        if self.onsets and self.onsets[0] < (P1 >> 24):
            # a hit inside this block: a head starts so that the hit lands on its sample
            o = self.onsets.pop(0) << 24
            k, p = 0, P0
            while p < o:
                k, p = k + 1, p + self.speed
            self.splice(max(0, o - k * self.rate), G_LOCK)
            self.floor = (o >> 24) + HOLD
            self.to_splice = HOP_BLOCKS
            self.stats["locks"] += 1
            if Search.owner is self:
                Search.owner, self.stage = None, None
        else:
            if self.stage is None and self.to_splice <= SEARCH_STAGES and Search.owner is None:
                Search.owner = self
                self.to_splice = SEARCH_STAGES
                lead = self.heads[-1][0] + (self.rate << 8)
                self.stage = [0, self.search(lead, P0 + (self.speed << 8))]
            if self.stage is not None and self.stage[0] < SEARCH_STAGES:
                self.stage[0] += 1
            if self.to_splice <= 0:
                if self.stage is not None and self.stage[0] >= SEARCH_STAGES:
                    (keep, start), self.stage, Search.owner = self.stage[1], None, None
                    if keep:
                        self.stats["kept"] += 1
                    else:
                        self.splice(start, G_HOP)
                    self.to_splice = HOP_BLOCKS
                else:
                    self.stats["delayed"] += 1
        g0, g1 = self.gains(self.fj), self.gains(self.fj + 1)
        out = [0] * BLK
        for hd, a, b in zip(self.heads, g0, g1):
            step, g, pos = (b - a) >> 5, a, hd[0]
            for i in range(BLK):
                out[i] += mul(self.read(pos), g)
                pos += self.rate
                g += step
            hd[0] = pos
        self.fj += 1
        if self.fj >= len(self.table) - 1:
            self.heads = [[p, t, t] for p, _, t in self.heads if t > 0]
            self.fj, self.table = HOP_BLOCKS, G_HOP
        self.P = P1
        self.to_splice -= 1
        return out


def render(x24, speed, rate=1.0, loop=False):
    """x24: ints in playback order; -> output words (half level, like core 1's sample reader), stats."""
    Search.owner = None
    t = Track(x24, round(speed * (1 << 24)), round(rate * (1 << 24)), loop)
    n_out = int((len(x24) - 1) / speed)
    out = []
    while len(out) < n_out:
        out += t.block()
    return out[:n_out], t.stats
