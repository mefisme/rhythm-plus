"""Host-only durable-first save coordinator with injected I/O results.

Models safety ordering, not FAT atomicity or actual firmware integration. A caller
must supply a consistent stock/automation snapshot and a fresh token. Existing
stock data is not submitted until the exact new sidecar is durably acknowledged.
"""
from dataclasses import dataclass
from enum import Enum,auto
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"modules"))
from project_layout import stamp_identity,read_identity,sidecar_identity
from automation_model import Bank


class State(Enum):
    IDLE=auto()
    EXTRA_WRITE=auto()
    EXTRA_SYNC=auto()
    STOCK_WRITE=auto()
    STOCK_SYNC=auto()
    COMPLETE=auto()
    FAILED=auto()


@dataclass(frozen=True)
class Request:
    kind: str
    token: bytes
    data: bytes=b""


class Save:
    def __init__(self,stock,bank,token,*,generation,used_tokens=()):
        try:current_token=read_identity(stock)
        except ValueError:current_token=None
        if token in used_tokens or current_token==token:
            raise ValueError("snapshot token already used")
        self.token=bytes(token)
        self.stock=stamp_identity(stock,self.token)
        self.extra=bank.dump(sidecar_identity(self.token),generation)
        self.generation=generation
        self.state=State.IDLE
        self.failure=None
        self.pending=None
        self.clean=False

    def begin(self):
        if self.state!=State.IDLE:
            raise ValueError("save already started")
        self.state=State.EXTRA_WRITE
        return self._request()

    def _request(self):
        kind={State.EXTRA_WRITE:"extra_write",State.EXTRA_SYNC:"extra_sync",
              State.STOCK_WRITE:"stock_write",State.STOCK_SYNC:"stock_sync"}[self.state]
        data=self.extra if self.state==State.EXTRA_WRITE else self.stock if self.state==State.STOCK_WRITE else b""
        self.pending=Request(kind,self.token,data)
        return self.pending

    def complete(self,request,*,status=0,transferred=0,snapshot_generation=None):
        if request is not self.pending or self.state in (State.COMPLETE,State.FAILED):
            raise ValueError("stale/duplicate save completion")
        self.pending=None
        if status or (request.kind.endswith("write") and transferred!=len(request.data)):
            self.failure=(request.kind,status,transferred)
            self.state=State.FAILED
            return None
        if self.state in (State.EXTRA_WRITE,State.EXTRA_SYNC) and snapshot_generation!=self.generation:
            self.failure=("snapshot_changed",self.generation,snapshot_generation)
            self.state=State.FAILED
            return None
        self.state={State.EXTRA_WRITE:State.EXTRA_SYNC,State.EXTRA_SYNC:State.STOCK_WRITE,
                    State.STOCK_WRITE:State.STOCK_SYNC,State.STOCK_SYNC:State.COMPLETE}[self.state]
        if self.state==State.COMPLETE:self.clean=snapshot_generation==self.generation
        return None if self.state==State.COMPLETE else self._request()


def load_pair(stock,sidecars,allowed=None):
    """Select only the sidecar identified by this loaded stock record.

    A torn/invalid stock file is outside this model: stock loader must validate it.
    Unknown/corrupt extra data returns a visible failure, never another generation.
    """
    try:
        token=read_identity(stock)
    except ValueError:
        return None,"corrupt_or_unsupported_identity"
    if token is None:
        return None,"legacy_or_missing_identity"
    data=sidecars.get(token)
    if data is None:
        return None,"missing_sidecar"
    try:
        bank,generation=Bank.load(data,sidecar_identity(token),**({} if allowed is None else {"allowed":allowed}))
    except ValueError:
        return None,"corrupt_or_wrong_sidecar"
    return (bank,generation),"loaded"
