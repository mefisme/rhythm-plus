"""A276: A275 with Sample mode pads 18-20 shown whether Granular is on or off."""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    offline_gap_build = '--fill-dsp-gaps' in sys.argv
    name = 'gap276' if offline_gap_build else 'a276'
    output_flags = ['--fill-dsp-gaps'] if offline_gap_build else ['--release']
    subprocess.run([sys.executable,str(ROOT/'tools/build_granular_current.py'),
        '--base=a0192',f'--name={name}','--pack-core1','--connect-arm',
        '--knob-pages','--companion-settings','--steady-track','--track-view-colors',
        '--remember-views','--editor-settings','--trim-unused',
        '--dspzip','--fine-controls','--fine-all','--no-burst','--turn-bar','--dark-spare','--granular-pad=26','--easy-zones','--stock-bar','--zone-pads','--full-freeze','--c0-idle','--stretch','--track-wipe','--pack-files','--pack-names','--no-k13-automation','--no-drone','--control-page','--mixer-shift','--plus-usb','--oneshot-scan2','--load-direct5','--replace-ack','--leave-fade','--route-sweep','--carry','--soft-leave','--keep-choke','--load-busy','--drain-idle','--stretch-handoff','--no-pvloop','--sm-stock','--dsp-pack','--file-tools','--dup-hold','--ft-buttons','--px-colour','--px-name','--no-easy-start','--dsp-rc','--scan-home','--steady-switch','--mode-fade','--scan-clock','--scan-centre','--scan-lock','--scan-each','--each-tags','--off-match',*output_flags],cwd=ROOT,check=True)
