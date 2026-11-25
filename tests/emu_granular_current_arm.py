"""Restored AG controls on the current build; no legacy persistence calls."""
import struct
import emu_fx_native_edges as F
G,E,SM=F.G,F.E,F.SM
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_R0,UC_ARM_REG_R1
def main():
    u=F.setup();r=E.MAN['report'];g=r['granular'];b=g['bridge'];ui=g['ui']
    slot=int(b['slot'],16);menu=int(ui['menu'],16)
    K=g['arm_kernel']['labels'];B={k:int(v,16) for k,v in b['labels'].items()}
    UI={k:int(v,16) for k,v in ui['labels'].items()}
    frames=[]
    def ret(uc,a,n,d):uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,ret,None,int(b['previous_frame'],16),int(b['previous_frame'],16)+1)
    def frame(uc,a,n,d):frames.append(uc.reg_read(UC_ARM_REG_R1));ret(uc,a,n,d)
    u.hook_add(UC_HOOK_CODE,frame,None,K['c_gr_runtime_frame'],K['c_gr_runtime_frame']+1)
    def forbidden(uc,a,n,d):raise AssertionError('legacy granular persistence reached')
    for name in ('project_save','project_load','levels_save','levels_load','shift_save','shift_load'):
        if 'c_gr_'+name not in K:continue  # companion-only builds remove these dead entries
        at=K['c_gr_'+name];u.hook_add(UC_HOOK_CODE,forbidden,None,at,at+1)
    E.call(u,UI['c_gustate'])
    ready,wait,upload=(int(b[k],16) for k in ('ready','wait','upload'))
    assert wait==slot+(468 if g.get('fine_controls') else 404),'readiness counter overlaps runtime state'
    u.mem_write(ready,b'\xa0');u.mem_write(wait,b'\0');u.mem_write(upload,b'\0')
    for i in range(199):E.call(u,B['c_gframe'],E.C.CTRL,0x20005000)
    assert not any(frames),'DSP activated before private readiness interval'
    E.call(u,B['c_gframe'],E.C.CTRL,0x20005000);assert frames[-1]==1
    u.mem_write(upload,b'\x01');E.call(u,B['c_gframe'],E.C.CTRL,0x20005000)
    assert frames[-1]==0 and u.mem_read(wait,1)==b'\0'
    u.mem_write(upload,b'\0')
    SM.sel(u,0);u.mem_write(menu+E.T.O_OPEN,b'\x01')
    u.mem_write(G.CONT+0x264,b'\0');u.mem_write(0x20000820,struct.pack('<I',1000))
    G.pad(u,ui['page_pad']);G.unpad(u,ui['page_pad'])
    E.call(u,K['c_gr_runtime_page'],slot,0);assert u.reg_read(UC_ARM_REG_R0)==1
    E.call(u,K['c_gr_params_get'],slot+104,0,0);before=u.reg_read(UC_ARM_REG_R0)
    G.knob(u,0,7)
    E.call(u,K['c_gr_params_get'],slot+104,0,0);assert u.reg_read(UC_ARM_REG_R0)==min(127,before+7)
    if ui.get('arrow_pages'):
        primary=min(127,before+7)
        E.press(u,19);E.release(u,19)
        assert u.mem_read(menu+E.T.O_OPEN,1)==b'\x01','Down closed editor or reached stock octave handling'
        E.call(u,K['c_gr_runtime_knob_page'],slot,0);assert u.reg_read(UC_ARM_REG_R0)==1
        G.knob(u,0,-4);assert u.mem_read(slot+212,1)==b'\x3c','page 2 K1 did not edit Level without Shift'
        E.call(u,K['c_gr_params_get'],slot+104,0,0);assert u.reg_read(UC_ARM_REG_R0)==primary
        SM.sel(u,1)
        E.call(u,K['c_gr_runtime_knob_page'],slot,1);assert u.reg_read(UC_ARM_REG_R0)==0,'page leaked to other track'
        SM.sel(u,0);E.press(u,20);E.release(u,20)
        E.call(u,K['c_gr_runtime_knob_page'],slot,0);assert u.reg_read(UC_ARM_REG_R0)==0
        assert u.mem_read(menu+E.T.O_OPEN,1)==b'\x01','Up closed editor or reached stock octave handling'
        print('PASS Down selects secondary knobs without Shift; Up restores primary; pages isolated per track')
    # Canonical companion settings round-trip, with fail-closed validation.
    if 'c_gr_runtime_settings_store' in K:
        scratch=0x20001000
        E.call(u,K['c_gr_runtime_settings_store'],slot,scratch)
        assert u.reg_read(UC_ARM_REG_R0)==1
        fine=bool(g.get('fine_controls'));n,size=(288,468) if fine else (224,404)
        storage=E.MAN['report'].get('storageshadow',{})
        n=storage.get('granular_settings_bytes',n)
        version=storage.get('granular_settings_version')
        if fine:u.mem_write(slot+404,bytes(range(16))*4)
        E.call(u,K['c_gr_runtime_settings_store'],slot,scratch)
        saved=bytes(u.mem_read(scratch,n))
        assert saved[:2]==b'GS' and saved[2] in ((version,) if version else (5,) if fine else (2,3,4)) and saved[3]==8
        original=bytes(u.mem_read(slot,size))
        u.mem_write(scratch+15,bytes([saved[15]^1]))
        E.call(u,K['c_gr_runtime_settings_load'],slot,scratch)
        assert u.reg_read(UC_ARM_REG_R0)==0
        assert bytes(u.mem_read(slot,size))==original,'corrupt settings partially changed runtime'
        u.mem_write(scratch,saved)
        u.mem_write(slot+104,b'\x01'*64)
        E.call(u,K['c_gr_runtime_settings_load'],slot,scratch)
        assert u.reg_read(UC_ARM_REG_R0)==1
        assert bytes(u.mem_read(slot+104,64))==saved[8:72]
        if fine:assert bytes(u.mem_read(slot+404,64))==saved[224:288]==bytes(range(16))*4
        E.call(u,K['c_gr_runtime_settings_store'],slot,scratch)
        assert bytes(u.mem_read(scratch,n))==saved,'companion round-trip changed settings'
        print('PASS companion settings round-trip and corrupt-data rejection; no legacy tail access')
    E.call(u,UI['c_gucommit'],slot)  # Must never access fragmented legacy tail.
    SM.sel(u,2);u.mem_write(menu+E.T.O_OPEN,b'\x01')
    E.call(u,UI['c_gucontext']);assert u.reg_read(UC_ARM_REG_R0)==8,'FX controller track can enter granular'
    # Attempt FX assignment through the actual Sample-mode pad gesture.
    u.mem_write(menu+E.T.O_OPEN,b'\0');u.mem_write(G.CONT+0x264,b'\x09')
    G.pad(u,7);G.unpad(u,7)  # Remove the fixture's existing FX track first.
    assert u.mem_read(G.blk(u)+12,1)==b'\xff'
    SM.sel(u,0);u.mem_write(menu+E.T.O_OPEN,b'\0');u.mem_write(G.CONT+0x264,b'\x09')
    u.mem_write(slot+168,b'\x12')  # Granular Texture requested on track 1.
    fx_before=bytes(u.mem_read(G.blk(u),26))
    for _ in range(2):G.pad(u,7);G.unpad(u,7)
    assert bytes(u.mem_read(G.blk(u),26))==fx_before,'granular track replaced FX controller'
    u.mem_write(slot+168,b'\x10')  # Off, but transition not yet acknowledged.
    u.mem_write(slot+10,b'\x01')
    for _ in range(2):G.pad(u,7);G.unpad(u,7)
    assert bytes(u.mem_read(G.blk(u),26))==fx_before,'pending granular transition allowed FX assignment'
    u.mem_write(slot+10,b'\0')
    for _ in range(2):
        G.pad(u,7);G.unpad(u,7)
        if u.mem_read(G.blk(u)+12,1)==b'\0':break
    assert u.mem_read(G.blk(u)+12,1)==b'\0','idle granular-off track cannot become FX controller'
    print('PASS independent readiness interval, upload reset and existing AG knob/page controls')
    print('PASS FX-sequencer track excluded; legacy fragmented persistence never called')
    print('PASS active/pending granular blocks FX assignment; fully off permits it')
    print('ALL PASS')
if __name__=='__main__':main()
