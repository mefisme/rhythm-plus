"""Offline single-engine core0 producer after the stock core1 acknowledgement.

Not a firmware installer. Shared addresses and voice lifetime are experimental.
Legacy mode uses private RAW. In-place mode writes the already-mixed native bank
for the next voice quantum and acknowledges native snapshots even when disabled.
"""
import core0
import granular0 as G
import granular_stock_controls as C
import granular_route_candidate as R
import granular_snapshot_candidate as S

AT,ENGINE,RAW=0x2980,0x2100,0x1480
SEEN=C.CONTROL+8
LIFE_KEY=0x674c31
ACK_ACTIVE=0x674331
ACK_IDLE=0x674732


def code(in_place=False,grain_cap=None):
    if in_place:import granular_inplace_candidate as IPC
    engine,grain,tables=C.code(latched_source=True,raw_output=None if in_place else RAW,code_at=ENGINE,grain_cap=grain_cap)
    assert ENGINE+len(engine)<=AT
    items=[('label','after_wait'),('jsr',0x1a11),('jsr','produce'),'rts',
           ('label','produce'),f'move x:>${G.GB+G.P_KEY:x},a',f'move #>${G.KEY:x},x0',
           'cmp x0,a',('jcc','ne','return'),('jsr',grain['g_save']),
           f'move x:>${G.GB+G.P_TRK:x},a','sub #>$1,a',
           'tst a',('jcc','lt','restore'),'cmp #>$8,a',('jcc','ge','restore'),
           'move a1,x1','asl #2,a,a',f'add #>${R.CONTROL:x},a','move a1,r2',
           'move y:(r2),a',f'move #>${R.KEY:x},x0','cmp x0,a',('jcc','ne','restore'),
           'move x1,a','asl #3,a,a',f'add #>${S.SNAPSHOT:x},a','move a1,r3',
           'move y:(r3),a','cmp x0,a',('jcc','ne','restore'),
           'move y:(r2+$1),x1','move y:(r3+$1),a','cmp x1,a',('jcc','ne','restore'),
           f'move a1,y:>${C.CONTROL+4:x}',
           'move y:(r2+$2),x1','move y:(r3+$2),a','cmp x1,a',('jcc','ne','restore'),
           f'move a1,y:>${C.CONTROL+5:x}',
           'move y:(r3+$3),a','tst a',('jcc','lt','restore'),'cmp #>$80,a',('jcc','ge','restore'),
           f'move a1,y:>${C.CONTROL+3:x}',
           'move y:(r3+$4),a','move y:(r3+$5),x1','move a1,y0',
           f'move a1,y:>${C.CONTROL:x}','clr b',f'move b,y:>${C.REVERSE:x}',
           'move x1,b','sub y0,b','tst b',('jcc','ge','forward_region'),
           'neg b',f'move x1,y:>${C.CONTROL:x}','move #>$1,a',f'move a1,y:>${C.REVERSE:x}',
           ('label','forward_region'),'cmp #>$8,b',('jcc','lt','restore'),
           f'move b1,y:>${C.CONTROL+1:x}',
           'move y:(r3+$6),a','asl #4,a,a','tst a',('jcc','le','restore'),
           f'cmp #>${C.SAFE_RATIO:x},a',('jcc','gt','restore'),f'move a1,y:>${C.CONTROL+2:x}',
           'move y:(r3),a','cmp x0,a',('jcc','ne','restore'),
           'move y:(r3+$1),a',f'move y:>${C.CONTROL+4:x},x1','cmp x1,a',('jcc','ne','restore'),
           'move y:(r3+$2),a',f'move y:>${C.CONTROL+5:x},x1','cmp x1,a',('jcc','ne','restore'),
           f'move y:>${C.CONTROL+3:x},a','asl #2,a,a',f'add #>${G.SMP:x},a','move a1,r1',
           f'move y:>${C.CONTROL:x},a','move x:(r1),x1','cmp x1,a',('jcc','lt','restore'),
           'move x:(r1+$1),a','tst a',('jcc','le','restore'),'add x1,a',
           'move a1,x1',f'move y:>${C.CONTROL:x},a',f'move y:>${C.CONTROL+1:x},y0',
           'add y0,a','cmp x1,a',('jcc','gt','restore'),
           'move y:(r2+$3),a',f'move a1,y:>${C.CONTROL+6:x}',
           'move y:(r3+$7),a',f'move a1,y:>${C.CONTROL+7:x}',
           f'move y:>${SEEN+3:x},a',f'cmp #>${LIFE_KEY:x},a',('jcc','ne','restart'),
           f'move y:>${SEEN:x},a',f'move y:>${C.CONTROL+4:x},x1','cmp x1,a',('jcc','ne','restart'),
           f'move y:>${SEEN+2:x},a',f'move y:>${C.CONTROL+6:x},x1','cmp x1,a',('jcc','ne','restart'),
           # Field 13: bit 1 Freeze holds the read point, bit 0 Retrigger restarts Texture.
           f'move x:>${G.GB+13:x},x1','btst #$1,x1',('jcc','cs','continue_voice'),
           'tst a',('jcc','ne','check_serial'),'btst #$0,x1',('jcc','cc','continue_voice'),
           ('label','check_serial'),
           f'move y:>${SEEN+1:x},a',f'move y:>${C.CONTROL+7:x},x1','cmp x1,a',('jcc','eq','continue_voice'),
           ('label','restart'),'clr a',f'move #>${G.VS:x},r1',
           f'do #${0x20+G.MAXG*G.GW:x},${{clear_grains:x}}','move a,x:(r1)+',('label','clear_grains'),
           ('label','continue_voice'),
           f'move y:>${C.CONTROL+4:x},a',f'move a1,y:>${SEEN:x}',
           f'move y:>${C.CONTROL+7:x},a',f'move a1,y:>${SEEN+1:x}',
           f'move y:>${C.CONTROL+6:x},a',f'move a1,y:>${SEEN+2:x}',
           f'move #>${LIFE_KEY:x},a',f'move a1,y:>${SEEN+3:x}',
           ('jsr',grain['g_block']),
           f'move x:>${G.GB+G.P_TRK:x},a','sub #>$1,a','asl #6,a,a',
           f'add #>${R.MAILBOX:x},a','move a1,r3','clr a','move a,y:(r3)',
           'move r3,a','add #>$3,a','move a1,r2',f'move #>${RAW:x},r1',
           'do #$20,${publish_end:x}','move y:(r1)+,a','move a,y:(r2)+',('label','publish_end'),
           f'move y:>${C.CONTROL+4:x},a','move a,y:(r3+$1)',
           f'move y:>${C.CONTROL+5:x},a','move a,y:(r3+$2)',
           f'move #>${R.KEY:x},a','move a,y:(r3)',
           ('label','restore'),('jsr',grain['g_rest']),('label','return'),'rts']
    if in_place:
        at=items.index(('jsr',grain['g_block']))+1
        end=items.index(('label','restore'),at)
        items[at:end]=[
            ('label','before_publish'),f'move x:>${G.GB+G.P_TRK:x},a','sub #>$1,a','move a1,x1',
            'asl #2,a,a',f'add #>${R.CONTROL:x},a','move a1,r2',
            'move x1,a','asl #3,a,a',f'add #>${S.SNAPSHOT:x},a','move a1,r3',
            'move y:(r2+$1),a',f'move y:>${C.CONTROL+4:x},x1','cmp x1,a',('jcc','ne','restore'),
            'move y:(r3),a',f'cmp #>${R.KEY:x},a',('jcc','ne','restore'),
            'move y:(r3+$1),a','cmp x1,a',('jcc','ne','restore'),
            'move y:(r3+$2),a',f'move y:>${C.CONTROL+5:x},x1','cmp x1,a',('jcc','ne','restore'),
            f'move #>${IPC.AUDIO_KEY:x},a','move a,y:(r3)']
    if in_place:
        items.insert(items.index(('label','produce'))-1,('jsr','acknowledge'))
        items += [('label','acknowledge'),('jsr',grain['g_save']),
                  f'move #>${S.SNAPSHOT:x},r3',f'move #>${R.CONTROL:x},r2',
                  'do #$8,${ack_end:x}',
                  'move y:(r3+$1),a','move y:(r2+$1),x1','cmp x1,a',('jcc','ne','ack_next'),
                  'move y:(r3),a',f'cmp #>${R.KEY:x},a',('jcc','eq','ack_active'),
                  f'cmp #>${S.INACTIVE_STATE:x},a',('jcc','ne','ack_next'),
                  f'move #>${ACK_IDLE:x},a',('jmp','ack_commit'),
                  ('label','ack_active'),f'move #>${ACK_ACTIVE:x},a',
                  ('label','ack_commit'),'move a,y:(r3)',('label','ack_next'),
                  'move r3,a','add #>$8,a','move a1,r3','move r2,a','add #>$4,a','move a1,r2',
                  ('label','ack_end'),('jsr',grain['g_rest']),'rts']
    words,labels=core0.asm_at(items,AT)
    assert AT+len(words)<0x4000
    return [('p',ENGINE,engine),('p',AT,words)],dict(labels=labels,engine_words=len(engine),producer_words=len(words),tables=tables,in_place=in_place)
