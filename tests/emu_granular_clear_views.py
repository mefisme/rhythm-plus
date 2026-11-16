"""View brightness/ownership/Clear-pad feedback across both parameter views."""
import struct
import emu_fx_native_edges as F
G,E,SM=F.G,F.E,F.SM

def main():
    u=F.setup();r=E.MAN['report'];g=r['granular'];s=int(g['bridge']['slot'],16);m=int(g['ui']['menu'],16)
    SM.sel(u,0);u.mem_write(m,b'\1');u.mem_write(G.CONT+0x264,b'\0')
    u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\0')
    pc=int(r['pageclear']['slot'],16)
    def tap(p):G.pad(u,p);G.unpad(u,p)
    def draw():
        E.led(u,int(r['tmenu']['labels']['c_tmled'],16))
        return E.out(u,int(g['ui']['labels']['c_guout'],16))
    def tick(n):u.mem_write(E.C.HAL_TICK,struct.pack('<I',E.u32(u,E.C.HAL_TICK)+n))
    def redcue(slot):return E.scl(E.u32(u,E.T.COLOURS+4*slot),E.dim_mul(u)-1)
    for dim in (False,True):
        a=E.ptr(u,E.u32(u,E.C.CTRL+E.T.O_DIM),E.T.P_DIM);v=E.u32(u,a)
        u.mem_write(a,struct.pack('<I',(v&~1024)|(1024 if dim else 0)))
        tap(25);G.held(u,23,True)
        plain=draw();u.mem_write(s+316,bytes(range(1,9)));borrowed=draw()
        assert borrowed[60:68]==plain[60:68],'Stock Clear recolored borrowed knobs'
        G.held(u,23,False);E.release(u,23)
        tap(E.GP);u.mem_write(s+104,b'\x60'*8)
        for page in (0,1):
            E.press(u,19 if page else 20);E.release(u,19 if page else 20)
            before=draw();G.held(u,23,True);during=draw()
            assert during[16:24]==before[16:24] and during[60:68]==before[60:68],('Clear dimmed values',dim,page)
            assert during[25]==during[E.GP]==redcue(0x54),('missing reset cues',dim,page)
            G.held(u,23,False);E.release(u,23)
        # Clear Stock while viewing Granular must not reset custom data or make
        # its value bar/knobs blink with the unrelated Stock confirmation.
        p=SM.pat(u,0);u.mem_write(p+0x128,b'\x41'+b'\xff'*191)
        manual=bytes(u.mem_read(s+104,64));ownership=bytes(u.mem_read(s+316,64))
        G.held(u,23,True);tap(25);start=E.u32(u,pc)
        assert u.mem_read(pc+4,1)==b'\x1a'
        assert bytes(u.mem_read(s+104,64))==manual and bytes(u.mem_read(s+316,64))==ownership
        assert bytes(u.mem_read(p+0x128,192))==b'\x41'+b'\xff'*191,'Stock reset erased borrowed lane'
        stable=draw()
        for elapsed in (0,64,128,192,256,320,384):
            u.mem_write(E.C.HAL_TICK,struct.pack('<I',start+elapsed));c=draw()
            assert c[16:24]==stable[16:24] and c[60:68]==stable[60:68],('Stock reset flashed Granular',dim,elapsed)
            expected=(0 if elapsed&64 else redcue(0x55)) if elapsed<384 else redcue(0x54)
            assert c[25]==expected,('Stock confirmation cadence',dim,elapsed)
        # Granular is also an available reset target and has the same flash.
        tap(E.GP);start=E.u32(u,pc);assert u.mem_read(pc+4,1)[0]==E.GP+1
        assert u.mem_read(s+104,8)!=b'\x60'*8
        for elapsed in (0,64,128,320,384):
            u.mem_write(E.C.HAL_TICK,struct.pack('<I',start+elapsed));c=draw()
            expected=(0 if elapsed&64 else redcue(0x55)) if elapsed<384 else redcue(0x54)
            assert c[E.GP]==expected,('Granular confirmation cadence',dim,elapsed)
        G.held(u,23,False);E.release(u,23);tick(400)
        assert draw()[E.GP] and draw()[25],'parameter pads disappeared after Clear'
    print('PASS both LED dim modes: Clear leaves Granular knobs/bar at normal brightness; Stock borrowed colors remain native')
    print('PASS both reset pads visible; Stock/Granular confirmations share cadence, preserve ownership and never flash Granular values')
    print('ALL PASS')
if __name__=='__main__':main()
