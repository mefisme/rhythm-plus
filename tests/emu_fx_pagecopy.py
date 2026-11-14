"""Native first-half duplication preserves packed FX and private automation."""
import sys
import emu_fx_native_edges as F
G,E,SM=F.G,F.E,F.SM
import automation_bank_helpers as BH
def main():
    u=F.setup();t=2
    for step,slot in ((0,21),(3,25),(15,22)):
        G.pad(u,step);G.pad(u,slot);G.unpad(u,slot);G.unpad(u,step)
    raw=bytearray(b'\xff'*4608)
    for k in range(3):
        for s in range(16):raw[k*1536+s*6]=k*20+s
    BH.write(u,E.MAN['report'],bytes(raw))
    codes=[G.pk_read(u,0,s) for s in range(16)]
    E.call(u,0x080480de,SM.obj(u,t))
    assert [G.pk_read(u,0,s) for s in range(16)]==codes
    assert [G.pk_read(u,0,s+16) for s in range(16)]==codes,'page duplication lost FX assignments'
    want=bytearray(raw)
    for k in range(3):want[k*1536+96:k*1536+192]=raw[k*1536:k*1536+96]
    assert BH.read(u,E.MAN['report'])==want,'page duplication lost automation or changed other patterns'
    print('PASS native page duplication copies FX assignments and all private cells; source and other patterns preserved')
    print('ALL PASS')
if __name__=='__main__':main()
