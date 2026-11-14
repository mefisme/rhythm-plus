"""Exercise real core edits through cache eviction and frozen RAM saves."""
import random,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('tools','tests')]
from build_automation_bank7 import build
from emu_playfix import machine,call,STACK
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_PRIMASK

def main():
    code,info=build()
    u=machine((ROOT/'remix/stock/circuitrhythm-firmware-5706-STOCK.bin').read_bytes(),
              (ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes(),mclass=True)
    u.mem_write(info['origin'],code);state,bank=0x3d40,0x1500
    def run(name,*args):
        if len(args)>4:u.mem_write(STACK+0xf0000,struct.pack('<'+'I'*(len(args)-4),*args[4:]))
        call(u,info['labels']['c_a3_'+name],*args[:4]);return u.reg_read(UC_ARM_REG_R0)
    def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    def read_saved():
        result=[]
        for lane in range(24):
            slot=u.mem_read(bank+44+lane,1)[0]
            if slot==255:result.append(b'\xff'*192);continue
            off,n,refs,kind=struct.unpack('<4H',u.mem_read(bank+68+slot*8,8))
            assert kind==1 and n==192
            result.append(bytes(u.mem_read(0x16e0+off,n)))
        return result
    def check(expected):
        for lane,raw in enumerate(expected):
            for i,v in enumerate(raw):assert run('bankget',bank,lane*192+i)==v,(lane,i)
    rng=random.Random(184);empty=b'\xff'*192
    run('init',state,bank);expected=[bytearray(empty) for _ in range(24)]
    for _ in range(350):
        k,p,step,v=rng.randrange(3),rng.randrange(8),rng.randrange(32),rng.randrange(128)
        assert run('lock',state,bank,k,p,step,v)==0
        expected[k*8+p][step*6:step*6+6]=bytes([v,255,255,255,255,255])
    check(expected)
    assert run('banksnapshot')==0;saved=read_saved();assert saved==expected
    for k in range(3):
        assert run('lock',state,bank,k,7,31,127)==0
        expected[k*8+7][186:192]=bytes([127,255,255,255,255,255])
    assert run('bulk',state,bank,0,7,0,2,0)==0
    for k in range(3):expected[k*8+2]=expected[k*8+7].copy()
    assert run('bulk',state,bank,2,2,31,5,16)==0
    for k in range(3):expected[k*8+5][96:102]=expected[k*8+2][186:192]
    check(expected);assert read_saved()==saved
    assert run('bulk',state,bank,4,0,0,0,0)==0
    check([empty]*24);assert read_saved()==saved
    run('bankrelease');assert word(bank+8)==0
    print('PASS actual core parameter locks, cache evictions, cross-pattern/page Copy and Clear preserve frozen Save')
    # Raw worst case: all event values and holes, then every live lane changes
    # while the entire original bank remains pinned for Save.
    run('init',state,bank)
    expected=[]
    for lane in range(24):
        raw=bytearray(rng.randrange(128) for _ in range(192));raw[17]=255;expected.append(raw)
        for i,v in enumerate(raw):run('bankset',bank,lane*192+i,v)
    assert run('banksnapshot')==0;saved=read_saved();assert saved==expected
    for lane in range(24):
        for i in range(192):
            v=rng.randrange(128);expected[lane][i]=v;run('bankset',bank,lane*192+i,v)
    assert run('bankflush')==0;assert word(bank+8)==9216
    check(expected);assert read_saved()==saved
    run('bankrelease');assert word(bank+8)==4608
    for lane in range(24):assert run('bankcompress',lane)==0
    check(expected)
    print('PASS full-capacity recording during Save retains all 9,216 bytes; post-Save compression preserves every cell')
    assert run('banksnapshot')==0
    settings=bytes(rng.randrange(256) for _ in range(100));u.mem_write(0x20005000,settings)
    size=run('bankfilesize');assert 176<=size<=4784
    def stream(chunk):
        out=bytearray()
        for offset in range(0,size,chunk):
            n=min(chunk,size-offset)
            assert run('bankfile',offset,0x20006000,n,0x20005000)==0
            out.extend(u.mem_read(0x20006000,n))
        return bytes(out)
    frozen=stream(512)
    assert frozen[:28]==struct.pack('<7I',0x33304152,4608,3,8,32,6,0)
    assert frozen[28:128]==settings
    assert stream(1)==frozen and stream(100)==frozen
    # Live edits and compaction between SD chunks cannot alter the saved file.
    assert run('bulk',state,bank,4,0,0,0,0)==0
    for k in range(3):assert run('lock',state,bank,k,4,12,42)==0
    assert run('bankflush')==0;assert stream(37)==frozen
    u.mem_write(0x20006000,b'unchanged')
    assert run('bankfile',size-1,0x20006000,2,0x20005000)==1
    assert bytes(u.mem_read(0x20006000,9))==b'unchanged'
    run('bankrelease');run('init',state,bank)
    descriptors=struct.unpack('<24H',frozen[128:176]);offset=176
    for lane,d in enumerate(descriptors):
        n=d&0x7fff;kind=d>>15;u.mem_write(0x20006000,frozen[offset:offset+n])
        assert run('bankimport',lane,0x20006000,n,kind)==0;offset+=n
    assert offset==len(frozen);check(expected)
    print('PASS RA03 bounded streaming, live edits between chunks, range rejection and complete compressed-file restore')
    # Simulate a live edit after maintenance captured a lane, before its encoded
    # version can publish. A stale prepared encoding must never overwrite it.
    run('bankget',bank,0)
    armed=[False,False]
    def edit(uc,a,n,d):
        if uc.reg_read(UC_ARM_REG_PRIMASK):armed[0]=True
        elif armed[0] and not armed[1]:
            armed[1]=True;uc.mem_write(0x3b00,b'\x31')
            uc.mem_write(state+92,struct.pack('<I',word(state+92)|1))
            uc.mem_write(state+4,struct.pack('<I',word(state+4)+1))
    h=u.hook_add(UC_HOOK_CODE,edit)
    assert run('bankmaintain',0)==3 and armed[1]
    u.hook_del(h);expected[0][0]=49;check(expected)
    u.reg_write(UC_ARM_REG_PRIMASK,1)
    assert run('bankmaintain',0)==1
    assert u.reg_read(UC_ARM_REG_PRIMASK)==1
    u.reg_write(UC_ARM_REG_PRIMASK,0)
    print('PASS a concurrent live edit rejects stale compression; maintenance refuses an already-masked caller')
    before_epoch=word(state+20);run('init',state,bank)
    assert word(state+20)==before_epoch+1
    armed[:]=[False,False]
    def switch_project(uc,a,n,d):
        if uc.reg_read(UC_ARM_REG_PRIMASK):armed[0]=True
        elif armed[0] and not armed[1]:
            armed[1]=True
            # A different project can have identical edit/pool generations.
            # The independent load epoch must still reject the old result.
            uc.mem_write(state+20,struct.pack('<I',word(state+20)+1))
    h=u.hook_add(UC_HOOK_CODE,switch_project)
    assert run('bankmaintain',0)==3 and armed[1]
    u.hook_del(h);check([empty]*24)
    print('PASS project-load epoch rejects stale compression even when edit generations match')
    assert run('lock',state,bank,0,0,0,12)==0
    assert run('lock',state,bank,0,7,0,99)==0
    assert run('bankget',bank,0)==12
    current_key=word(state+80)
    assert run('bankpeek',7*192)==99
    assert word(state+80)==current_key
    # A cached cross-pattern lookup must not decode or change the raw cache.
    count=[0]
    def tick(uc,a,n,d):count[0]+=1
    h=u.hook_add(UC_HOOK_CODE,tick)
    for _ in range(24):assert run('bankpeek',7*192)==99
    u.hook_del(h);assert count[0]<5000,count
    assert run('lock',state,bank,0,7,0,42)==0
    assert run('bankget',bank,0)==12
    assert run('bankpeek',7*192)==42
    print('PASS boundary lookahead leaves current-pattern cache intact; cached results invalidate after edits')
    print(f'ALL PASS ({info["bytes"]} bytes ARM code, prototype uninstalled)')
if __name__=='__main__':main()
