"""A0120/AD007 project-tail ledger and proposed automation identity.
A0121 preserves volume/movement and filter blocks as archived, inactive data.

No firmware hooks use the new blocks yet. Existing record size stays unchanged.
Identity uses a fresh opaque 96-bit token per saved snapshot; production token
generation, sidecar path and durable-save integration still require verification.
"""
from dataclasses import dataclass
import struct
import zlib

RECORD_BYTES=0x29484
TAIL=0x29110
TAIL_BYTES=0x374
USABLE_TAIL_BYTES=0x372  # Last two bytes are stock-owned.


@dataclass(frozen=True)
class Block:
    name: str
    offset: int
    size: int
    status: str="active"


BLOCKS=(
    Block("volume/movement",2,132),
    Block("random/glide",136,36),
    Block("pitch fade",172,20),
    Block("pattern mutation",192,84),
    Block("automation identity",276,20,"proposed"),
    Block("granular settings",296,32,"candidate"),
    Block("future envelope/waveshape",328,56,"future reservation"),
    Block("sample switches",384,20),
    Block("granular continuation A",404,16,"candidate"),
    Block("granular extension",420,100,"candidate"),
    Block("granular continuation B",520,10,"candidate"),
    Block("track page",530,10),
    Block("master resonance",540,4,"future reservation"),
    Block("compressor threshold",544,4,"future reservation"),
    Block("pitch/FX parameters",548,132),
    Block("pitch/FX secondary",680,68),
    Block("scene extension",748,112),
    Block("granular continuation C",860,22,"candidate"),
)
IDENTITY=next(block for block in BLOCKS if block.name=="automation identity")
GRANULAR=next(block for block in BLOCKS if block.name=="granular settings")


def validate_layout(blocks=BLOCKS):
    ordered=sorted(blocks,key=lambda block:block.offset)
    if any(block.offset<0 or block.size<=0 or block.offset+block.size>USABLE_TAIL_BYTES
           for block in ordered):
        raise ValueError("invalid tail block")
    if any(a.offset+a.size>b.offset for a,b in zip(ordered,ordered[1:])):
        raise ValueError("project-tail blocks overlap")


def encode_identity(token):
    if len(token)!=12 or token==bytes(12):
        raise ValueError("identity requires a nonzero 96-bit token")
    data=b"AT\x01\x00"+token
    return data+struct.pack("<I",zlib.crc32(data))


def decode_identity(data):
    if len(data)!=20:
        raise ValueError("wrong identity size")
    if data[:2]!=b"AT":
        return None  # Legacy project; no extra automation identity.
    if data[2:4]!=b"\x01\x00":
        raise ValueError("unsupported identity version/flags")
    if data[4:16]==bytes(12) or zlib.crc32(data[:16])!=struct.unpack_from("<I",data,16)[0]:
        raise ValueError("corrupt automation identity")
    return bytes(data[4:16])


def stamp_identity(record,token):
    if len(record)!=RECORD_BYTES:
        raise ValueError("wrong stock project size")
    result=bytearray(record)
    result[TAIL+IDENTITY.offset:TAIL+IDENTITY.offset+IDENTITY.size]=encode_identity(token)
    return bytes(result)


def read_identity(record):
    if len(record)!=RECORD_BYTES:
        raise ValueError("wrong stock project size")
    return decode_identity(record[TAIL+IDENTITY.offset:TAIL+IDENTITY.offset+IDENTITY.size])


def sidecar_identity(token):
    encode_identity(token)  # Validate the same token used by the stock tail block.
    return token+b"RPA1"  # Preserve the reference sidecar's 16-byte identity field.


validate_layout()
