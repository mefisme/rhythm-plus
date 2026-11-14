"""A0187 with FX-track exclusion before Track Parameter Editor entry/render."""
import os
os.environ['RH_GFX_EDITOR_GUARD']='1'
from build_a0187 import HERE,build,automation3,heldlocks,storageshadow,sdyield_rp,heldlights,automation3_ops

def main():
    b=build('A0188')
    b.add('automation3',automation3,cow=True)
    b.add('heldlocks',heldlocks)
    b.add('storageshadow',storageshadow,offload=True,automation=True)
    b.add('automation3_ops',automation3_ops)
    b.add('sdyield',sdyield_rp,magic=0x31464f53)
    b.add('heldlights',heldlights)
    out=b.finish(HERE/'firmware/a0188')
    for f in out.glob('circuitrhythm-5706-A0188.*'):f.replace(out/f'rhythmplus-A0188{f.suffix}')
if __name__=='__main__':main()
