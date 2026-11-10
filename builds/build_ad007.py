"""AD007: audited one-lane prototype plus opt-in larger-bank/codec/timing proof."""
import os
os.environ['RH_AUTOPROT']='1'
os.environ['RH_AUTOBANK']='1'
from pathlib import Path
import build_a0120 as baseline
import autoprot
import autobank
NAME='AD007'


def build(name=NAME):
    b=baseline.build(name)
    b.add('autoprot',autoprot,fix_record_touch=True,audit_batch=True,import_locks=True)
    b.add('autobank',autobank)
    return b


def main():
    out=build().finish(Path(__file__).resolve().parents[1]/'firmware'/NAME.lower())
    for f in out.glob(f'circuitrhythm-5706-{NAME}.*'):
        f.replace(out/f'rhythmplus-{NAME}{f.suffix}')


if __name__=='__main__':
    main()
