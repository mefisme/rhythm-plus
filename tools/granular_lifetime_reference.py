"""Offline actual A0122 native reader/lifetime, optionally replacing only its audio."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('modules','remix/tools')]
import rpasm
rpasm.use()
import core0
import rhdspemu
from granular_route_reference import segments
from granular_stock_reference import distortion_reciprocal
import granular_route_candidate as R

STATE,OUTPUT,TRACE=0x3a400,0x60000,0x3b000


def run(*,candidate=False,engine_mode=R.TRIGGERED,loop=False,sample_length=2048,
        sample_start=0,frames=160,release_at=None,note_at=None,note=67,flow=False):
    if not 1<=frames<=200 or not 512<=sample_length<=8192:raise ValueError('bounded fixture')
    if not 0<=note<111:raise ValueError('native note range')
    if flow and (not candidate or engine_mode!=R.TEXTURE):raise ValueError('Flow requires Texture candidate')
    segs=segments()
    if candidate:segs,_=R.patched(segs)
    if flow:
        import granular_flow_candidate as F
        segs,flow_meta=F.patched(segs)
    source=[(((i*977)%4001)-2000)*1024&0xffffff for i in range(16384)]
    params=[0]*32;params[0]=5;params[1]=1 if loop else 0;params[2]=2 if loop else 0
    params[6:14]=[64,0,127,64,0,0,127,0]
    memory=[('y',0x307c8,params),('x',0x30000+20,[sample_start,sample_length,sample_start+sample_length,0]),
            ('y',0x308c8+5*0xbc,[0x040041,0x042043]),('x',0x30200,distortion_reciprocal()),
            ('y',STATE,[0,OUTPUT,TRACE]),('y',0xffffd0,[0]),
            ('y',R.CONTROL,[R.KEY if candidate else 0,3,0,engine_mode])]
    memory += [('y',0x40000+i,source[i:i+64]) for i in range(0,len(source),64)]
    items=[('words',[0x05f420|k,0xffffff]) for k in range(8)]
    items += ['move #>$907f00,y1','move #>$0,y0',('jsr',0xe3a),('label','frame')]
    if note_at is not None:
        items += [f'move y:>${STATE:x},a',f'cmp #>${note_at:x},a',('jcc','ne','no_note'),
                  f'move #>${0xa07f00 if flow else 0x907f00:x},y1',
                  f'move #>${((note-60)<<16)&0xffffff:x},y0',
                  ('jsr',flow_meta['labels']['flow'] if flow else 0xe3a),('label','no_note')]
    if candidate:
        items += [f'move #>${R.KEY:x},a',f'move a,y:>${R.MAILBOX:x}',
                  'move #>$3,a',f'move a,y:>${R.MAILBOX+1:x}',f'move y:>${STATE:x},a',
                  f'move a1,y:>${R.MAILBOX+2:x}',f'move a1,y:>${R.CONTROL+2:x}',
                  f'move #>${R.MAILBOX+3:x},r1','move #>$100000,a',
                  'do #$20,${publish_end:x}','move a,y:(r1)+',('label','publish_end')]
    if release_at is not None:
        items += [f'move y:>${STATE:x},a',f'cmp #>${release_at:x},a',('jcc','ne','no_release'),
                  'move #>$800000,y1','move #>$2,y0',('jsr',0x509),('label','no_release')]
    items += [('jsr',0x221),f'move y:>${STATE+1:x},r1','move #>$304f0,r0',
              'do #$20,${capture_end:x}','move y:(r0)+,a','move a,y:(r1)+',('label','capture_end'),
              f'move r1,y:>${STATE+1:x}',f'move y:>${STATE+2:x},r1',
              'move x:>$44,a','move a,y:(r1)+','move x:>$4a,a','move a,y:(r1)+',
              'move x:>$43,a','move a,y:(r1)+',f'move r1,y:>${STATE+2:x}',
              ('jsr',0x289),f'move y:>${STATE:x},a','add #>$1,a',f'move a1,y:>${STATE:x}',
              f'cmp #>${frames:x},a',('jcc','lt','frame'),('jmp',0x7ff0)]
    wrapper,_=core0.asm_at(items,0x7000)
    result,ran=rhdspemu.run(1,pc=0x7000,stop=0x7ff0,segs=segs+[('p',0x7000,wrapper)],
        mem=memory,dumps=[('y',OUTPUT,frames*32),('y',TRACE,frames*3),('x',0x40,16),('y',0x40,16)],maxins=50_000_000)
    assert 'pc=007ff0' in ran,ran
    return dict(audio=result[('y',OUTPUT)],trace=[result[('y',TRACE)][i:i+3] for i in range(0,frames*3,3)],
                voice_x=result[('x',0x40)],voice_y=result[('y',0x40)],ran=ran)


if __name__=='__main__':
    for kwargs in ({},dict(candidate=True),dict(candidate=True,engine_mode=R.TEXTURE),dict(candidate=True,loop=True)):
        result=run(**kwargs)
        print(kwargs,'active',sum(bool(row[0]) for row in result['trace']),'voice',result['voice_x'],result['voice_y'],result['ran'])
