"""Read logical automation in either raw or adaptive firmware for assertions."""
from emu_playfix import call
from unicorn.arm_const import UC_ARM_REG_R0
def read(u,report,offset=0,size=4608):
    a=report['automation3']
    if not a.get('cow'):return bytes(u.mem_read(0x1500+offset,size))
    raw=bytearray()
    for lane in range(offset//192,(offset+size+191)//192):
        call(u,int(a['labels']['c_a3_bankread'],16),lane,0x20009000)
        assert u.reg_read(UC_ARM_REG_R0)==0
        raw.extend(u.mem_read(0x20009000,192))
    start=offset%192;return bytes(raw[start:start+size])
def write(u,report,raw,offset=0):
    a=report['automation3']
    if not a.get('cow'):u.mem_write(0x1500+offset,raw);return
    if offset==0 and len(raw)==4608:
        for lane in range(24):
            u.mem_write(0x20009000,raw[lane*192:lane*192+192])
            call(u,int(a['labels']['c_a3_bankimport'],16),lane,0x20009000,192,1)
            assert u.reg_read(UC_ARM_REG_R0)==0
    else:
        for i,v in enumerate(raw):call(u,int(a['labels']['c_a3_bankset'],16),0x1500,offset+i,v)
