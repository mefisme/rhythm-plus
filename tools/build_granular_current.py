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
PACK_FILES='--pack-files' in sys.argv
if PACK_FILES:os.environ['RH_PACK_FILES']='1'
if '--pack-names' in sys.argv:os.environ['RH_PACK_FILES']='2'
NO_A3='--no-k13-automation' in sys.argv
if '--no-drone' in sys.argv:os.environ['RH_NO_DRONE']='1'
if '--control-page' in sys.argv:os.environ['RH_GFX_CPAGE']='1'
if '--mixer-shift' in sys.argv:os.environ['RH_GFX_MIXSHIFT']='1'
if '--plus-usb' in sys.argv:os.environ['RH_PLUS_USB']='1'
if '--file-tools' in sys.argv:os.environ['RH_FILETOOLS']='1'
if '--dup-hold' in sys.argv:os.environ['RH_FT_HOLD']='1'
if '--px-colour' in sys.argv:os.environ['RH_PX_COLOUR']='1'
if '--px-name' in sys.argv:os.environ['RH_PX_NAME']='1'
if '--dsp-rc' in sys.argv:os.environ['RH_DSP_RC']='1'
if '--scan-home' in sys.argv:os.environ['RH_GRANULAR_SCAN_HOME']='1'
if '--steady-switch' in sys.argv:os.environ['RH_GRANULAR_STEADY_SWITCH']='1'
if '--mode-fade' in sys.argv:os.environ['RH_GRANULAR_MODE_FADE']='1'
if '--scan-clock' in sys.argv:os.environ['RH_SCAN_CLOCK']='1'
if '--scan-centre' in sys.argv:os.environ['RH_GRANULAR_SCAN_CENTRE']='1'
if '--scan-lock' in sys.argv:os.environ['RH_SCAN_LOCK']='1'
if '--scan-each' in sys.argv:os.environ['RH_GRANULAR_SCAN_EACH']='1'
if '--each-tags' in sys.argv:os.environ['RH_GRANULAR_SCAN_EACH_TAGS']='1'
if '--sample-hide' in sys.argv:os.environ['RH_GRANULAR_SAMPLE_HIDE']='1'
if '--off-match' in sys.argv:os.environ['RH_STRETCH_OFF_MATCH']='1'
if '--ft-buttons' in sys.argv:os.environ['RH_FT_BUTTONS']='1'
if '--oneshot-scan' in sys.argv:os.environ['RH_GRANULAR_ONESHOT_SCAN']='1'
if '--oneshot-scan2' in sys.argv:os.environ['RH_GRANULAR_ONESHOT_SCAN']='2'
if '--load-direct' in sys.argv:os.environ['RH_GRANULAR_LOAD_DIRECT']='1'
if '--load-direct2' in sys.argv:os.environ['RH_GRANULAR_LOAD_DIRECT']='2'
if '--load-direct3' in sys.argv:os.environ['RH_GRANULAR_LOAD_DIRECT']='3'
if '--load-direct4' in sys.argv:os.environ['RH_GRANULAR_LOAD_DIRECT']='4'
if '--load-direct5' in sys.argv:os.environ['RH_GRANULAR_LOAD_DIRECT']='5'
if '--load-times' in sys.argv:os.environ['RH_GRANULAR_LOAD_TIMES']='1'
if '--leave-queue' in sys.argv:os.environ['RH_GRANULAR_LEAVE_QUEUE']='3'
if '--replace-ack' in sys.argv:os.environ['RH_GRANULAR_REPLACE_ACK']='1'
if '--leave-fade' in sys.argv:os.environ['RH_GRANULAR_LEAVE_FADE']='200'
if '--route-sweep' in sys.argv:os.environ['RH_GRANULAR_ROUTE_SWEEP']='1'
if '--carry' in sys.argv:os.environ['RH_GRANULAR_CARRY']='1'
if '--soft-leave' in sys.argv:os.environ['RH_GRANULAR_SOFT_LEAVE']='1'
if '--keep-choke' in sys.argv:os.environ['RH_GRANULAR_KEEP_CHOKE']='1'
if '--load-busy' in sys.argv:os.environ['RH_GRANULAR_LOAD_BUSY']='1'
if '--drain-idle' in sys.argv:os.environ['RH_STRETCH_DRAIN_IDLE']='1'
if '--stretch-handoff' in sys.argv:os.environ['RH_GRANULAR_STRETCH_HANDOFF']='1'
if '--no-pvloop' in sys.argv:os.environ['RH_NO_PVLOOP']='1'
if '--sm-stock' in sys.argv:os.environ['RH_SM_STOCK']='1'
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
    fill_gaps = '--fill-dsp-gaps' in sys.argv
    if fill_gaps and (not CONNECT or '--dsp-pack' not in sys.argv or '--release' in sys.argv):
        raise ValueError('--fill-dsp-gaps requires connected Granular, DSP packing and offline output')
    with CURRENT.allocated(),B.builders(packed='--pack-core1' in sys.argv):
        b=build(NAME.upper(),granular_stage=True)
    if '--no-easy-start' in sys.argv:
        import noeasystart
        noeasystart.free(b)
    if not NO_A3:b.add('automation3',automation3,cow=True)
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
        if fill_gaps:
            import dsppack
            dsppack.install(b.img,b.report)
            holes = b.report['dsppack']['holes']
            # Use the retired core-0 stream and leave the first gap to File Tools and Stretch.
            gap_index = 2
            start, end = (int(value, 16) for value in holes[gap_index][:2])
            cursor = start

        def install_adapter(name, module, **options):
            nonlocal cursor
            if not fill_gaps:
                module.install(b.img,b.report,b.next_base(),**options)
                return
            address = (cursor + 15) & ~15
            module.install(b.img,b.report,address,placement_end=end,**options)
            cursor = address + b.report['granular'][name]['bytes']

        install_adapter('bridge',granular_bridge,current=True)
        install_adapter('ui',granular_ui,persist=False,current=True,page_pad=GRANULAR_PAD,pages=PAGES,track_views=TRACK_VIEWS,reverse_cycle=REVERSE_CYCLE,editor_settings=EDITOR_SETTINGS,no_burst=NO_BURST,shift_tap=SHIFT_TAP)
        install_adapter('lifecycle',granular_lifecycle,persist=False,companion=STORE)
        if fill_gaps:
            holes[gap_index] = [hex(cursor), hex(end), end - cursor]
            b.report['flash_gap_placement'] = dict(start=hex(start), end=hex(cursor), adapters=['bridge','ui','lifecycle'])
        if STRETCH and '--scan-lock' not in sys.argv:
            import stretch_arm
            stretch_arm.install(b.img,b.report,b.next_base())
    with CURRENT.allocated():L.validate(b.report)
    assert len(b.img)<=0x70000,hex(len(b.img))
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
    if os.environ.get('RH_GRANULAR_SCAN_HOME')=='1':g['scan_home']=dict(default=64,field13_bit=15)
    if os.environ.get('RH_GRANULAR_STEADY_SWITCH')=='1':g['steady_switch']=True
    if os.environ.get('RH_GRANULAR_MODE_FADE')=='1':g['mode_fade']=True
    if os.environ.get('RH_GRANULAR_SCAN_CENTRE')=='1':g['scan_centre']=dict(knobs=[63,65])
    if os.environ.get('RH_GRANULAR_SCAN_EACH')=='1':g['scan_each']=dict(setting_bit=4,settings_pads=dict(scan_length=20,gap=21,bounce=22,freeze=23,pitch_set=24),sample_mode_pads=[18,19,20])
    if os.environ.get('RH_GRANULAR_ONESHOT_SCAN') in ('1','2'):g['oneshot_scan']=True
    if os.environ.get('RH_GRANULAR_LEAVE_QUEUE'):g['leave_queue_ms']=int(os.environ['RH_GRANULAR_LEAVE_QUEUE'])
    if os.environ.get('RH_GRANULAR_REPLACE_ACK')=='1':g['replace_ack']=True
    if os.environ.get('RH_GRANULAR_LEAVE_FADE'):g['leave_fade_ms']=int(os.environ['RH_GRANULAR_LEAVE_FADE'])
    if os.environ.get('RH_GRANULAR_ROUTE_SWEEP')=='1':g['route_sweep']=True
    if os.environ.get('RH_GRANULAR_CARRY')=='1':g['carry']=True
    if os.environ.get('RH_GRANULAR_SOFT_LEAVE')=='1':g['soft_leave']=True
    if os.environ.get('RH_GRANULAR_KEEP_CHOKE')=='1':g['keep_choke']=True
    if os.environ.get('RH_GRANULAR_LOAD_BUSY')=='1':g['load_busy']=True
    if os.environ.get('RH_STRETCH_DRAIN_IDLE')=='1':g['stretch_drain_idle']=True
    if os.environ.get('RH_GRANULAR_STRETCH_HANDOFF')=='1':g['stretch_handoff']=True
    if os.environ.get('RH_GRANULAR_LOAD_TIMES')=='1':g['load_times']=dict(at=hex(int(b.report['granular']['bridge']['slot'],16)+472),bytes=8)
    if os.environ.get('RH_GRANULAR_LOAD_DIRECT'):g['load_direct']=True if os.environ['RH_GRANULAR_LOAD_DIRECT']=='1' else int(os.environ['RH_GRANULAR_LOAD_DIRECT'])
    if STICKY_ASSIGN:g['ui']['sticky_assign']=True
    if ZONE_PADS:g['easy_zones'].update(slices=[0]*8+[2]*8+[n for n in (3,4,6,8,12,16,32) for _ in range(16)],slice_word=7,zone_pads=True)
    if TRIM_UNUSED:b.report['unused_code_trim']=dict(policy='preserve exposed adapters; discard unreachable helpers',reference='A0204',recovered_bytes=1328)
    if '--dsp-pack' in sys.argv and not fill_gaps:
        import dsppack
        dsppack.install(b.img,b.report)
    if '--file-tools' in sys.argv:
        import filetools
        filetools.install(b.img,b.report)
    if STRETCH and '--scan-lock' in sys.argv:
        assert '--dsp-pack' in sys.argv
        import stretch_arm
        stretch_arm.install(b.img,b.report)
    if '--no-easy-start' in sys.argv:
        noeasystart.check(b.img,len(b.stock))
    if '--release' in sys.argv:
        assert NAME in ('a0193','a0194','a0195','a0196','a0197','a0198','a0199','a0200','a0201','a0202','a0203','a0204','a0205','a0206','a0207','a0208','a0209','a0210','a0211','a0212','a0213','a0214','a0215','a0216','a0217','a0218','a0219','a0220','a0221','a0222','a0223','a0224','a0225','a0226','a0227','a0228','a0229','a0230','a0231','a0232','a0233','a0234','a0235','a0236','a0237','a0238','a0239','a0240','a0241','a0242','a0243','a0244','a0245','a0246','a0247','a0248','a0249','a0250','a0251','a0252','a0253','a0254','a0255','a0256','a0257','a0258','a0259','a0260','a0261','a0262','a0263','a0264','a0265','a0266','a0267','a0268','a0269','a0270','a0271','a272','a273','a274','a275','a276') and BASE=='a0192' and CONNECT and PAGES and STORE
        out=b.finish(ROOT/'buildtmp'/'release'/NAME)
        for f in out.glob(f'circuitrhythm-5706-{NAME.upper()}.*'):f.replace(out/f'rhythmplus-{NAME.upper()}{f.suffix}')
        keep_released(out,ROOT/'firmware'/NAME)
        return
    folder=ROOT/'firmware'/NAME;folder.mkdir(exist_ok=True)
    raw=bytes(b.img);(folder/f'rhythmplus-{NAME.upper()}.bin').write_bytes(raw)
    m=dict(marker=NAME.upper(),offline_only=True,flashable=False,image_size=hex(len(raw)),
        image_sha256=hashlib.sha256(raw).hexdigest(),free_to_0x70000=hex(0x70000-len(raw)),report=b.report)
    (folder/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    print(json.dumps({k:v for k,v in m.items() if k!='report'},indent=2))
def keep_released(out,folder):
    """A committed build is never replaced by a different image: its folder changes only when the image is the same."""
    import subprocess
    new=json.loads((out/'manifest.json').read_text())['image_sha256']
    shown=subprocess.run(['git','show',f'HEAD:firmware/{folder.name}/manifest.json'],cwd=ROOT,capture_output=True,text=True)
    if shown.returncode==0:
        old=json.loads(shown.stdout)['image_sha256']
        if old!=new:raise SystemExit(f'{folder.name} is released and this image differs ({new[:16]} != {old[:16]}); firmware/{folder.name} is unchanged, the new build is in {out}')
    folder.mkdir(parents=True,exist_ok=True)
    for f in out.iterdir():f.replace(folder/f.name)
if __name__=='__main__':main()
