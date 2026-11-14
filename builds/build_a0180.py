"""Independent Shift K1-K3 automation in SD packs, companion bundle v2."""
import os
os.environ['RH_PROJECTPROBE']='0'
os.environ['RH_STORAGESHADOW']='1'
os.environ['RH_STEPMUT_OFFLOAD']='1'
os.environ['RH_AUTOMATION3']='1'
from build_a0176 import HERE,build
import automation3,storageshadow,sdyield_rp

def main():
    b=build('A0180')
    b.add('automation3',automation3)
    b.add('storageshadow',storageshadow,offload=True,automation=True)
    b.add('sdyield',sdyield_rp,magic=0x31464f53)
    out=b.finish(HERE/'firmware/a0180')
    for f in out.glob('circuitrhythm-5706-A0180.*'):
        f.replace(out/f'rhythmplus-A0180{f.suffix}')

if __name__=='__main__':main()
