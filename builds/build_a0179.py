"""Controlled Step Mutate offload; mandatory companion reads run in Content."""
import os
os.environ['RH_PROJECTPROBE']='0'
os.environ['RH_STORAGESHADOW']='1'
os.environ['RH_STEPMUT_OFFLOAD']='1'
from build_a0176 import HERE,build
import storageshadow
import sdyield_rp


def main():
    b=build('A0179');b.add('storageshadow',storageshadow,offload=True)
    b.add('sdyield',sdyield_rp,magic=0x31464f53)
    out=b.finish(HERE/'firmware/a0179')
    for f in out.glob('circuitrhythm-5706-A0179.*'):
        f.replace(out/f'rhythmplus-A0179{f.suffix}')


if __name__=='__main__':main()
