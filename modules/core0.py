"""Local core-0 adapter; historical builds retain the upstream upload verbatim.

Compressed images expose their decoded program to analysis tools, while their
actual ARM decoder/upload path is tested independently.
"""
import importlib.util
import os
import sys
from pathlib import Path

_path = Path(__file__).resolve().parents[1] / 'remix/tools/core0.py'
_spec = importlib.util.spec_from_file_location('_rp_upstream_core0', _path)
_upstream = importlib.util.module_from_spec(_spec)
_saved_path = sys.path[:]
try:
    _spec.loader.exec_module(_upstream)
finally:
    sys.path[:] = _saved_path
globals().update({k:v for k,v in vars(_upstream).items() if not k.startswith('_')})

def install(img, report, base_addr, **kwargs):
    if os.environ.get('RH_DSPZIP') == '1':
        import dspzip
        return dspzip.install(img, report, base_addr, **kwargs)
    return _upstream.install(img, report, base_addr, **kwargs)

def block_words(img):
    import dspzip
    if dspzip.is_packed(img):
        raw = dspzip.raw_stream(img)
        n = int.from_bytes(raw[:3], 'big')
        return n, int.from_bytes(raw[3:6], 'big'), [int.from_bytes(raw[i:i+3], 'big') for i in range(6, 6+3*n, 3)]
    return _upstream.block_words(img)

def sent(img, report):
    if report.get('dspzip'):
        import dspzip
        p = report['dspzip']; at = int(p['loader'],16)-BASE
        n = int.from_bytes(img[at:at+3],'big')
        loader = [int.from_bytes(img[i:i+3],'big') for i in range(at,at+3*(n+2),3)]
        raw = dspzip.raw_stream(img)
        return loader, [int.from_bytes(raw[i:i+3],'big') for i in range(0,len(raw),3)]
    return _upstream.sent(img, report)
