"""Local rhdsp adapter: block() also reads the DSP programs of a dsppack image."""
import importlib.util
import sys
from pathlib import Path

_path = Path(__file__).resolve().parents[1] / 'remix/tools/rhdsp.py'
_spec = importlib.util.spec_from_file_location('_rp_upstream_rhdsp', _path)
_upstream = importlib.util.module_from_spec(_spec)
_saved_path = sys.path[:]
try:
    _spec.loader.exec_module(_upstream)
finally:
    sys.path[:] = _saved_path
globals().update({k: v for k, v in vars(_upstream).items() if not k.startswith('_')})
_block = _upstream.block


def block(img, core, mode=0):
    import dsppack
    a = int.from_bytes(img[TABLE - BASE + 4 * (2 * core + mode):][:4], 'little')
    if mode == 0 and dsppack.is_packed(img):
        raw = dsppack.raw_streams(img)[core]
        n, load = int.from_bytes(raw[0:3], 'big'), int.from_bytes(raw[3:6], 'big')
        return a, n, load, raw[6:6 + 3 * n]
    return _block(img, core, mode)


_upstream.block = block
