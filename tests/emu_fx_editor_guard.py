"""FX track cannot open/render Track Parameter Editor before RGB conversion."""
import os,sys,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['RH_BUILD']=sys.argv[1] if len(sys.argv)>1 else 'a0188'
sys.path[:0]=[str(ROOT/p) for p in ('modules','tests','builds','remix/tools')]
import emu_gfxmix as G
import emu_tmenu as E
import emu_stepmut as SM
import rhbuild
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_LR

def main():
    build=os.environ['RH_BUILD'];fw=(ROOT/f'firmware/{build}/rhythmplus-{build.upper()}.bin').read_bytes()
    ram=(ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes()
    for mode in (0,3):
      for playing in (0,1):
        u=E.setup(fw,ram);t=2
        def w(a,v):u.mem_write(a,struct.pack('<I',v))
        def put(s,i,v):u.mem_write(E.ptr(u,s,i),bytes([v]))
        def ret(uc,a,n,d):uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        u.hook_add(UC_HOOK_CODE,ret,None,G.WR16,G.WR16+1)
        u.hook_add(UC_HOOK_CODE,ret,None,0x080406a8,0x080406a9)
        G.view(u,G.CONT);u.mem_write(G.CONT+0x264,b'\x09');SM.sel(u,t)
        G.held(u,G.BIT_CLEAR,True);G.pad(u,7);G.unpad(u,7);G.held(u,G.BIT_CLEAR,False)
        G.pad(u,7);G.unpad(u,7);u.mem_write(G.CONT+0x264,bytes([mode]))
        put(E.C.TRANSPORT,0,playing)
        head=rhbuild.bl_target(bytearray(fw),E.C.LED_CALLS[0])
        def frame():
          native=E.led(u,E.PREV_LED)
          actual=E.led(u,head)
          # Check before the old late c_gx_out close can hide an open menu.
          assert E.b8(u,E.T.O_OPEN)==0,'editor entered FX track before RGB output'
          assert actual[:32]==native[:32],'editor overlay leaked into pad frame'
          assert E.b8(u,E.T.O_PTRK)==0,'pending editor track press on FX track'
          assert E.b8(u,E.T.O_BACK)==0,'pending editor bounce on FX track'
        for _ in range(3):E.tap(u,t);frame()
        E.press(u,t);E.tick(u,1000);frame();E.release(u,t);frame()
        put(E.u32(u,E.C.CTRL+0xc),0,1);E.tap(u,t);frame();put(E.u32(u,E.C.CTRL+0xc),0,0)
        # Stale editor state (switching from another track or old pending hold)
        # must be cleared before a single editor marker is drawn.
        for off,value in ((E.T.O_OPEN,1),(E.T.O_STICKY,1),(E.T.O_PTRK,3),(E.T.O_BACK,1),(E.T.O_SHOP,1)):
          u.mem_write(E.SLOT+off,bytes([value]))
        frame()
        # Ordinary tracks retain their normal editor and own blinking cues.
        SM.sel(u,0);u.mem_write(G.CONT+0x264,b'\0')
        assert E.sel(u)==0,'ordinary track rejected by editor predicate'
        u.mem_write(E.SLOT+E.T.O_OPEN,b'\x01');u.mem_write(E.SLOT+E.T.O_STICKY,b'\x01')
        E.led(u,head)
        assert E.b8(u,E.T.O_OPEN)==1,'ordinary track editor disabled'
    print('PASS FX track: taps, long hold, Shift+track and stale editor state cannot enter or draw TPE in Samples/Gate, stopped/playing')
    print('PASS ordinary track editor remains available')
    print('ALL PASS')

if __name__=='__main__':main()
