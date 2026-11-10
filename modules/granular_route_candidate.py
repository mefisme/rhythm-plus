"""Offline DSP1 source-injection candidate, NOT installed in firmware.

Mailbox/control addresses are emulator-only. Consumer-owned controls must be
latched at a block boundary. Producer clears ready before writes and publishes
ready last, never rewriting the same epoch/sequence. A stale/torn packet silences
this source block; disabled tracks branch to the original sample reader.
"""
import core0
from granular_asm import assemble

AT=0xeac
CONTROL,MAILBOX=0x38000,0x38400  # Emulator-only, NOT a unit memory lease.
KEY=0x674e31
BUFFER=0x2a02
# Control word 3: 1 keeps the native reader, so grains end with a One Shot sample.
TEXTURE,TRIGGERED=0,1


def code():
    items=[('label','source'),
           'move y:>$1405,a','asl #2,a,a',f'add #>${CONTROL:x},a','move a1,r2',
           'move y:(r2),a',f'move #>${KEY:x},x0','cmp x0,a',('jcc','ne','stock_reader'),
           'move y:(r2+$3),a','tst a',('jcc','eq','snapshot_source'),('jsr',0x1e5),
           'move y:>$1405,a','asl #2,a,a',f'add #>${CONTROL:x},a','move a1,r2',
           ('label','snapshot_source'),
           'move y:>$1405,a','asl #6,a,a',f'add #>${MAILBOX:x},a','move a1,r3',
           'move y:(r2+$1),y0','move y:(r2+$2),x1',
           ('jsr','validate'),('jcc','ne','silent'),
           'move r3,a','add #>$3,a','move a1,r5',f'move #>${BUFFER:x},r1',
           'do #$20,${copy_end:x}','move y:(r5)+,a','move a,x:(r1)+',('label','copy_end'),
           ('label','copied'),('jsr','validate'),('jcc','ne','silent'),('label','consumed'),'clr a','move a,y:(r3)','rts',
           ('label','validate'),'move y:(r3),a','cmp x0,a',('jcc','ne','invalid'),
           'move y:(r3+$1),a','cmp y0,a',('jcc','ne','invalid'),
           'move y:(r3+$2),a','cmp x1,a',('label','invalid'),'rts',
           ('label','silent'),'clr a','move a,y:(r3)',f'move #>${BUFFER:x},r1',
           'do #$20,${zero_end:x}','move a,x:(r1)+',('label','zero_end'),'rts',
           ('label','stock_reader'),('jmp',0x1e5),
           ('label','fade'),'move y:>$1405,a','asl #2,a,a',f'add #>${CONTROL:x},a','move a1,r2',
           'move y:(r2),a',f'move #>${KEY:x},x0','cmp x0,a',('jcc','ne','stock_fade'),
           'move y:(r2+$3),a','tst a',('jcc','ne','stock_fade'),'rts',
           ('label','stock_fade'),('words',[0x0438f4,0x56e400]),('jmp',0x25e)]
    words,labels=assemble(items,AT)
    assert AT+len(words)<=0x1000,hex(AT+len(words))
    return words,labels


def patched(segments):
    words,labels=code()
    output=[];seen=set()
    expected={0x23d:0x0d01e5,0x25c:0x0438f4,0x25d:0x56e400}
    replacements={0x23d:0x0d0000|labels['source'],0x25c:0x0af080,0x25d:labels['fade']}
    for space,address,data in segments:
        data=list(data)
        if space=='p':
            assert not (address<AT+len(words) and AT<address+len(data)), 'candidate code overlaps existing firmware'
            for site,old in expected.items():
                if address<=site<address+len(data):
                    assert data[site-address]==old,(hex(site),hex(data[site-address]))
                    data[site-address]=replacements[site];seen.add(site)
        output.append((space,address,data))
    assert seen==set(expected)
    return output+[('p',AT,words)],dict(words=len(words),labels=labels)
