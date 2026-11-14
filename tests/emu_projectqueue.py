"""Real native queue/credit code plus compiled non-waiting adapter, no disk."""
import struct
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('tools','tests')]
from build_projectfile import build
from emu_playfix import machine,call
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *


def main():
    code,info=build()
    u=machine((ROOT/'remix/stock/circuitrhythm-firmware-5706-STOCK.bin').read_bytes(),
              (ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes(),mclass=True)
    u.mem_write(info['origin'],code)
    service,queue,ring,request,out,message=0x20001000,0x20001100,0x20002000,0x20003000,0x20004000,0x20004100
    payload=bytes(range(72));u.mem_write(request,payload)
    wakes=[];counts={'masked':0,'max':0}
    def hook(uc,address,size,data):
        if uc.reg_read(UC_ARM_REG_PRIMASK):counts['masked']+=1
        else:
            counts['max']=max(counts['max'],counts['masked']);counts['masked']=0
        if address==0x080240c0:
            assert not uc.reg_read(UC_ARM_REG_PRIMASK)
            wakes.append((uc.reg_read(UC_ARM_REG_R0),uc.reg_read(UC_ARM_REG_R1)))
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        if address in (0x0802acb8,0x0802acf8):raise AssertionError('waiting submission path called')
    u.hook_add(UC_HOOK_CODE,hook)
    def invoke(address,*args):
        call(u,address,*args)
        return u.reg_read(UC_ARM_REG_R0)
    def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    def reset(capacity=1024,credits=2):
        wakes.clear()
        u.mem_write(service,bytes(32))
        u.mem_write(service+0x10,bytes([credits,2]))
        u.mem_write(service+0x14,struct.pack('<I',queue))
        u.mem_write(queue,struct.pack('<I4H',ring,capacity,0,0,72))
        u.mem_write(ring,bytes(1024))
        u.reg_write(UC_ARM_REG_PRIMASK,0)
    fn=info['labels']['c_pf_submit']
    reset()
    assert invoke(fn,service,request)==0
    assert bytes(u.mem_read(service+0x10,2))==bytes([1,2])
    assert wakes==[(service,1)]
    u.mem_write(message,struct.pack('<2I',72,out))
    assert invoke(0x08040dee,queue,message)==1
    assert bytes(u.mem_read(out,72))==payload
    assert not u.reg_read(UC_ARM_REG_PRIMASK)
    print('PASS actual native queue copies all 72 bytes; credit is reserved before wake and IRQ mask restored')
    for capacity,credits in ((1024,0),(5,2)):
        reset(capacity,credits)
        before=bytes(u.mem_read(ring,1024))
        for _ in range(5):assert invoke(fn,service,request)==1
        assert bytes(u.mem_read(service+0x10,2))==bytes([credits,2])
        assert bytes(u.mem_read(ring,1024))==before and not wakes
    print('PASS exhausted credits and full queue return busy without waits, lost credit or buffer changes')
    reset()
    u.reg_write(UC_ARM_REG_PRIMASK,1)
    assert invoke(fn,service,request)==1 and u.reg_read(UC_ARM_REG_PRIMASK)==1 and not wakes
    u.reg_write(UC_ARM_REG_PRIMASK,0)
    assert invoke(fn,0,request)==1 and invoke(fn,service,0)==1
    assert counts['max']<5000,counts
    print('PASS masked/invalid callers refused; maximum masked instruction run:',counts['max'])
    print('LIMIT wake/scheduler intercepted; no installed hooks, SD writes or physical clock measurement')
    print('ALL PASS')


if __name__=='__main__':main()
