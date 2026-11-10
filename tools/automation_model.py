"""Host-only Track+ event-pool reference. No device/filesystem integration.

The default bank is a *candidate* budget, not verified hardware ownership.
This models capacity and atomic step edits, not a real-time scheduler.
"""
from dataclasses import dataclass, field
import struct
import zlib

PATTERNS = 64
EVENTS_PER_BLOCK = 24
WORDS_PER_BLOCK = 32
NUMERIC = frozenset(range(29)) - {5, 6, 10, 12, 15, 18, 21}
GRANULAR = frozenset(range(32, 44))  # Reserved; explicitly opt in for modelling.
MAGIC = b"RPAUTO01"
HEADER = struct.Struct("<8sHHHHII16sI")
DIRECTORY = struct.Struct("<HBB2s8s2xI4x")


class CapacityError(ValueError):
    pass


@dataclass(frozen=True, order=True)
class Event:
    position: int
    destination: int
    value: int
    kind: int = 0  # 0 continuous; 1 lock. Other types reserved.

    def word(self):
        if not (0 <= self.position < 192 and 0 <= self.destination < 64
                and 0 <= self.value < 16384 and self.kind in (0, 1)):
            raise ValueError("invalid event")
        if self.kind == 1 and self.position % 6:
            raise ValueError("step locks require microstep zero")
        return (self.position | self.destination << 8 | self.value << 14
                | self.kind << 28)

    @classmethod
    def decode(cls, word):
        if not 0 <= word < (1 << 30):
            raise ValueError("unsupported event flags")
        result = cls(word & 255, word >> 8 & 63, word >> 14 & 16383,
                     word >> 28 & 3)
        result.word()
        return result


def pack_block(events):
    """Exactly 24 records -> 32 full-width DSP words, least-significant first."""
    if len(events) != EVENTS_PER_BLOCK:
        raise ValueError("expected a full block")
    bits = sum(event.word() << (32 * i) for i, event in enumerate(events))
    return [(bits >> (24 * i)) & 0xffffff for i in range(WORDS_PER_BLOCK)]


def unpack_block(words):
    if len(words) != WORDS_PER_BLOCK or any(not 0 <= w <= 0xffffff for w in words):
        raise ValueError("invalid DSP block")
    bits = sum(word << (24 * i) for i, word in enumerate(words))
    return [Event.decode(bits >> (32 * i) & 0xffffffff)
            for i in range(EVENTS_PER_BLOCK)]


@dataclass
class Pattern:
    events: dict = field(default_factory=dict)  # (position,destination) -> Event
    continuous: set = field(default_factory=set)
    locks: set = field(default_factory=set)
    generation: int = 0
    minimum_blocks: int = 1

    @property
    def blocks(self):
        return max(self.minimum_blocks, (len(self.events) + 23) // 24)


class Bank:
    def __init__(self, payload_blocks=224, allowed=NUMERIC, minimum_blocks=1):
        if minimum_blocks not in (1, 2) or not 64 * minimum_blocks <= payload_blocks <= 224:
            raise ValueError("bank must fund the minimum without exceeding ceiling")
        self.payload_blocks = payload_blocks
        self.minimum_blocks = minimum_blocks
        self.allowed = frozenset(allowed)
        if not self.allowed <= (NUMERIC | GRANULAR):
            raise ValueError("destination profile includes unimplemented settings")
        self.patterns = [Pattern(minimum_blocks=minimum_blocks) for _ in range(PATTERNS)]

    @property
    def used_blocks(self):
        # Minimum blocks are reserved even for empty patterns.
        return sum(pattern.blocks for pattern in self.patterns)

    def _pattern(self, index):
        if not 0 <= index < PATTERNS:
            raise ValueError("invalid pattern")
        return self.patterns[index]

    def _commit(self, index, events, continuous, locks):
        old = self._pattern(index)
        # Empty destinations release their slots; no permanently orphaned lanes.
        present = {event.destination for event in events.values()}
        continuous = set(continuous) & present
        locks = set(locks) & present
        if continuous & locks:
            raise ValueError("destination already uses another recording mode")
        if len(continuous) > 2 or len(locks) > 8:
            raise CapacityError("destination slots full")
        for key, event in events.items():
            event.word()
            if key != (event.position, event.destination):
                raise ValueError("event key mismatch")
            if event.destination not in self.allowed:
                raise ValueError("unavailable destination")
            if event.destination not in (locks if event.kind else continuous):
                raise ValueError("event type does not match destination mode")
        candidate = Pattern(dict(events), continuous, locks,
                            (old.generation + 1) & 0xffffffff, self.minimum_blocks)
        if candidate.blocks > 16:
            raise CapacityError("pattern event limit reached")
        if self.used_blocks - old.blocks + candidate.blocks > self.payload_blocks:
            raise CapacityError("shared event pool full")
        if (old.events == candidate.events and old.continuous == continuous
                and old.locks == locks):
            return
        self.patterns[index] = candidate

    def lock_step(self, index, step, values):
        if not 0 <= step < 32:
            raise ValueError("invalid step")
        old = self._pattern(index)
        events = dict(old.events)
        locks = set(old.locks)
        for destination, value in values.items():
            if destination in old.continuous:
                raise ValueError("continuous destination requires point editing")
            key = (step * 6, destination)
            if value is None:
                events.pop(key, None)
            else:
                events[key] = Event(step * 6, destination, value, 1)
                locks.add(destination)
        self._commit(index, events, old.continuous, locks)

    def record_step(self, index, step, taken, points):
        """Commit a complete post-interpolation stock-style overdub step.

        points maps (destination,microstep) to a value; absent points on taken
        destinations erase older points. Untaken destinations remain untouched.
        Caller supplies ownership and interpolation; failure changes nothing.
        """
        if not 0 <= step < 32:
            raise ValueError("invalid step")
        taken = set(taken)
        if not taken <= self.allowed:
            raise ValueError("unavailable destination")
        old = self._pattern(index)
        if taken & old.locks:
            raise ValueError("step-lock destination requires explicit mode conversion")
        events = {key: event for key, event in old.events.items()
                  if not (event.destination in taken and event.position // 6 == step)}
        for (destination, micro), value in points.items():
            if destination not in taken or not 0 <= micro < 6:
                raise ValueError("point outside captured step")
            event = Event(step * 6 + micro, destination, value)
            events[event.position, destination] = event
        self._commit(index, events, old.continuous | taken, old.locks)

    def clear(self, index, destination=None):
        old = self._pattern(index)
        events = {} if destination is None else {
            key: event for key, event in old.events.items()
            if event.destination != destination}
        self._commit(index, events, old.continuous, old.locks)

    def dump(self, identity, generation=0):
        """Portable snapshot, NOT atomic pairing with stock's project save."""
        if len(identity) != 16 or not 0 <= generation <= 0xffffffff:
            raise ValueError("invalid snapshot identity or generation")
        descriptors, records = bytearray(), bytearray()
        for pattern in self.patterns:
            c, l = sorted(pattern.continuous), sorted(pattern.locks)
            descriptors += DIRECTORY.pack(len(pattern.events), len(c), len(l),
                                          bytes(c).ljust(2, b"\xff"),
                                          bytes(l).ljust(8, b"\xff"), pattern.generation)
            records += b"".join(struct.pack("<I", event.word())
                                for event in sorted(pattern.events.values()))
        payload = descriptors + records
        header = HEADER.pack(MAGIC, 2, self.payload_blocks, self.minimum_blocks, 0,
                             generation, len(payload), identity, 0)
        crc = zlib.crc32(header[:-4] + payload)
        return header[:-4] + struct.pack("<I", crc) + payload

    @classmethod
    def load(cls, data, identity, allowed=NUMERIC):
        if len(data) < HEADER.size or len(identity) != 16:
            raise ValueError("truncated header or invalid identity")
        magic, version, blocks, minimum, flags, generation, size, owner, crc = HEADER.unpack_from(data)
        if magic != MAGIC or version != 2 or flags or owner != identity:
            raise ValueError("incompatible or wrong-project snapshot")
        bank = cls(blocks, allowed, minimum)
        payload = data[HEADER.size:]
        if (size != len(payload) or size < 64 * DIRECTORY.size
                or size > 64 * DIRECTORY.size + blocks * 24 * 4
                or zlib.crc32(data[:HEADER.size - 4] + payload) != crc):
            raise ValueError("invalid snapshot length/checksum")
        cursor = 64 * DIRECTORY.size
        for index in range(PATTERNS):
            offset = index * DIRECTORY.size
            count, nc, nl, cs, ls, pg = DIRECTORY.unpack_from(payload, offset)
            if (nc > 2 or nl > 8 or count > 384 or cursor + count * 4 > size
                    or any(payload[offset + i] for i in (14, 15, 20, 21, 22, 23))
                    or cs[nc:] != b"\xff" * (2 - nc)
                    or ls[nl:] != b"\xff" * (8 - nl)):
                raise ValueError("invalid pattern descriptor")
            continuous, locks = set(cs[:nc]), set(ls[:nl])
            if (len(continuous) != nc or len(locks) != nl
                    or not (continuous | locks) <= bank.allowed):
                raise ValueError("invalid destination list")
            events = {}
            for _ in range(count):
                event = Event.decode(struct.unpack_from("<I", payload, cursor)[0])
                cursor += 4
                key = event.position, event.destination
                if key in events:
                    raise ValueError("duplicate event")
                events[key] = event
            bank._commit(index, events, continuous, locks)
            if (bank.patterns[index].continuous != continuous
                    or bank.patterns[index].locks != locks):
                raise ValueError("orphan destination")
            bank.patterns[index].generation = pg
        if cursor != size:
            raise ValueError("trailing snapshot bytes")
        return bank, generation


class StockTiming:
    """Read original 5706 ROM tables, never invent substitute time divisions."""
    def __init__(self, firmware):
        base = 0x08010000
        self.lengths = struct.unpack_from("<8I", firmware, 0x08068d9c - base)
        self.microsteps = firmware[0x0806651c-base:0x0806651c-base+192]
        self.weights = firmware[0x0806645c-base:0x0806645c-base+192]
        if self.lengths != (2, 3, 4, 6, 8, 12, 16, 24):
            raise ValueError("unsupported stock timing tables")

    def validate(self, rate, step, pulse):
        if not (0 <= rate < 8 and 0 <= step < 32
                and 0 <= pulse < self.lengths[rate]):
            raise ValueError("invalid sequencer position")


class SparsePlayer:
    """One destination's stock-style held/last state, driven by sparse events.

    Pattern routing, transitions, observers and manual DSP conversion are outside
    this reference. A manual move does not reset held/last; stop resets both.
    """
    def __init__(self, timing):
        self.timing = timing
        self.held = self.last = None

    def stop(self):
        self.held = self.last = None

    def value(self, pattern, destination, rate, step, pulse, next_value):
        t = self.timing
        t.validate(rate, step, pulse)

        def cell(micro):
            event = pattern.events.get((step*6 + micro, destination))
            return None if event is None else event.value

        value = None
        if rate < 4:
            value = cell(t.microsteps[rate*24+pulse])
        else:
            micro = pulse*6 // t.lengths[rate]
            left = cell(micro)
            right = cell(micro+1) if micro < 5 else next_value
            if left is not None:
                if right is not None:
                    offset = (rate-4)*48 + pulse*2
                    a, b = t.weights[offset:offset+2]
                    value = (left*a + right*b) >> 3
                elif pulse == 0 or (pulse-1)*6 // t.lengths[rate] != micro:
                    value = left
        if value is None:
            value = self.held
        self.held = None
        if rate < 3:
            micro = (pulse*3+2 if rate == 0 else pulse*2+1 if rate == 1
                     else 1 if pulse == 0 else 4 if pulse == 2 else 192)
            if micro < 6:
                self.held = cell(micro)
            if rate == 0 and self.held is None:
                self.held = cell(pulse*3+1)
        return value

    def tick(self, pattern, destination, rate, step, pulse, next_value):
        value = self.value(pattern, destination, rate, step, pulse, next_value)
        changed = value is not None and value != self.last
        self.last = value
        return value if changed else None
