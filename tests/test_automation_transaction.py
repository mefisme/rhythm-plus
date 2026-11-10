"""Interrupted copy-on-write staging, independent of actual storage ownership."""
from pathlib import Path
import random
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from automation_model import Event,CapacityError
from automation_transaction_model import TransactionBank


def replace(count,value):
    def operation(bank):
        events={}
        for n in range(count):
            event=Event(n//2,n%2,(value+n)&16383)
            events[event.position,event.destination]=event
        bank._commit(0,events,{0,1},set())
    return operation


class Transactions(unittest.TestCase):
    def test_every_interrupted_word_preserves_live_pattern(self):
        model=TransactionBank();model.edit(0,replace(384,1))
        view=model.view;before=model.events(0)
        for boundary in range(513):
            self.assertFalse(model.edit(0,replace(384,9000),boundary))
            self.assertIs(model.view,view)
            self.assertEqual(model.events(0),before)
        self.assertTrue(model.edit(0,replace(384,9000)))
        self.assertEqual(model.events(0),sorted(model.view[0].patterns[0].events.values()))

    def test_capacity_reserve_and_retry_at_full_pool(self):
        model=TransactionBank()
        #18*9 +46*1=208 charged blocks, leaving16 physically free.
        for index in range(64):
            blocks=9 if index<18 else 1
            count=blocks*24
            def operation(bank,index=index,count=count):
                events={}
                for n in range(count):
                    event=Event(n//2,n%2,n)
                    events[event.position,event.destination]=event
                bank._commit(index,events,{0,1},set())
            self.assertTrue(model.edit(index,operation))
        self.assertEqual(model.view[0].used_blocks,208)
        self.assertEqual(sum(map(len,model.view[1])),208)
        for attempt in range(12):
            value=9000+attempt
            self.assertFalse(model.edit(0,replace(216,value),128))
            self.assertTrue(model.edit(0,replace(216,value)))
        view=model.view
        with self.assertRaises(CapacityError):model.edit(0,replace(217,6000))
        self.assertIs(model.view,view)

    def test_random_edits_and_failures_do_not_leak_staging(self):
        rng=random.Random(208);model=TransactionBank()
        for _ in range(400):
            count=rng.randrange(385);value=rng.randrange(16384)
            before=model.events(0);view=model.view
            boundary=rng.randrange(((count+23)//24)*32+1) if rng.randrange(2) else None
            result=model.edit(0,replace(count,value),boundary)
            if not result:
                self.assertIs(model.view,view);self.assertEqual(model.events(0),before)
            else:self.assertEqual(model.events(0),sorted(model.view[0].patterns[0].events.values()))
            owned=[b for chain in model.view[1] for b in chain]
            self.assertEqual(len(owned),len(set(owned)))
            self.assertLessEqual(len(owned),208)

    def test_eight_active_dense_tracks_still_fit(self):
        model=TransactionBank()
        for index in range(8):
            def operation(bank,index=index):
                source={}
                for n in range(384):
                    event=Event(n//2,n%2,n)
                    source[event.position,event.destination]=event
                bank._commit(index,source,{0,1},set())
            self.assertTrue(model.edit(index,operation))
        self.assertEqual(model.view[0].used_blocks,184)


if __name__=='__main__':unittest.main()
