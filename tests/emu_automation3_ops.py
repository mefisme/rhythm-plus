"""Actual native Copy/Clear helpers plus private lanes and packed Grid FX."""
import os,sys,struct,random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['RH_BUILD']=sys.argv[1] if len(sys.argv)>1 else 'a0183'
sys.path[:0]=[str(ROOT/p) for p in ('modules','tests','builds','remix/tools')]
import emu_tmenu as E
import emu_gfxmix as G
import automation_bank_helpers as BH
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *

def main():
    build=os.environ['RH_BUILD'];rep=E.MAN['report']
    u=E.setup((ROOT/'firmware'/build/f'rhythmplus-{build.upper()}.bin').read_bytes(),
        (ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes())
    def w(a,v):u.mem_write(a,struct.pack('<I',v))
    def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    def setp(st,i,v):u.mem_write(E.ptr(u,st,i),bytes([v]))
    def ret(uc,a,n,d):uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,ret,None,G.WR16,G.WR16+1)
    t=2;G.view(u,G.CONT);u.mem_write(G.CONT+0x264,b'\x09');setp(word(G.CONT+0x25c),0,t)
    G.pad(u,7);G.unpad(u,7);u.mem_write(G.CONT+0x264,b'\0')
    assert u.mem_read(G.blk(u)+12,1)==bytes([t])
    for a,v in ((0xe000ef90,0x73),(0xe000ed08,0x08010000),(0xe000ed94,0),(0xe000ed14,0)):w(a,v)
    E.call(u,int(rep['storageshadow']['labels']['c_sh_block'],16))
    w(int(rep['storageshadow']['slot'],16)+22*4,8)
    rec=word(0x2003d380+4*t);pats=word(rec+4)
    rng=random.Random(183);initial=bytes(255 if rng.random()<.2 else rng.randrange(128) for _ in range(4608))
    def bank():return BH.read(u,rep)
    def putbank(b=initial):BH.write(u,rep,b)
    def lane(b,k,p):return b[(k*8+p)*192:(k*8+p+1)*192]
    def expect_pattern(b,src,dst):
        x=bytearray(b)
        for k in range(3):x[(k*8+dst)*192:(k*8+dst+1)*192]=lane(b,k,src) if src is not None else b'\xff'*192
        return bytes(x)
    def select(p,s=0):setp(word(rec+0x28),0,p);setp(word(rec+0x28),1,s)
    model={(0,1):(1<<5)|(1<<9)|(1<<16),(0,17):(1<<2)|(1<<3)|(1<<17),(7,3):1<<4}
    G.pk_encode(u,t,model);putbank();select(1)
    source=bytes(u.mem_read(pats,0xa28))
    E.call(u,0x080479ac,rec,pats,7,0)
    assert bank()==expect_pattern(initial,0,7)
    assert all(G.pk_read(u,7,s)==G.pk_read(u,0,s) for s in range(32))
    assert u.mem_read(pats+7*0xa28,0xa28)==source
    before=bank();E.call(u,0x080479ac,rec,pats+7*0xa28,7,0);assert bank()==before
    print('PASS pattern paste preserves all private microsteps, packed combinations/random/repeat and native pattern bytes; self-paste is safe')
    # Destination selected and unselected patterns use different native paths.
    for p in (1,7):
        before=bank();E.call(u,0x08047ad8,rec,p)
        assert bank()==expect_pattern(before,None,p)
        assert all(G.pk_read(u,p,s)==0 for s in range(32))
    print('PASS selected/unselected pattern Clear affects only that pattern, including packed FX')
    G.pk_encode(u,t,model);putbank();select(7,31)
    # Native clipboard retains source-step number in its existing four-byte descriptor.
    u.mem_write(word(rec+0x64)+3,b'\x11')
    before=bank();E.call(u,0x08047820,rec,pats+17*8,pats+0x128,0)
    expected=bytearray(before)
    for k in range(3):expected[(k*8+7)*192+31*6:(k*8+7)*192+32*6]=lane(before,k,0)[17*6:18*6]
    assert bank()==expected and G.pk_read(u,7,31)==G.pk_read(u,0,17)
    before=bank();E.call(u,0x080478d6,rec)
    expected=bytearray(before)
    for k in range(3):expected[(k*8+7)*192+31*6:(k*8+7)*192+32*6]=b'\xff'*6
    assert bank()==expected and G.pk_read(u,7,31)==0
    print('PASS cross-page step paste/Clear includes all six cells and packed FX, preserving every other step')
    other=word(0x2003d380+4*3);otherpats=word(other+4)
    putbank();before=bank();E.call(u,0x080479ac,other,pats,2,0);assert bank()==before
    select(1);E.call(u,0x080479ac,rec,otherpats,6,0)
    assert bank()==expect_pattern(before,None,6) and all(G.pk_read(u,6,s)==0 for s in range(32))
    print('PASS non-FX destinations do not acquire global FX lanes; non-FX sources clear stale destination private data')
    # Confirmed Clear + track number, through the real button wrappers.
    select(0);putbank();G.pk_encode(u,t,model)
    G.held(u,G.BIT_CLEAR,True);G.btn(u,t);assert bank()==initial
    E.call(u,E.C.BTN_RELEASE,E.C.CTRL,t);G.btn(u,t)
    assert bank()==expect_pattern(initial,None,0)
    assert G.pk_read(u,0,1)==model[0,1]
    assert list(u.mem_read(G.blk(u)+23,3))==[127,127,127]
    for k in range(3):
        E.call(u,int(rep['gfxmix']['labels']['c_gx_autovalue'],16),k,127)
        assert u.reg_read(UC_ARM_REG_R0)==127
    E.call(u,E.C.BTN_RELEASE,E.C.CTRL,t);G.held(u,G.BIT_CLEAR,False)
    print('PASS Clear + track requires confirmation, clears current private automation, resets routing values and preserves FX notes')
    putbank();u.mem_write(G.CONT+0x264,b'\x09');G.held(u,G.BIT_CLEAR,True);G.pad(u,7);G.unpad(u,7)
    assert bank()==b'\xff'*4608
    print('PASS existing FX-track full clear removes all eight private patterns')
    print('ALL PASS')

if __name__=='__main__':main()
