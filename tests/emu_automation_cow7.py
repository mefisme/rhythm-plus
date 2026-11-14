"""Actual M7 RAM pool: lossless edits, snapshots, Copy/Clear and raw worst case."""
import json,random,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('tools','tests')]
from build_automation_cow7 import build
from emu_playfix import machine,call,STACK
from unicorn.arm_const import UC_ARM_REG_R0

def main():
    code,info=build();u=machine((ROOT/'remix/stock/circuitrhythm-firmware-5706-STOCK.bin').read_bytes(),
        (ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes())
    u.mem_write(info['origin'],code)
    pool,data,source,dest=0x20001000,0x20002000,0x20005000,0x20006000
    def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    def run(name,*args):
        if len(args)>4:u.mem_write(STACK+0xf0000,struct.pack('<'+'I'*(len(args)-4),*args[4:]))
        call(u,info['labels']['c_cp_'+name],*args[:4]);return u.reg_read(UC_ARM_REG_R0)
    def put(lane,raw):u.mem_write(source,raw);return run('set',pool,data,lane,source)
    def get(lane,saved=0):
        assert run('read',pool,data,saved,lane,dest)==0
        return bytes(u.mem_read(dest,192))
    def check(active,saved=None):
        assert run('valid',pool)==1
        for lane in range(24):
            assert get(lane)==active[lane],('live',lane)
            if saved is not None:assert get(lane,1)==saved[lane],('saved',lane)
    rng=random.Random(700183);empty=b'\xff'*192
    run('init',pool,9216);active=[empty]*24
    for lane in range(24):
        v=bytes((lambda x:x if x<128 else 255-x)((lane*7+i)%256) for i in range(192))
        assert put(lane,v)==0;active[lane]=v
    live_size=word(pool+8);assert live_size<2000
    assert run('snapshot',pool)==0;saved=active.copy();assert word(pool+8)==live_size
    for lane in (0,8,16):
        v=bytes(min(127,(x+1)) for x in active[lane]);assert put(lane,v)==0;active[lane]=v
    peak=word(pool+8);check(active,saved)
    assert peak<2500
    print(f'PASS full smooth bank {live_size} B; save snapshot adds zero payload; edits to three lanes peak at {peak} B')
    # Copy aliases immutable records, then diverges safely on subsequent edits.
    before=word(pool+8);assert run('copy',pool,data,0,3,3)==0
    active[3:6]=active[0:3];assert word(pool+8)<=before
    v=bytes(rng.randrange(128) for _ in range(192));assert put(3,v)==0;active[3]=v
    check(active,saved)
    assert run('clear',pool,data,0,8)==0;active[:8]=[empty]*8
    check(active,saved);run('release',pool,data);check(active)
    print('PASS Copy initially shares data, edited copies fork, and Clear cannot alter a frozen save snapshot')
    # Fully incompressible current and saved versions still fit without a limit.
    run('init',pool,9216);active=[]
    for lane in range(24):
        raw=bytearray(rng.randrange(128) for _ in range(192));raw[42]=255
        assert put(lane,bytes(raw))==0;active.append(bytes(raw))
    assert word(pool+8)==4608
    assert run('snapshot',pool)==0;saved=active.copy()
    for lane in range(24):
        raw=bytearray(rng.randrange(128) for _ in range(192));raw[42]=255
        assert put(lane,bytes(raw))==0;active[lane]=bytes(raw)
    assert word(pool+8)==9216;check(active,saved)
    # At all 48 slots occupied, exclusive live rows are replaceable in place.
    for i in range(120):
        lane=rng.randrange(24);raw=bytearray(rng.randrange(128) for _ in range(192));raw[42]=255
        assert put(lane,bytes(raw))==0;active[lane]=bytes(raw)
        assert run('valid',pool)==1
    check(active,saved);run('release',pool,data);assert word(pool+8)==4608
    print('PASS every live and saved point fits in the 9216-byte fallback, including edits with all 48 record slots occupied')
    # Small test-only capacities must fail atomically, never truncate a lane.
    run('init',pool,256)
    raw=bytearray(rng.randrange(128) for _ in range(192));raw[42]=255
    assert put(0,bytes(raw))==0;assert run('snapshot',pool)==0
    before=bytes(u.mem_read(pool,456)),bytes(u.mem_read(data,9216))
    raw[5]^=1;assert put(0,bytes(raw))==2
    assert before==(bytes(u.mem_read(pool,456)),bytes(u.mem_read(data,9216)))
    print('PASS insufficient experimental capacity reports unchanged failure without discarding active or saved data')
    result=dict(prototype_only=True,installed=False,code_bytes=info['bytes'],metadata_bytes=456,
        smooth_live_payload=live_size,smooth_save_plus_three_edited_lanes=peak,
        raw_live_fallback=4608,raw_live_and_save_fallback=9216,
        hypothetical_smooth_ram_with_metadata_cache_settings=peak+456+576+100,
        old_active_and_save_bytes=9344)
    (ROOT/'buildtmp/automation-cow7-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('ALL PASS')

if __name__=='__main__':main()
