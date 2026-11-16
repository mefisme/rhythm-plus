"""Reset feedback RGB must match stock Clear red through its real converter."""
from pathlib import Path
import struct
import sys
import emu_tmenu as E
ALLRESET=E.MAN['report']['pageclear'].get('allreset',True)


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
        outfn=E.rhbuild.bl_target(bytearray(fw),E.T.OUT_CALL)
        if ALLRESET:
            E.pad(uc,31);E.unpad(uc,31);E.led(uc,head)
            rgb=E.out(uc,outfn)
            pads=[E.T.PAD_PAGE0+j for j,pg in enumerate(E.PADMAP) if pg is not None]+[31]
            E.check(f'LED dim {dim}: Clear All: the page pads and pad 32 match held Clear red',all(rgb[p]==red for p in pads),[hex(rgb[p]) for p in pads]+[hex(red)])
            E.tick(uc,384);E.led(uc,head);rgb=E.out(uc,outfn)
            E.check(f'LED dim {dim}: available pad stays dimmer than reset',0<rgb[31]<red,(hex(rgb[31]),hex(red)))
        else:
            E.led(uc,head)
            if 'c_gr_clear_views' in E.MAN['report'].get('granular',{}).get('arm_kernel',{}).get('labels',{}):
                cue=E.scl(E.u32(uc,E.T.COLOURS+4*0x54),E.dim_mul(uc)-1)
                E.check(f'LED dim {dim}: Granular reset cue shows on the Granular pad',E.out(uc,outfn)[E.GP]==cue)
            else:
                E.check(f'LED dim {dim}: no Clear All: pad 32 dark with Clear held',E.out(uc,outfn)[31]==0,hex(E.out(uc,outfn)[31]))
        E.pad(uc,25);E.unpad(uc,25);E.led(uc,head)
        E.check(f'LED dim {dim}: per-page flash matches held Clear red',E.out(uc,outfn)[25]==red)
        E.press(uc,t);E.release(uc,t)
        E.check(f'LED dim {dim}: armed track matches held Clear red',E.out(uc,outfn)[32+t]==red)
        E.press(uc,t);E.release(uc,t)
        E.check(f'LED dim {dim}: confirmed track flash matches held Clear red',E.out(uc,outfn)[32+t]==red)
    print('ALL PASS' if not E.FAILS else f'{len(E.FAILS)} FAILED')
    if E.FAILS:raise SystemExit(1)


if __name__=='__main__':main()
