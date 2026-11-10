"""Compile standalone Cortex-M7 automation primitives for local emulation only."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / part) for part in ("modules", "builds", "remix/tools")]
from autoprot import elf_image

ORIGIN = 0x08070000  # Emulation placement, not an installed firmware allocation.


def build():
    sources = [ROOT / "modules" / name for name in
               ("automation_core.c","automation_map.c","automation_identity.c","automation_io.c",
                "automation_pool.c","automation_runtime.c","automation_edit.c")]
    headers=[ROOT/"modules"/name for name in ("automation_pool.h","automation_runtime.h","automation_lock_layout.h")]
    work = ROOT / "buildtmp/automation-core"
    work.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(b"".join(source.read_bytes() for source in sources+headers)+b"zig0.13-thumb-m7-Oz-v2").hexdigest()
    metadata = work / "kernel.json"
    if metadata.exists():
        cached = json.loads(metadata.read_text())
        if cached["source_build_hash"] == digest:
            code = (work / "kernel.bin").read_bytes()
            if hashlib.sha256(code).hexdigest() == cached["code_sha256"]:
                return cached
    script = work / "kernel.ld"
    script.write_text(f"SECTIONS {{ . = 0x{ORIGIN:x}; .text : {{ KEEP(*(.text*)) KEEP(*(.rodata*)) }} /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) }} }}")
    zig = Path(os.environ.get("RH_ZIG", ROOT / "buildtmp/zig-toolchain/ziglang/zig.exe"))
    env = os.environ.copy()
    env.update(ZIG_GLOBAL_CACHE_DIR=str(work / "zig-global"),
               ZIG_LOCAL_CACHE_DIR=str(work / "zig-local"))
    args = [str(zig), "cc", "-target", "thumb-freestanding-eabi", "-mcpu=cortex_m7",
            "-mthumb", "-Oz", "-g", "-fno-lto", "-ffreestanding", "-fno-builtin",
            "-fno-unwind-tables", "-fno-asynchronous-unwind-tables",
            "-fno-stack-protector", "-nostdlib", *map(str,sources), "-Wl,-T,"+str(script),
            "-Wl,--entry=c_ap_pack", "-o", str(work / "kernel.elf")]
    result = subprocess.run(args, env=env, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stdout+result.stderr)
    code, labels = elf_image(work / "kernel.elf", ORIGIN)
    if len(code) > 4096:
        raise RuntimeError("storage primitives exceed 4KiB sub-budget")
    (work / "kernel.bin").write_bytes(code)
    info = dict(origin=ORIGIN, bytes=len(code), labels=labels, source_build_hash=digest,
                code_sha256=hashlib.sha256(code).hexdigest(),
                scope="Standalone local Cortex-M7 kernel; not firmware")
    metadata.write_text(json.dumps(info, indent=2)+"\n")
    return info


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
