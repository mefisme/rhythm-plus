"""Offline relocation against A0185; leaves historical AG builders unchanged.

The current Grid FX controls own core0 X:1400..14BF. Keep the grain copy at
its existing X:1500 and relocate its 256-word working state to X:4000.
This is ledger ownership, not a new hardware canary result.
"""
from contextlib import contextmanager
from dataclasses import replace
import granular0 as G
import granular_layout as L
import granular_stock_controls as C
import granular_note_candidate as N

@contextmanager
def allocated():
    changes=[(G,k,getattr(G,k)+0x2c00) for k in ('GB','RNG','VS','GR0')]
    changes += [(C,k,getattr(C,k)+0x2c00) for k in
                ('LOCK_RNG','LOCK_STEP','LOCK_SEEDS','BURST_LEFT','BURST_GAP','BURST_RNG','BURST_PH')]
    # The current engine retains the native trigger, rather than the retired
    # Pitch+ trigger at E3A. Count accepted notes at the existing downstream call.
    changes += [(N,'NATIVE_TRIGGER',0x2fd)]
    old=[getattr(m,k) for m,k,v in changes];regions=L.REGIONS
    try:
        for m,k,v in changes:setattr(m,k,v)
        L.REGIONS=tuple(replace(r,start=0x4000) if r.core==0 and r.space=='x' and r.start==0x1400 else r
                        for r in regions)+(L.Region(0,'y',G.SAVE,24,'granular working register saves'),)
        with L.allocated():yield
    finally:
        L.REGIONS=regions
        for (m,k,v),value in zip(changes,old):setattr(m,k,value)
