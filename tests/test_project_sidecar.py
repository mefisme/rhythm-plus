"""Run: .venv/Scripts/python.exe -m unittest discover -s tests -p test_project_sidecar.py"""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from project_sidecar_model import Bank, Save, load, snapshot, RECORD, STEP, IDENTITY, CELLS


class Worker:
    def __init__(self, fail=None, edit=None):
        self.events = []
        self.files = {'companion': bytearray(), 'native': bytearray()}
        self.fail, self.edit = fail, edit

    def write(self, kind, offset, data):
        self.events.append(('write', kind))
        if self.fail == len(self.events):
            raise OSError('injected media failure')
        assert offset == len(self.files[kind]) and len(data) <= 512
        self.files[kind].extend(data)
        if self.edit:
            self.edit()
            self.edit = None
        return len(data)

    def sync(self, kind):
        self.events.append(('sync', kind))
        if self.fail == len(self.events):
            raise OSError('injected sync failure')


class Tests(unittest.TestCase):
    def setUp(self):
        self.native = bytearray((i * 37) & 255 for i in range(RECORD))
        settings = bytearray(b'SM\x00\x02' + bytes(range(96)))
        settings[2] = (sum(settings[4:]) ^ 0x5C) & 255
        self.native[STEP:STEP + 100] = settings
        self.bank = Bank()
        self.token = b'0123456789ab'

    def test_dense_roundtrip_and_preservation(self):
        for c in range(3):
            for p in range(8):
                for s in range(32):
                    for m in range(6):
                        self.bank.record(c, p, s, m, (s + m + c) % 128)
        stock, extra = snapshot(self.native, self.bank, self.token, offload=True)
        data, settings, generation = load(stock, extra)
        self.assertEqual(data, self.bank.data)
        self.assertEqual(generation, CELLS)
        self.assertEqual(settings, self.native[STEP:STEP + 100])
        allowed = set(range(IDENTITY, IDENTITY + 20)) | set(range(STEP, STEP + 100))
        self.assertTrue(all(a == b for i, (a, b) in enumerate(zip(stock, self.native)) if i not in allowed))
        self.assertEqual(stock[STEP:STEP + 100], bytes(100))

    def test_snapshot_isolation_during_recording(self):
        save = Save(self.native, self.bank, self.token, offload=True)
        worker = Worker(edit=lambda: self.bank.record(0, 0, 0, 0, 99))
        self.assertFalse(save.run(worker, self.bank))  # New edits remain unsaved.
        data, _, _ = load(bytes(worker.files['native']), bytes(worker.files['companion']))
        self.assertEqual(data[0], 255)
        self.assertEqual(self.bank.data[0], 99)
        first_native = worker.events.index(('write', 'native'))
        self.assertEqual(worker.events[first_native - 1], ('sync', 'companion'))

    def test_every_companion_failure_blocks_native_write(self):
        save = Save(self.native, self.bank, self.token, offload=True)
        count = (len(save.companion) + 511) // 512 + 1
        for failure in range(1, count + 1):
            worker = Worker(fail=failure)
            with self.assertRaises(OSError):
                save.run(worker, self.bank)
            self.assertFalse(worker.files['native'])
        self.assertEqual(self.native[STEP:STEP + 2], b'SM')

    def test_pair_corruption_and_wrong_project(self):
        stock, extra = snapshot(self.native, self.bank, self.token, offload=True)
        for index in (0, 12, len(extra) // 2, len(extra) - 1):
            bad = bytearray(extra)
            bad[index] ^= 1
            with self.assertRaises(ValueError):
                load(stock, bad)
        wrong = bytearray(stock)
        wrong[100] ^= 1
        with self.assertRaises(ValueError):
            load(wrong, extra)
        with self.assertRaises(ValueError):
            load(stock, b'')
        with self.assertRaises(ValueError):
            snapshot(stock, self.bank, self.token)

    def test_no_offload_preserves_settings(self):
        stock, extra = snapshot(self.native, self.bank, self.token)
        self.assertEqual(stock[STEP:STEP + 100], self.native[STEP:STEP + 100])
        self.assertEqual(load(stock, extra)[1], self.native[STEP:STEP + 100])

    def test_short_write_blocks_native(self):
        worker = Worker()
        worker.write = lambda *args: 0
        with self.assertRaises(OSError):
            Save(self.native, self.bank, self.token).run(worker, self.bank)
        self.assertFalse(worker.files['native'])

    def test_native_failure_is_reported_and_success_is_clean(self):
        save = Save(self.native, self.bank, self.token, offload=True)
        worker = Worker()
        self.assertTrue(save.run(worker, self.bank))
        self.assertEqual(worker.events[-1], ('sync', 'native'))
        first_native = worker.events.index(('write', 'native')) + 1
        for failure in (first_native, len(worker.events)):
            with self.assertRaises(OSError):
                save.run(Worker(fail=failure), self.bank)

    def test_invalid_settings_refuse_offload(self):
        self.native[STEP + 4] ^= 1
        with self.assertRaises(ValueError):
            snapshot(self.native, self.bank, self.token, offload=True)


if __name__ == '__main__':
    unittest.main()
