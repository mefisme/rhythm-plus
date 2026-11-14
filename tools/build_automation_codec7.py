"""Build the portable Cortex-M7 codec prototype; no firmware installation."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('modules','builds','tests','remix/tools')]
from stepmut import compile_c
def build():
    code,L=compile_c(0x08078000,{},src=ROOT/'modules/automation_codec7.c',name='automation-codec7',
        prefix='c_lc_',need=('c_lc_encode','c_lc_decode'),max_code=0x2000)
    return code,dict(origin=0x08078000,bytes=len(code),labels=L,installed=False)
if __name__=='__main__':print(json.dumps(build()[1],indent=2))
