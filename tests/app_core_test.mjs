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
check("copy with replace: the old project and its Plus file go to the trash", names(root, "Rhythm/26_Other Pack/Sessions").includes("03_Old.ncs")
      && !names(root, "Rhythm/26_Other Pack/Sessions").includes("03_New Name.ncs") && names(root, "Rhythm Plus trash").length === 1
      && JSON.stringify(names(root, `Rhythm Plus trash/${names(root, "Rhythm Plus trash")[0]}/26_Other Pack/Sessions`)) === JSON.stringify(["03_New Name.ncs", `RP_03_New Name_${hex(A)}.rps`].sort()));
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
const tr = names(root, "Rhythm Plus trash")[0];
check("delete: the project and its Plus file go to the trash", !names(root, "Rhythm/07_Beats/Sessions").some(n => /^12_|^RP_12_/.test(n))
      && names(root, `Rhythm Plus trash/${tr}/07_Beats/Sessions`).includes("12_Old.ncs") && names(root, `Rhythm Plus trash/${tr}/07_Beats/Sessions`).includes(`RP_12_Old_${hex(B)}.rps`));

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
const changed = await RP.tidyApply(card, plan);
check("tidy: the count of files changed (3 put next to projects, 3 RP_AUTO copies)", changed === 6, changed);
check("tidy: the RP_AUTO files go next to their projects under the unit's names", names(root, "Rhythm/07_Beats/Sessions").includes(`RP_08_Lost_${hex(D)}.rps`)
      && names(root, "Rhythm/07_Beats/Sessions").includes(`RP_30_Far_${hex(D)}.rps`) && names(root, "Rhythm/07_Beats/Sessions").includes(`RP_31_Short_${hex(B)}.rps`)
      && !names(root, "Rhythm/07_Beats/Sessions").includes(`RP_31_${hex(B)}.rps`));
check("tidy: RP_AUTO keeps only the orphan; copies went to the trash", JSON.stringify(names(root, "RP_AUTO")) === JSON.stringify([`${hex(O)}.RPS`]), names(root, "RP_AUTO"));
check("tidy: every project with a Plus file is 'here' or 'bad'", Object.values(await st(beats)).every(s => s === "here" || s === "stock"), await st(beats));
put(root, `Rhythm/07_Beats/Sessions/RP_31_${hex(B)}.rps`, B);                  // the old name again, as a restore of an older backup leaves it
card.drop();
plan = await RP.tidyPlan(card);
check("tidy plan: a project's second Plus file", plan.extra.length === 1 && plan.extra[0].name === `RP_31_${hex(B)}.rps`, plan.extra.map(x => x.name));
await RP.tidyApply(card, plan, {orphans: true});
check("tidy: the second Plus file goes to the trash; the unit's name stays", !names(root, "Rhythm/07_Beats/Sessions").includes(`RP_31_${hex(B)}.rps`)
      && names(root, "Rhythm/07_Beats/Sessions").includes(`RP_31_Short_${hex(B)}.rps`));
check("tidy with orphans: RP_AUTO is empty, the orphan is in the trash", names(root, "RP_AUTO").length === 0 && names(root, `Rhythm Plus trash/${tr}/RP_AUTO`).includes(`${hex(O)}.RPS`));

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
check("restore: the project and its Plus file are back; the twin is in the trash", RP.crc32(at(root, "Rhythm/07_Beats/Sessions/05_New Name.ncs").bytes) === RP.crc32(keep)
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
check("a swap puts nothing in the trash", !at(R2, "Rhythm Plus trash"));
await RP.transfer("projects", beta, [0, 1], beta, [1, 2], {move: true});
check("move two projects down one slot in their pack (they overlap)", JSON.stringify(names(R2, "Rhythm/05_Beta/Sessions"))
      === JSON.stringify(["02_Two.ncs", "03_One.ncs", "01_One.ncs", `RP_01_One_${hex(P1)}.rps`, `RP_03_One_${hex(P1)}.rps`].sort())
      && !at(R2, "Rhythm Plus trash"), names(R2, "Rhythm/05_Beta/Sessions"));
await RP.transfer("projects", beta, [1], beta, [3], {move: true});
check("move onto a used slot: the old project and its Plus file go to the trash", names(R2, "Rhythm/05_Beta/Sessions").includes("03_One.ncs")
      && !names(R2, "Rhythm/05_Beta/Sessions").includes("01_One.ncs") && names(R2, "Rhythm Plus trash").length === 1);

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
check("swap: the projects that use them are rewritten; the old files are kept in the trash", changed.includes(2)
      && !!at(R2, `Rhythm Plus trash/${names(R2, "Rhythm Plus trash")[0]}/00_Alpha/Sessions/02_Uses.ncs`), changed);
changed = await RP.transfer("samples", alpha, [2], alpha, [7], {move: true});
u = sess("00_Alpha", "02_Uses.ncs");
check("move Hat from 3 to 8: the file moves and the projects point at 8", names(R2, "Rhythm/00_Alpha/PCM").includes("07_Hat.wav") && u[RP.SLOT_AT] === 7
      && u[0x2E4 + 16 + 5] === 7, [u[RP.SLOT_AT], u[0x2E4 + 21]]);
changed = await RP.transfer("samples", alpha, [7], alpha, [0], {move: true});
u = sess("00_Alpha", "02_Uses.ncs");
check("move onto a used slot: the old sample goes to the trash; what used it points at the freed slot", names(R2, "Rhythm/00_Alpha/PCM").includes("00_Hat.wav")
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
check("delete two samples: they go to the trash", !names(R2, "Rhythm/05_Gamma Pack/PCM").includes("10_Big Kick.wav") && !names(R2, "Rhythm/05_Gamma Pack/PCM").includes("11_Big Kick.wav"));

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
check("USB: delete a sample (no trash over USB)", !unitDev.files.has("5/1/1"));

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
const dest = new Dir("Backups");
await RP.backup(c, dest);
const bk = [...dest.kids.values()][0];
check("USB+: a backup over USB holds the Plus files and RP_AUTO",
      !!bk && !!bk.find("Rhythm")?.find("03_Other")?.find("Sessions")?.find(`RP_08_Auto_${hex(B)}.rps`) && !!bk.find("RP_AUTO")?.find(`${hex(B)}.RPS`));
const wrong = new PlusUnit(); wrong.folderOf = x => x.name === "00_Usb Pack" ? "01_Else" : x.name;
wrong.files.set("3/1/0", {name: "00_Song.ncs", bytes: project(1, A)});
const cw = await RP.Card.open(new RP.DevRoot(wrong));
err = null; try { await RP.projects(cw.pack(0)); } catch (e) { err = e.message; }
check("USB+: a pack number that the unit maps to another folder is refused", err === "device-plus-pack");
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
console.log(fails ? `${fails} FAIL` : "ALL PASS");
process.exit(fails ? 1 : 0);
