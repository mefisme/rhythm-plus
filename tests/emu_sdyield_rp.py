"""A0178 SD wait-loop port: execute emitted ARM, intercept loop/exit only."""
import json
import struct
import sys
from pathlib import Path
from emu_playfix import machine,STACK,SENT
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1]


def main():
    build=sys.argv[1] if len(sys.argv)>1 else 'a0178'
    rep=json.loads((ROOT/'firmware'/build/'manifest.json').read_text())['report']
    block=int(rep['sdyield']['block'],16)
    slot=int(rep['storageshadow']['slot'],16)
    fn=int(rep['sdyield']['labels']['c_sdy'],16)
    u=machine((ROOT/'firmware'/build/f'rhythmplus-{build.upper()}.bin').read_bytes(),
              (ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes())
    driver=0x20007000;targets=[];yields=[]
    def w(a,v):u.mem_write(a,struct.pack('<I',v))
    def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    def branch(uc,a,size,data):
        targets.append(a);uc.reg_write(UC_ARM_REG_PC,SENT)
    def written(uc,access,a,size,value,data):
        if a==0xe000ed04:yields.append(value)
    for a in (0x08023864,0x08023886):u.hook_add(UC_HOOK_CODE,branch,None,a,a+1)
    u.hook_add(UC_HOOK_MEM_WRITE,written)
    def step(now,state=1,scheduler=1):
        w(0x20000820,now);w(driver+0x40,state);u.mem_write(0x20006f55,bytes([scheduler]))
        u.reg_write(UC_ARM_REG_R4,driver);u.reg_write(UC_ARM_REG_SP,STACK+0xf0000)
        u.emu_start(fn|1,SENT,count=500)
        assert u.reg_read(UC_ARM_REG_PC)==SENT and u.reg_read(UC_ARM_REG_R4)==driver
        assert u.reg_read(UC_ARM_REG_SP)==STACK+0xf0000
        return targets[-1]
    w(slot,0)
    assert step(0)==0x08023864 and step(1,0)==0x08023886 and not yields
    w(slot,0x31464f53 if rep['storageshadow'].get('offload') else 0x31534852);u.mem_write(block,bytes(20))
    assert step(100)==0x08023864
    step(101);assert not yields
    step(102);assert yields==[0x10000000]
    step(103,scheduler=0);assert len(yields)==1
    assert step(105,state=0)==0x08023886
    assert [word(block+i) for i in (0,8,12,16)]==[0,1,5,1]
    step(106,state=0);assert word(block+8)==1
    print('PASS early/missing RAM and short waits retain stock branch; >=2ms waits yield only with scheduler running')
    print('PASS finished waits clear ownership and update duration/yield counters exactly once')
    u.mem_write(block,bytes(20));yields.clear()
    step(0xfffffffe);step(1);step(2,state=0)
    assert yields==[0x10000000] and word(block+12)==4
    print('PASS unsigned tick wrap and driver/stack preservation')
    print('LIMIT PendSV execution/scheduler intercepted; physical audio/clock continuity requires hardware test')
    print('ALL PASS')


if __name__=='__main__':main()
