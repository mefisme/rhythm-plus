"""Latched granular navigation, 16-control group feedback and recording LEDs."""
import struct
import emu_fx_native_edges as F
G,E,SM=F.G,F.E,F.SM

def main():
    u=F.setup();r=E.MAN['report'];g=r['granular'];K=g['arm_kernel']['labels'];slot=int(g['bridge']['slot'],16);menu=int(g['ui']['menu'],16)
    SM.sel(u,0);u.mem_write(menu+E.T.O_OPEN,b'\1');u.mem_write(G.CONT+0x264,b'\0')
    G.pad(u,31);u.mem_write(0x20000820,struct.pack('<I',E.u32(u,0x20000820)+400))
    E.call(u,K['c_gr_runtime_ui_frame'],slot,0,1);G.unpad(u,31)
    assert u.mem_read(slot+102,1)==b'\1','held sound settings did not latch'
    G.pad(u,31);G.unpad(u,31);assert u.mem_read(slot+102,1)==b'\0','tap did not close settings'
    G.pad(u,31);E.press(u,19);E.release(u,19);G.unpad(u,31)
    assert u.mem_read(slot+380,1)[0]&128,'assignment settings did not latch'
    u.mem_write(slot+104,b'\x60'*64);u.mem_write(slot+212,b'\x10'*8);u.mem_write(slot+236,b'\x10'*56)
    color=E.u32(u,0x20003974+4*E.T.TRK_SLOTS[0]);buf=0x20001000;groups=[]
    for index in range(32):
        selected=u.mem_read(slot+380,1)[0]&15;assert selected==index%16
        u.mem_write(buf,struct.pack('<69I',*([0xffffff]*69)))
        E.call(u,K['c_gr_runtime_draw'],slot,0,buf,0)
        out=struct.unpack('<69I',u.mem_read(buf,69*4))
        assert out[60+(selected&7)]==0x9eff59,'selected assignment knob lost bright green'
        active,inactive=(51,52) if selected>=8 else (52,51)
        assert max(out[active]>>s&255 for s in (0,8,16))>16*max(out[inactive]>>s&255 for s in (0,8,16)),'arrow contrast unclear'
        if selected in (0,8):groups.append(out[61:68])
        G.pad(u,24);G.unpad(u,24)
    assert groups[0]==groups[1],'assignment knobs incorrectly displayed parameter values'
    G.pad(u,31);G.unpad(u,31)
    assert u.mem_read(slot+380,1)[0]&128==0 and u.mem_read(slot+102,1)==b'\0'
    # Real panel turns and converted output, both pages and all controls.
    rec=SM.obj(u,0);pat=SM.pat(u,0)
    for d in range(16):
        page,k=divmod(d,8)
        E.press(u,19 if page else 20);E.release(u,19 if page else 20)
        u.mem_write(slot+316,bytes([d+1])+bytes(7));u.mem_write(slot+388,bytes(16))
        u.mem_write(pat+0x128,b'\xff'*192)
        u.mem_write(E.ptr(u,E.C.TRANSPORT,0),b'\1');u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\1')
        G.knob(u,k,3)
        E.led(u,int(r['tmenu']['labels']['c_tmled'],16))
        out=E.out(u,int(g['ui']['labels']['c_guout'],16));rgb=out[60+k]
        assert (rgb>>16&255)>(rgb>>8&255)*4 and (rgb>>16&255)>(rgb&255)*4,('live recording red',d,hex(rgb))
        # The assigned lane's held value must show red even without Record.
        u.mem_write(pat+0x128+3*6,b'\x40'+b'\xff'*5)
        u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\0');G.pad(u,3)
        E.led(u,int(r['tmenu']['labels']['c_tmled'],16))
        out=E.out(u,int(g['ui']['labels']['c_guout'],16));rgb=out[60+k]
        assert (rgb>>16&255)>(rgb>>8&255)*4 and (rgb>>16&255)>(rgb&255)*4,('held lock red',d,hex(rgb))
        G.unpad(u,3)
    print('PASS hold latches settings/assignments; tap returns value mode; complete 16-control cycles show green selection and arrow groups')
    print('PASS all 16 controls show live-recording red and held automation red on their actual page')
    print('ALL PASS')
if __name__=='__main__':main()
