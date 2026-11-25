"""GS v11 saves (A297-A299) load without their Macro data."""

import struct
import zlib

import emu_fx_native_edges as fixture
from unicorn.arm_const import UC_ARM_REG_R0

G, E = fixture.G, fixture.E


def main():
    report = E.MAN['report']
    if 11 not in report['storageshadow'].get('granular_read_versions', []) or report['storageshadow'].get('granular_settings_version') != 10:
        print('SKIP no GS v11 read in this build')
        return
    u = fixture.setup()
    granular = report['granular']
    slot = int(granular['bridge']['slot'], 16)
    labels = granular['arm_kernel']['labels']
    buf = 0x20001000

    def call(name, *args):
        E.call(u, labels['c_gr_' + name], *args)
        return u.reg_read(UC_ARM_REG_R0)

    ring = report['ring_mod_dsp']['settings_itcm_start']
    u.mem_write(ring, bytes([90, 70]))
    assert call('runtime_settings_store', slot, buf)
    v10 = bytes(u.mem_read(buf, 406))
    assert v10[:3] == b'GS\x0a'
    v11 = bytearray(v10 + bytes(64))
    v11[2] = 11
    v11[152 + 2], v11[152 + 5] = 30, 31   # track 1: lanes K3 and K6 on Macro 1 and 2
    v11[406], v11[422] = 100, 38           # a macro value and a link, ignored here
    struct.pack_into('<I', v11, 4, zlib.crc32(bytes(v11[8:])))
    u.mem_write(buf, bytes(v11))
    assert call('runtime_settings_valid', buf)
    assert call('runtime_settings_load', slot, buf)
    assert bytes(u.mem_read(ring, 2)) == bytes([90, 70])
    assert call('runtime_settings_store', slot, buf)
    again = bytes(u.mem_read(buf, 406))
    assert again[2] == 10
    assert again[152 + 2] == 0 and again[152 + 5] == 0
    assert again[385:387] == bytes([90, 70])
    bad = bytearray(v11)
    bad[100] ^= 1
    u.mem_write(buf, bytes(bad))
    assert not call('runtime_settings_valid', buf)
    print('PASS GS v11 loads: Ring Mod values kept, Macro lanes freed, saved again as v10; a bad CRC is refused')


if __name__ == '__main__':
    main()
