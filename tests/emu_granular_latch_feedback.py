"""Latched granular navigation, 16-control group feedback and recording LEDs."""
import struct
import sys
import emu_fx_native_edges as F
G,E,SM=F.G,F.E,F.SM

def main():
    u=F.setup();r=E.MAN['report'];g=r['granular'];K=g['arm_kernel']['labels'];slot=int(g['bridge']['slot'],16);menu=int(g['ui']['menu'],16)
    SM.sel(u,0);u.mem_write(menu+E.T.O_OPEN,b'\1');u.mem_write(G.CONT+0x264,b'\0')
    dim=E.ptr(u,E.u32(u,E.C.CTRL+E.T.O_DIM),E.T.P_DIM);u.mem_write(dim,struct.pack('<I',E.u32(u,dim)&~1024))
    G.pad(u,E.GP);u.mem_write(0x20000820,struct.pack('<I',E.u32(u,0x20000820)+400))
    E.call(u,K['c_gr_runtime_ui_frame'],slot,0,1);G.unpad(u,E.GP)
    assert u.mem_read(slot+102,1)==b'\1','held sound settings did not latch'
    G.pad(u,E.GP);G.unpad(u,E.GP);assert u.mem_read(slot+102,1)==b'\0','tap did not close settings'
    G.pad(u,E.GP);E.press(u,19);E.release(u,19);G.unpad(u,E.GP)
    assert u.mem_read(slot+380,1)[0]&128,'assignment settings did not latch'
    u.mem_write(slot+104,b'\x60'*64);u.mem_write(slot+212,b'\x10'*8);u.mem_write(slot+236,b'\x10'*56)
    color=E.u32(u,0x20003974+4*E.T.TRK_SLOTS[0]);buf=0x20001000;groups=[]
    dests=16 if g.get('burst',True) else 14
    if '--turn-select' in sys.argv:
        rec=SM.obj(u,0);points=E.u32(u,rec+4)+0x128
        before=bytes(u.mem_read(points,12*192))
        values=bytes(u.mem_read(slot+104,64))+bytes(u.mem_read(slot+212,8))+bytes(u.mem_read(slot+236,56))
        G.knob(u,3,127)
        assert u.mem_read(slot+380,1)[0]==0x83
        for _ in range(5):G.pad(u,24);G.unpad(u,24)
        assert u.mem_read(slot+380,1)[0]==0x88
        G.knob(u,3,-127)
        assert u.mem_read(slot+380,1)[0]==0x8b
        G.knob(u,7,127)
        assert u.mem_read(slot+380,1)[0]==(0x8b if dests==14 else 0x8f)
        for _ in range(dests):
            if u.mem_read(slot+380,1)[0]==0x80:break
            G.pad(u,24);G.unpad(u,24)
        assert u.mem_read(slot+380,1)[0]==0x80
        assert bytes(u.mem_read(points,12*192))==before
        assert bytes(u.mem_read(slot+104,64))+bytes(u.mem_read(slot+212,8))+bytes(u.mem_read(slot+236,56))==values
        print('PASS turning selects within either assignment group without changing values or automation')
    for index in range(2*dests):
        selected=u.mem_read(slot+380,1)[0]&15;assert selected==index%dests
        u.mem_write(buf,struct.pack('<69I',*([0xffffff]*69)))
        E.call(u,K['c_gr_runtime_draw'],slot,0,buf,0)
        out=struct.unpack('<69I',u.mem_read(buf,69*4))
        selected_color = 0xffffff if ((E.MAN['marker'][:1]=='A' and len(E.MAN['marker'])==4) and 'A283' <= E.MAN['marker']) else 0x9eff59
        assert out[60+(selected&7)]==selected_color,'selected assignment knob color is incorrect'
        marker = E.MAN['marker']
        down_lit = marker == 'A285' or (not ((marker[:1]=='A' and len(marker)==4) and 'A286' <= marker) and selected >= 8)
        active,inactive=(51,52) if down_lit else (52,51)
        assert max(out[active]>>s&255 for s in (0,8,16))>16*max(out[inactive]>>s&255 for s in (0,8,16)),'arrow contrast unclear'
        if selected in (0,8):groups.append(out[61:68])
        G.pad(u,24);G.unpad(u,24)
    spare=6 if g['ui'].get('assign_dark_spare') else 7
    assert groups[0][:spare-1]==groups[1][:spare-1] and not any(groups[1][spare-1:]) if spare==6 else groups[0]==groups[1],'assignment knobs incorrectly displayed parameter values'
    G.pad(u,E.GP);G.unpad(u,E.GP)
    assert u.mem_read(slot+380,1)[0]&128==0 and u.mem_read(slot+102,1)==b'\0'
    # Real panel turns and converted output, both pages and all controls.
    rec=SM.obj(u,0);pat=SM.pat(u,0)
    for d in range(dests):
        page,k=divmod(d,8)
        E.press(u,19 if page else 20);E.release(u,19 if page else 20)
        u.mem_write(slot+316,bytes([d+1])+bytes(7));u.mem_write(slot+388,bytes(16))
        u.mem_write(pat+0x128,b'\xff'*192)
        u.mem_write(E.ptr(u,E.C.TRANSPORT,0),b'\1');u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\1')
        G.knob(u,k,3)
        E.led(u,int(r['tmenu']['labels']['c_tmled'],16))
        out=E.out(u,int(g['ui']['labels']['c_guout'],16));rgb=out[60+k]
        if E.MAN['report']['granular'].get('movement_bar_feedback'):
            assert (rgb>>16&255)>(rgb>>8&255)*4 and (rgb>>16&255)>(rgb&255)*4,('live recording knob not red',d,hex(rgb))
            assert any(out[16:24]) and all(not (v&0xffff) for v in out[16:24]),('recording bar not red',d)
        else:
            assert (rgb>>16&255)>(rgb>>8&255)*4 and (rgb>>16&255)>(rgb&255)*4,('live recording red',d,hex(rgb))
        # The assigned lane's held value must show red even without Record.
        u.mem_write(pat+0x128+3*6,b'\x40'+b'\xff'*5)
        u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\0');G.pad(u,3)
        E.led(u,int(r['tmenu']['labels']['c_tmled'],16))
        out=E.out(u,int(g['ui']['labels']['c_guout'],16));rgb=out[60+k]
        assert (rgb>>16&255)>(rgb>>8&255)*4 and (rgb>>16&255)>(rgb&255)*4,('held lock red',d,hex(rgb))
        G.unpad(u,3)
    print('PASS hold latches settings/assignments; tap returns value mode; complete control cycles show the selection and arrow groups')
    print(f'PASS all {dests} controls show live-recording feedback and held automation red on their actual page')
    print('ALL PASS')
if __name__=='__main__':main()
