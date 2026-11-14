"""Offline current-build granular: startup, ownership and actual stage audio.

No ARM granular page, legacy save codec or device writes are installed.
"""
import copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('modules','tools','tests','remix/tools')]
import core0,rhdsp1,rhdspemu as D,dspmap
import granular_bundle as B
import granular_current_layout as CURRENT
import granular_layout as L
import granular_pool_candidate as P
import granular0 as G
import emu_granular_pool as POOL

def read(name):
    folder=ROOT/'firmware'/name
    return (folder/f'rhythmplus-{name.upper()}.bin').read_bytes(),json.loads((folder/'manifest.json').read_text())
def programs(image,report):
    loader,stream=core0.sent(image,report)
    result=[('p',loader[1],loader[2:])];i=0
    while stream[i]:
        n,a=stream[i:i+2];result.append(('p',a,stream[i+2:i+2+n]));i+=n+2
    assert stream[i:i+2]==[0,0]
    return result
def flat(segments):return {a+i:w for sp,a,words in segments if sp=='p' for i,w in enumerate(words)}

def main():
    name=sys.argv[1] if len(sys.argv)>1 else 'gr001'
    image,manifest=read(name);report=manifest['report'];g=report['granular']
    base,baseline=read(g['base_build'].lower())
    assert not g['old_project_codec_installed']
    if 'arm_kernel' not in g:
        assert manifest['offline_only'] and not manifest['flashable']
        assert report['rhstate']==baseline['report']['rhstate']
    segs=programs(image,report);actual=flat(segs);old=flat(programs(base,baseline['report']))
    allowed={0,1,0x228,0x229}
    assert all(actual[a]==w for a,w in old.items() if a not in allowed)
    assert actual[0x225]==int(report['gfxsplit']['pre'],16)
    before=flat(rhdsp1.parse(rhdsp1.sent(bytearray(base),baseline['report'],'pitchmod'))[0])
    after=flat(rhdsp1.parse(rhdsp1.sent(bytearray(image),report,'pitchmod'))[0])
    changed={0x122,0x23d,0x25c,0x25d,0x22f,0x230,0x231,0x232,0x233,0x2f3,0x4e6}
    assert all(after[a]==w for a,w in before.items() if a not in changed)
    assert after[0x2f3]==g['core1_stages']['notes']['labels']['note_on']
    print('PASS current Grid FX hooks/sound code retained; only declared granular dispatch hooks alter native core1')
    with CURRENT.allocated():
        L.validate(report);assert not dspmap.overlaps(dspmap.regions(report))
        assert G.GB==0x4000 and G.LB==0x1500
        # Poison private state to make clearing observable; Grid FX storage
        # carries a different pattern and must survive both clear phases.
        memory=[];dumps=[]
        for r in L.REGIONS:
            if r.core not in (-1,0):continue
            sp='y' if r.space=='shared' else r.space
            memory.append((sp,r.start,[0x6a7a4b]*r.words));dumps.append((sp,r.start,r.words))
        fx=[0x123400+i for i in range(192)]
        memory += [('x',0x1400,fx),('x',0x3fff,[0x5a1234]),('x',0x4100,[0x5a1234])]
        guards=[('x',0x1400,192),('x',0x3fff,1),('x',0x4100,1)]
        result,ran=D.run(0,pc=0,stop=0x100,segs=segs,mem=memory,dumps=dumps+guards,maxins=100000)
        assert 'pc=000100' in ran
        for sp,a,n in dumps:
            shared=0x37400<=a<0x37460
            expected=[0]*n if shared else [0x6a7a4b]*n
            if a==B.FLAG:expected[0]=0
            assert result[sp,a]==expected,(sp,hex(a))
        assert result['x',0x1400]==fx
        assert result['x',0x3fff]==result['x',0x4100]==[0x5a1234]
        first=int(g['first_pass'],16);body=g['pool']['labels']['after_wait']+2
        for flag,cleared in ((0,True),(1,False)):
            caller,_=core0.asm_at(['move #>$1234,r0',('jsr',first),('jmp',0x3f00)],0x3f00)
            result,ran=D.run(0,pc=0x3f00,stop=body,segs=segs+[('p',0x3f00,caller),('p',0x1a11,[0xc])],
                mem=memory+[('y',B.FLAG,[flag])],dumps=dumps+guards,maxins=200000)
            assert f'pc={body:06x}' in ran
            for sp,a,n in dumps:
                if 0x37400<=a<0x37460:continue
                if a==B.FLAG:assert result[sp,a]==[1,0x1234];continue
                assert result[sp,a]==([0]*n if cleared else [0x6a7a4b]*n),(sp,hex(a),flag)
            assert result['x',0x1400]==fx
            assert result['x',0x3fff]==result['x',0x4100]==[0x5a1234]
        print('PASS early boot clears only shared metadata; first-pass private clearing preserves all Grid FX buffers and relocation guards')
    # Use the actual stage-loaded program, not just regenerated candidates.
    reference,_=POOL.run((0,),bounded=True,host_mailbox=True)
    original=P.code
    try:
        P.code=lambda **kwargs:(copy.deepcopy(segs),copy.deepcopy(g['pool']))
        with CURRENT.allocated():
            relocated,meta=POOL.run((0,),bounded=True,host_mailbox=True)
            assert relocated==reference and any(relocated[0])
            assert sum(meta['live_grains'])<=16
            _,meta=POOL.run((0,),bounded=True,host_mailbox=True,rebalance=True)
            for frame in range(POOL.FRAMES):
                active=8 if 24<=frame<48 else 1
                counts=meta['block_counts'][frame*8:frame*8+active]
                assert max(counts)<=16//active and sum(counts)<=16,(frame,counts)
    finally:P.code=original
    print('PASS actual staged renderer: relocated nonzero audio matches prior engine bit-for-bit; shared grain cap holds through 1/8/1 active tracks')
    print('LIMIT DSP execution tests; hardware audio continuity and deadlines remain unverified')
    print('ALL PASS')
if __name__=='__main__':main()
