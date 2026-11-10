"""Inspect actual staging loader streams and execute cold initialization."""
from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('tools','modules','tests','remix/tools')]
import granular_layout as L
import granular_bundle as B
import granular_pool_candidate as P
import granular_inplace_candidate as I
import granular_snapshot_candidate as S
import granular_note_candidate as N
import granular_flow_candidate as F
from granular_route_reference import segments as baseline1
import core0
import rhdsp1
import rhdspemu
import dspmap
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB
from unicorn.arm_const import *


def check_shared_host_bank():
    # Run stock DSP command bodies with the words sent by the ARM transport.
    # Replace only RTI and the serial output, which the harness supplies.
    address=0x37420
    output=0x1f00
    items=[]
    def command(word,entry):
        items.extend([f'move #>${word:x},x0','move x0,a',('jsr',entry)])
    command(0x008000,0x17b)              # Narrow address selects Y.
    command(0x080000|address,0x173)      # Wide set retains Y.
    command(0xabcdef,0x192)              # Write data to the selected bank.
    command(0x880000|address,0x173)      # Old wide read selects X (bit 15 clear).
    items.extend(['move x:$11,a',f'move a1,y:>${output:x}'])
    command(0x008000,0x17b)
    command(0x080000|address,0x173)
    command(0x400000,0x19a)              # Read next retains Y.
    items.append(('jmp',0x3100))
    wrapper,_=core0.asm_at(items,0x3000)
    capture,_=core0.asm_at([f'move x0,y:>${output+1:x}'],0x1a4)
    segments=rhdspemu.segments(0)+[('p',0x1ad,[0xc]),('p',0x1a4,capture),('p',0x3000,wrapper)]
    memory=[('y',0x2002,[0xffff]),('x',address,[0x123456]),('y',address,[0x654321])]
    data,ran=rhdspemu.run(0,pc=0x3000,stop=0x3100,segs=segments,mem=memory,
                          dumps=[('x',address,1),('y',address,1),('y',output,2)])
    assert 'pc=003100' in ran
    assert data['x',address]==[0x123456] and data['y',address]==[0xabcdef]
    assert data['y',output]==[0x880000|address,0xabcdef]
    print('PASS stock DSP host handler selects X for the old wide read and preserves Y for the corrected read/write sequence')


def main():
    check_shared_host_bank()
    folder=ROOT/'buildtmp/granular-stage'
    image=(folder/'image.bin').read_bytes();manifest=json.loads((folder/'manifest.json').read_text());report=manifest['report']
    assert not list(folder.glob('*.syx'))
    L.validate(report);assert not dspmap.overlaps(dspmap.regions(report))
    actual1=rhdsp1.parse(rhdsp1.sent(image,report,'pitchmod'))[0]
    with L.allocated():
        expected=baseline1()
        for module in (I,S,N,F):expected,_=module.patched(expected)
        reference={address+i:word for space,address,words in expected if space=='p' for i,word in enumerate(words)}
        actual={address+i:word for space,address,words in actual1 if space=='p' for i,word in enumerate(words)}
        for address,word in reference.items():assert actual[address]==word,hex(address)
        pool,pool_meta=P.code(host_mailbox=True)
        host_control=[0,17,0,1]+[0]*28
        host_params=[0x123456]+[0]*127
        fixture=[('y',P.HOST_CONTROL,host_control),('y',P.HOST_PARAMS,host_params),
                 ('y',I.CONTROL,[0,0,29,0]),('y',S.SNAPSHOT,[S.INACTIVE_STATE,17,29,0,0,0,0,8]),
                 ('y',0x372fb,[5,7])]
        mailbox,_=rhdspemu.run(0,call=pool_meta['labels']['after_wait'],
            segs=pool+[('p',0x1a11,[0xc])],mem=fixture,
            dumps=[('y',I.CONTROL,4),('y',P.HOST_SNAPSHOT,8),('x',P.STATE,1),('y',P.HOST_ALLOC,2)])
        assert mailbox['y',I.CONTROL]==[0,17,29,1]
        assert mailbox['y',P.HOST_SNAPSHOT]==[0x674732,17,29,0,0,0,0,8]
        assert mailbox['x',P.STATE]==[0x123456] and mailbox['y',P.HOST_ALLOC]==[5,7]
        print('PASS actual core0 mailbox preserves the requested frame and returns idle and allocator status over private Y')
    loader,stream=core0.sent(image,report)
    programs=[('p',loader[1],loader[2:])];index=0
    while stream[index]:
        count,address=stream[index:index+2]
        programs.append(('p',address,stream[index+2:index+2+count]));index+=count+2
    assert stream[index:index+2]==[0,0]
    program={address+i:word for space,address,words in programs for i,word in enumerate(words)}
    for _,address,words in pool:
        assert [program[address+i] for i in range(len(words))]==words
    assert [program[0],program[1]]==[0x0af080,B.INIT]
    first=int(report['granular']['first_pass'],16)
    assert [program[0x228],program[0x229]]==[0x0bf080,first]
    assert [program[0x224],program[0x225]]==[0x0bf080,int(report['c0fx']['c0'],16)]
    memory=[];dumps=[]
    for region in L.REGIONS:
        if region.core not in (-1,0):continue
        space='y' if region.space=='shared' else region.space
        memory += [(space,region.start,[0x6a7a4b]*region.words)]
        dumps += [(space,region.start,region.words)]
    guards=[('x',0x13ff),('x',0x1600),('x',0x2c00),('y',0x1f58),('y',0x1fcd),('y',0x1fd5),('y',0x27ff),('y',0x2a80),('y',0x2aff),('y',0x2be2),('y',0x373ff),('y',0x37460)]
    for space,address in guards:memory += [(space,address,[0x5a1234])];dumps += [(space,address,1)]
    result,ran=rhdspemu.run(0,pc=0,stop=0x100,segs=programs,mem=memory+[('y',B.FLAG,[7])],dumps=dumps+[('y',B.FLAG,1)],maxins=100000)
    assert 'pc=000100' in ran and result['y',B.FLAG]==[0]
    shared={(('y' if r.space=='shared' else r.space),r.start) for r in L.REGIONS if r.core==-1}
    for space,address,count in dumps:
        if address==B.FLAG:continue
        poisoned=[0x6a7a4b]*count if (space,address) not in shared else [0]*count
        assert result[space,address]==([0x5a1234] if (space,address) in guards else poisoned),(space,hex(address))
    stub=0x3000
    words,marks=core0.asm_at(['move #>$1234,r0',('jsr',first),'move r0,y:>$3f00',('label','done'),'nop'],stub)
    caller=[('p',stub,words),('p',0x1a11,[0xc])];done=marks['done']-2
    body=pool_meta['labels']['after_wait']+2
    for flag,cleared in ((0,True),(1,False)):
        result,ran=rhdspemu.run(0,pc=stub,stop=done+2,segs=programs+caller,mem=memory+[('y',B.FLAG,[flag])],
                                dumps=[('y',B.FLAG,1),('y',0x3f00,1)],maxins=200000)
        assert result['y',0x3f00]==[0x1234] and result['y',B.FLAG]==[1],(ran[-200:],result['y',0x3f00])
        result,ran=rhdspemu.run(0,pc=stub,stop=body,segs=programs+caller,mem=memory+[('y',B.FLAG,[flag])],dumps=dumps,maxins=200000)
        assert f'pc={body:06x}' in ran,ran[-120:]
        for space,address,count in dumps:
            if (space,address) in guards:assert result[space,address]==[0x5a1234],(space,hex(address))
            elif (space,address) not in shared and address!=B.FLAG:
                assert result[space,address]==([0]*count if cleared else [0x6a7a4b]*count),(space,hex(address),flag)
    print('PASS first main-loop pass clears core 0 regions once and keeps r0; later passes leave them')
    kernel=report['granular']['arm_kernel'];origin=kernel['origin']
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
    start=origin&~0xfff;u.mem_map(start,0x4000);u.mem_write(origin,image[origin-0x08010000:origin-0x08010000+kernel['bytes']])
    u.mem_map(0x20000000,0x10000);u.reg_write(UC_ARM_REG_R0,0x20000100)
    u.reg_write(UC_ARM_REG_SP,0x2000ff00);u.reg_write(UC_ARM_REG_LR,(start+0x3ff0)|1)
    u.emu_start(kernel['labels']['c_gr_params_init']|1,start+0x3ff0,count=100000)
    assert bytes(u.mem_read(0x20000100,64))==bytes((0,64,51,72,0,0,64,0))*8
    print('PASS actual staging loader streams contain the verified DSP1 route/snapshot/note/Flow code and bounded DSP0 pool; original ring hook retained')
    print('PASS core0 reset clears the shared regions and the first-pass flag only, then enters native startup; boundary canaries untouched')
    print('PASS memory ledger has no overlaps; embedded ARM kernel runs at its actual link address including readonly default table')
    print(f'STAGE ONLY: {len(image)} image bytes; {0x70000-len(image)} bytes below current ceiling')


if __name__=='__main__':main()
