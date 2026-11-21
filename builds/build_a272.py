"""A272: A0271 with Scan length per sample (Granular settings pad 20, Sample mode pad 20), and Textured / Triggered and Retrigger on Sample mode pads 18 and 19."""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    subprocess.run([sys.executable,str(ROOT/'tools/build_granular_current.py'),
        '--base=a0192','--name=a272','--pack-core1','--connect-arm',
        '--knob-pages','--companion-settings','--steady-track','--track-view-colors',
        '--remember-views','--editor-settings','--trim-unused',
        '--dspzip','--fine-controls','--fine-all','--no-burst','--turn-bar','--dark-spare','--granular-pad=26','--easy-zones','--stock-bar','--zone-pads','--full-freeze','--c0-idle','--stretch','--track-wipe','--pack-files','--pack-names','--no-k13-automation','--no-drone','--control-page','--mixer-shift','--plus-usb','--oneshot-scan2','--load-direct5','--replace-ack','--leave-fade','--route-sweep','--carry','--soft-leave','--keep-choke','--load-busy','--drain-idle','--stretch-handoff','--no-pvloop','--sm-stock','--dsp-pack','--file-tools','--dup-hold','--ft-buttons','--px-colour','--px-name','--no-easy-start','--dsp-rc','--scan-home','--steady-switch','--mode-fade','--scan-clock','--scan-centre','--scan-lock','--scan-each','--release'],cwd=ROOT,check=True)
