"""Offline GR001: current A0185 plus relocated granular DSP, no ARM UI/store.

Emits only an unmarked binary/manifest for emulation. Never SysEx or uploader.
"""
import hashlib,json,sys,importlib,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('builds','modules','tools','tests','remix/tools')]
BASE=next((a.split('=',1)[1] for a in sys.argv if a.startswith('--base=')),'a0185')
NAME=next((a.split('=',1)[1] for a in sys.argv if a.startswith('--name=')),'gr001')
CONNECT='--connect-arm' in sys.argv
PAGES='--knob-pages' in sys.argv
STORE='--companion-settings' in sys.argv
REVERSE_CYCLE='--reverse-cycle' in sys.argv
EDITOR_SETTINGS='--editor-settings' in sys.argv
if REVERSE_CYCLE:os.environ['RH_TPE_REVERSE_CYCLE']='1'
REMEMBER_VIEWS='--remember-views' in sys.argv
TRACK_VIEWS='--track-view-colors' in sys.argv
STEADY='--steady-track' in sys.argv
if STEADY:os.environ['RH_TPE_STEADY_TRACK']='1'
if STORE:os.environ['RH_GRANULAR_COMPANION']='1'
if CONNECT:os.environ.update(RH_GRANULAR='1',RH_GRANULAR_CURRENT_ARM='1')
base_module=importlib.import_module('build_'+BASE)
build,automation3,heldlocks,storageshadow,sdyield_rp,heldlights,automation3_ops=(getattr(base_module,n) for n in
    ('build','automation3','heldlocks','storageshadow','sdyield_rp','heldlights','automation3_ops'))
import granular_current_layout as CURRENT
import granular_layout as L
import granular_bundle as B

def main():
    with CURRENT.allocated(),B.builders(packed='--pack-core1' in sys.argv):
        b=build(NAME.upper(),granular_stage=True)
    b.add('automation3',automation3,cow=True)
    b.add('heldlocks',heldlocks)
    b.add('automation3_ops',automation3_ops)
    b.add('heldlights',heldlights)
    if CONNECT:
        from build_granular_owner import build as owner
        import granular_bridge,granular_ui,granular_lifecycle
        import rhstate
        at=b.next_base(4);compiled=owner(at,pages=PAGES,page_pad=31,assign=True,state_address=rhstate.ST+rhstate.OFF['granular'][0],storage_address=rhstate.ST+rhstate.OFF['storageshadow'][0],held_address=int(b.report['tmenu']['labels']['c_tmheld'],16),menu_pulse=STEADY,view_colors=TRACK_VIEWS,remember_views=REMEMBER_VIEWS,reverse_cycle=REVERSE_CYCLE,editor_settings=EDITOR_SETTINGS,menu_address=int(b.report['tmenu']['slot'],16))
        code=Path(compiled['binary']).read_bytes()
        b.img+=b'\xff'*(at-0x08010000-len(b.img))+code
        while len(b.img)%4:b.img.append(255)
        b.report['granular']['arm_kernel']=compiled
    b.add('storageshadow',storageshadow,offload=True,automation=True)
    b.add('sdyield',sdyield_rp,magic=0x31464f53)
    if CONNECT:
        import granular_lanes
        granular_lanes.install(b.img,b.report,b.next_base())
        granular_bridge.install(b.img,b.report,b.next_base(),current=True)
        granular_ui.install(b.img,b.report,b.next_base(),persist=False,current=True,pages=PAGES,track_views=TRACK_VIEWS,reverse_cycle=REVERSE_CYCLE,editor_settings=EDITOR_SETTINGS)
        granular_lifecycle.install(b.img,b.report,b.next_base(),persist=False,companion=STORE)
    with CURRENT.allocated():L.validate(b.report)
    assert len(b.img)<=0x70000
    g=b.report['granular'];g.update(scope='OFFLINE DSP-only: no ARM owner/UI or settings storage',
        base_build=BASE.upper(),manual_activation=False,old_project_codec_installed=False)
    if CONNECT:g.update(scope='Granular restored with companion settings and explicit native sound-lane assignments' if STORE else 'OFFLINE ARM controls/lifecycle connected; persistence disabled',manual_activation=True,automation=True,settings_companion=STORE,sd_packs_only=STORE,navigation_persistent=REMEMBER_VIEWS)
    if REVERSE_CYCLE:g['ui']['settings_cycle_forward']=True
    if REMEMBER_VIEWS:
        g['lane_assignments']['storage']='GS v3 companion; automation values remain native'
        b.report['storageshadow'].update(granular_settings_version=3,granular_read_versions=[2,3],navigation_bytes=8)
    if EDITOR_SETTINGS:
        g['lane_assignments']['storage']='GS v4 companion; automation values remain native'
        b.report['storageshadow'].update(granular_settings_version=4,granular_read_versions=[2,3,4],track_editor_settings=True)
    if '--release' in sys.argv:
        assert NAME in ('a0193','a0194','a0195','a0196','a0197','a0198','a0199','a0200','a0201') and BASE=='a0192' and CONNECT and PAGES and STORE
        out=b.finish(ROOT/'firmware'/NAME)
        for f in out.glob(f'circuitrhythm-5706-{NAME.upper()}.*'):f.replace(out/f'rhythmplus-{NAME.upper()}{f.suffix}')
        return
    folder=ROOT/'firmware'/NAME;folder.mkdir(exist_ok=True)
    raw=bytes(b.img);(folder/f'rhythmplus-{NAME.upper()}.bin').write_bytes(raw)
    m=dict(marker=NAME.upper(),offline_only=True,flashable=False,image_size=hex(len(raw)),
        image_sha256=hashlib.sha256(raw).hexdigest(),free_to_0x70000=hex(0x70000-len(raw)),report=b.report)
    (folder/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    print(json.dumps({k:v for k,v in m.items() if k!='report'},indent=2))
if __name__=='__main__':main()
