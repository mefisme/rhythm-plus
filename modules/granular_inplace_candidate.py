"""Offline in-place raw-grain handoff using stock track ping-pong buffers.

Snapshot ready changes STATE -> AUDIO -> consumed. Native clear preserves raw
input only for enabled, active voices; source copy clears it before stock mix.
No separate audio mailbox allocation. Metadata addresses remain emulator-only.
"""
import os

import core0
from granular_asm import assemble
from granular_route_candidate import AT,CONTROL,KEY,BUFFER,TEXTURE,TRIGGERED
from granular_snapshot_candidate import SNAPSHOT

AUDIO_KEY=0x674132
BANK=0x304f0
# Control word 3: 0 no native reader, 1 the native reader; time stretch (packed layout, LOOP_NATIVE): 2 stretch on, 3 stretch
# fading out, 4 stretch draining (time stretch builds: the stretch words stay full while the native reader runs unheard). With 2 the native reader
# runs in Loop play mode and while the crossfade to the stretch words is not full, with 3 and 4 always; the gain
# (Y:XG + t, Q23) moves 1 / XFADE_BLOCKS of full a block, sample by sample.
NATIVE_IN_LOOP,FADING_OUT,DRAINING=2,3,4
PLAY_MODE=0x307c9  # + 32 t: 2 = Loop
LOOP_NATIVE=False  # set by the packed layout; else word 3 = 2 or 3 acts as 1
XG,NRUN=0x1fa0,0x1fa8  # core 1 Y + t: the crossfade gain; 1 when the native reader ran this block
XFADE_BLOCKS=8
XSTEP=0x800000//(32*XFADE_BLOCKS)
CLEAR_AT=0xfb8


def stretch_items():
    """the packed layout's source and fade: the Loop native reader and the crossfade of time stretch"""
    t_at=lambda base,reg:['move y:>$1405,a',f'add #>${base:x},a',f'move a1,{reg}']
    return [('label','source'),'move y:>$1405,a','asl #2,a,a',f'add #>${CONTROL:x},a','move a1,r2',
           'move y:(r2),a',f'move #>${KEY:x},x0','cmp x0,a',('jcc','ne','stock_reader'),
           'move y:(r2+$3),a',('jsr','native_on'),('jcc','ne','reload'),('jsr',0x1e5),
           ('label','reload'),'move y:>$1405,a','asl #2,a,a',f'add #>${CONTROL:x},a','move a1,r2',
           ('label','snapshot_source'),'move y:>$1405,a','asl #3,a,a',f'add #>${SNAPSHOT:x},a','move a1,r3',
           'move y:(r2+$1),y0','move y:(r2+$2),x1',f'move #>${AUDIO_KEY:x},x0',
           ('jsr','validate'),('jcc','ne','silent'),('jsr','buffer_address'),f'move #>${BUFFER:x},r1',
           ('jsr','words_in'),'move y:>$1405,a','asl #2,a,a',f'add #>${CONTROL:x},a','move a1,r2',
           'move y:(r2+$1),y0','move y:(r2+$2),x1',f'move #>${AUDIO_KEY:x},x0',
           ('label','copied'),('jsr','validate'),('jcc','ne','silent'),('label','consumed'),
           'clr a','move a,y:(r3)',('jsr','zero_bus'),'rts',
           ('label','validate'),'move y:(r3),a','cmp x0,a',('jcc','ne','invalid'),
           'move y:(r3+$1),a','cmp y0,a',('jcc','ne','invalid'),
           'move y:(r3+$2),a','cmp x1,a',('label','invalid'),'rts',
           # no stretch words this block: the native reader's words stay when it ran, else silence
           ('label','silent'),'clr a','move a,y:(r3)',('jsr','keep_native'),('jcc','ne','silent_bus'),'clr a',f'move #>${BUFFER:x},r1',
           'do #$20,${zero_end:x}','move a,x:(r1)+',('label','zero_end'),('label','silent_bus'),('jsr','zero_bus'),'rts',
           ('label','buffer_address'),'movep y:<<$ffffd0,b','asl #5,b,b','move y:>$1405,a','asl #6,a,a',
           f'add #>${BANK:x},a','add b,a','move a1,r5','rts',
           ('label','zero_bus'),('jsr','buffer_address'),'clr a','do #$20,${bus_zero_end:x}',
           'move a,y:(r5)+',('label','bus_zero_end'),'rts',
           # Z clear: word 3 is 2 or 3 and the native reader ran this block
           ('label','keep_native'),'move y:>$1405,a','asl #2,a,a',f'add #>${CONTROL+3:x},a','move a1,r2','move y:(r2),a',
           f'cmp #${NATIVE_IN_LOOP:x},a',('jcc','lt','kn_no'),*t_at(NRUN,'r2'),'move y:(r2),a','tst a','rts',
           ('label','kn_no'),'clr a','rts',
           # the stretch words into the buffer (r5 -> r1): copied, or crossfaded with the native reader's words there
           ('label','words_in'),('jsr','keep_native'),('jcc','eq','wi_copy'),
           'move y:>$1405,a','asl #2,a,a',f'add #>${CONTROL+3:x},a','move a1,r2','move y:(r2),a','move a1,x0',*t_at(XG,'r2'),
           'tfr x0,a',f'cmp #${FADING_OUT:x},a',('jcc','eq','wi_down'),
           'move y:(r2),a','move #>$7fffff,x0','cmp x0,a',('jcc','eq','wi_copy'),f'move #>${XSTEP:x},y1',('jmp','wi_mix'),
           ('label','wi_down'),'move y:(r2),a','tst a',('jcc','eq','wi_keep'),f'move #>${-XSTEP&0xffffff:x},y1',
           ('label','wi_mix'),'move y:(r2),b','do #$20,${wi_me:x}',
           'move b,x1','move x:(r1),y0','move y:(r5)+,a','sub y0,a','move a,x0','mpy x1,x0,a','add y0,a','move a,x:(r1)+','add y1,b',
           ('label','wi_me'),'tst b',('jcc','ge','wi_lo'),'clr b',
           ('label','wi_lo'),'move #>$7fffff,x0','cmp x0,b','tgt x0,b','move b,y:(r2)',
           ('label','wi_keep'),'rts',
           ('label','wi_copy'),'do #$20,${copy_end:x}','move y:(r5)+,a','move a,x:(r1)+',('label','copy_end'),'rts',
           # a = word 3: NRUN + t set when the native reader runs (Z set), cleared else (Z clear); word 3 = 0 or 1 clears the gain
           ('label','native_on'),'move a1,x0',*t_at(XG,'r6'),'tfr x0,a','cmp #$1,a',('jcc','eq','no_yes0'),
           f'cmp #${FADING_OUT:x},a',('jcc','eq','no_yes'),
           *([f'cmp #${DRAINING:x},a',('jcc','eq','no_yes')] if os.environ.get('RH_STRETCH')=='1' else []),
           f'cmp #${NATIVE_IN_LOOP:x},a',('jcc','ne','no_off'),
           'move y:(r6),a','move #>$7fffff,x1','cmp x1,a',('jcc','ne','no_yes'),
           'move y:>$1405,a','asl #5,a,a',f'add #>${PLAY_MODE:x},a','move a1,r2','move y:(r2),a','cmp #$2,a',('jcc','eq','no_yes'),
           ('jmp','no_not'),
           ('label','no_off'),'clr a','move a,y:(r6)',
           ('label','no_not'),'clr a','move a,y:(r6+$8)','move #>$1,a','tst a','rts',
           ('label','no_yes0'),'clr a','move a,y:(r6)',
           ('label','no_yes'),'move #>$1,a','move a,y:(r6+$8)','clr a','rts',
           ('label','stock_reader'),*t_at(XG,'r2'),'clr a','move a,y:(r2)','move a,y:(r2+$8)',('jmp',0x1e5),
           ('label','fade'),'move y:>$1405,a','asl #2,a,a',f'add #>${CONTROL:x},a','move a1,r2',
           'move y:(r2),a',f'move #>${KEY:x},x0','cmp x0,a',('jcc','ne','stock_fade'),
           *t_at(NRUN,'r2'),'move y:(r2),a','tst a',('jcc','ne','stock_fade'),'rts',
           ('label','stock_fade'),('words',[0x0438f4,0x56e400]),('jmp',0x25e)]


def code():
    items=stretch_items() if LOOP_NATIVE else [('label','source'),'move y:>$1405,a','asl #2,a,a',f'add #>${CONTROL:x},a','move a1,r2',
           'move y:(r2),a',f'move #>${KEY:x},x0','cmp x0,a',('jcc','ne','stock_reader'),
           'move y:(r2+$3),a','tst a',('jcc','eq','snapshot_source'),('jsr',0x1e5),
           'move y:>$1405,a','asl #2,a,a',f'add #>${CONTROL:x},a','move a1,r2',
           ('label','snapshot_source'),'move y:>$1405,a','asl #3,a,a',f'add #>${SNAPSHOT:x},a','move a1,r3',
           'move y:(r2+$1),y0','move y:(r2+$2),x1',f'move #>${AUDIO_KEY:x},x0',
           ('jsr','validate'),('jcc','ne','silent'),('jsr','buffer_address'),f'move #>${BUFFER:x},r1',
           'do #$20,${copy_end:x}','move y:(r5)+,a','move a,x:(r1)+',('label','copy_end'),
           ('label','copied'),('jsr','validate'),('jcc','ne','silent'),('label','consumed'),
           'clr a','move a,y:(r3)',('jsr','zero_bus'),'rts',
           ('label','validate'),'move y:(r3),a','cmp x0,a',('jcc','ne','invalid'),
           'move y:(r3+$1),a','cmp y0,a',('jcc','ne','invalid'),
           'move y:(r3+$2),a','cmp x1,a',('label','invalid'),'rts',
           ('label','silent'),'clr a','move a,y:(r3)',f'move #>${BUFFER:x},r1',
           'do #$20,${zero_end:x}','move a,x:(r1)+',('label','zero_end'),('jsr','zero_bus'),'rts',
           ('label','buffer_address'),'movep y:<<$ffffd0,b','asl #5,b,b','move y:>$1405,a','asl #6,a,a',
           f'add #>${BANK:x},a','add b,a','move a1,r5','rts',
           ('label','zero_bus'),('jsr','buffer_address'),'clr a','do #$20,${bus_zero_end:x}',
           'move a,y:(r5)+',('label','bus_zero_end'),'rts',
           ('label','stock_reader'),('jmp',0x1e5),
           ('label','fade'),'move y:>$1405,a','asl #2,a,a',f'add #>${CONTROL:x},a','move a1,r2',
           'move y:(r2),a',f'move #>${KEY:x},x0','cmp x0,a',('jcc','ne','stock_fade'),
           'move y:(r2+$3),a','tst a',('jcc','ne','stock_fade'),'rts',
           ('label','stock_fade'),('words',[0x0438f4,0x56e400]),('jmp',0x25e)]
    words,labels=assemble(items,AT)
    assert AT+len(words)<=0xf20,hex(AT+len(words))
    clear=[('label','clear_output'),f'move #>${CONTROL:x},r2','move #>$44,r1',
           'do #$8,${clear_end:x}','move y:(r2),a',f'move #>${KEY:x},x0','cmp x0,a',('jcc','ne','clear'),
           'move x:(r1),a','tst a',('jcc','eq','clear'),'move (r5)+n5',('jmp','next'),
           ('label','clear'),'clr a','rep b','move a,y:(r5)+',
           ('label','next'),'move (r5)+n5','move r2,a','add #>$4,a','move a1,r2',
           'move r1,a','add #>$10,a','move a1,r1',('label','clear_end'),'clr a','rts']
    clear_words,clear_labels=assemble(clear,CLEAR_AT)
    return [('p',AT,words),('p',CLEAR_AT,clear_words)],dict(words=len(words)+len(clear_words),source_words=len(words),clear_words=len(clear_words),labels={**labels,**clear_labels})


def patched(segments):
    additions,metadata=code();labels=metadata['labels'];seen=set();output=[]
    expected={0x23d:0x0d01e5,0x25c:0x0438f4,0x25d:0x56e400,
              0x22f:0x060880,0x230:0x000233,0x231:0x06cf20,0x232:0x5e5d00,0x233:0x204d00}
    replacement={0x23d:0x0d0000|labels['source'],0x25c:0x0af080,0x25d:labels['fade'],
                 0x22f:0x0d0000|labels['clear_output'],0x230:0,0x231:0,0x232:0,0x233:0}
    for space,address,data in segments:
        data=list(data)
        if space=='p':
            for _,new_address,new_words in additions:
                assert not(address<new_address+len(new_words) and new_address<address+len(data))
            for site,old in expected.items():
                if address<=site<address+len(data):
                    assert data[site-address]==old,(hex(site),hex(data[site-address]))
                    data[site-address]=replacement[site];seen.add(site)
        output.append((space,address,data))
    assert seen==set(expected)
    return output+additions,metadata
