"""Compile the standalone granular mode owner for actual ARM emulation only."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import re
ROOT=Path(__file__).resolve().parents[1]
ORIGIN=0x08070000


def elf(path,origin=ORIGIN):
    data=path.read_bytes();header=struct.unpack_from('<16sHHIIIIIHHHHHH',data)
    assert data[:4]==b'\x7fELF' and header[2]==40
    sections=[struct.unpack_from('<10I',data,header[6]+i*header[11]) for i in range(header[12])]
    chunks=[];labels={}
    for _,kind,flags,address,offset,size,link,info,align,entry in sections:
        if flags&2 and size:
            assert kind!=8,'unexpected global BSS'
            assert origin<=address<address+size<=min(origin+0x4800,0x08080000)
            chunks.append((address,data[offset:offset+size]))
        if kind==2:
            strings=sections[link];table=data[strings[4]:strings[4]+strings[5]]
            for i in range(offset,offset+size,entry):
                name,value,_,info,_,index=struct.unpack_from('<IIIBBH',data,i)
                name=table[name:].split(b'\0',1)[0].decode()
                if index and info&15==2 and name.startswith('c_gr_'):labels[name]=value&~1
    end=max(address+len(chunk) for address,chunk in chunks);code=bytearray(b'\xff'*(end-origin))
    for address,chunk in chunks:code[address-origin:address-origin+len(chunk)]=chunk
    return bytes(code),labels


def ONESHOT_SCAN():return os.environ.get('RH_GRANULAR_ONESHOT_SCAN') in ('1','2')


def LOAD_DIRECT():return int(os.environ.get('RH_GRANULAR_LOAD_DIRECT') or 0)


def build(origin=ORIGIN,pages=False,page_pad=29,assign=False,state_address=0,storage_address=0,held_address=0,menu_pulse=False,view_colors=False,remember_views=False,reverse_cycle=False,editor_settings=False,menu_address=0,trim_unused=False,fine_controls=False,fine_all=False,no_burst=False,turn_bar=False,dark_spare=False,easy_zones=False,stock_bar=False,zone_pads=False,full_freeze=False,shift_tap=False,sticky_assign=False,stretch_on=0):
    assert 0x08010000<=origin<=0x0807f000 and origin%4==0
    assert 26<=page_pad<=31
    source=ROOT/'modules/granular_owner.c'
    work=ROOT/(('buildtmp/granular-owner' if origin==ORIGIN else f'buildtmp/granular-owner-{origin:08x}')+('-pages' if pages else '')+f'-pad{page_pad}-assign{int(assign)}')
    work.mkdir(parents=True,exist_ok=True)
    policy=(b'trim-standalone-v1' if trim_unused else b'')+(b'fine-v1' if fine_controls else b'')+(b'fine-all-v1' if fine_all else b'')+(b'no-burst-v1' if no_burst else b'')+(b'turn-bar-v1' if turn_bar else b'')+(b'dark-spare-v1' if dark_spare else b'')+(b'easy-zones-v1' if easy_zones else b'')+(b'stock-bar-v1' if stock_bar else b'')+(b'zone-pads-v1' if zone_pads else b'')+(b'full-freeze-v1' if full_freeze else b'')+(b'shift-tap-v1' if shift_tap else b'')+(b'sticky-assign-v1' if sticky_assign else b'')+(b'stretch-v2-%x'%stretch_on if stretch_on else b'')+(b'oneshot-scan-v1' if ONESHOT_SCAN() else b'')+(b'load-direct-v%d'%LOAD_DIRECT() if LOAD_DIRECT() else b'')
    digest=hashlib.sha256(source.read_bytes()+b'zig0.13-thumb-m7-Oz-v3'+struct.pack('<13I',origin,pages,page_pad,assign,state_address,storage_address,held_address,menu_pulse,view_colors,remember_views,reverse_cycle,editor_settings,menu_address)+policy).hexdigest()
    metadata=work/'kernel.json'
    if metadata.exists():
        cached=json.loads(metadata.read_text())
        if cached['source_build_hash']==digest and hashlib.sha256((work/'kernel.bin').read_bytes()).hexdigest()==cached['code_sha256']:return cached
    script=work/'kernel.ld'
    obsolete={'c_gr_'+n for n in ('project_save','project_load','levels_save','levels_load','shift_save','shift_load','runtime_store')}
    roots=set(re.findall(r'\b(c_gr_\w+)\([^;{}]*\)\s*\{',source.read_text()))-obsolete
    if trim_unused:
        assert editor_settings
        # These are standalone test/inspection entry points or duplicate
        # callable copies of already-inlined helpers. Real C references still
        # retain any needed function. Historical/standalone builds keep them.
        roots-={'c_gr_'+name for name in ('owner_size','owner_epoch','owner_mode','owner_flags',
            'owner_set_flags','params_word','ui_size','ui_pad','runtime_size')}
    sections=(' '.join('KEEP(*(.text.'+name+'))' for name in sorted(roots))+' *(.text*) *(.rodata*)') if editor_settings else 'KEEP(*(.text*)) KEEP(*(.rodata*))'
    script.write_text(f'SECTIONS {{ . = 0x{origin:x}; .text : {{ {sections} }} /DISCARD/ : {{ *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) }} }}')
    zig=Path(os.environ.get('RH_ZIG',ROOT/'buildtmp/zig-toolchain/ziglang/zig.exe'))
    env=os.environ.copy();env.update(ZIG_GLOBAL_CACHE_DIR=str(work/'zig-global'),ZIG_LOCAL_CACHE_DIR=str(work/'zig-local'))
    args=[str(zig),'cc','-target','thumb-freestanding-eabi','-mcpu=cortex_m7','-mthumb','-Oz','-g','-fno-lto',
          '-DG_KNOB_PAGES='+str(int(pages)),'-DG_PAGE_PAD='+str(page_pad),'-DG_LANE_ASSIGN='+str(int(assign)),'-DG_STATE='+str(state_address),'-DG_STORAGE='+str(storage_address),'-DG_HELD_FN='+str(held_address),'-DG_MENU_PULSE='+str(int(menu_pulse)),'-DG_TRACK_VIEWS='+str(int(view_colors)),'-DG_NAV_PERSIST='+str(int(remember_views)),'-DG_REVERSE_CYCLE='+str(int(reverse_cycle)),
          '-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-fno-stack-protector',
          '-nostdlib',str(source),'-Wl,-T,'+str(script),'-Wl,--entry=c_gr_owner_init','-o',str(work/'kernel.elf')]
    if editor_settings:
        # The companion-only build never calls the retired project-tail codec.
        # Retain every other public entry for adapters and ARM regression tests.
        args+=['-DG_EDITOR_SETTINGS=1','-DG_MENU='+str(menu_address),'-ffunction-sections','-fdata-sections','-Wl,--gc-sections']
    if fine_controls:args+=['-DG_FINE_CONTROLS=1']
    if stretch_on:args+=['-DG_STRETCH=1',f'-DG_STRETCH_ON={stretch_on}']
    if fine_all:
        assert fine_controls;args+=['-DG_FINE_ALL=1']
    if no_burst:args+=['-DG_NO_BURST=1']
    if turn_bar:
        assert editor_settings;args+=['-DG_TURN_BAR=1']
    if dark_spare:
        assert no_burst;args+=['-DG_DARK_SPARE=1']
    if easy_zones:
        assert no_burst;args+=['-DG_EASY_ZONES=1']
    if stock_bar:args+=['-DG_STOCK_BAR=1']
    if zone_pads:
        assert easy_zones and stock_bar;args+=['-DG_ZONE_PADS=1']
    if full_freeze:args+=['-DG_FULL_FREEZE=1']
    if ONESHOT_SCAN():args+=['-DG_ONESHOT_SCAN=1']
    if LOAD_DIRECT():args+=[f'-DG_LOAD_DIRECT={LOAD_DIRECT()}']
    if shift_tap:
        assert editor_settings and not reverse_cycle;args+=['-DG_SHIFT_TAP=1']
    if sticky_assign:
        assert assign and pages and not shift_tap;args+=['-DG_STICKY_ASSIGN=1']
    result=subprocess.run(args,env=env,capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    code,labels=elf(work/'kernel.elf',origin);(work/'kernel.bin').write_bytes(code)
    info=dict(origin=origin,bytes=len(code),labels=labels,source_build_hash=digest,code_sha256=hashlib.sha256(code).hexdigest(),binary=str(work/'kernel.bin'),
              scope='Standalone granular ownership candidate; not firmware')
    metadata.write_text(json.dumps(info,indent=2)+'\n');return info


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin',type=lambda value:int(value,0),default=ORIGIN)
    print(json.dumps(build(parser.parse_args().origin),indent=2))
