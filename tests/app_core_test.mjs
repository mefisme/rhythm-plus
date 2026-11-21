// The app's card logic (tools/app/core.js) on a fake card: FAT names (case kept, compared without case), no folder rename.
//   node tests/app_core_test.mjs
import {createRequire} from "module";
const require = createRequire(import.meta.url);
const RP = require("../tools/app/core.js");

let fails = 0;
const check = (name, ok, info) => { console.log((ok ? "PASS " : "FAIL ") + name + (ok || info === undefined ? "" : "  " + JSON.stringify(info))); if (!ok) fails++; };
const err = name => Object.assign(new Error(name), {name});

class File_ { constructor(b) { this.b = b; } get size() { return this.b.length; } async arrayBuffer() { return this.b.slice().buffer; }
  slice(a, z) { const c = this.b.slice(a, z); return {arrayBuffer: async () => c.buffer}; } }
class FileH {
  constructor(parent, name, bytes) { this.kind = "file"; this.parent = parent; this.name = name; this.bytes = bytes; }
  async getFile() { return new File_(this.bytes); }
  async createWritable() { const h = this; let buf = null;
    return {write: async b => { buf = new Uint8Array(b); }, close: async () => { h.bytes = buf; }, abort: async () => {}}; }
}
class Dir {
  constructor(name, parent = null) { this.kind = "directory"; this.name = name; this.parent = parent; this.kids = new Map(); }
  find(name) { for (const [k, v] of this.kids) if (k.toLowerCase() === name.toLowerCase()) return v; return null; }
  async getDirectoryHandle(name, {create = false} = {}) {
    const h = this.find(name);
    if (h) { if (h.kind !== "directory") throw err("TypeMismatchError"); return h; }
    if (!create) throw err("NotFoundError");
    const d = new Dir(name, this); this.kids.set(name, d); return d;
  }
  async getFileHandle(name, {create = false} = {}) {
    const h = this.find(name);
    if (h) { if (h.kind !== "file") throw err("TypeMismatchError"); return h; }
    if (!create) throw err("NotFoundError");
    const f = new FileH(this, name, new Uint8Array(0)); this.kids.set(name, f); return f;
  }
  async removeEntry(name) { for (const k of this.kids.keys()) if (k.toLowerCase() === name.toLowerCase()) { this.kids.delete(k); return; } throw err("NotFoundError"); }
  async *entries() { for (const [k, v] of [...this.kids]) yield [k, v]; }
}
const at = (d, path) => path.split("/").reduce((x, p) => x && x.find(p), d);
const names = (d, path) => { const x = at(d, path); return x ? [...x.kids.keys()].sort() : []; };
function put(d, path, bytes) {
  const parts = path.split("/"), file = parts.pop();
  let x = d; for (const p of parts) { let y = x.find(p); if (!y) { y = new Dir(p, x); x.kids.set(p, y); } x = y; }
  x.kids.set(file, new FileH(x, file, bytes));
}
const plusFile = seed => Uint8Array.from({length: 5072}, (_, i) => (i * 7 + seed) & 255);
function project(seed, plus) {                              // a project; with plus, its metadata points to that Plus file
  const b = new Uint8Array(RP.SESS_SIZE); b.set([0x52, 0x55, 0x53, 0x45]); b[100] = seed;
  if (plus) { const v = new DataView(b.buffer); b.set([0x53, 0x4F, 4, 1], RP.META); v.setUint32(RP.META + 4, RP.crc32(plus), true); v.setUint32(RP.META + 8, plus.length, true); }
  return b;
}
const hex = p => RP.hex8(RP.crc32(p));
const sameB = (a, b) => !!a && !!b && a.length === b.length && a.every((v, i) => v === b[i]);

// ---- a card: pack 08 with five projects, pack 27, RP_AUTO
const root = new Dir("SD");
const A = plusFile(1), B = plusFile(2), C = plusFile(3), D = plusFile(4), E = plusFile(5), O = plusFile(9);
put(root, "Rhythm/07_Beats/Sessions/05_MyBeat.ncs", project(5, A));
put(root, `Rhythm/07_Beats/Sessions/RP_05_MyBeat_${hex(A)}.rps`, A);           // here
put(root, "Rhythm/07_Beats/Sessions/06_Old.ncs", project(6, B));
put(root, `Rhythm/07_Beats/Sessions/RP_06_${hex(B)}.rps`, B);                   // the A0234 name: renamed
put(root, "Rhythm/07_Beats/Sessions/07_Auto.ncs", project(7, C));
put(root, `RP_AUTO/${hex(C)}.RPS`, C);                                          // auto
put(root, "Rhythm/07_Beats/Sessions/08_Lost.ncs", project(8, D));               // missing
put(root, "Rhythm/07_Beats/Sessions/09_SESSION.ncs", project(9, null));         // stock
put(root, "Rhythm/07_Beats/PCM/00_Kick.wav", new Uint8Array(44));
put(root, "Rhythm/26_Other Pack/Sessions/00_Two.ncs", project(10, E));
put(root, `Rhythm/26_Other Pack/Sessions/RP_00_Two_${hex(E)}.rps`, Uint8Array.from(E, (v, i) => i === 3 ? v ^ 1 : v));   // bad
put(root, `RP_AUTO/${hex(A)}.RPS`, A);                                          // a copy the unit left after a save: dup
put(root, `RP_AUTO/${hex(O)}.RPS`, O);                                          // no project: orphan

const card = await RP.Card.open(root);
check("the card: two packs, by their numbers", card.packs.map(p => p.folder).join() === "07_Beats,26_Other Pack");
let threw = null;
const only = await RP.Card.open(at(root, "Rhythm"));
check("the Rhythm folder alone: the packs; RP_AUTO is not known", only.packs.length === 2 && !only.autoDir
      && (await RP.projects(only.pack(7))).find(p => p.slot === 7).state === "missing");
only.useAuto(at(root, "RP_AUTO"));
check("the Rhythm folder, then the RP_AUTO folder: RP_AUTO files are found", (await RP.projects(only.pack(7))).find(p => p.slot === 7).state === "auto");
try { only.useAuto(at(root, "Rhythm/07_Beats")); } catch (e) { threw = e.message; }
check("a folder that is not RP_AUTO is refused", threw === "no-auto", threw);
threw = null; try { await RP.Card.open(at(root, "Rhythm/07_Beats")); } catch (e) { threw = e.message; }
check("a pack folder: refused", threw === "no-rhythm", threw);
const beats = card.pack(7), other = card.pack(26);
const st = async (pack) => Object.fromEntries((await RP.projects(pack)).map(p => [p.slot, p.state]));
check("each project's Plus file state", JSON.stringify(await st(beats)) === JSON.stringify({5: "here", 6: "renamed", 7: "auto", 8: "missing", 9: "stock"}), await st(beats));
check("a Plus file whose bytes do not match the key: bad", (await st(other))[0] === "bad");
check("the unit's name: RP_<slot>_<name>_<KEY>.rps", RP.plusName(beats, 5, "MyBeat", RP.crc32(A)) === `RP_05_MyBeat_${hex(A)}.rps`);
const long = {folder: "07_" + "P".repeat(27)};
check("the longest pack and project names: the name is whole", RP.plusName(long, 5, "N".repeat(24), 1) === "RP_05_" + "N".repeat(24) + "_00000001.rps");
check("a name too long for the unit's path is cut to 103 characters", ("1:/Rhythm/" + long.folder + "/Sessions/" + RP.plusName(long, 5, "N".repeat(60), 1)).length === 103);
check("the unit's parse rules", RP.plusParse("RP_05_" + hex(A) + ".rps").slot === 5 && !RP.plusParse("RP_05_X" + hex(A) + ".rps") && !RP.plusParse("rp_05_" + hex(A) + ".rps")
      && !RP.plusParse("RP_05_" + hex(A).toLowerCase() + ".rps"));

check("samples: by slot, from the PCM folder", JSON.stringify((await RP.samples(beats)).map(({slot, name, file, size}) => ({slot, name, file, size})))
      === JSON.stringify([{slot: 0, name: "Kick", file: "00_Kick.wav", size: 44}]));

// ---- rename
await RP.renameProject(beats, 5, "New Name");
check("rename: the project and its Plus file get the new name", names(root, "Rhythm/07_Beats/Sessions").includes("05_New Name.ncs")
      && names(root, "Rhythm/07_Beats/Sessions").includes(`RP_05_New Name_${hex(A)}.rps`) && !names(root, "Rhythm/07_Beats/Sessions").includes("05_MyBeat.ncs"));
check("rename: still 'here'", (await st(beats))[5] === "here");
threw = null; try { await RP.renameProject(beats, 5, "Bad/Name"); } catch (e) { threw = e.message; }
check("rename: a character the card does not take", threw === "rename-char", threw);
threw = null; try { await RP.renameProject(beats, 7, "é"); } catch (e) { threw = e.message; }
check("rename: not ASCII", threw === "rename-ascii", threw);
await RP.renameProject(beats, 7, "Auto2");
check("rename of an RP_AUTO-only project: its Plus file is made next to it", names(root, "Rhythm/07_Beats/Sessions").includes(`RP_07_Auto2_${hex(C)}.rps`) && (await st(beats))[7] === "here");

// ---- copy and move
await RP.copyProject(beats, 5, other, 3);
check("copy to another pack: the project and its Plus file, with the new slot", names(root, "Rhythm/26_Other Pack/Sessions").includes("03_New Name.ncs")
      && names(root, "Rhythm/26_Other Pack/Sessions").includes(`RP_03_New Name_${hex(A)}.rps`) && (await st(other))[3] === "here" && (await st(beats))[5] === "here");
threw = null; try { await RP.copyProject(beats, 6, other, 3); } catch (e) { threw = e.message; }
check("copy onto a used slot: refused without replace", threw === "slot-used", threw);
await RP.copyProject(beats, 6, other, 3, {replace: true});
check("copy with replace: the old project and its Plus file are deleted, no trash folder", names(root, "Rhythm/26_Other Pack/Sessions").includes("03_Old.ncs")
      && !names(root, "Rhythm/26_Other Pack/Sessions").includes("03_New Name.ncs") && !names(root, "Rhythm/26_Other Pack/Sessions").includes(`RP_03_New Name_${hex(A)}.rps`)
      && !at(root, "Rhythm Plus trash"));
check("copy of a renamed Plus file: written under the unit's name", names(root, "Rhythm/26_Other Pack/Sessions").includes(`RP_03_Old_${hex(B)}.rps`));
await RP.copyProject(beats, 6, beats, 12, {move: true});
check("move in the pack: slot 6 goes, slot 12 has the project and its Plus file", !names(root, "Rhythm/07_Beats/Sessions").some(n => /^06_|^RP_06_/.test(n))
      && names(root, "Rhythm/07_Beats/Sessions").includes("12_Old.ncs") && names(root, "Rhythm/07_Beats/Sessions").includes(`RP_12_Old_${hex(B)}.rps`));
threw = null; try { await RP.copyProject(beats, 8, other, 20); } catch (e) { threw = e.message; }
check("copy of a project whose Plus file is missing: refused", threw === "plus-missing", threw);
await RP.copyProject(beats, 9, other, 21);
check("copy of a stock project: no Plus file", names(root, "Rhythm/26_Other Pack/Sessions").includes("21_SESSION.ncs") && (await st(other))[21] === "stock");

// ---- delete
await RP.deleteProject(beats, 12);
check("delete: the project and its Plus file are deleted, no trash folder", !names(root, "Rhythm/07_Beats/Sessions").some(n => /^12_|^RP_12_/.test(n))
      && !at(root, "Rhythm Plus trash"));

// ---- tidy
put(root, "Rhythm/07_Beats/Sessions/30_Far.ncs", project(30, D));
put(root, `RP_AUTO/${hex(D)}.RPS`, D);                                         // 08_Lost and 30_Far now load from RP_AUTO
put(root, "Rhythm/07_Beats/Sessions/31_Short.ncs", project(31, B));
put(root, `Rhythm/07_Beats/Sessions/RP_31_${hex(B)}.rps`, B);                  // an A0234 name
card.drop();
let plan = await RP.tidyPlan(card);
const who = x => x.map(({pack, p}) => pack.slot + "/" + p.slot).sort().join();
check("tidy plan: files to put next to their projects", who(plan.fix) === "7/30,7/31,7/8", who(plan.fix));
check("tidy plan: RP_AUTO copies every project already has", plan.dup.sort().join() === [RP.crc32(A), RP.crc32(C)].sort().join(), plan.dup);
check("tidy plan: RP_AUTO files with no project", plan.orphan.length === 1 && plan.orphan[0] === RP.crc32(O), plan.orphan);
check("tidy plan: projects with a bad Plus file", who(plan.bad) === "26/0", who(plan.bad));
check("tidy plan: no second Plus files", plan.extra.length === 0, plan.extra.map(x => x.name));
check("tidy plan: every test project has no name inside, so each is listed; a card read gives every name", plan.names.length === 7 && !plan.namesUnread, plan.names.length);
const changed = await RP.tidyApply(card, plan);
check("tidy: the count of files changed (7 names, 3 put next to projects, 3 RP_AUTO copies)", changed === 13, changed);
check("tidy: the changes by kind", JSON.stringify(plan.done) === JSON.stringify({names: 7, extra: 0, placed: 3, copies: 3, unused: 0}), plan.done);
check("tidy: after Fix, no names differ", (await RP.tidyPlan(card)).names.length === 0);
check("tidy: the RP_AUTO files go next to their projects under the unit's names", names(root, "Rhythm/07_Beats/Sessions").includes(`RP_08_Lost_${hex(D)}.rps`)
      && names(root, "Rhythm/07_Beats/Sessions").includes(`RP_30_Far_${hex(D)}.rps`) && names(root, "Rhythm/07_Beats/Sessions").includes(`RP_31_Short_${hex(B)}.rps`)
      && !names(root, "Rhythm/07_Beats/Sessions").includes(`RP_31_${hex(B)}.rps`));
check("tidy: RP_AUTO keeps only the orphan; the copies are deleted", JSON.stringify(names(root, "RP_AUTO")) === JSON.stringify([`${hex(O)}.RPS`]), names(root, "RP_AUTO"));
check("tidy: every project with a Plus file is 'here' or 'bad'", Object.values(await st(beats)).every(s => s === "here" || s === "stock"), await st(beats));
put(root, `Rhythm/07_Beats/Sessions/RP_31_${hex(B)}.rps`, B);                  // the old name again, as a restore of an older backup leaves it
card.drop();
plan = await RP.tidyPlan(card);
check("tidy plan: a project's second Plus file", plan.extra.length === 1 && plan.extra[0].name === `RP_31_${hex(B)}.rps`, plan.extra.map(x => x.name));
await RP.tidyApply(card, plan, {orphans: true});
check("tidy: the second Plus file is deleted; the unit's name stays", !names(root, "Rhythm/07_Beats/Sessions").includes(`RP_31_${hex(B)}.rps`)
      && names(root, "Rhythm/07_Beats/Sessions").includes(`RP_31_Short_${hex(B)}.rps`));
check("tidy with orphans: RP_AUTO is empty, the orphan is deleted", names(root, "RP_AUTO").length === 0 && !at(root, "Rhythm Plus trash"));

// ---- backup and restore
const dest = new Dir("Backups");
const made = await RP.backup(card, dest);
const bk = at(dest, made.name);
check("backup: the Rhythm folder, RP_AUTO and the backup file", !!at(bk, "Rhythm/07_Beats/Sessions/05_New Name.ncs") && !!at(bk, RP.BACKUP_FILE) && made.files > 10, made);
const keep = at(root, "Rhythm/07_Beats/Sessions/05_New Name.ncs").bytes;
at(root, "Rhythm/07_Beats/Sessions/05_New Name.ncs").bytes = project(55, A);
await at(root, "Rhythm/07_Beats/Sessions").removeEntry(`RP_05_New Name_${hex(A)}.rps`);
put(root, "Rhythm/07_Beats/Sessions/05_Twin.ncs", project(77, null));
let rp = await RP.restorePlan(card, bk);
check("restore plan: the changed project, the lost Plus file; a second 05_ file is a twin", rp.write.length === 2 && rp.twins.length === 1 && rp.twins[0].name === "05_Twin.ncs" && rp.same > 10,
      {w: rp.write.map(x => x.name), t: rp.twins.map(x => x.name), same: rp.same});
await RP.restoreApply(card, rp);
check("restore: the project and its Plus file are back; the twin is deleted", RP.crc32(at(root, "Rhythm/07_Beats/Sessions/05_New Name.ncs").bytes) === RP.crc32(keep)
      && !!at(root, `Rhythm/07_Beats/Sessions/RP_05_New Name_${hex(A)}.rps`) && !at(root, "Rhythm/07_Beats/Sessions/05_Twin.ncs"));
put(root, "Rhythm/07_Drums/Sessions/00_X.ncs", project(1, null));
await at(root, "Rhythm").removeEntry("07_Beats");
await card.scan();
rp = await RP.restorePlan(card, bk);
check("restore plan: a pack number with another name on the card is a conflict", rp.conflict.length === 1 && rp.conflict[0].card === "07_Drums", rp.conflict);
threw = null; try { await RP.restoreApply(card, rp); } catch (e) { threw = e.message; }
check("restore with a conflict: refused", threw === "backup-conflict", threw);
threw = null; try { await RP.restorePlan(card, root); } catch (e) { threw = e.message; }
check("restore from a folder that is not a backup: refused", threw === "backup-bad", threw);

// ================================================================ slots: a second card
{
const R2 = new Dir("SD2");
const P1 = plusFile(21), P2 = plusFile(22);
const wav = k => Uint8Array.from({length: 100}, (_, i) => (i * 3 + k) & 255);
function song(seed, plus, track0, flips) {                  // a project whose track 1 plays sample track0; flips: [[step, sample]] on track 1
  const b = project(seed, plus);
  for (let t = 0; t < 8; t++) b[RP.SLOT_AT + t] = 0xFF;
  for (let p = 0; p < 64; p++) for (let st = 0; st < 32; st++) b[0x2E4 + 0xA28 * p + st * 8 + 5] = 0xFF;
  b[RP.SLOT_AT] = track0;
  for (const [st, smp] of flips) { const o = 0x2E4 + st * 8; b[o + 2] = 1; b[o + 5] = smp; }
  return b;
}
put(R2, "Rhythm/00_Alpha/Sessions/00_One.ncs", song(1, P1, 0, [[3, 1]]));
put(R2, `Rhythm/00_Alpha/Sessions/RP_00_One_${hex(P1)}.rps`, P1);
put(R2, "Rhythm/00_Alpha/Sessions/01_Two.ncs", song(2, null, 1, []));
put(R2, "Rhythm/00_Alpha/PCM/00_Kick.wav", wav(0));
put(R2, "Rhythm/00_Alpha/PCM/01_Snare.wav", wav(1));
put(R2, "Rhythm/00_Alpha/PCM/02_Hat.wav", wav(2));
put(R2, "Rhythm/05_Beta/Sessions/00_Old.ncs", song(3, P2, 0, []));
put(R2, `Rhythm/05_Beta/Sessions/RP_00_Old_${hex(P2)}.rps`, P2);
const c2 = await RP.Card.open(R2), alpha = c2.pack(0), beta = c2.pack(5);
const sess = (pk, f) => at(R2, `Rhythm/${pk}/Sessions/${f}`).bytes;

await RP.transfer("projects", alpha, [0], beta, [3]);
check("copy a project to another pack: its Plus file goes with it, under the new slot", names(R2, "Rhythm/05_Beta/Sessions").includes("03_One.ncs")
      && names(R2, "Rhythm/05_Beta/Sessions").includes(`RP_03_One_${hex(P1)}.rps`) && names(R2, "Rhythm/00_Alpha/Sessions").includes("00_One.ncs"));
await RP.transfer("projects", alpha, [0, 1], beta, [0, 1], {swap: true});
check("swap two projects with two of another pack: each with its Plus file", names(R2, "Rhythm/05_Beta/Sessions").includes("00_One.ncs")
      && names(R2, "Rhythm/05_Beta/Sessions").includes("01_Two.ncs") && names(R2, "Rhythm/00_Alpha/Sessions").includes("00_Old.ncs")
      && names(R2, "Rhythm/00_Alpha/Sessions").includes(`RP_00_Old_${hex(P2)}.rps`) && names(R2, "Rhythm/05_Beta/Sessions").includes(`RP_00_One_${hex(P1)}.rps`)
      && !names(R2, "Rhythm/00_Alpha/Sessions").includes("01_Two.ncs"), [names(R2, "Rhythm/00_Alpha/Sessions"), names(R2, "Rhythm/05_Beta/Sessions")]);
check("a swap deletes nothing", !at(R2, "Rhythm Plus trash"));
await RP.transfer("projects", beta, [0, 1], beta, [1, 2], {move: true});
check("move two projects down one slot in their pack (they overlap)", JSON.stringify(names(R2, "Rhythm/05_Beta/Sessions"))
      === JSON.stringify(["02_Two.ncs", "03_One.ncs", "01_One.ncs", `RP_01_One_${hex(P1)}.rps`, `RP_03_One_${hex(P1)}.rps`].sort())
      && !at(R2, "Rhythm Plus trash"), names(R2, "Rhythm/05_Beta/Sessions"));
await RP.transfer("projects", beta, [1], beta, [3], {move: true});
check("move onto a used slot: the old project and its Plus file are deleted", names(R2, "Rhythm/05_Beta/Sessions").includes("03_One.ncs")
      && !names(R2, "Rhythm/05_Beta/Sessions").includes("01_One.ncs") && !at(R2, "Rhythm Plus trash"));

// ---- samples: copy between packs, reorder inside a pack (the projects follow)
await RP.transfer("samples", alpha, [0, 1], beta, [10, 11]);
check("copy two samples to another pack", names(R2, "Rhythm/05_Beta/PCM").join() === "10_Kick.wav,11_Snare.wav" && names(R2, "Rhythm/00_Alpha/PCM").length === 3);
put(R2, "Rhythm/00_Alpha/Sessions/02_Uses.ncs", song(4, null, 2, [[0, 0], [1, 1], [2, 2]]));
alpha.drop();
let changed = await RP.transfer("samples", alpha, [0], alpha, [1], {swap: true});
let u = sess("00_Alpha", "02_Uses.ncs");
check("swap Kick and Snare: they trade numbers", RP.crc32(at(R2, "Rhythm/00_Alpha/PCM/00_Snare.wav").bytes) === RP.crc32(wav(1))
      && RP.crc32(at(R2, "Rhythm/00_Alpha/PCM/01_Kick.wav").bytes) === RP.crc32(wav(0)));
check("swap: a project's track and step flips follow the samples", u[RP.SLOT_AT] === 2 && u[0x2E4 + 5] === 1 && u[0x2E4 + 8 + 5] === 0 && u[0x2E4 + 16 + 5] === 2,
      [u[RP.SLOT_AT], u[0x2E4 + 5], u[0x2E4 + 13], u[0x2E4 + 21]]);
check("swap: the projects that use them are rewritten in place", changed.includes(2) && !at(R2, "Rhythm Plus trash"), changed);
changed = await RP.transfer("samples", alpha, [2], alpha, [7], {move: true});
u = sess("00_Alpha", "02_Uses.ncs");
check("move Hat from 3 to 8: the file moves and the projects point at 8", names(R2, "Rhythm/00_Alpha/PCM").includes("07_Hat.wav") && u[RP.SLOT_AT] === 7
      && u[0x2E4 + 16 + 5] === 7, [u[RP.SLOT_AT], u[0x2E4 + 21]]);
changed = await RP.transfer("samples", alpha, [7], alpha, [0], {move: true});
u = sess("00_Alpha", "02_Uses.ncs");
check("move onto a used slot: the old sample is deleted; what used it points at the freed slot", names(R2, "Rhythm/00_Alpha/PCM").includes("00_Hat.wav")
      && !names(R2, "Rhythm/00_Alpha/PCM").includes("00_Snare.wav") && u[RP.SLOT_AT] === 0 && u[0x2E4 + 8 + 5] === 7 && u[0x2E4 + 5] === 1,
      [u[RP.SLOT_AT], u[0x2E4 + 5], u[0x2E4 + 13]]);
await RP.transfer("samples", alpha, [1], beta, [20], {move: true});
check("move a sample to another pack: no project is rewritten", names(R2, "Rhythm/05_Beta/PCM").includes("20_Kick.wav") && !names(R2, "Rhythm/00_Alpha/PCM").includes("01_Kick.wav"));

// ---- rename and delete
await RP.renameItem("samples", beta, 10, "Big Kick");
check("rename a sample", names(R2, "Rhythm/05_Beta/PCM").includes("10_Big Kick.wav") && !names(R2, "Rhythm/05_Beta/PCM").includes("10_Kick.wav"));
threw = null; try { await RP.renameItem("samples", beta, 10, "X".repeat(30)); } catch (e) { threw = e.message; }
check("a sample name too long for the card", threw === "rename-long" && RP.nameMax(10, "sample") === 23 && RP.nameMax(100, "sample") === 22, threw);
threw = null; try { await RP.renameItem("samples", beta, 11, "Big Kick"); } catch (e) { threw = e.message; }
check("two samples may share a name (the number differs)", threw === null, threw);
await RP.renameItem("projects", beta, 3, "Renamed");
check("rename a project through the slot call: the Plus file too", names(R2, "Rhythm/05_Beta/Sessions").includes("03_Renamed.ncs")
      && names(R2, "Rhythm/05_Beta/Sessions").includes(`RP_03_Renamed_${hex(P1)}.rps`));
const beta2 = await RP.renamePack(beta, "Gamma Pack");
check("rename a pack: the folder takes the new name with all its files", names(R2, "Rhythm").includes("05_Gamma Pack") && !names(R2, "Rhythm").includes("05_Beta")
      && names(R2, "Rhythm/05_Gamma Pack/Sessions").includes(`RP_03_Renamed_${hex(P1)}.rps`) && beta2.name === "Gamma Pack" && !names(R2, "Rhythm").includes("~rp-rename.tmp"));
threw = null; try { await RP.renamePack(beta2, "Alpha"); } catch (e) { threw = e.message; }
check("a pack name the card does not take", threw === null || threw === "rename-taken", threw);
threw = null; try { await RP.renamePack(c2.pack(0), "a/b"); } catch (e) { threw = e.message; }
check("a pack name with a slash: refused", threw === "rename-char", threw);
await RP.deleteItems("samples", beta2, [10, 11]);
check("delete two samples: they are deleted", !names(R2, "Rhythm/05_Gamma Pack/PCM").includes("10_Big Kick.wav") && !names(R2, "Rhythm/05_Gamma Pack/PCM").includes("11_Big Kick.wav"));

// ---- files from the computer
const unit = RP.wavEncode(Float32Array.from({length: 480}, (_, i) => Math.sin(i / 10)));
const info = RP.wavInfo(unit);
check("the unit's WAV: 48 kHz, mono, 16 bits, data at 44", RP.unitWav(info) && info.at === 44 && info.data === 960 && unit.length === 1004, info);
check("a stereo WAV is not the unit's format", !RP.unitWav({...info, channels: 2}));
check("a computer file name, made safe", RP.fileName("07_My Loop (é).wav", "samples") === "My Loop (_)" && RP.fileName("x".repeat(40) + ".wav", "samples").length === 22);
check("free runs of slots", JSON.stringify(RP.freeRun([{slot: 0}, {slot: 2}], 128, 2)) === "[3,4]" && RP.freeRun([], 4, 2, 3) === null);
await RP.putFiles("samples", c2.pack(0), [{name: "Drop A", bytes: unit}, {name: "Drop B", bytes: unit}], [40, 41]);
check("dropped samples land in their slots", names(R2, "Rhythm/00_Alpha/PCM").includes("40_Drop A.wav") && names(R2, "Rhythm/00_Alpha/PCM").includes("41_Drop B.wav"));
const drop = song(9, P2, 0, []);
check("a dropped project's key", RP.projectKey(drop) === RP.crc32(P2) && RP.projectKey(song(9, null, 0, [])) === null && RP.projectProblem(drop) === null
      && RP.projectProblem(new Uint8Array(10)) === "proj-size");
await RP.putFiles("projects", c2.pack(0), [{name: "Dropped", bytes: drop, key: RP.crc32(P2), plus: P2}], [30]);
check("a dropped project with its Plus file", names(R2, "Rhythm/00_Alpha/Sessions").includes("30_Dropped.ncs")
      && names(R2, "Rhythm/00_Alpha/Sessions").includes(`RP_30_Dropped_${hex(P2)}.rps`) && (await RP.project(c2.pack(0), 30)).state === "here");
}

// ================================================================ the unit over USB: the folder calls on a fake unit
{
class FakeUnit {                                            // the Device calls the folders use, on an in-memory card
  constructor() { this.packs_ = [{P: 1, name: "00_Usb Pack"}, {P: 4, name: "03_Other"}]; this.files = new Map(); this.calls = []; }
  key(T, P, I) { return `${T}/${P}/${I}`; }
  async packs() { return this.packs_.map(x => ({...x})); }
  async items(T, P) { return [...this.files].filter(([k]) => k.startsWith(`${T}/${P}/`)).map(([k, v]) => ({I: +k.split("/")[2], name: v.name})); }
  async size(T, P, I) { return this.files.get(this.key(T, P, I)).bytes.length; }
  async read(T, P, I) { this.calls.push("read"); return this.files.get(this.key(T, P, I)).bytes.slice(); }
  async write(T, P, I, data) { this.calls.push("write"); this.files.set(this.key(T, P, I), {name: RP.pad2(I) + (T === 3 ? "_SESSION.ncs" : "_PCM.wav"), bytes: data.slice()}); }
  name(n) { if (n.length > 31) throw new Error("device-name"); return n; }
  async rename(T, P, I, name) { this.calls.push("rename"); this.files.get(this.key(T, P, I)).name = name; }
  async renamePack(P, name) { this.packs_.find(x => x.P === P).name = name; }
  async del(T, P, I) { this.calls.push("del"); this.files.delete(this.key(T, P, I)); }
}
const unitDev = new FakeUnit();
unitDev.files.set("3/1/0", {name: "00_Song.ncs", bytes: project(1, plusFile(1))});
unitDev.files.set("5/1/0", {name: "00_Kick.wav", bytes: Uint8Array.of(1, 2, 3)});
unitDev.files.set("5/1/1", {name: "01_Snare.wav", bytes: Uint8Array.of(4, 5, 6)});
const usb = await RP.Card.open(new RP.DevRoot(unitDev));
check("USB: the unit's packs, as folders", usb.device && usb.packs.map(p => p.folder).join() === "00_Usb Pack,03_Other");
const up = usb.pack(0), other = usb.pack(3);
const ps = await RP.projects(up);
check("USB: a project's Plus state is not read (it would read the whole file)", ps.length === 1 && ps[0].state === "usb" && !unitDev.calls.includes("read"));
check("USB: samples by slot", (await RP.samples(up)).map(x => x.slot + ":" + x.name).join() === "0:Kick,1:Snare");
await RP.transfer("samples", up, [0], other, [5]);
check("USB: copy a sample to another pack: written, then given its name", unitDev.files.get("5/4/5").name === "05_Kick.wav");
await RP.transfer("samples", up, [0], up, [1], {swap: true});
check("USB: swap two samples", unitDev.files.get("5/1/0").name === "00_Snare.wav" && unitDev.files.get("5/1/1").name === "01_Kick.wav"
      && unitDev.files.get("3/1/0").bytes !== undefined);
await RP.renameItem("samples", up, 0, "Snare 2");
check("USB: rename a sample with the unit's own rename", unitDev.files.get("5/1/0").name === "00_Snare 2.wav");
await RP.renamePack(up, "Renamed");
check("USB: rename a pack", unitDev.packs_[0].name === "00_Renamed");
await usb.scan();
await RP.deleteItems("samples", usb.pack(0), [1]);
check("USB: delete a sample", !unitDev.files.has("5/1/1"));

// ---- the unit over USB with Rhythm Plus's file commands: Plus files go with their projects
class PlusUnit extends FakeUnit {                            // also the Plus file commands, on a per-folder map (dir 0 = RP_AUTO)
  constructor() { super(); this.plusOk = true; this.plus = new Map([[0, new Map()], [1, new Map()], [4, new Map()]]); this.order = []; }
  async plusFolder(dir) { const x = this.packs_.find(p => p.P === dir); return x ? "1:/Rhythm/" + (this.folderOf?.(x) ?? x.name) + "/Sessions/" : "1:/RP_AUTO/"; }
  async plusList(dir) { return [...this.plus.get(dir)].map(([name, b]) => ({name, size: b.length})); }
  async plusRead(dir, name) { const b = this.plus.get(dir).get(name); if (!b) throw new Error("gone"); return b.slice(); }
  async plusWrite(dir, name, data) { this.order.push("plus " + name); this.plus.get(dir).set(name, data.slice()); }
  async plusDel(dir, name) { this.order.push("plusdel " + name); this.plus.get(dir).delete(name); }
  async plusRename(dir, name, to) { const m = this.plus.get(dir); m.set(to, m.get(name)); m.delete(name); }
  async write(T, P, I, data) { this.order.push("write " + T + "/" + P + "/" + I); return super.write(T, P, I, data); }
  async del(T, P, I) { this.order.push("del " + T + "/" + P + "/" + I); return super.del(T, P, I); }
}
const dev = new PlusUnit(), A = plusFile(41), B = plusFile(42), C = plusFile(43);
dev.files.set("3/1/0", {name: "00_Song.ncs", bytes: project(1, A)});
dev.plus.get(1).set(`RP_00_Song_${hex(A)}.rps`, A);
dev.files.set("3/1/1", {name: "01_Auto.ncs", bytes: project(2, B)});
dev.plus.get(0).set(`${hex(B)}.RPS`, B);
dev.files.set("3/1/2", {name: "02_Lost.ncs", bytes: project(3, C)});
dev.files.set("3/1/3", {name: "03_Plain.ncs", bytes: project(4, null)});
const c = await RP.Card.open(new RP.DevRoot(dev));
const P0 = c.pack(0), P3 = c.pack(3);
const st = await RP.projects(P0);
check("USB+: a slot with a Plus file shows it, from its name alone (no project read)",
      st.map(x => x.slot + ":" + x.state).join() === "0:usbplus,1:usb,2:usb,3:usb" && !dev.calls.includes("read"), st.map(x => x.state));
await RP.transfer("projects", P0, [0], P3, [5]);
check("USB+: copy to another pack writes the project and its Plus file under the unit's name for the new slot",
      dev.files.get("3/4/5").name === "05_Song.ncs" && sameB(dev.plus.get(4).get(`RP_05_Song_${hex(A)}.rps`), A)
      && dev.plus.get(1).has(`RP_00_Song_${hex(A)}.rps`));
await RP.transfer("projects", P0, [1], P3, [6]);
check("USB+: a project whose Plus file is only in RP_AUTO takes it from there", sameB(dev.plus.get(4).get(`RP_06_Auto_${hex(B)}.rps`), B));
let err = null; try { await RP.transfer("projects", P0, [2], P3, [7]); } catch (e) { err = e.message; }
check("USB+: a project whose Plus file is nowhere is refused, nothing written", err === "plus-missing" && !dev.files.has("3/4/7"));
await RP.transfer("projects", P0, [3], P3, [8]);
check("USB+: a project with no Plus settings copies alone", dev.files.get("3/4/8").name === "08_Plain.ncs" && dev.plus.get(4).size === 2);
await RP.transfer("projects", P3, [5], P3, [9], {move: true});
check("USB+: move inside a pack: the Plus file takes the new slot's name, the old one is gone",
      dev.files.get("3/4/9").name === "09_Song.ncs" && !dev.files.has("3/4/5")
      && dev.plus.get(4).has(`RP_09_Song_${hex(A)}.rps`) && !dev.plus.get(4).has(`RP_05_Song_${hex(A)}.rps`));
await RP.renameItem("projects", P3, 9, "Tune");
check("USB+: rename a project renames its Plus file", dev.files.get("3/4/9").name === "09_Tune.ncs" && dev.plus.get(4).has(`RP_09_Tune_${hex(A)}.rps`));
dev.order.length = 0;
await RP.deleteItems("projects", P3, [9]);
check("USB+: delete removes the Plus file first, then the project (the unit would move a Plus file left behind to RP_AUTO)",
      dev.order.join() === `plusdel RP_09_Tune_${hex(A)}.rps,del 3/4/9` && !dev.plus.get(4).has(`RP_09_Tune_${hex(A)}.rps`));
dev.order.length = 0;
await RP.transfer("projects", P3, [6], P3, [8], {swap: true});
check("USB+: swap two projects: each Plus file follows its project",
      dev.files.get("3/4/8").name === "08_Auto.ncs" && dev.plus.get(4).has(`RP_08_Auto_${hex(B)}.rps`) && dev.files.get("3/4/6").name === "06_Plain.ncs"
      && !dev.plus.get(4).has(`RP_06_Auto_${hex(B)}.rps`));
dev.files.set("6/4/0", {name: "00_GRIDFX.ncg", bytes: new Uint8Array(112).fill(7)});
dev.files.set("7/4/0", {name: "00_META.ncm", bytes: Uint8Array.of(9, 0x1b)});
const dest = new Dir("Backups");
const devItems = dev.items.bind(dev);
dev.items = async (T, P) => { if (T === 6 && P === 1) throw new Error("device-status-5"); return devItems(T, P); };
await RP.backup(c, dest);
dev.items = devItems;
const bk = [...dest.kids.values()][0];
check("USB: a backup over USB holds each pack's Grid FX and meta files; a pack with no GridFx folder is no error",
      sameB(bk.find("Rhythm")?.find("03_Other")?.find("GridFx")?.find("00_GRIDFX.ncg")?.bytes ?? new Uint8Array(0), new Uint8Array(112).fill(7))
      && sameB(bk.find("Rhythm")?.find("03_Other")?.find("meta")?.find("00_META.ncm")?.bytes ?? new Uint8Array(0), Uint8Array.of(9, 0x1b)));
check("USB+: a backup over USB holds the Plus files and RP_AUTO",
      !!bk && !!bk.find("Rhythm")?.find("03_Other")?.find("Sessions")?.find(`RP_08_Auto_${hex(B)}.rps`) && !!bk.find("RP_AUTO")?.find(`${hex(B)}.RPS`));
const wrong = new PlusUnit(); wrong.folderOf = x => x.name === "00_Usb Pack" ? "01_Else" : x.name;
wrong.files.set("3/1/0", {name: "00_Song.ncs", bytes: project(1, A)});
const cw = await RP.Card.open(new RP.DevRoot(wrong));
err = null; try { await RP.projects(cw.pack(0)); } catch (e) { err = e.message; }
check("USB+: a pack number that the unit maps to another folder is refused", err === "device-plus-pack");

// A0260+: the unit reads a project's Plus bytes itself, so the Plus file check runs over USB.
class MetaUnit extends PlusUnit {
  constructor() { super(); this.metaOk = true; }
  async plusMeta(dir, slot) {
    const f = this.files.get(`3/${dir}/${slot}`);
    return f ? {size: f.bytes.length, m: f.bytes.slice(RP.META, RP.META + 20), head: this.names ? f.bytes.slice(0, 48) : null, colour: this.colours || this.names ? f.bytes[12] : null} : null;
  }
}
const mn = new MetaUnit(), pn = project(5, null); pn.set(new TextEncoder().encode("Old Name"), 16);
mn.files.set("3/1/0", {name: "00_New Name.ncs", bytes: pn});
const mnPlan = async () => RP.tidyPlan(await RP.Card.open(new RP.DevRoot(mn)));
const old3 = await mnPlan();
mn.names = true;
const plan3 = await mnPlan();
check("names over USB: older firmware cannot read them and Check says so; version 3 lists the project",
      old3.namesUnread && !old3.names.length && !plan3.namesUnread && plan3.names.length === 1 && plan3.names[0].p.inner === "Old Name");
await RP.tidyApply(await RP.Card.open(new RP.DevRoot(mn)), plan3);
check("names over USB: Fix writes the file name inside the project",
      new TextDecoder().decode(mn.files.get("3/1/0").bytes.subarray(16, 48)) === "New Name".padEnd(32));
const mc = new MetaUnit(), pc = project(5, null); pc[12] = 10;
mc.files.set("3/1/0", {name: "00_Blue.ncs", bytes: pc});
const mcPack = async () => (await RP.Card.open(new RP.DevRoot(mc))).pack(0);
const noCol = (await RP.projects(await mcPack()))[0].colour;
mc.colours = true;
check("colours over USB: Plus version 2 gives each project's colour in the list; older firmware gives none",
      noCol === null && (await RP.projects(await mcPack()))[0].colour === 10, noCol);
const mu = new MetaUnit(), M1 = plusFile(51), M2 = plusFile(52);
mu.files.set("3/1/0", {name: "00_Here.ncs", bytes: project(5, M1)});
mu.plus.get(1).set(`RP_00_Here_${hex(M1)}.rps`, M1);
mu.plus.get(1).set(`RP_00_${hex(M1)}.rps`, M1);
mu.files.set("3/1/1", {name: "01_Auto.ncs", bytes: project(6, M2)});
mu.plus.get(0).set(`${hex(M2)}.RPS`, M2);
mu.plus.get(0).set(`${hex(M1)}.RPS`, M1);
mu.plus.get(0).set(`0BADF00D.RPS`, plusFile(54));
mu.files.set("3/1/2", {name: "02_Plain.ncs", bytes: project(7, null)});
const cm = await RP.Card.open(new RP.DevRoot(mu));
const sm = await RP.projects(cm.pack(0));
check("USB check: the project's state from the unit's own read, no whole project read",
      sm.map(x => x.slot + ":" + x.state).join() === "0:here,1:auto,2:stock" && !mu.calls.includes("read"), sm.map(x => x.state));
const plan = await RP.tidyPlan(cm);
check("USB check: the plan finds the RP_AUTO-only project, the extra file, the RP_AUTO copy no longer needed and the orphan",
      plan.fix.length === 1 && plan.extra.length === 1 && plan.dup.length === 1 && plan.orphan.length === 1, JSON.stringify([plan.fix.length, plan.extra.length, plan.dup.length, plan.orphan.length]));
await RP.tidyApply(cm, plan, {orphans: true});
check("USB fix: the Plus file next to its project under the unit's name; the extras deleted",
      sameB(mu.plus.get(1).get(`RP_01_Auto_${hex(M2)}.rps`), M2) && !mu.plus.get(1).has(`RP_00_${hex(M1)}.rps`)
      && mu.plus.get(1).has(`RP_00_Here_${hex(M1)}.rps`) && mu.plus.get(0).size === 0, [...mu.plus.get(1).keys(), ...mu.plus.get(0).keys()].join());
const again = await RP.tidyPlan(cm);
check("USB fix: a second check finds nothing", !again.fix.length && !again.extra.length && !again.dup.length && !again.orphan.length);
const mu2 = new MetaUnit(), M3 = plusFile(55), M4 = plusFile(56);
mu2.files.set("3/1/0", {name: "00_Unread.ncs", bytes: project(8, M3)});
mu2.plus.get(0).set(`${hex(M3)}.RPS`, M3);
mu2.plus.get(0).set(`${hex(M4)}.RPS`, M4);
const read2 = mu2.plusMeta;
mu2.plusMeta = async (dir, slot) => { if (slot === 0) throw new Error("device-plus-1"); return read2.call(mu2, dir, slot); };
const unsure = await RP.tidyPlan(await RP.Card.open(new RP.DevRoot(mu2)));
check("USB check: with a project the unit could not read, no RP_AUTO file counts as unused", unsure.orphan.length === 0, unsure.orphan);
mu2.plusMeta = read2;
const sure = await RP.tidyPlan(await RP.Card.open(new RP.DevRoot(mu2)));
check("USB check: with every project read, only the RP_AUTO file no project uses counts as unused", sure.orphan.length === 1, sure.orphan);
}

// ---- the Plus file commands' bytes, against a model of the firmware's replies
{
const disk = new Map(), dirs = {0: "1:/RP_AUTO/", 1: "1:/Rhythm/00_Usb Pack/Sessions/"};
let busy = 1, sent = 0;
const nib = v => [28, 24, 20, 16, 12, 8, 4, 0].map(k => (v >>> k) & 15), g32 = (m, o) => { let v = 0; for (let i = 0; i < 8; i++) v = v * 16 + (m[o + i] & 15); return v >>> 0; };
const tx = {onmessage: null, send(m) {
  sent++;
  if (m[0] !== 0xF0 || m[1] !== 0x7D) return;
  if (m.length !== 232 || m[231] !== 0xF7) throw new Error("not padded");
  const cmd = m[4], dir = m[6], L = m[7], name = String.fromCharCode(...m.subarray(8, 8 + L)), a = 8 + L, key = dir + "/" + name;
  let st = 0, out = [];
  if (busy && cmd === 0x21) { busy--; st = 0x102; }
  else if (cmd === 0x20) out = [...nib(1), dirs[dir].length, ...[...dirs[dir]].map(ch => ch.charCodeAt(0))];
  else if (cmd === 0x21 && dir === 9) st = 5;
  else if (cmd === 0x21) { const k = [...disk.keys()].filter(x => x.startsWith(dir + "/"))[g32(m, a)]; if (!k) st = 0x110; else { const nm = k.slice(2); out = [...nib(disk.get(k).length), nm.length, ...[...nm].map(ch => ch.charCodeAt(0))]; } }
  else if (cmd === 0x22) { const b = disk.get(key); if (!b) st = 4; else { const off = g32(m, a), part = b.subarray(off, off + Math.min(64, m[a + 8])); out = [...nib(b.length), ...nib(part.length), ...[...part].flatMap(v => [v >> 4, v & 15])]; } }
  else if (cmd === 0x23) { const off = g32(m, a), n = m[a + 8], part = Uint8Array.from({length: n}, (_, i) => (m[a + 9 + 2 * i] << 4) | m[a + 10 + 2 * i]);
    const b = off ? disk.get(key) : new Uint8Array(0); if (!b || b.length !== off) st = 0x103; else { const nb = new Uint8Array(off + n); nb.set(b); nb.set(part, off); disk.set(key, nb); } }
  else if (cmd === 0x24) st = disk.delete(key) ? 0 : 4;
  else if (cmd === 0x25) { const b = disk.get(key); if (!b) st = 4; else out = [...nib(b.length), ...nib(RP.crc32(b))]; }
  else if (cmd === 0x26) { const to = String.fromCharCode(...m.subarray(a + 1, a + 1 + m[a])); disk.set(dir + "/" + to, disk.get(key)); disk.delete(key); }
  const r = Uint8Array.from([0xF0, 0x7D, 0x43, 0x54, cmd | 0x40, m[5], ...nib(st), ...out, 0xF7]);
  setTimeout(() => tx.onmessage(r), 0);
}};
const d = new RP.Device(tx);
check("bytes: the unit says it has the Plus file commands", await d.plusHello() === true && d.plusOk);
check("bytes: the folder of a pack number", await d.plusFolder(1) === dirs[1]);
const body = Uint8Array.from({length: 150}, (_, i) => (i * 37 + 11) & 255), nm = `RP_05_Song_${RP.hex8(RP.crc32(body))}.rps`;
await d.plusWrite(1, nm, body);
check("bytes: a write in 64-byte chunks makes the file, then its CRC is checked", sameB(disk.get("1/" + nm), body));
const ls = await d.plusList(1);
check("bytes: list (after one busy answer, asked again)", ls.length === 1 && ls[0].name === nm && ls[0].size === 150 && busy === 0);
check("bytes: a pack with no Sessions folder lists no Plus files", (await d.plusList(9)).length === 0);
check("bytes: read back", sameB(await d.plusRead(1, nm), body));
await d.plusRename(1, nm, "RP_06_Song_" + nm.slice(11));
await d.plusDel(1, "RP_06_Song_" + nm.slice(11));
check("bytes: rename, then delete", disk.size === 0);
const quiet = new RP.Device({onmessage: null, send() {}});
check("bytes: firmware without the commands: no answer means none", await quiet.plusHello() === false);
}

{
const src = new Dir("Big"); for (let i = 0; i < 5; i++) put(src, `f${i}.bin`, Uint8Array.of(i));
const dst = new Dir("Copy"); let n = 0, err = null;
RP.go();
try { await RP.backup ? await (async () => { for (const [name, h] of await RP.entries(src)) { await RP.writeFile(dst, name, await RP.readHandle(h)); if (++n === 2) RP.stop(); } })() : 0; } catch (e) { err = e.message; }
RP.go();
check("Cancel stops before the next file; what was copied stays", err === "cancelled" && dst.kids.size === 2, {err, size: dst.kids.size});
}

// ---- a Components pack file (.circuitrhythmpack): a zip, read and written into an empty pack slot
{
const deflate = async b => new Uint8Array(await new Response(new Blob([b]).stream().pipeThrough(new CompressionStream("deflate-raw"))).arrayBuffer());
async function zip(entries) {                               // [[name, bytes, deflated]] -> a zip, as Components writes one
  const enc = new TextEncoder(), parts = [], dir = []; let off = 0;
  const le = (n, k) => Array.from({length: k}, (_, i) => (n >>> (8 * i)) & 255);
  for (const [name, b, z] of entries) {
    const nm = enc.encode(name), data = z ? await deflate(b) : b, crc = RP.crc32(b), m = z ? 8 : 0;
    const head = [...le(0x04034B50, 4), 10, 0, 0, 0, ...le(m, 2), 0, 0, 0, 0, ...le(crc, 4), ...le(data.length, 4), ...le(b.length, 4), ...le(nm.length, 2), 0, 0];
    parts.push(Uint8Array.from(head), nm, data);
    dir.push(Uint8Array.from([...le(0x02014B50, 4), 20, 0, 10, 0, 0, 0, ...le(m, 2), 0, 0, 0, 0, ...le(crc, 4), ...le(data.length, 4), ...le(b.length, 4),
      ...le(nm.length, 2), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ...le(off, 4)]), nm);
    off += head.length + nm.length + data.length;
  }
  const size = dir.reduce((s, x) => s + x.length, 0);
  const end = Uint8Array.from([...le(0x06054B50, 4), 0, 0, 0, 0, ...le(entries.length, 2), ...le(entries.length, 2), ...le(size, 4), ...le(off, 4), 0, 0]);
  return new Uint8Array(await new Blob([...parts, ...dir, end]).arrayBuffer());
}
const fx = Array.from({length: 16}, (_, i) => Uint8Array.of(i >> 2, i, 0, 0, 0, 0, 0));
const wav = n => Uint8Array.from({length: 60}, (_, i) => (i * n) & 255);
const index = {name: "London Test", product: "circuit-rhythm", version: "2.0",
  projects: [{name: "User Session", url: "projects/project_0.ncs"}, {name: "", url: "projects/project_1.ncs"}],
  samples: [{name: "Kick: Hard", url: "samples/sample_0.wav"}, {name: "Snare", url: "samples/sample_1.wav"}, {name: "", url: "samples/sample_2.wav"}],
  gridEffects: fx.map((_, i) => ({effectType: 0, url: `grid_effects/grid_effect_${i}.grideffect`}))};
const blank = project(12, null); blank.set([0x49, 0x4E, 0x49, 0x54]);        // "INIT": a blank project, as Components packs hold
const pkFile = await zip([["projects/", new Uint8Array(0)], ["index.json", new TextEncoder().encode(JSON.stringify(index)), true],
  ["projects/project_0.ncs", project(11, null), true], ["projects/project_1.ncs", blank, true],
  ["samples/sample_0.wav", wav(3), true], ["samples/sample_1.wav", wav(5), false],
  ...fx.map((b, i) => [`grid_effects/grid_effect_${i}.grideffect`, b, true])]);
const pk = await RP.readPack(pkFile);
check("pack file: name, projects with safe names (the blank one left out), samples, the 16 Grid FX as one file",
      pk.name === "London Test" && pk.projects.map(x => x.slot + ":" + x.name).join() === "0:User Session" && pk.blank === 1
      && pk.samples.map(x => x.slot + ":" + x.name).join() === "0:Kick_ Hard,1:Snare" && sameB(pk.gridfx, Uint8Array.from(fx.flatMap(b => [...b]))),
      [pk.name, pk.projects.map(x => x.name), pk.samples.map(x => x.name)]);
const sd = new Dir("SD2");
put(sd, "Rhythm/00_First/Sessions/00_A.ncs", project(1, null));
const c2 = await RP.Card.open(sd);
const made = await RP.loadPack(c2, 4, pk.name, pk);
check("load pack: the pack folder as the unit lays it out",
      made && made.slot === 4 && names(sd, "Rhythm").join() === "00_First,04_London Test"
      && names(sd, "Rhythm/04_London Test/Sessions").join() === "00_User Session.ncs"
      && names(sd, "Rhythm/04_London Test/PCM").join() === "00_Kick_ Hard.wav,01_Snare.wav"
      && sameB(at(sd, "Rhythm/04_London Test/GridFx/00_GRIDFX.ncg").bytes, pk.gridfx) && sameB(at(sd, "Rhythm/04_London Test/meta/00_META.ncm").bytes, Uint8Array.of(0, 0))
      && sameB(at(sd, "Rhythm/04_London Test/PCM/01_Snare.wav").bytes, wav(5)), names(sd, "Rhythm/04_London Test/PCM"));
let e2 = null; try { await RP.loadPack(c2, 0, "Other", pk); } catch (e) { e2 = e.message; }
check("load pack: a used pack slot is refused", e2 === "pack-used", e2);
e2 = null; try { await RP.readPack(await zip([["index.json", new TextEncoder().encode(JSON.stringify({...index, product: "circuit-tracks"}))]])); } catch (e) { e2 = e.message; }
check("pack file: a pack for another product is refused", e2 === "pack-product", e2);
const broken = pkFile.slice(), snare = wav(5);
const sAt = broken.findIndex((_, i) => snare.every((v, k) => broken[i + k] === v));
broken[sAt + 10] ^= 0xFF;                                    // inside the stored sample's data: its CRC no longer matches
e2 = null; try { await RP.readPack(broken); } catch (e) { e2 = e.message; }
check("pack file: a damaged file is refused", e2 === "pack-bad", e2);
e2 = null; try { await RP.readPack(await zip([["index.json", new TextEncoder().encode(JSON.stringify({...index, samples: [{name: "Lost", url: "samples/sample_9.wav"}]}))]])); } catch (e) { e2 = e.message; }
check("pack file: a named sample with no file is refused; an entry with no name and no file is an empty slot (above)", e2 === "pack-bad" && pk.samples.length === 2, e2);
const defName = {3: "SESSION.ncs", 5: "PCM.wav", 6: "GRIDFX.ncg", 7: "META.ncm"};
const ud = {                                                 // the unit over USB: it makes the pack folder, NN_PACK, at the first write
  packs_: [{P: 1, name: "00_First"}], files: new Map(), key: (T, P, I) => `${T}/${P}/${I}`,
  async packs() { return this.packs_.map(x => ({...x})); },
  async items(T, P) { return [...this.files].filter(([k]) => k.startsWith(`${T}/${P}/`)).map(([k, v]) => ({I: +k.split("/")[2], name: v.name})); },
  name(n) { if (n.length > 31) throw new Error("device-name"); return n; },
  async write(T, P, I, data) {
    if (!this.packs_.some(x => x.P === P)) this.packs_.push({P, name: RP.pad2(P - 1) + "_PACK"});
    this.files.set(this.key(T, P, I), {name: (I >= 100 ? String(I) : RP.pad2(I)) + "_" + defName[T], bytes: data.slice()});
  },
  async rename(T, P, I, name) { this.files.get(this.key(T, P, I)).name = name; },
  async size(T, P, I) { return this.files.get(this.key(T, P, I)).bytes.length; },
  async read(T, P, I) { return this.files.get(this.key(T, P, I)).bytes.slice(); },
  async renamePack(P, name) { this.packs_.find(x => x.P === P).name = name; }};
const cu = await RP.Card.open(new RP.DevRoot(ud));
const mu3 = await RP.loadPack(cu, 9, pk.name, pk);
check("load pack over USB: every file by type and slot under its name; the pack renamed",
      mu3 && mu3.folder === "09_London Test" && ud.packs_.find(x => x.P === 10).name === "09_London Test"
      && ud.files.get("3/10/0").name === "00_User Session.ncs" && !ud.files.has("3/10/1")
      && ud.files.get("5/10/0").name === "00_Kick_ Hard.wav" && sameB(ud.files.get("6/10/0").bytes, pk.gridfx) && sameB(ud.files.get("7/10/0").bytes, Uint8Array.of(0, 0)),
      [...ud.files.keys()]);
ud.delPack = async function (P) { this.calls = [...(this.calls || []), "delPack " + P]; this.packs_ = this.packs_.filter(x => x.P !== P); };
await RP.deletePack(cu, cu.pack(9));
check("delete pack over USB: the unit's whole-pack delete; the pack is gone from the list", ud.calls.join() === "delPack 10" && !cu.pack(9), ud.calls);

// delete on the card: the Plus files to RP_AUTO first, then the whole pack to the trash
const sd3 = new Dir("SD3"), K1 = plusFile(71);
put(sd3, "Rhythm/02_Old/Sessions/00_Song.ncs", project(1, K1));
put(sd3, `Rhythm/02_Old/Sessions/RP_00_Song_${hex(K1)}.rps`, K1);
put(sd3, "Rhythm/02_Old/PCM/00_Kick.wav", wav(2));
put(sd3, "Rhythm/02_Old/GridFx/00_GRIDFX.ncg", new Uint8Array(112));
put(sd3, "Rhythm/05_Keep/Sessions/00_A.ncs", project(2, null));
put(sd3, "RP_AUTO/.keep", new Uint8Array(0));
const c3 = await RP.Card.open(sd3);
await RP.deletePack(c3, c3.pack(2));
check("delete pack: its Plus file in RP_AUTO, the pack folder deleted with every file, no trash folder, the other pack kept",
      sameB(at(sd3, `RP_AUTO/${hex(K1)}.RPS`)?.bytes, K1) && names(sd3, "Rhythm").join() === "05_Keep" && !c3.pack(2) && !!c3.pack(5) && !at(sd3, "Rhythm Plus trash"),
      {rhythm: names(sd3, "Rhythm"), auto: names(sd3, "RP_AUTO")});
await RP.deletePack(c3, c3.pack(5));
await RP.loadPack(c3, 5, pk.name, pk);
check("replace a pack: delete, then load into the same slot", names(sd3, "Rhythm").join() === "05_London Test" && c3.pack(5)?.folder === "05_London Test", names(sd3, "Rhythm"));

// colours: a pack's in byte 0 of meta/00_META.ncm (byte 1 kept), a project's in byte 12 of its file
const sd4 = new Dir("SD4"), proj4 = project(3, null); proj4[12] = 8;
put(sd4, "Rhythm/00_Col/Sessions/00_Song.ncs", proj4);
put(sd4, "Rhythm/00_Col/meta/00_META.ncm", Uint8Array.of(0, 4));
put(sd4, "Rhythm/01_NoMeta/Sessions/00_X.ncs", project(4, null));
const c4 = await RP.Card.open(sd4), col4 = c4.pack(0);
check("colours: the pack's and the project's, as the unit wrote them; no meta file: none",
      await RP.packColour(col4) === 0 && (await RP.projects(col4))[0].colour === 8 && await RP.packColour(c4.pack(1)) === null);
await RP.setPackColour(col4, 8);
await RP.setPackColour(c4.pack(1), 11);
const before4 = at(sd4, "Rhythm/00_Col/Sessions/00_Song.ncs").bytes.slice();
await RP.setProjectColour(col4, 0, 10);
const after4 = at(sd4, "Rhythm/00_Col/Sessions/00_Song.ncs").bytes;
check("colours: the pack's byte 0 set, byte 1 kept; a pack with no meta file gets one; the project's byte 12 alone changes",
      sameB(at(sd4, "Rhythm/00_Col/meta/00_META.ncm").bytes, Uint8Array.of(8, 4)) && sameB(at(sd4, "Rhythm/01_NoMeta/meta/00_META.ncm").bytes, Uint8Array.of(11, 0))
      && after4[12] === 10 && after4.every((v, i) => i === 12 || v === before4[i]) && (await RP.projects(col4))[0].colour === 10);
e2 = null; try { await RP.setPackColour(col4, 14); } catch (e) { e2 = e.message; }
check("colours: only the 14 stock colours", e2 === "colour", e2);
const nameIn = b => new TextDecoder().decode(b.subarray(RP.NAME_AT, RP.NAME_AT + 32));
const beforeN = at(sd4, "Rhythm/00_Col/Sessions/00_Song.ncs").bytes.slice();
await RP.renameProject(col4, 0, "Night Drive");
const afterN = at(sd4, "Rhythm/00_Col/Sessions/00_Night Drive.ncs").bytes;
check("project rename: the file name and the name inside the file (32 bytes, padded with spaces); nothing else changes",
      nameIn(afterN) === "Night Drive".padEnd(32) && afterN.every((v, i) => (i >= RP.NAME_AT && i < RP.NAME_AT + 32) || v === beforeN[i]), nameIn(afterN));
await RP.putFiles("projects", col4, [{name: "From Disk", bytes: project(6, null)}], [5]);
check("project added from the computer: the name inside the file is its slot name",
      nameIn(at(sd4, "Rhythm/00_Col/Sessions/05_From Disk.ncs").bytes) === "From Disk".padEnd(32));
const cu2 = await RP.Card.open(new RP.DevRoot(ud)), usbPack = await RP.loadPack(cu2, 12, "Usb Col", pk);
await RP.setPackColour(usbPack, 5);
await RP.setProjectColour(usbPack, 0, 12);
await RP.renameProject(usbPack, 0, "Usb Name");
check("project rename over USB: the file renamed and written back with the name inside",
      ud.files.get(`3/${usbPack.slot + 1}/0`).name.endsWith("_Usb Name.ncs") && new TextDecoder().decode(ud.files.get(`3/${usbPack.slot + 1}/0`).bytes.subarray(16, 48)) === "Usb Name".padEnd(32));
check("colours over USB: the meta file written as type 7, the project written back with byte 12 changed",
      ud.files.get(`7/${usbPack.slot + 1}/0`).bytes[0] === 5 && ud.files.get(`3/${usbPack.slot + 1}/0`).bytes[12] === 12, [...ud.files.keys()]);
}
console.log(fails ? `${fails} FAIL` : "ALL PASS");
process.exit(fails ? 1 : 0);
