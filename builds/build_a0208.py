"""A0208: A0207 behavior; no Burst; fine adjust on six primary knobs."""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    subprocess.run([sys.executable,str(ROOT/'tools/build_granular_current.py'),
        '--base=a0192','--name=a0208','--pack-core1','--connect-arm',
        '--knob-pages','--companion-settings','--steady-track','--track-view-colors',
        '--remember-views','--reverse-cycle','--editor-settings','--trim-unused',
        '--dspzip','--fine-controls','--fine-all','--no-burst','--release'],cwd=ROOT,check=True)
