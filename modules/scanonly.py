"""Keep sample-start scan while leaving the stock filters unchanged.

The archived Filter page's extra modes, pitch follow, coefficient copies and
second filter pass are not emitted. Existing stock LP/HP/resonance stay stock.
Call after nocomb.strip(), before pitchmod and fshape.strip(filt=False).
"""
import voicefilt as VF


def strip():
    original=VF.items
    def items():
        source=original()
        # hpidx remains an origin alias for pitchmod's segment validator only.
        return [("label","hpidx"),("label","post"),"rts"]+source[source.index(("label","scan")):]
    def patches(labels):
        return [(VF.P_SCAN,VF.OLD[VF.P_SCAN][0],VF.JSR_SHORT|labels["scan"])]
    VF.items,VF.patches=items,patches


def install(img,report,base_addr):
    import rhdsp1
    # Removal must leave all four stock filter patch sites byte-for-byte intact.
    for address in (VF.P_HPIDX,VF.P_LPIDX,VF.P_RES,VF.P_HPSAVE):
        for offset,word in enumerate(VF.OLD[address]):
            at=rhdsp1.where(img,address+offset)
            assert int.from_bytes(img[at:at+3],"big")==word
    report["scanonly"]={"stock_filters":True,"scan":report["pitchmod"]["filt"]["scan"]}
    return {},b""
