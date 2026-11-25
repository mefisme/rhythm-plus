/* The Circuit Rhythm's SD card, read and written from the browser (File System Access API). No DOM: tests/app_core_test.mjs runs it on a fake card.
   File system helpers, backups and the name rules adapted from Circuit Remix (remix/tools/rm_app.html), Copyright (c) 2026 Ghillermo, MIT License.

   The card: Rhythm/NN_Pack (NN 00..30 = packs 1..31) with Sessions, PCM, meta; RP_AUTO/ and RP_INTERNAL/ (the internal pack's
   Plus files) at the top.
   A project: Sessions/NN_Name.ncs, 169 092 B. Its Rhythm Plus metadata at 0x29224: "SO", version, a flag (0 = no Plus file),
   the key (the Plus file's CRC-32) and the Plus file's size.
   Its Plus file: Sessions/RP_NN_[Name_]KEY.rps next to it, or RP_AUTO/KEY.RPS. The unit finds it by the key: the exact name, then
   RP_AUTO, then any RP_ file of the pack with that key.
   The stock firmware takes a file by its NN_ prefix alone, so nothing that starts with digits is ever left in a pack folder.
   Over USB the card is the unit's own file protocol behind the same folder calls (Device, DevRoot below, from Circuit Remix): it reaches
   projects, samples and packs, not the Plus files. */
const RP = (() => {
"use strict";
const NSESS = 64, NPACKS = 31, NSAMPLES = 128, SESS_SIZE = 0x29484, META = 0x29110 + 276, PATH_MAX = 104, PROJ_NAME = 24, FOLDER_MAX = 30;
const SAMPLE_FILE = 26, SAMPLE_MAX = 0x2F0000;              // NN_Name before .wav; the stock reads no more of a sample's data than SAMPLE_MAX
const PAGES = 2695, PAGE_WORDS = 4096;                      // a pack's sample memory on the unit: 2,695 pages of 4,096 16-bit words (~230 s mono at 48 kHz)
const samplePages = size => Math.ceil(Math.min(Math.max(0, size - 44), SAMPLE_MAX) / 2 / PAGE_WORDS);   // size = the WAV file's bytes
const SLOT_AT = 0x28CEC, PAT0 = 0x2E4, PAT = 0xA28, NSTEPS = 32, STEP = 8;    // a project's sample per track; each step's sample flip at +5
const AUTO = "RP_AUTO", INTERNAL = "RP_INTERNAL", BACKUP_FILE = "rhythm-plus-backup.json", TMP = "~rp-rename.tmp";
const pad2 = n => String(n).padStart(2, "0");
const hex8 = k => (k >>> 0).toString(16).toUpperCase().padStart(8, "0");
const lower = s => s.toLowerCase();

const CRCT = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
function crc32(d) { let c = 0xFFFFFFFF; for (let i = 0; i < d.length; i++) c = CRCT[(c ^ d[i]) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }
const u32 = (b, o) => (b[o] | b[o + 1] << 8 | b[o + 2] << 16 | b[o + 3] << 24) >>> 0;
const sameBytes = (a, b) => a.length === b.length && a.every((v, i) => v === b[i]);
function stamp(d = new Date()) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}_${pad2(d.getHours())}${pad2(d.getMinutes())}${pad2(d.getSeconds())}`;
}

// ---------------------------------------------------------------- the file system
async function entries(dir) {
  const out = [];
  for await (const [name, h] of dir.entries()) out.push([name, h]);
  return out.sort((a, b) => a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0);
}
async function subdir(dir, name, create = false) {
  try { return await dir.getDirectoryHandle(name, {create}); }
  catch (e) { if (e.name === "NotFoundError" || e.name === "TypeMismatchError") return null; throw e; }
}
async function fileIn(dir, name) {
  try { return await dir.getFileHandle(name); }
  catch (e) { if (e.name === "NotFoundError" || e.name === "TypeMismatchError") return null; throw e; }
}
// Cancel: every file read or write checks it first, so a long job stops between files, never inside one.
const halt = {asked: false};
const stop = () => { halt.asked = true; }, go = () => { halt.asked = false; };
const checkHalt = () => { if (halt.asked) throw new Error("cancelled"); };
const readHandle = async h => { checkHalt(); return new Uint8Array(await (await h.getFile()).arrayBuffer()); };
async function writeFile(dir, name, bytes) {
  checkHalt();
  const w = await (await dir.getFileHandle(name, {create: true})).createWritable();
  try { await w.write(bytes); await w.close(); }
  catch (e) { try { await w.abort(); } catch (_) { /* the write's own error is the one to report */ } throw e; }
}
async function writeChecked(dir, name, bytes) {             // written, then read back; the unit checks its own writes against a CRC
  await writeFile(dir, name, bytes);
  if (dir.device) return;
  if (!sameBytes(await readHandle(await dir.getFileHandle(name)), bytes)) throw new Error("verify");
}
async function dirPath(root, parts, create) { let d = root; for (const p of parts) { d = await subdir(d, p, create); if (!d) return null; } return d; }
async function copyTree(src, dst, tick) {
  for (const [n, h] of await entries(src)) {
    if (/\.crswap$/i.test(n)) continue;                     // the browser's temporary file
    if (h.kind === "directory") await copyTree(h, await dst.getDirectoryHandle(n, {create: true}), tick);
    else { const b = await readHandle(h); await writeFile(dst, n, b); if (tick) tick(n, b.length); }
  }
}
async function sameTree(a, b) {                             // every file of a is in b with its size
  for (const [n, h] of await entries(a)) {
    if (/\.crswap$/i.test(n)) continue;
    if (h.kind === "directory") { const d = await subdir(b, n); if (!d || !await sameTree(h, d)) return false; continue; }
    const g = await fileIn(b, n);
    if (!g || (await g.getFile()).size !== (await h.getFile()).size) return false;
  }
  return true;
}
async function treeInfo(dir) {
  let files = 0, bytes = 0;
  for (const [, h] of await entries(dir)) {
    if (h.kind === "directory") { const t = await treeInfo(h); files += t.files; bytes += t.bytes; }
    else { files++; bytes += (await h.getFile()).size; }
  }
  return {files, bytes};
}
// A file renamed in its folder: the browser's own move when it has one, else a checked copy under a temporary name.
async function renameIn(dir, from, to) {
  if (from === to) return;
  if (dir.renameEntry) return dir.renameEntry(from, to);
  const h = await dir.getFileHandle(from);
  if (typeof h.move === "function") {
    try { await h.move(to); return; }
    catch (e) { if (!["NotSupportedError", "TypeError", "InvalidModificationError"].includes(e.name)) throw e; }
  }
  const bytes = await readHandle(h);
  await writeChecked(dir, TMP, bytes);
  await dir.removeEntry(from);
  await writeChecked(dir, to, bytes);
  await dir.removeEntry(TMP);
}

// ---------------------------------------------------------------- names
// The unit's own Plus file name: RP_<slot>_[<project name>_]<KEY>.rps, the name cut to fit its 104-character path.
function plusName(pack, slot, name, key) {
  const room = Math.max(0, PATH_MAX - 20 - ("1:/Rhythm/" + pack.folder + "/Sessions/").length);
  const part = name.slice(0, room);
  return "RP_" + pad2(slot) + "_" + (part ? part + "_" : "") + hex8(key) + ".rps";
}
function plusParse(n) {                                     // -> {slot, key} or null, as the unit reads a name
  const L = n.length;
  if (L < 18 || L >= 128 || !/^RP_\d\d_/.test(n) || !n.endsWith(".rps") || (L > 18 && (L < 20 || n[L - 13] !== "_"))) return null;
  const k = n.slice(L - 12, L - 4);
  return /^[0-9A-F]{8}$/.test(k) ? {slot: +n.slice(3, 5), key: parseInt(k, 16) >>> 0} : null;
}
const autoParse = n => { const m = /^([0-9A-Fa-f]{8})\.RPS$/i.exec(n); return m ? parseInt(m[1], 16) >>> 0 : null; };
const prefix = slot => slot >= 100 ? String(slot) : pad2(slot);
const NAME_RULE = {project: [PROJ_NAME, ".ncs"], sample: [SAMPLE_FILE, ".wav"], pack: [FOLDER_MAX, ""]};
const nameMax = (slot, kind = "project") => kind === "project" ? PROJ_NAME : NAME_RULE[kind][0] - prefix(slot).length - 1;
function nameProblem(name, slot, others, kind = "project") {    // -> null, or the reason (rename-*); others: the folder's other names
  if (!name) return "rename-empty";
  if (name !== name.trim() || name.endsWith(".")) return "rename-edge";
  if (!/^[ -~]+$/.test(name)) return "rename-ascii";
  if (/[\\/:*?"<>|]/.test(name)) return "rename-char";
  if (name.length > nameMax(slot, kind)) return "rename-long";
  if (others.some(o => lower(o) === lower(prefix(slot) + "_" + name + NAME_RULE[kind][1]))) return "rename-taken";
  return null;
}
const projectPart = file => file.replace(/\.ncs$/i, "").slice(file.indexOf("_") + 1);

// ---------------------------------------------------------------- the card
class Pack {
  constructor(card, slot, name, folder, dir) { this.card = card; this.slot = slot; this.name = name; this.folder = folder; this.dir = dir; this._list = null; this._samples = null; }
  drop() { this._list = null; this._samples = null; }
}
// root: the card's top folder, or null when only the Rhythm folder was given (the browser may not offer a drive's top folder).
// Then RP_AUTO is the folder given with useAuto.
class Card {
  constructor(root, rhythm) { this.root = root; this.rhythm = rhythm; this.device = !!rhythm.device; this.autoDir = null; this.intDir = null; this.packs = []; this._auto = null; }
  static async open(dir) {
    const rhythm = await subdir(dir, "Rhythm");
    if (rhythm) { const c = new Card(dir, rhythm); c.autoDir = await subdir(dir, AUTO); c.intDir = await subdir(dir, INTERNAL); await c.scan(); return c; }
    const packLike = (await entries(dir)).some(([n, h]) => h.kind === "directory" && /^\d\d_/.test(n));
    if (!packLike) throw new Error("no-rhythm");
    const c = new Card(null, dir);
    if (dir.device && dir.auto) c.autoDir = dir.auto;
    await c.scan();
    return c;
  }
  useAuto(dir) { if (lower(dir.name) !== lower(AUTO)) throw new Error("no-auto"); this.autoDir = dir; this.drop(); }
  get top() { return this.root || this.rhythm; }
  async scan() {
    const out = [];
    for (const [n, h] of await entries(this.rhythm)) {
      const m = /^(\d\d)_(.*)$/.exec(n);
      if (!m || h.kind !== "directory" || +m[1] >= NPACKS || out.some(p => p.slot === +m[1])) continue;
      out.push(new Pack(this, +m[1], m[2], n, h));
    }
    this.packs = out; this._auto = null;
  }
  pack(slot) { return this.packs.find(p => p.slot === slot) || null; }
  drop() { this._auto = null; for (const p of this.packs) p.drop(); }
  async auto() {                                            // RP_AUTO: key -> {name, handle}
    if (this._auto) return this._auto;
    const m = new Map(), d = this.autoDir;
    if (d) for (const [n, h] of await entries(d)) { const k = autoParse(n); if (k !== null && h.kind === "file" && !m.has(k)) m.set(k, {name: n, handle: h}); }
    return this._auto = m;
  }
}

// A pack's projects with the state of their Plus file:
//   stock: needs none; here: next to it, as the unit names it; renamed: next to it under another name (it still loads);
//   auto: only in RP_AUTO (it loads); missing: nowhere (the unit flashes Save red); bad: found, but not the file the project wants.
async function projects(pack) {
  if (pack._list) return pack._list;
  const d = await subdir(pack.dir, "Sessions"), list = [], plus = [];
  if (d) for (const [n, h] of await entries(d)) {
    if (h.kind !== "file") continue;
    const r = /^(\d\d)_(.*)\.ncs$/i.exec(n), q = plusParse(n);
    if (q) plus.push({name: n, handle: h, ...q});
    if (!r || +r[1] >= NSESS || list.some(p => p.slot === +r[1])) continue;
    if (h.device && !h.folder.dev.metaOk) { list.push({slot: +r[1], file: n, name: projectPart(n), key: null, plusSize: 0, usb: true, plus: []}); continue; }
    if (h.device) {                                         // over USB the unit reads the project's Plus bytes itself
      const x = await h.folder.dev.plusMeta(h.folder.P, +r[1]).catch(() => undefined);
      if (x === null) continue;
      if (!x) { list.push({slot: +r[1], file: n, name: projectPart(n), key: null, plusSize: 0, usb: true, plus: []}); continue; }
      const m = x.m, claimed = x.size === SESS_SIZE && m[0] === 0x53 && m[1] === 0x4F && m[3] !== 0;
      list.push({slot: +r[1], file: n, name: projectPart(n), size: x.size, colour: x.colour == null ? null : colourOf(x.colour), inner: x.head ? innerName(x.head) : undefined,
                 key: claimed ? u32(m, 4) : null, plusSize: claimed ? u32(m, 8) : 0});
      continue;
    }
    const f = await h.getFile(), m = new Uint8Array(await f.slice(META, META + 20).arrayBuffer());
    const head = new Uint8Array(await f.slice(0, PROJ_HEAD).arrayBuffer());
    const claimed = f.size === SESS_SIZE && m[0] === 0x53 && m[1] === 0x4F && m[3] !== 0;
    list.push({slot: +r[1], file: n, name: projectPart(n), size: f.size, colour: colourOf(head[PROJ_COLOUR]), inner: innerName(head), key: claimed ? u32(m, 4) : null, plusSize: claimed ? u32(m, 8) : 0});
  }
  const auto = await pack.card.auto();
  for (const p of list) {
    if (p.usb) { p.plus = plus.filter(x => x.slot === p.slot); p.state = p.plus.length ? "usbplus" : "usb"; continue; }
    p.plus = plus.filter(x => p.key !== null && x.key === p.key && x.slot === p.slot);
    if (p.key === null) { p.state = "stock"; continue; }
    const want = plusName(pack, p.slot, p.name, p.key), exact = p.plus.find(x => x.name === want);
    const any = exact || p.plus[0] || plus.find(x => x.key === p.key), a = auto.get(p.key);
    const src = any || a;
    p.want = want; p.source = src ? {name: src.name, handle: src.handle, where: any ? "pack" : "auto"} : null;
    if (!src) { p.state = "missing"; continue; }
    const b = await readHandle(src.handle);
    p.state = crc32(b) !== p.key || b.length !== p.plusSize ? "bad" : exact ? "here" : any ? "renamed" : "auto";
  }
  pack._plus = plus;
  return pack._list = list;
}
async function samples(pack) {                              // PCM/NN_Name.wav (from 100 on, three digits): [{slot, name, file, size}]
  if (pack._samples) return pack._samples;
  const d = await subdir(pack.dir, "PCM"), out = [];
  if (d) for (const [n, h] of await entries(d)) {
    const r = /^(\d{2,3})_(.+)\.wav$/i.exec(n);
    if (r && h.kind === "file" && +r[1] < NSAMPLES && !out.some(x => x.slot === +r[1]))
      out.push({slot: +r[1], name: r[2], file: n, handle: h, size: (await h.getFile()).size});
  }
  return pack._samples = out.sort((a, b) => a.slot - b.slot);
}
async function project(pack, slot) { return (await projects(pack)).find(p => p.slot === slot) || null; }
async function plusBytes(p) { return p.source && p.state !== "bad" ? readHandle(p.source.handle) : null; }

// ---------------------------------------------------------------- project operations: the Plus file always goes with its project
const NAME_AT = 16, NAME_LEN = 32, PROJ_HEAD = 48;          // the project's name inside its file, padded with spaces
const innerName = h => isBlank(h) ? null : String.fromCharCode(...h.subarray(NAME_AT, NAME_AT + NAME_LEN)).replace(/[\s\0]+$/, "");   // null: a blank project
function withName(b, name) {
  const o = b.slice();
  o.fill(0x20, NAME_AT, NAME_AT + NAME_LEN);
  for (let i = 0; i < Math.min(name.length, NAME_LEN); i++) { const c = name.charCodeAt(i); o[NAME_AT + i] = c < 32 || c > 126 ? 0x5F : c; }
  return o;
}
async function renameProject(pack, slot, name) {
  const p = await project(pack, slot), list = await projects(pack);
  if (!p) throw new Error("gone");
  const bad = nameProblem(name, slot, list.filter(x => x !== p).map(x => x.file));
  if (bad) throw new Error(bad);
  const d = await subdir(pack.dir, "Sessions"), file = pad2(slot) + "_" + name + ".ncs";
  const b = await readHandle(await d.getFileHandle(p.file));
  if (!projectProblem(b)) await writeChecked(d, p.file, withName(b, name));
  await renameIn(d, p.file, file);
  if (p.usb && p.plus.length) await renameIn(d, p.plus[0].name, plusName(pack, slot, name, p.plus[0].key));
  if (p.key !== null) {
    const want = plusName(pack, slot, name, p.key);
    if (p.plus.length) await renameIn(d, p.plus[0].name, want);
    else if (p.source) await writeChecked(d, want, await readHandle(p.source.handle));
    for (const x of p.plus.slice(1)) await d.removeEntry(x.name);
  }
  pack.drop();
}
// Copy (or move) a project to a slot of a pack. A project already in that slot is deleted only with replace.
async function copyProject(src, slot, dst, to, {move = false, replace = false} = {}) {
  const p = await project(src, slot);
  if (!p) throw new Error("gone");
  if (move && src === dst && slot === to) return;
  const old = await project(dst, to);
  if (old && !replace) throw new Error("slot-used");
  const bytes = await readHandle(await (await subdir(src.dir, "Sessions")).getFileHandle(p.file)), plus = await plusBytes(p);
  if (p.key !== null && !plus) throw new Error(p.state === "bad" ? "plus-bad" : "plus-missing");
  const d = await subdir(dst.dir, "Sessions", true), file = pad2(to) + "_" + p.name + ".ncs";
  if (old) await deleteFiles(dst, old, d);
  await writeChecked(d, file, bytes);
  if (plus) await writeChecked(d, plusName(dst, to, p.name, p.key), plus);
  if (move) {
    const s = await subdir(src.dir, "Sessions");
    await s.removeEntry(p.file);
    for (const x of p.plus) await s.removeEntry(x.name);
  }
  src.drop(); dst.drop();
}
async function deleteFiles(pack, p, d) {
  await d.removeEntry(p.file);
  for (const x of p.plus) await d.removeEntry(x.name);
}
async function deleteProject(pack, slot) {
  const p = await project(pack, slot);
  if (!p) return;
  await deleteFiles(pack, p, await subdir(pack.dir, "Sessions"));
  pack.drop();
}

// ---------------------------------------------------------------- slots: copy, move, swap, delete and rename of projects and samples
// A placement writes items read beforehand, so sources and targets may overlap (a reorder). An item already in a target slot is deleted.
// A project takes its Plus file along, under the unit's name for its new slot.
const KIND = {projects: {folder: "Sessions", size: NSESS, list: projects}, samples: {folder: "PCM", size: NSAMPLES, list: samples}};
const fileFor = (kind, slot, name) => prefix(slot) + "_" + name + (kind === "projects" ? ".ncs" : ".wav");
async function itemAt(kind, pack, slot) { return (await KIND[kind].list(pack)).find(x => x.slot === slot) || null; }
async function readItem(kind, pack, slot) {                 // -> {name, bytes, key, plus} or null
  const x = await itemAt(kind, pack, slot);
  if (!x) return null;
  const bytes = await readHandle(await (await subdir(pack.dir, KIND[kind].folder)).getFileHandle(x.file));
  if (x.usb) return {name: x.name, ...await usbPlus(pack, bytes, x.name)};
  if (kind === "samples" || x.key === null) return {name: x.name, bytes, key: null, plus: null};
  const plus = await plusBytes(x);
  if (!plus) throw Object.assign(new Error(x.state === "bad" ? "plus-bad" : "plus-missing"), {item: x.name});
  return {name: x.name, bytes, key: x.key, plus};
}
// A project read over USB: its Plus file by the key in its bytes, in its pack, then in RP_AUTO. Without the unit's Plus commands: none.
async function usbPlus(pack, bytes, item) {
  const key = projectKey(bytes);
  if (key === null || !pack.card.rhythm.dev.plusOk) return {bytes, key: null, plus: null};
  await projects(pack);
  const all = pack._plus.filter(x => x.key === key), auto = (await pack.card.auto()).get(key);
  const src = all[0] || auto;
  if (!src) throw Object.assign(new Error("plus-missing"), {item});
  const plus = await readHandle(src.handle);
  if (crc32(plus) !== key) throw Object.assign(new Error("plus-bad"), {item});
  return {bytes, key, plus};
}
async function removeAt(kind, pack, slot) {                 // a slot's file(s)
  const x = await itemAt(kind, pack, slot);
  if (!x) return;
  const d = await subdir(pack.dir, KIND[kind].folder);
  for (const n of [...(x.plus || []).map(y => y.name), x.file]) await d.removeEntry(n);
  pack.drop();
}
async function writeAt(kind, pack, slot, item) {
  const d = await subdir(pack.dir, KIND[kind].folder, true);
  await writeChecked(d, fileFor(kind, slot, item.name), item.bytes);
  if (item.plus) await writeChecked(d, plusName(pack, slot, item.name, item.key), item.plus);
  pack.drop();
}
// moves: [{from: {pack, slot} | null, item?, to: {pack, slot}}]; a move with from has its source emptied unless it is also a target.
async function place(kind, moves, {keepSources = false} = {}, tick) {
  const id = (pk, n) => pk.slot + ":" + n;
  for (const m of moves) if (m.from && !m.item) m.item = await readItem(kind, m.from.pack, m.from.slot);
  const targets = new Set(moves.map(m => id(m.to.pack, m.to.slot)));
  let n = 0;
  for (const m of moves) {
    const t = m.to;
    await removeAt(kind, t.pack, t.slot);
    if (m.item) await writeAt(kind, t.pack, t.slot, m.item);
    if (tick) tick(++n, moves.length);
  }
  if (!keepSources) for (const m of moves) if (m.from && !targets.has(id(m.from.pack, m.from.slot))) await removeAt(kind, m.from.pack, m.from.slot);
}
// Copy, move or swap the items of src's slots `from` to dst's slots `to` (as many). Samples moved or swapped inside one pack keep playing in
// every project of that pack: the projects follow the new numbers.
async function transfer(kind, src, from, dst, to, {move = false, swap = false} = {}, tick) {
  if (from.length !== to.length || to.some(n => n < 0 || n >= KIND[kind].size)) throw new Error("order-range");
  const moves = from.map((f, i) => ({from: {pack: src, slot: f}, to: {pack: dst, slot: to[i]}}));
  if (swap) for (let i = 0; i < from.length; i++) if (!from.includes(to[i]) || src !== dst) moves.push({from: {pack: dst, slot: to[i]}, to: {pack: src, slot: from[i]}});
  const items = await Promise.all(moves.map(m => readItem(kind, m.from.pack, m.from.slot)));
  moves.forEach((m, i) => { m.item = items[i]; });
  const live = moves.filter(m => m.item || swap);
  await place(kind, live, {keepSources: !move && !swap}, tick);
  if (kind === "samples" && src === dst && (move || swap)) {
    const map = new Map();
    from.forEach((f, i) => map.set(f, to[i]));
    if (swap) to.forEach((t, i) => { if (!map.has(t)) map.set(t, from[i]); });
    else {                                                  // what pointed at a replaced sample points at a freed slot: silence, as before
      const freed = from.filter(f => !to.includes(f)), hit = to.filter(t => !from.includes(t));
      hit.forEach((t, i) => map.set(t, freed[i]));
    }
    return remapPack(src, map);
  }
  return [];
}
async function deleteItems(kind, pack, slots) { for (const n of slots) await removeAt(kind, pack, n); }
async function renameItem(kind, pack, slot, name) {
  const x = await itemAt(kind, pack, slot), list = await KIND[kind].list(pack);
  if (!x) throw new Error("gone");
  if (kind === "projects") return renameProject(pack, slot, name);
  const bad = nameProblem(name, slot, list.filter(y => y !== x).map(y => y.file), "sample");
  if (bad) throw new Error(bad);
  await renameIn(await subdir(pack.dir, "PCM"), x.file, fileFor(kind, slot, name));
  pack.drop();
}
// The sample numbers a project uses: each track's sample and each step's sample flip. -> how many references changed
function remapSession(b, map) {
  let n = 0;
  const f = at => { if (map.has(b[at])) { b[at] = map.get(b[at]); n++; } };
  for (let t = 0; t < 8; t++) {
    if (b[SLOT_AT + t] < NSAMPLES) f(SLOT_AT + t);
    for (let p = 0; p < 8; p++) for (let s = 0; s < NSTEPS; s++) { const o = PAT0 + PAT * (8 * t + p) + s * STEP + 5; if (b[o] < NSAMPLES) f(o); }
  }
  return n;
}
async function remapPack(pack, map) {                       // -> the project slots rewritten
  const d = await subdir(pack.dir, "Sessions"), out = [];
  if (!d) return out;
  for (const x of await projects(pack)) {
    const b = await readHandle(await d.getFileHandle(x.file));
    if (b.length !== SESS_SIZE) continue;
    if (!remapSession(b, map)) continue;
    await writeChecked(d, x.file, b);
    out.push(x.slot);
  }
  pack.drop();
  return out;
}
// A pack's folder takes a new name; its number stays. Without a folder move in the browser: a checked copy under a temporary name.
async function renamePack(pack, name) {
  const card = pack.card, bad = nameProblem(name, pack.slot, card.packs.filter(x => x !== pack).map(x => x.folder), "pack");
  if (bad) throw new Error(bad);
  const to = pad2(pack.slot) + "_" + name;
  if (to === pack.folder) return pack;
  const top = card.rhythm;
  if (top.renameEntry) await top.renameEntry(pack.folder, to);
  else if (!(typeof pack.dir.move === "function" && await pack.dir.move(to).then(() => true, () => false))) {
    if (await subdir(top, TMP)) throw new Error("rename-left");
    const tmp = await top.getDirectoryHandle(TMP, {create: true});
    try { await copyTree(pack.dir, tmp); if (!await sameTree(pack.dir, tmp)) throw new Error("verify"); }
    catch (e) { await top.removeEntry(TMP, {recursive: true}); throw e; }
    await top.removeEntry(pack.folder, {recursive: true});
    const dst = await top.getDirectoryHandle(to, {create: true});
    await copyTree(tmp, dst);
    if (!await sameTree(tmp, dst)) throw new Error("rename-half");
    await top.removeEntry(TMP, {recursive: true});
  }
  await card.scan();
  return card.pack(pack.slot);
}

// ---------------------------------------------------------------- files from the computer
function wavInfo(b) {                                       // -> {format, channels, rate, bits, at, data} or null
  const tag = (o, n) => String.fromCharCode(...b.subarray(o, o + n));
  if (b.length < 12 || tag(0, 4) !== "RIFF" || tag(8, 4) !== "WAVE") return null;
  const v = new DataView(b.buffer, b.byteOffset, b.byteLength), out = {};
  for (let o = 12; o + 8 <= b.length;) {
    const id = tag(o, 4), n = v.getUint32(o + 4, true);
    if (id === "fmt ") { out.format = v.getUint16(o + 8, true); out.channels = v.getUint16(o + 10, true); out.rate = v.getUint32(o + 12, true); out.bits = v.getUint16(o + 22, true); }
    else if (id === "data") { out.at = o + 8; out.data = Math.min(n, b.length - o - 8); break; }
    o += 8 + n + (n & 1);
  }
  return out;
}
// The unit's own sample format: 48 kHz, mono, 16-bit PCM, a 44-byte header.
const unitWav = i => !!i && i.format === 1 && i.channels === 1 && i.rate === 48000 && i.bits === 16 && i.at !== undefined;
function wavEncode(f32) {                                   // mono 48 kHz floats -> the unit's WAV
  const n = f32.length, b = new Uint8Array(44 + 2 * n), v = new DataView(b.buffer);
  const put = (o, s) => { for (let i = 0; i < s.length; i++) b[o + i] = s.charCodeAt(i); };
  put(0, "RIFF"); v.setUint32(4, 36 + 2 * n, true); put(8, "WAVE"); put(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, 48000, true); v.setUint32(28, 96000, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); put(36, "data"); v.setUint32(40, 2 * n, true);
  for (let i = 0; i < n; i++) v.setInt16(44 + 2 * i, Math.max(-32768, Math.min(32767, Math.round(f32[i] * 32767))), true);
  return b;
}
function projectProblem(b) {                                // -> null, or why these bytes are not a project (proj-*)
  if (b.length !== SESS_SIZE) return "proj-size";
  const h = String.fromCharCode(...b.subarray(0, 4));
  return h === "RUSE" || h === "RDEM" || h === "INIT" ? null : "proj-head";       // INIT: a blank project, as Components packs hold
}
// ---------------------------------------------------------------- colours of packs and projects: the stock's 14 (its table at 0x08069060)
const COLOURS = ["#fa0005", "#fc2d5d", "#fc7035", "#fd4000", "#ff982b", "#ffff00", "#e9e838", "#90ef1a", "#18ff00", "#7cff43", "#3cd6fe", "#1000ff", "#6f00fe", "#b718b9"];
// on screen: the same 14 as Components draws them (the LED values above look darker on a screen)
const COLOURS_SHOWN = ["#ff3d3d", "#ff3374", "#ff7f73", "#ffa033", "#ffc47d", "#fff033", "#e3ff80", "#a8ec1c", "#3dff3d", "#4ef58f", "#38aaff", "#3d5cff", "#7b38ff", "#ff52d1"];
const PROJ_COLOUR = 12, META_FILE = "00_META.ncm";           // a project's colour byte; a pack's is byte 0 of meta/00_META.ncm (byte 1: its last project)
const colourOf = v => v < COLOURS.length ? v : null;
async function packColour(pack) {                           // -> 0-13, or null with no meta file
  const d = await subdir(pack.dir, "meta"), h = d && await fileIn(d, META_FILE);
  const b = h ? await readHandle(h) : null;
  return b && b.length ? colourOf(b[0]) : null;
}
async function setPackColour(pack, c) {
  if (colourOf(c) === null) throw new Error("colour");
  const d = await subdir(pack.dir, "meta", true), h = await fileIn(d, META_FILE), b = h ? await readHandle(h) : null;
  const out = b && b.length >= 2 ? b.slice() : META_DEFAULT.slice();
  out[0] = c;
  await writeChecked(d, META_FILE, out);
}
async function setProjectColour(pack, slot, c) {           // the whole project is read and written back, with one byte changed
  if (colourOf(c) === null) throw new Error("colour");
  const p = (await projects(pack)).find(x => x.slot === slot);
  if (!p) throw notFound();
  const d = await subdir(pack.dir, "Sessions"), b = await readHandle(await d.getFileHandle(p.file));
  if (projectProblem(b)) throw new Error("proj-head");
  b[PROJ_COLOUR] = c;
  await writeChecked(d, p.file, b);
  pack.drop();
}
function projectKey(b) {                                    // the key of the Plus file a project wants, or null
  return b.length === SESS_SIZE && b[META] === 0x53 && b[META + 1] === 0x4F && b[META + 3] !== 0 ? u32(b, META + 4) : null;
}
const safeName = (s, max) => s.replace(/^\d{2,3}_/, "").replace(/[^ -~]|[\\/:*?"<>|]/g, "_").slice(0, max).replace(/^[\s.]+|[\s.]+$/g, "");
function fileName(file, kind) {                             // a computer file's name, made safe for its slot
  return safeName(file.replace(/\.[^.]+$/, ""), kind === "samples" ? SAMPLE_FILE - 4 : PROJ_NAME) || (kind === "samples" ? "Sample" : "SESSION");
}
function freeRun(list, size, count, start = -1) {           // -> count slots from start (the first free run when start < 0), or null
  const used = new Set(list.map(x => x.slot));
  if (start < 0) for (let i = 0; i + count <= size; i++) if (Array.from({length: count}, (_, k) => i + k).every(k => !used.has(k))) { start = i; break; }
  if (start < 0 || start + count > size) return null;
  return Array.from({length: count}, (_, k) => start + k);
}
async function putFiles(kind, pack, items, to, tick) {      // items: [{name, bytes, key?, plus?}] into slots to
  if (kind === "projects") items = items.map(x => ({...x, bytes: withName(x.bytes, x.name)}));
  await place(kind, items.map((item, i) => ({from: null, item, to: {pack, slot: to[i]}})), {}, tick);
}

// ---------------------------------------------------------------- tidy: Plus files next to their projects, RP_AUTO cleared
// -> {fix: [{pack, p}] renamed files and RP_AUTO-only projects, extra: [{pack, p, name}] second Plus files of one project,
//     dup: [keys of RP_AUTO files that every project already has next to it], orphan: [keys of RP_AUTO files that no project on the card uses],
//     missing: [{pack, p}], bad: [{pack, p}]}
async function tidyPlan(card) {
  const plan = {fix: [], extra: [], dup: [], orphan: [], missing: [], bad: [], names: [], namesUnread: false}, used = new Map();
  let unread = false;
  for (const pack of card.packs) for (const p of await projects(pack)) {
    if (p.inner === undefined) plan.namesUnread = true;
    else if (p.inner !== null && safeName(p.inner, PROJ_NAME) !== p.name) plan.names.push({pack, p});
    if (p.usb) unread = true;
    if (p.key === null) continue;
    if (!used.has(p.key)) used.set(p.key, []);
    used.get(p.key).push({pack, p});
    if (p.state === "renamed" || p.state === "auto") plan.fix.push({pack, p});
    if (p.state === "here" || p.state === "renamed") {
      const keep = p.plus.find(x => x.name === p.want) || p.plus[0];
      for (const x of p.plus) if (x !== keep) plan.extra.push({pack, p, name: x.name});
    }
    if (p.state === "missing") plan.missing.push({pack, p});
    else if (p.state === "bad") plan.bad.push({pack, p});
  }
  for (const [key] of await card.auto()) {
    const u = used.get(key);
    if (!u) { if (!unread) plan.orphan.push(key); }     // a project the unit could not read may use it
    else if (u.every(x => x.p.state === "here" || x.p.state === "renamed")) plan.dup.push(key);
  }
  return plan;
}
// A project's second Plus files are deleted; every Plus file gets the unit's name, next to its project; then the RP_AUTO files that every
// project has are deleted, and the orphans too with orphans. -> the number of files changed; plan.done has them by kind
async function tidyApply(card, plan, {orphans = false} = {}, tick) {
  let n = 0;
  const done = plan.done = {names: 0, extra: 0, placed: 0, copies: 0, unused: 0};
  const step = k => { done[k]++; n++; if (tick) tick(n); };
  for (const {pack, p} of plan.names) {
    const d = await subdir(pack.dir, "Sessions"), b = await readHandle(await d.getFileHandle(p.file));
    if (!projectProblem(b)) { await writeChecked(d, p.file, withName(b, p.name)); step("names"); }
    pack.drop();
  }
  for (const {pack, name} of plan.extra) { await (await subdir(pack.dir, "Sessions")).removeEntry(name); pack.drop(); step("extra"); }
  for (const {pack, p} of plan.fix) {
    const d = await subdir(pack.dir, "Sessions", true), keep = p.plus.filter(x => !plan.extra.some(e => e.pack === pack && e.name === x.name));
    if (p.state === "renamed" && keep.length) await renameIn(d, keep[0].name, p.want);
    else await writeChecked(d, p.want, await readHandle(p.source.handle));
    pack.drop(); step("placed");
  }
  card._auto = null;
  const again = await tidyPlan(card), d = card.autoDir, auto = await card.auto();
  for (const [keys, k] of [[again.dup, "copies"], [orphans ? again.orphan : [], "unused"]]) for (const key of keys) {
    const e = auto.get(key);
    if (e) { await d.removeEntry(e.name); step(k); }
  }
  card.drop();
  return n;
}

// ---------------------------------------------------------------- a Components pack file (.circuitrhythmpack): a zip with index.json
async function inflate(raw) { return new Uint8Array(await new Response(new Blob([raw]).stream().pipeThrough(new DecompressionStream("deflate-raw"))).arrayBuffer()); }
async function unzip(bytes) {                               // -> Map(name -> bytes); stored or deflated entries, each checked against its CRC
  const v = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength), out = new Map(), dec = new TextDecoder();
  let e = bytes.length - 22;
  while (e >= 0 && v.getUint32(e, true) !== 0x06054B50) e--;
  if (e < 0) throw new Error("pack-bad");
  for (let i = 0, n = v.getUint16(e + 10, true), o = v.getUint32(e + 16, true); i < n; i++) {
    if (v.getUint32(o, true) !== 0x02014B50) throw new Error("pack-bad");
    const method = v.getUint16(o + 10, true), crc = v.getUint32(o + 16, true), csize = v.getUint32(o + 20, true), size = v.getUint32(o + 24, true);
    const nl = v.getUint16(o + 28, true), at = v.getUint32(o + 42, true), name = dec.decode(bytes.subarray(o + 46, o + 46 + nl));
    o += 46 + nl + v.getUint16(o + 30, true) + v.getUint16(o + 32, true);
    if (name.endsWith("/")) continue;
    if (v.getUint32(at, true) !== 0x04034B50) throw new Error("pack-bad");
    const from = at + 30 + v.getUint16(at + 26, true) + v.getUint16(at + 28, true), raw = bytes.subarray(from, from + csize);
    const b = method === 0 ? raw.slice() : method === 8 ? await inflate(raw) : null;
    if (!b || b.length !== size || crc32(b) !== crc) throw new Error("pack-bad");
    out.set(name, b);
  }
  return out;
}
const GRIDFX_SIZE = 7, NGRIDFX = 16, META_DEFAULT = Uint8Array.of(0, 0);     // META_DEFAULT: red, last project 0, as Components writes
const isBlank = b => String.fromCharCode(...b.subarray(0, 4)) === "INIT";
// -> {name, projects: [{slot, name, bytes}], blank: the blank projects left out, samples: [{slot, name, bytes}], gridfx: the 16 Grid FX as one file, or null}
async function readPack(bytes) {
  const z = await unzip(bytes), index = z.get("index.json");
  if (!index) throw new Error("pack-bad");
  const j = JSON.parse(new TextDecoder().decode(index));
  if (j.product !== "circuit-rhythm") throw new Error("pack-product");
  // an entry with no name and no file is an empty slot; a named entry with no file is a damaged pack
  const get = x => { const b = z.get(x.url); if (!b && x.name) throw new Error("pack-bad"); return b || null; };
  const all = (j.projects || []).slice(0, NSESS).map((x, slot) => {
    const b = get(x);
    if (b && projectProblem(b)) throw new Error("pack-bad");
    return b && {slot, name: safeName(x.name || "", PROJ_NAME) || "SESSION", bytes: b};
  }).filter(Boolean);
  const projects = all.filter(x => !isBlank(x.bytes)).map(x => ({...x, bytes: withName(x.bytes, x.name)}));     // an empty slot loads the same blank project
  const samples = (j.samples || []).slice(0, NSAMPLES).map((x, slot) => { const b = get(x); return b && {slot, name: safeName(x.name || "", nameMax(slot, "sample")) || "PCM", bytes: b}; })
    .filter(Boolean);
  const fx = (j.gridEffects || []).map(x => z.get(x.url));
  const gridfx = fx.length === NGRIDFX && fx.every(b => b && b.length === GRIDFX_SIZE) ? Uint8Array.from(fx.flatMap(b => [...b])) : null;
  return {name: safeName(j.name || "", FOLDER_MAX - 3) || "PACK", projects, blank: all.length - projects.length, samples, gridfx};
}
// A whole pack, deleted. Its Plus files go to RP_AUTO first, as the unit does.
async function deletePack(card, pack) {
  if (card.device) await card.rhythm.removeEntry(pack.folder);
  else {
    const have = await card.auto(), auto = card.autoDir || await placeOf(card, [AUTO], true);
    if (auto) for (const p of await projects(pack)) {
      if (p.key === null || have.has(p.key)) continue;
      const b = await plusBytes(p);
      if (b) { await writeChecked(auto, hex8(p.key) + ".RPS", b); have.set(p.key, {name: hex8(p.key) + ".RPS"}); }
    }
    card._auto = null;
    await card.rhythm.removeEntry(pack.folder, {recursive: true});
  }
  await card.scan();
}
// A read pack into an empty pack slot, as the unit lays a pack out. Over USB the unit makes the folders as it writes. -> the new Pack
async function loadPack(card, slot, name, pk, tick) {
  if (card.pack(slot)) throw new Error("pack-used");
  const bad = nameProblem(name, slot, card.packs.map(x => x.folder), "pack");
  if (bad) throw new Error(bad);
  const folder = pad2(slot) + "_" + name, files = [
    ...pk.projects.map(x => ["Sessions", 3, x.slot, prefix(x.slot) + "_" + x.name + ".ncs", x.bytes]),
    ...pk.samples.map(x => ["PCM", 5, x.slot, prefix(x.slot) + "_" + x.name + ".wav", x.bytes]),
    ...(pk.gridfx ? [["GridFx", 6, 0, "00_GRIDFX.ncg", pk.gridfx]] : []),
    ["meta", 7, 0, "00_META.ncm", META_DEFAULT]];
  let n = 0;
  if (card.device) {
    const dev = card.rhythm.dev, P = slot + 1, def = new Map(DEV_FOLDERS.map(([d, T, f]) => [T, f]));
    for (const [, T, I, file, b] of files) {
      dev.name(file);
      checkHalt();
      await dev.write(T, P, I, b);
      if (file !== prefix(I) + "_" + def.get(T)) await dev.rename(T, P, I, file);
      if (tick) tick(++n, files.length);
    }
    await dev.renamePack(P, folder);
    card.rhythm.cache = null;
  } else {
    const top = await card.rhythm.getDirectoryHandle(folder, {create: true}), dirs = new Map();
    for (const [sub, , , file, b] of files) {
      checkHalt();
      if (!dirs.has(sub)) dirs.set(sub, await subdir(top, sub, true));
      await writeChecked(dirs.get(sub), file, b);
      if (tick) tick(++n, files.length);
    }
  }
  await card.scan();
  return card.pack(slot);
}

// ---------------------------------------------------------------- backup and restore: the Rhythm folder, RP_AUTO and RP_INTERNAL, in a folder outside the card's packs
async function backup(card, dest, tick) {
  const name = "Rhythm Plus backup " + stamp(), top = await dest.getDirectoryHandle(name, {create: true});
  const parts = [["Rhythm", card.rhythm]];
  if (card.autoDir) parts.push([AUTO, card.autoDir]);
  if (card.intDir) parts.push([INTERNAL, card.intDir]);
  let files = 0, bytes = 0;
  for (const [n, src] of parts) {
    const dst = await top.getDirectoryHandle(n, {create: true});
    await copyTree(src, dst, (f, size) => { files++; bytes += size; if (tick) tick(f, files); });
    if (!await sameTree(src, dst)) throw new Error("verify");
  }
  await writeFile(top, BACKUP_FILE, new TextEncoder().encode(JSON.stringify({app: "Rhythm Plus", made: stamp(), packs: card.packs.map(p => p.folder), files, bytes}, null, 1)));
  return {name, files, bytes};
}
// -> {write: [{parts, name, handle, old}], same, conflict: [{folder, card}]}. A pack whose number has another name on the card is a conflict:
// both folders would start with the same NN_.
async function placeOf(card, parts, create) {             // a backup path (Rhythm/..., RP_AUTO/... or RP_INTERNAL/...) on the card
  if (parts[0] === "Rhythm") return dirPath(card.rhythm, parts.slice(1), create);
  if (parts[0] === INTERNAL) {
    if (!card.intDir && card.root && create) card.intDir = await subdir(card.root, INTERNAL, true);
    return card.intDir && dirPath(card.intDir, parts.slice(1), create);
  }
  if (!card.autoDir && card.root && create) card.autoDir = await subdir(card.root, AUTO, true);
  return card.autoDir && dirPath(card.autoDir, parts.slice(1), create);
}
async function restorePlan(card, top) {
  if (!await fileIn(top, BACKUP_FILE)) throw new Error("backup-bad");
  const plan = {write: [], twins: [], same: 0, conflict: []}, rhythm = await subdir(top, "Rhythm");
  const walk = async (src, parts) => {
    for (const [n, h] of await entries(src)) {
      if (h.kind === "directory") { await walk(h, [...parts, n]); continue; }
      const dir = await placeOf(card, parts, false), old = dir && await fileIn(dir, n);
      if (old && sameBytes(await readHandle(old), await readHandle(h))) { plan.same++; continue; }
      plan.write.push({parts, name: n, handle: h, old: !!old});
      const pre = /^(\d{2,3})_/.exec(n);
      if (dir && pre && parts[0] === "Rhythm" && parts.length === 3)
        for (const [m, g] of await entries(dir)) if (g.kind === "file" && m !== n && m.startsWith(pre[0]) && lower(m.slice(m.lastIndexOf("."))) === lower(n.slice(n.lastIndexOf("."))))
          plan.twins.push({parts, name: m});
    }
  };
  if (rhythm) for (const [folder, h] of await entries(rhythm)) {
    if (h.kind !== "directory") continue;
    const m = /^(\d\d)_/.exec(folder), on = m && card.packs.find(p => p.slot === +m[1]);
    if (on && on.folder !== folder) { plan.conflict.push({folder, card: on.folder}); continue; }
    await walk(h, ["Rhythm", folder]);
  }
  const auto = await subdir(top, AUTO);
  if (auto && !card.autoDir && !card.root) plan.noAuto = true;      // the backup's RP_AUTO cannot be put back until that folder is given
  else if (auto) await walk(auto, [AUTO]);
  const internal = await subdir(top, INTERNAL);
  if (internal && !card.root) plan.noInternal = true;              // only the card's top folder can take it
  else if (internal) await walk(internal, [INTERNAL]);
  return plan;
}
async function restoreApply(card, plan, tick) {
  if (plan.conflict.length) throw new Error("backup-conflict");
  let n = 0;
  const gone = new Set();
  for (const x of [...plan.twins, ...plan.write.filter(w => w.old)]) {
    const id = lower([...x.parts, x.name].join("/"));
    if (!gone.has(id)) { gone.add(id); await (await placeOf(card, x.parts, false)).removeEntry(x.name); }
  }
  for (const w of plan.write) { await writeChecked(await placeOf(card, w.parts, true), w.name, await readHandle(w.handle)); if (tick) tick(w.name, ++n); }
  await card.scan(); card.drop();
  return n;
}

// ---------------------------------------------------------------- the unit over USB: the stock file protocol, F0 00 20 29 01 63 03 CMD ...
// From Circuit Remix's rm_app.html (Ghillermo, MIT). Rules the firmware does not enforce: 40 with a session open, or 41 with none, damages the
// loaded project; a write deletes the old file before any data arrives; a data packet must be one constant size (CHUNK); names over 31
// characters overwrite the firmware's stack.
const NOVATION = [0xF0, 0x00, 0x20, 0x29, 0x01, 0x63], CHUNK = 0x2000, NAME_MAX = 31;
// Rhythm Plus's own SysEx (A0239 and newer): F0 7D 43 54 cmd seq dir len name fields.., padded to PX_PAD; the reply: cmd | 0x40, seq,
// the status as 8 nibbles, then the command's fields. dir 0 = RP_AUTO, 1-31 = a pack (its USB number). Only Plus file names are taken.
const PX_SIG = [0xF0, 0x7D, 0x43, 0x54], PX_PAD = 232, PX_N = 64;
const BUILD_AT = 0x080101E8;                                // where every Rhythm Plus build keeps its name (A0213 and newer)
const PX = {BAD: 0x100, NOPACK: 0x101, BUSY: 0x102, SHORT: 0x103, END: 0x110};
const nibbles = b => { const o = []; for (const v of b) o.push(v >> 4, v & 15); return o; };
const unnib = (m, at, n) => { const o = new Uint8Array(n); for (let i = 0; i < n; i++) o[i] = ((m[at + 2 * i] & 15) << 4) | (m[at + 2 * i + 1] & 15); return o; };
const pxError = st => new Error(st === PX.BUSY ? "device-busy" : st === 4 ? "gone" : st === 8 ? "plus-exists" : "device-plus-" + st.toString(16));
const n32 = v => [28, 24, 20, 16, 12, 8, 4, 0].map(k => (v >>> k) & 15);
function un32(b, o) { let v = 0; for (let i = 0; i < 8; i++) v = v * 16 + (b[o + i] & 15); return v; }
function enc7(d) {
  const out = [];
  for (let i = 0; i < d.length; i += 7) {
    const n = Math.min(7, d.length - i); let m = 0;
    for (let k = 0; k < n; k++) m |= (d[i + k] >> 7) << k;
    out.push(m);
    for (let k = 0; k < n; k++) out.push(d[i + k] & 0x7F);
  }
  return out;
}
function dec7(e) {
  const out = new Uint8Array(e.length); let o = 0;
  for (let i = 0; i < e.length; i += 8) {
    const m = e[i], n = Math.min(7, e.length - i - 1);
    for (let k = 0; k < n; k++) out[o++] = e[i + 1 + k] | (((m >> k) & 1) << 7);
  }
  return out.subarray(0, o);
}
const isFile = m => m[6] === 3;
const text = (m, a, b) => String.fromCharCode(...m.subarray(a, b));
const notFound = () => Object.assign(new Error("not found"), {name: "NotFoundError"});
class Device {
  // tx: {send(Uint8Array), onmessage} over a Web MIDI port pair
  constructor(tx) { this.tx = tx; this.q = []; this.wake = null; this.sess = false; this.loaded = null; this.tail = Promise.resolve(); tx.onmessage = m => this.rx(m); }
  rx(m) { this.q.push(m); if (this.wake) { const w = this.wake; this.wake = null; w(); } }
  run(fn) { const p = this.tail.then(fn); this.tail = p.catch(() => {}); return p; }       // one command at a time, its replies with it
  async next(test, ms) {
    const end = Date.now() + ms;
    for (;;) {
      while (this.q.length) { const m = this.q.shift(); if (test(m)) return m; }
      const left = end - Date.now();
      if (left <= 0) throw new Error("device-timeout");
      await new Promise(res => { const t = setTimeout(() => { this.wake = null; res(); }, left); this.wake = () => { clearTimeout(t); res(); }; });
    }
  }
  file(...b) { this.tx.send(Uint8Array.from([...NOVATION, 3, ...b, 0xF7])); }
  async status(ms) { const m = await this.next(x => isFile(x) && (x[7] === 4 || x[7] === 5), ms); return {ok: m[7] === 4, c: un32(m, 8), code: m[7] === 5 ? m[19] : 0}; }
  async must(ms) { const s = await this.status(ms); if (!s.ok) throw new Error("device-status-" + s.code); return s; }
  identify() {
    return this.run(async () => {
      this.q.length = 0;
      this.tx.send(Uint8Array.of(0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7));
      const m = await this.next(x => x[1] === 0x7E && x[3] === 6 && x[4] === 2, 2000);
      if (m[5] !== 0 || m[6] !== 0x20 || m[7] !== 0x29 || m[8] !== 1 || m[9] !== 0x63) throw new Error("device-other");
      this.tx.send(Uint8Array.of(...NOVATION, 0x49, 0xF7));
      const s = await this.next(x => x[6] === 9 && x.length >= 20, 1000).catch(() => null);
      this.loaded = s ? s[s.length - 2] : null;
    });
  }
  open() {
    return this.run(async () => {
      this.q.length = 0;
      this.file(0x0B, 1);                                   // a session left open answers; a closed one ignores it
      const m = await this.next(x => isFile(x) && (x[7] === 0x0B || x[7] === 4 || x[7] === 5), 1000).catch(() => null);
      if (m) { this.sess = true; return; }
      this.file(0x40, 0);
      const s = await this.status(60000);
      if (!s.ok) throw new Error(s.code === 3 ? "device-busy" : "device-status-" + s.code);
      this.sess = true;
    });
  }
  close() { return this.run(async () => { if (!this.sess) return; this.sess = false; this.file(0x41, 0); await this.must(60000); }); }
  closeNow() { if (this.sess) { this.sess = false; this.file(0x41, 0); } }
  packs() {
    return this.run(async () => {
      this.file(0x0B, 2);
      const h = await this.next(x => isFile(x) && x[7] === 0x0B && x[8] === 2, 20000), out = [];
      for (let i = 0; i < h[9]; i++) {
        const m = await this.next(x => isFile(x) && x[7] === 0x0C && x[8] === 2, 3000).catch(() => null);
        if (!m) break;
        out.push({P: m[9], name: text(m, 10, m.length - 1)});
      }
      return out;
    });
  }
  items(T, P) {
    return this.run(async () => {
      this.file(0x0B, T, P);
      const h = await this.next(x => isFile(x) && (x[7] === 5 || (x[7] === 0x0B && x[8] === T && x[9] === P)), 20000), out = [];
      if (h[7] === 5) throw new Error("device-status-" + h[19]);
      for (let i = 0, n = h[10] + 128 * h[11]; i < n; i++) {
        const m = await this.next(x => isFile(x) && x[7] === 0x0C && x[8] === T && x[9] === P, 3000).catch(() => null);
        if (!m) break;
        out.push({I: m[10], name: text(m, 11, m.length - 1)});
      }
      return out;
    });
  }
  value(cmd, T, P, I, ms) {                                 // 0A size, 0D CRC
    return this.run(async () => {
      this.file(cmd, T, P, I);
      const m = await this.next(x => isFile(x) && (x[7] === 5 || (x[7] === cmd && x[8] === T && x[9] === P && x[10] === I)), ms);
      if (m[7] === 5) throw new Error("device-status-" + m[19]);
      return un32(m, 11);
    });
  }
  size(T, P, I) { return this.value(0x0A, T, P, I, 5000); }
  read(T, P, I) {
    return this.run(async () => {
      this.file(1, ...n32(0), T, P, I, 2, ...n32(0));
      const h = await this.next(x => isFile(x) && (x[7] === 1 || x[7] === 5 || x[7] === 6), 10000);
      if (h[7] === 6) return null;
      if (h[7] === 5) throw new Error("device-status-" + h[19]);
      const size = un32(h, 20), out = new Uint8Array(size);
      for (let o = 0; ;) {
        const m = await this.next(x => isFile(x) && (x[7] === 2 || x[7] === 3), 5000);
        if (m[7] === 2) { const d = dec7(m.subarray(19, m.length - 1)); if (o + d.length > size) throw new Error("device-read"); out.set(d, o); o += d.length; continue; }
        if (o !== size || un32(m, 19) !== crc32(out)) throw new Error("device-read");
        return out;
      }
    });
  }
  write(T, P, I, data) {
    return this.run(async () => {
      const n = Math.ceil(data.length / CHUNK), crc = crc32(data);
      for (let attempt = 0; ; attempt++) {
        this.file(1, ...n32(0), T, P, I, 1, ...n32(data.length));
        await this.must(10000);
        for (let k = 1, resend = 0; k <= n;) {
          this.file(2, ...n32(k), T, P, I, ...enc7(data.subarray((k - 1) * CHUNK, k * CHUNK)));
          const s = await this.status(10000);
          if (s.ok) { k++; resend = 0; continue; }
          if (s.code !== 2 || ++resend > 4) throw new Error("device-status-" + s.code);
          k = s.c + 1;
        }
        this.file(3, ...n32(n + 1), T, P, I, ...n32(crc));
        const s = await this.status(10000 + 1000 * data.length / 1048576);      // it reads the file back from the card
        if (s.ok) return;
        if (s.code !== 4 || attempt >= 2) throw new Error("device-status-" + s.code);
      }
    });
  }
  name(name) {
    if (name.length > NAME_MAX || !/^[ -~]+$/.test(name)) throw new Error("device-name");
    return [...name].map(c => c.charCodeAt(0));
  }
  rename(T, P, I, name) { const b = this.name(name); return this.run(async () => { this.file(7, T, P, I, ...b); await this.must(10000); }); }
  renamePack(P, name) { const b = this.name(name); return this.run(async () => { this.file(7, 2, P, ...b); await this.must(30000); }); }
  delPack(P) { return this.run(async () => { this.file(8, 2, P); await this.must(60000); }); }
  del(T, P, I) { return this.run(async () => { this.file(8, T, P, I); await this.must(10000); }); }
  px(cmd, dir, name = "", fields = [], ms = 4000) {
    if (!/^[ -~]{0,64}$/.test(name)) return Promise.reject(new Error("device-name"));
    return this.run(async () => {
      for (let tries = 0; ; tries++) {
        const seq = this.seq = ((this.seq || 0) + 1) & 0x7F, m = new Uint8Array(PX_PAD);
        m.set([...PX_SIG, cmd, seq, dir, name.length, ...[...name].map(c => c.charCodeAt(0)), ...fields]); m[PX_PAD - 1] = 0xF7;
        this.tx.send(m);
        const r = await this.next(x => x[0] === 0xF0 && x[1] === 0x7D && x[2] === 0x43 && x[3] === 0x54 && x[4] === (cmd | 0x40) && x[5] === seq, ms);
        const st = un32(r, 6);
        if (st === PX.BUSY && tries < 40) { await new Promise(res => setTimeout(res, 50)); continue; }
        return {st, r};
      }
    });
  }
  async buildName() {                                      // the Rhythm Plus build in the unit's flash, through rdiag's flash read; null if none answers
    return this.run(async () => {
      const seq = this.seq = ((this.seq || 0) + 1) & 0x7F, m = new Uint8Array(PX_PAD);
      m.set([...PX_SIG, 2, seq, ...n32(BUILD_AT), 8]); m[PX_PAD - 1] = 0xF7;
      this.tx.send(m);
      const r = await this.next(x => x[0] === 0xF0 && x[1] === 0x7D && x[4] === 0x42 && x[5] === seq, 800).catch(() => null);
      if (!r || un32(r, 6)) return null;
      const t = String.fromCharCode(...unnib(r, 14, 8)).split(String.fromCharCode(0))[0];
      return /^[A-Z]{1,2}\d{3,4}$/.test(t) ? t : null;
    });
  }
  async plusHello() {                                       // -> true when the firmware has the Plus file commands
    const a = await this.px(0x20, 0, "", [], 800).catch(() => null);
    this.plusOk = !!a && a.st === 0 && un32(a.r, 14) >= 1;
    this.pxVersion = this.plusOk ? un32(a.r, 14) : 0;
    this.metaOk = false;
    if (this.plusOk) { const b = await this.px(0x28, 0, "", [0], 800).catch(() => null); this.metaOk = !!b && b.st !== PX.BAD; }
    return this.plusOk;
  }
  async plusMeta(dir, slot) {                               // -> {size, m: the 20 Plus bytes, head: the first 48 bytes (version 3), colour (version 2+)}, or null for an empty slot
    const {st, r} = await this.px(0x28, dir, "", [slot]);
    if (st === 4) return null;
    if (st) throw pxError(st);
    const head = this.pxVersion >= 3 ? unnib(r, 62, 48) : null;
    return {size: un32(r, 14), m: unnib(r, 22, 20), head, colour: head ? head[12] : this.pxVersion >= 2 ? unnib(r, 62, 1)[0] : null};
  }
  async plusFolder(dir) { const {st, r} = await this.px(0x20, dir); if (st) throw pxError(st); return String.fromCharCode(...r.subarray(23, 23 + r[22])); }
  async plusList(dir) {
    const out = [];
    for (let i = 0; i < 512; i++) {
      const {st, r} = await this.px(0x21, dir, "", n32(i));
      if (st === PX.END || !i && (st === 4 || st === 5)) return out;     // 4, 5: the folder is not on the card, so it holds none
      if (st) throw pxError(st);
      out.push({name: String.fromCharCode(...r.subarray(23, 23 + r[22])), size: un32(r, 14)});
    }
    return out;
  }
  async plusRead(dir, name) {
    let size = Infinity, out = new Uint8Array(0);
    for (let off = 0; off < size;) {
      const {st, r} = await this.px(0x22, dir, name, [...n32(off), PX_N]);
      if (st) throw pxError(st);
      size = un32(r, 14); const n = un32(r, 22);
      if (!n && off < size) throw new Error("device-read");
      const b = new Uint8Array(off + n); b.set(out); b.set(unnib(r, 30, n), off); out = b; off += n;
    }
    const c = await this.px(0x25, dir, name);
    if (c.st || un32(c.r, 14) !== out.length || un32(c.r, 22) !== crc32(out)) throw new Error("device-read");
    return out;
  }
  async plusWrite(dir, name, data) {
    for (let off = 0; off === 0 || off < data.length; off += PX_N) {
      const part = data.subarray(off, off + PX_N), {st} = await this.px(0x23, dir, name, [...n32(off), part.length, ...nibbles(part)]);
      if (st) throw pxError(st);
    }
    const c = await this.px(0x25, dir, name);
    if (c.st || un32(c.r, 14) !== data.length || un32(c.r, 22) !== crc32(data)) throw new Error("verify");
  }
  async plusDel(dir, name) { const {st} = await this.px(0x24, dir, name); if (st && st !== 4) throw pxError(st); }
  async plusRename(dir, name, to) { const {st} = await this.px(0x26, dir, name, [to.length, ...[...to].map(c => c.charCodeAt(0))]); if (st) throw pxError(st); }
}
// The unit as folders: Rhythm's packs, each with Sessions (type 3) and PCM (type 5); a file is (type, pack, slot).
// the stock USB types: 3 Sessions, 5 PCM, 6 GridFx, 7 meta (a pack may have no GridFx folder)
const DEV_FOLDERS = [["Sessions", 3, "SESSION.ncs"], ["PCM", 5, "PCM.wav"], ["GridFx", 6, "GRIDFX.ncg"], ["meta", 7, "META.ncm"]], DEV_OPTIONAL = new Set([6, 7]);
class DevFile {
  constructor(folder, I, name) { this.kind = "file"; this.device = true; this.folder = folder; this.I = I; this.name = name; }
  async getFile() {
    const f = this.folder, read = () => f.dev.read(f.T, f.P, this.I);
    return {name: this.name, size: await f.dev.size(f.T, f.P, this.I), arrayBuffer: async () => (await read()).buffer, slice: (a, b) => ({arrayBuffer: async () => (await read()).slice(a, b).buffer})};
  }
  async createWritable() {
    let data = new Uint8Array(0);
    return {write: async b => { data = b; }, close: () => this.folder.put(this.I, this.name, data), abort: async () => {}};
  }
}
class DevPlusFile {
  constructor(folder, name, size) { this.kind = "file"; this.device = true; this.plus = true; this.folder = folder; this.name = name; this.size = size; }
  async getFile() {
    const f = this.folder, read = () => f.dev.plusRead(f.P, this.name);
    return {name: this.name, size: this.size, arrayBuffer: async () => (await read()).buffer, slice: (a, b) => ({arrayBuffer: async () => (await read()).slice(a, b).buffer})};
  }
  async createWritable() {
    let data = new Uint8Array(0);
    return {write: async b => { data = b; }, close: async () => { await this.folder.dev.plusWrite(this.folder.P, this.name, data); this.folder.cache = null; }, abort: async () => {}};
  }
}
class DevFolder {
  // T null: RP_AUTO (P 0), Plus files only. A pack's Sessions lists its Plus files when the firmware has the commands.
  constructor(pack, name, T, def) { this.kind = "directory"; this.device = true; this.dev = pack.dev; this.P = pack.P; this.pack = pack; this.name = name; this.T = T; this.def = def; this.cache = null; }
  get plus() { return !!this.dev.plusOk && (this.T === 3 || this.T === null); }
  isPlus(n) { return this.plus && (this.T === null ? autoParse(n) !== null : !!plusParse(n)); }
  async list() {
    if (this.cache) return this.cache;
    const out = this.T === null ? [] : DEV_OPTIONAL.has(this.T) ? await this.dev.items(this.T, this.P).catch(() => []) : await this.dev.items(this.T, this.P);
    if (this.plus) {
      if (this.T !== null && !this.pack.checked) {           // the unit's folder for this pack number must be this pack
        const want = "1:/Rhythm/" + this.pack.name + "/Sessions/", got = await this.dev.plusFolder(this.P);
        if (lower(got) !== lower(want)) throw new Error("device-plus-pack");
        this.pack.checked = true;
      }
      for (const x of await this.dev.plusList(this.P)) out.push({name: x.name, size: x.size, plus: true});
    }
    return this.cache = out;
  }
  async *entries() { for (const e of await this.list()) yield [e.name, e.plus ? new DevPlusFile(this, e.name, e.size) : new DevFile(this, e.I, e.name)]; }
  async getFileHandle(name, opt = {}) {
    const e = (await this.list()).find(x => x.name === name), m = /^(\d{2,3})_/.exec(name);
    if (e && e.plus) return new DevPlusFile(this, e.name, e.size);
    if (this.isPlus(name)) { if (!opt.create) throw notFound(); return new DevPlusFile(this, name, 0); }
    if (e) return new DevFile(this, e.I, e.name);
    if (!opt.create) throw notFound();
    if (!m) throw new Error("device-name");
    return new DevFile(this, +m[1], name);
  }
  async put(I, name, data) {
    this.dev.name(name);                                    // refused before the write takes the old file away
    await this.dev.write(this.T, this.P, I, data);
    this.cache = null;
    const was = pad2(I) + "_" + this.def;
    if (was !== name) { await this.dev.rename(this.T, this.P, I, name); this.cache = null; }
  }
  async removeEntry(name) {
    const e = (await this.list()).find(x => x.name === name);
    if (!e) return;
    if (e.plus) await this.dev.plusDel(this.P, name); else await this.dev.del(this.T, this.P, e.I);
    this.cache = null;
  }
  async renameEntry(name, to) {
    const e = (await this.list()).find(x => x.name === name);
    if (!e) throw notFound();
    if (e.plus) { if (!this.isPlus(to)) throw new Error("device-name"); await this.dev.plusRename(this.P, name, to); }
    else await this.dev.rename(this.T, this.P, e.I, to);
    this.cache = null;
  }
}
class DevPack {
  constructor(root, P, name) { this.kind = "directory"; this.device = true; this.dev = root.dev; this.P = P; this.name = name; this.sub = new Map(DEV_FOLDERS.map(([n, T, def]) => [n, new DevFolder(this, n, T, def)])); }
  async *entries() { for (const e of this.sub) yield e; }
  async getDirectoryHandle(n) { const d = this.sub.get(n); if (!d) throw notFound(); return d; }
}
class DevRoot {
  constructor(dev) {
    this.kind = "directory"; this.device = true; this.dev = dev; this.name = "Circuit Rhythm"; this.cache = null; this.open = new Map();
    this.auto = dev.plusOk ? new DevFolder({dev, P: 0, name: AUTO}, AUTO, null, null) : null;
  }
  async list() { return this.cache || (this.cache = (await this.dev.packs()).filter(x => x.P >= 1)); }    // pack 0, the internal memory, stays out
  handle(P, name) { let h = this.open.get(name); if (!h) this.open.set(name, h = new DevPack(this, P, name)); return h; }
  async *entries() { for (const x of await this.list()) yield [x.name, this.handle(x.P, x.name)]; }
  async getDirectoryHandle(name) { const x = (await this.list()).find(e => e.name === name); if (!x) throw notFound(); return this.handle(x.P, x.name); }
  async renameEntry(name, to) {
    const x = (await this.list()).find(e => e.name === name);
    if (!x) throw notFound();
    await this.dev.renamePack(x.P, to);
    this.cache = null; this.open.delete(name);
  }
  async removeEntry(name) {                                 // the whole pack; Rhythm Plus moves the pack's Plus files to RP_AUTO first
    const x = (await this.list()).find(e => e.name === name);
    if (!x) throw notFound();
    await this.dev.delPack(x.P);
    this.cache = null; this.open.delete(name);
  }
}

return {stop, go, NSAMPLES, SAMPLE_MAX, PAGES, PAGE_WORDS, samplePages, SLOT_AT, Device, DevRoot, enc7, dec7, KIND, transfer, place, deleteItems, renameItem, renamePack, remapSession, remapPack,
  wavInfo, unitWav, wavEncode, projectProblem, projectKey, fileName, freeRun, putFiles, nameMax, itemAt, unzip, readPack, loadPack, deletePack, COLOURS, COLOURS_SHOWN, packColour, NAME_AT, setPackColour, setProjectColour,
  NSESS, NPACKS, SESS_SIZE, META, PROJ_NAME, FOLDER_MAX, AUTO, BACKUP_FILE, pad2, hex8, crc32, stamp, entries, subdir, readHandle, writeFile, treeInfo,
  plusName, plusParse, autoParse, nameProblem, Card, Pack, projects, project, samples, renameProject, copyProject, deleteProject, tidyPlan, tidyApply,
  backup, restorePlan, restoreApply};
})();
if (typeof window !== "undefined") window.RP = RP;
if (typeof module !== "undefined") module.exports = RP;
