"""Validate replacement address proposal against the corrected ownership ledger."""
from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / part) for part in ("tools","modules","builds","remix/tools")]
from automation_memory import BankMap, Span
import dspmap


class MemoryTests(unittest.TestCase):
    def test_every_word_and_block_in_corrected_free_map(self):
        report = json.loads((ROOT / "firmware/a0120/manifest.json").read_text())["report"]
        regions = dspmap.regions(report)
        holes = dspmap.free(regions,0,"x")
        bank = BankMap()
        physical = [bank.physical(i) for i in range(bank.words)]
        self.assertEqual(len(set(physical)),8192)
        self.assertEqual(bank.words*3,24576)
        for address in physical:
            self.assertTrue(any(start <= address < end for start,end in holes),hex(address))
            self.assertFalse(0x3000 <= address < 0x4000)
        for index in range(256):
            start,count = bank.block(index)
            self.assertEqual(physical[index*32:index*32+32],list(range(start,start+count)))
        self.assertEqual(bank.physical(3071),0x2fff)
        self.assertEqual(bank.physical(3072),0x4000)
        self.assertEqual(bank.physical(4095),0x43ff)
        self.assertEqual(bank.physical(4096),0x4f90)
        self.assertEqual(bank.physical(8191),0x5f8f)

    def test_quarantine_and_bad_maps(self):
        for spans in ((Span(0x2400,8192,"rejected old map"),),
                      (Span(0x2400,32,"a"),Span(0x2410,32,"b")),
                      (Span(0x5ff0,32,"overflow"),),
                      (Span(0x4400,32,"stock"),),
                      (Span(0x4f80,32,"stock"),),
                      (Span(0x2400,33,"partial block"),)):
            with self.assertRaises(ValueError):BankMap(spans)
        for index in (-1,8192,0xffffffff):
            with self.assertRaises(ValueError):BankMap().physical(index)

    def test_corrected_headroom_is_candidate_only(self):
        report = json.loads((ROOT / "firmware/a0120/manifest.json").read_text())["report"]
        regions = dspmap.regions(report)
        free = sum((end-start)*3 for space in ("x","y")
                   for start,end in dspmap.free(regions,0,space))
        self.assertEqual(free,53880)
        self.assertEqual(free-BankMap().words*3,29304)


if __name__ == "__main__":unittest.main()
