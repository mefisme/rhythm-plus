"""Run the existing DSP proofs at explicit candidate integration addresses."""
from pathlib import Path
import importlib
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('tests','tools','modules','remix/tools')]
import granular_layout as L
import granular_route_candidate as R
import granular_snapshot_candidate as S


def main():
    report=json.loads((ROOT/'firmware/a0122/manifest.json').read_text())['report']
    regions=L.validate(report)
    for forbidden in ('envexp','granchain','autobank','autoprot'):
        try:L.validate({**report,forbidden:{}})
        except ValueError:pass
        else:raise AssertionError(forbidden)
    original=(R.CONTROL,S.SNAPSHOT,S.SAVE)
    with L.allocated():
        assert (R.CONTROL,S.SNAPSHOT,S.SAVE)==(0x37400,0x37420,0x1f80)
        for name in ('ack','snapshot','notes','flow','inplace','pool'):
            print('ALLOCATED PROOF:',name,flush=True)
            importlib.import_module('emu_granular_'+name).main()
    assert (R.CONTROL,S.SNAPSHOT,S.SAVE)==original
    print(f'PASS {len(regions)} explicit regions fit A0122 private memory ledger; incompatible legacy engines/diagnostics rejected')
    print('PASS actual DSP proof suite at candidate shared/private addresses; generator relocation restored afterward')
    print('LIMIT: shared-tail static candidate based on stock/upstream layout; real concurrency, startup and pack lifecycle still need integration and hardware validation')


if __name__=='__main__':main()
