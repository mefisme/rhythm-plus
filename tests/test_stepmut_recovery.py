import sys
import struct
import unittest
import zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from restore_stepmut_project import recover,RECORD,META,OLD


class Tests(unittest.TestCase):
    def fixture(self,default=False):
        native=bytearray((i*31)&255 for i in range(RECORD))
        settings=bytearray(b'SM\0\2'+bytes(range(96)))
        settings[2]=(sum(settings[4:])^0x5c)&255
        key=zlib.crc32(settings)
        header=bytearray(b'SO\1'+bytes([not default])+struct.pack('<3I',0 if default else key,0 if default else 100,0))
        header+=struct.pack('<I',zlib.crc32(header))
        native[META:META+20]=header;native[OLD:OLD+100]=bytes(100)
        return bytes(native),{f'{key:08X}.RPS':bytes(settings)},bytes(settings)

    def test_roundtrip_preserves_other_bytes(self):
        native,files,settings=self.fixture();result=recover(native,files)
        self.assertEqual(result[OLD:OLD+100],settings)
        allowed=set(range(META,META+20))|set(range(OLD,OLD+100))
        self.assertTrue(all(a==b for i,(a,b) in enumerate(zip(native,result)) if i not in allowed))
        self.assertEqual(native[OLD:OLD+100],bytes(100))

    def test_fileless_defaults(self):
        native,_,_=self.fixture(True);result=recover(native,{})
        self.assertEqual(result[OLD:OLD+2],b'SM')

    def test_missing_or_corrupt_refuses(self):
        native,files,_=self.fixture()
        with self.assertRaises(KeyError):recover(native,{})
        name=next(iter(files))
        with self.assertRaises(ValueError):recover(native,{name:bytes(100)})
        bad=bytearray(native);bad[META+4]^=1
        with self.assertRaises(ValueError):recover(bad,files)


if __name__=='__main__':unittest.main()
