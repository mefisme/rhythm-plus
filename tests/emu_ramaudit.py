"""RAM audit of a build: every load / store our code ran in the emulator tests (RH_MEMAUDIT log) against the manifest's RAM block.

    python tests/emu_ramaudit.py BUILD LOG       (LOG: the file the suites wrote with RH_MEMAUDIT=LOG)

Checks: the slots fit the block, in order, without overlap, under the stock's heap limit and above the stock's last allocation in the
RAM dump; each access inside the block lands in a slot (none in a gap or past a slot's end); prints which module touches which slot,
the slots no test touched, and the stock RAM each module reads or writes outside the block.
"""
import json
import struct
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / d) for d in ("modules", "builds", "tests", "remix/tools")]
import rhstate  # noqa: E402

DUMP = HERE / "remix" / "stock" / "rhythm-ram-frd1-synced.bin"
RAM = 0x20000000


def main():
    build, log = sys.argv[1], Path(sys.argv[2])
    rep = json.loads((HERE / "firmware" / build / "manifest.json").read_text())["report"]
    blk = rep["rhstate"]
    st, size = int(blk["block"], 16), blk["size"]
    offs = sorted(blk["off"].items(), key=lambda kv: kv[1])
    slots = [(name, off, (offs[i + 1][1] if i + 1 < len(offs) else size) - off) for i, (name, off) in enumerate(offs)]
    fails = []

    def check(ok, what):
        print(("PASS " if ok else "FAIL ") + what)
        if not ok:
            fails.append(what)

    dump = DUMP.read_bytes()
    heap_cur = struct.unpack_from("<I", dump, rhstate.HEAP_CUR_PTR - RAM)[0]
    check(st + size == rhstate.HEAP_LIMIT, f"block {st:#x}..{st + size:#x} ({size} B) ends at the stock's heap limit {rhstate.HEAP_LIMIT:#x}")
    check(heap_cur <= st, f"the stock's last allocation in the dump ({heap_cur:#x}) is below the block ({st - heap_cur} B free)")
    check(all(n > 0 and n % 4 == 0 for _, _, n in slots), "every slot a multiple of 4 bytes")

    bases = sorted((int(v.get("base") or v.get("tables"), 16), k) for k, v in rep.items() if isinstance(v, dict) and (v.get("base") or v.get("tables")))

    def module(pc):
        m = None
        for b, k in bases:
            if pc >= b:
                m = k
        return m

    def slot(a):
        for name, off, n in slots:
            if st + off <= a < st + off + n:
                return name, a - st - off, n
        return None

    use, outside, bad = defaultdict(set), defaultdict(set), []
    for line in log.read_text().split("\n"):
        if not line:
            continue
        pc, a, n, rw = line.split()
        pc, a, n = int(pc, 16), int(a, 16), int(n)
        m = module(pc)
        if st <= a < st + size:
            s = slot(a)
            if s is None or s[1] + n > s[2]:
                bad.append((m, hex(pc), hex(a), n, rw))
            else:
                use[s[0]].add((m, rw))
        else:
            outside[m].add((a, rw))
    check(not bad, f"every access inside the block lands inside one slot ({len(bad)} outside: {bad[:6]})")
    print("\nslot           off  size  touched by")
    for name, off, n in slots:
        who = sorted({f"{m}:{''.join(sorted(r for mm, r in use[name] if mm == m))}" for m, _ in use[name]})
        print(f"  {name:12s} {off:4d} {n:5d}  {', '.join(who) or '(no test touched it)'}")
    print("\nstock RAM outside the block, by module (distinct addresses read / written)")
    for m in sorted(outside, key=str):
        r = len({a for a, k in outside[m] if k == "r"})
        w = sorted({a for a, k in outside[m] if k == "w"})
        print(f"  {str(m):12s} read {r:4d}, write {len(w):4d}" + (f"  e.g. {', '.join(hex(a) for a in w[:4])}" if w else ""))
    print("\nALL PASS" if not fails else f"\n{len(fails)} FAIL")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
