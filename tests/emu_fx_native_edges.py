"""Native edge semantics around FX assignment and private lock selection."""
import os,sys,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['RH_BUILD']=sys.argv[1] if len(sys.argv)>1 else 'a0191'
sys.path[:0]=[str(ROOT/p) for p in ('modules','tests','builds','remix/tools')]
import emu_gfxmix as G
import emu_tmenu as E
import emu_stepmut as SM
import automation_bank_helpers as BH
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_LR

def setup():
    b=os.environ['RH_BUILD']
    u=E.setup((ROOT/f'firmware/{b}/rhythmplus-{b.upper()}.bin').read_bytes(),
              (ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes())
    def ret(uc,a,n,d):uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,ret,None,G.WR16,G.WR16+1)
    G.view(u,G.CONT);u.mem_write(G.CONT+0x264,b'\x09');SM.sel(u,2)
    G.held(u,G.BIT_CLEAR,True);G.pad(u,7);G.unpad(u,7);G.held(u,G.BIT_CLEAR,False)
    G.pad(u,7);G.unpad(u,7);u.mem_write(G.CONT+0x264,b'\0')
    for a,v in ((0xe000ef90,0x73),(0xe000ed08,0x08010000),(0xe000ed94,0),(0xe000ed14,0)):
        u.mem_write(a,struct.pack('<I',v))
    E.call(u,int(E.MAN['report']['storageshadow']['labels']['c_sh_block'],16))
    u.mem_write(int(E.MAN['report']['storageshadow']['slot'],16)+88,struct.pack('<I',8))
    return u

def main():
    u=setup()
    G.pad(u,4);G.pad(u,21)
    fx=G.pk_read(u,0,4)
    assert fx,'fixture did not assign FX'
    # Same pad-down report must not toggle its assignment off again.
    for i in range(5):
        G.pad(u,21,70+i)
        assert G.pk_read(u,0,4)==fx,'duplicate down toggled FX assignment'
    G.unpad(u,21);G.unpad(u,4)
    # An unmatched release must have no custom side effects.
    before=bytes(u.mem_read(G.SLOT,472))
    G.unpad(u,5)
    after=bytes(u.mem_read(G.SLOT,472))
    # The old pad-only diagnostic ring is expected to record the report.
    assert before[:240]==after[:240] and before[372:]==after[372:],'unmatched release changed FX state'
    assert G.pk_read(u,0,4)==fx
    print('PASS repeated native down reports preserve FX assignment; unmatched up preserves FX state')
    # Selecting private automation without moving a knob cannot program notes.
    for record in (0,1):
        u=setup();t=2;rec=SM.obj(u,t);pat=E.u32(u,rec+4)
        u.mem_write(E.ptr(u,E.u32(u,E.C.CTRL+0xc),0),b'\x01')
        u.mem_write(E.ptr(u,E.C.TRANSPORT,1),bytes([record]))
        before=bytes(u.mem_read(pat,8*0xa28))
        G.pad(u,4);G.unpad(u,4)
        assert bytes(u.mem_read(pat,8*0xa28))==before,'private selection created a native note'
        G.pad(u,4);G.knob(u,2,-7);G.unpad(u,4)
        assert bytes(u.mem_read(pat,8*0xa28))==before,'private lock edit changed native notes'
        want=bytearray(b'\xff'*4608)
        if record:want[2*1536+4*6]=120
        assert BH.read(u,E.MAN['report'])==want,'lock edit changed other automation'
    print('PASS private selection and K3 lock preserve native notes and other automation')
    print('ALL PASS')
if __name__=='__main__':main()
