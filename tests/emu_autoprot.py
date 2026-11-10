"""One-lane actual ARM kernel, stock 12-lane playback, bounded DSP model.
Runs only the hardware transport mocks; cache, 14-bit arithmetic, stock interpolation,
UI wrappers, recorder bridge and DSP conversion execute from firmware bytes.
"""
import os,sys,struct,random
from pathlib import Path
os.environ['RH_AUTOPROT']='1'
import emu_tmenu as E
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE,UC_HOOK_MEM_READ
from unicorn.arm_const import *
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from automation_model import Bank as EventBank, StockTiming, SparsePlayer

def main():
 _,fw,ram=(Path(p).read_bytes() for p in sys.argv[1:4]);u=E.setup(fw,ram)
 rep=E.MAN['report']['autoprot'];L={k:int(v,16) for k,v in rep['labels'].items()};C={k:int(v,16) for k,v in rep['config'].items()}
 memory={0x4000+i:0 for i in range(192)};locked=[False];deliver=[];io=[];race=[False];journal=[];cycles=[0]
 def w(a,v):u.mem_write(a,struct.pack('<I',v))
 def word(a):return E.u32(u,a)
 def ret(v=0):u.reg_write(UC_ARM_REG_R0,v);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
 def hook(uc,a,n,d):
  x,y,z=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
  if a==0x8029c8c:
   if x==0x20003688:
    assert not locked[0];locked[0]=True
    if race[0]:uc.mem_write(C['UPLOAD_ADDR'],b'\x01')
   ret()
  elif a==0x8030eb8:
   if word(x)==0x20003688:assert locked[0];locked[0]=False
   ret()
  elif a==0x8031268:
   assert locked[0] and x==0 and y in memory;io.append(('r',y));ret(memory[y]<<8)
  elif a==0x80311da:
   if x==0 and z in memory:
    assert locked[0] and y&255==0;memory[z]=y>>8;io.append(('w',z))
   ret()
  elif a==C['SP_WRITE']:deliver.append((x,y));journal.append('extra');ret()
 for a in [0x8029c8c,0x8030eb8,0x8031268,0x80311da,C['SP_WRITE']]:u.hook_add(UC_HOOK_CODE,hook,None,a,a+1)
 def cycle_tick(uc,access,address,size,value,data):
  if E.u32(uc,0xe0001000)&1:
   cycles[0]=(cycles[0]+100)&0xffffffff;uc.mem_write(0xe0001004,struct.pack('<I',cycles[0]))
 u.hook_add(UC_HOOK_MEM_READ,cycle_tick,None,0xe0001004,0xe0001007)
 def run(name,*args):E.call(u,L[name],*args);assert not locked[0];return u.reg_read(UC_ARM_REG_R0)
 def tr(i,v):
  p=E.ptr(u,0x200122b0,i);u.mem_write(p,struct.pack('<I',v))
 def ready():
  u.mem_write(C['READY_ADDR'],bytes([C['READY_VALUE']]));u.mem_write(C['WAIT_ADDR'],b'\xc8');u.mem_write(C['UPLOAD_ADDR'],b'\0')
  w(0xe000ef90,0x73);w(0xe000ed08,0x8010000);w(0xe000ed94,0)
  w(0xe0001000,0x100);w(0xe000edfc,0x20);w(0xe0001fb4,3)
 ready();tr(0,0);tr(1,0);tr(2,0)
 record=word(0x2003c0cc);stock=bytes(u.mem_read(record,0x29484))
 # Never read ITCM before an explicit arm through the initialized private enable word.
 E.check('prototype starts disabled',word(C['FLAG_ADDR'])==0)
 tr(0,1);E.check('arming rejected while playing',run('c_aparm')==2 and not io);tr(0,0)
 memory[0x4007]=1234;E.check('occupied candidate RAM rejected',run('c_aparm')==6 and not any(t=='w' for t,_ in io));memory[0x4007]=0;io.clear()
 E.check('explicit arm initializes only its fixed 192 DSP words',run('c_aparm')==0 and set(memory.values())=={65535})
 # Layout from C struct, asserted via successful sentinel/round-trip checks.
 CACHE=0x128;HELD=0x118;LAST=0x11a;OUTPUT=0x11c;PENDING=0x11e;PREV=0x122
 E.check('empty 14-bit cache initialized',bytes(u.mem_read(CACHE,384))==b'\xff'*384)
 def lane(vals):u.mem_write(CACHE,struct.pack('<192H',*vals))
 # A stock one-lane descriptor and custom synthetic stores remain INSIDE physical ITCM.
 obj,vt,sink,provider,put=0x800,0x900,0xa00,0x08000180,0x08000190
 stores={};events=[];provider_lanes={}
 w(vt+0x14,provider|1);w(sink,vt+0x40);w(vt+0x40,put|1);w(obj,vt);w(obj+0x2c,sink)
 for i,off in enumerate([0xc,0x10,0x30,0x34,0x38]):
  st=0xb00+i*0x40;stores[st]=st+0x20;w(obj+off,st);w(st+0x20,0);w(st+0x24,0)
 w(stores[word(obj+0x30)],1);u.mem_write(obj+0x3c,b'\x01');w(obj+0x40,0xd00);w(0xd00,0x200);w(obj+0x44,0xff00);w(obj+0x48,0xd10);w(obj+0x4c,0xd14)
 def sh(uc,a,n,d):
  x,y,z=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
  if a==0x803fc58:
   if x not in stores:return
   ret(stores[x]+y*4)
  elif a==provider:ret(provider_lanes.get(y,0x2000))
  elif a==put:events.append(z);ret()
 for a in [0x803fc58,provider,put]:u.hook_add(UC_HOOK_CODE,sh,None,a,a+1)
 rng=random.Random(4);positions=0
 for case in range(8):
  values=[255 if rng.random()<.55 else rng.randrange(128) for i in range(192)]
  u.mem_write(0x2000,bytes(values));lane([65535 if v==255 else v for v in values])
  eventbank=EventBank()
  for step in range(32):
   eventbank.record_step(0,step,{0},{(0,m):values[step*6+m] for m in range(6) if values[step*6+m]!=255})
  for rate,length in enumerate([2,3,4,6,8,12,16,24]):
   sparse=SparsePlayer(StockTiming(fw))
   w(stores[word(obj+0x10)]+4,rate);w(stores[word(obj+0xc)],0);w(stores[word(obj+0xc)]+4,1)
   u.mem_write(HELD,b'\xff\xff');u.mem_write(0xd10,b'\xff\xff');u.mem_write(0xd14,b'\xff\xff')
   for step in [0,1,15,16,31,0]:
    for pulse in range(length):
     events.clear();E.call(u,0x8055324,obj,0,step,pulse)
     actual=run('c_apvalue',rate,step,pulse,65535 if values[6]==255 else values[6])
     expected=struct.unpack('<H',u.mem_read(0xd14,2))[0]
     assert actual==expected,(case,rate,step,pulse,actual,expected)
     candidate=sparse.value(eventbank.patterns[0],0,rate,step,pulse,None if values[6]==255 else values[6])
     assert (65535 if candidate is None else candidate)==expected,('host sparse',case,rate,step,pulse)
     expected_held=struct.unpack('<H',u.mem_read(0xd10,2))[0]
     assert (65535 if sparse.held is None else sparse.held)==expected_held
     assert bytes(u.mem_read(HELD,2))==bytes(u.mem_read(0xd10,2))
     positions+=1
 E.check(f'14-bit playback algorithm matches actual stock for {positions} byte-domain positions at all 8 rates',True)
 E.check(f'host sparse-event player matches actual stock values and held state at the same {positions} positions',True)
 # Next-pattern lookahead must interpolate toward the real next pattern, not
 # wrap to step zero of the current one. Compare actual sink deliveries too.
 chainbank=EventBank();chainvalues={}
 for pattern in (0,1):
  vals=[255 if rng.random()<.45 else rng.randrange(128) for _ in range(192)]
  vals[0]=20+pattern*70;vals[-1]=100-pattern*60
  chainvalues[pattern]=vals;provider_lanes[pattern]=0x2000+pattern*0x400
  u.mem_write(provider_lanes[pattern],bytes(vals))
  for step in range(32):
   chainbank.record_step(pattern,step,{0},{(0,m):vals[step*6+m] for m in range(6) if vals[step*6+m]!=255})
 schedule=[(p,s) for p in (0,1,0) for s in range(32)];chain_checks=0
 for rate,length in enumerate([2,3,4,6,8,12,16,24]):
  sparse=SparsePlayer(StockTiming(fw));w(stores[word(obj+0x10)]+4,rate)
  u.mem_write(0xd10,b'\xff\xff');u.mem_write(0xd14,b'\xff\xff')
  for i,(pattern,step) in enumerate(schedule):
   np,ns=schedule[(i+1)%len(schedule)]
   w(stores[word(obj+0xc)],np);w(stores[word(obj+0xc)]+4,ns)
   nv=chainvalues[np][ns*6];nv=None if nv==255 else nv
   for pulse in range(length):
    events.clear();E.call(u,0x8055324,obj,pattern,step,pulse)
    value=sparse.tick(chainbank.patterns[pattern],0,rate,step,pulse,nv)
    assert events==([] if value is None else [value]),('chain output',rate,pattern,step,pulse,value,events)
    actual_held=struct.unpack('<H',u.mem_read(0xd10,2))[0]
    assert actual_held==(65535 if sparse.held is None else sparse.held),('chain held',rate,pattern,step,pulse)
    chain_checks+=1
 provider_lanes.clear()
 E.check(f'host sparse playback matches stock deliveries and held state across {chain_checks} chained-pattern ticks, all 8 rates',True)
 # Fine values must stay distinct; direct interpolation independently computed.
 vals=[65535]*192;vals[:7]=[8193,8197,12003,16383,1,0,16379];lane(vals);u.mem_write(HELD,b'\xff\xff')
 for pulse in range(24):
  a=pulse//4;w0,w1=bytes(u.mem_read(0x806645c+3*48+pulse*2,2))
  expected=(vals[a]*w0+vals[a+1]*w1)>>3
  assert run('c_apvalue',7,0,pulse,vals[6])==expected
 E.check('14-bit fine values and interpolation preserve low seven bits',True)
 # Recording -> real DSP backing -> invalidate cache -> CPU refill -> playback candidate.
 lane([65535]*192);u.mem_write(PREV,b'\0');io.clear()
 for rate in range(8):
  u.mem_write(PREV,b'\0')
  for pulse in range([2,3,4,6,8,12,16,24][rate]):run('c_aprecord',rate,3,pulse,10001+pulse)
 E.check('recording writes only bounded DSP backing',any(t=='w' for t,a in io))
 before=bytes(u.mem_read(CACHE,384));u.mem_write(CACHE,b'\xaa'*384)
 E.check('refill recovers exact recorded 14-bit lane from DSP',run('c_aprefill')==0 and bytes(u.mem_read(CACHE,384))==before)
 E.check('core recording/playback/refill leave whole stock project unchanged',bytes(u.mem_read(record,0x29484))==stock)
 # Differential recording against the real stock live-record helpers.
 robj,rvt,ratehook=0x1400,0x1480,0x080001a0;current_rate=[0]
 w(robj,rvt);w(rvt+8,ratehook|1);w(rvt+0x1c,provider|1)
 w(robj+0xc,word(obj+0xc));w(robj+0x38,0x1500);w(robj+0x3c,0x1510)
 u.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:ret(current_rate[0]),None,ratehook,ratehook+1)
 rec_checks=0
 for rate,length in enumerate([2,3,4,6,8,12,16,24]):
  current_rate[0]=rate;w(0x1500,0);u.mem_write(0x1510,b'\xff');u.mem_write(0x2000,b'\xff'*192)
  lane([65535]*192);u.mem_write(PREV,b'\0')
  for step in [0,1,15,31,0]:
   w(stores[word(obj+0xc)],0);w(stores[word(obj+0xc)]+4,step)
   for pulse in range(length):
    value=rng.randrange(128)
    E.call(u,0x8049706,robj,0,value,0)
    E.call(u,0x80497ec,robj,0,pulse,value)
    run('c_aprecord',rate,step,pulse,value)
    narrow=bytes(u.mem_read(0x2000,192));wide=struct.unpack('<192H',u.mem_read(CACHE,384))
    assert wide==tuple(65535 if x==255 else x for x in narrow),(rate,step,pulse)
    rec_checks+=1
 E.check(f'live-record interpolation matches actual stock across {rec_checks} points and all 8 rates',True)
 # A taken stock lane also writes empty ticks, erasing previous overdub points.
 if rep.get('audit_batch'):
  gap_checks=0
  for rate,length in enumerate([2,3,4,6,8,12,16,24]):
   current_rate[0]=rate;w(0x1500,0);u.mem_write(0x1510,b'\xff')
   old=[rng.randrange(128) for _ in range(192)]
   u.mem_write(0x2000,bytes(old));lane(old);u.mem_write(PREV,b'\0')
   for tick in range(length*64):
    step=(tick//length)%32;pulse=tick%length
    w(stores[word(obj+0xc)],0);w(stores[word(obj+0xc)]+4,step)
    value=rng.randrange(128) if tick%7==0 else 255
    E.call(u,0x8049706,robj,0,value,0)
    E.call(u,0x80497ec,robj,0,pulse,value)
    run('c_aprecord',rate,step,pulse,65535 if value==255 else value)
    narrow=bytes(u.mem_read(0x2000,192));wide=struct.unpack('<192H',u.mem_read(CACHE,384))
    assert wide==tuple(65535 if x==255 else x for x in narrow),(rate,step,pulse,'empty overdub')
    gap_checks+=1
  E.check(f'taken-lane empty ticks and loop returns match stock across {gap_checks} ticks',True)
 # Manual moves must obey stock last-applied/held comparisons, not a fabricated latch.
 if rep.get('audit_batch'):
  tr(0,0);tr(1,0);run('c_aparm')
  narrow=[255]*192;narrow[0]=64;narrow[48]=0
  u.mem_write(0x2000,bytes(narrow));lane([65535 if v==255 else v*128 for v in narrow])
  w(stores[word(obj+0x10)]+4,3)
  w(E.ptr(u,word(0x200470d4+0x10),1),3)
  u.mem_write(0xd10,b'\xff\xff');u.mem_write(0xd14,b'\xff\xff')
  def refplay(step,pulse):events.clear();E.call(u,0x8055324,obj,0,step,pulse);return events.copy()
  # No reset callback: both stock and extra must apply the first lock after a stopped manual move.
  run('c_apmanual',0,0,12800);tr(0,1)
  assert refplay(0,0)==[64]
  run('c_applay',0x200470d4,0,0,0)
  assert struct.unpack('<H',u.mem_read(OUTPUT,2))[0]==8192
  # An unchanged automated value is not resent by stock just to undo a manual move.
  run('c_apmanual',0,0,12800);deliver.clear()
  assert refplay(0,0)==[]
  run('c_applay',0x200470d4,0,0,0)
  assert not deliver and struct.unpack('<H',u.mem_read(OUTPUT,2))[0]==12800
  # A distinct subsequent lock resumes without Stop/Play.
  assert refplay(8,0)==[0]
  run('c_applay',0x200470d4,0,8,0)
  assert struct.unpack('<H',u.mem_read(OUTPUT,2))[0]==0
  E.check('manual stopped/running moves match stock first-lock, unchanged-value, and next-distinct-lock semantics without synthetic resets',True)
  tr(0,0);run('c_aparm')
  narrow=[255]*192;narrow[0:3]=[64,32,16]
  u.mem_write(0x2000,bytes(narrow));lane([65535 if v==255 else v*128 for v in narrow])
  w(stores[word(obj+0x10)]+4,0);w(E.ptr(u,word(0x200470d4+0x10),1),0)
  u.mem_write(0xd10,b'\xff\xff');u.mem_write(0xd14,b'\xff\xff');tr(0,1)
  assert refplay(0,0)==[64];run('c_applay',0x200470d4,0,0,0)
  run('c_apmanual',0,0,12800)
  assert refplay(0,1)==[16];run('c_applay',0x200470d4,0,0,1)
  E.check('manual move retains stock fast-rate held microstep behavior',struct.unpack('<H',u.mem_read(OUTPUT,2))[0]==2048)
  tr(0,0)
 # Actual UI path, Record + held step, Clear-left; stock lane bytes snapshot stays untouched.
 u=E.setup(fw,ram)
 u.hook_add(UC_HOOK_MEM_READ,cycle_tick,None,0xe0001004,0xe0001007)
 for a in [0x8029c8c,0x8030eb8,0x8031268,0x80311da,C['SP_WRITE']]:u.hook_add(UC_HOOK_CODE,hook,None,a,a+1)
 memory.update({k:0 for k in memory});ready();tr(0,0);tr(1,0);tr(2,0)
 run('c_aparm');tr(1,0)
 E.led(u,E.rhbuild.bl_target(bytearray(fw),E.C.LED_CALLS[0]))
 # Open Track + on selected Track 1 by the established tap gesture.
 E.tap(u,0)
 E.led(u,E.rhbuild.bl_target(bytearray(fw),E.C.LED_CALLS[0]))
 E.pad(u,E.pp(E.T.PAGE_SP));E.unpad(u,E.pp(E.T.PAGE_SP));tr(1,1)
 E.knob(u,0,3)
 E.check('real UI knob reaches independent fine-value pending state',struct.unpack('<H',u.mem_read(PENDING,2))[0]!=65535 or word(OUTPUT)&65535!=65535)
 E.check('stock automation cells unchanged by extra UI move',bytes(u.mem_read(record+0x2e4+0x128,0x900))==stock[0x2e4+0x128:0x2e4+0xa28])
 # Held step uses the existing selection; extra lock stays 14-bit with remaining slots absent.
 E.pad(u,4);E.knob(u,0,2)
 heldvals=struct.unpack('<6H',u.mem_read(CACHE+4*12,12))
 E.check('Record plus held step records a separate extra lock',heldvals[0]!=65535 and heldvals[1:]==(65535,)*5)
 if rep.get('audit_batch'):
  tr(1,0)
  head=E.rhbuild.bl_target(bytearray(fw),E.C.LED_CALLS[0])
  frame=E.led(u,head)
  assert frame[E.T.LED_KNOB0]==E.T.COL_REC
  saved=bytes(u.mem_read(CACHE+4*12,12));u.mem_write(CACHE+4*12,b'\xff'*12)
  empty=E.led(u,head);u.mem_write(CACHE+4*12,saved)
  E.check('held-step K1 red feedback indicates actual extra lock; empty step does not',empty[E.T.LED_KNOB0]!=E.T.COL_REC)
  # Use stock audition entry and its actual microstep timer callback, with original stock values in parallel.
  so=word(C['TM_STEP_PTR']);bank=record+0x2e4+0x128
  u.mem_write(bank+6*192+4*6,bytes([31,255,255,77,255,255]))
  dest=word(word(word(so+0x50)))&~1;preview_events=[]
  def pv(uc,a,n,d):preview_events.append((uc.reg_read(UC_ARM_REG_R1),uc.reg_read(UC_ARM_REG_R2)));ret()
  hp=u.hook_add(UC_HOOK_CODE,pv,None,dest,dest+1)
  before=bytes(u.mem_read(HELD,4));deliver.clear();E.call(u,0x805ce84,so,0)
  assert deliver[-1]==(((heldvals[0]-8192)*192)&0xffffffff,C['PITCH_AMOUNT_Y'])
  ids=struct.unpack('<12H',u.mem_read(word(so+0x54),24));assert (ids[6],31) in preview_events
  u.mem_write(CACHE+4*12+6,struct.pack('<H',12003));u.mem_write(so+0xb5,b'\x02')
  E.call(u,0x805ce28,3,so)
  assert deliver[-1]==(((12003-8192)*192)&0xffffffff,C['PITCH_AMOUNT_Y']) and (ids[6],77) in preview_events
  assert bytes(u.mem_read(HELD,4))==before
  u.hook_del(hp)
  E.check('stock step-audition entry and microstep callback apply corresponding extra values without resetting player comparison state',True)
  tr(1,1)
 E.unpad(u,4)
 # Regression from hardware: record while stopped, disarm, first start without a stop transition.
 tr(1,0);tr(0,1);deliver.clear();run('c_applay',0x200470d4,0,4,0)
 E.check('held lock entered while stopped applies on FIRST start without a reset callback',bool(deliver) and deliver[-1]==(((heldvals[0]-8192)*192)&0xffffffff,C['PITCH_AMOUNT_Y']))
 tr(0,0);tr(1,1)
 # Real UI Clear-left must clear this lane, never a stock lane.
 w(E.C.CTRL+0xa0,1<<23);E.knob(u,0,-E.T.CLR_N);w(E.C.CTRL+0xa0,0)
 E.check('real Clear-left gesture clears the extra lane',bytes(u.mem_read(CACHE,384))==b'\xff'*384)
 if rep.get('audit_batch'):
  # Record enabled alone must not take or clear this independent lane.
  base=0x20040db4;pos=word(base+0xc)
  tr(0,0);tr(1,0);run('c_aprec_listener',base+8,word(base+0x30),1,0)
  lane([4321]*192);tr(0,1);tr(1,1)
  for i,v in enumerate([0,4,0]):u.mem_write(E.ptr(u,pos,i),struct.pack('<I',v))
  run('c_aprec_listener',base+8,word(base+0x30),1,0)
  E.check('Record without a knob takeover preserves the extra lane',struct.unpack('<192H',u.mem_read(CACHE,384))==(4321,)*192)
 # Queue an actual fine-valued UI move while live recording; run the stock listener.
 tr(0,1);tr(1,1);E.knob(u,0,1)
 expected=struct.unpack('<H',u.mem_read(PENDING,2))[0]
 assert expected!=65535
 base=0x20040db4;pos=word(base+0xc)
 assert pos==word(0x200470d4+8)
 for i,v in enumerate([0,4,0]):u.mem_write(E.ptr(u,pos,i),struct.pack('<I',v))
 # Clear stock recording inputs for this extra-only tick, without changing stock code.
 maskstore=word(base+0x2c);w(E.ptr(u,maskstore,0),0)
 run('c_aprec_listener',base+8,word(base+0x30),1,0)
 E.check('stock clock listener records the actual UI pending value at its microstep',struct.unpack('<H',u.mem_read(CACHE+4*12,2))[0]==expected and memory[0x4000+24]==expected)
 if rep.get('audit_batch'):
  # Once taken, a later empty tick clears an existing point like stock overdub.
  for i,v in enumerate([0,5,0]):u.mem_write(E.ptr(u,pos,i),struct.pack('<I',v))
  u.mem_write(CACHE+5*12,struct.pack('<H',4321))
  run('c_aprec_listener',base+8,word(base+0x30),1,0)
  E.check('taken extra lane clears an older point on an empty recording tick',struct.unpack('<H',u.mem_read(CACHE+5*12,2))[0]==65535)
 # All 12 stock lanes and the extra lane record on the same stock clock event.
 E.knob(u,0,1);expected=struct.unpack('<H',u.mem_read(PENDING,2))[0]
 for i,v in enumerate([0,8,0]):u.mem_write(E.ptr(u,pos,i),struct.pack('<I',v))
 stock_values=bytes(range(31,43));u.mem_write(word(base+0x28),stock_values+b'\xff')
 w(E.ptr(u,maskstore,0),0xfff)
 run('c_aprec_listener',base+8,word(base+0x30),1,0)
 bank=record+0x2e4+0x128
 assert all(u.mem_read(bank+k*192+8*6,1)[0]==stock_values[k] for k in range(12))
 E.check('all 12 stock lanes record alongside the independent extra lane',struct.unpack('<H',u.mem_read(CACHE+8*12,2))[0]==expected)
 tr(0,0);tr(1,0);tr(0,1)  # First playback from stopped recording: no reset callback assumed.
 # Close Track +: playback must remain active and precede stock note output.
 E.tap(u,0);E.led(u,E.rhbuild.bl_target(bytearray(fw),E.C.LED_CALLS[0]))
 deliver.clear();io.clear();stock_events=[]
 player=0x200470d4
 for off,val in [(0x30,0xfff),(0x34,0),(0x38,0)]:w(E.ptr(u,word(player+off),0),val)
 destination=word(word(word(player+0x2c)))&~1
 def stock_sink(uc,a,n,d):stock_events.append((uc.reg_read(UC_ARM_REG_R1),uc.reg_read(UC_ARM_REG_R2)));ret()
 u.hook_add(UC_HOOK_CODE,stock_sink,None,destination,destination+1)
 before_play=bytes(u.mem_read(record,0x29484))
 run('c_applay',player,0,8,0)
 E.check('automation playback leaves saved parameter blocks and checksums untouched',bytes(u.mem_read(record,0x29484))==before_play)
 ids=struct.unpack('<12H',u.mem_read(word(player+0x40),24))
 E.check('actual stock player sends all 12 original destinations during extra playback',all((ident,value) in stock_events for ident,value in zip(ids,stock_values)))
 E.check('closed-page playback sends the extra DSP word from ITCM with no backing reads',bool(deliver) and deliver[-1]==(((expected-8192)*192)&0xffffffff,C['PITCH_AMOUNT_Y']) and not any(t=='r' for t,a in io))
 tr(0,0)
 if rep.get('audit_batch'):
  import rdiag as R
  responses=[];rd={k:int(v,16) for k,v in E.MAN['report']['rdiag']['labels'].items()}
  def output(uc,a,n,d):
   b,length=struct.unpack('<II',uc.mem_read(uc.reg_read(UC_ARM_REG_R2),8));responses.append(bytes(uc.mem_read(b,length)));ret()
  u.hook_add(UC_HOOK_CODE,output,None,R.ROUTER,R.ROUTER+1)
  def request(command,key=0,length=R.PAD):
   responses.clear();msg=0x2004d000;packet=bytearray(R.PAD);packet[:4]=bytes(R.SIG);packet[4]=command;packet[5]=12;packet[-1]=0xf7
   packet[6:14]=bytes((key>>k)&15 for k in range(28,-1,-4))
   u.mem_write(msg,bytes(packet));u.mem_write(msg-16,struct.pack('<II',msg,length))
   E.call(u,rd['c_rdin'],0,msg-16,0)
   if not responses:return None
   b=responses[-1];assert b[:6]==bytes(R.SIG)+bytes([command|64,12]) and b[-1]==247
   return [sum(b[i+j]<<(28-4*j) for j in range(8)) for i in range(6,len(b)-1,8)]
  before=memory.copy();assert request(52,0)==[1] and memory==before
  assert request(52,0x41505431,length=16) is None and memory==before
  E.check('actual SysEx dispatch rejects bad key and short packets without DSP mutation',True)
  # Run real stock observer -> sequencer -> automation -> note callback, not just our helper.
  run('c_aparm');lane([8192]+[65535]*191)
  player=0x200470d4
  for i,v in enumerate([0,0,0]):w(E.ptr(u,word(player+8),i),v)
  w(E.ptr(u,word(player+0x10),1),3)
  w(E.ptr(u,word(player+0x20),0),0);w(E.ptr(u,word(player+0x28),0),0)
  note=word(word(player)+8)&~1
  hn=u.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:journal.append('note') or ret(),None,note,note+1)
  journal.clear();tr(0,0);E.call(u,0x8055120,player,word(player+0x18),1,0)
  assert not journal
  tr(0,1);cycles[0]=0xfffffff0
  E.call(u,0x8055120,player,word(player+0x18),1,0)
  assert 'extra' in journal and 'note' in journal and journal.index('extra')<journal.index('note'),journal
  u.hook_del(hn)
  status=request(53);assert status[1]==0xad000006 and status[2]==1 and status[10]>0,status
  E.check('real stock observer gates stopped playback and delivers extra value before note callback; cycle accounting handles wraparound',True)
  # A genuine stop notification must clear comparison state; do not call our reset helper directly.
  tr(0,0);u.mem_write(HELD,struct.pack('<HH',123,456))
  E.call(u,0x8055120,player,0x200122b0,1,0)
  E.check('real transport stop observer resets extra held/last state',bytes(u.mem_read(HELD,4))==b'\xff'*4)
  # Preserve history when a guard invalidates the runtime, and recheck upload AFTER acquiring mutex.
  run('c_aprecord',3,2,0,12003);recorded=word(0x10c);assert recorded>0
  io.clear();race[0]=True;run('c_aprecord',3,3,0,10001);race[0]=False
  assert not any(t=='w' for t,a in io)
  status=request(53);assert status[2]==0 and status[6]==recorded and status[12]==4,status
  E.check('upload race performs no DSP write and disabled diagnostics retain recording history with guard reason',True)
  ready();assert request(52,0x41505431)==[0]
  run('c_aprecord',3,1,0,8193);recorded=word(0x10c)
  run('c_apload_disable');status=request(53)
  E.check('project-load invalidation retains counters with a distinct reason and disables runtime',status[2]==0 and status[6]==recorded and status[12]==2)
  ready();assert request(52,0x41505431)==[0]
  for cmd in [6,9,51,56,253]:assert request(cmd)==[0xffffffff]
  E.check('unrelated write commands remain disabled',True)
 run('c_apdisable');E.check('disable ends prototype activity',word(C['FLAG_ADDR'])!=0x41505431)
 E.check('disable restores prior trace controls',word(0xe0001000)==0x100 and word(0xe000edfc)==0x20)
 print('ALL PASS' if not E.FAILS else f'{len(E.FAILS)} FAILED')
 if E.FAILS:raise SystemExit(1)
if __name__=='__main__':main()
