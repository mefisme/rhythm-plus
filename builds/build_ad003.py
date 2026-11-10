"""AD003: bounded stock consecutive-read timing; same AD002 test windows."""
from pathlib import Path
import build_ad001 as baseline
import dsdiag
NAME='AD003'
def build(name=NAME):
    b=baseline.build(name)
    b.add('dsdiag',dsdiag,consecutive=True)
    return b
def main():
    out=build().finish(Path(__file__).resolve().parents[1]/'firmware'/NAME.lower())
    for f in out.glob(f'circuitrhythm-5706-{NAME}.*'):
        f.replace(out/f'rhythmplus-{NAME}{f.suffix}')
if __name__=='__main__':main()
