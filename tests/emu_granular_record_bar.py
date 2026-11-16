"""Granular recording feedback: temporary bar/knob red and held-lock red."""
import struct
import emu_fx_native_edges as F
G,E,SM=F.G,F.E,F.SM

def main():
    u=F.setup();r=E.MAN['report'];g=r['granular'];K=g['arm_kernel']['labels']
    s=int(g['bridge']['slot'],16);m=int(g['ui']['menu'],16)
    SM.sel(u,0);u.mem_write(m,b'\1');u.mem_write(G.CONT+0x264,b'\0');G.pad(u,E.GP);G.unpad(u,E.GP)
    def draw():
        E.led(u,int(r['tmenu']['labels']['c_tmled'],16))
        return E.out(u,int(g['ui']['labels']['c_guout'],16))
    def red(v):return bool(v) and not(v&0xffff)
    def tick(n):u.mem_write(E.C.HAL_TICK,struct.pack('<I',E.u32(u,E.C.HAL_TICK)+n))
    for page in (0,1):
        E.press(u,19 if page else 20);E.release(u,19 if page else 20)
        for k in range(8 if not page or g.get('burst',True) else 6):
            u.mem_write(s+316,bytes([k+8*page+1])+bytes(7));u.mem_write(s+388,bytes(16))
            p=SM.pat(u,0);u.mem_write(p+0x128,b'\xff'*192)
            u.mem_write(E.ptr(u,E.C.TRANSPORT,0),b'\1');u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\1')
            G.knob(u,k,5);c=draw()
            assert red(c[60+k]),('live recording knob not red',page,k)
            assert any(c[16:24]) and all(not(v&0xffff) for v in c[16:24]),('live bar',page,k)
            tick(501);c=draw();assert any(v&0xffff for v in c[16:24]) and not red(c[60+k]),('bar/knob stayed red after movement',page,k)
            # Playing through automation without a panel gesture must not light red.
            E.call(u,K['c_gr_lane_inner'],0x20043700,0,70,3);assert not red(draw()[60+k])
            G.pad(u,4);G.knob(u,k,3);c=draw()
            assert red(c[60+k]) and any(red(v) for v in c[16:24]),('lock feedback',page,k)
            tick(501);c=draw();assert red(c[60+k]) and any(v&0xffff for v in c[16:24]),('held-lock idle feedback',page,k)
            G.unpad(u,4);assert not red(draw()[60+k]),('released lock knob stayed red',page,k)
            u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\0');G.pad(u,4)
            assert red(draw()[60+k]),('existing held automation missing with Record off',page,k)
            G.unpad(u,4)
    print(f"PASS all {16 if g.get('burst',True) else 14} controls: moving recording bar/knob red expires; playback stays normal; held automation retains red")
    # Clear RGB must match the same palette/dimming calculation as Stock,
    # without multiplying by another knob/page brightness level.
    for dim in (0,1):
        a=E.ptr(u,E.u32(u,E.C.CTRL+E.T.O_DIM),E.T.P_DIM);value=E.u32(u,a)
        u.mem_write(a,struct.pack('<I',(value&~1024)|(1024 if dim else 0)))
        for delta,slot in ((-40,0x55),(40,0x0e)):
            G.held(u,23,True);G.knob(u,0,delta);c=draw()
            palette=E.u32(u,E.T.COLOURS+4*slot);factor=141 if dim else 256
            expected=sum((((palette>>shift&255)*factor)>>8)<<shift for shift in (0,8,16))
            assert c[60]==expected,('Clear brightness',dim,delta,hex(c[60]),hex(expected))
            G.held(u,23,False);E.release(u,23);assert draw()[60]!=expected
    print('PASS Clear red/blue brightness exactly matches Stock palette and dimming; release restores track color')
    print('ALL PASS')
if __name__=='__main__':main()
