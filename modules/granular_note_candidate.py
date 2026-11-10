"""Offline serial for notes actually accepted by A0122's native trigger queue.

The existing drone/legato handler is retained. Count at its downstream trigger
call, so held same-note drone messages do not become false grain retriggers.
Addresses are emulator-only until allocated safely.
"""
import core0
from granular_asm import assemble
AT,SERIAL,TEMP=0xfa0,0x38f10,0x38f18
NATIVE_TRIGGER=0xe3a


def code():
    import granular_snapshot_candidate as S
    bind=S.code()[1]['bind_note']
    items=[('label','note_on'),'move y1,a','and #>$7,a',f'add #>${SERIAL:x},a',f'move a1,y:>${TEMP:x}',
           ('jsr',NATIVE_TRIGGER),f'move r4,y:>${TEMP+1:x}',f'move y:>${TEMP:x},r4',
           'move y:(r4),a','add #>$1,a','move a1,y:(r4)',
           'move r4,a',f'sub #>${SERIAL:x},a',('jsr',bind),f'move y:>${TEMP+1:x},r4','rts']
    words,labels=assemble(items,AT)
    assert AT+len(words)<=0x1000
    return words,labels


def patched(segments):
    words,labels=code();output=[];seen=False
    for space,address,data in segments:
        data=list(data)
        if space=='p':
            assert not(address<AT+len(words) and AT<address+len(data))
            if address<=0x2f2<address+len(data):
                off=0x2f2-address
                assert data[off:off+2]==[0x0bf0a2,NATIVE_TRIGGER]
                data[off+1]=labels['note_on'];seen=True
        output.append((space,address,data))
    assert seen
    return output+[('p',AT,words)],dict(words=len(words),labels=labels)
