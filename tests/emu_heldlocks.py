"""Actual native lock/record helpers across all twelve track lanes."""
import os,sys,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['RH_BUILD']=sys.argv[1] if len(sys.argv)>1 else 'a0181'
sys.path[:0]=[str(ROOT/p) for p in ('modules','tests','builds','remix/tools')]
import emu_tmenu as E
from unicorn.arm_const import UC_ARM_REG_R0

def main():
    build=os.environ['RH_BUILD'];u=E.setup((ROOT/'firmware'/build/f'rhythmplus-{build.upper()}.bin').read_bytes(),
        (ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes())
    def w(a,v):u.mem_write(a,struct.pack('<I',v))
    def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    def store(s,i,v):u.mem_write(E.ptr(u,s,i),bytes([v]))
    store(E.C.TRANSPORT,0,1);store(E.C.TRANSPORT,1,1);store(E.C.TRANSPORT,2,0)
    for t in (0,7):
        rec=word(0x2003d380+4*t);pats=word(rec+4);player=0x200470d4+0x190*t
        so=word(0x20048b9c+0x74+4*t)
        store(word(rec+0x28),0,3);store(word(rec+0x28),1,2)
        store(word(so+E.T.HELDSTEP),1,17);w(so+E.T.PADS_DOWN,1<<17)
        for k in range(12):
            u.mem_write(pats+3*0xa28+0x128+k*192,b'\xff'*192)
            E.call(u,0x08047d82,rec,k,40+k)
            lane=bytes(u.mem_read(pats+3*0xa28+0x128+k*192,192))
            expected=bytearray(b'\xff'*192);expected[17*6]=40+k
            assert lane==expected,(t,k)
            assert u.mem_read(E.ptr(u,word(rec+0x28),1),1)==b'\x02'
        ko=word(0x20048b9c+0x1c4+4*t)
        mask=word(E.ptr(u,word(ko+0x1c),0))
        assert mask&255==255,('native held-lock feedback',t,hex(mask))
        auto=next(a for a in range(0x20040d00,0x20042400,4) if word(a)==0x08067864 and word(a+0xc)==word(player+8))
        for i,v in enumerate((0,6,0)):store(word(auto+0xc),i,v)
        before=bytes(u.mem_read(pats,8*0xa28));w(word(auto+0x38),0xfff)
        for k in range(12):
            E.call(u,0x08049706,auto,k,90,0)
            E.call(u,0x080497ec,auto,k,0,90)
        assert u.mem_read(pats,8*0xa28)==before
        assert word(word(auto+0x38))&0xfff==0
        # Released: the original streaming helper works at the live position.
        w(so+E.T.PADS_DOWN,0)
        for k in range(12):
            E.call(u,0x080497ec,auto,k,0,90)
            assert u.mem_read(pats+0x128+k*192+6*6,1)==b'Z',(t,k)
        assert u.mem_read(pats+3*0xa28+0x128+17*6,1)==b'('
    print('PASS all 12 native lanes: held-step edits target only selected pattern/step and restore selected position')
    print('PASS continuous recording/interpolation cannot write other steps while held; release resumes native recording')
    print('ALL PASS')

if __name__=='__main__':main()
