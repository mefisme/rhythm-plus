"""Actual DSP1 routing candidate: stale/torn rejection and A0122 voice-loop equivalence."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('tools','modules','remix/tools')]
from granular_route_reference import render,segments
from render_granular_reference import fixture,render as grains
import granular_route_candidate as R
import core0
import rhdspemu


def direct(epoch=7,sequence=23,ready=None,mutation=None,enabled=True,repeat=False):
    code,labels=R.code();track=5
    config=R.CONTROL+track*4;mail=R.MAILBOX+track*64
    payload=[0x110000+index*211 for index in range(32)]
    memory=[('y',0x1405,[track]),('y',config,[R.KEY if enabled else 0,7,23,0]),
            ('y',mail,[R.KEY if ready is None else ready,epoch,sequence]+payload),
            ('x',R.BUFFER-1,[0x123456]+[0xbadc0d]*32+[0x654321])]
    instructions=[('words',[0x05f420|k,0xffffff]) for k in range(8)]
    instructions += ['move #>$123456,r0','move #>$654321,n0',('jsr',labels['source'])]
    if repeat:instructions += [('jsr',labels['source'])]
    instructions += ['move r0,y:>$3a100','move n0,y:>$3a101',('jmp',0x7ff0)]
    wrapper,_=core0.asm_at(instructions,0x7100)
    segs=[('p',R.AT,code),('p',0x7100,wrapper)]
    if mutation:
        offset,value={'ready':(0,0),'epoch':(1,8),'sequence':(2,24)}[mutation]
        mutate,_=core0.asm_at([f'move #>${value:x},a',f'move a1,y:>${mail+offset:x}',
                              ('jsr',labels['validate']),('jcc','ne',labels['silent']),('jmp',labels['consumed'])],0x7200)
        jump,_=core0.asm_at([('jmp',0x7200)],labels['copied'])
        segs += [('p',labels['copied'],jump),('p',0x7200,mutate)]
    result,ran=rhdspemu.run(1,pc=0x7100,stop=0x7ff0 if enabled else 0x1e5,
        segs=segs,mem=memory,dumps=[('x',R.BUFFER-1,34),('y',0x3a100,2)],maxins=10000)
    words=result[('x',R.BUFFER-1)]
    assert words[0]==0x123456 and words[-1]==0x654321
    if enabled:assert result[('y',0x3a100)]==[0x123456,0x654321]
    return words[1:33],payload,ran


def main():
    actual,payload,_=direct();assert actual==payload
    for kwargs in (dict(epoch=6),dict(sequence=22),dict(ready=0)):
        actual,_,_=direct(**kwargs);assert actual==[0]*32
    for kind in ('ready','epoch','sequence'):
        actual,_,_=direct(mutation=kind);assert actual==[0]*32
    untouched,_,ran=direct(enabled=False)
    assert untouched==[0xbadc0d]*32 and 'pc=0001e5' in ran
    replay,_,_=direct(repeat=True);assert replay==[0]*32
    print('PASS accepted packets are consumed once; replay without publication supplies zero input')
    print('PASS DSP source hook: exact copy; wrong generation/frame or incomplete publication silences source; post-copy mutation rejected')
    print('PASS source-buffer guards, native r0/n0 preserved; disabled hook branches to original reader without touching audio')
    source,_=grains(fixture(),.04,dict(size=35,dens=55,scan=40))
    configs=[dict(lp=50+8*t,hp=6*t,resonance=10*t,distortion=3*t,slope=40+4*t) for t in range(8)]
    expected,base=render(source,candidate=False,configs=configs)
    assert all(any(track) for track in expected)
    blocks=len(source)//32
    for enabled in ((),*( (track,) for track in range(8)),(0,2,5),tuple(range(8))):
        actual,details=render(source,enabled=enabled,configs=configs)
        assert actual==expected,enabled
        assert details['reader_calls']==[0 if t in enabled else blocks for t in range(8)]
    print('PASS actual A0122 voice loop: all-off, each selected track, mixed tracks and all8 routes match native-boundary input bit-for-bit')
    faults=((15,0,'epoch'),(25,2,'sequence'),(35,5,'not_ready'))
    expected,_=render(source,candidate=False,configs=configs,reader_gaps=[(b,t) for b,t,_ in faults])
    actual,_=render(source,enabled=(0,2,5),configs=configs,faults=faults)
    assert actual==expected
    print('PASS stale/missing packets equal zero-input reference through persistent stock filters/envelope/mixer; other tracks unaffected')
    changes=((20,0,{'lp':25}),(30,5,{'distortion':70}),(35,2,{'hp':90}))
    expected,_=render(source,candidate=False,configs=configs,changes=changes)
    actual,_=render(source,enabled=(0,2,5),configs=configs,changes=changes)
    assert actual==expected
    unchanged,_=render(source,candidate=False,configs=configs)
    for t in range(8):
        if t in (0,2,5):
            at={0:20,5:30,2:35}[t]*32
            assert actual[t][:at]==unchanged[t][:at] and actual[t][at:]!=unchanged[t][at:]
        else:assert actual[t]==unchanged[t]
    print('PASS simultaneous independent stock cutoff/drive/HP changes affect their routed tracks and preserve all unrelated output')
    full,_=render(source,candidate=False)
    ended,_=render(source,candidate=False,near_end=True)
    actual,_=render(source,enabled=(0,2,5),near_end=True)
    for t in range(8):assert actual[t]==(full[t] if t in (0,2,5) else ended[t])
    assert ended!=full
    triggered,info=render(source,enabled=tuple(range(8)),near_end=True,modes=[R.TRIGGERED]*8)
    assert triggered==ended and info['reader_calls']==[blocks]*8
    print('PASS One Shot Triggered runs native readers and retains the endpoint fade; other play modes bypass reader lifetime')
    print('PASS granular routing bypasses sample-reader endpoint fade; ordinary tracks retain native endpoint fade')
    print(f'PASS routing candidate fits{len(R.code()[0])} DSP program words in the current A0122 program gap')
    print('LIMIT: reader/producer fixtures; no live dual-core deadline, physical mailbox allocation, source snapshot export or note/texture ownership proof')
    print('ALL PASS')


if __name__=='__main__':main()
