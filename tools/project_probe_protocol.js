/* Read-only A0177 diagnostic protocol; shared by browser and Node checks. */
const ProjectProbe = (() => {
  function nibbles(value, count = 8) {
    return Array.from({length: count}, (_, i) => (value >>> (4 * (count - i - 1))) & 15);
  }
  function number(bytes) {
    let value = 0;
    for (const b of bytes) {
      if (b > 15) throw new Error('Invalid nibble');
      value = (value * 16 + b) >>> 0;
    }
    return value;
  }
  function request(address, length, sequence) {
    if (length < 1 || length > 64 || address < 0x20000000 || address + length > 0x20050000)
      throw new Error('Read outside diagnostic RAM range');
    const msg = new Uint8Array(232);
    msg.set([0xf0, 0x7d, 0x43, 0x54, 2, sequence, ...nibbles(address), length]);
    msg[231] = 0xf7;
    return msg;
  }
  function reply(data, sequence, length) {
    if (data[0] !== 0xf0 || data[1] !== 0x7d || data[2] !== 0x43 || data[3] !== 0x54 ||
        data[4] !== 0x42 || data[5] !== sequence) return null;
    if (number(data.slice(6, 14))) throw new Error('Device refused RAM read');
    if (data.length !== 15 + length * 2 || data[data.length - 1] !== 0xf7)
      throw new Error('Incomplete diagnostic reply');
    return Uint8Array.from({length}, (_, i) => number(data.slice(14 + i * 2, 16 + i * 2)));
  }
  function decode(bytes) {
    if (bytes.length !== 1056) throw new Error('Wrong log size');
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const word = offset => view.getUint32(offset, true);
    if (word(0) !== 0x31505052) throw new Error('No A0177 project log. Confirm the installed build and load a project.');
    const total = word(4);
    const names = ['', 'read_begin', 'read_end', 'apply_begin', 'apply_end', 'save_submit', 'save_return', 'save_callback'];
    const events = [];
    for (let i = 0; i < 32; i++) {
      const fields = Array.from({length: 8}, (_, j) => word(32 + i * 32 + j * 4));
      const [sequence, ms, kind, ...args] = fields;
      if (sequence && sequence <= total && sequence > Math.max(0, total - 32))
        events.push({sequence, ms, kind, event: names[kind] || 'unknown', args});
    }
    events.sort((a, b) => a.sequence - b.sequence);
    const reads = [];
    let start;
    for (const event of events) {
      if (event.kind === 1) start = event;
      if (event.kind === 2 && start && event.args[0] === start.args[0] && event.args[1] === start.args[1]) {
        // Native descriptor field 3 is a byte; its upper stack bytes can be
        // uninitialized. Raw words stay in events for forensic inspection.
        reads.push({slot: event.args[0], packContext: event.args[1] & 255, bytes: start.args[3],
                    elapsedMs: (event.ms - start.ms) >>> 0, result: event.args[2]});
        start = undefined;
      }
    }
    return {build: 'A0177', total, counts: {reads: word(8), applies: word(12), saves: word(16), callbacks: word(20)}, events, reads};
  }
  function decodeShadow(bytes, magic = 0x31534852, build = 'A0178') {
    if (bytes.length !== 1024) throw new Error('Wrong A0178 status size');
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const w = i => view.getUint32(i * 4, true);
    if (w(0) !== magic) throw new Error(`No ${build} storage status. Confirm the build and load a project.`);
    const names = ['magic','active','pending','mode','stage','nativeSaves','nativeLoads',
      'mirrorWrites','mirrorReads','verified','missing','failed','skipped','lastError',
      'elapsedMs','startMs','itcmcr','vtor','mpu','ccr','guardFailures','projectSlot',
      'packContext','fileOperations','queueBusy','waitActive','waitStartMs','longWaits',
      'maxWaitMs','yields'];
    const result = {build};
    names.forEach((name, i) => result[name] = w(i));
    result.hardwareReady = w(16) === 0x73 && w(17) >= 0x08010000 && w(17) < 0x08080000 &&
      !(w(18) & 1) && !(w(19) & 0x10000);
    result.path = String.fromCharCode(...bytes.slice(376,408)).split('\0')[0];
    result.settingsSnapshot = [...bytes.slice(176,276)];
    return result;
  }
  function decodeStepMutate(bytes) {
    if (bytes.length !== 100) throw new Error('Wrong Step Mutate block size');
    const checksum = (bytes.slice(4).reduce((sum,b) => sum + b, 0) ^ 0x5c) & 255;
    return {valid: bytes[0] === 83 && bytes[1] === 77 && bytes[3] === 2 && bytes[2] === checksum,
      version: bytes[3], checksum: bytes[2], expectedChecksum: checksum, bytes:[...bytes]};
  }
  function crc32(bytes) {
    let crc = 0xffffffff;
    for (const b of bytes) {crc ^= b; for (let i=0;i<8;i++) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));}
    return (~crc) >>> 0;
  }
  function decodeOffloadMetadata(bytes) {
    if (bytes.length !== 20) throw new Error('Wrong offload metadata size');
    const view = new DataView(bytes.buffer,bytes.byteOffset,20);
    const claimed = bytes[0] === 83 && bytes[1] === 79;
    const file = bytes[3] === 1, key=view.getUint32(4,true), size=view.getUint32(8,true);
    const valid = claimed && bytes[2] === 1 && bytes[3] <= 1 && view.getUint32(12,true) === 0 &&
      view.getUint32(16,true) === crc32(bytes.slice(0,16)) &&
      (file ? size === 100 : key === 0 && size === 0);
    return {claimed,valid,version:bytes[2],file,key,size,
      path: valid && file ? `1:/RP_AUTO/${key.toString(16).toUpperCase().padStart(8,'0')}.RPS` : null};
  }
  function decodeOffload(bytes) {
    const result=decodeShadow(bytes,0x31464f53,'A0179');
    result.runtimeState=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength).getUint32(124,true);
    result.liveSettings=decodeStepMutate(Uint8Array.from(result.settingsSnapshot));
    return result;
  }
  function isDefaultStepMutate(bytes) {
    const defaults=[0x2e,0x0a,0,0x2a,0x2a,0x1e,2,2,7,0x0a,4,0];
    return decodeStepMutate(Uint8Array.from(bytes)).valid && bytes.slice(4).every((b,i)=>b===defaults[i%12]);
  }
  return {request, reply, decode, decodeShadow, decodeStepMutate, crc32, decodeOffloadMetadata, decodeOffload,isDefaultStepMutate};
})();
if (typeof module !== 'undefined') module.exports = ProjectProbe;
