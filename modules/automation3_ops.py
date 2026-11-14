"""Extend existing native pattern/step operations and confirmed track reset."""
from pathlib import Path
import os
import rhbuild
from stepmut import compile_c
from thumb import b_w
ROOT=Path(__file__).resolve().parents[1]

def install(img,report,base_addr):
    gx={k:int(v,16) for k,v in report['gfxmix']['labels'].items()}
    hooks=[(0x080479ac,'patternpaste'),(0x08047ad8,'patternclear'),(0x08047820,'steppaste'),
           (0x080478d6,'stepclear'),(int(report['trackreset']['labels']['c_trreset'],16),'trackreset')]
    if os.environ.get('RH_GFX_PAGECOPY')=='1':hooks.append((0x080480de,'pagecopy'))
    defs=dict(GX_FX=gx['c_gx_autofx'],GX_READ=gx['c_gx_smread'],GX_WRITE=gx['c_gx_smwrite'],
        GX_DEFAULTS=gx['c_gx_autodefaults'],CORE_BULK=int(report['automation3']['labels']['c_a3_bulk'],16),
        CORE_MANUAL=int(report['automation3']['labels']['c_a3_manual'],16),
        AUTO_READY=int(report['automation3']['labels']['c_a3_available'],16))
    defs['CORE_STATE']=int(report['automation3']['state'],16)
    if os.environ.get('RH_AUTOMATION_TASK_GUARD')=='1':defs['TASK_GUARD']=1
    prefix=bytearray();heads={}
    for at,name in hooks:
        head=bytes(img[at-rhbuild.BASE:at-rhbuild.BASE+4]);heads[name]=head
        ins=list(rhbuild.MD.disasm(head,at))
        assert sum(i.size for i in ins)==4 and all(i.mnemonic in ('push','push.w','mov','movs','sub','sub.w') for i in ins)
        defs['TR_'+name.upper()]=base_addr+len(prefix)
        prefix+=head+b_w(base_addr+len(prefix)+4,at+4)
    code,L=compile_c(base_addr+len(prefix),defs,src=ROOT/'modules/automation3_ops.c',name='automation3-ops',prefix='c_ao_',
        need=tuple('c_ao_'+n for _,n in hooks)+('c_ao_trackclear',),max_code=0x2000)
    img+=b'\xff'*(base_addr-rhbuild.BASE-len(img))+prefix+code
    while len(img)%4:img.append(255)
    for at,name in hooks:rhbuild.patch(img,at,'|'.join(rhbuild.disasm(heads[name],at)),b_w(at,L['c_ao_'+name]))
    rhbuild.patch(img,gx['c_gx_autotrackclear'],'movs r0, #0|bx lr',b_w(gx['c_gx_autotrackclear'],L['c_ao_trackclear']))
    report['automation3_ops']=dict(code=len(code)+len(prefix),labels={k:hex(v) for k,v in L.items()},
        trampolines={k:hex(v) for k,v in defs.items() if k.startswith('TR_')},clipboard_bytes=0)
    return L,code
