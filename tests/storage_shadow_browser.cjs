/* Execute the actual page handlers with a synthetic Web MIDI device. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const P=require('../tools/project_probe_protocol.js');
const html=fs.readFileSync('tools/stepmut_storage_probe.html','utf8');
const slot=Number(html.match(/const SLOT = (0x[0-9a-f]+);/)[1]);
const bytes=new Uint8Array(fs.readFileSync('buildtmp/a0178-mirror-status.bin'));
const record=0x20012c48,smAddress=record+0x29110+404;
const pointer=new Uint8Array(4);new DataView(pointer.buffer).setUint32(0,record,true);
const sm=bytes.slice(176,276);
const listeners=new Set(),requests=[];
const input={id:'in',name:'Circuit Rhythm',open:async()=>{},close:async()=>{},
  addEventListener:(name,fn)=>listeners.add(fn),removeEventListener:(name,fn)=>listeners.delete(fn)};
const output={id:'out',name:'Circuit Rhythm',open:async()=>{},close:async()=>{},send:msg=>{
  assert.equal(msg[4],2);requests.push(msg);
  const address=[...msg.slice(6,14)].reduce((a,b)=>a*16+b,0),count=msg[14];
  let payload;
  if(address>=slot && address+count<=slot+bytes.length)payload=bytes.slice(address-slot,address-slot+count);
  else if(address===0x2003c0cc && count===4)payload=pointer;
  else if(address>=smAddress && address+count<=smAddress+100)payload=sm.slice(address-smAddress,address-smAddress+count);
  else throw new Error('Unexpected RAM address');
  const result=[240,125,67,84,66,msg[5],...Array(8).fill(0)];
  for(const b of payload)result.push(b>>4,b&15);
  result.push(247);queueMicrotask(()=>{for(const fn of listeners)fn({data:Uint8Array.from(result)});});
}};
const elements={};
for(const id of ['connect','input','output','label','capture','download','status'])
  elements[id]={value:'',options:[],disabled:false,textContent:'',
    add(option){this.options.push(option);if(!this.value)this.value=option.value;},
    replaceChildren(){this.options=[];this.value='';}};
elements.label.value='synthetic-save';
const context=vm.createContext({ProjectProbe:P,Uint8Array,Date,JSON,setTimeout,clearTimeout,
  navigator:{requestMIDIAccess:async()=>({inputs:new Map([['in',input]]),outputs:new Map([['out',output]])})},
  document:{getElementById:id=>elements[id]},Option:function(text,value){this.text=text;this.value=value;}});
new vm.Script([...html.matchAll(/<script>([\s\S]*?)<\/script>/g)][0][1]).runInContext(context);
(async()=>{
  await elements.connect.onclick();assert.equal(elements.capture.disabled,false);
  await elements.capture.onclick();
  const result=JSON.parse(elements.status.textContent);
  assert.equal(result.label,'synthetic-save');assert.equal(result.verified,1);
  assert.equal(result.failed,0);assert.equal(result.hardwareReady,true);
  assert.equal(result.currentProjectSettings.valid,true);
  assert.deepEqual(result.currentProjectSettings.bytes,[...sm]);
  assert.equal(requests.length,21);assert.equal(listeners.size,0);
  assert.equal(elements.download.disabled,false);
  console.log('ALL PASS: real page connects, captures 21 RAM-only reads, validates current native settings and releases MIDI listener');
})().catch(error=>{console.error(error);process.exitCode=1;});
