"""Controlled Step Mutate SD mirror. Embedded settings remain authoritative."""
import os
os.environ['RH_PROJECTPROBE']='0'
os.environ['RH_STORAGESHADOW']='1'
from build_a0176 import HERE,build
import storageshadow
import sdyield_rp


def main():
    b=build('A0178');b.add('storageshadow',storageshadow)
    b.add('sdyield',sdyield_rp)
    out=b.finish(HERE/'firmware/a0178')
    for f in out.glob('circuitrhythm-5706-A0178.*'):
        f.replace(out/f'rhythmplus-A0178{f.suffix}')


if __name__=='__main__':main()
