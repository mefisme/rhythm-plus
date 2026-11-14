"""Offline recovery to a NEW legacy-compatible native project record.

Usage: python tools/restore_stepmut_project.py INPUT RP_AUTO OUTPUT
Never edits the input or overwrites an existing output. Handles SO v1 only.
"""
from pathlib import Path
import struct
import sys
import zlib
from project_sidecar_model import RECORD, TAIL, step_valid
META=TAIL+276
OLD=TAIL+404
DEFAULTS=bytes([0x2e,0x0a,0,0x2a,0x2a,0x1e,2,2,7,0x0a,4,0])


def recover(native, companions):
    if len(native)!=RECORD:raise ValueError('Expected a complete native project record')
    meta=native[META:META+20]
    if (meta[:3]!=b'SO\1' or meta[3]>1 or struct.unpack_from('<I',meta,12)[0] or
            struct.unpack_from('<I',meta,16)[0]!=zlib.crc32(meta[:16])):
        raise ValueError('Missing or invalid SO v1 metadata')
    key,size=struct.unpack_from('<2I',meta,4)
    if meta[3]:
        if size!=100:raise ValueError('Unsupported companion size')
        settings=companions[f'{key:08X}.RPS']
        if not step_valid(settings) or zlib.crc32(settings)!=key:raise ValueError('Companion mismatch/corruption')
    else:
        if key or size:raise ValueError('Invalid default metadata')
        settings=bytearray(b'SM\0\2'+DEFAULTS*8)
        settings[2]=(sum(settings[4:])^0x5c)&255
    result=bytearray(native)
    result[META:META+20]=bytes(20)
    result[OLD:OLD+100]=settings
    return bytes(result)


def main():
    if len(sys.argv)!=4:raise SystemExit(__doc__)
    src,folder,dst=map(Path,sys.argv[1:])
    if src.resolve()==dst.resolve():raise ValueError('Output must be a separate file')
    native=src.read_bytes();meta=native[META:META+20]
    companions={}
    if len(meta)==20 and meta[3]==1:
        key=struct.unpack_from('<I',meta,4)[0];name=f'{key:08X}.RPS'
        companions[name]=(folder/name).read_bytes()
    result=recover(native,companions)
    with dst.open('xb') as f:f.write(result)
    print(f'Created recovered legacy-compatible record: {dst}')


if __name__=='__main__':main()
