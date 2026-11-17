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
TRIM_UNUSED='--trim-unused' in sys.argv
DSPZIP='--dspzip' in sys.argv
FINE='--fine-controls' in sys.argv
FINE_ALL='--fine-all' in sys.argv
NO_BURST='--no-burst' in sys.argv
TURN_BAR='--turn-bar' in sys.argv
DARK_SPARE='--dark-spare' in sys.argv
EASY_ZONES='--easy-zones' in sys.argv
STOCK_BAR='--stock-bar' in sys.argv
ZONE_PADS='--zone-pads' in sys.argv
FULL_FREEZE='--full-freeze' in sys.argv
SHIFT_TAP='--shift-tap' in sys.argv
STICKY_ASSIGN='--sticky-assign' in sys.argv
TRACK_WIPE='--track-wipe' in sys.argv
if TRACK_WIPE:os.environ['RH_TRACKWIPE']='1'
C0_IDLE='--c0-idle' in sys.argv
if C0_IDLE:os.environ['RH_C0IDLE']='1'
STRETCH='--stretch' in sys.argv
if STRETCH:os.environ['RH_STRETCH']='1'
if SHIFT_TAP:os.environ['RH_TPE_REVERSE_CYCLE']='1'
if ZONE_PADS:os.environ['RH_GRANULAR_SLICE_WORD7']='1'
if EASY_ZONES:os.environ['RH_GRANULAR_SLICE_SCATTER']='1'
# Pad index of the Granular parameter pad view: 31 is pad 32, 26 is pad 27.
GRANULAR_PAD=next((int(a.split('=',1)[1]) for a in sys.argv if a.startswith('--granular-pad=')),31)
assert GRANULAR_PAD in (26,31)
if FINE_ALL:FINE=True;os.environ['RH_GRANULAR_FINE_ALL']='1'
if NO_BURST:os.environ['RH_GRANULAR_NOBURST']='1'
if FINE:os.environ['RH_GRANULAR_FINE']='1'
if DSPZIP:os.environ['RH_DSPZIP']='1'
if TRIM_UNUSED:os.environ['RH_TRIM_UNUSED']='1'
if REVERSE_CYCLE:os.environ['RH_TPE_REVERSE_CYCLE']='1'
REMEMBER_VIEWS='--remember-views' in sys.argv
TRACK_VIEWS='--track-view-colors' in sys.argv
STEADY='--steady-track' in sys.argv
if STEADY:os.environ['RH_TPE_STEADY_TRACK']='1'
if STORE:os.environ['RH_GRANULAR_COMPANION']='1'
if CONNECT:os.environ.update(RH_GRANULAR='1',RH_GRANULAR_CURRENT_ARM='1')
# Bind the local adapter before upstream modules change their import paths.
sys.path.insert(0,str(ROOT/'modules'))
import core0
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
        at=b.next_base(4);compiled=owner(at,pages=PAGES,page_pad=GRANULAR_PAD,assign=True,state_address=rhstate.ST+rhstate.OFF['granular'][0],storage_address=rhstate.ST+rhstate.OFF['storageshadow'][0],held_address=int(b.report['tmenu']['labels']['c_tmheld'],16),menu_pulse=STEADY,view_colors=TRACK_VIEWS,remember_views=REMEMBER_VIEWS,reverse_cycle=REVERSE_CYCLE,editor_settings=EDITOR_SETTINGS,menu_address=int(b.report['tmenu']['slot'],16),trim_unused=TRIM_UNUSED,fine_controls=FINE,fine_all=FINE_ALL,no_burst=NO_BURST,turn_bar=TURN_BAR,dark_spare=DARK_SPARE,easy_zones=EASY_ZONES,stock_bar=STOCK_BAR,zone_pads=ZONE_PADS,full_freeze=FULL_FREEZE,shift_tap=SHIFT_TAP,sticky_assign=STICKY_ASSIGN,stretch_on=rhstate.ST+rhstate.OFF['stretch'][0] if STRETCH else 0)
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
        granular_ui.install(b.img,b.report,b.next_base(),persist=False,current=True,page_pad=GRANULAR_PAD,pages=PAGES,track_views=TRACK_VIEWS,reverse_cycle=REVERSE_CYCLE,editor_settings=EDITOR_SETTINGS,no_burst=NO_BURST,shift_tap=SHIFT_TAP)
        granular_lifecycle.install(b.img,b.report,b.next_base(),persist=False,companion=STORE)
        if STRETCH:
            import stretch_arm
            stretch_arm.install(b.img,b.report,b.next_base())
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
        g['movement_bar_feedback']=True
        g['lane_assignments']['storage']='GS v4 companion; automation values remain native'
        b.report['storageshadow'].update(granular_settings_version=4,granular_read_versions=[2,3,4],track_editor_settings=True)
    if FINE:
        assert EDITOR_SETTINGS and PAGES and STORE
        g['fine_controls']=dict(knobs=['Position','Size','Density','Scan','Position scatter','Pitch scatter'] if FINE_ALL else ['Position','Size','Scan'],page='primary',gesture='Shift + turn',steps_per_knob_step=16,recorded=False)
        g['lane_assignments']['storage']='GS v5 companion; automation values remain native'
        b.report['storageshadow'].update(granular_settings_version=5,granular_read_versions=[2,3,4,5],granular_settings_bytes=288,max_bundle_bytes=5072,settings_single_buffer=True)
    if NO_BURST:g['burst']=False;g['secondary_knobs']=['Level','Size scatter','Timing','Jitter','Slice','Lock']
    if TURN_BAR:g['ui']['turn_bar_ms']=500
    if DARK_SPARE:g['ui']['assign_dark_spare']=True
    if EASY_ZONES:g['easy_zones']=dict(timing_quarter_ticks=[24,16,12,8,6,4,3,2],slices=[0,2,3,4,6,8,12,16],lock=[0,96,127],slice_scatter=True)
    if STOCK_BAR:g['ui']['stock_bar']=True
    if FULL_FREEZE:g['full_freeze']=True
    if STICKY_ASSIGN:g['ui']['sticky_assign']=True
    if ZONE_PADS:g['easy_zones'].update(slices=[0]*8+[2]*8+[n for n in (3,4,6,8,12,16,32) for _ in range(16)],slice_word=7,zone_pads=True)
    if TRIM_UNUSED:b.report['unused_code_trim']=dict(policy='preserve exposed adapters; discard unreachable helpers',reference='A0204',recovered_bytes=1328)
    if '--release' in sys.argv:
        assert NAME in ('a0193','a0194','a0195','a0196','a0197','a0198','a0199','a0200','a0201','a0202','a0203','a0204','a0205','a0206','a0207','a0208','a0209','a0210','a0211','a0212','a0213','a0214','a0215','a0216','a0217','a0218','a0219','a0220','a0221','a0222','a0223','a0224','a0225','a0226','a0227','a0228','a0229','a0230','a0231','a0232','a0233') and BASE=='a0192' and CONNECT and PAGES and STORE
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
