"""Shift reverses the parameter cycle without opening or dismissing a modal."""

import struct

import emu_fx_native_edges as fixture

G, E, SM = fixture.G, fixture.E, fixture.SM


def since(build):
    marker = E.MAN['marker']
    return (marker[:1]=='A' and len(marker)==4) and build <= marker


def main():
    u=fixture.setup()
    report=E.MAN['report']; granular=report['granular']; kernel=granular['arm_kernel']['labels']
    slot=int(granular['bridge']['slot'],16); menu=int(granular['ui']['menu'],16)
    filter_pad=report['filter_cutoff']['editor_pad']-1
    SM.sel(u,0);u.mem_write(menu+E.T.O_OPEN,b'\1');u.mem_write(G.CONT+0x264,b'\0')

    def tap(pad):
        G.pad(u,pad);G.unpad(u,pad)

    def shift(active):
        G.held(u,27,active)
        store=E.u32(u,E.C.CTRL+0x0c)
        u.mem_write(E.ptr(u,store,0),bytes([active]))
        E.call(u,int(granular['ui']['labels']['c_gucontext'],16))

    def selected():return u.mem_read(menu+E.T.O_KNOB,1)[0]
    def group():
        E.call(u,kernel['c_gr_runtime_knob_page'],slot,0)
        from unicorn.arm_const import UC_ARM_REG_R0
        return u.reg_read(UC_ARM_REG_R0)

    def arrows(*, colors=False):
        E.led(u, int(report['tmenu']['labels']['c_tmled'], 16))
        lights = E.out(u, int(granular['ui']['labels']['c_guout'], 16))
        if colors: return lights[51:53]
        return tuple(bool(light) for light in lights[51:53])  # Down, Up.

    check_arrows = since('A285')
    settings_arrows = (since('A286'), E.MAN['marker'] == 'A285')
    assignment_arrows = settings_arrows[::-1]

    def hold(pad):
        G.pad(u,pad)
        u.mem_write(0x20000820,struct.pack('<I',E.u32(u,0x20000820)+400))
        E.call(u,kernel['c_gr_runtime_ui_frame'],slot,0,1)
        G.unpad(u,pad)

    tap(25);u.mem_write(menu+E.T.O_KNOB,b'\1')
    if E.MAN['marker'] == 'A294': assert not arrows()[0]
    shift(True)
    assert u.mem_read(slot+102,1)==b'\0','Shift opened Stock settings'
    tap(24);assert selected()==8
    shift(False);tap(24);assert selected()==1

    tap(E.GP);u.mem_write(menu+E.T.O_KNOB,b'\x08')
    if since('A286'): assert arrows() == (True, False)
    tap(24);assert (group(),selected())==(1,1)
    if since('A286'): assert arrows() == (False, True)
    shift(True);tap(24);assert (group(),selected())==(0,8)
    assert u.mem_read(slot+102,1)==b'\0','Shift opened Granular settings'
    shift(False)

    hold(E.GP)
    if since('A293'):
        down, up = arrows(colors=True)
        assert down and down == (down & 255) * 0x010101 and up == 0
    assert u.mem_read(slot+102,1)==b'\1'
    if check_arrows: assert arrows() == settings_arrows
    tap(24);assert (group(),selected())==(1,1)
    if check_arrows: assert arrows() == settings_arrows
    shift(True);tap(24);assert (group(),selected())==(0,8)
    assert u.mem_read(slot+102,1)==b'\1','Shift dismissed Granular settings'
    E.press(u,19);E.release(u,19);u.mem_write(slot+380,b'\x88')
    if check_arrows: assert arrows() == assignment_arrows
    tap(24);assert u.mem_read(slot+380,1)==b'\x87'
    if check_arrows: assert arrows() == assignment_arrows
    shift(False);tap(24);assert u.mem_read(slot+380,1)==b'\x88'

    if check_arrows:
        E.press(u,20);E.release(u,20)
        assert arrows() == settings_arrows
    tap(filter_pad);u.mem_write(menu+E.T.O_KNOB,b'\x03')
    shift(True);tap(24);assert selected()==1,'Filter reverse cycle stopped on unused K2'
    shift(False);tap(24);assert selected()==3
    hold(filter_pad);E.press(u,19);E.release(u,19)
    G.knob(u,3,1)  # Select LFO depth, destination 17.
    shift(True);tap(24);tap(16)
    assert u.mem_read(slot+316,1)==b'\x15','Filter reverse assignment did not wrap to decay'
    shift(False);tap(filter_pad);assert not u.mem_read(slot+380,1)[0]&128
    print('ALL PASS')


if __name__=='__main__':
    main()
