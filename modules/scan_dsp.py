"""Scan: each note of a plain track starts further into its sample (core 1, at the note start P:$32D)."""

import core0

TRIGGER = 0x32D
SHIFT_WORD = 0x0C1D93  # asl #9,b,b: b = the start, a fraction of the sample
JSR_SHORT = 0x0D0000
AMOUNT = 0x1E10  # Y + track: 0..$7fffff, the share of the room after the start that the start moves on
SAVE = AMOUNT + 8
DATA_WORDS = 9


def code(origin):
    """start + amount x (1 - start). x1, y1 and n1 are written by the stock before they are read again."""
    return core0.asm_at([
        ('label', 'scan'),
        'asl #9,b,b', 'move b1,x1',
        'move n3,b', 'and #>$7,b', 'move b1,n1',
        f'move r1,y:>${SAVE:x}', f'move #>${AMOUNT:x},r1',
        'move x1,b', 'move y:(r1+n1),y1',
        'mac -x1,y1,b', 'add y1,b',
        f'move y:>${SAVE:x},r1', 'rts',
    ], origin)


def hook(segments, origin, report):
    """Call the adapter at P:$32D and add its words at origin."""
    words, labels = code(origin)
    out, seen = [], False
    for space, address, data in segments:
        if space == 'p' and address <= TRIGGER < address + len(data):
            data = list(data)
            assert data[TRIGGER - address] == SHIFT_WORD
            data[TRIGGER - address] = JSR_SHORT | labels['scan']
            seen = True
        out.append((space, address, data))
    assert seen and origin + len(words) <= 0x1000
    report['scan_dsp'] = dict(entry=hex(labels['scan']), words=len(words), amount=hex(AMOUNT), data_words=DATA_WORDS)
    return out + [('p', origin, words)], words
