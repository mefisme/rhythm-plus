"""AD004 volatile Track 1 Pattern 1 pitch envelope amount automation proof."""
import os
os.environ['RH_AUTOPROT']='1'
from pathlib import Path
import build_a0120 as baseline
import autoprot
NAME='AD004'
def build(name=NAME):
 b=baseline.build(name);b.add('autoprot',autoprot);return b
def main():
 out=build().finish(Path(__file__).resolve().parents[1]/'firmware'/NAME.lower())
 for f in out.glob(f'circuitrhythm-5706-{NAME}.*'):f.replace(out/f'rhythmplus-{NAME}{f.suffix}')
if __name__=='__main__':main()
