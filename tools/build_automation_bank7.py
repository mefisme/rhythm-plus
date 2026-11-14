"""Compile the RAM adapter with the actual recording/playback core, uninstalled."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('modules','builds','tests','remix/tools')]
from stepmut import compile_c
def build():
    folder=ROOT/'buildtmp/automation-bank7';folder.mkdir(parents=True,exist_ok=True)
    source=folder/'combined.c'
    names=('automation3.h','automation_codec7.c','automation_cow7.c','automation_bank7.c','automation3.c')
    source.write_bytes(b'\n'.join((ROOT/'modules'/n).read_bytes().replace(b'#include "automation3.h"',b'') for n in names))
    code,labels=compile_c(0x08078000,dict(COW7=1),src=source,name='automation-bank7',prefix='c_a3_',
        need=('c_a3_init','c_a3_record','c_a3_value','c_a3_banksnapshot'),max_code=0x5000)
    return code,dict(origin=0x08078000,bytes=len(code),labels=labels,installed=False)
