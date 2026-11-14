"""Common native track lock writer and live recorder suppression."""
from pathlib import Path
import rhbuild
from stepmut import compile_c
from thumb import b_w
ROOT=Path(__file__).resolve().parents[1]
HOOKS=((0x08047d82,'lock'),(0x08049706,'bridge'),(0x080497ec,'tick'))

def install(img,report,base_addr):
    prefix=bytearray();defs={'TM_HELD':int(report['tmenu']['labels']['c_tmheld'],16)}
    heads={}
    for at,name in HOOKS:
        head=bytes(img[at-rhbuild.BASE:at-rhbuild.BASE+4]);heads[name]=head
        ins=list(rhbuild.MD.disasm(head,at))
        assert sum(i.size for i in ins)==4 and all(i.mnemonic in ('push','push.w','mov','movs','sub','sub.w') for i in ins)
        defs['TR_'+name.upper()]=base_addr+len(prefix)
        prefix+=head+b_w(base_addr+len(prefix)+4,at+4)
    code,L=compile_c(base_addr+len(prefix),defs,src=ROOT/'modules/heldlocks.c',name='heldlocks',prefix='c_hl_',
                     need=tuple('c_hl_'+n for _,n in HOOKS),max_code=0x1000)
    img+=b'\xff'*(base_addr-rhbuild.BASE-len(img))+prefix+code
    while len(img)%4:img.append(255)
    for at,name in HOOKS:
        rhbuild.patch(img,at,'|'.join(rhbuild.disasm(heads[name],at)),b_w(at,L['c_hl_'+name]))
    report['heldlocks']=dict(code=len(prefix)+len(code),tracks=8,lanes=12,
        labels={k:hex(v) for k,v in L.items()},trampolines={k:hex(v) for k,v in defs.items() if k.startswith('TR_')})
    return L,code
