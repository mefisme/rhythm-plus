"""Build-time DSP integration for the offline granular staging image.

Wrap the existing upload builders before they run: never add program words after
the core1 landing has already started execution. No legacy granular/mixer path.
"""
from contextlib import contextmanager
import core0
import rhdsp1
import granular_layout as L
import granular_pool_candidate as P
import granular_inplace_candidate as I
import granular_snapshot_candidate as S
import granular_note_candidate as N
import granular_flow_candidate as F

INIT=0x2d00
FLAG,R0_SAVE=0x1fd8,0x1fd9
STOCK_WAIT=0x1a11


def clear(regions,tag):
    items=[]
    for index,region in enumerate(regions):
        space='y' if region.space=='shared' else region.space
        items += [f'move #>${region.start:x},r0',f'do #${region.words:x},${{{tag}_{index}:x}}',
                  f'move a,{space}:(r0)+',('label',f'{tag}_{index}')]
    return items


def init_code(pool_body):
    # Reset clears only what core 1 can read before core 0's main loop; the stock
    # startup must not wait behind the full clear.
    items=[('label','init')]
    for k in range(8):items += [('words',[0x05f420|k,0xffffff])]
    items += ['clr a',*clear([r for r in L.REGIONS if r.core==-1],'shared'),f'move a,y:>${FLAG:x}',('jmp',0x100)]
    # First main-loop pass, after the stock wait: clear core 0's own regions once.
    private=[r for r in L.REGIONS if r.core==0 and not FLAG<=r.start<r.end<=FLAG+2]
    items += [('label','first'),('jsr',STOCK_WAIT),f'move r0,y:>${R0_SAVE:x}',f'move y:>${FLAG:x},a','tst a',('jcc','ne','cleared'),
              'clr a',*clear(private,'private'),'move #>$1,a',f'move a1,y:>${FLAG:x}',
              ('label','cleared'),f'move y:>${R0_SAVE:x},r0',('jmp',pool_body)]
    words,labels=core0.asm_at(items,INIT)
    return words,labels


@contextmanager
def builders(cores=(0,1)):
    original1,original0=rhdsp1.install,core0.install
    def core1(img,report,base,code,key,**kwargs):
        if 1 not in cores:return original1(img,report,base,code,key,**kwargs)
        assert key=='pitchmod' and rhdsp1.START+len(code)<=I.AT,(key,hex(rhdsp1.START+len(code)),hex(I.AT))
        count,stock=rhdsp1.words(img)
        segments=rhdsp1.parse([count,0]+stock)[0]+[('p',rhdsp1.START,list(code))]
        before={address+i:word for space,address,words in segments if space=='p' for i,word in enumerate(words)}
        stages={}
        for name,module in (('route',I),('snapshot',S),('notes',N),('flow',F)):
            segments,stages[name]=module.patched(segments)
        after={address+i:word for space,address,words in segments if space=='p' for i,word in enumerate(words)}
        end=max(after)+1;combined=[after.get(address,0) for address in range(rhdsp1.START,end)]
        for address,word in before.items():
            if address<rhdsp1.START and after[address]!=word:rhdsp1.patch_p(img,address,word,after[address])
        labels=original1(img,report,base,combined,key,**kwargs)
        report.setdefault('granular',{}).update(integration_version=1,core1_start=hex(I.AT),core1_end=hex(end),core1_stages=stages,
            native_core1_words=len(code),core1_added_words=end-I.AT)
        return labels
    def core0_upload(img,report,base,**kwargs):
        if 0 not in cores:return original0(img,report,base,**kwargs)
        assert kwargs.get('loader') and not kwargs.get('counter')
        _,_,native=core0.block_words(img)
        assert native[:2]==[0x0c0100,0] and native[0x228:0x22a]==[0x0bf080,0x1a11]
        segments,pool=P.code(host_mailbox=True)
        assert P.AT+pool['words']<=INIT
        extras=[(address,words) for space,address,words in segments if space=='p']
        program={address+i:word for address,words in extras for i,word in enumerate(words)}
        wait=pool['labels']['after_wait']
        assert [program[wait],program[wait+1]]==[0x0bf080,STOCK_WAIT]
        initial,labels=init_code(wait+2)
        extras += [(INIT,initial),(0,[0x0af080,labels['init']]),(0x228,[0x0bf080,labels['first']])]
        kwargs['segs']=list(kwargs['segs'])+extras
        result=original0(img,report,base,**kwargs)
        report.setdefault('granular',{}).update(core0_segments=[dict(start=hex(address),words=len(words)) for address,words in extras if address>=0x1fed],
            pool=pool,init=hex(INIT),first_pass=hex(labels['first']),core0_initialized_regions=[region.owner for region in L.REGIONS if region.core in (-1,0)],
            regions=[dict(core=region.core,space=region.space,start=hex(region.start),words=region.words,owner=region.owner) for region in L.REGIONS],
            scope='DSP staging only; ARM transport/UI/project hooks not installed',shared_tail_hardware_proved=False)
        return result
    try:
        rhdsp1.install,core0.install=core1,core0_upload
        yield
    finally:rhdsp1.install,core0.install=original1,original0
