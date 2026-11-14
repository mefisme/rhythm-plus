"""Explicit per-track native sound-lane ownership; native banks stay unchanged."""
import rhbuild
from thumb import b_w

def install(img,report,base):
    L=report['granular']['arm_kernel']['labels']
    rhbuild.patch_word(img,0x080696ac,0x08049b29,L['c_gr_lane_inner']|1)
    rhbuild.patch_word(img,0x08068cf8,0x08036b05,L['c_gr_lane_gate']|1)
    site=0x08047ca8;head=bytes(img[site-rhbuild.BASE:site-rhbuild.BASE+4])
    img+=b'\xff'*(base-rhbuild.BASE-len(img))+head+b_w(base+4,site+4)
    while len(img)%4:img.append(255)
    rhbuild.patch(img,site,'|'.join(rhbuild.disasm(head,site)),b_w(site,L['c_gr_lane_stockclear']))
    rhbuild.patch(img,L['c_gr_lane_nativeclear'],'movs r0, #0|bx lr',b_w(L['c_gr_lane_nativeclear'],base))
    site=int(report['tmenu']['labels']['c_tmlane'],16)
    at=rhbuild.BASE+len(img);head=bytes(img[site-rhbuild.BASE:site-rhbuild.BASE+4])
    img+=head+b_w(at+4,site+4)
    rhbuild.patch(img,site,'|'.join(rhbuild.disasm(head,site)),b_w(site,L['c_gr_lane_stockview']))
    rhbuild.patch(img,L['c_gr_lane_nativeview'],'movs r0, #0|bx lr',b_w(L['c_gr_lane_nativeview'],at))
    report['granular']['lane_assignments']=dict(lanes=8,tracks=8,storage='GS v2 companion; values remain native',
        automatic_assignment=False,mixer_lanes_preserved=True)
