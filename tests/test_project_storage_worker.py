import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from project_sidecar_model import Bank, Save, RECORD
from project_storage_worker import Worker, Loader


class Tests(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.save = Save(bytes(RECORD), self.bank, b'0123456789ab')

    def drain(self, worker):
        requests = []
        while not worker.done and not worker.error:
            request = worker.poll(len(requests) * 2)
            self.assertIsNotNone(request)
            self.assertIsNone(worker.poll(0))
            requests.append(request)
            worker.complete(request, 0, len(request.data), len(requests) * 2 + 1)
        return requests

    def test_ack_owns_buffer_and_save_as_target(self):
        target = [2, 17, 3]
        worker = Worker(self.save, target)
        request = worker.poll(0)
        target[1] = 50
        self.assertEqual(request.target, (2, 17, 3))
        self.assertEqual(worker.offset, 0)
        self.assertIsNone(worker.poll(1000))
        worker.complete(request, 0, 0, 1001)
        next_request = worker.poll(1002)
        self.assertEqual(next_request.operation, 'write')
        data = next_request.data
        self.bank.record(0, 0, 0, 0, 1)
        self.assertEqual(next_request.data, data)
        self.assertIsNone(worker.poll(1003))
        with self.assertRaises(ValueError):
            worker.complete(request, 0, 0, 1004)
        worker.complete(next_request, 0, len(data), 1005)
        self.assertEqual(worker.offset, len(data))
        self.drain(worker)
        self.assertFalse(worker.clean(self.bank))

    def test_order_and_clean_completion(self):
        worker = Worker(self.save, (2, 0, 0))
        requests = self.drain(worker)
        first_native = next(i for i, r in enumerate(requests) if r.kind == 'native')
        self.assertEqual(requests[first_native - 1].operation, 'close')
        self.assertEqual(requests[first_native - 2].operation, 'sync')
        self.assertTrue(worker.clean(self.bank))
        self.assertTrue(all(len(r.data) <= 512 for r in requests))

    def test_all_companion_failures_prevent_native_submission(self):
        reference = self.drain(Worker(self.save, (2, 0, 0)))
        count = next(i for i, r in enumerate(reference) if r.kind == 'native')
        for failure in range(count):
            worker = Worker(self.save, (2, 0, 0))
            for i in range(failure + 1):
                request = worker.poll(i)
                worker.complete(request, 5 if i == failure else 0,
                                0 if i == failure else len(request.data), i)
            self.assertIsNone(worker.poll(999))
            self.assertFalse(worker.done)
            self.assertFalse(worker.clean(self.bank))
            self.assertTrue(all(event[2] == 'companion' for event in worker.trace))

    def test_short_callback_and_cross_worker_callback(self):
        worker = Worker(self.save, (2, 0, 0))
        other = Worker(self.save, (2, 0, 0))
        request = worker.poll(0)
        foreign = other.poll(0)
        with self.assertRaises(ValueError):
            worker.complete(foreign, 0, 0, 1)
        worker.complete(request, 0, 0, 1)
        request = worker.poll(2)
        worker.complete(request, 0, len(request.data) - 1, 3)
        self.assertIsNotNone(worker.error)
        self.assertIsNone(worker.poll(4))

    def test_load_publishes_only_complete_validated_pair(self):
        loader = Loader(self.save.native, len(self.save.companion), (2, 0, 0))
        while loader.result is None:
            request = loader.poll(0)
            self.assertIsNone(loader.result)
            self.assertIsNone(loader.poll(1))
            data = self.save.companion[request.offset:request.offset + len(request.data)]
            loader.complete(request, 0, data, 2)
            self.assertIsNone(loader.error)
        self.assertEqual(loader.result[0], self.bank.data)
        self.assertIsNone(loader.poll(3))

    def test_load_cancel_and_short_read_never_publish(self):
        for cancel in (False, True):
            loader = Loader(self.save.native, len(self.save.companion), (2, 0, 0))
            request = loader.poll(0)
            if cancel:
                loader.cancel()
            loader.complete(request, 0, b'', 1)
            self.assertIsNone(loader.result)
            self.assertIsNone(loader.poll(2))

    def test_normalized_native_image_is_rejected(self):
        # Stock 080379B2 modifies bytes 8..11 after the read; validation belongs
        # before that call, not after native state/application notifications.
        changed = bytearray(self.save.native)
        changed[8:12] = b'\x01\x00\x00\x00'
        loader = Loader(changed, len(self.save.companion), (2, 0, 0))
        while loader.error is None:
            request = loader.poll(0)
            loader.complete(request, 0, self.save.companion[
                request.offset:request.offset + len(request.data)], 1)
        self.assertIsNone(loader.result)


if __name__ == '__main__':
    unittest.main()
