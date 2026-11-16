"""A0207: A0206 behavior; Shift + turn fine Position, Size and Scan."""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    subprocess.run([sys.executable,str(ROOT/'tools/build_granular_current.py'),
        '--base=a0192','--name=a0207','--pack-core1','--connect-arm',
        '--knob-pages','--companion-settings','--steady-track','--track-view-colors',
        '--remember-views','--reverse-cycle','--editor-settings','--trim-unused',
        '--dspzip','--fine-controls','--release'],cwd=ROOT,check=True)
