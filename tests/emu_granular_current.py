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
    if report.get('c0idle'):
        import c0idle
        allowed|={a+i for a,ws in c0idle.STOCK.items() for i in range(len(ws))}
        idle=int(report['c0idle']['at'],16)
        assert [actual[0x1ff],actual[0x200],actual[0x201]]==[0x0af0a9,idle,0],'idle counter branch'
    if report.get('ring_mod_dsp'):allowed|={0x225}
    assert all(actual[a]==w for a,w in old.items() if a not in allowed)
    assert actual[0x225]==int(report['ring_mod_dsp']['entry'] if report.get('ring_mod_dsp') else report['gfxsplit']['pre'],16)
    before=flat(rhdsp1.parse(rhdsp1.sent(bytearray(base),baseline['report'],'pitchmod'))[0])
    after=flat(rhdsp1.parse(rhdsp1.sent(bytearray(image),report,'pitchmod'))[0])
    from drone_gone import undrone
    before=undrone(before,baseline['report'],report)
    changed={0x122,0x23d,0x25c,0x25d,0x22f,0x230,0x231,0x232,0x233,0x2f3,0x4e6}
    if report.get('filter_cutoff'):
        import filter_cutoff
        changed|={filter_cutoff.LOWPASS_CALL}
    if report.get('pitch_envelope_dsp'):
        import pitch_envelope_dsp,pitchmod
        changed|={pitch_envelope_dsp.NOTE_CALL,pitchmod.P_RR_CALL}
    if report.get('scan_dsp'):
        import scan_dsp
        changed|={scan_dsp.TRIGGER}
    if 'pvloop' in baseline['report'] and 'pvloop' not in report:     # the stock preview player back in its place
        import pvloop as PV
        stock=flat(rhdsp1.parse(rhdsp1.sent(bytearray((ROOT/'remix/stock/circuitrhythm-firmware-5706-STOCK.bin').read_bytes()),baseline['report'],'pitchmod'))[0])
        room=set(range(PV.A1,PV.E1))|set(range(PV.A2,PV.E2))|{PV.CALL_PV,PV.CALL_ENV}
        assert all(after[a]==stock[a] for a in room)
        changed|=room
    if 'smswitch' in baseline['report'] and 'endfade' in report:      # no loop crossfade: Remix's XF / WC back to the stock's
        import loopxf as XF
        stock=flat(rhdsp1.parse(rhdsp1.sent(bytearray((ROOT/'remix/stock/circuitrhythm-firmware-5706-STOCK.bin').read_bytes()),baseline['report'],'pitchmod'))[0])
        room=set(range(XF.AT,XF.END))|set(range(XF.WC_AT,XF.WC_END))|{0x197,0x19f}
        assert all(after[a]==stock[a] for a in room),'the crossfade areas are not the stock code'
        lf=int(report['endfade']['loopfade'],16)
        changed|=room|set(range(lf,lf+14))
    bad=[hex(a) for a,w in before.items() if a not in changed and after.get(a)!=w]
    assert not bad,("core 1 words changed",bad[:12],len(bad))
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
            shared=0x37400<=a<0x37468
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
                if 0x37400<=a<0x37468:continue
                if a==B.FLAG:assert result[sp,a]==[1,0x1234];continue
                assert result[sp,a]==([0]*n if cleared else [0x6a7a4b]*n),(sp,hex(a),flag)
            assert result['x',0x1400]==fx
            assert result['x',0x3fff]==result['x',0x4100]==[0x5a1234]
        print('PASS early boot clears only shared metadata; first-pass private clearing preserves all Grid FX buffers and relocation guards')
    # Use the actual stage-loaded program, not just regenerated candidates.
    reference,_=POOL.run((0,),bounded=True,host_mailbox=True)
    # Fine builds take Position/Scan (and Density, both scatters) in sixteenths
    # and Size in samples. The pool fixture's 7-bit values, scaled, must render
    # identically, including against a reference engine that still has Burst.
    fine=bool(g.get('fine_controls'));every=fine and len(g['fine_controls']['knobs'])==6
    scaled={'size':G.tables()['SIZE_T'][35],'pos':42*16,'scan':48*16} if fine else None
    if every:
        scaled['dens']=55*16
        scattered,_=POOL.run((0,),bounded=True,host_mailbox=True,settings={'spr':20,'pspr':20})
    original=P.code
    try:
        P.code=lambda **kwargs:(copy.deepcopy(segs),copy.deepcopy(g['pool']))
        with CURRENT.allocated():
            relocated,meta=POOL.run((0,),bounded=True,host_mailbox=True,settings=scaled)
            assert relocated==reference and any(relocated[0])
            if fine:
                steps=[('pos',42*16+8),('scan',48*16+8),('size',(G.tables()['SIZE_T'][35]+G.tables()['SIZE_T'][36])//2)]
                if every:
                    base={**scaled,'spr':320,'pspr':320}
                    same,_=POOL.run((0,),bounded=True,host_mailbox=True,settings=base)
                    assert same==scattered,'scaled scatter words differ from the 7-bit engine'
                    steps+=[('dens',55*16+8)]
                for name,value in steps:
                    moved,_=POOL.run((0,),bounded=True,host_mailbox=True,settings={**scaled,name:value})
                    assert moved!=reference,('fine step did not reach the engine',name)
                if every:
                    for name in ('spr','pspr'):
                        moved,_=POOL.run((0,),bounded=True,host_mailbox=True,settings={**base,name:328})
                        assert moved!=scattered,('fine step did not reach the engine',name)
                print(f"PASS fine 0 renders bit-for-bit like the 7-bit engine; half-step {', '.join(g['fine_controls']['knobs'])} each change the audio")
            if g.get('easy_zones'):
                # Word 13: slices - 1 in bits 15..18, Lock in bits 8..14. 8 slices; scatter below one slice snaps to the playhead's slice.
                word7=g['easy_zones'].get('slice_word')==7
                def run(slices,spr=0,lock=0,step=0):
                    words={7:127|(slices-1)<<8|step<<13,13:lock<<8} if word7 else {13:(slices-1)<<15|lock<<8|step<<19}
                    return POOL.run((0,),bounded=True,host_mailbox=True,settings={**scaled,**words,'spr':spr})[0]
                sliced=run(8);assert any(sliced[0]) and sliced!=reference,'Slice did not change the audio'
                assert run(8,400)==sliced,'scatter below one slice moved the start in Slice mode'
                wide=run(8,2047);assert any(wide[0]) and wide!=sliced,'full scatter did not jump slices'
                assert run(8,2047,127)!=wide,'Lock did not reach Slice mode scatter'
                for step in (3,7):assert any(run(8,2047,0,step)[0]),('wrapped slice silent',step)
                if word7:
                    many=run(32);assert any(many[0]) and many!=run(16),'32 slices render like 16'
                    assert run(32,0,0,17)!=run(32,0,0,1),'slice step above 15 was cut to 4 bits'
                    assert any(run(32,2047,0,31)[0]),'last 32-slice step silent'
                print('PASS Slice mode: scatter below one slice keeps the slice; full scatter jumps whole slices and wraps; Lock repeats it'+('; 32 slices and steps above 16 play' if word7 else ''))
            assert sum(meta['live_grains'])<=16
            _,meta=POOL.run((0,),bounded=True,host_mailbox=True,rebalance=True,settings=scaled)
            for frame in range(POOL.FRAMES):
                active=8 if 24<=frame<48 else 1
                counts=meta['block_counts'][frame*8:frame*8+active]
                assert max(counts)<=16//active and sum(counts)<=16,(frame,counts)
    finally:P.code=original
    print('PASS actual staged renderer: relocated nonzero audio matches prior engine bit-for-bit; shared grain cap holds through 1/8/1 active tracks')
    print('LIMIT DSP execution tests; hardware audio continuity and deadlines remain unverified')
    print('ALL PASS')
if __name__=='__main__':main()
