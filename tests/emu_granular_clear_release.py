"""Clear acknowledgements must expire, allowing a new native-style gesture."""
import emu_fx_native_edges as F
G,E,SM=F.G,F.E,F.SM

def main():
    u=F.setup();r=E.MAN['report'];g=r['granular'];K=g['arm_kernel']['labels']
    s=int(g['bridge']['slot'],16);m=int(g['ui']['menu'],16);counters=m+E.T.O_CLRR
    u.mem_write(m+E.T.O_OPEN,b'\1');u.mem_write(G.CONT+0x264,b'\0')
    u.mem_write(E.ptr(u,E.C.TRANSPORT,1),b'\0')
    def draw():
        E.led(u,int(r['tmenu']['labels']['c_tmled'],16))
        return E.out(u,int(g['ui']['labels']['c_guout'],16))
    def clear(k,delta):
        G.held(u,23,True);G.knob(u,k,delta)
        expected=8+k if delta<0 else k
        assert u.mem_read(counters+expected,1)==b'(',('threshold',k,delta)
        out=draw()
        G.held(u,23,False);E.release(u,23)
        assert bytes(u.mem_read(counters,16))==bytes(16),'release left sticky counters'
        normal=draw();assert normal[60+k]!=out[60+k],('sticky color',k,delta,hex(out[60+k]))
    for track in (0,7):
        SM.sel(u,track);G.pad(u,E.GP);G.unpad(u,E.GP)
        for page in (0,1):
            E.press(u,19 if page else 20);E.release(u,19 if page else 20)
            for k in range(8):
                for delta in (-40,40):
                    clear(k,delta)
                    # No intervening renderer is required to begin again.
                    G.held(u,23,True);G.knob(u,k,39 if delta>0 else -39)
                    assert max(u.mem_read(counters,16))==39,'next gesture reused old threshold'
                    G.held(u,23,False);E.release(u,23)
    print('PASS all 16 controls, tracks 1/8, both Clear directions: acknowledgement expires and next gesture starts fresh')
    # Fallback when no button-up event was delivered: even a closed/reopened
    # editor must never render stale acknowledgement colors with Clear up.
    u.mem_write(counters,b'('*16);draw()
    assert bytes(u.mem_read(counters,16))==bytes(16)
    print('PASS output fallback clears stale counters without a Clear release event')
    print('ALL PASS')
if __name__=='__main__':main()
