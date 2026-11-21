"""A0267: A0266 with Scan centred by default (centred Scan holds the playhead at Position) and a steady Granular on/off pad."""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    subprocess.run([sys.executable,str(ROOT/'tools/build_granular_current.py'),
        '--base=a0192','--name=a0267','--pack-core1','--connect-arm',
        '--knob-pages','--companion-settings','--steady-track','--track-view-colors',
        '--remember-views','--editor-settings','--trim-unused',
        '--dspzip','--fine-controls','--fine-all','--no-burst','--turn-bar','--dark-spare','--granular-pad=26','--easy-zones','--stock-bar','--zone-pads','--full-freeze','--c0-idle','--stretch','--track-wipe','--pack-files','--pack-names','--no-k13-automation','--no-drone','--control-page','--mixer-shift','--plus-usb','--oneshot-scan2','--load-direct5','--replace-ack','--leave-fade','--route-sweep','--carry','--soft-leave','--keep-choke','--load-busy','--drain-idle','--stretch-handoff','--no-pvloop','--sm-stock','--dsp-pack','--file-tools','--dup-hold','--ft-buttons','--px-colour','--px-name','--no-easy-start','--dsp-rc','--scan-home','--steady-switch','--release'],cwd=ROOT,check=True)
