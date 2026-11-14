"""A0177 controlled lifecycle/timing baseline. No companion/offload installed."""
import os
os.environ['RH_PROJECTPROBE']='1'
from build_a0176 import HERE, build
import projectprobe


def main():
    b=build('A0177')
    b.add('projectprobe',projectprobe)
    out=b.finish(HERE/'firmware/a0177')
    for f in out.glob('circuitrhythm-5706-A0177.*'):
        f.replace(out/f'rhythmplus-A0177{f.suffix}')


if __name__=='__main__':main()
