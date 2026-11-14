"""Execute compiled Cortex-M7 worker with injected file/lease boundaries only."""
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
              (ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes())
    u.mem_write(info['origin'],code)
    job,ops,file,path,buffer=0x20001000,0x20001100,0x20001200,0x20001300,0x20002000
    funcs=[0x08000200+i*4 for i in range(7)]
    u.mem_write(ops,struct.pack('<7I',*(a|1 for a in funcs)))
    u.mem_write(path,b'1:/RP_AUTO/test.rpa\0')
    payload=bytes((i*17)&255 for i in range(4708))
    state={}
    def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    def hook(uc,address,size,data):
        n=funcs.index(address)
        args=[uc.reg_read(UC_ARM_REG_R0+i) for i in range(4)]
        result=0
        if n==0:
            state['locks']+=1
            result=int(state['busy'])
            if not result:
                assert not state['held'];state['held']=True
        elif n==1:
            assert state['held'];state['held']=False;state['unlocks']+=1
        else:
            assert state['held']
            state['events'].append(n)
            fail=len(state['events'])==state['fail']
            result=5 if fail else 0
            if n==2:
                assert args[:2]==[file,path]
                state['mode']=args[2]
                if not fail and args[2]==7 and state['exists']:result=8
                if not result:
                    if args[2]==7:state['disk']=bytearray();state['exists']=True
                    state['position']=0
            elif n in (3,4):
                _,ptr,count,actual=args
                assert count<=512
                done=0 if fail else count-1 if state['short'] else count
                uc.mem_write(actual,struct.pack('<I',done))
                if not result:
                    pos=state['position']
                    if n==3:uc.mem_write(ptr,bytes(state['disk'][pos:pos+done]))
                    else:state['disk'].extend(uc.mem_read(ptr,done))
                    state['position']+=done
        uc.reg_write(UC_ARM_REG_R0,result)
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    for address in funcs:u.hook_add(UC_HOOK_CODE,hook,None,address,address+1)
    def invoke(name,*args):
        call(u,info['labels']['c_pf_'+name],*args)
        return u.reg_read(UC_ARM_REG_R0)
    def reset(write=1,exists=False,fail=0,short=False):
        state.clear();state.update(locks=0,unlocks=0,held=False,busy=False,
            events=[],mode=None,exists=exists,disk=bytearray(payload if exists else b''),
            position=0,fail=fail,short=short)
        u.mem_write(job,struct.pack('<12I',0,file,path,buffer,len(payload),0,write,0,0,0,0,0))
        u.mem_write(buffer,payload if write else bytes(len(payload)))
        assert invoke('begin',job,ops)==0
    def step():
        before=len(state['events'])
        result=invoke('step',job)
        assert len(state['events'])-before<=1
        assert not state['held']
        return result
    def drain():
        for _ in range(30):
            result=step()
            if result in (2,3):return result
        raise AssertionError('worker did not finish')
    reset()
    assert drain()==2 and state['disk']==payload and state['mode']==7
    assert state['events'][-2:]==[5,6] and word(job+20)==len(payload)
    successful_ops=len(state['events'])
    assert state['locks']==state['unlocks']
    print('PASS bounded write chunks, exact payload, exclusive create, sync/close ordering and ABI')
    reset(write=0,exists=True)
    assert drain()==2 and bytes(u.mem_read(buffer,len(payload)))==payload
    assert state['mode']==1 and 5 not in state['events'] and 4 not in state['events']
    print('PASS read-only loading uses private handle and complete payload')
    reset(exists=True)
    assert drain()==3 and state['disk']==payload and state['events']==[2]
    print('PASS existing companion is refused without overwriting it')
    for failure in range(1,successful_ops+1):
        reset(fail=failure)
        assert drain()==3 and word(job+32)!=0
        assert state['locks']==state['unlocks']
        if failure==successful_ops:
            assert word(job+40)==1 and invoke('begin',job,ops)==1
        else:assert word(job+40)==0
    print('PASS failure at every open/write/sync/close operation, cleanup and failed-close ownership')
    for write in (0,1):
        reset(write=write,exists=not write,short=True)
        assert drain()==3 and word(job+20)==0 and word(job+32)==2
    print('PASS short read/write never advances acknowledged progress or reports success')
    reset();state['busy']=True
    before=bytes(u.mem_read(job,48))
    for _ in range(5):assert step()==1
    assert bytes(u.mem_read(job,48))==before and not state['events'] and state['unlocks']==0
    state['busy']=False
    assert step()==0
    invoke('cancel',job)
    assert drain()==3 and state['events']==[2,6] and word(job+40)==0
    reset();invoke('cancel',job)
    assert drain()==3 and not state['events']
    print('PASS busy lease yields without work; cancellation closes owned file and never starts new I/O')
    print('LIMIT lease/FatFs operations injected; no installed hooks, physical SD or scheduler timing')
    print('ALL PASS')


if __name__=='__main__':main()
