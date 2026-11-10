"""AD001: A0120 plus opt-in ITCM/decoder diagnostics; no automation feature yet."""
from pathlib import Path
import build_a0120 as baseline
import acdiag

NAME = 'AD001'


def build(name=NAME):
    b = baseline.build(name)
    b.add('acdiag', acdiag)
    return b


def main():
    out = build().finish(Path(__file__).resolve().parents[1] / 'firmware' / NAME.lower())
    for f in out.glob(f'circuitrhythm-5706-{NAME}.*'):
        f.replace(out / f'rhythmplus-{NAME}{f.suffix}')


if __name__ == '__main__':
    main()
