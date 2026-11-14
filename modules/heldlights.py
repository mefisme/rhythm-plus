"""Held-step recording pad feedback outside the Track Parameter Editor."""
from pathlib import Path
import rhbuild,tmenu
from stepmut import compile_c
from thumb import bl
ROOT=Path(__file__).resolve().parents[1]

def install(img,report,base_addr):
    previous=rhbuild.bl_target(img,tmenu.OUT_CALL)
    defs=dict(PREV_OUT=previous,TM_HELD=int(report['tmenu']['labels']['c_tmheld'],16),
        TM_SLOT=int(report['tmenu']['slot'],16),MS_SLOT=int(report['mutset']['slot'],16),
        SM_SLOT=int(report['stepmut']['slot'],16))
    code,L=compile_c(base_addr,defs,src=ROOT/'modules/heldlights.c',name='heldlights',prefix='c_hp_',
                     need=('c_hp_out',),max_code=0x1000)
    img+=b'\xff'*(base_addr-rhbuild.BASE-len(img))+code
    while len(img)%4:img.append(255)
    rhbuild.patch(img,tmenu.OUT_CALL,f'bl #{previous:#x}',bl(tmenu.OUT_CALL,L['c_hp_out']))
    report['heldlights']=dict(code=len(code),previous=hex(previous),
        labels={k:hex(v) for k,v in L.items()},visual_only=True)
    return L,code
