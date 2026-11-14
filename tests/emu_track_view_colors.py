"""Unselected TPE track colors follow each track's remembered pad view."""
import struct
import emu_fx_native_edges as F
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC
G,E,SM=F.G,F.E,F.SM

def main():
    u=F.setup();r=E.MAN['report'];g=r['granular'];K=g['arm_kernel']['labels'];slot=int(g['bridge']['slot'],16);menu=int(g['ui']['menu'],16)
    # Disable the fixture's FX track so every track can open the editor.
    SM.sel(u,2);u.mem_write(G.CONT+0x264,b'\x09');G.pad(u,7);G.unpad(u,7)
    u.mem_write(G.CONT+0x264,b'\0');u.mem_write(menu+E.T.O_OPEN,b'\1')
    root=int(g['ui']['labels']['c_guout'],16);views=[False]*8
    def output(selected):
        SM.sel(u,selected);E.led(u,int(r['tmenu']['labels']['c_tmled'],16));return E.out(u,root)
    def check(selected):
        out=output(selected)
        for t in range(8):
            rgb=out[32+t]
            if t==selected:
                color=E.u32(u,0x20003974+4*E.T.TRK_SLOTS[t]);level=max(rgb>>s&255 for s in (0,8,16));peak=max(color>>s&255 for s in (0,8,16))
                assert all(abs((rgb>>s&255)-(color>>s&255)*level//peak)<=1 for s in (0,8,16)),('selected track hue',t,hex(rgb),hex(color))
            elif views[t]:
                level=max(rgb>>s&255 for s in (0,8,16));expected=sum(((0x9eff59>>s&255)*level//255)<<s for s in (0,8,16))
                assert rgb==expected and rgb,('granular view',selected,t,hex(rgb))
            else:assert rgb and (rgb&255)==(rgb>>8&255)==(rgb>>16&255),('stock view',selected,t,hex(rgb))
    # Real pad selections update only the selected track's remembered view.
    for t in (0,7,3,5):
        SM.sel(u,t);G.pad(u,31);G.unpad(u,31);views[t]=True
        for selected in range(8):check(selected)
    for t in (7,0):
        SM.sel(u,t);G.pad(u,25);G.unpad(u,25);views[t]=False
        for selected in range(8):check(selected)
    # Engine enabled is intentionally different from editor view ownership.
    u.mem_write(slot+168+6,b'\x22');views[6]=False
    check(1)
    # Selected state, native confirmations and editor-closed behavior are preserved.
    scratch=0x20001000;u.mem_write(scratch,struct.pack('<69I',*([0x808080]*69)))
    u.mem_write(scratch+33*4,struct.pack('<I',0xff2a1a));u.mem_write(scratch+32*4,struct.pack('<I',0x123456))
    E.call(u,K['c_gr_track_views'],slot,0,scratch)
    assert E.u32(u,scratch+33*4)==0xff2a1a and E.u32(u,scratch+32*4)==0x123456
    calls=[];hook=u.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:calls.append(a),None,K['c_gr_track_views'],K['c_gr_track_views']+1)
    u.mem_write(menu+E.T.O_OPEN,b'\0');E.out(u,root);assert not calls,'view colors leaked outside the editor'
    u.hook_del(hook)
    print('PASS mixed Stock/Granular remembered views across all 8 selections; pad changes affect only their track')
    print('PASS engine enablement is independent; selected hue/red confirmation/editor-closed output preserved')
    print('ALL PASS')
if __name__=='__main__':main()
