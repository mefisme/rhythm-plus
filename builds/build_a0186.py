"""A0185 with private knob gestures cancelling native step tap toggles."""
import os
os.environ['RH_PRIVATE_GESTURE']='1'
from build_a0185 import HERE,build,automation3,heldlocks,storageshadow,sdyield_rp,heldlights,automation3_ops

def main():
    b=build('A0186')
    b.add('automation3',automation3,cow=True)
    b.add('heldlocks',heldlocks)
    b.add('storageshadow',storageshadow,offload=True,automation=True)
    b.add('automation3_ops',automation3_ops)
    b.add('sdyield',sdyield_rp,magic=0x31464f53)
    b.add('heldlights',heldlights)
    out=b.finish(HERE/'firmware/a0186')
    for f in out.glob('circuitrhythm-5706-A0186.*'):f.replace(out/f'rhythmplus-A0186{f.suffix}')
if __name__=='__main__':main()
