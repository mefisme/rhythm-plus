"""Execute compacted core1 audio path and verify archived placements restore."""
import copy,json,sys
from contextlib import nullcontext
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('tools','modules','tests','remix/tools')]
import rhdsp1
import rhdsp
from build_dsp_fixture import build as build_fixture
import granular_route_reference as REF
import granular_inplace_candidate as I
import granular_core1_packing as PACK
import granular_current_layout as CURRENT
import granular_snapshot_candidate as S
import granular_note_candidate as N
import granular_flow_candidate as F

def artifact(name):
    folder=ROOT/'firmware'/name
    report=json.loads((folder/'manifest.json').read_text())['report']
    image=bytearray((folder/f'rhythmplus-{name.upper()}.bin').read_bytes())
    return rhdsp1.parse(rhdsp1.sent(image,report,'pitchmod'))[0],report.get('granular',{})

def main():
    old,g0=artifact('gr002');new,g1=artifact('gr003')
    assert g1['core1_packed'] and g1['core1_padding_words']==0
    assert int(g0['core1_end'],16)-int(g1['core1_end'],16)==280
    fields=lambda:(I.AT,I.CLEAR_AT,S.AT,S.LIMIT,N.AT,F.AT,F.DISPATCH)
    saved=fields()
    with CURRENT.allocated(),PACK.placed(int(g1['core1_start'],16)):
        assert I.AT==int(g1['core1_start'],16)
        generated,_=artifact('a0192')
        for name,module in (('route',I),('snapshot',S),('notes',N),('flow',F)):
            generated,meta=module.patched(generated)
            assert meta==g1['core1_stages'][name],name
        uploaded={a+i:w for sp,a,ws in new if sp=='p' for i,w in enumerate(ws)}
        expected={a+i:w for sp,a,ws in generated if sp=='p' for i,w in enumerate(ws)}
        assert uploaded==expected,'uploaded packed code differs from tested adapters'
    assert fields()==saved,'packed placement escaped its scoped context'
    # The route fixture isolates handoff from the separately tested snapshot/
    # flow scheduler. Full staged programs have different clear scheduling and
    # are not compatible with that fixture's opposite-bank assertion.
    import math
    source=[int(0x180000*math.sin(i*.09)) for i in range(320)]
    baseline,_=artifact('a0192')
    segment_fn=REF.segments
    REF.segments=lambda:copy.deepcopy(baseline)
    def run(g,bank,enabled):
        with PACK.placed(int(g['core1_start'],16)) if g.get('core1_packed') else nullcontext():
            return REF.render(source,enabled=enabled,in_place=True,bank=bank,
                              configs=[dict(lp=100,hp=0,resonance=10,distortion=0,slope=0)]*8)[0]
    original_tool=rhdsp.TOOL
    rhdsp.TOOL=str(build_fixture())
    try:
      with CURRENT.allocated():
            for bank in (0,1):
                for enabled in ((),(0,),(2,5),tuple(range(8))):
                    a=run(g0,bank,enabled);b=run(g1,bank,enabled)
                    assert a==b,(bank,enabled)
                    assert any(any(track) for track in a),'vacuous silent audio comparison'
    finally:
        REF.segments=segment_fn
        rhdsp.TOOL=original_tool
    print('PASS packed adapters match uploaded stages; zero padding; 280 core1 words recovered')
    print('PASS old/packed handoff with native shaping: both banks, disabled/single/mixed/all tracks, bit-identical nonzero audio')
    print('PASS historical placements restored after scoped generation')
    print('ALL PASS')
if __name__=='__main__':main()
