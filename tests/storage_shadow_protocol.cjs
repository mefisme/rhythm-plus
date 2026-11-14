const assert=require('node:assert/strict'),fs=require('node:fs');
const P=require('../tools/project_probe_protocol.js');
const man=JSON.parse(fs.readFileSync('firmware/a0178/manifest.json'));
const html=fs.readFileSync('tools/stepmut_storage_probe.html','utf8');
assert(html.includes(`const SLOT = ${man.report.storageshadow.slot};`));
const data=new Uint8Array(1024),view=new DataView(data.buffer);
for(const [i,v] of [[0,0x31534852],[9,3],[16,0x73],[17,0x08010000]])view.setUint32(i*4,v,true);
data.set(Buffer.from('1:/RP_AUTO/12345678.RPS\0'),376);
const result=P.decodeShadow(data);
assert.equal(result.verified,3);assert.equal(result.hardwareReady,true);
assert.equal(result.path,'1:/RP_AUTO/12345678.RPS');
assert.equal(result.settingsSnapshot.length,100);
view.setUint32(19*4,0x10000,true);assert.equal(P.decodeShadow(data).hardwareReady,false);
assert.throws(()=>P.decodeShadow(new Uint8Array(1024)));
const sm=new Uint8Array(100);sm.set([83,77,0x5c,2]);
assert.equal(P.decodeStepMutate(sm).valid,true);
sm[4]=1;assert.equal(P.decodeStepMutate(sm).valid,false);
assert.equal(P.decodeStepMutate(new Uint8Array(100)).valid,false);
new(require('node:vm').Script)([...html.matchAll(/<script>([\s\S]*?)<\/script>/g)][0][1]);
console.log('ALL PASS: A0178 manifest address, status layout, guard decoding and capture JavaScript syntax');
if(fs.existsSync('buildtmp/a0178-mirror-status.bin')) {
  const actual=P.decodeShadow(new Uint8Array(fs.readFileSync('buildtmp/a0178-mirror-status.bin')));
  assert.equal(actual.verified,1);assert.equal(actual.mirrorWrites,1);
  assert.equal(actual.hardwareReady,true);assert.equal(actual.failed,0);
  assert.equal(actual.settingsSnapshot[0],83);assert.equal(actual.settingsSnapshot[1],77);
  console.log('PASS: decoded actual compiled Cortex-M7 status snapshot');
}
