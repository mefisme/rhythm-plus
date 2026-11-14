"""Opposite-group lane ownership is dim red; existing green meanings stay."""
import struct
import emu_fx_native_edges as F
G,E,SM=F.G,F.E,F.SM

def main():
    u=F.setup();g=E.MAN['report']['granular'];K=g['arm_kernel']['labels'];slot=int(g['bridge']['slot'],16)
    E.call(u,int(g['ui']['labels']['c_gustate'],16));u.mem_write(slot+168,b'\x10')
    mapping=bytes([1,2,9,10,0,0,0,0]);u.mem_write(slot+316,mapping);out=0x20001000
    def rgb(color,level):return sum(((color>>s&255)*level//255)<<s for s in (0,8,16))
    for selected,expected in ((0,[0x9eff59,rgb(0x9eff59,63),rgb(0xff2a1a,31),rgb(0xff2a1a,31),rgb(0xffffff,31)]),
                              (8,[rgb(0xff2a1a,31),rgb(0xff2a1a,31),0x9eff59,rgb(0x9eff59,63),rgb(0xffffff,31)])):
        u.mem_write(slot+380,bytes([128|selected]));u.mem_write(out,struct.pack('<69I',*([0xffffff]*69)))
        E.call(u,K['c_gr_runtime_draw'],slot,0,out,0)
        actual=struct.unpack('<69I',u.mem_read(out,69*4))
        assert list(actual[16:21])==expected,(selected,[hex(v) for v in actual[16:21]],[hex(v) for v in expected])
        assert u.mem_read(slot+316,8)==mapping,'render changed assignments'
    # Full output-chain transition must keep the same granular-view track
    # buttons and dim stock-view pad, instead of falling back to stock white.
    SM.sel(u,0);menu=int(g['ui']['menu'],16)
    u.mem_write(menu+E.T.O_OPEN,b'\1');u.mem_write(G.CONT+0x264,b'\0')
    u.mem_write(slot+380,b'\0')
    G.pad(u,31);u.mem_write(0x20000820,struct.pack('<I',E.u32(u,0x20000820)+400))
    E.call(u,K['c_gr_runtime_ui_frame'],slot,0,1);G.unpad(u,31)
    E.led(u,int(E.MAN['report']['tmenu']['labels']['c_tmled'],16))
    root=int(g['ui']['labels']['c_guout'],16);settings=E.out(u,root)
    E.press(u,19);E.release(u,19);assignment=E.out(u,root)
    assert assignment[32:40]==settings[32:40],'assignment changed track-view indicators'
    assert assignment[25]==settings[25],'stock parameter pad became selected'
    for value in (0,127):
        u.mem_write(slot+104,bytes([value])*64);u.mem_write(slot+212,bytes([value])*8);u.mem_write(slot+236,bytes([value])*56)
        for selected in range(16):
            u.mem_write(slot+380,bytes([128|selected]));rendered=E.out(u,root)
            leds=rendered[60:68];bright=leds[selected&7]
            assert bright and len({c for i,c in enumerate(leds) if i!=(selected&7)})==1
            assert max(bright>>s&255 for s in (0,8,16))>4*max(leds[(selected+1)&7]>>s&255 for s in (0,8,16))
    print('PASS settings-to-assignment keeps granular track/pad indicators; all 16 selections ignore knob values')
    print('PASS both knob groups: selected bright green, same-group dim green, opposite-group dim red, stock dim white')
    print('ALL PASS')
if __name__=='__main__':main()
