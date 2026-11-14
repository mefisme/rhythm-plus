"""Execute actual Cortex-M7 lossless codec, corruption checks and bank budgets."""
import json,random,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('tools','tests')]
from build_automation_codec7 import build
from emu_playfix import machine,call
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_READ
from unicorn.arm_const import UC_ARM_REG_R0

def main():
    code,info=build();u=machine((ROOT/'remix/stock/circuitrhythm-firmware-5706-STOCK.bin').read_bytes(),
        (ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes())
    u.mem_write(info['origin'],code)
    src,out,decoded=0x20001000,0x20002000,0x20003000
    rng=random.Random(183);modes={};rows=[];counts=[0];monitor=[False]
    def executed(uc,a,n,d):
        if monitor[0]:counts[0]+=1
    u.hook_add(UC_HOOK_CODE,executed,None,info['origin'],info['origin']+len(code)-1)
    def run(name,*args):call(u,info['labels']['c_lc_'+name],*args);return u.reg_read(UC_ARM_REG_R0)
    def encode(values,measure=False):
        u.mem_write(src,bytes(values));u.mem_write(out,b'\xa5'*195)
        counts[0]=0;monitor[0]=measure;n=run('encode',out,193,src);monitor[0]=False
        enc_count=counts[0];assert n<=193
        payload=bytes(u.mem_read(out,n));assert u.mem_read(out+n,195-n)==b'\xa5'*(195-n)
        if n:modes[payload[0]]=modes.get(payload[0],0)+1
        u.mem_write(decoded,b'\xa5'*194)
        counts[0]=0;monitor[0]=measure;assert run('decode',decoded,out,n)==0;monitor[0]=False
        assert u.mem_read(decoded,192)==bytes(values) and u.mem_read(decoded+192,2)==b'\xa5'*2
        return payload,enc_count,counts[0]
    fixtures=[bytes([255])*192,bytes([0])*192,bytes([127])*192,bytes(range(128))+bytes(range(64)),
              bytes([0,255])*96,bytes([127,255])*96]
    for present in (1,2,3,6,16,32,64,96,128,190,191,192):
        for _ in range(8):
            v=[255]*192
            for i in rng.sample(range(192),present):v[i]=rng.randrange(128)
            fixtures.append(bytes(v))
    for v in fixtures:encode(v)
    for _ in range(100):
        value=rng.randrange(128);v=[]
        for i in range(192):
            value=max(0,min(127,value+rng.choice((-2,-1,0,1,2))))
            v.append(value if rng.random()>.1 else 255)
        encode(v)
    # Explicit repeats are preserved as events; absent cells stay absent.
    for v in (bytes([32])*192,bytes([32,255])*96):encode(v)
    bad=b'\x80'+b'\xff'*191;u.mem_write(src,bad);u.mem_write(out,b'\xa5'*193)
    assert run('encode',out,193,src)==0xffffffff and u.mem_read(out,193)==b'\xa5'*193
    u.mem_write(src,bytes([127])*192);assert run('encode',out,0,src)==0xffffffff
    # Failed decodes never publish partially decoded cells or read past input.
    bounds=[0]
    def read(uc,access,a,size,value,d):
        if out<=a<out+256:assert a+size<=out+bounds[0],('overread',hex(a),size,bounds[0])
    watch=u.hook_add(UC_HOOK_MEM_READ,read)
    corrupt=[b'\xff',b'\0',b'\x02\0',b'\x03\0',b'\x04'+bytes(26)]
    for _ in range(300):corrupt.append(bytes(rng.randrange(256) for _ in range(rng.randrange(1,194))))
    rejected=0
    for payload in corrupt:
        bounds[0]=len(payload);u.mem_write(out,payload);u.mem_write(decoded,b'\xa5'*192)
        if run('decode',decoded,out,len(payload)):
            rejected+=1;assert u.mem_read(decoded,192)==b'\xa5'*192
    u.hook_del(watch)
    print(f'PASS {len(fixtures)+102} exact lane round trips, explicit event/absence distinction, bounds and {rejected} rejected corrupt inputs')
    banks={
      'empty':[bytes([255])*192]*24,
      'three locks per lane':[], 'smooth sweeps, all lanes':[],
      'dense random, all lanes':[], 'one absence + random, all lanes':[]}
    for lane in range(24):
        v=[255]*192
        for i in (0,17*6,31*6):v[i]=rng.randrange(128)
        banks['three locks per lane'].append(bytes(v))
        start=rng.randrange(128)
        banks['smooth sweeps, all lanes'].append(bytes((lambda x:x if x<128 else 255-x)((start+i)%256) for i in range(192)))
        v=bytes(rng.randrange(128) for _ in range(192));banks['dense random, all lanes'].append(v)
        v=bytearray(v);v[42]=255;banks['one absence + random, all lanes'].append(bytes(v))
    hardware=ROOT/'notes/automation-device-test/live-cutoff-track1.bin'
    if hardware.exists():
        b=hardware.read_bytes()
        active=[b[p*0xa28+0x128+k*192:p*0xa28+0x128+(k+1)*192] for p in range(8) for k in range(12)]
        active=[v for v in active if len(v)==192 and any(x!=255 for x in v)]
        if active:banks['captured cutoff lane repeated for stress']=[active[0]]*24
    for name,lanes in banks.items():
        encoded=[encode(v,True) for v in lanes];size=56+sum(len(e[0]) for e in encoded)
        row=dict(scenario=name,raw_bank_bytes=4608,compressed_with_directory=size,
            active_plus_cache_and_save=2*size+576+128,
            max_encode_instructions=max(e[1] for e in encoded),max_decode_instructions=max(e[2] for e in encoded))
        rows.append(row);print(f'{name}: bank {size} B; bank + 576 B cache + save snapshot/settings {row["active_plus_cache_and_save"]} B')
    result=dict(prototype_only=True,installed=False,code_bytes=len(code),directory_bytes=56,
        raw_active_plus_snapshot=9344,modes=modes,rows=rows,
        instruction_counts_are_not_hardware_timings=True)
    (ROOT/'buildtmp/automation-codec7-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('ALL PASS')

if __name__=='__main__':main()
