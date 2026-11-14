"""Actual ARM upload wrapper/native sender and sequential DSP loader proof.

Physical SPI/SHI ready/ack boundaries are injected. No hardware boot claim.
"""
import json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('modules','tests','remix/tools')]
import core0,gfxsplit as G,rhdspemu as D,rhdsp1
from emu_playfix import machine,call
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *

def main():
    name=sys.argv[1] if len(sys.argv)>1 else 'a0185'
    def read(n):
        d=ROOT/'firmware'/n
        return (d/f'rhythmplus-{n.upper()}.bin').read_bytes(),json.loads((d/'manifest.json').read_text())['report']
    old,orep=read('a0184');image,rep=read(name)
    expected=G.program(old,orep['gfxsplit'])
    assert G.program(image,rep['gfxsplit'])==expected
    assert len(expected)==8336
    assert image[G.DP.TABLE-G.DP.BASE:G.DP.TABLE-G.DP.BASE+4]==struct.pack('<I',core0.BLK0)
    assert image[G.DP.TABLE-G.DP.BASE+4:G.DP.TABLE-G.DP.BASE+16]==old[G.DP.TABLE-G.DP.BASE+4:G.DP.TABLE-G.DP.BASE+16]
    assert rhdsp1.sent(bytearray(image),rep,'pitchmod')==rhdsp1.sent(bytearray(old),orep,'pitchmod')
    assert len(old)-len(image)==24416
    print('PASS all 8,336 DSP sound words and complete core1 stream match A0184; 24,416 flash bytes reclaimed')
    u=machine(image,(ROOT/'remix/stock/rhythm-ram-frd1-synced.bin').read_bytes(),mclass=True)
    groups=[];entries=[]
    def ret(v=0):u.reg_write(UC_ARM_REG_R0,v);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def hook(uc,a,n,d):
        x,y=uc.reg_read(UC_ARM_REG_R0),uc.reg_read(UC_ARM_REG_R1)
        assert not uc.reg_read(UC_ARM_REG_PRIMASK)
        if a==core0.SEND:entries.append((x,y));return # execute native sender
        if a==0x08031048:groups.append([x,bytearray()]);ret()
        elif a==0x08046504:
            assert 0<y<=510 and y%3==0
            groups[-1][1].extend(uc.mem_read(x,y));ret()
        elif a==0x0803107a:
            assert groups[-1][0]==x
            assert len(groups[-1][1])==((y&65535)+2)*3
            ret()
        else:ret()
    boundaries=(core0.SEND,0x08031048,0x08046504,0x0803107a,0x08046414)
    for a in boundaries:u.hook_add(UC_HOOK_CODE,hook,None,a,a+1)
    def block(at):
        off=at-G.DP.BASE;n=int.from_bytes(image[off:off+3],'big')
        return image[off:off+(n+2)*3]
    entry=int(rep['core0']['labels']['c_d0up'],16)
    addresses=[int(v,16) for v in rep['core0']['blocks']]
    plan=[addresses[0],core0.BLK0,*addresses[1:]]
    captured=[]
    for _ in range(3):
        entries.clear();groups.clear();call(u,entry,core0.BLK0,0)
        assert entries==[(a,0) for a in plan]
        assert [bytes(g[1]) for g in groups]==[block(a) for a in plan]
        captured=[bytes(g[1]) for g in groups]
    mode1=struct.unpack_from('<I',image,G.DP.TABLE-G.DP.BASE+4)[0]
    entries.clear();groups.clear();call(u,entry,mode1,0)
    assert entries==[(mode1,0)] and bytes(groups[0][1])==block(mode1)
    print('PASS actual ARM wrapper and stock sender: correct loader/original/extension/end stream on repeated uploads; mode1 forwards unchanged')
    # Execute the complete native startup function with hardware/task operations
    # stubbed, exercising the real patched call site and both core uploads.
    for a in (0x08046538,0x0802b69c,0x0802366c,0x08046534,0x08023416,
              0x080312cc,0x08031338,0x0803136c,0x080311da):
        u.hook_add(UC_HOOK_CODE,hook,None,a,a+1)
    entries.clear();groups.clear();call(u,0x08031110,0,0,0,0)
    assert entries[2:2+len(plan)]==[(a,0) for a in plan]
    assert entries[0]==(0x08031638,0) and entries[1][1]==1 and entries[-1][1]==1
    entries.clear();groups.clear();call(u,0x08031110,1,0,0,0)
    assert (mode1,0) in entries and not any(a in addresses for a,c in entries)
    print('PASS native startup/reload dispatcher uses segmented mode0 and original mode1 without altering the core1 upload order')
    # Sequential-memory input replaces physical SHI wait/read only. The same
    # loader algorithm writes the captured word stream then jumps via P:0.
    stream=b''.join(captured[1:]);words=[int.from_bytes(stream[i:i+3],'big') for i in range(0,len(stream),3)]
    loader,_=core0.asm_at(core0.loader_items(port=False),core0.LD)
    prefix,_=core0.asm_at(['move #>$30000,r6',('jmp',core0.LD)],0x3f00)
    result,ran=D.run(0,pc=0x3f00,stop=0x100,segs=[('p',core0.LD,loader),('p',0x3f00,prefix)],
        mem=[('x',0x30000,words)],dumps=[('p',0,len(expected))],maxins=100000)
    assert 'pc=000100' in ran,ran
    assert result['p',0]==expected
    print('PASS DSP loader algorithm consumes captured native stream, reproduces every sound word and reaches stock entry P:$100')
    print('LIMIT physical SHI/SPI timing and cold boot still require hardware validation; no SD dependency added')
    print('ALL PASS')
if __name__=='__main__':main()
