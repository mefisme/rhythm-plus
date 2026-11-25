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
if '--clear-save' in sys.argv:os.environ['RH_CLEAR_SAVE']='1'
if '--internal-plus' in sys.argv:os.environ['RH_INTERNAL_PLUS']='1'
if '--internal-keep' in sys.argv:os.environ['RH_INTERNAL_KEEP']='1'
if '--quantize' in sys.argv:os.environ['RH_QUANTIZE']='1'
if '--quantize-flash' in sys.argv:os.environ['RH_QUANTIZE_FLASH']='1'
if '--scrub-any' in sys.argv:os.environ['RH_SCRUB_ANY']='1'
if '--scrub-knobs' in sys.argv:os.environ['RH_SCRUB_KNOBS']='1'
if '--scrub-lights' in sys.argv:os.environ['RH_SCRUB_LIGHTS']='1'
if '--cues' in sys.argv:os.environ['RH_CUES']='1'
if '--cues2' in sys.argv:os.environ['RH_CUES']='2'
if '--stretch-gap' in sys.argv:os.environ['RH_FT_END']='1'
if '--k1-edge' in sys.argv:os.environ['RH_K1_EDGE']='1'
if '--cue-plus' in sys.argv:os.environ['RH_CUE_PLUS']='1'
if '--cue-latch' in sys.argv:os.environ['RH_CUE_LATCH']='1'
if '--latch-tap' in sys.argv:os.environ['RH_LATCH_TAP']='1'
if '--cue-tune' in sys.argv:os.environ['RH_CUE_TUNE']='1'
if '--cue-auto' in sys.argv:os.environ['RH_CUE_AUTO']='1'
if '--cue-peek' in sys.argv:os.environ['RH_CUE_PEEK']='1'
if '--cue-loop' in sys.argv:os.environ['RH_CUE_LOOP']='1'
if '--cue-sync' in sys.argv:os.environ['RH_CUE_SYNC']='1'
if '--cue-down' in sys.argv:os.environ['RH_CUE_DOWN']='1'
if '--cue-k1' in sys.argv:os.environ['RH_CUE_K1']='1'
if '--cue-speed' in sys.argv:os.environ['RH_CUE_SPEED']='1'
if '--cue-home' in sys.argv:os.environ['RH_CUE_HOME']='1'
if '--cue-v3' in sys.argv:os.environ['RH_CUE_V3']='1'
if '--cue-cols' in sys.argv:os.environ['RH_CUE_COLS']='1'
if '--cue-one' in sys.argv:os.environ['RH_CUE_ONE']='1'
if '--cue-pass' in sys.argv:os.environ['RH_CUE_PASS']='1'
if '--cue-tap' in sys.argv:os.environ['RH_CUE_TAP']='1'
if '--cue-home1' in sys.argv:os.environ['RH_CUE_HOME1']='1'
if '--cue-bar' in sys.argv:os.environ['RH_CUE_BAR']='1'
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
if '--ft-gap' in sys.argv:os.environ['RH_FT_GAP']='1'
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
if '--pitch-dsp-probe' in sys.argv:
    os.environ['RH_PITCH_DSP_PROBE']='1'
if '--ring-dsp-probe' in sys.argv:
    os.environ['RH_RING_DSP_PROBE']='1'
if '--read-v11' in sys.argv:
    os.environ['RH_READ_V11']='1'
if '--scan-dsp-probe' in sys.argv:
    os.environ['RH_SCAN_DSP_PROBE']='1'
import core0
base_module=importlib.import_module('build_'+BASE)
build,automation3,heldlocks,storageshadow,sdyield_rp,heldlights,automation3_ops=(getattr(base_module,n) for n in
    ('build','automation3','heldlocks','storageshadow','sdyield_rp','heldlights','automation3_ops'))
import granular_current_layout as CURRENT
import granular_layout as L
import granular_bundle as B

def main():
    filter_dsp_probe = '--filter-dsp-probe' in sys.argv
    pitch_dsp_probe = '--pitch-dsp-probe' in sys.argv
    ring_dsp_probe = '--ring-dsp-probe' in sys.argv
    read_v11 = '--read-v11' in sys.argv
    scan_dsp_probe = '--scan-dsp-probe' in sys.argv
    if scan_dsp_probe and not (ring_dsp_probe and read_v11):
        raise ValueError('Scan shares the FX page with Ring Mod and its settings buffer')
    if '--release' in sys.argv and scan_dsp_probe != (NAME in ('a301','a302','a303','a304','a305','a306','a307','a308','a309','a310','a311','a312','a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')):
        raise ValueError('The Scan build requires an A-series Scan marker')
    if read_v11 and not ring_dsp_probe:
        raise ValueError('Reading GS v11 requires the Ring Mod editor')
    if '--release' in sys.argv and read_v11 != (NAME in ('a300','a301','a302','a303','a304','a305','a306','a307','a308','a309','a310','a311','a312','a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')):
        raise ValueError('Unexpected GS v11 read setting for this release')
    if ring_dsp_probe and (not pitch_dsp_probe or '--fill-dsp-gaps' not in sys.argv):
        raise ValueError('Ring Mod requires Pitch and packed gap placement')
    if '--release' in sys.argv and ring_dsp_probe != (NAME in ('a295','a296','a297','a298','a299','a300','a301','a302','a303','a304','a305','a306','a307','a308','a309','a310','a311','a312','a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')):
        raise ValueError('The Ring Mod build requires an A-series Ring Mod marker')
    if pitch_dsp_probe and not filter_dsp_probe:
        raise ValueError('Pitch requires the shared Filter editor')
    if '--release' in sys.argv and pitch_dsp_probe != (NAME in ('a289','a290','a291','a292','a293','a294','a295','a296','a297','a298','a299','a300','a301','a302','a303','a304','a305','a306','a307','a308','a309','a310','a311','a312','a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')):
        raise ValueError('The Pitch build requires an A-series Pitch build marker')
    if '--release' in sys.argv and filter_dsp_probe != (NAME in ('a278','a279','a280','a281','a282','a283','a284','a285','a286','a287','a288','a289','a290','a291','a292','a293','a294','a295','a296','a297','a298','a299','a300','a301','a302','a303','a304','a305','a306','a307','a308','a309','a310','a311','a312','a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')):
        raise ValueError('The Filter hardware candidate requires an A-series Filter build marker')
    if filter_dsp_probe:
        os.environ['RH_FILTER_EDITOR_PROBE']='1'
    fill_gaps = '--fill-dsp-gaps' in sys.argv
    if fill_gaps and (not CONNECT or '--dsp-pack' not in sys.argv):
        raise ValueError('--fill-dsp-gaps requires connected Granular and DSP packing')
    if '--release' in sys.argv and fill_gaps != (NAME in ('g276t','a277','a278','a279','a280','a281','a282','a283','a284','a285','a286','a287','a288','a289','a290','a291','a292','a293','a294','a295','a296','a297','a298','a299','a300','a301','a302','a303','a304','a305','a306','a307','a308','a309','a310','a311','a312','a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')):
        raise ValueError('Unexpected DSP gap placement setting for this release')
    with CURRENT.allocated(),B.builders(packed='--pack-core1' in sys.argv,filter_dsp_probe=filter_dsp_probe,pitch_dsp_probe=pitch_dsp_probe,ring_dsp_probe=ring_dsp_probe,scan_dsp_probe=scan_dsp_probe):
        b=build(NAME.upper(),granular_stage=True)
    if ring_dsp_probe:
        import dspmap
        assert not dspmap.overlaps(dspmap.regions(b.report))
    if '--no-easy-start' in sys.argv:
        import noeasystart
        noeasystart.free(b)
    if '--easy-gaps' in sys.argv:           # heldlocks and heldlights in Easy Start's freed code
        assert '--no-easy-start' in sys.argv
        import rhbuild
        rhbuild.PLACE.update({'heldlocks#0': noeasystart.HOLES[0][0], 'heldlights#0': noeasystart.HOLES[1][0]})
    if not NO_A3:b.add('automation3',automation3,cow=True)
    b.add('heldlocks',heldlocks)
    b.add('automation3_ops',automation3_ops)
    b.add('heldlights',heldlights)
    if '--easy-gaps' in sys.argv:
        for tag, (lo, hi) in (('heldlocks#0', noeasystart.HOLES[0]), ('heldlights#0', noeasystart.HOLES[1])):
            assert b.sizes[tag] <= hi - lo, f'{tag} does not fit its gap'
        b.report['noeasystart']['used'] = {tag: b.sizes[tag] for tag in ('heldlocks#0', 'heldlights#0')}
    if CONNECT:
        from build_granular_owner import build as owner
        import granular_bridge,granular_ui,granular_lifecycle
        import rhstate
        at=b.next_base(4);compiled=owner(at,pages=PAGES,page_pad=GRANULAR_PAD,assign=True,state_address=rhstate.ST+rhstate.OFF['granular'][0],storage_address=rhstate.ST+rhstate.OFF['storageshadow'][0],held_address=int(b.report['tmenu']['labels']['c_tmheld'],16),menu_pulse=STEADY,view_colors=TRACK_VIEWS,remember_views=REMEMBER_VIEWS,reverse_cycle=REVERSE_CYCLE,editor_settings=EDITOR_SETTINGS,menu_address=int(b.report['tmenu']['slot'],16),trim_unused=TRIM_UNUSED,fine_controls=FINE,fine_all=FINE_ALL,no_burst=NO_BURST,turn_bar=TURN_BAR,dark_spare=DARK_SPARE,easy_zones=EASY_ZONES,stock_bar=STOCK_BAR,zone_pads=ZONE_PADS,full_freeze=FULL_FREEZE,shift_tap=SHIFT_TAP,sticky_assign=STICKY_ASSIGN,stretch_on=rhstate.ST+rhstate.OFF['stretch'][0] if STRETCH else 0)
        code=Path(compiled['binary']).read_bytes()
        b.img+=b'\xff'*(at-0x08010000-len(b.img))+code
        while len(b.img)%4:b.img.append(255)
        b.report['granular']['arm_kernel']=compiled
    if ring_dsp_probe:
        import dsppack
        dsppack.install(b.img,b.report)
        hole=b.report['dsppack']['holes'][0]
        start,end=(int(value,16) for value in hole[:2])
        address=(start+3)&~3
        storageshadow.install(b.img,b.report,address,offload=True,automation=True,placement_end=end)
        cursor=(address+b.report['storageshadow']['code_bytes']+3)&~3
        hole[:]=[hex(cursor),hex(end),end-cursor]
        b.report['storage_gap_placement']=dict(start=hex(address),end=hex(cursor))
    else:
        b.add('storageshadow',storageshadow,offload=True,automation=True)
    if '--sd-gap' not in sys.argv:
        b.add('sdyield',sdyield_rp,magic=0x31464f53)
    if CONNECT:
        import granular_lanes
        granular_lanes.install(b.img,b.report,b.next_base())
        if fill_gaps:
            import dsppack
            if not ring_dsp_probe:
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
            stretch_arm.install(b.img,b.report,None if '--stretch-gap' in sys.argv else b.next_base())   # None: the first gap
    if '--release' in sys.argv and (('--internal-keep' in sys.argv) != (NAME in ('a305','a306','a307','a308','a309','a310','a311','a312','a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--quantize' in sys.argv) != (NAME in ('a305','a306','a307','a308','a309','a310','a311','a312','a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--quantize-flash' in sys.argv) != (NAME in ('a306','a307','a308','a309','a310','a311','a312','a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--scrub-any' in sys.argv) != (NAME in ('a307','a308','a309','a310','a311','a312','a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--scrub-knobs' in sys.argv) != (NAME in ('a308','a309','a310','a311','a312','a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--scrub-lights' in sys.argv) != (NAME in ('a309','a310','a311','a312','a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--cues' in sys.argv) != (NAME in ('a310',)) or ('--cues2' in sys.argv) != (NAME in ('a311','a312','a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--mm-gap' in sys.argv) != (NAME in ('a311','a312','a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--stretch-gap' in sys.argv) != (NAME in ('a311','a312','a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--k1-edge' in sys.argv) != (NAME in ('a312','a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--cue-plus' in sys.argv) != (NAME in ('a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--cue-latch' in sys.argv) != (NAME in ('a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--latch-tap' in sys.argv) != (NAME in ('a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--cue-tune' in sys.argv) != (NAME in ('a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--cue-auto' in sys.argv) != (NAME in ('a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--cue-peek' in sys.argv) != (NAME in ('a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--cue-loop' in sys.argv) != (NAME in ('a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--cue-sync' in sys.argv) != (NAME in ('a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--cue-down' in sys.argv) != (NAME in ('a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--cue-k1' in sys.argv) != (NAME in ('a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--cue-speed' in sys.argv) != (NAME in ('a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--cue-home' in sys.argv) != (NAME in ('a321','a322','a323','a324','a325','a326','a327','a328','a329')) or ('--cue-v3' in sys.argv) != (NAME in ('a322','a323','a324','a325','a326','a327','a328','a329')) or ('--cue-cols' in sys.argv) != (NAME in ('a323','a324','a325','a326','a327','a328','a329')) or ('--cue-one' in sys.argv) != (NAME in ('a324','a325','a326','a327','a328','a329')) or ('--cue-pass' in sys.argv) != (NAME in ('a325','a326','a327','a328','a329')) or ('--cue-tap' in sys.argv) != (NAME in ('a326','a327','a328','a329')) or ('--cue-home1' in sys.argv) != (NAME in ('a327','a328','a329')) or ('--cue-bar' in sys.argv) != (NAME in ('a328','a329')) or ('--easy-gaps' in sys.argv) != (NAME in ('a328','a329')) or ('--ft-gap' in sys.argv) != (NAME in ('a329',)) or ('--sd-gap' in sys.argv) != (NAME in ('a329',))):
        raise ValueError('Unexpected internal keep or quantize setting for this release')
    if '--release' in sys.argv and ('--internal-plus' in sys.argv) != (NAME in ('a304','a305','a306','a307','a308','a309','a310','a311','a312','a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')):
        raise ValueError('Unexpected internal pack Plus setting for this release')
    if '--release' in sys.argv and ('--clear-save' in sys.argv) != (NAME in ('a303','a304','a305','a306','a307','a308','a309','a310','a311','a312','a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')):
        raise ValueError('Unexpected Clear + Save setting for this release')
    if '--release' in sys.argv and ('--midi-merge' in sys.argv) != (NAME in ('a302','a303','a304','a305','a306','a307','a308','a309','a310','a311','a312','a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329')):
        raise ValueError('Unexpected MIDI merge setting for this release')
    if '--midi-merge' in sys.argv:
        import midimerge
        if '--mm-gap' in sys.argv:          # in the granular adapters' gap, after them
            gap=b.report['dsppack']['holes'][2];at=(int(gap[0],16)+15)&~15;end=int(gap[1],16)
            midimerge.install(b.img,b.report,at)
            after=(at+b.report['midimerge']['bytes']+3)&~3;assert after<=end,'MIDI Merge does not fit the gap'
            gap[:]=[hex(after),hex(end),end-after]
        else:
            midimerge.install(b.img,b.report,b.next_base())
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
    if filter_dsp_probe:
        b.report['storageshadow'].update(granular_settings_version=7,granular_read_versions=[2,3,4,5,6,7],granular_settings_bytes=336,max_bundle_bytes=5120)
        b.report['filter_cutoff'].update(editor_pad=28,page_rgb=0x0088dd,granular_rgb=0x9eff59,itcm_start=0x3500,itcm_bytes=160)
        g['ui'].update(reverse_cycle=True,cycle_across_knob_groups=True,shift_opens_settings=False)
    if pitch_dsp_probe:
        b.report['storageshadow'].update(granular_settings_version=8,granular_read_versions=[2,3,4,5,6,7,8],granular_settings_bytes=385,max_bundle_bytes=5169)
        b.report['pitch_envelope_dsp'].update(settings_itcm_start=0x35a0,settings_itcm_bytes=192,editor_pad=29,page_rgb=0xffad20)
    if ring_dsp_probe:
        b.report['storageshadow'].update(granular_settings_version=10,granular_read_versions=[2,3,4,5,6,7,8,9,10],granular_settings_bytes=406,max_bundle_bytes=5190)
        if read_v11:
            b.report['storageshadow'].update(granular_read_versions=[2,3,4,5,6,7,8,9,10,11],max_bundle_bytes=5254,settings_buffer_itcm_start=0x3700)
        b.report['ring_mod_dsp'].update(editor_pad=31,page_rgb=0xd04080,settings_itcm_start=0x3660,settings_itcm_bytes=68)
        if scan_dsp_probe:
            b.report['storageshadow'].update(granular_settings_version=12,granular_read_versions=[2,3,4,5,6,7,8,9,10,11,12],granular_settings_bytes=423)
            b.report['ring_mod_dsp'].update(editor_pad=30,page_rgb=0x4000dd,settings_itcm_bytes=160)
            b.report['scan_dsp'].update(knobs=[3,4],settings_pad=18,granular='Position')
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
    if '--file-tools' in sys.argv and '--ft-gap' not in sys.argv:
        import filetools
        filetools.install(b.img,b.report)
    if '--sd-gap' in sys.argv:              # sdyield in the second gap that dsppack leaves
        import rhbuild
        gap=b.report['dsppack']['holes'][1];at=(int(gap[0],16)+3)&~3;end=int(gap[1],16)
        rhbuild.PLACE['sdyield#0']=at
        b.add('sdyield',sdyield_rp,magic=0x31464f53)
        after=(at+b.sizes['sdyield#0']+3)&~3;assert after<=end,'sdyield does not fit the gap'
        gap[:]=[hex(after),hex(end),end-after]
    if STRETCH and '--scan-lock' in sys.argv:
        assert '--dsp-pack' in sys.argv
        import stretch_arm
        stretch_arm.install(b.img,b.report)
    if '--ft-gap' in sys.argv:              # after stretch, in the rest of the first gap
        assert '--file-tools' in sys.argv
        import filetools
        filetools.install(b.img,b.report)
    if '--no-easy-start' in sys.argv:
        from build_granular_owner import thumb_instruction
        instruction_maps = [ROOT / b.report['gfxmix']['instruction_map']]
        if filter_dsp_probe:
            instruction_maps.append(Path(compiled['binary']).with_suffix('.elf'))

        def check_instruction(address, instruction):
            return any(thumb_instruction(path, address, instruction) for path in instruction_maps)

        noeasystart.check(b.img, len(b.stock), check_instruction, placed=b.placed)
    if '--release' in sys.argv:
        assert NAME in ('a0193','a0194','a0195','a0196','a0197','a0198','a0199','a0200','a0201','a0202','a0203','a0204','a0205','a0206','a0207','a0208','a0209','a0210','a0211','a0212','a0213','a0214','a0215','a0216','a0217','a0218','a0219','a0220','a0221','a0222','a0223','a0224','a0225','a0226','a0227','a0228','a0229','a0230','a0231','a0232','a0233','a0234','a0235','a0236','a0237','a0238','a0239','a0240','a0241','a0242','a0243','a0244','a0245','a0246','a0247','a0248','a0249','a0250','a0251','a0252','a0253','a0254','a0255','a0256','a0257','a0258','a0259','a0260','a0261','a0262','a0263','a0264','a0265','a0266','a0267','a0268','a0269','a0270','a0271','a272','a273','a274','a275','a276','g276t','a277','a278','a279','a280','a281','a282','a283','a284','a285','a286','a287','a288','a289','a290','a291','a292','a293','a294','a295','a296','a297','a298','a299','a300','a301','a302','a303','a304','a305','a306','a307','a308','a309','a310','a311','a312','a313','a314','a315','a316','a317','a318','a319','a320','a321','a322','a323','a324','a325','a326','a327','a328','a329') and BASE=='a0192' and CONNECT and PAGES and STORE
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
