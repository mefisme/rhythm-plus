"""Private RAM engine versus actual 5706 playback/recording instructions.

Only provider/store/sink boundaries are mocked. No native automation is borrowed.
"""
import random, struct, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('tools','tests')]
if '--cow' in sys.argv:
    from build_automation_bank7 import build
else:
    from build_automation3 import build
from emu_playfix import machine,call,STACK
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *

def main():
    code,info=build()
    u=machine((ROOT/'remix/stock/circuitrhythm-firmware-5706-STOCK.bin').read_bytes(),
              (ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes(),mclass='--cow' in sys.argv)
    u.mem_write(info['origin'],code)
    cow='--cow' in sys.argv
    state,bank=0x3d40 if cow else 0x3a00,0x1500
    def w(a,v):u.mem_write(a,struct.pack('<I',v))
    def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    def run(name,*args):
        if len(args)>4:u.mem_write(STACK+0xf0000,struct.pack('<'+'I'*(len(args)-4),*args[4:]))
        call(u,info['labels']['c_a3_'+name],*args[:4])
        return u.reg_read(UC_ARM_REG_R0)
    def writebank(lane,raw):
        if cow:
            u.mem_write(0x20007000,raw)
            assert run('bankimport',lane,0x20007000,192,1)==0
        else:u.mem_write(bank+lane*192,raw)
    def readbank(lane):
        if cow:
            assert run('bankread',lane,0x20007000)==0
            return bytes(u.mem_read(0x20007000,192))
        return bytes(u.mem_read(bank+lane*192,192))
    def ret(v=0):u.reg_write(UC_ARM_REG_R0,v);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    obj,vt,sink,provider,put=0x800,0x900,0xa00,0x08000180,0x08000190
    stores={};events=[];lanes={p:0x20003000+p*192 for p in range(8)}
    w(vt+0x14,provider|1);w(sink,vt+0x40);w(vt+0x40,put|1);w(obj,vt);w(obj+0x2c,sink)
    for i,off in enumerate([0xc,0x10,0x30,0x34,0x38]):
        st=0xb00+i*0x40;stores[st]=st+0x20;w(obj+off,st);w(st+0x20,0);w(st+0x24,0)
    w(stores[word(obj+0x30)],1);u.mem_write(obj+0x3c,b'\x01')
    w(obj+0x40,0xd00);w(0xd00,0x200);w(obj+0x44,0xff00);w(obj+0x48,0xd10);w(obj+0x4c,0xd14)
    rate=[0];robj,rvt,ratehook=0xe00,0xe80,0x080001a0
    w(robj,rvt);w(rvt+8,ratehook|1);w(rvt+0x1c,provider|1)
    w(robj+0xc,word(obj+0xc));w(robj+0x38,0xf00);w(robj+0x3c,0xf10)
    def hook(uc,a,n,d):
        x,y,z=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
        if a==0x803fc58:
            if x in stores:ret(stores[x]+y*4)
        elif a==provider:ret(lanes[z if x==robj else y])
        elif a==put:events.append(z);ret()
        elif a==ratehook:ret(rate[0])
    for a in (0x803fc58,provider,put,ratehook):u.hook_add(UC_HOOK_CODE,hook,None,a,a+1)
    record=word(0x2003c0cc);native=bytes(u.mem_read(record,0x29484))
    rng=random.Random(180);checks=0
    for trial in range(3):
        run('init',state,bank)
        for p in range(8):
            vals=bytes(255 if rng.random()<.5 else rng.randrange(128) for _ in range(192))
            u.mem_write(lanes[p],vals);writebank(p,vals)
        schedule=[(p,s) for p in (0,7,3,0) for s in (0,1,15,16,30,31)]
        for rate[0],length in enumerate((2,3,4,6,8,12,16,24)):
            run('reset',state);u.mem_write(0xd10,b'\xff\xff');u.mem_write(0xd14,b'\xff\xff')
            # Reset output as well so differential comparison starts absent.
            u.mem_write(state+36,b'\xff\xff')
            expected=65535
            w(stores[word(obj+0x10)]+4,rate[0])
            for i,(p,step) in enumerate(schedule):
                np,ns=schedule[(i+1)%len(schedule)]
                w(stores[word(obj+0xc)],np);w(stores[word(obj+0xc)]+4,ns)
                nv=u.mem_read(lanes[np]+ns*6,1)[0];nv=65535 if nv==255 else nv
                for pulse in range(length):
                    events.clear();call(u,0x8055324,obj,p,step,pulse)
                    actual=run('value',state,bank,0,p,step,pulse,rate[0],nv)
                    if events:expected=events[-1]
                    assert actual==expected,('play',trial,rate[0],p,step,pulse,actual,expected)
                    assert u.mem_read(state+24,2)==u.mem_read(0xd10,2),('held',rate[0],step,pulse)
                    checks+=1
    print(f'PASS {checks} playback positions match native across eight rates and pattern changes')
    checks=0
    for rate[0],length in enumerate((2,3,4,6,8,12,16,24)):
        run('init',state,bank);w(0xf00,0);u.mem_write(0xf10,b'\xff')
        vals=bytes(rng.randrange(128) for _ in range(192))
        for p in (0,7):u.mem_write(lanes[p],vals);writebank(p,vals)
        run('manual',state,0,64,1)
        for tick in range(length*96):
            step=(tick//length)%32;pulse=tick%length;p=7 if tick//length//32==1 else 0
            w(stores[word(obj+0xc)],p);w(stores[word(obj+0xc)]+4,step)
            v=rng.randrange(128) if tick%7==0 else 255
            if v!=255:run('manual',state,0,v,1)
            call(u,0x8049706,robj,0,v,0);call(u,0x80497ec,robj,0,pulse,v)
            run('record',state,bank,p,step,pulse,rate[0])
            for checkp in (0,7):
                assert readbank(checkp)==u.mem_read(lanes[checkp],192),('record',rate[0],p,step,pulse,checkp)
            checks+=1
    print(f'PASS {checks} recording ticks including empty overdubs match native')
    run('init',state,bank)
    assert run('lock',state,bank,2,7,31,127)==0
    expected=bytearray(b'\xff'*4608);expected[-6]=127
    assert b''.join(readbank(p) for p in range(24))==expected
    assert run('lock',state,bank,3,7,31,12)==1
    assert run('clear',state,bank,2,7,31)==0
    assert b''.join(readbank(p) for p in range(24))==b'\xff'*4608
    # A frozen snapshot remains independent of edits to the active bank.
    if cow:
        assert run('banksnapshot')==0
        run('lock',state,bank,1,0,0,0)
        # Detailed frozen-view checks are in emu_automation_bank7.py.
        run('bankrelease')
    else:
        u.mem_write(0x27a0,bytes(u.mem_read(bank,4608)));run('lock',state,bank,1,0,0,0)
        assert u.mem_read(0x27a0,4608)==b'\xff'*4608
    assert u.mem_read(record,0x29484)==native
    print('PASS lock/Clear isolation, bounds, snapshot independence, and whole native project preservation')

if __name__=='__main__':main()
