"""Granular and Stock parameter pads share the same inactive brightness."""
import struct
import emu_fx_native_edges as F
G,E=F.G,F.E

def main():
    u=F.setup();g=E.MAN['report']['granular'];K=g['arm_kernel']['labels'];slot=int(g['bridge']['slot'],16);buf=0x20001000
    E.call(u,int(g['ui']['labels']['c_gustate'],16))
    for level in (64,141,255):
        actual_level=E.dim_mul(u)-1 if g['ui'].get('native_brightness') else level
        frame=struct.pack('<69I',*([(level<<16)|(level<<8)|level]*69))
        for t in range(8):
            u.mem_write(slot+168+t,b'\0');u.mem_write(buf,frame)
            E.call(u,K['c_gr_runtime_draw'],slot,t,buf,0)
            inactive=E.u32(u,buf+E.GP*4)
            u.mem_write(slot+168+t,b'\x10');u.mem_write(buf,frame)
            E.call(u,K['c_gr_runtime_draw'],slot,t,buf,0)
            stock=E.u32(u,buf+25*4);active=E.u32(u,buf+E.GP*4)
            peak=lambda c:max(c>>s&255 for s in (0,8,16))
            assert peak(inactive)==peak(stock)==actual_level//16,(t,level,hex(inactive),hex(stock))
            assert peak(active)==actual_level,'active granular pad dimmed'
    print('PASS inactive Granular matches inactive Stock brightness for all tracks/dim levels; active brightness unchanged')
    print('ALL PASS')
if __name__=='__main__':main()
