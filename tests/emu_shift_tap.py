"""Shift tap opens/closes settings; Shift held is a modifier; pad 25 cycles both ways in every view."""
import emu_fx_native_edges as F
from unicorn.arm_const import UC_ARM_REG_R0
G,E,SM=F.G,F.E,F.SM

def main():
    u=F.setup();r=E.MAN['report'];g=r['granular'];K=g['arm_kernel']['labels']
    if not g['ui'].get('shift_tap'):print('PASS not a Shift tap build: nothing to check');print('ALL PASS');return
    s=int(g['bridge']['slot'],16);m=int(g['ui']['menu'],16);t=0
    SM.sel(u,t);u.mem_write(m+E.T.O_OPEN,b'\1');u.mem_write(G.CONT+0x264,b'\0')
    context=lambda:E.call(u,int(g['ui']['labels']['c_gucontext'],16))
    def shift(on):
        G.held(u,27,on);u.mem_write(E.ptr(u,E.u32(u,E.C.CTRL+0xc),0),bytes([on]));context()
    def tap_shift():shift(1);shift(0)
    def tap(p):G.pad(u,p);G.unpad(u,p)
    shown=lambda:u.mem_read(s+102,1)[0]==1
    selected=lambda:u.mem_read(m+8,1)[0]
    def knob_page():
        E.call(u,K['c_gr_runtime_knob_page'],s,t);return u.reg_read(UC_ARM_REG_R0)
    assignment=lambda:u.mem_read(s+380+t,1)[0]
    secondary=len(g['secondary_knobs'])
    for view in ('Stock','Granular'):
        if view=='Granular':tap(E.GP);assert u.mem_read(s+168+t,1)[0]&16,'fixture: Granular view not open'
        shift(1);assert not shown(),(view,'holding Shift opened settings')
        shift(0);assert shown(),(view,'Shift tap did not open settings')
        tap_shift();assert not shown(),(view,'Shift tap did not close settings')
        shift(1);G.knob(u,1,1);G.knob(u,1,-1);shift(0);assert not shown(),(view,'Shift + turn toggled settings')
        u.mem_write(m+8,b'\3');shift(1);tap(24);assert selected()==2,(view,'Shift + pad 25 did not go back');shift(0)
        assert not shown(),(view,'Shift + pad 25 toggled settings')
        tap(24);assert selected()==3,(view,'pad 25 did not go forward')
        u.mem_write(m+8,b'\1');shift(1);tap(24);shift(0)
        assert selected()==(secondary if view=='Granular' and knob_page() else 8),(view,'reverse did not wrap',selected())
        print(f'PASS {view}: Shift tap toggles settings; Shift held + turn or pad 25 is a chord; pad 25 forward, Shift + pad 25 back, wrapping')
    # Granular settings: pad 25 walks every control on both pages, both ways.
    E.press(u,20);E.release(u,20);assert not knob_page()
    tap_shift();assert shown()
    u.mem_write(m+8,b'\1');walk=[]
    for _ in range(8+secondary):tap(24);walk.append((knob_page(),selected()))
    assert walk==[(0,k) for k in range(2,9)]+[(1,k) for k in range(1,secondary+1)]+[(0,1)],('settings cycle',walk)
    shift(1);tap(24);assert (knob_page(),selected())==(1,secondary),'settings reverse did not wrap to the last secondary knob'
    tap(24);assert (knob_page(),selected())==(1,secondary-1);shift(0);assert shown(),'Shift chord closed settings'
    print(f'PASS Granular settings: pad 25 cycles all {8+secondary} controls across both pages; Shift + pad 25 goes back')
    # Assignments: Down opens them, pad 25 both ways, Up returns, a Shift tap or the pad closes.
    E.press(u,19);E.release(u,19);assert assignment()&128,'Down did not open assignments'
    before=assignment()&15;tap(24);assert assignment()&15==(before+1)%(8+secondary)
    shift(1);tap(24);tap(24);shift(0);assert assignment()&15==(before-1)%(8+secondary),'assignment reverse'
    assert shown() and assignment()&128,'Shift chord closed assignments'
    E.press(u,20);E.release(u,20);assert shown() and not assignment()&128,'Up did not return to sound settings'
    E.press(u,19);E.release(u,19);tap_shift();assert not shown() and not assignment()&128,'Shift tap did not close assignments'
    tap_shift();assert shown();tap(E.GP);assert not shown(),'Granular pad tap did not close settings'
    print('PASS assignments: Down opens, pad 25 both ways, Up back to settings; Shift tap or pad 27 closes')
    print('ALL PASS')
if __name__=='__main__':main()
