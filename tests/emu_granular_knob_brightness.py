"""Granular value LEDs retain the stock-derived floor and full brightness range."""
import struct
import sys
import emu_fx_native_edges as F
G,E=F.G,F.E

def main():
    u=F.setup();g=E.MAN['report']['granular'];K=g['arm_kernel']['labels'];slot=int(g['bridge']['slot'],16);buf=0x20001000
    E.call(u,int(g['ui']['labels']['c_gustate'],16));u.mem_write(slot+168,b'\x10')
    dim=E.ptr(u,E.u32(u,E.C.CTRL+E.T.O_DIM),E.T.P_DIM);u.mem_write(dim,struct.pack('<I',E.u32(u,dim)&~1024))
    def draw(knob):
        u.mem_write(buf,struct.pack('<69I',*([0xffffff]*69)))
        E.call(u,K['c_gr_runtime_draw'],slot,0,buf,knob)
        return struct.unpack('<69I',u.mem_read(buf,69*4))
    for level in (0,64,127):
        # Primary Scan is bipolar; K1 remains selected so Scan shows value level.
        u.mem_write(slot+104+3,bytes([level]));out=draw(0)
        distance=min(127,abs(level-64)*2);brightness=(distance*460+6656)>>8
        expected=sum(((0x9eff59>>s&255)*brightness//255)<<s for s in (0,8,16))
        assert out[63]==expected,(level,hex(out[63]),hex(expected))
        assert max(out[63]>>s&255 for s in (0,8,16))>=26,'center below stock-derived floor'
        if '--primary-brightness' in sys.argv:
            track=E.u32(u,E.T.COLOURS+4*E.T.TRK_SLOTS[0]);selected=draw(3)[63]
            expected=sum(((track>>s&255)*brightness//255)<<s for s in (0,8,16))
            assert selected==expected,(level,hex(selected),hex(expected))
        # Secondary Level is unipolar and uses the same curve without distance conversion.
        u.mem_write(slot+212,bytes([level]));out=draw(9)
        brightness=(level*460+6656)>>8
        expected=sum(((0x9eff59>>s&255)*brightness//255)<<s for s in (0,8,16))
        assert out[60]==expected,('secondary',level,hex(out[60]),hex(expected))
    # Assignment indicators deliberately retain fixed selector brightness.
    u.mem_write(slot+380,b'\x80');out=draw(0)
    assert out[60]==(0xffffff if ((E.MAN['marker'][:1]=='A' and len(E.MAN['marker'])==4) and 'A283' <= E.MAN['marker']) else 0x9eff59) and max(out[61]>>s&255 for s in (0,8,16))==31
    print('PASS bipolar center/extremes and secondary value LEDs use stock-derived curve; assignment dimming unchanged')
    print('ALL PASS')
if __name__=='__main__':main()
