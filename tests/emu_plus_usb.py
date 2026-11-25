"""Plus files over USB (A0239+): rdiag's commands 0x20-0x27 run through c_sh_pxmidi and c_sh_backend on a fake card."""
import json
import struct
import sys
import zlib
from pathlib import Path
from emu_playfix import machine, call, STACK
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
ROOT = Path(__file__).resolve().parents[1]
SIG = bytes((0xF0, 0x7D, 0x43, 0x54))
PAD = 232
BAD, NOPACK, BUSY, SHORT, END = 0x100, 0x101, 0x102, 0x103, 0x110
CONTENT_READ, ROUTER = 0x08046054, 0x080298B8


def nib32(v): return bytes((v >> s) & 15 for s in range(28, -4, -4))


def un32(b, o): return int.from_bytes(bytes(((b[o + 2 * i] & 15) << 4) | (b[o + 2 * i + 1] & 15) for i in range(4)), "big")


def main():
    build = sys.argv[1] if len(sys.argv) > 1 else "a0239"
    report = json.loads((ROOT / "firmware" / build / "manifest.json").read_text())["report"]
    rep = report["storageshadow"]; slot = int(rep["slot"], 16)
    assert rep.get("plus_usb"), "no Plus file commands in this build"
    L = {k: int(v, 16) for k, v in rep["labels"].items()}
    D = {k: int(v, 16) for k, v in report["rdiag"]["labels"].items()}
    u = machine((ROOT / "firmware" / build / f"rhythmplus-{build.upper()}.bin").read_bytes(),
                (ROOT / "remix/stock/rhythm-ram-frd1-synced.bin").read_bytes(), mclass=True)
    def w(a, v): u.mem_write(a, struct.pack("<I", v))
    def word(a): return struct.unpack("<I", u.mem_read(a, 4))[0]
    def ret(v=0): u.reg_write(UC_ARM_REG_R0, v); u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
    def cstr(a): return bytes(u.mem_read(a, 104)).split(b"\0")[0].decode()
    for a, v in ((0xe000ef90, 0x73), (0xe000ed08, 0x08010000), (0xe000ed94, 0), (0xe000ed14, 0)): w(a, v)
    PACKS = {8: "1:/Rhythm/07_Beats", 27: "1:/Rhythm/26_Other Pack"}
    dirs = {p + "/Sessions" for p in PACKS.values()}
    disk = {"1:/Rhythm/07_Beats/Sessions/05_SESSION.ncs": bytearray(b"x" * 40),
            "1:/Rhythm/07_Beats/Sessions/RP_05_notes.txt": bytearray(b"n")}
    auto = [False]; fil = {"name": None, "pos": 0, "mode": 0}; listing = {}; replies = []; calls = []
    def parent(n): return n.rsplit("/", 1)[0]
    def present(d): return d == "1:/RP_AUTO" and auto[0] or d in dirs

    def hook(uc, a, n, data):
        x, y, z, q = [uc.reg_read(UC_ARM_REG_R0 + i) for i in range(4)]
        sp = uc.reg_read(UC_ARM_REG_SP)
        if a == CONTENT_READ:                 # the stock waits for Content, which runs the backend: (item, off, buf, len, cb, ctx, &done)
            calls.append("content")
            assert word(sp) == 0 and word(sp + 4) == 0, "a waiting read: no callback"
            w(sp, word(sp + 8)); uc.reg_write(UC_ARM_REG_PC, L["c_sh_backend"] | 1); return
        if a == ROUTER:
            m = struct.unpack("<2I", uc.mem_read(z, 8)); replies.append(bytes(uc.mem_read(m[0], m[1]))); ret(); return
        if a == 0x0802e25a: ret(int(y in PACKS)); return
        if a == 0x0802e44c: u.mem_write(0x20009800, PACKS[y].encode() + b"\0"); ret(0x20009800); return
        if a == 0x08022788:
            d = cstr(x)
            if d == "1:/RP_AUTO": r = 8 if auto[0] else 0; auto[0] = True; ret(r); return
            ret(8 if d in dirs else 5); return
        if a == 0x08022528:
            d = cstr(y)
            if not present(d): ret(5); return
            listing[x] = sorted(k.rsplit("/", 1)[1] for k in disk if parent(k) == d); ret(0); return
        if a == 0x080225b6:
            e = listing[x].pop(0) if listing[x] else ""
            uc.mem_write(y, bytes(0x16 + 128)); uc.mem_write(y + 8, b"\x20"); uc.mem_write(y + 0x16, e.encode() + b"\0")
            if e: w(y, len(disk[parent_of(x) + "/" + e]))
            ret(0); return
        if a == 0x08022588: listing.pop(x, None); ret(0); return
        if a == 0x080226ec: ret(0 if disk.pop(cstr(x), None) is not None else 4); return
        if a == 0x080228c2:
            s, d = cstr(x), cstr(y)
            if s not in disk: ret(4); return
            if d in disk: ret(8); return
            disk[d] = disk.pop(s); ret(0); return
        if a == 0x08021d90:
            assert x == 0x400 and fil["name"] is None, "one private FIL, closed between uses"
            name = cstr(y)
            if not present(parent(name)): ret(5); return
            if z == 7 and name in disk: ret(8); return
            if z in (1, 2) and name not in disk: ret(4); return
            if z in (7, 0x0a): disk[name] = bytearray()
            fil.update(name=name, pos=0, mode=z); w(x + 12, len(disk[name])); ret(); return
        if a == 0x080223d8:
            assert x == 0x400 and fil["name"]; fil["pos"] = min(y, len(disk[fil["name"]])) if fil["mode"] == 1 else y; ret(); return
        if a in (0x08021f72, 0x080220fc):
            b = disk[fil["name"]]; p = fil["pos"]
            if a == 0x080220fc:
                assert fil["mode"] != 1; b[p:p + z] = uc.mem_read(y, z)
            else:
                z = len(b[p:p + z]); uc.mem_write(y, bytes(b[p:p + z]))
            fil["pos"] = p + z; w(q, z); ret(); return
        if a == 0x080222bc: ret(); return
        if a == 0x08022346: fil["name"] = None; ret(); return
    opened = {}
    def parent_of(x): return opened[x]
    orig = hook
    def hook2(uc, a, n, data):
        if a == 0x08022528: opened[uc.reg_read(UC_ARM_REG_R0)] = cstr(uc.reg_read(UC_ARM_REG_R1))
        orig(uc, a, n, data)
    for a in (CONTENT_READ, ROUTER, 0x0802e25a, 0x0802e44c, 0x08022788, 0x08022528, 0x080225b6, 0x08022588, 0x080226ec,
              0x080228c2, 0x08021d90, 0x080223d8, 0x08021f72, 0x080220fc, 0x080222bc, 0x08022346):
        u.hook_add(UC_HOOK_CODE, hook2, None, a, a + 1)

    def prev_out(uc, a, n, data): ret(0)
    u.hook_add(UC_HOOK_CODE, prev_out, None, int(rep["prev_out"], 16), int(rep["prev_out"], 16) + 1)
    BUF, MSG, PORT = 0x2000b000, 0x2000b400, 2
    seq = [0]
    def send(cmd, dir_=0, name=b"", fields=b"", length=PAD):
        seq[0] = (seq[0] + 1) & 0x7F
        body = SIG + bytes((cmd, seq[0], dir_, len(name))) + name + fields
        assert len(body) < length
        m = body + bytes(length - 1 - len(body)) + b"\xF7"
        u.mem_write(BUF, m); w(MSG, BUF); w(MSG + 4, len(m)); replies.clear()
        call(u, D["c_rdin"], PORT, MSG, 0)
        assert len(replies) == 1, replies
        r = replies[0]
        assert r[:4] == SIG and r[4] == cmd | 0x40 and r[5] == seq[0] and r[-1] == 0xF7, r[:8]
        return un32(r, 6), r
    def ok(st, what): assert st == 0, f"{what}: status {st:#x}"

    st, _ = send(0x20, 8); assert st == BUSY, "before the first frame sets up the private memory"
    call(u, L["c_sh_out"], 0, 0x2000b800, 0, 0)                   # one LED frame: ready() sets the guards up
    st, r = send(0x20, 8)
    ok(st, "info"); assert un32(r, 14) in (1, 2, 3)
    n = r[22]; assert bytes(r[23:23 + n]) == b"1:/Rhythm/07_Beats/Sessions/", bytes(r[23:23 + n])
    print("PASS info: the version and the pack's Sessions folder")

    body = bytes((i * 37 + 11) & 255 for i in range(150))
    name = b"RP_05_Intro Groove_DEADBEEF.rps"
    for off in range(0, len(body), 64):
        part = body[off:off + 64]
        st, _ = send(0x23, 8, name, nib32(off) + bytes((len(part),)) + bytes(v for b in part for v in (b >> 4, b & 15)))
        ok(st, f"write at {off}")
    path = "1:/Rhythm/07_Beats/Sessions/" + name.decode()
    assert disk[path] == body
    st, _ = send(0x23, 8, name, nib32(10) + b"\x01\x00\x00")
    assert st == SHORT and disk[path] == body
    print("PASS write: three chunks make the file; a chunk away from the end is refused")

    st, r = send(0x21, 8, b"", nib32(0)); ok(st, "list 0")
    assert un32(r, 14) == 150 and bytes(r[23:23 + r[22]]) == name
    st, r = send(0x21, 8, b"", nib32(1)); assert st == END
    print("PASS list: only Plus files (not the project, not RP_05_notes.txt), with their size")

    got = bytearray()
    for off in range(0, 200, 64):
        st, r = send(0x22, 8, name, nib32(off) + bytes((64,))); ok(st, "read")
        assert un32(r, 14) == 150
        c = un32(r, 22); got += bytes(((r[30 + 2 * i] & 15) << 4) | (r[31 + 2 * i] & 15) for i in range(c))
    assert bytes(got) == body
    st, r = send(0x25, 8, name); ok(st, "crc"); assert un32(r, 14) == 150 and un32(r, 22) == zlib.crc32(body)
    print("PASS read and CRC match the file")

    new = b"RP_07_Intro Groove_DEADBEEF.rps"
    st, _ = send(0x26, 8, name, bytes((len(new),)) + new); ok(st, "rename")
    path2 = "1:/Rhythm/07_Beats/Sessions/" + new.decode()
    assert path2 in disk and path not in disk
    st, _ = send(0x26, 8, new, bytes((14,)) + b"05_SESSION.ncs"); assert st == BAD and path2 in disk
    print("PASS rename inside the folder; a name that is not a Plus file is refused")

    to = b"RP_09_Copy_DEADBEEF.rps"
    st, _ = send(0x27, 8, new, bytes((27, len(to))) + to); ok(st, "copy")
    path3 = "1:/Rhythm/26_Other Pack/Sessions/" + to.decode()
    assert disk[path3] == body and disk[path2] == body
    disk[path3][0] ^= 1
    st, _ = send(0x27, 8, new, bytes((27, len(to))) + to); assert st == 8 and disk[path3][0] == body[0] ^ 1
    big = bytes(range(256)) * 3 + b"tail"
    disk["1:/Rhythm/07_Beats/Sessions/RP_10_Big_0BADF00D.rps"] = bytearray(big)
    st, _ = send(0x27, 8, b"RP_10_Big_0BADF00D.rps", bytes((27, 22)) + b"RP_11_Big_0BADF00D.rps"); ok(st, "copy big")
    assert disk["1:/Rhythm/26_Other Pack/Sessions/RP_11_Big_0BADF00D.rps"] == big
    print("PASS copy to another pack, also past one buffer; an existing target is left alone (status 8)")

    st, _ = send(0x24, 8, new); ok(st, "delete"); assert path2 not in disk
    st, _ = send(0x24, 8, new); assert st == 4
    print("PASS delete; a second delete says no file")

    key = b"DEADBEEF.RPS"
    st, _ = send(0x23, 0, key, nib32(0) + b"\x02\x01\x02\x03\x04"); ok(st, "RP_AUTO write")
    assert disk["1:/RP_AUTO/DEADBEEF.RPS"] == b"\x12\x34" and auto[0]
    st, r = send(0x21, 0, b"", nib32(0)); ok(st, "RP_AUTO list"); assert bytes(r[23:23 + r[22]]) == key
    print("PASS RP_AUTO: <key>.RPS is made with its folder, and listed")

    for bad in (b"../x", b"RP_05_a/b_DEADBEEF.rps", b"05_SESSION.ncs", b"RP_05_x_DEADBEEF.rpx", b"RP_5_x_DEADBEEF.rps"):
        st, _ = send(0x22, 8, bad, nib32(0) + b"\x10"); assert st == BAD, (bad, st)
    st, _ = send(0x22, 0, b"RP_05_x_DEADBEEF.rps", nib32(0) + b"\x10"); assert st == BAD
    st, _ = send(0x22, 5, name, nib32(0) + b"\x10"); assert st == NOPACK
    st, _ = send(0x21, 5, b"", nib32(0)); assert st == NOPACK
    print("PASS refused: paths, project files, wrong suffix or digits, a pack name in RP_AUTO, a missing pack")

    if "filetools" in report:
        SESS, AT = 0x29484, 0x29110 + 276
        def project(path, key, size=150):
            b = bytearray(SESS); b[:4] = b"RUSE"; b[12] = 10; b[16:48] = path.rsplit("_", 1)[-1][:-4].encode().ljust(32)
            if key: b[AT:AT + 12] = b"SO\x04\x01" + struct.pack("<II", key, size)
            disk[path] = b
        A, B = "1:/Rhythm/07_Beats/Sessions/", "1:/Rhythm/26_Other Pack/Sessions/"
        project(A + "06_Groove.ncs", 0x0BADC0DE); disk[A + "RP_06_Groove_0BADC0DE.rps"] = bytearray(body)
        project(A + "04_Stock.ncs", 0)
        st, r = send(0x28, 8, b"", bytes((6,))); ok(st, "meta")
        m = bytes(((r[22 + 2 * i] & 15) << 4) | (r[23 + 2 * i] & 15) for i in range(20))
        assert un32(r, 14) == SESS and m[:12] == b"SO\x04\x01" + struct.pack("<II", 0x0BADC0DE, 150), m
        st, _ = send(0x28, 8, b"", bytes((7,))); assert st == 4
        st, v = send(0x20, 0, b"", b""); ok(st, "info")
        if un32(v, 14) == 2:
            assert (((r[62] & 15) << 4) | (r[63] & 15)) == 10, r[62:64]
            print("PASS project meta, version 2: the project's colour after the Plus bytes")
        if un32(v, 14) >= 3:
            h = bytes(((r[62 + 2 * i] & 15) << 4) | (r[63 + 2 * i] & 15) for i in range(48))
            assert h[:4] == b"RUSE" and h[12] == 10 and h[16:48] == b"Groove".ljust(32), h
            print("PASS project meta, version 3: the project's first 48 bytes (header, colour, name) after the Plus bytes")
        print("PASS project meta: a slot's size and Plus bytes; an empty slot is 4")
        st, r = send(0x29, 8, b"", bytes((6, 27, 3, 0))); ok(st, "slot copy")
        assert un32(r, 14) == 1 and disk[B + "RP_03_0BADC0DE.rps"] == body
        project(B + "03_Groove.ncs", 0x0BADC0DE); disk[B + "RP_03_Old_11111111.rps"] = bytearray(b"old")
        st, _ = send(0x29, 8, b"", bytes((6, 27, 3, 1))); ok(st, "slot drop")
        assert B + "RP_03_Old_11111111.rps" not in disk and B + "RP_03_0BADC0DE.rps" in disk
        print("PASS a project copy's Plus file: to the other pack under the new slot, then the slot's older files deleted")
        st, r = send(0x29, 8, b"", bytes((4, 27, 5, 0))); ok(st, "stock project"); assert un32(r, 14) == 0
        st, r = send(0x29, 0, b"", bytes((4, 27, 5, 0))); ok(st, "internal pack"); assert un32(r, 14) == 0
        if rep.get("internal_pack"):                               # the internal pack's file is on the card, one a slot
            I = "1:/RP_INTERNAL/"; dirs.add(I[:-1]); disk[I + "RP_05_Int_0A0B0C0D.rps"] = bytearray(b"int")
            st, r = send(0x29, 0, b"", bytes((5, 27, 7, 0))); ok(st, "from the internal pack")
            assert un32(r, 14) == 1 and disk[B + "RP_07_0A0B0C0D.rps"] == b"int" and I + "RP_05_Int_0A0B0C0D.rps" in disk
            del disk[B + "RP_07_0A0B0C0D.rps"]
            print("PASS an internal project's copy to a card pack takes its Plus file from RP_INTERNAL")
        project(A + "09_Lost.ncs", 0x01234567)
        st, _ = send(0x29, 8, b"", bytes((9, 27, 6, 0))); assert st == 4 and not any("RP_06_" in k for k in disk if k.startswith(B))
        send(0x23, 0, b"01234567.RPS", nib32(0) + b"\x02\x07\x07\x08\x08"); disk["1:/RP_AUTO/01234567.RPS"] = bytearray(b"auto")
        st, r = send(0x29, 8, b"", bytes((9, 27, 6, 0))); ok(st, "from RP_AUTO"); assert disk[B + "RP_06_01234567.rps"] == b"auto"
        print("PASS no Plus file to copy: a stock project or the internal pack; a missing file is 4 and writes nothing; RP_AUTO's copy is found")
        COPY = 0x0804143e
        result = [0]
        u.hook_add(UC_HOOK_CODE, lambda uc, a, n, d: ret(result[0]), None, COPY, COPY + 1)
        for k in [k for k in disk if k.startswith(B)]: del disk[k]
        ours = sorted(k[len(A):] for k in disk if k.startswith(A) and k[len(A):].startswith("RP_") and k.endswith(".rps"))
        ITEMS = 0x2000b600
        def packcopy(kind, a_, b_):
            u.mem_write(ITEMS, struct.pack("<3I3I", kind, 0, a_, kind, 0, b_)); w(STACK + 0xF0000, 0)
            call(u, L["c_sh_packcopy"], ITEMS, ITEMS + 12, 0, 0)
            return u.reg_read(UC_ARM_REG_R0)
        result[0] = 2
        assert packcopy(1, 8, 27) == 2 and not any(k.startswith(B) for k in disk), "a failed stock copy: nothing follows"
        result[0] = 0
        assert packcopy(2, 8, 27) == 0 and not any(k.startswith(B) for k in disk), "one item: nothing follows"
        assert packcopy(1, 0, 27) == 0 and not any(k.startswith(B) for k in disk), "from the internal pack: no Plus files"
        assert packcopy(1, 8, 27) == 0
        got = sorted(k[len(B):] for k in disk if k.startswith(B))
        assert got == ours and all(disk[B + n] == disk[A + n] for n in ours), (got, ours)
        print(f"PASS pack duplicate: the stock's copy, then the pack's {len(ours)} Plus files with it; nothing after a failed copy, one item or the internal pack")
    w(slot + 4, 1)                                                 # m[ACTIVE]: a project load or save under way
    st, _ = send(0x21, 8, b"", nib32(0)); assert st == BUSY
    w(slot + 4, 0)
    st, _ = send(0x21, 8, b"", nib32(0)); ok(st, "list after busy")
    print("PASS busy while a project load or save runs")

    before = calls.count("content")
    st, r = send(0x2F, 8); assert st == 0xFFFFFFFF or st >= 0x100
    st, r = send(0x01, 0); assert un32(r, 6) == int(report["rdiag"]["version"], 16)
    assert calls.count("content") == before + 1
    print("PASS rdiag ping still answers; every Plus command is one waiting Content read")
    print("ALL PASS")


if __name__ == "__main__":
    main()
