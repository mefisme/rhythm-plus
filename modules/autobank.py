"""AD007 fixed-bank proof. Never reserves or writes over prototype backing."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from autoprot import elf_image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).with_suffix('.c')
CACHE = ROOT / 'builds/autobank-cache.json'
KEY = 0x41424b31


def compile_kernel(origin, config):
    definitions = '\n'.join(f'#define {k} 0x{v:x}u' for k,v in sorted(config.items()))+'\n'
    source_bytes = SOURCE.read_bytes()+(SOURCE.parent/'automation_core.c').read_bytes()
    digest = hashlib.sha256(source_bytes+definitions.encode()+str(origin).encode()+b'zig0.13-v1').hexdigest()
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    if digest in cache:
        return bytes.fromhex(cache[digest]['code']), cache[digest]['labels']
    work = ROOT/'buildtmp/autobank'
    work.mkdir(parents=True,exist_ok=True)
    (work/'autobank_config.h').write_text(definitions)
    link = work/'kernel.ld'
    link.write_text(f'SECTIONS {{ . = 0x{origin:x}; .text : {{ KEEP(*(.text*)) KEEP(*(.rodata*)) }} /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) }} }}')
    zig = Path(os.environ.get('RH_ZIG',ROOT/'buildtmp/zig-toolchain/ziglang/zig.exe'))
    env = os.environ.copy()
    env.update(ZIG_GLOBAL_CACHE_DIR=str(work/'zig-global'), ZIG_LOCAL_CACHE_DIR=str(work/'zig-local'))
    args = [str(zig),'cc','-target','thumb-freestanding-eabi','-mcpu=cortex_m7','-mthumb','-Oz','-g',
            '-fno-lto','-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
            '-fno-stack-protector','-nostdlib','-I',str(work),str(SOURCE),'-Wl,-T,'+str(link),
            '-Wl,--entry=c_apbkcommand','-o',str(work/'kernel.elf')]
    result = subprocess.run(args,env=env,capture_output=True,text=True)
    if result.returncode:
        raise RuntimeError(result.stdout+result.stderr)
    code,labels = elf_image(work/'kernel.elf',origin)
    if len(code)>6144:
        raise RuntimeError('bank proof exceeds its temporary 6KiB code ceiling')
    cache[digest] = dict(code=code.hex(),labels=labels)
    CACHE.write_text(json.dumps(cache,indent=2)+'\n')
    return code,labels


def install(img,report,base_addr):
    import rhbuild,rhstate
    from thumb import bl
    assert 'autoprot' in report and 'autobank' in rhstate.OFF
    ap = report['autoprot']
    config = {k:int(ap['config'][k],16) for k in (
        'PRIVATE_MAGIC_ADDR','PRIVATE_MAGIC','READY_ADDR','READY_VALUE','WAIT_ADDR','UPLOAD_ADDR','GET32','PUT32')}
    config.update(FLAG_ADDR=rhstate.ST+rhstate.OFF['autobank'][0],
                  PREV_COMMAND=int(ap['labels']['c_apcommand'],16),
                  AP_IMPORT=int(ap['labels']['c_apimport'],16))
    start = int(report['rdiag']['labels']['c_rdcmd'],16)
    calls = [instruction.address for instruction in rhbuild.MD.disasm(img[start-rhbuild.BASE:start-rhbuild.BASE+0x180],start)
             if instruction.mnemonic=='bl' and int(instruction.op_str.removeprefix('#'),16)==config['PREV_COMMAND']]
    assert len(calls)==1,calls
    origin = (base_addr+3)&~3
    code,labels = compile_kernel(origin,config)
    rhbuild.patch(img,calls[0],f"bl #{config['PREV_COMMAND']:#x}",bl(calls[0],labels['c_apbkcommand']))
    img += b'\xff'*(origin-rhbuild.BASE-len(img))+code
    while len(img)%4:img.append(255)
    report['autobank'] = dict(proof_only=True,key=hex(KEY),flag=hex(config['FLAG_ADDR']),
        commands=dict(status=40,initialize=41,fill=42,check=43,clear=44,roundtrip=45,read_timing=46,restore_locks=47),
        bank_start='0x2400',bank_words=8192,chunk_words=32,
        excluded_chunks=list(range(224,230)),itcm=['0x300','0x514'],state_bytes=532,
        regions=[dict(core=0,space='x',start='0x2400',words=7168),
                 dict(core=0,space='x',start='0x40c0',words=832)],
        code_bytes=len(code),command_site=hex(calls[0]),config={k:hex(v) for k,v in config.items()},
        labels={k:hex(v) for k,v in labels.items()},source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest())
    return labels,code
