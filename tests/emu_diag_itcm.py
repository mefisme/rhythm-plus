"""Private automation diagnostics are read-only and require mapped ITCM."""
import os,sys,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['RH_BUILD']=sys.argv[1] if len(sys.argv)>1 else 'a0189'
sys.path[:0]=[str(ROOT/p) for p in ('modules','tests','builds','remix/tools')]
import emu_tmenu as E
import rdiag as R
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R2,UC_ARM_REG_PC,UC_ARM_REG_LR

def main():
 build=os.environ['RH_BUILD'];u=E.setup((ROOT/f'firmware/{build}/rhythmplus-{build.upper()}.bin').read_bytes(),
    (ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes())
 hook=int(E.MAN['report']['rdiag']['labels']['c_rdin'],16);msg=0x20007000;replies=[];writes=[]
 def router(uc,a,n,d):
  ptr=uc.reg_read(UC_ARM_REG_R2);buf,size=struct.unpack('<II',uc.mem_read(ptr,8));replies.append(bytes(uc.mem_read(buf,size)))
  uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,router,None,R.ROUTER,R.ROUTER+1)
 u.mem_write(0xe000ef90,struct.pack('<I',0x73));u.mem_write(0x100,bytes(range(64)))
 u.mem_write(0x3d40,bytes(range(128)))
 u.hook_add(UC_HOOK_MEM_WRITE,lambda uc,a,p,n,v,d:writes.append((p,n)),None,0x100,0x3fff)
 def request(addr,length):
  b=bytearray(232);b[:6]=bytes([0xf0,0x7d,0x43,0x54,2,1]);b[6:14]=bytes((addr>>s)&15 for s in range(28,-1,-4));b[14]=length;b[-1]=0xf7
  u.mem_write(msg,bytes(b));u.mem_write(msg-16,struct.pack('<II',msg,len(b)));replies.clear();E.call(u,hook,0,msg-16,0)
  reply=replies[-1];status=int(''.join(f'{n:x}' for n in reply[6:14]),16)
  data=bytes((reply[i]<<4)|reply[i+1] for i in range(14,len(reply)-1,2));return status,data
 for addr,n in ((0x100,64),(0x3d40,64),(0x3fc0,64)):
  expected=bytes(u.mem_read(addr,n));assert request(addr,n)==(0,expected)
 for addr,n in ((0,1),(0xff,2),(0x3fff,2),(0x4000,1),(0xe000ef90,4)):
  assert request(addr,n)[0]==1,(hex(addr),n)
 u.mem_write(0xe000ef90,struct.pack('<I',0x72));assert request(0x3d40,64)[0]==1
 assert not writes,writes
 print('PASS read-only ITCM inspection; exact bounds, peripheral rejection, mapping guard and no private RAM writes')
 print('ALL PASS')
if __name__=='__main__':main()
