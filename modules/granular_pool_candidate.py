"""Offline eight-context wrapper around the verified single-engine producer.

Private working buffers are reused serially. Per-track controls, random state,
grains, source bindings and restart serials are retained independently. This
does not yet impose the final shared grain/CPU budget and is not flashable.
"""
import core0
import granular0 as G
import granular_source_binding as B
import granular_producer_candidate as P
import granular_route_candidate as R
import granular_snapshot_candidate as S

AT,STATE,META,SAVE,TEMP=0x2b00,0x2400,0x2800,0x1f40,0x1fd0
STATE_STRIDE,META_STRIDE=256,80
GRAIN_META_WORDS=B.WORDS+G.MAXG
HOST_CONTROL,HOST_SNAPSHOT,HOST_PARAMS,HOST_ALLOC=0x2b00,0x2b20,0x2b60,0x2be0


def code(bounded=True,host_mailbox=False):
    segments,producer=P.code(in_place=True,grain_cap=TEMP+1 if bounded else None)
    metadata_address=[f'move y:>${TEMP:x},a','asl #4,a,a','move a1,x0',
                      'asl #2,a,a','add x0,a',f'add #>${META:x},a']
    items=[('label','after_wait'),('jsr',0x1a11)]
    for k in range(8):
        items += [f'move r{k},y:>${SAVE+k:x}',f'move n{k},y:>${SAVE+8+k:x}',
                  ('words',[0x057060|k,SAVE+16+k]),('words',[0x05f420|k,0xffffff])]
    if host_mailbox:
        # ARM uses stock narrow Y accesses exclusively for this mailbox.
        # Keep the consumer-owned frame request (+2) in shared memory intact.
        items += [f'move #>${HOST_CONTROL:x},r0',f'move #>${R.CONTROL:x},r1',
                  f'move #>${HOST_PARAMS:x},r2',f'move #>${STATE:x},r3',
                  'do #$8,${host_track_end:x}',
                  'move y:(r0)+,a','move a,y:(r1)+','move y:(r0)+,a','move a,y:(r1)+',
                  'move (r0)+','move (r1)+','move y:(r0)+,a','move a,y:(r1)+',
                  'do #$10,${host_params_end:x}','move y:(r2)+,a','move a,x:(r3)+',
                  ('label','host_params_end'),'move r3,a','add #>$f0,a','move a1,r3',
                  ('label','host_track_end')]
    if bounded:
        items += ['clr a',f'move a,y:>${TEMP+2:x}',f'move a,y:>${TEMP+3:x}','move #>$1,x1',f'move #>${STATE:x},r0',
                  f'move #>${R.CONTROL:x},r2',f'move #>${S.SNAPSHOT:x},r3',
                  'do #$8,${count_end:x}','move x:(r0+$f),a',f'cmp #>${G.KEY:x},a',('jcc','ne','count_next'),
                  'move y:(r2),a',f'cmp #>${R.KEY:x},a',('jcc','ne','count_next'),
                  'move y:(r3),a',f'cmp #>${R.KEY:x},a',('jcc','ne','count_next'),
                  'move y:(r3+$1),a','move y:(r2+$1),x0','cmp x0,a',('jcc','ne','count_next'),
                  f'move y:>${TEMP+2:x},a','add #>$1,a',f'move a1,y:>${TEMP+2:x}',
                  f'move y:>${TEMP+3:x},a','or x1,a',f'move a1,y:>${TEMP+3:x}',
                  ('label','count_next'),'move x1,a','asl a','move a1,x1','move r0,a','add #>$100,a','move a1,r0',
                  'move r2,a','add #>$4,a','move a1,r2','move r3,a','add #>$8,a','move a1,r3',
                  ('label','count_end'),f'move y:>${TEMP+2:x},a','add #>${caps:x},a','move a1,r0',
                  'move p:(r0),a',f'move a1,y:>${TEMP+1:x}','move #>$1,a',f'move a1,y:>${TEMP+4:x}']
    items += ['clr a',f'move a,y:>${TEMP:x}',('label','track'),
              f'move y:>${TEMP:x},a','asl #8,a,a',f'add #>${STATE:x},a','move a1,r0',
              'move x:(r0+$f),a',f'cmp #>${G.KEY:x},a',('jcc','ne','next'),
              f'move #>${G.GB:x},r1','do #$100,${load_state:x}',
              'move x:(r0)+,a','move a,x:(r1)+',('label','load_state'),
              f'move y:>${TEMP:x},a','add #>$1,a',f'move a1,x:>${G.GB+G.P_TRK:x}',
              *metadata_address,'move a1,r0',
              f'move #>${B.META:x},r1',f'do #${GRAIN_META_WORDS:x},${{load_sources:x}}',
              'move y:(r0)+,a','move a,y:(r1)+',('label','load_sources'),
              f'move #>${P.SEEN:x},r1','do #$4,${load_seen:x}',
              'move y:(r0)+,a','move a,y:(r1)+',('label','load_seen'),
              ('jsr',producer['labels']['produce']),
              ('label','before_save'),f'move y:>${TEMP:x},a','asl #8,a,a',f'add #>${STATE+16:x},a','move a1,r1',
              f'move #>${G.GB+16:x},r0','do #$f0,${save_state:x}',
              'move x:(r0)+,a','move a,x:(r1)+',('label','save_state'),
              *metadata_address,'move a1,r1',
              f'move #>${B.META:x},r0',f'do #${GRAIN_META_WORDS:x},${{save_sources:x}}',
              'move y:(r0)+,a','move a,y:(r1)+',('label','save_sources'),
              f'move #>${P.SEEN:x},r0','do #$4,${save_seen:x}',
              'move y:(r0)+,a','move a,y:(r1)+',('label','save_seen'),
              ('label','next'),f'move y:>${TEMP:x},a','add #>$1,a',f'move a1,y:>${TEMP:x}',
              'cmp #>$8,a',('jcc','lt','track'),('jsr',producer['labels']['acknowledge'])]
    if bounded:
        at=items.index(('label','track'))+1
        items[at:at]=[f'move y:>${TEMP+3:x},a',f'move y:>${TEMP+4:x},x0','and x0,a',('jcc','eq','next')]
        at=items.index(('label','next'))+1
        items[at:at]=[f'move y:>${TEMP+4:x},a','asl a',f'move a1,y:>${TEMP+4:x}']
        at=items.index(('jsr',producer['labels']['produce']))
        items[at:at]=[f'move y:>${TEMP+1:x},a','move #>$10,b','sub a,b','tst b',('jcc','le','retired'),
                      'asl #2,a,a','move a1,x0','asl #1,a,a','add x0,a',f'add #>${G.GR0:x},a','move a1,r0',
                      f'move #>${G.GW:x},n0','clr a','do b,${retire_end:x}',
                      'move a,x:(r0)+n0',('label','retire_end'),('label','retired')]
    if host_mailbox:
        items += [f'move #>${S.SNAPSHOT:x},r0',f'move #>${HOST_SNAPSHOT:x},r1',
                  'do #$8,${host_status_end:x}','move r1,r2','move y:(r0)+,x1',
                  'clr a','move a,y:(r1)+',
                  'do #$7,${host_payload_end:x}','move y:(r0)+,a','move a,y:(r1)+',
                  ('label','host_payload_end'),'move x1,y:(r2)',
                  ('label','host_status_end'),
                  'move y:>$372fb,a',f'move a,y:>${HOST_ALLOC:x}',
                  'move y:>$372fc,a',f'move a,y:>${HOST_ALLOC+1:x}']
    for k in range(8):
        items += [f'move y:>${SAVE+k:x},r{k}',f'move y:>${SAVE+8+k:x},n{k}',('words',[0x05f060|k,SAVE+16+k])]
    items += ['rts']
    if bounded:items += [('label','caps'),('words',[16,16,8,5,4,3,2,2,2])]
    words,labels=core0.asm_at(items,AT)
    assert AT+len(words)<0x3fe0
    return segments+[('p',AT,words)],dict(labels=labels,words=len(words),producer=producer,bounded=bounded,
        state_words=8*STATE_STRIDE,metadata_words=8*META_STRIDE)
