"""A0177 wrapper argument/return/ABI and read-only ring-buffer checks."""
import json
import struct
import sys
from pathlib import Path
from emu_playfix import machine, call, STACK
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import *

ROOT=Path(__file__).resolve().parents[1]


def main():
    folder=ROOT/'firmware/a0177'
    man=json.loads((folder/'manifest.json').read_text())['report']
    probe=man['projectprobe']
    slot=int(probe['slot'],16)
    block=int(man['rhstate']['block'],16)
    u=machine((folder/'rhythmplus-A0177.bin').read_bytes(),
              (ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes(),mclass=True)
    labels={k:int(v,16) for k,v in probe['labels'].items()}
    tramp={k:int(v,16) for k,v in probe['trampolines'].items()}
    item,session,buffer=0x20004000,0x20004100,0x20005000
    u.mem_write(item,struct.pack('<3I',2,17,3))
    u.mem_write(session+0x14,struct.pack('<I',buffer))
    seen=[]
    def skip(uc,address,size,data):
        args=[uc.reg_read(UC_ARM_REG_R0+i) for i in range(4)]
        sp=uc.reg_read(UC_ARM_REG_SP)
        args+=list(struct.unpack('<2I',uc.mem_read(sp,8)))
        seen.append((address,args))
        uc.reg_write(UC_ARM_REG_R0,0x12345678)
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    for address in tramp.values():u.hook_add(UC_HOOK_CODE,skip,None,address,address+1)
    def invoke(name,args):
        # call() fixes SP and checks all callee-saved registers.
        extras=list(args[4:])+[0,0]
        u.mem_write(STACK+0xf0000,struct.pack('<2I',*extras[:2]))
        call(u,labels['c_pp_'+name],*args[:4])
        return u.reg_read(UC_ARM_REG_R0)
    cases=[('load',[session,item,0,buffer,0x29484]),
           ('apply',[session,0,23,24]),
           ('save',[session,item,0,buffer,0x29484,0x20003000]),
           ('done',[item,7,3,buffer,16,session])]
    for name,args in cases:
        assert invoke(name,args)==0x12345678
        assert seen[-1][1][:len(args)]==args,(name,seen[-1])
    header=struct.unpack('<8I',u.mem_read(slot,32))
    assert header[:6]==(0x31505052,7,1,1,1,1),header
    events=[struct.unpack('<8I',u.mem_read(slot+32+i*32,32)) for i in range(7)]
    assert [e[2] for e in events]==list(range(1,8))
    assert events[-1][5:7]==(3,16)
    print('PASS all four wrappers preserve arguments, returns, stack and callee-saved registers')
    print('PASS load/apply/save/completion events retain destination, error and transferred count')
    writes=[]
    def written(uc,access,address,size,value,data):writes.append((address,size))
    u.hook_add(UC_HOOK_MEM_WRITE,written)
    for i in range(40):invoke('load',cases[0][1])
    total=struct.unpack('<I',u.mem_read(slot+4,4))[0]
    events=[struct.unpack('<8I',u.mem_read(slot+32+i*32,32)) for i in range(32)]
    assert total==87 and sorted(e[0] for e in events)==list(range(56,88))
    assert all(block<=a and a+n<=block+man['rhstate']['size'] or
               STACK<=a and a+n<=STACK+0x100000 for a,n in writes),writes[:5]
    print('PASS ring wraps within reserved RAM without modifying project or other stock data')
    # Non-project reads are forwarded without recording an event.
    u.mem_write(item,struct.pack('<I',3))
    invoke('load',cases[0][1])
    assert struct.unpack('<I',u.mem_read(slot+4,4))[0]==87
    print('PASS non-project storage operations are forwarded without logging')
    u.mem_write(item,struct.pack('<I',2))
    for mask in (0,1):
        u.reg_write(UC_ARM_REG_PRIMASK,mask)
        invoke('load',cases[0][1])
        assert u.reg_read(UC_ARM_REG_PRIMASK)==mask
    print('PASS prior interrupt-mask state is preserved, including already-masked callers')
    u.reg_write(UC_ARM_REG_PRIMASK,0)
    replies=[]
    def router(uc,address,size,data):
        ptr=uc.reg_read(UC_ARM_REG_R2)
        buf,length=struct.unpack('<2I',uc.mem_read(ptr,8))
        replies.append(bytes(uc.mem_read(buf,length)))
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,router,None,0x080298b8,0x080298b9)
    msg=bytearray(232)
    msg[:6]=bytes([0xf0,0x7d,0x43,0x54,2,7])
    msg[6:14]=bytes((slot>>(4*(7-i)))&15 for i in range(8))
    msg[14]=64;msg[-1]=0xf7
    u.mem_write(0x20008000,bytes(msg))
    u.mem_write(0x20007ff0,struct.pack('<2I',0x20008000,232))
    call(u,int(man['rdiag']['labels']['c_rdin'],16),0,0x20007ff0,0)
    assert len(replies)==1 and replies[0][:6]==bytes([0xf0,0x7d,0x43,0x54,0x42,7])
    raw=replies[0]
    assert raw[6:14]==bytes(8) and len(raw)==143
    decoded=bytes(raw[i]*16+raw[i+1] for i in range(14,len(raw)-1,2))
    assert decoded==bytes(u.mem_read(slot,64))
    print('PASS browser-format RAM request reads actual probe bytes through installed SysEx dispatcher')
    u.mem_write(block,bytes(4))
    u.mem_write(0x20002b54,struct.pack('<I',0x2004f760))
    u.mem_write(0x20002b58,struct.pack('<I',block+4))
    before=bytes(u.mem_read(slot,1056))
    assert invoke('load',cases[0][1])==0x12345678
    assert bytes(u.mem_read(slot,1056))==before
    print('PASS unavailable private RAM disables probing while forwarding stock operation')
    print('LIMIT original callees intercepted here; full original storage flow checked separately')
    print('ALL PASS')


if __name__=='__main__':main()
