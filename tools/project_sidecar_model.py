"""Host prototype, not firmware: immutable RAM snapshots and acknowledged I/O.

Uses the sample writer's buffer ownership/order, not its WAV format. No physical
SD timing or native project-write atomicity is simulated here.
"""
import hashlib
import struct
import zlib

RECORD = 0x29484
TAIL = 0x29110
IDENTITY = TAIL + 276  # Current A0176 free range; 20 bytes.
STEP = TAIL + 404
CELLS = 3 * 8 * 32 * 6
HEADER = struct.Struct('<4s12sI32sII')


def step_valid(data):
    return (len(data) == 100 and data[:2] == b'SM' and data[3] == 2
            and data[2] == ((sum(data[4:]) ^ 0x5C) & 255))


class Bank:
    def __init__(self):
        self.data = bytearray([255]) * CELLS
        self.generation = 0

    def record(self, control, pattern, step, microstep, value):
        if not (0 <= control < 3 and 0 <= pattern < 8 and
                0 <= step < 32 and 0 <= microstep < 6 and 0 <= value < 128):
            raise ValueError('automation coordinate/value')
        self.data[((control * 8 + pattern) * 32 + step) * 6 + microstep] = value
        self.generation += 1


def snapshot(native, bank, token, *, offload=False):
    if len(native) != RECORD or len(token) != 12:
        raise ValueError('record/token size')
    old = native[IDENTITY:IDENTITY + 20]
    if old[:4] == b'RP\x01\x00' and old[4:16] == token:
        raise ValueError('fresh snapshot token required')
    stock = bytearray(native)
    settings = bytes(stock[STEP:STEP + 100]) if offload else b''
    if offload and not step_valid(settings):
        raise ValueError('invalid legacy Step Mutate settings')
    identity = b'RP\x01\x00' + token
    stock[IDENTITY:IDENTITY + 20] = identity + struct.pack('<I', zlib.crc32(identity))
    if offload:
        stock[STEP:STEP + 100] = bytes(100)
    stock = bytes(stock)
    payload = bytes(bank.data) + settings
    header = HEADER.pack(b'RPA1', token, bank.generation,
                         hashlib.sha256(stock).digest(), len(bank.data), len(settings))
    body = header + payload
    return stock, body + struct.pack('<I', zlib.crc32(body))


def load(native, companion):
    if len(native) != RECORD or len(companion) < HEADER.size + 4:
        raise ValueError('truncated project pair')
    identity = native[IDENTITY:IDENTITY + 20]
    if (identity[:4] != b'RP\x01\x00' or
            zlib.crc32(identity[:16]) != struct.unpack('<I', identity[16:])[0]):
        raise ValueError('invalid identity')
    magic, token, generation, digest, cells, settings_len = HEADER.unpack_from(companion)
    if (magic != b'RPA1' or token != identity[4:16] or cells != CELLS or
            settings_len not in (0, 100) or
            len(companion) != HEADER.size + cells + settings_len + 4 or
            hashlib.sha256(native).digest() != digest or
            zlib.crc32(companion[:-4]) != struct.unpack('<I', companion[-4:])[0]):
        raise ValueError('invalid or mismatched companion')
    data = companion[HEADER.size:HEADER.size + cells]
    if any(value > 127 and value != 255 for value in data):
        raise ValueError('invalid automation value')
    settings = companion[HEADER.size + cells:-4] if settings_len else native[STEP:STEP + 100]
    if settings_len and not step_valid(settings):
        raise ValueError('invalid offloaded settings')
    # Settings remain separate: never repopulate the reclaimed native region.
    return data, settings, generation


class Save:
    """Inject a worker performing write(kind, offset, immutable_bytes), sync(kind).

    Each write returns the completed byte count. Calls are completion events in
    this synchronous host harness; firmware must submit/yield/ack asynchronously.
    Worker must exclusively create a fresh companion; never overwrite old pairs.
    """
    def __init__(self, native, bank, token, *, offload=False):
        self.native, self.companion = snapshot(native, bank, token, offload=offload)
        self.generation = bank.generation

    def run(self, worker, bank):
        for kind, data in [('companion', self.companion), ('native', self.native)]:
            for offset in range(0, len(data), 512):
                chunk = data[offset:offset + 512]
                if worker.write(kind, offset, chunk) != len(chunk):
                    raise OSError('short write')
            worker.sync(kind)
        return bank.generation == self.generation
