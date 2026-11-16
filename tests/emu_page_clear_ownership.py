"""Page reset clears only the current owner's native automation lanes."""
import itertools,struct
import emu_fx_native_edges as F
G,E,SM=F.G,F.E,F.SM

def main():
    u=F.setup();r=E.MAN['report'];g=r['granular'];s=int(g['bridge']['slot'],16);m=int(g['ui']['menu'],16)
    SM.sel(u,2);u.mem_write(G.CONT+0x264,b'\x09');G.pad(u,7);G.unpad(u,7)
    u.mem_write(G.CONT+0x264,b'\0');u.mem_write(m,b'\1')
    cases=0
    for t in range(8):
        SM.sel(u,t)
        # Both primary and secondary destinations, with ownership rotated so
        # each native sound lane is tested as borrowed and Stock-owned.
        mapping=bytes((1+(k*2+t)%16) if (k+t)%2==0 else 0 for k in range(8))
        u.mem_write(s+316+t*8,mapping)
        for view,target,playing,record,held in itertools.product((25,E.GP),(25,E.GP),(0,1),(0,1),(False,True)):
            G.pad(u,view);G.unpad(u,view)
            u.mem_write(E.ptr(u,E.C.TRANSPORT,0),bytes([playing]));u.mem_write(E.ptr(u,E.C.TRANSPORT,1),bytes([record]))
            p=SM.pat(u,t);rec=SM.obj(u,t);base=E.u32(u,rec+4)
            for k in range(12):u.mem_write(p+0x128+k*192,bytes([30+k])*192)
            if held:G.pad(u,4)
            scope=E.ptr(u,E.u32(u,rec+0x40),0);scope_before=bytes(u.mem_read(scope,1))
            notes=bytes(u.mem_read(p,0x100));bank=bytes(u.mem_read(base,8*0xa28))
            others=[bytes(u.mem_read(E.u32(u,SM.obj(u,n)+4),8*0xa28)) if n!=t else b'' for n in range(8)]
            G.held(u,23,True);G.pad(u,target);G.unpad(u,target);G.held(u,23,False);E.release(u,23)
            assert u.mem_read(s+316+t*8,8)==mapping,'page clear changed lane assignments'
            assert bytes(u.mem_read(scope,1))==scope_before,'page clear did not restore held scope'
            assert bytes(u.mem_read(p,0x100))==notes,'page clear changed notes'
            for k in range(12):
                mine=k<8 and (bool(mapping[k]) if target==E.GP else not mapping[k])
                expected=b'\xff'*192 if mine else bytes([30+k])*192
                assert bytes(u.mem_read(p+0x128+k*192,192))==expected,(t,view,target,playing,record,held,k)
            off=p-base
            assert bytes(u.mem_read(base,off))==bank[:off]
            assert bytes(u.mem_read(p+0xa28,8*0xa28-off-0xa28))==bank[off+0xa28:],'changed another pattern'
            for n in range(8):
                if n!=t:assert bytes(u.mem_read(E.u32(u,SM.obj(u,n)+4),8*0xa28))==others[n],'changed another track'
            if held:G.unpad(u,4)
            cases+=1
    print('PASS',cases,'actual page-clear gestures: both viewed/target pads, all8 tracks, transport/Record states, with/without held steps')
    print('PASS Stock preserves borrowed lanes; Granular clears only its own primary/secondary lanes; assignments, notes, sends, other patterns/tracks preserved')
    print('ALL PASS')
if __name__=='__main__':main()
