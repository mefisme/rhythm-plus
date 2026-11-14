"""Three independent lanes: native timing callbacks, owned ITCM bank only."""
from pathlib import Path
import os
import rhbuild
from stepmut import compile_c
from thumb import b_w,bl
ROOT=Path(__file__).resolve().parents[1]

def install(img,report,base_addr,cow=False):
    gx={k:int(v,16) for k,v in report['gfxmix']['labels'].items()}
    reset=0x080552f6
    old=bytes(img[reset-rhbuild.BASE:reset-rhbuild.BASE+4])
    assert all(x.split(' ')[0] in ('push','push.w','mov','movs') for x in rhbuild.disasm(old,reset))
    prefix=old+b_w(base_addr+4,reset+4)
    defs=dict(RESET_TRAMP=base_addr,GX_FX=gx['c_gx_autofx'],
              TM_HELD=int(report['tmenu']['labels']['c_tmheld'],16))
    if cow:defs['COW7']=1
    if os.environ.get('RH_AUTOMATION_TASK_GUARD')=='1':defs['TASK_GUARD']=1
    folder=ROOT/'buildtmp/automation3-runtime';folder.mkdir(parents=True,exist_ok=True)
    src=folder/'combined.c'
    adapters=b'\n'.join((ROOT/'modules'/n).read_bytes() for n in
        ('automation_codec7.c','automation_cow7.c','automation_bank7.c')) if cow else b''
    src.write_bytes((ROOT/'modules/automation3.h').read_bytes()+b'\n'+adapters+b'\n'+
        (ROOT/'modules/automation3.c').read_bytes().replace(b'#include "automation3.h"',b'')+b'\n'+
        (ROOT/'modules/automation3_runtime.c').read_bytes())
    code,L=compile_c(base_addr+len(prefix),defs,src=src,name='automation3-runtime',prefix='c_a3_',
        need=('c_a3_available','c_a3_play','c_a3_listener','c_a3_playerreset','c_a3_touch'),max_code=0x4000)
    img+=b'\xff'*(base_addr-rhbuild.BASE-len(img))+prefix+code
    while len(img)%4:img.append(255)
    rhbuild.patch(img,reset,'|'.join(rhbuild.disasm(old,reset)),b_w(reset,L['c_a3_playerreset']))
    rhbuild.patch(img,0x080552ac,'bl #0x8055324',bl(0x080552ac,L['c_a3_play']))
    rhbuild.patch_word(img,0x08067894,0x0804946d,L['c_a3_listener']|1)
    rhbuild.patch(img,gx['c_gx_autotouch'],'movs r0, #0|bx lr',b_w(gx['c_gx_autotouch'],L['c_a3_touch']))
    rhbuild.patch(img,gx['c_gx_autovalue'],'mov r0, r1|bx lr',b_w(gx['c_gx_autovalue'],L['c_a3_controlvalue']))
    if 'c_gx_autored' in gx:
        rhbuild.patch(img,gx['c_gx_autored'],'movs r0, #0|bx lr',b_w(gx['c_gx_autored'],L['c_a3_red']))
        rhbuild.patch(img,gx['c_gx_autodisplay'],'mov r0, r1|bx lr',b_w(gx['c_gx_autodisplay'],L['c_a3_display']))
    report['automation3']=dict(code=len(code)+len(prefix),active=hex(0x1500),active_bytes=4608,
        snapshot=hex(0x2720),snapshot_bytes=4736,state=hex(0x3a00),state_bytes=128,
        controls=3,patterns=8,steps=32,microsteps=6,sd_packs_only=True,native_lanes_used=[],
        labels={k:hex(v) for k,v in L.items()},trampoline=hex(base_addr))
    if cow:report['automation3'].update(cow=True,active_bytes=456,state=hex(0x3d40),snapshot=None,snapshot_bytes=0,
        pool=hex(0x16e0),pool_bytes=9216,cache=hex(0x3b00),cache_bytes=576,io=hex(0x3de0),io_bytes=512)
    if defs.get('TASK_GUARD'):report['automation3']['task_guard']='basepri-0xc0'
    return L,code
