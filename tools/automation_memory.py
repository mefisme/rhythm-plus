"""Candidate logical DSP bank maps. A map validates addresses, not ownership.

Stock X3000..3FFF was disproved by AD007 hardware. No installed firmware uses
this replacement proposal; the upper span still needs a preservation proof.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    start: int
    words: int
    evidence: str


REPLACEMENT = (
    Span(0x2400, 0xc00, "canaries survived exercised playback/Grid FX"),
    Span(0x4000, 0x400, "canaries/prototype survived exercised playback/Grid FX"),
    Span(0x4f90, 0x1000, "zero read-only snapshot only; preservation UNPROVED"),
)
CANDIDATE_X_HOLES=((0x1420,0x1600),(0x2400,0x3000),(0x4000,0x4400),
                   (0x4d00,0x4f80),(0x4f90,0x6000))


class BankMap:
    def __init__(self, spans=REPLACEMENT):
        self.spans = tuple(spans)
        if not self.spans or len(self.spans)>8:
            raise ValueError("bank map requires one to eight spans")
        for span in self.spans:
            if (span.words <= 0 or span.words % 32 or span.start < 0
                    or span.start+span.words > 0x6000):
                raise ValueError("invalid/block-crossing X span")
            if max(span.start,0x3000) < min(span.start+span.words,0x4000):
                raise ValueError("known Grid FX workspace conflict")
            if not any(start<=span.start and span.start+span.words<=end
                       for start,end in CANDIDATE_X_HOLES):
                raise ValueError("stock/active-feature workspace conflict")
        ordered = sorted(self.spans, key=lambda span: span.start)
        if any(a.start+a.words > b.start for a,b in zip(ordered,ordered[1:])):
            raise ValueError("physical spans overlap")
        self.words = sum(span.words for span in self.spans)
        if self.words > 8192:
            raise ValueError("24KiB DSP ceiling exceeded")

    def physical(self, index):
        if not 0 <= index < self.words:
            raise ValueError("logical word out of range")
        for span in self.spans:
            if index < span.words:
                return span.start+index
            index -= span.words
        raise AssertionError("unreachable")

    def block(self, block):
        if not 0 <= block < self.words//32:
            raise ValueError("logical block out of range")
        start = self.physical(block*32)
        if self.physical(block*32+31) != start+31:
            raise ValueError("block crosses a physical span")
        return start,32
