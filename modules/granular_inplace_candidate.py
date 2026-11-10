"""Offline in-place raw-grain handoff using stock track ping-pong buffers.

Snapshot ready changes STATE -> AUDIO -> consumed. Native clear preserves raw
input only for enabled, active voices; source copy clears it before stock mix.
No separate audio mailbox allocation. Metadata addresses remain emulator-only.
"""
import core0
from granular_asm import assemble
from granular_route_candidate import AT,CONTROL,KEY,BUFFER,TEXTURE,TRIGGERED
from granular_snapshot_candidate import SNAPSHOT

AUDIO_KEY=0x674132
BANK=0x304f0
CLEAR_AT=0xfb8


def code():
    items=[('label','source'),'move y:>$1405,a','asl #2,a,a',f'add #>${CONTROL:x},a','move a1,r2',
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
