"""Actual ARM bounded capture FIFO, epoch isolation and publication ordering."""
from collections import deque
from pathlib import Path
import random
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_automation_core import build
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *


def main():
    info=build();u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);origin=info['origin']
    u.mem_map(origin,0x2000)
    u.mem_write(origin,(ROOT/'buildtmp/automation-core/kernel.bin').read_bytes())
    u.mem_map(0x20000000,0x10000)
    runtime,out,stack,stop=0x20001000,0x20004000,0x2000ff00,origin+0x1ff0
    capture=runtime+6144;control=runtime+8064
    epoch,head,tail=control+4,control+16,control+20
    writes=[]
    def monitor(uc,access,address,size,value,data):
        if stack-1024<=address and address+size<=stack:return
        assert (capture<=address and address+size<=capture+1024 or
                address in (head,tail) and size==4 or out<=address and address+size<=out+8)
        writes.append((address,size))
    u.hook_add(UC_HOOK_MEM_WRITE,monitor)
    def w(a,v):u.mem_write(a,struct.pack('<I',v))
    def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    def raw():return bytes(u.mem_read(runtime,8192))
    def call(name,*args):
        writes.clear()
        for i,v in enumerate(args):u.reg_write(UC_ARM_REG_R0+i,v)
        for i in range(8):u.reg_write(UC_ARM_REG_R4+i,0x5170+i)
        u.reg_write(UC_ARM_REG_SP,stack);u.reg_write(UC_ARM_REG_LR,stop|1)
        u.emu_start(info['labels'][name]|1,stop,count=10000)
        assert u.reg_read(UC_ARM_REG_PC)==stop and u.reg_read(UC_ARM_REG_SP)==stack
        assert [u.reg_read(UC_ARM_REG_R4+i) for i in range(8)]==list(range(0x5170,0x5178))
        return u.reg_read(UC_ARM_REG_R0)
    def push(event,context):
        result=call('c_ap_capture_push',runtime,event,context)
        if result==0:
            assert writes[-1]==(head,4)
            assert all(capture<=a<capture+1024 for a,n in writes[:-1])
        else:assert not writes
        return result
    def pop():
        u.mem_write(out,b'\xa5'*8)
        result=call('c_ap_capture_pop',runtime,out)
        if result in (0,4) or result==3 and writes:
            assert writes[-1]==(tail,4)
        else:assert not writes
        if result:assert bytes(u.mem_read(out,8))==b'\xa5'*8
        return result,struct.unpack('<II',bytes(u.mem_read(out,8)))
    w(epoch,1);w(head,0xffffffc0);w(tail,0xffffffc0)
    assert pop()[0]==1
    for i in range(128):assert push(i%192|((i%64)<<8)|((i%16384)<<14),64+i%64)==0
    before=raw();assert push(0,64)==2 and raw()==before
    for i in range(128):
        assert pop()==(0,(i%192|((i%64)<<8)|((i%16384)<<14),64+i%64))
    assert word(head)==64 and word(tail)==64 and pop()[0]==1
    print('PASS all128 slots usable, full/empty safe, FIFO preserved across32bit counter wrap')
    rng=random.Random(128);expected=deque()
    for _ in range(5000):
        if rng.randrange(2):
            event=rng.randrange(192)|(rng.randrange(64)<<8)|(rng.randrange(16384)<<14)
            context=64+rng.randrange(64)
            result=push(event,context)
            assert result==(2 if len(expected)==128 else 0)
            if not result:expected.append((event,context))
        else:
            result,pair=pop();assert result==(0 if expected else 1)
            if not result:assert pair==expected.popleft()
    while expected:assert pop()==(0,expected.popleft())
    print('PASS5,000 randomized operations preserve value, destination, pattern and order')
    for event,context in ((192,64),(1<<30,64),(2<<28,64),((1<<28)|1,64),(0,0),(0,128)):
        before=raw();assert push(event,context)==3 and raw()==before
    assert push((1<<28)|6,127)==0 # Valid lock at step boundary, last pattern.
    w(epoch,2);assert pop()[0]==4 # Project switch cannot emit an old command.
    assert push(0,128)==0
    w(capture+(word(tail)&127)*8,1<<30)
    assert pop()[0]==3 and word(head)==word(tail) # Bad entry consumed once.
    w(head,(word(tail)+129)&0xffffffff)
    before=raw();assert push(0,128)==3 and pop()[0]==3 and raw()==before
    print('PASS malformed/stale contexts cannot emit; corrupt counters reject without writes')
    print('PASS payload writes precede head publication; output consumption precedes tail release')
    print('LIMIT: SPSC calls serialized in emulation; IRQ/task ownership and real-time draining unproved')
    print('ALL PASS')


if __name__=='__main__':main()
