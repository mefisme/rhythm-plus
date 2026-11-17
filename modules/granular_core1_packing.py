"""Scoped placement of existing granular adapters; historical addresses restored."""
from contextlib import contextmanager
import granular_inplace_candidate as I
import granular_snapshot_candidate as S
import granular_note_candidate as N
import granular_flow_candidate as F

@contextmanager
def placed(start,stretch=True):
    fields=((I,'AT'),(I,'LOOP_NATIVE'),(I,'CLEAR_AT'),(S,'AT'),(S,'LIMIT'),(S,'EXPORT_POSITION'),(N,'AT'),(F,'AT'),(F,'DISPATCH'))
    previous=[getattr(m,k) for m,k in fields]
    try:
        I.AT=start;I.LOOP_NATIVE=S.EXPORT_POSITION=stretch
        _,route=I.code()
        I.CLEAR_AT=start+route['source_words']
        S.AT=I.CLEAR_AT+route['clear_words'];S.LIMIT=0x1000
        N.AT=S.AT+len(S.code()[0]);S.LIMIT=N.AT
        F.AT=N.AT+len(N.code()[0])
        F.DISPATCH=F.AT+len(F.code()[0])
        yield
    finally:
        for (module,key),value in zip(fields,previous):setattr(module,key,value)
