"""Reset feedback RGB must match stock Clear red through its real converter."""
from pathlib import Path
import struct
import sys
import emu_tmenu as E


def main():
    stock, fw, ram = (Path(p).read_bytes() for p in sys.argv[1:4])
    for dim in (True, False):
        uc, ref = E.setup(fw,ram), E.setup(stock,ram,False)
        t=E.sel(uc)
        for u in (uc,ref):
            store=E.u32(u,E.C.CTRL+E.T.O_DIM)
            ptr=E.ptr(u,store,E.T.P_DIM)
            value=E.u32(u,ptr)
            u.mem_write(ptr,struct.pack('<I',value|(1<<10) if dim else value&~(1<<10)))
        # The stock at 0x0804B51E gives held Clear palette 0x55. Run the stock RGB conversion.
        ref.mem_write(E.FRAME,bytes(138))
        ref.mem_write(E.FRAME+2*E.C.LED_CLEAR,struct.pack('<H',0x55))
        red=E.out(ref,E.rhbuild.bl_target(bytearray(stock),E.T.OUT_CALL))[E.C.LED_CLEAR]
        E.tap(uc,t)
        head=E.rhbuild.bl_target(bytearray(fw),E.C.LED_CALLS[0])
        E.led(uc,head)
        uc.mem_write(E.C.CTRL+0xA0,struct.pack('<I',E.u32(uc,E.C.CTRL+0xA0)|(1<<23)))
        E.pad(uc,31);E.unpad(uc,31);E.led(uc,head)
        outfn=E.rhbuild.bl_target(bytearray(fw),E.T.OUT_CALL)
        rgb=E.out(uc,outfn)
        E.check(f'LED dim {dim}: Clear All matches held Clear red',all(rgb[p]==red for p in range(25,32) if not (E.T.PAD_PAGE0<=p<E.T.PAD_PAGE0+len(E.PADMAP) and E.PADMAP[p-E.T.PAD_PAGE0] is None)),(hex(rgb[31]),hex(red)))
        E.tick(uc,384);E.led(uc,head);rgb=E.out(uc,outfn)
        E.check(f'LED dim {dim}: available pad stays dimmer than reset',0<rgb[31]<red,(hex(rgb[31]),hex(red)))
        E.pad(uc,25);E.unpad(uc,25);E.led(uc,head)
        E.check(f'LED dim {dim}: per-page flash matches held Clear red',E.out(uc,outfn)[25]==red)
        E.press(uc,t);E.release(uc,t)
        E.check(f'LED dim {dim}: armed track matches held Clear red',E.out(uc,outfn)[32+t]==red)
        E.press(uc,t);E.release(uc,t)
        E.check(f'LED dim {dim}: confirmed track flash matches held Clear red',E.out(uc,outfn)[32+t]==red)
    print('ALL PASS' if not E.FAILS else f'{len(E.FAILS)} FAILED')
    if E.FAILS:raise SystemExit(1)


if __name__=='__main__':main()
