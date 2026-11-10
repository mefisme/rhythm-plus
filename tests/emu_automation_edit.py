"""Actual ARM in-place staged step edits against independent host Bank semantics."""
from pathlib import Path
import random
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_automation_core import build
from automation_model import Bank,Event,NUMERIC
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *


def main():
    info=build();u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);origin=info['origin']
    u.mem_map(origin,0x2000)
    u.mem_write(origin,(ROOT/'buildtmp/automation-core/kernel.bin').read_bytes())
    u.mem_map(0x20000000,0x10000)
    events,desc,request,allow,stack,stop=0x20001000,0x20002000,0x20002100,0x20002200,0x2000ff00,origin+0x1ff0
    low=[stack]
    def monitor(uc,access,address,size,value,data):
        if stack-2048<=address and address+size<=stack:
            low[0]=min(low[0],address);return
        assert (events<=address and address+size<=events+1536 or
                desc<=address and address+size<=desc+24)
    u.hook_add(UC_HOOK_MEM_WRITE,monitor)
    mask=sum(1<<d for d in NUMERIC);u.mem_write(allow,struct.pack('<II',mask&0xffffffff,mask>>32))
    def stage(bank):
        p=bank.patterns[0];words=[e.word() for e in sorted(p.events.values())]
        u.mem_write(events,struct.pack('<384I',*(words+[0xa5a5a5a5]*(384-len(words)))))
        c,l=sorted(p.continuous),sorted(p.locks)
        data=struct.pack('<HHHBB2s8sHI',65535,65535,len(words),(len(words)+23)//24,0,
                         bytes(c).ljust(2,b'\xff'),bytes(l).ljust(8,b'\xff'),0,0)
        u.mem_write(desc,data)
    def perform(step,kind,taken,points):
        words=[e.word() for e in sorted(points)]
        mask=sum(1<<d for d in taken)
        u.mem_write(request,struct.pack('<17I',step,kind,mask&0xffffffff,mask>>32,len(words),
                                       *(words+[0]*(12-len(words)))))
        before=bytes(u.mem_read(events,1536))+bytes(u.mem_read(desc,24))
        for i,v in enumerate((events,desc,request,allow)):u.reg_write(UC_ARM_REG_R0+i,v)
        for i in range(8):u.reg_write(UC_ARM_REG_R4+i,0x8150+i)
        u.reg_write(UC_ARM_REG_SP,stack);u.reg_write(UC_ARM_REG_LR,stop|1)
        u.emu_start(info['labels']['c_ap_edit_step']|1,stop,count=200000)
        assert u.reg_read(UC_ARM_REG_PC)==stop and u.reg_read(UC_ARM_REG_SP)==stack
        assert [u.reg_read(UC_ARM_REG_R4+i) for i in range(8)]==list(range(0x8150,0x8158))
        result=u.reg_read(UC_ARM_REG_R0)
        if result:assert bytes(u.mem_read(events,1536))+bytes(u.mem_read(desc,24))==before
        return result
    def verify(bank):
        p=bank.patterns[0];count=struct.unpack('<H',bytes(u.mem_read(desc+4,2)))[0]
        assert count==len(p.events)
        assert list(struct.unpack('<'+'I'*count,bytes(u.mem_read(events,count*4))))==[e.word() for e in sorted(p.events.values())]
        c=bytes(u.mem_read(desc+8,2));l=bytes(u.mem_read(desc+10,8))
        assert c==bytes(sorted(p.continuous)).ljust(2,b'\xff')
        assert l==bytes(sorted(p.locks)).ljust(8,b'\xff')
    rng=random.Random(384);bank=Bank();success=0;rejected=0
    destinations=sorted(NUMERIC)
    for _ in range(3000):
        stage(bank);step=rng.randrange(32);kind=rng.randrange(2)
        taken=set(rng.sample(destinations,rng.randrange(4)))
        if kind:
            values={d:rng.randrange(16384) if rng.randrange(3) else None for d in taken}
            points=[Event(step*6,d,v,1) for d,v in values.items() if v is not None]
            operation=lambda:bank.lock_step(0,step,values)
        else:
            values={(d,m):rng.randrange(16384) for d in taken for m in range(6) if rng.randrange(3)==0}
            points=[Event(step*6+m,d,v) for (d,m),v in values.items()]
            operation=lambda:bank.record_step(0,step,taken,values)
        try:operation();expected=True
        except ValueError:expected=False
        result=perform(step,kind,taken,points)
        assert (result==0)==expected,(step,kind,taken,result)
        if expected:verify(bank);success+=1
        else:rejected+=1
    print(f'PASS3,000 ARM step edits match host: {success} accepted, {rejected} atomically rejected')
    # Fully dense pattern: replacement must reclaim taken points before capacity check.
    bank=Bank()
    for step in range(32):bank.record_step(0,step,{0,1},{(d,m):100+d+m for d in (0,1) for m in range(6)})
    stage(bank);points=[Event(12+m,d,8000+d+m) for d in (0,1) for m in range(6)]
    assert perform(2,0,{0,1},points)==0
    bank.record_step(0,2,{0,1},{(d,m):8000+d+m for d in (0,1) for m in range(6)})
    verify(bank);stage(bank)
    assert perform(2,1,{2},[Event(12,2,16383,1)])==1
    # Valid source, invalid caller step and cross-mode request.
    assert perform(32,0,{0},[])==4
    assert perform(2,1,{0},[])==4
    # Damaged source rejects before touching any part of the staged pattern.
    u.mem_write(events,struct.pack('<I',1<<30))
    assert perform(2,0,{0},[])==2
    print('PASS full-pattern replacement, capacity rejection, mode conflict and source corruption are atomic')
    print(f'PASS writes bounded; maximum observed primitive stack use {stack-low[0]}bytes')
    print('LIMIT: staged buffer only; pool admission, DSP writes and live cache publication remain separate')
    print('ALL PASS')


if __name__=='__main__':main()
