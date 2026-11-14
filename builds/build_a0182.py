"""A0181 plus white playhead / red held-step recording indication."""
from build_a0181 import HERE,build,automation3,heldlocks,storageshadow,sdyield_rp
import heldlights

def main():
    b=build('A0182')
    b.add('automation3',automation3)
    b.add('heldlocks',heldlocks)
    b.add('storageshadow',storageshadow,offload=True,automation=True)
    b.add('sdyield',sdyield_rp,magic=0x31464f53)
    b.add('heldlights',heldlights)
    out=b.finish(HERE/'firmware/a0182')
    for f in out.glob('circuitrhythm-5706-A0182.*'):
        f.replace(out/f'rhythmplus-A0182{f.suffix}')

if __name__=='__main__':main()
