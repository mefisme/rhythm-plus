"""Callback-driven host worker contract for project_sidecar_model snapshots.

No SD API installed. poll() only exposes one immutable request; submit it from a
storage task, then acknowledge the actual completion. Never call SD from a tick.
"""
from dataclasses import dataclass
from project_sidecar_model import HEADER, CELLS, load


@dataclass(frozen=True)
class Request:
    serial: int
    target: tuple
    kind: str
    operation: str
    offset: int
    data: bytes


class Worker:
    def __init__(self, snapshot, target):
        self.snapshot = snapshot
        self.target = tuple(target)  # Captured Save As destination, not current UI.
        self.files = (('companion', snapshot.companion), ('native', snapshot.native))
        self.file_index = self.offset = self.serial = 0
        self.phase = 'create'
        self.pending = None
        self.error = None
        self.trace = []

    @property
    def done(self):
        return self.phase == 'done'

    def poll(self, timestamp):
        if self.pending is not None or self.error or self.done:
            return None
        kind, data = self.files[self.file_index]
        operation = self.phase
        chunk = data[self.offset:self.offset + 512] if operation == 'write' else b''
        self.serial += 1
        self.pending = Request(self.serial, self.target, kind, operation, self.offset, chunk)
        self.trace.append((timestamp, 'submit', kind, operation, self.offset))
        return self.pending

    def complete(self, request, status, transferred, timestamp):
        if request is not self.pending or self.pending is None:
            raise ValueError('stale or foreign completion')
        self.trace.append((timestamp, 'complete', request.kind, request.operation, status, transferred))
        self.pending = None
        expected = len(request.data) if request.operation == 'write' else 0
        if status or transferred != expected:
            self.error = (status, transferred, expected)
            return
        if self.phase == 'create':
            # Companion must be exclusive-created. Native open semantics belong to
            # the original project-save path, which this harness does not replace.
            self.phase = 'write'
        elif self.phase == 'write':
            self.offset += transferred
            if self.offset == len(self.files[self.file_index][1]):
                self.phase = 'sync'
        elif self.phase == 'sync':
            self.phase = 'close'
        elif self.phase == 'close':
            self.file_index += 1
            self.offset = 0
            self.phase = 'done' if self.file_index == 2 else 'create'

    def clean(self, bank):
        return self.done and not self.error and bank.generation == self.snapshot.generation


class Loader:
    """Read a known-length companion and publish only after pair validation.

    Caller provides the unmodified native disk image, before stock normalization.
    The target tags the request; an abandoned loader cannot activate a new project.
    File open/size/close ownership remains the storage adapter's responsibility.
    """
    def __init__(self, native_disk_image, size, target):
        if size not in (HEADER.size + CELLS + 4, HEADER.size + CELLS + 104):
            raise ValueError('unexpected companion size')
        self.native = bytes(native_disk_image)
        self.size, self.target = size, tuple(target)
        self.buffer = bytearray()
        self.pending = self.result = self.error = None
        self.cancelled = False
        self.serial = 0
        self.trace = []

    def poll(self, timestamp):
        if self.pending is not None or self.cancelled or self.error or self.result is not None:
            return None
        self.serial += 1
        count = min(512, self.size - len(self.buffer))
        self.pending = Request(self.serial, self.target, 'companion', 'read',
                               len(self.buffer), bytes(count))
        self.trace.append((timestamp, 'read_submit', len(self.buffer), count))
        return self.pending

    def cancel(self):
        self.cancelled = True
        self.result = None

    def complete(self, request, status, data, timestamp):
        if request is not self.pending or self.pending is None:
            raise ValueError('stale or foreign completion')
        self.pending = None
        self.trace.append((timestamp, 'read_complete', request.offset, len(data), status))
        if self.cancelled:
            return
        if status or len(data) != len(request.data):
            self.error = 'read failed or short'
            return
        self.buffer.extend(data)
        if len(self.buffer) == self.size:
            try:
                result = load(self.native, bytes(self.buffer))
            except ValueError as error:
                self.error = str(error)
            else:
                self.result = result
                self.trace.append((timestamp, 'validated'))
