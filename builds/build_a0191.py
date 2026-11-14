"""Fix candidate: keep panel IRQs running during private automation memory work."""
import os
os.environ['RH_GFX_NATIVE_EDGES']='1'
os.environ['RH_AUTOMATION_TASK_GUARD']='1'
os.environ['RH_GFX_INPUT_TRACE']='1'
from build_a0189 import HERE,build,automation3,heldlocks,storageshadow,sdyield_rp,heldlights,automation3_ops

def main():
    b=build('A0191')
    b.add('automation3',automation3,cow=True)
    b.add('heldlocks',heldlocks)
    b.add('storageshadow',storageshadow,offload=True,automation=True)
    b.add('automation3_ops',automation3_ops)
    b.add('sdyield',sdyield_rp,magic=0x31464f53)
    b.add('heldlights',heldlights)
    out=b.finish(HERE/'firmware/a0191')
    for f in out.glob('circuitrhythm-5706-A0191.*'):f.replace(out/f'rhythmplus-A0191{f.suffix}')
if __name__=='__main__':main()
