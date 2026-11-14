"""A0180 plus audible gate-boundary retrigger and stock recording LEDs."""
import os
os.environ['RH_GFX_RETRIGGER']='1'
os.environ['RH_GFX_FEEDBACK']='1'
from build_a0180 import HERE,build,automation3,storageshadow,sdyield_rp
import heldlocks

def main():
    b=build('A0181')
    b.add('automation3',automation3)
    b.add('heldlocks',heldlocks)
    b.add('storageshadow',storageshadow,offload=True,automation=True)
    b.add('sdyield',sdyield_rp,magic=0x31464f53)
    out=b.finish(HERE/'firmware/a0181')
    for f in out.glob('circuitrhythm-5706-A0181.*'):
        f.replace(out/f'rhythmplus-A0181{f.suffix}')

if __name__=='__main__':main()
