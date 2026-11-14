"""Compile private worker for Cortex-M7 emulation only; no firmware hooks."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('modules','builds','tests','remix/tools')]
from stepmut import compile_c
ORIGIN=0x08078000


def build():
    code,labels=compile_c(ORIGIN,{},src=ROOT/'modules/projectfile.c',name='projectfile',
                          prefix='c_pf_',need=('c_pf_begin','c_pf_step','c_pf_cancel','c_pf_submit','c_pf_dma'),max_code=0x1000)
    folder=ROOT/'buildtmp/projectfile'
    (folder/'worker.bin').write_bytes(code)
    info={'origin':ORIGIN,'bytes':len(code),'labels':labels,'installed':False}
    (folder/'worker.json').write_text(json.dumps(info,indent=2))
    return code,info


if __name__=='__main__':print(json.dumps(build()[1],indent=2))
