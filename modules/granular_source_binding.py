"""Experimental per-grain source binding for the offline Remix renderer.

NOT installed by A0121. Single-engine reference only. The48 Y words below are
emulator storage, not an ownership claim for the unit. Each grain retains its
page-table pointer, source start and source length while new grains may use a
new step source. Pack/sample deletion lifetime handling remains unimplemented.
"""
import granular0 as G

META=0x1f80
WORDS=G.MAXG*3


def items(source):
    assert G.GW==12 and G.MAXG==16
    result=list(source)
    #12-word grain stride /4 ->3-word metadata stride, without division.
    address=['move r2,a',f'sub #>${G.GR0:x},a','lsr #2,a',
             f'add #>${META:x},a','move a1,r4']
    save=address+sum(([f'move x:(r7+${field:x}),x0','move x0,y:(r4)+']
                      for field in (G.V_TAB,G.V_S,G.V_L)),[])
    load=address+sum((['move y:(r4)+,x0',f'move x0,x:(r7+${field:x})']
                      for field in (G.V_TAB,G.V_S,G.V_L)),[])
    at=result.index(('label','g_sok'))+1
    result[at:at]=save
    at=result.index(('label','g_grain'))+1
    result[at:at]=load
    return result


def code(**kwargs):
    if kwargs.get('multi'):raise ValueError('offline single-engine proof only')
    original=G.items
    try:
        G.items=lambda *a,**k:items(original(*a,**k))
        return G.code(**kwargs)
    finally:G.items=original
