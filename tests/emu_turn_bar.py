"""A knob turn shows the value bar over open Stock/Granular settings for 500 ms; assignments keep their pads and darken unused knobs."""
import struct
import emu_fx_native_edges as F
G,E,SM=F.G,F.E,F.SM
TICK=0x20006f3c

def main():
    u=F.setup();r=E.MAN['report'];g=r['granular'];K=g['arm_kernel']['labels']
    turn_bar=g['ui'].get('turn_bar_ms')==500
    s=int(g['bridge']['slot'],16);m=int(g['ui']['menu'],16)
    SM.sel(u,0);u.mem_write(m+E.T.O_OPEN,b'\1');u.mem_write(G.CONT+0x264,b'\0')
    context=lambda:E.call(u,int(g['ui']['labels']['c_gucontext'],16))
    def tap(p):G.pad(u,p);G.unpad(u,p)
    def shift(on):u.mem_write(E.ptr(u,E.u32(u,E.C.CTRL+0xc),0),bytes([on]));context()
    def settings(on):
        if not g['ui'].get('shift_tap'):shift(on);return
        if (u.mem_read(s+102,1)[0]==1)!=bool(on):G.held(u,27,True);shift(1);G.held(u,27,False);shift(0)
    def hold(p):
        G.pad(u,p);u.mem_write(0x20000820,struct.pack('<I',E.u32(u,0x20000820)+400))
        E.call(u,K['c_gr_runtime_ui_frame'],s,0,1);G.unpad(u,p)
    def bar():
        E.led(u,int(r['tmenu']['labels']['c_tmled'],16))
        return tuple(E.out(u,int(g['ui']['labels']['c_guout'],16))[16:24])
    def later(ms):u.mem_write(TICK,struct.pack('<I',E.u32(u,TICK)+ms))
    def check(name,turn):
        later(1000);settings=bar();assert u.mem_read(s+102,1)==b'\1',(name,'fixture: settings not open')
        turn(1);turn(-1);shown=bar()
        if not turn_bar:
            assert shown==settings,(name,'value bar replaced settings without the option');return
        assert shown==values and shown!=settings,(name,'turn did not show the value bar',shown,settings)
        later(499);assert bar()==values,(name,'value bar left too early')
        later(2);assert bar()==settings,(name,'settings did not return after 500 ms')
    # Stock: settings latched by holding pad 25.
    u.mem_write(TICK,struct.pack('<I',100000))
    G.knob(u,0,1);G.knob(u,0,-1);later(1000);values=bar();assert any(values)
    hold(25);check('Stock',lambda d:G.knob(u,0,d))
    tap(25);assert u.mem_read(s+102,1)==b'\0'
    # Granular: settings held open by Shift; Shift turns are fine turns.
    tap(E.GP);assert u.mem_read(s+168,1)[0]&16,'fixture: Granular view not open'
    G.knob(u,0,1);G.knob(u,0,-1);later(1000);values=bar();assert any(values)
    settings(1);check('Granular',lambda d:G.knob(u,0,d))
    # Assignments keep their pads through a turn.
    if g['ui'].get('sticky_assign'):
        G.held(u,19,True);E.press(u,19);u.mem_write(0x20000820,struct.pack('<I',E.u32(u,0x20000820)+400));E.call(u,K['c_gr_runtime_ui_frame'],s,0,1);G.held(u,19,False);E.release(u,19)
    else:E.press(u,19);E.release(u,19)
    assert u.mem_read(s+380,1)[0]&128,'fixture: assignments not open'
    later(1000);assign=bar();G.knob(u,1,1);G.knob(u,1,-1);assert bar()==assign,'assignment pads replaced by a turn'
    if g['ui'].get('assign_dark_spare'):
        for _ in range(14):
            if u.mem_read(s+380,1)[0]&15>=8:break
            tap(24)
        E.led(u,int(r['tmenu']['labels']['c_tmled'],16));knobs=E.out(u,int(g['ui']['labels']['c_guout'],16))[60:68]
        assert all(knobs[:6]) and not any(knobs[6:]),('second set: K7/K8 not dark',knobs)
        for _ in range(14):
            if u.mem_read(s+380,1)[0]&15<8:break
            tap(24)
        E.led(u,int(r['tmenu']['labels']['c_tmled'],16));assert all(E.out(u,int(g['ui']['labels']['c_guout'],16))[60:68]),'first set: a knob dark'
        print('PASS assignments: second set lights K1-K6 only; first set lights all eight')
    settings(0)
    print('PASS '+('turns show the value bar over Stock and Granular settings for 500 ms; assignments keep their pads' if turn_bar
                   else 'without the option, turns keep the settings pads'))
    print('ALL PASS')
if __name__=='__main__':main()
