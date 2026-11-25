"""Input diagnostic records actual knob index/delta and held-pad context."""
import os,sys,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['RH_BUILD']=sys.argv[1] if len(sys.argv)>1 else 'a0190'
sys.path[:0]=[str(ROOT/p) for p in ('modules','tests','builds','remix/tools')]
import emu_gfxmix as G
import emu_tmenu as E
import emu_stepmut as SM
from emu_playfix import SENT
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_LR

def main():
 b=os.environ['RH_BUILD'];u=E.setup((ROOT/f'firmware/{b}/rhythmplus-{b.upper()}.bin').read_bytes(),
   (ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes())
 def ret(uc,a,n,d):uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,ret,None,G.WR16,G.WR16+1)
 G.view(u,G.CONT);u.mem_write(G.CONT+0x264,b'\x09');SM.sel(u,2)
 G.held(u,G.BIT_CLEAR,True);G.pad(u,7);G.unpad(u,7);G.held(u,G.BIT_CLEAR,False)
 G.pad(u,7);G.unpad(u,7);u.mem_write(G.CONT+0x264,b'\0')
 u.mem_write(E.ptr(u,E.u32(u,E.C.CTRL+0xc),0),b'\x01')
 before=bytes(u.mem_read(G.blk(u),26))
 G.pad(u,4);G.knob(u,2,-7);G.unpad(u,4)
 n=u.mem_read(G.SLOT+242,1)[0];ring=struct.unpack('<32I',u.mem_read(G.SLOT+244,128))
 tail=[ring[(n-9+i)%32] for i in range(9)]
 # Bit 1 is the control page: Shift on the FX track opens it only in builds without the page 2 controls.
 page=0 if E.MAN['report']['gfxmix'].get('control_page') else 2
 assert tail==[0xd10400fd|page,100,SENT|1,0xd3020511|page,0xfffffff9,SENT|1,0xd2040511|page,0,SENT|1],list(map(hex,tail))
 after=bytes(u.mem_read(G.blk(u),26))
 assert after[23:]==(before[23:] if page==0 else bytes([127,127,120])),'Shift + K3 changes the blend only where Shift opens the control page'
 assert before[4:23]==after[4:23]
 print('PASS log captures pad/knob/release, exact delta, caller and held/Shift context in existing ring; only requested control changes')
 print('ALL PASS')
if __name__=='__main__':main()
