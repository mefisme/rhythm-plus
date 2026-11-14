"""Settings-only parameter-pad pulse uses the Mutate coefficient; track is steady."""
import struct
import emu_fx_native_edges as F
G,E,SM=F.G,F.E,F.SM

def main():
    u=F.setup();r=E.MAN['report'];g=r['granular'];K=g['arm_kernel']['labels'];slot=int(g['bridge']['slot'],16);menu=int(g['ui']['menu'],16)
    SM.sel(u,0);u.mem_write(menu+E.T.O_OPEN,b'\1');u.mem_write(G.CONT+0x264,b'\0')
    root=int(g['ui']['labels']['c_guout'],16);context=int(g['ui']['labels']['c_gucontext'],16)
    shift=lambda:E.ptr(u,E.u32(u,E.C.CTRL+0xc),0)
    G.pad(u,31);G.unpad(u,31)
    E.led(u,int(r['tmenu']['labels']['c_tmled'],16))
    coefficients=(0,64,128,192,255)
    def sample():
        result=[]
        for c in coefficients:
            u.mem_write(0x20003974+4*0x0a,struct.pack('<I',c));result.append(E.out(u,root))
        return result
    baseline=sample();base=baseline[0][31]
    assert len({o[31] for o in baseline})==1,'value-mode pad pulsed'
    def check(mode):
        E.led(u,int(r['tmenu']['labels']['c_tmled'],16))
        values=sample()
        for coefficient,out in zip(coefficients,values):
            level=64+((255-coefficient)*192>>8)
            expected=sum((((base>>s&255)*(level+1))>>8)<<s for s in (0,8,16))
            assert out[31]==expected,(mode,coefficient,hex(out[31]),hex(expected))
        assert len({o[32] for o in values})==1 and values[0][32]!=0,('track pulsed',mode)
        assert len({o[60] for o in values})==1,('selected knob pulsed',mode)
    G.pad(u,31);u.mem_write(0x20000820,struct.pack('<I',E.u32(u,0x20000820)+400))
    E.call(u,K['c_gr_runtime_ui_frame'],slot,0,1);G.unpad(u,31);check('pad-held settings')
    E.press(u,19);E.release(u,19);check('pad-held assignments')
    G.pad(u,31);G.unpad(u,31)
    for physical in (False,True):
        G.held(u,27,physical);u.mem_write(shift(),b'\1');E.call(u,context);check('Shift settings')
        E.press(u,19);E.release(u,19);check('Shift assignments')
        G.held(u,27,False);u.mem_write(shift(),b'\0');E.call(u,context)
        assert len({o[31] for o in sample()})==1,'Shift release retained menu pulse'
    print('PASS pad-held/held-Shift/sticky-Shift settings and assignments match Mutate pulse; value mode stays steady')
    print('PASS selected track and selected knob stay steady through every pulse phase')
    print('ALL PASS')
if __name__=='__main__':main()
