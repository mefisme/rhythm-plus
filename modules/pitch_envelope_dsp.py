"""Prototype DSP adapter for adding a per-track log-pitch offset."""

import core0
import pitchmod

OFFSET = 0x1E20
TRACKS = 8
SCRATCH = OFFSET + TRACKS
INITIAL = OFFSET + 16
NOTE_CALL = 0x168
NOTE_CALL_WORD = 0x05089B
REGISTERS = ("a0", "a1", "a2", "r1", "n1", "sr")


def code(origin):
    """Add the active voice's offset in Stock pitch units before resampling."""
    save = [f"move {reg},y:>${SCRATCH + i:x}" for i, reg in enumerate(REGISTERS)]
    track_index = ["move r4,a", "sub #>$40,a", "lsr #4,a", "move a1,n1"]
    return core0.asm_at([
        ("label", "note"),
        *save, *track_index,
        f"move #>${INITIAL:x},r1",
        "move y:(r1+n1),a",
        f"move #>${OFFSET:x},r1",
        "move a1,y:(r1+n1)",
        ("jmp", "mix"),
        ("label", "pitch"),
        *save, *track_index,
        f"move #>${OFFSET:x},r1",
        "move y:(r1+n1),a",
        ("label", "mix"),
        "tst a",
        ("jcc", "eq", "restore"),
        "add y0,a",
        f"move #>${pitchmod.PITCH_MAX:x},y0",
        "cmp y0,a",
        "tgt y0,a",
        f"move #>${pitchmod.PITCH_MIN:x},y0",
        "cmp y0,a",
        "tlt y0,a",
        "move a1,y0",
        ("label", "restore"),
        *(f"move y:>${SCRATCH + index:x},{reg}"
          for index, reg in enumerate(REGISTERS)),
        ("jmp", pitchmod.P_EXP),
    ], origin)



def install(image, report, origin):
    """Wrap the native periodic pitch update in the offline firmware."""
    import dspmap
    import rhdsp1

    words, labels = code(origin)
    end = INITIAL + TRACKS
    assert origin + len(words) <= dspmap.SIZE[1, 'p']
    assert any(lo <= OFFSET and end <= hi
               for lo, hi in dspmap.free(dspmap.regions(report), 1, 'y'))
    rhdsp1.patch_p(image, pitchmod.P_RR_CALL, pitchmod.OLD_RR_CALL,
                  pitchmod.JSR_SHORT | labels['pitch'])
    rhdsp1.patch_p(image, NOTE_CALL, NOTE_CALL_WORD, pitchmod.JSR_SHORT | labels['note'])
    report['pitch_envelope_dsp'] = dict(entry=hex(labels['pitch']), note=hex(labels['note']), words=len(words),
                                       offset=hex(OFFSET), tracks=TRACKS, data_words=end-OFFSET)
    return words
