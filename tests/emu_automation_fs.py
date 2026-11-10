"""Read-only save-path research: execute stock request/callback ARM code.

The filesystem task is intercepted. No files on the device or SD are touched.
This establishes request direction and callback lifetime, not persistence.
"""
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / part) for part in ("tests", "modules", "builds", "remix/tools")]
from emu_playfix import machine, STACK, SENT
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *


def main():
    firmware = (ROOT / "remix/stock/circuitrhythm-firmware-5706-STOCK.bin").read_bytes()
    ram = (ROOT / "remix/stock/rhythm-ram-frd1-synced.bin").read_bytes()
    u = machine(firmware, ram)
    requests, completions, write_callbacks = [], [], []
    worker_requests, worker_posts = [], []
    pending = [False]
    disk_result = [0, 0x29484]
    worker_request = [b""]
    obj, item, buffer, callback, vtable = (0x20001000, 0x20001100, 0x20001200,
                                         0x20001300, 0x20001400)
    target = 0x08000180

    def write(address, value):
        u.mem_write(address, struct.pack("<I", value))

    def read(address):
        return struct.unpack("<I", u.mem_read(address, 4))[0]

    def ret(value=0):
        u.reg_write(UC_ARM_REG_R0, value)
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))

    def hook(uc, address, size, data):
        if address in (0x0802aca2, 0x0802acb8):
            request = uc.reg_read(UC_ARM_REG_R1)
            raw = bytes(uc.mem_read(request, 72))
            requests.append(dict(async_=address == 0x0802acb8, operation=raw[0],
                                 item=struct.unpack_from("<3I", raw, 4),
                                 transfer=struct.unpack_from("<3I", raw, 16),
                                 callback=struct.unpack_from("<I", raw, 60)[0],
                                 context=struct.unpack_from("<I", raw, 64)[0]))
            ret()
        elif address == target:
            completions.append((uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1)))
            ret()
        elif address == 0x08047304:
            sp = uc.reg_read(UC_ARM_REG_SP)
            write_callbacks.append((uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1),
                                    uc.reg_read(UC_ARM_REG_R2), uc.reg_read(UC_ARM_REG_R3),
                                    read(sp), read(sp+4)))
        elif address in (0x0802ca6c, 0x08023cea):
            ret()  # Worker mutex boundary only, no filesystem implementation.
        elif address == 0x08040e18:
            ret(int(pending[0]))
        elif address == 0x08040dee:
            queue_buffer = read(uc.reg_read(UC_ARM_REG_R1)+4)
            uc.mem_write(queue_buffer, worker_request[0])
            pending[0] = False
            ret(1)
        elif address == 0x080411d8:
            sp = uc.reg_read(UC_ARM_REG_SP)
            worker_requests.append((uc.reg_read(UC_ARM_REG_R1), uc.reg_read(UC_ARM_REG_R2),
                                    uc.reg_read(UC_ARM_REG_R3)))
            write(read(sp), disk_result[1])
            ret(disk_result[0])
        elif address == 0x080419cc:
            message = uc.reg_read(UC_ARM_REG_R2)
            worker_posts.append((uc.reg_read(UC_ARM_REG_R1), bytes(uc.mem_read(message, 30))))
            ret()

    for address in (0x0802aca2, 0x0802acb8, target, 0x08047304,
                    0x0802ca6c, 0x08023cea, 0x08040e18, 0x08040dee,
                    0x080411d8, 0x080419cc):
        u.hook_add(UC_HOOK_CODE, hook, None, address, address+1)

    def call(address, *args):
        sp = STACK + 0xf0000
        for index, value in enumerate(args[:4]):
            u.reg_write(UC_ARM_REG_R0+index, value)
        for index, value in enumerate(args[4:]):
            write(sp+4*index, value)
        for index in range(8):
            u.reg_write(UC_ARM_REG_R4+index, 0x1114+index)
        u.reg_write(UC_ARM_REG_SP, sp)
        u.reg_write(UC_ARM_REG_LR, SENT | 1)
        u.emu_start(address | 1, SENT, count=100000)
        assert u.reg_read(UC_ARM_REG_PC) == SENT
        assert u.reg_read(UC_ARM_REG_SP) == sp
        assert [u.reg_read(UC_ARM_REG_R4+i) for i in range(8)] == list(range(0x1114, 0x111c))

    # The stock's descriptor is kind, slot, pack/context, not a filename.
    for offset, value in enumerate((2, 17, 3)):
        write(item+4*offset, value)
    call(0x08047270, obj, item, 0, buffer, 0x34)
    request = requests[-1]
    assert request == dict(async_=False, operation=6, item=(2, 17, 3),
                           transfer=(0, buffer, 0x34), callback=0, context=0)
    print("PASS stock 47270 submits synchronous operation 6 with offset/buffer/length")

    write(callback, vtable)
    write(vtable, target | 1)
    call(0x080472e2, obj, item, 0, buffer, 0x29484, callback)
    request = requests[-1]
    assert request == dict(async_=True, operation=7, item=(2, 17, 3),
                           transfer=(0, buffer, 0x29484), callback=0x08047305, context=obj)
    assert read(obj+4) == callback and not completions
    print("PASS stock 472E2 queues operation 7 and retains caller callback after return")

    # The callback's first argument is an item descriptor pointer, not an error
    # code. Trace its use through cleanup before interpreting completion status.
    for slot in (17, 18, 19):
        write(item+4, slot)
        write(obj+4, callback)
        call(0x08047304, item, 0, 0, 0, 0, obj)
        assert requests[-1]["operation"] == 8
        assert requests[-1]["item"] == (2, slot, 3)
        assert read(obj+4) == 0
        assert completions[-1] == (callback, item)
    print("PASS stock completion clears retained pointer and forwards item after operation 8")
    # Execute the real worker-to-callback bridge. Error is R2 of the six-argument
    # callback; the final ordinary observer drops it, so persistence must capture
    # this earlier result. Nothing here invokes the disk implementation.
    message = 0x20001500
    for status, transferred in ((0, 0x29484), (2, 0), (3, 7), (5, 0)):
        write(obj+4, callback)
        raw = struct.pack("<I3IBBIII", 0x08047305, 2, 17, 3, 1, status,
                          buffer, transferred, obj)
        u.mem_write(message, raw)
        call(0x0802b064, message)
        assert write_callbacks[-1] == (message+4, 1, status, buffer, transferred, obj)
        assert completions[-1] == (callback, message+4)
        assert read(obj+4) == 0
    print("PASS actual completion bridge preserves error and transferred length before observer drops them")
    # Run the actual Content worker over a single queued request. Inject only
    # the disk backend's result, then check the worker-created completion frame.
    worker = 0x20001800
    write(worker+0x14, 0x20001900)
    raw = bytearray(72)
    raw[0] = 7
    struct.pack_into("<3I", raw, 4, 2, 17, 3)
    struct.pack_into("<3I", raw, 16, 0, buffer, 0x29484)
    struct.pack_into("<2I", raw, 60, 0x08047305, obj)
    for status, transferred in ((0, 0x29484), (2, 0), (3, 7), (5, 0)):
        worker_request[0] = bytes(raw)
        disk_result[:] = status, transferred
        pending[0] = True
        u.mem_write(worker+0x10, b"\x00\x01\x00\x00")
        call(0x0802ad40, worker)
        assert worker_requests[-1] == (0, buffer, 0x29484)
        bridge, frame = worker_posts[-1]
        assert bridge == 0x0802b065
        fields = struct.unpack("<I3IBBIII", frame)
        assert fields[0:4] == (0x08047305, 2, 17, 3)
        assert fields[5:] == (status, buffer, transferred, obj)
        write(obj+4, callback)
        u.mem_write(message, frame)
        call(bridge & ~1, message)
        assert write_callbacks[-1][2] == status
        assert write_callbacks[-1][4] == transferred
    print("PASS actual Content worker propagates full, short, failed and unavailable-write results")
    print("LIMIT: disk backend/queues/mutexes intercepted; SD atomicity and crash recovery unproved")
    print("ALL PASS")


if __name__ == "__main__":
    main()
