"""Archived Ring Mod oscillator and wet mix, at the core 0 mixer input."""

import core0

ORIGIN = 0x3900
MIX_CALL = 0x224
MIX = 0x50  # The existing Grid FX mixer split, installed before this adapter.
OLD_CALL = (0x0BF080, MIX)
BANK = 0x304F0
STATE = 0x1E80
TRACKS = 8
SAVE = STATE + 3 * TRACKS


def oscillator(buffer):
    return [
        "add x0,b", "move b1,y0", "move y0,b", "tfr b,a", "abs a", "asl a",
        "sub #>$7fffff,a", "move a,x1", "abs a", "move a,y0", "mpy -x1,y0,a",
        "add x1,a", "add x1,a", "move a,x1", "mpy y1,x1,a", "sub y1,a",
        "add #>$7fffff,a", "move a,x1", f"move {buffer},y0", "mpy x1,y0,a",
        f"move a,{buffer}+",
    ]


def code():
    """Process the active bank without changing the native mixer's inputs when dry."""
    items = [("label", "ring"), ("jsr", "save"),
             "movep y:<<$ffffd0,b", "asl #5,b,b", "move b,n3",
             f"move #>${BANK:x},r3", "lua (r3)+n3,r3", "move #$40,n3",
             f"move #>${STATE:x},r6", "do #8,${track_end:x}",
             "move y:(r6+$10),a", "tst a", ("jcc", "eq", "next_track"),
             "move r3,r2", "move y:(r6),b", "move y:(r6+$8),x0",
             "move y:(r6+$10),y1", "move x:$3a,n5", "do n5,${sample_end:x}",
             *oscillator("y:(r2)"), ("label", "sample_end"), "move b1,y:(r6)",
             ("label", "next_track"), "move (r3)+n3", "move (r6)+",
             ("label", "track_end"), ("jsr", "restore"), ("jmp", MIX)]
    # Preserve the address registers and set linear addressing across the block.
    items += [("label", "save")]
    for k in (2, 3, 5, 6):
        items += [f"move r{k},y:>${SAVE+k:x}", f"move n{k},y:>${SAVE+8+k:x}",
                  ("words", [0x057060 | k, SAVE + 16 + k]),
                  ("words", [0x05F420 | k, 0xFFFFFF])]
    items += ["rts", ("label", "restore")]
    for k in (2, 3, 5, 6):
        items += [f"move y:>${SAVE+k:x},r{k}", f"move y:>${SAVE+8+k:x},n{k}",
                  ("words", [0x05F060 | k, SAVE + 16 + k])]
    items += ["rts"]
    return core0.asm_at(items, ORIGIN)


def segment(native, report):
    words, labels = code()
    actual = tuple(native[MIX_CALL:MIX_CALL+2])
    assert actual == OLD_CALL, tuple(hex(w) for w in actual)
    report["ring_mod_dsp"] = dict(entry=hex(labels["ring"]), words=len(words),
                                 state=hex(STATE), data_words=48, routing="after_filter")
    return [(ORIGIN, words), (MIX_CALL, [OLD_CALL[0], labels["ring"]])]


BEFORE_STATE = 0x1E60
BEFORE_SAVE = BEFORE_STATE + 3 * TRACKS
SOURCE_CALL = 0x23D


def before_source(segments, origin, source, report):
    """Apply the ring oscillator to the common source buffer before native filtering."""
    from granular_route_candidate import BUFFER

    # r1 is saved last, at BEFORE_SAVE+13, and is the pointer for the other saves.
    registers = ('a0', 'a1', 'a2', 'b0', 'b1', 'b2', 'x0', 'x1', 'y0', 'y1', 'r2', 'n1', 'sr')
    r1_save = BEFORE_SAVE + len(registers)
    words, labels = core0.asm_at([
        ('label', 'source'), ('jsr', source),
        f'move r1,y:>${r1_save:x}', f'move #>${BEFORE_SAVE:x},r1',
        *(f'move {reg},y:(r1)+' for reg in registers),
        'move y:>$1405,n1', f'move #>${BEFORE_STATE:x},r1', 'lua (r1)+n1,r1',
        'move y:(r1+$10),y1', 'move y1,a', 'tst a', ('jcc','eq','restore'),
        'move y:(r1),b', 'move y:(r1+$8),x0', f'move #>${BUFFER:x},r2',
        'do #$20,${end:x}', *oscillator('x:(r2)'), ('label','end'),
        'move b1,y:(r1)',
        ('label','restore'),
        f'move #>${BEFORE_SAVE:x},r1',
        *(f'move y:(r1)+,{reg}' for reg in registers),
        f'move y:>${r1_save:x},r1',
        'rts',
    ], origin)
    assert origin + len(words) <= 0x1000
    patched = []
    for space, address, values in segments:
        if space == 'p' and address <= SOURCE_CALL < address + len(values):
            index = SOURCE_CALL - address
            values = list(values)
            assert values[index] == 0x0D0000 | source
            values[index] = 0x0D0000 | labels['source']
        patched.append((space, address, values))
    report['ring_mod_before'] = dict(entry=hex(labels['source']), words=len(words),
                                    state=hex(BEFORE_STATE), data_words=24+len(registers)+1)
    return patched + [('p',origin,words)]
