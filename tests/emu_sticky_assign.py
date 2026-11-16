"""Settings arrows pick the knob page; holding Down opens sticky assignments; the pad or a Shift press closes latched menus."""
import struct
import emu_fx_native_edges as F
from unicorn.arm_const import UC_ARM_REG_R0
G,E,SM=F.G,F.E,F.SM
CLOCK=0x20000820

def main():
    u=F.setup();r=E.MAN['report'];g=r['granular'];K=g['arm_kernel']['labels']
    if not g['ui'].get('sticky_assign'):print('PASS not a sticky assignment build: nothing to check');print('ALL PASS');return
    s=int(g['bridge']['slot'],16);m=int(g['ui']['menu'],16);t=0
    SM.sel(u,t);u.mem_write(m+E.T.O_OPEN,b'\1');u.mem_write(G.CONT+0x264,b'\0')
    context=lambda:E.call(u,int(g['ui']['labels']['c_gucontext'],16))
    def shift(on):G.held(u,27,on);u.mem_write(E.ptr(u,E.u32(u,E.C.CTRL+0xc),0),bytes([on]));context()
    def later(ms):u.mem_write(CLOCK,struct.pack('<I',E.u32(u,CLOCK)+ms));E.call(u,K['c_gr_runtime_ui_frame'],s,t,1)
    def tap(p):G.pad(u,p);G.unpad(u,p)
    def hold(p):G.pad(u,p);later(400);G.unpad(u,p)
    def down(held_ms):
        G.held(u,19,True);E.press(u,19);later(held_ms);G.held(u,19,False);E.release(u,19);later(1)
    up=lambda:(E.press(u,20),E.release(u,20))
    shown=lambda:u.mem_read(s+102,1)[0]==1
    assigned=lambda:bool(u.mem_read(s+380+t,1)[0]&128)
    def page():E.call(u,K['c_gr_runtime_knob_page'],s,t);return u.reg_read(UC_ARM_REG_R0)
    tap(E.GP);assert u.mem_read(s+168+t,1)[0]&16,'fixture: Granular view not open'
    for entry in ('Shift','pad menu'):
        if entry=='Shift':shift(1)
        else:hold(E.GP)
        assert shown(),(entry,'settings not shown')
        down(100);assert page()==1 and not assigned() and shown(),(entry,'Down tap did not pick the second knob page')
        up();assert page()==0 and not assigned() and shown(),(entry,'Up tap did not pick the first knob page')
        down(400);assert assigned() and shown(),(entry,'holding Down did not open assignments')
        if entry=='Shift':
            shift(0);assert assigned() and shown(),'assignments closed with Shift release'
        up();assert shown() and not assigned(),(entry,'Up did not return to sound settings')
        down(400);assert assigned()
        tap(E.GP);assert not shown() and not assigned(),(entry,'pad tap did not close assignments')
        print(f'PASS {entry}: Up/Down taps pick the knob page; holding Down opens assignments, which stay open; Up returns; the pad closes')
    # A Shift press or tap closes a latched menu and shows nothing until it is let go.
    for menu in ('assignments','pad menu'):
        hold(E.GP)
        if menu=='assignments':down(400);assert assigned()
        shift(1);assert not shown() and not assigned(),(menu,'Shift press did not close the menu')
        for _ in range(3):context()
        assert not shown(),(menu,'held Shift reopened settings after closing')
        shift(0);assert not shown(),(menu,'Shift release reopened settings')
        shift(1);assert shown(),'next Shift hold did not show settings';shift(0);assert not shown()
    tap(25);hold(25);assert shown(),'fixture: Stock pad menu'
    shift(1);assert not shown(),'Shift did not close Stock pad menu';shift(0)
    print('PASS a Shift press closes assignments or a pad menu (Stock too) and stays quiet until released; the next hold works')
    print('ALL PASS')
if __name__=='__main__':main()
