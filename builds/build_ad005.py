"""AD005 volatile one-lane proof: recording no longer suspends first playback."""
import os
os.environ['RH_AUTOPROT']='1'
from pathlib import Path
import build_a0120 as baseline
import autoprot
NAME='AD005'
def build(name=NAME):
 b=baseline.build(name);b.add('autoprot',autoprot,fix_record_touch=True);return b
def main():
 out=build().finish(Path(__file__).resolve().parents[1]/'firmware'/NAME.lower())
 for f in out.glob(f'circuitrhythm-5706-{NAME}.*'):f.replace(out/f'rhythmplus-{NAME}{f.suffix}')
if __name__=='__main__':main()
