"""Local rhdsp1 adapter: words() also reads core 1's block of a dsppack image."""
import importlib.util
import sys
from pathlib import Path

_path = Path(__file__).resolve().parents[1] / 'remix/tools/rhdsp1.py'
_spec = importlib.util.spec_from_file_location('_rp_upstream_rhdsp1', _path)
_upstream = importlib.util.module_from_spec(_spec)
_saved_path = sys.path[:]
try:
    _spec.loader.exec_module(_upstream)
finally:
    sys.path[:] = _saved_path
globals().update({k: v for k, v in vars(_upstream).items() if not k.startswith('_')})
_words, _where = _upstream.words, _upstream.where


def words(img, blk=BLK1):
    import dsppack
    if blk == BLK1 and dsppack.is_packed(img):
        raw = dsppack.raw_streams(img)[1]
        n = int.from_bytes(raw[0:3], 'big')
        return n, [int.from_bytes(raw[6 + 3 * i:9 + 3 * i], 'big') for i in range(n)]
    return _words(img, blk)


def where(img, paddr):
    import dsppack
    assert not dsppack.is_packed(img), 'core 1 is packed: its words have no flash address'
    return _where(img, paddr)


_upstream.words = words
_upstream.where = where
