"""Create an offline DSP-integrated image; deliberately emits no flashable SysEx."""
from pathlib import Path
import hashlib
import json
import os
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('builds','modules','tools','remix/tools')]
# One-core test builds keep the A0122 main-chip code, so they leave the Granular RAM slot out.
CORE_ONLY={'AGC0':(0,),'AGC1':(1,)}
os.environ['RH_GRANULAR']='0' if CORE_ONLY.keys()&set(sys.argv) else '1'
SEEDS,PEND,SCN,VIEWS,BOUNCE,SHTRK,SHLED,CLRPG,SHMUT=('AG016','AG017','AG018'),('AG019',),('AG020',),('AG021',),('AG022',),('AG023',),('AG024',),('AG025',),('AG026',)
os.environ['RH_MUTSET']='11' if set(SHMUT)&set(sys.argv) else '10' if set(CLRPG)&set(sys.argv) else '9' if set(SHLED)&set(sys.argv) else '8' if set(SHTRK)&set(sys.argv) else '7' if set(BOUNCE)&set(sys.argv) else '6' if set(VIEWS)&set(sys.argv) else '5' if set(SCN)&set(sys.argv) else '4' if set(PEND)&set(sys.argv) else '3' if set(SEEDS)&set(sys.argv) else '2'
from build_a0121 import build as baseline
import granular_layout as L
import granular_bundle as B
from build_granular_owner import build as kernel
import granular_bridge
import granular_ui
import granular_lifecycle
import crashlog


FULL=('AG001','AG002','AG003','AG004','AG005','AG006','AG007','AG008','AG009','AG010','AG011','AG012','AG013','AG014','AG015')+SEEDS+PEND+SCN+VIEWS+BOUNCE+SHTRK+SHLED+CLRPG+SHMUT
DSP_ONLY,ARM_ONLY='AGDSP','AGARM'


def build(name='AG001'):
    with L.allocated():
        if name==ARM_ONLY:candidate=baseline(name=name,error_led=False)
        else:
            with B.builders(CORE_ONLY.get(name,(0,1))):candidate=baseline(name=name,error_led=False)
    if name in CORE_ONLY:return finish(name,candidate)
    L.validate(candidate.report)
    if name==DSP_ONLY:return finish(name,candidate)
    candidate.report.setdefault('granular',{})
    at=candidate.next_base(4);compiled=kernel(at)
    code=Path(compiled['binary']).read_bytes()
    candidate.img += b'\xff'*(at-0x08010000-len(candidate.img))+code
    while len(candidate.img)%4:candidate.img.append(255)
    assert len(candidate.img)<0x70000
    candidate.report['granular']['arm_kernel']=compiled
    granular_bridge.install(candidate.img,candidate.report,candidate.next_base())
    granular_ui.install(candidate.img,candidate.report,candidate.next_base())
    granular_lifecycle.install(candidate.img,candidate.report,candidate.next_base())
    if name=='AG013':crashlog.install(candidate.img,candidate.report,candidate.next_base())
    candidate.report['granular']['scope']='Offline integrated candidate: runtime, UI, project application and pack/sample replacement connected'
    return finish(name,candidate)


def finish(name,candidate):
    work=ROOT/'buildtmp/granular-stage';work.mkdir(parents=True,exist_ok=True)
    (work/'image.bin').write_bytes(candidate.img)
    report=dict(scope='OFFLINE STAGE: runtime, UI and lifecycle connected; validation incomplete, no SysEx',
        image_bytes=len(candidate.img),image_sha256=hashlib.sha256(candidate.img).hexdigest(),report=candidate.report)
    (work/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    # Existing regression tools take a firmware folder. This mirror still has
    # no SysEx and is explicitly marked offline, not an uploader release.
    checks=ROOT/'firmware'/name.lower();checks.mkdir(parents=True,exist_ok=True)
    (checks/f'rhythmplus-{name}.bin').write_bytes(candidate.img)
    (checks/'manifest.json').write_text(json.dumps({**report,'marker':name,'image_size':hex(len(candidate.img)),
        'free_to_0x70000':hex(0x70000-len(candidate.img))},indent=2)+'\n')
    return report


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name',choices=FULL+(DSP_ONLY,ARM_ONLY)+tuple(CORE_ONLY),default='AG001')
    result=build(parser.parse_args().name)
    print(json.dumps({key:result[key] for key in ('scope','image_bytes','image_sha256')},indent=2))
