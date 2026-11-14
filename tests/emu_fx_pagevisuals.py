"""FX colors in both probability/gate layers; overlapping gates stay lit."""
import struct
import emu_fx_native_edges as F
G,E=F.G,F.E
def main():
    u=F.setup()
    G.pad(u,0);G.pad(u,21);G.unpad(u,21);G.unpad(u,0)
    codes=E.u32(u,E.u32(u,G.CONT+4))
    pal=lambda c:E.u32(u,0x20003974+4*c)
    for mode in (0,3,4,5,6):
        u.mem_write(G.CONT+0x264,bytes([mode]))
        u.mem_write(codes,struct.pack('<H',0x18))
        out=G.out(u);assert out[0] in (G.scl(pal(0x67),141),G.scl(pal(0x67),255)),(mode,hex(out[0]))
    u.mem_write(G.CONT+0x264,b'\0')
    u.mem_write(E.ptr(u,E.C.TRANSPORT,0),b'\x01')
    for s in (5,6):
        u.mem_write(G.TBL+7*s,bytes([0,0,0,0,0,0,0]))
        u.mem_write(G.SLOT+40+2*s,struct.pack('<H',12))
    u.mem_write(G.SLOT+16,struct.pack('<H',1<<6))
    u.mem_write(G.SLOT+72+5,b'\x01');u.mem_write(G.SLOT+72+6,b'\x02')
    u.mem_write(G.SLOT+88,b'\x07')
    u.mem_write(G.SLOT+38,struct.pack('<H',E.u32(u,G.HAL_TICK)&65535))
    out=G.out(u)
    assert out[21]==out[22] and out[21]!=0,'older overlapping Beat Repeat gate went dark'
    u.mem_write(G.SLOT+50,b'\0\0')
    expired=G.out(u)
    assert expired[21]!=expired[22],'expired gate remained highlighted'
    u.mem_write(G.SLOT+50,struct.pack('<H',12))
    G.view(u,G.MIX);u.mem_write(G.mode_p(u),b'\x07')
    master=G.out(u)
    assert master[21]==master[22] and master[21]!=0,'Grid FX view lost overlapping gate indication'
    u.mem_write(G.SLOT+50,b'\0\0');master=G.out(u)
    assert master[21]!=master[22],'Grid FX view retained expired gate indication'
    print('PASS Sample, Gate and both Probability/Gate layers retain FX pink colors')
    print('PASS both overlapping Beat Repeat gates lit; expired older gate dims')
    print('ALL PASS')
if __name__=='__main__':main()
