"""A0184 with segmented core0 upload instead of a duplicate DSP image."""
import os
os.environ['RH_GFX_SEGMENTS']='1'
from build_a0184 import HERE,build,automation3,heldlocks,storageshadow,sdyield_rp,heldlights,automation3_ops
def main():
    b=build('A0185')
    b.add('automation3',automation3,cow=True)
    b.add('heldlocks',heldlocks)
    b.add('storageshadow',storageshadow,offload=True,automation=True)
    b.add('automation3_ops',automation3_ops)
    b.add('sdyield',sdyield_rp,magic=0x31464f53)
    b.add('heldlights',heldlights)
    out=b.finish(HERE/'firmware/a0185')
    for f in out.glob('circuitrhythm-5706-A0185.*'):f.replace(out/f'rhythmplus-A0185{f.suffix}')
if __name__=='__main__':main()
