"""Controlled hardware baseline for native project lifecycle; no added SD I/O."""
from pathlib import Path
import rhbuild
import rhstate
from stepmut import compile_c
from thumb import b_w

HOOKS = ((0x08047270, 'load', 'push {r0, r1, r2, r3, r4, lr}|mov r0, r1'),
         (0x08037366, 'apply', 'push.w {r3, r4, r5, r6, r7, r8, sb, sl, fp, lr}'),
         (0x080472E2, 'save', 'push {r1, r2, r3, r4, r5, lr}|mov r4, r1'),
         (0x08047304, 'done', 'push {r3, r4, r5, lr}|mov r4, r0'))


def install(img, report, base_addr):
    # Four relocatable prologues followed by jumps back to original+4.
    prefix = bytearray()
    defs = dict(SLOT=rhstate.ST+rhstate.OFF['projectprobe'][0],
                C_RST=int(report['rhstate']['labels']['c_rst'],16))
    expected = {}
    for address, name, _ in HOOKS:
        old = bytes(img[address-rhbuild.BASE:address-rhbuild.BASE+4])
        text = '|'.join(rhbuild.disasm(old,address))
        # Exact expected text is checked before any patch; prologues contain no
        # PC-relative operands. Their final expected strings are fixed below.
        expected[name] = text
        defs['TR_'+name.upper()] = base_addr+len(prefix)
        prefix += old+b_w(base_addr+len(prefix)+4,address+4)
    need=tuple('c_pp_'+name for _,name,_ in HOOKS)
    code, labels = compile_c(base_addr+len(prefix), defs,
                            src=Path(__file__).with_suffix('.c'), name='projectprobe',
                            prefix='c_pp_',need=need,max_code=0x1800)
    for address,name,text in HOOKS:
        assert expected[name] == text, (name,expected[name],text)
    img += bytes([255])*(base_addr-rhbuild.BASE-len(img))+prefix+code
    while len(img)%4:img.append(255)
    for address,name,text in HOOKS:
        rhbuild.patch(img,address,text,b_w(address,labels['c_pp_'+name]))
    report['projectprobe']=dict(slot=hex(defs['SLOT']),bytes=1056,events=32,
        added_sd_io=False,offload=False,labels={k:hex(v) for k,v in labels.items()},
        trampolines={k:hex(v) for k,v in defs.items() if k.startswith('TR_')},
        hooks={name:hex(address) for address,name,_ in HOOKS})
    return labels,code
