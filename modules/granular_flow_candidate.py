"""Offline Texture pitch-only command and native queue dispatcher candidate.

Native pitch refresh consumes voice Y+2. Updating only that note field allows
Flow notes to reach native tune/Pitch+ without restarting the voice envelope.
The ARM candidate must forward a real note-on if the voice is inactive.
"""
from granular_asm import assemble

AT,SAVE,DISPATCH=0xfd8,0x38f1a,0xfe8


def code():
    items=[('label','flow'),f'move r0,y:>${SAVE:x}',
           'move y1,a','and #>$7,a','asl #4,a,a','add #>$42,a','move a1,r0',
           'move y0,y:(r0)',f'move y:>${SAVE:x},r0','rts']
    words,labels=assemble(items,AT)
    return words,labels


def patched(segments):
    import granular_route_candidate as R
    words,labels=code()
    dispatch,extra=assemble([
        ('label','dispatch'),'cmp #>$a00000,b',('jcc','ne',0x4cd),
        'move y1,a','and #>$7,a','asl #2,a,a',f'add #>${R.CONTROL:x},a','move a1,r2',
        'move y:(r2),a',f'cmp #>${R.KEY:x},a',('jcc','ne',0x4cd),
        'move y:(r2+$3),a','tst a',('jcc','ne',0x4cd),('jmp',labels['flow'])],DISPATCH)
    additions=[('p',AT,words),('p',DISPATCH,dispatch)];output=[];seen=False
    for space,address,data in segments:
        data=list(data)
        if space=='p':
            for _,new_address,new_words in additions:
                assert not(address<new_address+len(new_words) and new_address<address+len(data))
            if address<=0x4e6<address+len(data):
                assert data[0x4e6-address]==0x050fc7
                data[0x4e6-address]=0x0c0000|extra['dispatch'];seen=True
        output.append((space,address,data))
    assert seen
    return output+additions,dict(words=len(words)+len(dispatch),body_words=len(words),labels={**labels,**extra})
