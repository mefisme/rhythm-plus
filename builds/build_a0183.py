"""A0182 plus private automation / Grid FX Copy and Clear integration."""
import os
os.environ['RH_AUTO_BULK']='1'
from build_a0182 import HERE,build,automation3,heldlocks,storageshadow,sdyield_rp,heldlights
import automation3_ops

def main():
    b=build('A0183')
    b.add('automation3',automation3)
    b.add('heldlocks',heldlocks)
    b.add('storageshadow',storageshadow,offload=True,automation=True)
    b.add('automation3_ops',automation3_ops)
    b.add('sdyield',sdyield_rp,magic=0x31464f53)
    b.add('heldlights',heldlights)
    out=b.finish(HERE/'firmware/a0183')
    for f in out.glob('circuitrhythm-5706-A0183.*'):
        f.replace(out/f'rhythmplus-A0183{f.suffix}')

if __name__=='__main__':main()
