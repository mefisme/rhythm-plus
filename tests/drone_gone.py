"""Expected core 1 words of a build without Drone, from a base build with it (fshape's drone_items first in smswitch's code)."""
import fshape as FS


def undrone(base, base_rep, rep):
    """base: {P address: word}; the drone words removed, later code and its addresses moved down, the note hooks the stock's"""
    if not rep.get('smswitch', {}).get('no_drone') or 'drone' not in base_rep.get('smswitch', {}):
        return base
    s = int(base_rep['smswitch']['drone'], 16)
    d = int(base_rep['smswitch']['loopfade'], 16) - s
    assert int(rep['smswitch']['loopfade'], 16) == s and d > 0
    stock = {FS.NOTE_AT: FS.NOTE_OLD[0], FS.NOTE_AT + 1: FS.NOTE_OLD[1], FS.OFF_AT: FS.OFF_OLD[0], FS.OFF_AT + 1: FS.OFF_OLD[1]}
    top = max(base)
    out = {}
    for a, w in base.items():
        if s <= a < s + d:
            continue
        if a in stock:
            w = stock[a]
        elif s + d <= (w & 0xFFFF) <= top and (w >> 16) in (0x0, 0xC, 0xD):     # an address into the moved code
            w -= d
        elif s + d <= (w & 0xFFF) <= top and (w >> 16) in (0xE, 0xF):          # Jcc / JScc with a 12-bit address
            w -= d
        out[a if a < s else a - d] = w
    return out
