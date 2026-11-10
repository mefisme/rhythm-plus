"""Host-only design proofs; run with Python's unittest, no firmware or unit I/O."""
import random
import struct
import sys
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from automation_model import (Bank, CapacityError, Event, NUMERIC, GRANULAR,
                              HEADER, DIRECTORY, pack_block, unpack_block,
                              SparsePlayer, StockTiming)
from automation_capacity import SCENARIOS, measure

IDENTITY = b"test-project-001"


class ModelTests(unittest.TestCase):
    def test_eight_track_and_chain_capacity(self):
        dense = SCENARIOS[1]
        self.assertFalse(measure(dense, 24, 2)["fits"])
        self.assertTrue(measure(dense, 24, 1)["fits"])
        self.assertEqual(measure(dense, 24, 1)["charged_blocks"], 184)
        self.assertFalse(measure(dense, 20, 1)["fits"])
        self.assertTrue(measure(SCENARIOS[0], 16, 1)["fits"])
        self.assertTrue(measure(SCENARIOS[6], 16, 1)["fits"])
        self.assertFalse(measure(SCENARIOS[-1], 24, 1)["fits"])

    def test_one_block_minimum_exact_capacity_and_snapshot(self):
        bank = Bank()
        for pattern in range(23):
            for step in range(32 if pattern < 22 else 28):
                bank.record_step(pattern, step, {4}, {(4, m): 8193 for m in range(6)})
        for pattern in range(23, 64):
            for step in range(24):
                bank.lock_step(pattern, step, {0: 12003})
        self.assertEqual(sum(len(p.events) for p in bank.patterns), 5376)
        self.assertEqual(bank.used_blocks, 224)
        before = bank.dump(IDENTITY)
        with self.assertRaises(CapacityError):
            bank.lock_step(63, 24, {0: 12003})
        self.assertEqual(bank.dump(IDENTITY), before)
        restored, _ = Bank.load(before, IDENTITY)
        self.assertEqual(restored.minimum_blocks, 1)
        self.assertEqual(restored.dump(IDENTITY), before)

    def test_full_width_codec(self):
        rng = random.Random(5706)
        for _ in range(1000):
            events = [Event(rng.randrange(192), rng.randrange(64),
                            rng.randrange(16384)) for _ in range(24)]
            self.assertEqual(events, unpack_block(pack_block(events)))
        edges = [Event(0, 0, 0, 1), Event(186, 63, 16383, 1),
                 Event(191, 63, 16383)] * 8
        self.assertEqual(edges, unpack_block(pack_block(edges)))
        with self.assertRaises(ValueError):
            Event.decode(1 << 30)
        with self.assertRaises(ValueError):
            Event(192, 1, 0).word()
        with self.assertRaises(ValueError):
            Event(1, 1, 0, 1).word()

    def fill_exact_bank(self):
        bank = Bank(minimum_blocks=2)
        # 16 dense lanes use the complete shared allowance: 16*(8-2)=96.
        for pattern in range(16):
            for step in range(32):
                bank.record_step(pattern, step, {4},
                                 {(4, micro): step * 6 + micro for micro in range(6)})
        # All other patterns can still use their guaranteed 48-event minimum.
        for pattern in range(16, 64):
            for step in range(24):
                bank.lock_step(pattern, step, {0: 0, 1: 16383})
        return bank

    def test_guaranteed_capacity_and_exact_ceiling(self):
        bank = self.fill_exact_bank()
        self.assertEqual(bank.used_blocks, 224)
        self.assertEqual(sum(len(p.events) for p in bank.patterns), 5376)
        before = bank.dump(IDENTITY)
        with self.assertRaises(CapacityError):
            bank.lock_step(63, 24, {0: 42})
        self.assertEqual(before, bank.dump(IDENTITY))
        bank.lock_step(63, 0, {0: 42})  # Replacement works without a new block.
        self.assertEqual(bank.patterns[63].events[0, 0].value, 42)
        bank.clear(0)
        self.assertEqual(bank.used_blocks, 218)
        bank.lock_step(63, 24, {0: 42})
        self.assertEqual(bank.used_blocks, 219)

    def test_record_step_is_atomic_at_exhaustion(self):
        bank = Bank()
        for step in range(32):
            bank.record_step(0, step, {4, 8},
                             {(d, m): 8193 for d in (4, 8) for m in range(6)})
        self.assertEqual(bank.patterns[0].blocks, 16)
        before = bank.dump(IDENTITY)
        with self.assertRaises(CapacityError):
            bank.lock_step(0, 0, {0: 7})
        self.assertEqual(before, bank.dump(IDENTITY))
        # Replace both taken lanes at a step, including all empty ticks.
        bank.record_step(0, 0, {4, 8}, {(4, 0): 0, (8, 5): 16383})
        self.assertEqual(len(bank.patterns[0].events), 374)

    def test_ownership_empty_ticks_and_loop_overwrite(self):
        bank = Bank()
        for step in range(32):
            bank.record_step(0, step, {4, 8},
                             {(d, m): 123 for d in (4, 8) for m in range(6)})
        old = bank.dump(IDENTITY)
        bank.record_step(0, 0, set(), {})  # Untaken input must not erase either lane.
        self.assertEqual(len(bank.patterns[0].events), 384)
        for step in range(32):
            bank.record_step(0, step, {4}, {(4, 0): step})
        self.assertEqual(len(bank.patterns[0].events), 224)
        self.assertEqual(sum(e.destination == 8 for e in bank.patterns[0].events.values()), 192)
        bank.record_step(0, 0, {4}, {})
        self.assertNotIn((0, 4), bank.patterns[0].events)
        self.assertNotEqual(old, bank.dump(IDENTITY))

    def test_slot_limits_and_explicit_modes(self):
        bank = Bank()
        bank.lock_step(0, 0, {d: 8193 for d in sorted(NUMERIC)[:8]})
        before = bank.dump(IDENTITY)
        with self.assertRaises(CapacityError):
            bank.lock_step(0, 1, {28: 100})
        with self.assertRaises(ValueError):
            bank.record_step(0, 0, {0}, {(0, 1): 100})
        self.assertEqual(bank.dump(IDENTITY), before)
        bank.clear(0, 0)
        bank.lock_step(0, 0, {28: 100})
        bank.record_step(1, 0, {4, 8}, {(4, 0): 1, (8, 0): 2})
        before = bank.dump(IDENTITY)
        with self.assertRaises(CapacityError):
            bank.record_step(1, 1, {11}, {(11, 0): 3})
        self.assertEqual(before, bank.dump(IDENTITY))

    def test_sparse_player_first_start_manual_comparison_and_stop(self):
        root = Path(__file__).resolve().parents[1]
        timing = StockTiming((root / "remix/stock/circuitrhythm-firmware-5706-STOCK.bin").read_bytes())
        bank = Bank()
        bank.lock_step(0, 0, {0: 8193})
        bank.lock_step(0, 8, {0: 0})
        player = SparsePlayer(timing)
        pattern = bank.patterns[0]
        self.assertEqual(player.tick(pattern, 0, 3, 0, 0, None), 8193)
        # A manual DSP output change must not reset this comparison state.
        self.assertIsNone(player.tick(pattern, 0, 3, 0, 0, None))
        self.assertEqual(player.tick(pattern, 0, 3, 8, 0, None), 0)
        player.stop()
        self.assertEqual(player.tick(pattern, 0, 3, 0, 0, None), 8193)

    def test_smaller_budget_and_granular_sharing(self):
        bank = Bank(149, NUMERIC | GRANULAR)
        bank.record_step(0, 0, {32, 33}, {(32, 0): 0, (33, 5): 16383})
        with self.assertRaises(CapacityError):
            bank.record_step(0, 1, {4}, {(4, 0): 8192})
        with self.assertRaises(ValueError):
            Bank().lock_step(0, 0, {32: 7})
        bank.lock_step(1, 31, {43: 16383})
        loaded, generation = Bank.load(bank.dump(IDENTITY, 12), IDENTITY, NUMERIC | GRANULAR)
        self.assertEqual(generation, 12)
        self.assertEqual(loaded.dump(IDENTITY, 12), bank.dump(IDENTITY, 12))

    def test_snapshot_roundtrip_and_corruption(self):
        bank = self.fill_exact_bank()
        data = bank.dump(IDENTITY, 0xffffffff)
        restored, generation = Bank.load(data, IDENTITY)
        self.assertEqual(generation, 0xffffffff)
        self.assertEqual(data, restored.dump(IDENTITY, generation))
        self.assertLess(len(data), 24 * 1024)
        rng = random.Random(14)
        for _ in range(200):
            mutated = bytearray(data)
            offset = rng.randrange(len(mutated))
            mutated[offset] ^= 1 << rng.randrange(8)
            with self.assertRaises(ValueError):
                Bank.load(mutated, IDENTITY)
        for cut in (0, 39, 40, len(data)-1):
            with self.assertRaises(ValueError):
                Bank.load(data[:cut], IDENTITY)
        with self.assertRaises(ValueError):
            Bank.load(data, b"test-project-002")

    def test_semantic_corruption_with_valid_checksum(self):
        bank = Bank()
        bank.lock_step(0, 0, {0: 8193, 1: 12003})
        base = bank.dump(IDENTITY)

        def reseal(data):
            crc = zlib.crc32(data[:HEADER.size-4] + data[HEADER.size:])
            struct.pack_into("<I", data, HEADER.size-4, crc)
            return data

        # Unknown flags, invalid position, wrong type, unavailable ID, duplicate.
        record = HEADER.size + 64 * DIRECTORY.size
        for word in (1 << 30, 192 | 1 << 28, 0, 5 << 8 | 1 << 28):
            data = bytearray(base)
            struct.pack_into("<I", data, record, word)
            with self.assertRaises(ValueError):
                Bank.load(reseal(data), IDENTITY)
        data = bytearray(base)
        data[record+4:record+8] = data[record:record+4]
        with self.assertRaises(ValueError):
            Bank.load(reseal(data), IDENTITY)
        for offset in (14, 20):
            data = bytearray(base)
            data[HEADER.size + offset] = 1
            with self.assertRaises(ValueError):
                Bank.load(reseal(data), IDENTITY)

    def test_random_edits_against_independent_capacity_calculation(self):
        rng = random.Random(5376)
        bank = Bank()
        for _ in range(2000):
            index, step, destination = rng.randrange(64), rng.randrange(32), rng.choice(sorted(NUMERIC))
            value = None if rng.random() < .2 else rng.randrange(16384)
            old = bank.patterns[index]
            proposed = dict(old.events)
            if value is None:
                proposed.pop((step*6, destination), None)
            else:
                proposed[step*6, destination] = Event(step*6, destination, value, 1)
            enough = len({e.destination for e in proposed.values()}) <= 8
            before = bank.dump(IDENTITY)
            try:
                bank.lock_step(index, step, {destination: value})
            except CapacityError:
                self.assertFalse(enough)
                self.assertEqual(before, bank.dump(IDENTITY))
            else:
                self.assertTrue(enough)
                self.assertEqual(proposed, bank.patterns[index].events)
            expected_blocks = sum(max(bank.minimum_blocks, (len(p.events)+23)//24) for p in bank.patterns)
            self.assertEqual(bank.used_blocks, expected_blocks)
            self.assertLessEqual(bank.used_blocks, bank.payload_blocks)


if __name__ == "__main__":
    unittest.main()
