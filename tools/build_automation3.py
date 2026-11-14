"""Compile the private three-control engine for local Cortex-M7 tests."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('modules','builds','tests','remix/tools')]
from stepmut import compile_c
ORIGIN=0x08078000
def build():
    folder=ROOT/'buildtmp/automation3';folder.mkdir(parents=True,exist_ok=True)
    source=folder/'combined.c'
    source.write_bytes((ROOT/'modules/automation3.h').read_bytes()+b'\n'+(ROOT/'modules/automation3.c').read_bytes().replace(b'#include "automation3.h"',b''))
    code,labels=compile_c(ORIGIN,{},src=source,name='automation3',prefix='c_a3_',need=('c_a3_init','c_a3_record','c_a3_value'),max_code=0x1800)
    (folder/'core.bin').write_bytes(code)
    info={'origin':ORIGIN,'bytes':len(code),'labels':labels,'installed':False}
    (folder/'core.json').write_text(json.dumps(info,indent=2))
    return code,info
if __name__=='__main__':print(json.dumps(build()[1],indent=2))
