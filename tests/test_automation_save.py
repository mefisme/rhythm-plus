"""Fault injection for proposed project identity, ordering and recovery rules."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/part) for part in ("tools","modules","builds","remix/tools")]
from project_layout import (BLOCKS,Block,IDENTITY,GRANULAR,TAIL,RECORD_BYTES,
                            validate_layout,encode_identity,decode_identity,
                            stamp_identity,read_identity,sidecar_identity)
from automation_model import Bank
from automation_save_model import Save,State,load_pair

OLD=bytes.fromhex("00112233445566778899aabb")
NEW=bytes.fromhex("aabbccddeeff001122334455")


class SaveTests(unittest.TestCase):
    def fixtures(self):
        stock=bytearray(RECORD_BYTES)
        stock[TAIL:TAIL+0x374]=b"\x5a"*0x374
        old=Bank();old.lock_step(0,0,{0:8193})
        new=Bank();new.lock_step(0,0,{0:12003});new.lock_step(63,31,{28:16383})
        return stamp_identity(stock,OLD),old,new

    def test_layout_and_byte_exact_identity_update(self):
        validate_layout()
        self.assertEqual(IDENTITY.offset+IDENTITY.size,GRANULAR.offset)
        self.assertEqual(GRANULAR.offset+GRANULAR.size,328)
        with self.assertRaises(ValueError):
            validate_layout(BLOCKS+(Block("bad legacy granular",748,32),))
        stock,_,_=self.fixtures()
        changed=stamp_identity(stock,NEW)
        start=TAIL+IDENTITY.offset;end=start+IDENTITY.size
        self.assertEqual(changed[:start],stock[:start])
        self.assertEqual(changed[end:],stock[end:])
        self.assertEqual(read_identity(changed),NEW)
        self.assertEqual(len(changed),RECORD_BYTES)

    def test_identity_legacy_corruption_and_versions(self):
        self.assertIsNone(decode_identity(bytes(20)))
        self.assertEqual(decode_identity(encode_identity(NEW)),NEW)
        for index in range(20):
            data=bytearray(encode_identity(NEW));data[index]^=1
            if index<2:self.assertIsNone(decode_identity(data))
            else:
                with self.assertRaises(ValueError):decode_identity(data)
        with self.assertRaises(ValueError):encode_identity(bytes(12))

    def test_save_order_requires_exact_bytes_and_sync(self):
        stock,old,new=self.fixtures()
        save=Save(stock,new,NEW,generation=9,used_tokens={OLD})
        request=save.begin();self.assertEqual(request.kind,"extra_write")
        request=save.complete(request,transferred=len(request.data),snapshot_generation=9)
        self.assertEqual(request.kind,"extra_sync")
        request=save.complete(request,snapshot_generation=9)
        self.assertEqual(request.kind,"stock_write")
        request=save.complete(request,transferred=len(request.data))
        self.assertEqual(request.kind,"stock_sync")
        request=save.complete(request)
        self.assertIsNone(request);self.assertEqual(save.state,State.COMPLETE)

    def test_partial_extra_never_submits_stock_write(self):
        stock,old,new=self.fixtures()
        example=Save(stock,new,NEW,generation=4)
        # Every byte boundary of this encoded extra snapshot.
        for transferred in range(len(example.extra)):
            save=Save(stock,new,NEW,generation=4)
            request=save.begin()
            self.assertIsNone(save.complete(request,transferred=transferred,snapshot_generation=4))
            self.assertEqual(save.state,State.FAILED)

    def test_each_error_stage_and_duplicate_completion(self):
        stock,old,new=self.fixtures()
        for failed_stage in range(4):
            for error in (1,2,3,5,6):
                save=Save(stock,new,NEW,generation=4);request=save.begin()
                for stage in range(failed_stage):
                    request=save.complete(request,transferred=len(request.data),snapshot_generation=4)
                previous=request
                self.assertIsNone(save.complete(request,status=error,snapshot_generation=4))
                self.assertEqual(save.state,State.FAILED)
                with self.assertRaises(ValueError):save.complete(previous)
        save=Save(stock,new,NEW,generation=4);request=save.begin()
        save.complete(request,transferred=len(request.data),snapshot_generation=4)
        with self.assertRaises(ValueError):save.complete(request)

    def test_snapshot_change_aborts_before_stock(self):
        stock,old,new=self.fixtures()
        for change_stage in (0,1):
            save=Save(stock,new,NEW,generation=4);request=save.begin()
            if change_stage:request=save.complete(request,transferred=len(request.data),snapshot_generation=4)
            self.assertIsNone(save.complete(request,transferred=len(request.data),snapshot_generation=5))
            self.assertEqual(save.state,State.FAILED)
            self.assertEqual(save.failure[0],"snapshot_changed")

    def test_crash_boundaries_keep_old_or_exact_new_pair(self):
        stock,old,new=self.fixtures()
        original={OLD:old.dump(sidecar_identity(OLD),3)}
        save=Save(stock,new,NEW,generation=4)
        # Existing sidecar is not overwritten. Orphan new data is ignored by old stock.
        for cut in range(len(save.extra)+1):
            disk=dict(original);disk[NEW]=save.extra[:cut]
            loaded,status=load_pair(stock,disk)
            self.assertEqual(status,"loaded")
            self.assertEqual(loaded[1],3)
        disk={**original,NEW:save.extra}
        loaded,status=load_pair(save.stock,disk)
        self.assertEqual(status,"loaded");self.assertEqual(loaded[1],4)
        self.assertEqual(loaded[0].dump(sidecar_identity(NEW),4),save.extra)
        # Cross-project data, corrupt or missing new payload never falls back to old.
        for payload in (original[OLD],save.extra[:-1],b"bad"):
            self.assertEqual(load_pair(save.stock,{OLD:original[OLD],NEW:payload})[1],"corrupt_or_wrong_sidecar")
        self.assertEqual(load_pair(save.stock,original)[1],"missing_sidecar")

    def test_clone_and_fresh_token_requirement(self):
        stock,old,new=self.fixtures()
        with self.assertRaises(ValueError):Save(stock,new,OLD,generation=4,used_tokens={OLD})
        with self.assertRaises(ValueError):Save(stock,new,OLD,generation=4)
        save=Save(stock,new,NEW,generation=4,used_tokens={OLD})
        sidecars={OLD:old.dump(sidecar_identity(OLD),3),NEW:save.extra}
        self.assertEqual(load_pair(stock,sidecars)[0][1],3)
        self.assertEqual(load_pair(save.stock,sidecars)[0][1],4)
        bad=bytearray(save.stock);bad[TAIL+IDENTITY.offset+16]^=1
        self.assertEqual(load_pair(bad,sidecars)[1],"corrupt_or_unsupported_identity")

    def test_edits_after_snapshot_remain_dirty(self):
        stock,old,new=self.fixtures()
        save=Save(stock,new,NEW,generation=4);request=save.begin()
        for _ in range(2):request=save.complete(request,transferred=len(request.data),snapshot_generation=4)
        new.lock_step(0,3,{0:9})
        request=save.complete(request,transferred=len(request.data),snapshot_generation=5)
        save.complete(request,snapshot_generation=5)
        self.assertEqual(save.state,State.COMPLETE)
        self.assertFalse(save.clean)
        loaded,status=load_pair(save.stock,{NEW:save.extra})
        self.assertEqual(status,'loaded')
        self.assertNotIn((18,0),loaded[0].patterns[0].events)
        self.assertIn((18,0),new.patterns[0].events)


if __name__=="__main__":unittest.main()
