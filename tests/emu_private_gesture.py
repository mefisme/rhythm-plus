"""Real pad -> private knob -> pad release, rather than isolated lock helpers."""
import os,sys,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['RH_BUILD']=sys.argv[1] if len(sys.argv)>1 else 'a0186'
sys.path[:0]=[str(ROOT/p) for p in ('modules','tests','builds','remix/tools')]
import emu_gfxmix as G
import emu_tmenu as E
import emu_stepmut as SM
import automation_bank_helpers as BH
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_R0

def main():
    build=os.environ['RH_BUILD']
    fw=(ROOT/f'firmware/{build}/rhythmplus-{build.upper()}.bin').read_bytes()
    ram=(ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes()
    count=0
    for mode in (0,3):
      for playing in (0,1):
       for recording in (0,1):
        for page in (0,1):
         for occupied in (0,1):
          u=E.setup(fw,ram);t=2
          def w(a,v):u.mem_write(a,struct.pack('<I',v))
          def put(s,i,v):u.mem_write(E.ptr(u,s,i),bytes([v]))
          def ret(uc,a,n,d):uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
          u.hook_add(UC_HOOK_CODE,ret,None,G.WR16,G.WR16+1)
          G.view(u,G.CONT);u.mem_write(G.CONT+0x264,b'\x09');SM.sel(u,t)
          G.held(u,G.BIT_CLEAR,True);G.pad(u,7);G.unpad(u,7);G.held(u,G.BIT_CLEAR,False)
          G.pad(u,7);G.unpad(u,7);u.mem_write(G.CONT+0x264,b'\0')
          so=E.u32(u,G.CONT+0x74+4*t);put(E.u32(u,so+0x60),0,page)
          step=4+16*page
          if occupied:
            G.pad(u,4);G.pad(u,21);G.unpad(u,21);G.unpad(u,4)
          rec=SM.obj(u,t);pat=E.u32(u,rec+4)
          for a,v in ((0xe000ef90,0x73),(0xe000ed08,0x08010000),(0xe000ed94,0),(0xe000ed14,0)):w(a,v)
          E.call(u,int(E.MAN['report']['storageshadow']['labels']['c_sh_block'],16))
          w(int(E.MAN['report']['storageshadow']['slot'],16)+88,8)
          put(E.u32(u,so+0x60),0,page)
          put(E.C.TRANSPORT,0,playing);put(E.C.TRANSPORT,1,recording);put(E.C.TRANSPORT,2,0)
          u.mem_write(G.CONT+0x264,bytes([mode]));put(E.u32(u,E.C.CTRL+0xc),0,1);G.held(u,27,True)
          notes=bytes(u.mem_read(pat,8*0xa28));fx=G.pk_read(u,0,step)
          bank=BH.read(u,E.MAN['report'],0,4608)
          G.pad(u,4)
          if occupied:G.knob(u,3,-1)
          audition_color=0xff0000 if occupied else 0x00ff00
          for k in range(3):
            G.knob(u,k,-20-k)
            # Rendering/maintenance between movements must neither create
            # native notes nor change the independent audition toggle.
            for frame in range(2):
              w(G.HAL_TICK,1000+count*160+k*40+frame*20)
              G.out(u)
              E.call(u,int(E.MAN['report']['storageshadow']['labels']['c_sh_out'],16),E.C.CTRL,G.OUT,G.FRAME)
              assert E.u32(u,G.OUT+4*63)==G.scl(audition_color,141),'audition color changed'
              assert u.mem_read(pat,8*0xa28)==notes,'native notes/automation changed while held'
          G.unpad(u,4)
          assert u.mem_read(pat,8*0xa28)==notes,(mode,playing,recording,page,occupied,'native pattern changed')
          assert G.pk_read(u,0,step)==fx,'FX assignment changed'
          expected=bytearray(bank)
          if recording:
            for k in range(3):expected[(k*8)*192+step*6:(k*8)*192+step*6+6]=bytes([107-k])+b'\xff'*5
          actual=BH.read(u,E.MAN['report'],0,4608)
          assert actual==expected,(mode,playing,recording,page,occupied,[(i,a,b) for i,(a,b) in enumerate(zip(actual,expected)) if a!=b][:24])
          if recording and playing and occupied and page==0:
            A={k:int(v,16) for k,v in E.MAN['report']['automation3']['labels'].items()}
            state=int(E.MAN['report']['automation3']['state'],16)
            player=0x200470d4+0x190*t
            auto=next(a for a in range(0x20040d00,0x20042400,4)
                      if E.u32(u,a)==0x08067864 and E.u32(u,a+0xc)==E.u32(u,player+8))
            # A second real held-pad recording gesture sets a different value.
            G.pad(u,7)
            for k in range(3):G.knob(u,k,-30)
            heldbank=BH.read(u,E.MAN['report'],0,4608)
            # The actual installed listener must not stream while a pad is held.
            for st in range(8,12):
              for pulse in range(6):
                for i,v in enumerate((0,st,pulse)):put(E.u32(u,auto+0xc),i,v)
                E.call(u,A['c_a3_listener'],auto+8,E.u32(u,auto+0x30),1,0)
            assert BH.read(u,E.MAN['report'],0,4608)==heldbank,'held lock streamed to playhead'
            G.unpad(u,7)
            assert u.mem_read(pat,8*0xa28)==notes,'second lock gesture changed notes'
            # Release must not arm a continuous private recording either.
            for st in range(12,16):
              put(E.u32(u,auto+0xc),1,st)
              E.call(u,A['c_a3_listener'],auto+8,E.u32(u,auto+0x30),1,0)
            assert BH.read(u,E.MAN['report'],0,4608)==heldbank,'released lock streamed to playhead'
            put(E.C.TRANSPORT,1,0)
            E.call(u,A['c_a3_reset'],state)
            put(E.u32(u,player+0x10),1,3)
            # Real native player plus installed private player, two complete
            # loops. Empty cells retain output until the next explicit lock.
            for turn in range(2):
              for st in range(32):
                for pulse in range(6):
                  put(E.u32(u,player+0xc),0,0);put(E.u32(u,player+0xc),1,(st+1)%32)
                  E.call(u,A['c_a3_play'],player,0,st,pulse)
                  for k in range(3):
                    E.call(u,G.LB['c_gx_autovalue'],k,127)
                    want=(107-k) if 4<=st<7 else (77-k)
                    assert u.reg_read(UC_ARM_REG_R0)==want,(mode,turn,st,pulse,k,want,u.reg_read(UC_ARM_REG_R0))
                w(G.HAL_TICK,4000+turn*640+st*20)
                G.out(u)
                E.call(u,int(E.MAN['report']['storageshadow']['labels']['c_sh_out'],16),E.C.CTRL,G.OUT,G.FRAME)
                assert E.u32(u,G.OUT+4*63)==G.scl(audition_color,141),'K4 changed during lock playback'
            assert BH.read(u,E.MAN['report'],0,4608)==heldbank,'playback changed recorded automation'
            # Editing an existing lock must start from that step's saved
            # value, even though playback currently holds the other lock.
            put(E.C.TRANSPORT,1,1);G.pad(u,4)
            for k in range(3):
              G.knob(u,k,5)
              assert BH.read(u,E.MAN['report'],k*1536+4*6,1)==bytes([112-k]),'edit jumped from live value instead of held lock'
              G.knob(u,k,-5)
            G.unpad(u,4)
            assert BH.read(u,E.MAN['report'],0,4608)==heldbank,'round-trip lock edit changed other data'
            # Record remains armed. A fresh unheld knob movement resumes
            # continuous recording at the current playhead position.
            G.knob(u,2,1)
            for i,v in enumerate((0,18,0)):put(E.u32(u,auto+0xc),i,v)
            E.call(u,A['c_a3_listener'],auto+8,E.u32(u,auto+0x30),1,0)
            resumed=bytearray(heldbank);resumed[2*1536+18*6]=106
            assert BH.read(u,E.MAN['report'],0,4608)==resumed,'new unheld knob movement did not resume live recording'
          count+=1
    print(f'PASS {count} complete gestures: both views/pages, empty/FX notes, playing/stopped, Record off/on')
    print('PASS all K1-K3 locks preserve native notes/automation/FX assignments; K4 stays steady in both audition states through rendering and compression')
    print('PASS two real held-step locks retain exact values for two playback loops; native listener cannot stream while held or after release')
    print('PASS re-editing a lock uses its saved value rather than the different currently playing value')
    print('PASS after pad release, Record stays armed and a new knob turn resumes continuous recording at the playhead')
    print('ALL PASS')

if __name__=='__main__':main()
