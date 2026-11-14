"""Both bars use track hue; arrows distinguish primary and secondary controls."""
import struct
import emu_fx_native_edges as F
G,E,SM=F.G,F.E,F.SM

def main():
    u=F.setup();g=E.MAN['report']['granular'];K=g['arm_kernel']['labels'];slot=int(g['bridge']['slot'],16)
    E.call(u,int(g['ui']['labels']['c_gustate'],16))
    out=0x20001000
    for t in range(8):
        u.mem_write(slot+168+t,b'\x10');u.mem_write(slot+104+t*8,b'\x60');u.mem_write(slot+212+t,b'\x60')
        color=E.u32(u,0x20003974+4*E.T.TRK_SLOTS[t])
        for page in (0,1):
            E.call(u,K['c_gr_runtime_arrow'],slot,t,19 if page else 20)
            u.mem_write(out,struct.pack('<69I',*([0xffffff]*69)))
            E.call(u,K['c_gr_runtime_draw'],slot,t,out,page*8)
            expected=color
            assert E.u32(u,out+16*4)==expected,(t,page,hex(E.u32(u,out+16*4)),hex(color))
            up=E.u32(u,out+52*4)
            if not page:assert up==0x9eff59,('Up granular hue',t,hex(up))
            # Lock drawing is a second rendering path; it must use the same hue.
            u.mem_write(slot+316+t*8,bytes([1+8*page])+bytes(7))
            rec=SM.obj(u,t);pat=SM.pat(u,t)
            u.mem_write(pat+0x128,b'\x60'+b'\xff'*5)
            stepobj=E.u32(u,G.CONT+0x74+4*t)
            u.mem_write(E.ptr(u,E.u32(u,stepobj+E.T.HELDSTEP),1),b'\0')
            u.mem_write(stepobj+E.T.PADS_DOWN,struct.pack('<I',1))
            E.call(u,K['c_gr_lane_draw'],slot,t,out,0)
            assert E.u32(u,out+16*4)==expected,('held',t,page,hex(E.u32(u,out+16*4)),hex(color))
            u.mem_write(stepobj+E.T.PADS_DOWN,struct.pack('<I',0))
    print('PASS all 8 tracks: primary/secondary value-bar hues, held locks and granular-green arrows')
    print('ALL PASS')
if __name__=='__main__':main()
