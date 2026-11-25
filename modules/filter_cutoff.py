"""DSP adapter for applying a signed per-track offset to native low-pass cutoff."""

import core0
import rhdsp1


STOCK_CUTOFF = 0x523
LOWPASS_CALL = 0x528
LOWPASS_CALL_WORD = 0x0508C8
LOWPASS = 0x590
TRACK = 0x1405
OFFSET = 0x1E00
TRACKS = 8
SCRATCH = OFFSET + TRACKS
SCRATCH_REGISTERS = ('a0', 'a1', 'a2', 'x0', 'r1', 'n1', 'sr')


def code(origin):
    """Adjust the already-loaded cutoff, then tail-call the stock filter."""
    return core0.asm_at([
        ('label', 'cutoff'),
        *(f'move {reg},y:>${SCRATCH+i:x}' for i, reg in enumerate(SCRATCH_REGISTERS)),
        f'move y:>${TRACK:x},n1',
        f'move #>${OFFSET:x},r1',
        'move y:(r1+n1),a',
        'tst a',
        ('jcc', 'eq', 'restore'),
        'move n5,a',
        'move y:(r1+n1),x0',
        'add x0,a',
        'move #>$0,x0',
        'cmp x0,a',
        'tlt x0,a',
        'move #>$80,x0',
        'cmp x0,a',
        'tgt x0,a',
        'move a1,n5',
        ('label', 'restore'),
        *(f'move y:>${SCRATCH+i:x},{reg}' for i, reg in enumerate(SCRATCH_REGISTERS)),
        ('jmp', LOWPASS),
    ], origin)


def patches(address):
    assert 0 <= address < 0x1000
    return [(LOWPASS_CALL, LOWPASS_CALL_WORD, 0x0D0000 | address)]


def patch_stock(image, address):
    for destination, original, replacement in patches(address):
        rhdsp1.patch_p(image, destination, original, replacement)


def install_dsp(image, report, origin):
    """Link the adapter after the stock cutoff and resonance loads."""
    import dspmap
    import granular_layout

    regions = dspmap.regions(report)
    end = SCRATCH + len(SCRATCH_REGISTERS)
    assert any(lo <= OFFSET and end <= hi
               for lo, hi in dspmap.free(regions, 1, 'y'))
    assert not any(r.core == 1 and r.space == 'y'
                   and OFFSET < r.end and r.start < end
                   for r in granular_layout.REGIONS)

    words, labels = code(origin)
    assert origin + len(words) <= dspmap.SIZE[1, 'p']
    patch_stock(image, labels['cutoff'])
    report['filter_cutoff'] = dict(cutoff=hex(labels['cutoff']),
                                   words=len(words), offset=hex(OFFSET), tracks=TRACKS,
                                   data_words=end-OFFSET)
    return words


def initialize_offsets(raw, offset=OFFSET, tracks=TRACKS):
    """Prepend a normal Y segment to the mode-0 DSP loader stream."""
    assert len(raw)%3==0 and int.from_bytes(raw[:3],'big')+2==len(raw)//3
    assert raw[3:6]==b'\0\0\0'
    segment=(2,tracks,offset,*([0]*tracks))
    count=len(raw)//3-2+len(segment)
    return count.to_bytes(3,'big')+raw[3:6]+b''.join(w.to_bytes(3,'big') for w in segment)+raw[6:]
