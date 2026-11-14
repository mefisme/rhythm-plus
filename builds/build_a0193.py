"""A0192 plus restored granular on pad 32, page-2 knobs and SD companion settings.
Native sound-lane assignments; existing independent FX automation retained.
"""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    subprocess.run([sys.executable,str(ROOT/'tools/build_granular_current.py'),
        '--base=a0192','--name=a0193','--pack-core1','--connect-arm',
        '--knob-pages','--companion-settings','--release'],cwd=ROOT,check=True)
