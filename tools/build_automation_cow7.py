"""Compile adaptive lane pool / RAM-only shared save snapshot proof."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('modules','builds','tests','remix/tools')]
from stepmut import compile_c
def build():
    folder=ROOT/'buildtmp/automation-cow7';folder.mkdir(parents=True,exist_ok=True)
    src=folder/'combined.c'
    src.write_bytes((ROOT/'modules/automation_codec7.c').read_bytes()+b'\n'+(ROOT/'modules/automation_cow7.c').read_bytes())
    code,L=compile_c(0x08078000,{},src=src,name='automation-cow7',prefix='c_cp_',
        need=('c_cp_init','c_cp_set','c_cp_read','c_cp_snapshot','c_cp_release','c_cp_valid'),max_code=0x3000)
    return code,dict(origin=0x08078000,bytes=len(code),labels=L,installed=False,metadata_bytes=456,max_data_bytes=9216)
if __name__=='__main__':print(json.dumps(build()[1],indent=2))
