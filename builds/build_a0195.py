"""A0194 plus active-page Shift settings/assignments; pad-hold entry retained.
Native sound-lane assignments; existing independent FX automation retained.
"""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    subprocess.run([sys.executable,str(ROOT/'tools/build_granular_current.py'),
        '--base=a0192','--name=a0195','--pack-core1','--connect-arm',
        '--knob-pages','--companion-settings','--release'],cwd=ROOT,check=True)
