"""Offline export of final native voice state for a core0 grain producer.

No firmware installation or physical shared-memory lease. Exports after native
Pitch+ processing: ready, epoch, frame, source, start, end, Q15 ratio, accepted-note serial.
Consumer-owned epoch/frame controls must already be coherently latched.
"""
import core0
from granular_asm import assemble
from granular_route_candidate import CONTROL,KEY
from granular_note_candidate import SERIAL

AT,SNAPSHOT,SAVE=0xf20,0x38c00,0x38f00
LIMIT=0xfa0  # Note-serial code starts here.
REFRESH_START_SHIFT,TRIGGER_START_SHIFT,SHIFT_WORD,JSR_SHORT=0x2a4,0x32d,0x0c1d93,0x0d0000
INACTIVE_STATE=0x674531


def code(scan=None):
    items=[('label','update'),('jsr',0x289),('jsr','bind_source'),('jsr','request'),('jsr','export'),'rts',('label','export')]
    for register in range(4):items += [f'move r{register},y:>${SAVE+register:x}']
    items += [f'move #>${KEY:x},x0','move #>$40,r0',f'move #>${SNAPSHOT:x},r3',
              f'move #>${CONTROL:x},r2',f'move #>${SERIAL:x},r1','do #$8,${export_end:x}',
              'clr a','move a,y:(r3)',
              'move y:(r2+$1),a','move a,y:(r3+$1)',
              'move y:(r2+$2),a','move a,y:(r3+$2)',
              'move x:(r0+$4),a','tst a',('jcc','eq','idle'),
              'move y:(r1),a','move a,y:(r3+$7)',
              'move y:(r0+$4),a','move a,y:(r3+$4)',
              'move y:(r0+$3),a','move a,y:(r3+$5)',
              'move y:(r0),a','move a,y:(r3+$6)',
              'move x0,y:(r3)',('jmp','skip'),('label','idle'),
              f'move #>${INACTIVE_STATE:x},a','move a,y:(r3)',('label','skip'),
              'lua (r0+$10),r0','lua (r3+$8),r3','lua (r2+$4),r2','move (r1)+',('label','export_end')]
    for register in range(4):items += [f'move y:>${SAVE+register:x},r{register}']
    items += ['rts',('label','request'),f'move r0,y:>${SAVE+4:x}',
              'move y:>$1602,a','add #>$1,a','move a1,x1',f'move #>${CONTROL+2:x},r0',
              'do #$8,${request_end:x}','move x1,y:(r0)','lua (r0+$4),r0',
              ('label','request_end'),f'move y:>${SAVE+4:x},r0','rts',
              ('label','bind_source'),'move y:>$121,a',('jmp','bind_note'),
              ('label','bind_note'),f'move r0,y:>${SAVE+5:x}',f'move a1,y:>${SAVE+6:x}',
              'asl #4,a,a','add #>$45,a','move a1,r0','move x:(r0),r0','move y:(r0),x0',
              f'move y:>${SAVE+6:x},a','asl #3,a,a',f'add #>${SNAPSHOT+3:x},a','move a1,r0','move x0,y:(r0)',
              f'move y:>${SAVE+5:x},r0','rts']
    if scan is not None:
        # Keeps FX Scan on enabled tracks when P:289 rewrites the region. Runs
        # before export, so SAVE is free; n3 is not live across this call.
        items += [('label','scan_refresh'),f'move r1,y:>${SAVE:x}','move y:>$121,a','move a1,n3',
                  'asl #2,a,a',f'add #>${CONTROL:x},a','move a1,r1','move y:(r1),a',
                  f'move y:>${SAVE:x},r1',f'cmp #>${KEY:x},a',('jcc','ne','scan_off'),
                  ('jmp',scan),('label','scan_off'),'asl #9,b,b','rts']
    words,labels=assemble(items,AT)
    assert AT+len(words)<=LIMIT,hex(AT+len(words))
    return words,labels


def patched(segments):
    scan=None
    for space,address,data in segments:
        if space=='p' and address<=TRIGGER_START_SHIFT<address+len(data):
            word=data[TRIGGER_START_SHIFT-address]
            if word&0xff0000==JSR_SHORT:scan=word&0xffff
    words,labels=code(scan);output=[];seen=False
    for space,address,data in segments:
        data=list(data)
        if space=='p':
            assert not (address<AT+len(words) and AT<address+len(data)), 'snapshot code overlaps existing program'
            if address<=0x122<address+len(data):
                assert data[0x122-address]==0x0d0289
                data[0x122-address]=0x0d0000|labels['update'];seen=True
            if scan is not None and address<=REFRESH_START_SHIFT<address+len(data):
                assert data[REFRESH_START_SHIFT-address]==SHIFT_WORD
                data[REFRESH_START_SHIFT-address]=JSR_SHORT|labels['scan_refresh']
        output.append((space,address,data))
    assert seen
    return output+[('p',AT,words)],dict(words=len(words),labels=labels)
