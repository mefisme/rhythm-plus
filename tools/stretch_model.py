"""Reference model of the core 0 time stretch engine, for listening tests and the DSP port.

The playhead moves `speed` source samples per output sample; read heads move `rate` (Tune) samples.
Every `hop` output samples a new head starts where the source best matches the running head (WSOLA)
and crossfades in. When the playhead reaches a transient, a head starts exactly on it with a short fade,
and later searches cannot go back before it, so a hit plays once and keeps its attack.
"""
from __future__ import annotations

import math
import sys
import wave
from pathlib import Path

import numpy as np

SR = 48000


def load(path, start=0.0, secs=None):
    with wave.open(str(path)) as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    assert sw == 2, "16-bit WAV only"
    x = np.frombuffer(raw, "<i2").astype(np.float64).reshape(-1, ch).mean(axis=1) / 32768
    a = int(start * sr)
    b = len(x) if secs is None else a + int(secs * sr)
    return x[a:b], sr


def save(path, x, sr):
    q = np.round(np.clip(x, -1, 1 - 2 ** -23) * 2 ** 23) / 2 ** 23   # 24-bit DSP word
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(np.round(q * 32767).astype("<i2").tobytes())


def read(x, pos):
    """Linear interpolation, zero outside the sample."""
    i = np.floor(pos).astype(np.int64)
    f = pos - i
    ok0 = (i >= 0) & (i < len(x))
    ok1 = (i + 1 >= 0) & (i + 1 < len(x))
    a = np.where(ok0, x[np.clip(i, 0, len(x) - 1)], 0.0)
    b = np.where(ok1, x[np.clip(i + 1, 0, len(x) - 1)], 0.0)
    return a + (b - a) * f


def onsets(x, blk=128, ratio=6.0, floor=2e-5, gap=2400, loud=0.1):
    """Transient positions: high-band energy of a 128-sample block well above the 4 blocks before it
    and at least `loud` of the loudest block so far."""
    d = np.diff(x, prepend=x[0])
    nb = len(d) // blk
    e = (d[:nb * blk] ** 2).reshape(nb, blk).sum(axis=1)
    out = []
    top = 0.0
    for j in range(4, nb):
        ref = e[j - 4:j].mean()
        top = max(top, e[j])
        if e[j] > ratio * ref + floor * blk and e[j] >= loud * top and (not out or j * blk - out[-1] > gap):
            c = np.cumsum(d[j * blk:(j + 1) * blk] ** 2)
            out.append(max(0, j * blk + int(np.searchsorted(c, 0.1 * c[-1])) - 16))
    return out


class Stats:
    def __init__(self):
        self.splices = self.locks = self.kept = self.macs = self.reads = 0
        self.peak_heads = 1


def stretch(x, speed, rate=1.0, hop=1024, delta=480, lock=True, tfade=96, tout=96, hold=480, dec=8, step=8,
            fdec=2, xf=None, tl=None, st=None):
    """xf: crossfade of a splice (default hop); tl: samples the search compares (default xf); tfade / tout: fade in of the head on a hit, fade out of the heads under it
    (equal lengths keep the total gain at 1)."""
    st = st or Stats()
    delta = min(delta, hop // 2)
    xf = xf or hop
    n_out = int((len(x) - 1) / speed)
    out = np.zeros(n_out)
    heads = [[0.0, 1.0, 1.0]]                      # [position, gain at fade start, gain at fade end]
    fade_t, fade_n = 0, 1                          # samples into the fade, fade length
    out_n = 1                                      # fade length of the old heads
    ons = onsets(x) if lock else []
    oi = 0
    floor = 0.0
    while oi < len(ons) and ons[oi] <= 0:
        floor = ons[oi] + hold; oi += 1
    t, next_splice = 0, hop

    def ramp(t, n):
        return np.sin(0.5 * np.pi * np.minimum(t, n) / n) ** 2

    def gain_now():
        si, so = float(ramp(fade_t, fade_n)), float(ramp(fade_t, out_n))
        return [h[1] + (h[2] - h[1]) * (si if h[2] > h[1] else so) for h in heads]

    def splice(target, flen, search, olen=None):
        nonlocal heads, fade_t, fade_n, out_n
        target = max(target, floor)
        lead = heads[-1][0]
        best = target
        if search:
            L = min(flen, tl or flen)
            idx = np.arange(0, L, dec) * rate
            tmpl = read(x, lead + idx)
            lo = max(math.ceil(target - delta), math.ceil(floor))
            hi = int(target + delta)
            if hi < lo:
                hi = lo
            fidx = np.arange(0, L, fdec) * rate
            ftmpl = read(x, lead + fidx)
            def score(cs, idx=idx, tmpl=tmpl):
                seg = read(x, np.asarray(cs, dtype=np.float64)[:, None] + idx[None, :])
                c = seg @ tmpl
                e = (seg * seg).sum(axis=1) + 1e-12
                st.macs += seg.size * 2
                return c * np.abs(c) / e
            coarse = np.arange(lo, hi + 1, step)
            sc = score(coarse)
            k = int(np.argmax(sc))
            fine = np.arange(max(lo, coarse[k] - step + 1), min(hi, coarse[k] + step - 1) + 1)
            sf = score(fine, fidx, ftmpl)
            best = float(fine[int(np.argmax(sf))]) + (lead - math.floor(lead))
            st.reads += (hi - lo + 1) + int(L * rate)
            if lo <= lead <= hi:                       # the running head is a candidate too
                sn = score([lead], fidx, ftmpl)[0]
                if sn >= sf.max() * 0.999:
                    st.kept += 1
                    return
        g = gain_now()
        heads = [[h[0], gi, 0.0] for h, gi in zip(heads, g) if gi > 1e-6] + [[best, 0.0, 1.0]]
        st.peak_heads = max(st.peak_heads, len(heads))
        fade_t, fade_n, out_n = 0, flen, olen or flen
        st.splices += 1

    while t < n_out:
        end = min(next_splice, n_out)
        t_on = math.ceil(ons[oi] / speed) if oi < len(ons) else n_out + 1
        if t_on <= t:
            splice(ons[oi], tfade, False, tout)
            floor = ons[oi] + hold
            oi += 1
            st.locks += 1
            next_splice = t + hop
            continue
        end = min(end, t_on)
        m = end - t
        ii = np.arange(m)
        si, so = ramp(fade_t + ii, fade_n), ramp(fade_t + ii, out_n)
        y = np.zeros(m)
        for h in heads:
            y += read(x, h[0] + ii * rate) * (h[1] + (h[2] - h[1]) * (si if h[2] > h[1] else so))
            h[0] += m * rate
        out[t:end] = y
        fade_t += m
        if fade_t >= max(fade_n, out_n):
            heads = [[h[0], h[2], h[2]] for h in heads if h[2] > 0]
        t = end
        if t >= next_splice:
            splice(t * speed, xf, True)
            next_splice = t + hop
    return out, st


def remix_two_grain(x, speed, rate=1.0, g=2048):
    """Two grains half a grain apart, each starting at the playhead, triangular windows (Remix's stretch)."""
    n_out = int((len(x) - 1) / speed)
    t = np.arange(n_out)
    y = np.zeros(n_out)
    for off in (0, g // 2):
        age = (t + off) % g
        start = (t - age) * speed
        w = 1 - np.abs(age - g / 2) / (g / 2)
        y += read(x, start + age * rate) * w
    return y


if __name__ == "__main__":
    x, sr = load(sys.argv[1])
    y, s = stretch(x, float(sys.argv[3]))
    save(sys.argv[2], y, sr)
    print(vars(s))
