"""Build an isolated DSP interpreter with readable/writable peripheral fixture latches.

Generated from the existing GPL dsptool source; does not modify the shared tool
or emulator tree. 56362/56367 peripherals supply register storage for bank tests;
this is not a DSP56724 dual-core timing model.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
ROOT=Path(__file__).resolve().parents[1]


def build():
    base=Path(os.environ.get('RH_DSP_HOST_ROOT',ROOT.parent/'CIRCUIT-HACKS-RC'))
    emulator=base/'ext/dsp56300'
    source=base/'tools/dsptool/dsptool.cpp'
    libs=[emulator/'build/source'/sub/name for sub,name in (
        ('dsp56kEmu','libdsp56kEmu.a'),('dsp56kBase','libdsp56kBase.a'),('asmjit','libasmjit.a'),('vtuneSdk','libvtuneSdk.a'))]
    original=source.read_text(encoding='utf-8')
    assert original.count('PeripheralsNop px, py;')==1
    generated=original.replace('PeripheralsNop px, py;','Peripherals56362 px; Peripherals56367 py;')
    needle='while (s >> w) mem.set(area(c[0]), addr++, strtoul(w.c_str(), nullptr, 16));'
    assert generated.count(needle)==1
    generated=generated.replace(needle,'''while (s >> w) {
                const TWord value = strtoul(w.c_str(), nullptr, 16);
                if (c == "Y" && addr >= 0xffff80) py.write(addr++, value);
                else mem.set(area(c[0]), addr++, value);
            }''')
    digest=hashlib.sha256(generated.encode()+b''.join(hashlib.sha256(path.read_bytes()).digest() for path in libs)).hexdigest()
    work=ROOT/'buildtmp/dsp-fixture';work.mkdir(parents=True,exist_ok=True)
    output=work/'dsptool-fixture.exe';metadata=work/'build.json'
    if output.exists() and metadata.exists() and json.loads(metadata.read_text())['source_hash']==digest:return output
    cpp=work/'dsptool-fixture.cpp';cpp.write_text(generated,encoding='utf-8')
    compiler=shutil.which('g++')
    if not compiler:raise RuntimeError('g++ required for isolated peripheral fixture tool')
    env=os.environ.copy();env['PATH']=str(Path(compiler).parent)+os.pathsep+env.get('PATH','')
    result=subprocess.run([compiler,'-O2','-DNDEBUG','-DASMJIT_STATIC','-std=c++17','-static',
        '-I'+str(emulator/'source'),'-I'+str(emulator/'source/asmjit/src'),str(cpp),
        '-Wl,--start-group',*map(str,libs),'-Wl,--end-group','-lpthread','-o',str(output)],env=env,capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    metadata.write_text(json.dumps(dict(source_hash=digest,source=str(source),libraries=list(map(str,libs)),
        scope='Isolated register-latch fixture; not real dual-core timing'),indent=2)+'\n')
    return output


if __name__=='__main__':print(build())
