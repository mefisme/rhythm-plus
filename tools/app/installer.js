"use strict";
const PATCHES = __PATCHES__;
const STOCK_SYX = "__STOCK_SYX__", STOCK_IMG = "__STOCK_IMG__";
// [{v, kind: "stable" | "test", es, en}]; the first build is picked when the page opens.
const BUILDS = __BUILDS__;
const KIND = { stable: ["Estable", "Stable"], test: ["En desarrollo", "In development"], official: ["Oficial", "Official"], custom: ["Personalizado", "Custom"] };
const NOV = [0xF0, 0x00, 0x20, 0x29, 0x00];
const $ = id => document.getElementById(id);
let LANG = (() => { const q = new URLSearchParams(location.search).get("lang"); if (q === "es" || q === "en") return q;
  try { const s = localStorage.getItem("rp-lang"); if (s === "es" || s === "en") return s; } catch (e) {}
  return /^es\b/i.test(navigator.language || "") ? "es" : "en"; })();
const t = (es, en) => LANG === "en" ? en : es;
const log = (m, cls) => { const d = document.createElement("div"); if (cls) d.className = cls;
  d.textContent = new Date().toLocaleTimeString() + "  " + m; $("log").appendChild(d); $("log").scrollTop = 1e9; };
// Text that goes into innerHTML is escaped: a file name like "<img onerror=…>.syx" must not run script on a page with SysEx access.
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const hex = a => Array.from(a, b => b.toString(16).padStart(2, "0")).join(" ");
let midi = null, packets = null, stockImg = null, stockSyx = null, xfer = null, idPending = null, chosen = BUILDS[0].v;
let custom = null;                                       // {name, msgs}: a Circuit Rhythm .syx that is sent as it is

// ---------- the builds
const ALL = [...BUILDS, { v: "Oficial", kind: "official", es: "El firmware de Novation sin cambios. Úsalo para volver atrás.", en: "Novation’s firmware unchanged. Use it to go back." },
  { v: "Custom", kind: "custom", es: "Cualquier .syx de Circuit Rhythm. La página comprueba que es un firmware de Circuit Rhythm y que no está dañado, pero no lo que hace.",
    en: "Any Circuit Rhythm .syx. The page checks that it is a Circuit Rhythm firmware and that it is not damaged, but not what it does." }];
const isCustom = () => chosen === "Custom";
function showFileStep() {
  $("needOfficial").style.display = isCustom() ? "none" : ""; $("needCustom").style.display = isCustom() ? "" : "none";
  $("dropBig").textContent = isCustom() ? t("Suelta tu archivo .syx", "Drop your .syx file") : t("Suelta el .syx oficial", "Drop the official .syx");
  const ok = isCustom() ? !!custom : !!stockImg, name = isCustom() ? custom && custom.name : $("drop").dataset.official;
  $("drop").classList.toggle("got", ok);
  $("fileInfo").innerHTML = ok ? `<span class="ok">✔ ${esc(name)}</span>` : "";
  if (!ok) $("verInfo").textContent = "";
}
function drawBuilds() {
  $("builds").innerHTML = "";
  for (const b of ALL) {
    const el = document.createElement("label"); el.className = "build" + (b.v === chosen ? " sel" : ""); el.setAttribute("role", "radio");
    el.setAttribute("aria-checked", b.v === chosen);
    const name = b.v === "Oficial" ? t("Oficial", "Official") : b.v === "Custom" ? t("Archivo propio", "Custom file") : b.v;
    el.innerHTML = `<input type="radio" name="ver" value="${esc(b.v)}"><span class="radio"></span><span><span class="t">${esc(name)}<span class="pill p-${b.kind}">${esc(t(...KIND[b.kind]))}</span></span><span class="d">${esc(t(b.es, b.en))}</span></span>`;
    el.onclick = e => { e.preventDefault(); if (xfer || chosen === b.v) return; chosen = b.v; drawBuilds(); showFileStep(); updateAck(true); prepare(); };
    $("builds").appendChild(el);
  }
}

let midiNote = null;
function setMidiState(es, en, cls) { midiNote = [es, en, cls]; $("midiState").textContent = t(es, en); $("midiState").className = cls; $("midiLed").className = "led " + cls; }
function setLang(l) {
  LANG = l; document.documentElement.lang = l; try { localStorage.setItem("rp-lang", l); } catch (e) {}
  for (const b of document.querySelectorAll(".seg button")) b.classList.toggle("on", b.dataset.lang === l);
  drawBuilds(); showFileStep(); prepare();
  if (midiNote) setMidiState(...midiNote);
  fillPorts();
}
for (const b of document.querySelectorAll(".seg button")) b.onclick = () => setLang(b.dataset.lang);
function marks() {
  const done = [!needsAck(chosen) || $("ack").checked, !!packets, !!(midi && outPort() && inPort()), $("c4").dataset.done === "1"];
  const now = done.indexOf(false);
  for (let i = 0; i < 4; i++) {
    $("d" + (i + 1)).className = "dot" + (done[i] ? " done" : i === now ? " now" : "");
    if (i < 3) $("b" + (i + 1)).className = "bar" + (done[i] ? " done" : "");
    $("c" + (i + 1)).classList.toggle("later", now >= 0 && i > now);
  }
}

// ---------- CRC-32/MPEG-2, 7-bit blocks
const CRC_T = (() => { const t = new Uint32Array(256); for (let i = 0; i < 256; i++) { let c = i << 24;
  for (let k = 0; k < 8; k++) c = (c & 0x80000000) ? ((c << 1) ^ 0x04C11DB7) : (c << 1); t[i] = c >>> 0; } return t; })();
function crc32mpeg(u8) { let c = 0xFFFFFFFF; for (const b of u8) c = ((c << 8) ^ CRC_T[((c >>> 24) ^ b) & 0xFF]) >>> 0; return c >>> 0; }
function nib(arr) { let v = 0; for (const b of arr) { if (b > 15) throw Error("nibble"); v = v * 16 + b; } return v; }
function nibbles(v, n) { const o = []; for (let i = n - 1; i >= 0; i--) o.push(Math.floor(v / 16 ** i) % 16); return o; }
function unpackBlock(p) { if (p.length !== 37) throw Error(t("bloque de longitud ", "block of length ") + p.length);
  let bits = 0n; for (const b of p) { if (b & 0x80) throw Error(t("byte no MIDI", "not a MIDI byte")); bits = (bits << 7n) | BigInt(b); }
  bits >>= 3n; const out = new Uint8Array(32); for (let i = 31; i >= 0; i--) { out[i] = Number(bits & 0xFFn); bits >>= 8n; } return out; }
function packBlock(b) { let bits = 0n; for (const x of b) bits = (bits << 8n) | BigInt(x); bits <<= 3n;
  const o = new Array(37); for (let i = 36; i >= 0; i--) { o[i] = Number(bits & 0x7Fn); bits >>= 7n; } return o; }
function splitSyx(u) { const msgs = []; for (let i = 0; i < u.length;) { const s = u.indexOf(0xF0, i); if (s < 0) break; const e = u.indexOf(0xF7, s); if (e < 0) throw Error(t("SysEx sin terminar", "unterminated SysEx"));
  const m = u.slice(s, e + 1); for (let k = 0; k < 5; k++) if (m[k] !== NOV[k]) throw Error(t("cabecera no Novation", "not a Novation header")); msgs.push(m); i = e + 1; } return msgs; }
function decodeSyx(buf) {
  const msgs = splitSyx(new Uint8Array(buf)), cmd = msgs.map(m => m[5]);
  if (cmd[0] !== 0x71 || cmd[1] !== 0x7C || cmd[cmd.length - 1] !== 0x73 || cmd.slice(2, -1).some(c => c !== 0x72)) throw Error(t("orden de mensajes inesperado", "unexpected message order"));
  const init = msgs[0].slice(6, -1); if (init[0] !== 0x01 || init[1] !== 0x63) throw Error(t("no es un firmware de Circuit Rhythm", "not a Circuit Rhythm firmware"));
  const hdr = msgs[1].slice(6, -1); const size = nib(hdr.slice(7, 15)), crc = nib(hdr.slice(15, 23));
  const blocks = [unpackBlock(msgs[msgs.length - 1].slice(6, -1))]; for (const m of msgs.slice(2, -1)) blocks.push(unpackBlock(m.slice(6, -1)));
  const img = new Uint8Array(blocks.length * 32); blocks.forEach((b, i) => img.set(b, i * 32));
  if (size > img.length || size > 0x70000) throw Error(t("tamaño inválido", "invalid size"));
  const im = img.slice(0, size); if (crc32mpeg(im) !== crc) throw Error(t("CRC no coincide", "CRC mismatch")); return { msgs, img: im };
}
function encodeSyx(img) {                               // protocol 0x731, product 0x63
  const pad = new Uint8Array(Math.ceil(img.length / 32) * 32).fill(0xFF); pad.set(img);
  const msgs = [], H = NOV;
  msgs.push(Uint8Array.from([...H, 0x71, 0x01, 0x63, 0x00, 0x00, ...nibbles(0x731, 4), 0xF7]));
  msgs.push(Uint8Array.from([...H, 0x7C, 0x00, ...nibbles(0x731, 6), ...nibbles(img.length, 8), ...nibbles(crc32mpeg(img), 8), 0xF7]));
  for (let i = 32; i < pad.length; i += 32) msgs.push(Uint8Array.from([...H, 0x72, ...packBlock(pad.subarray(i, i + 32)), 0xF7]));
  msgs.push(Uint8Array.from([...H, 0x73, ...packBlock(pad.subarray(0, 32)), 0xF7]));
  return msgs;
}
function applyPatch(src, ops) {
  let n = 0; for (const o of ops) n += o[0] === 0 ? o[2] : atob(o[1]).length;
  const out = new Uint8Array(n); let p = 0;
  for (const o of ops) {
    if (o[0] === 0) { if (o[1] + o[2] > src.length) throw Error(t("parche fuera de rango", "patch out of range")); out.set(src.subarray(o[1], o[1] + o[2]), p); p += o[2]; }
    else { const s = atob(o[1]); for (let i = 0; i < s.length; i++) out[p++] = s.charCodeAt(i); }
  }
  return out;
}
async function sha256(buf) { const h = await crypto.subtle.digest("SHA-256", buf); return hex(new Uint8Array(h)).replace(/ /g, ""); }
function concat(msgs) { let n = 0; for (const m of msgs) n += m.length; const u = new Uint8Array(n); let p = 0; for (const m of msgs) { u.set(m, p); p += m.length; } return u; }

// ---------- the official file and the build
async function takeFile(f) {
  packets = null;
  if (isCustom()) custom = null; else { stockImg = stockSyx = null; delete $("drop").dataset.official; }
  showFileStep(); updateSend();
  if (!f) return;
  const buf = await f.arrayBuffer();
  try {
    if (isCustom()) {
      if (new Uint8Array(buf)[0] !== 0xF0) throw Error(t("no es un archivo .syx", "not a .syx file"));
      const d = decodeSyx(buf); custom = { name: f.name, msgs: d.msgs };
      log(`${f.name}: ${t("firmware de Circuit Rhythm, CRC correcto", "Circuit Rhythm firmware, CRC correct")} (${d.img.length} bytes)`);
    } else {
      const h = await sha256(buf);
      if (h === STOCK_SYX) { const d = decodeSyx(buf); stockImg = d.img; stockSyx = d.msgs; }
      else if (h === STOCK_IMG) { stockImg = new Uint8Array(buf); stockSyx = encodeSyx(stockImg); }
      else if (new Uint8Array(buf)[0] === 0xF0) { const d = decodeSyx(buf); if (await sha256(d.img) === STOCK_IMG) { stockImg = d.img; stockSyx = d.msgs; } }
      if (!stockImg) throw Error(t("no es el firmware oficial 2.0.1 (5706). Descárgalo con el enlace de arriba, o elige Archivo propio.",
        "this is not the official 2.0.1 (5706) firmware. Download it with the link above, or choose Custom file."));
      $("drop").dataset.official = f.name;
      log(t("Firmware oficial verificado", "Official firmware verified"));
    }
    showFileStep(); await prepare();
  } catch (e) { $("fileInfo").innerHTML = `<span class="bad">${esc(f.name)}: ${esc(e.message)}</span>`; }
  marks();
}
$("file").onchange = () => takeFile($("file").files[0]);
for (const ev of ["dragenter", "dragover"]) $("drop").addEventListener(ev, e => { e.preventDefault(); if (!xfer) $("drop").classList.add("over"); });
for (const ev of ["dragleave", "drop"]) $("drop").addEventListener(ev, e => { e.preventDefault(); $("drop").classList.remove("over"); });
$("drop").addEventListener("drop", e => { if (!xfer && e.dataTransfer.files[0]) takeFile(e.dataTransfer.files[0]); });
async function prepare() {
  packets = null; updateSend();
  if (isCustom()) {
    if (!custom) return;
    packets = custom.msgs;
    $("verInfo").innerHTML = `<span class="warn">${t("Firmware de Circuit Rhythm sin daños. No se puede comprobar lo que hace.", "A Circuit Rhythm firmware with no damage. What it does cannot be checked.")}</span> · ${packets.length} ${t("mensajes", "messages")}`;
    updateSend(); return;
  }
  if (!stockImg) return;
  const v = chosen;
  try {
    if (v === "Oficial") { packets = stockSyx; $("verInfo").innerHTML = `<span class="ok">✔ ${t("listo", "ready")}</span>`; updateSend(); return; }
    const P = PATCHES[v]; const img = applyPatch(stockImg, P.ops);
    const hi = await sha256(img); if (hi !== P.image_sha256) throw Error(t("la imagen parcheada no coincide con la publicada (", "the patched image does not match the published one (") + hi.slice(0, 16) + "…)");
    const msgs = encodeSyx(img); const hs = await sha256(concat(msgs)); if (hs !== P.syx_sha256) throw Error(t("el .syx no coincide con el publicado (", "the .syx does not match the published one (") + hs.slice(0, 16) + "…)");
    if (chosen !== v) return;
    packets = msgs;
    $("verInfo").innerHTML = `<span class="ok">✔ ${t("listo y verificado", "ready and verified")}</span> · SHA-256 ${hs.slice(0, 16)}…`;
    log(`${v} ${t("preparado y verificado", "prepared and verified")} (${hs.slice(0, 16)}…)`, "ok");
  } catch (e) { $("verInfo").innerHTML = `<span class="bad">${esc(e.message)}</span>`; }
  updateSend();
}

// ---------- MIDI
function closePort(p) {
  if (!p) return;
  try { if (p.type === "input") p.onmidimessage = null; } catch (e) {}
  if (p.state === "disconnected") return;
  try { if (p.type === "output" && p.clear) p.clear(); } catch (e) {}
  try { if (p.connection !== "closed") Promise.resolve(p.close()).catch(() => {}); } catch (e) {}
}
function openPorts(inp, out, ms = 6000) {
  return Promise.race([Promise.all([inp.open(), out.open()]),
    new Promise((_, rej) => setTimeout(() => rej(new Error(t("el puerto no responde (¿se está reiniciando el aparato?)", "the port does not respond (is the device restarting?)"))), ms))]);
}
function dropMidi(es, en) { releaseAll(); midi = null; for (const id of ["outSel", "inSel"]) $(id).innerHTML = "";
  $("btnId").disabled = true; setMidiState(es, en, "warn"); $("btnMidi").disabled = false; updateSend(); }
function releaseAll() {
  if (idPending) { clearTimeout(idPending.t); idPending.inp.removeEventListener("midimessage", idPending.h); idPending = null; }
  if (xfer) { clearTimeout(xfer.timer); xfer.inp.removeEventListener("midimessage", onMsg); xfer = null; }
  if (!midi) return; midi.onstatechange = null;
  for (const p of midi.inputs.values()) closePort(p); for (const p of midi.outputs.values()) closePort(p);
}
window.addEventListener("pagehide", () => { try { releaseAll(); } catch (e) {} midi = null; });
window.addEventListener("beforeunload", e => { if (xfer) { e.preventDefault(); e.returnValue = ""; return; } releaseAll(); });
$("btnMidi").onclick = async () => {
  if (midi) releaseAll();
  try { midi = await navigator.requestMIDIAccess({ sysex: true }); }
  catch (e) { setMidiState("acceso denegado: " + e.message, "access denied: " + e.message, "bad"); return; }
  midi.onstatechange = onState; fillPorts(); $("btnId").disabled = false; updateSend();
};
let portsTimer = null;
function onState(ev) {
  const p = ev.port; log(`MIDI: ${p.type} «${p.name}» ${p.state} / ${p.connection}`);
  if (p.state === "disconnected") {
    if (xfer && (p === xfer.out || p === xfer.inp)) { finish(t("el puerto del Circuit Rhythm ha desaparecido (¿se ha reiniciado o desconectado?)", "the Circuit Rhythm port has gone (restarted or disconnected?)"), "warn"); dropMidi("el aparato se está reiniciando: cuando arranque, pulsa Conectar", "the device is restarting: when it starts, press Connect"); return; }
    if (idPending && (p === idPending.out || p === idPending.inp)) idDone(t("dispositivo desconectado", "device disconnected"), "bad");
    closePort(p);
    if (/circuit rhythm/i.test(p.name || "")) { dropMidi("el Circuit Rhythm se ha desconectado: cuando esté listo, pulsa Conectar", "the Circuit Rhythm was disconnected: when it is ready, press Connect"); return; }
  }
  clearTimeout(portsTimer); portsTimer = setTimeout(() => { if (midi) fillPorts(); }, 400);
}
function score(name) { if (!/circuit rhythm/i.test(name)) return -1; if (/midi ?[23]|midiin2|midiout2|midiin3|midiout3|din|daw/i.test(name)) return 0; return 2; }
function fillPorts() {
  if (!midi) return;
  for (const [sel, map] of [[$("outSel"), midi.outputs], [$("inSel"), midi.inputs]]) {
    const prev = sel.value; sel.innerHTML = "";
    const ports = [...map.values()].sort((a, b) => score(b.name) - score(a.name));
    for (const p of ports) { const o = document.createElement("option"); o.value = p.id; o.textContent = p.name + (score(p.name) === 2 ? t("  ← recomendado", "  ← recommended") : ""); sel.appendChild(o); }
    if ([...sel.options].some(o => o.value === prev)) sel.value = prev;
  }
  const found = outPort() && score(outPort().name) === 2;
  if (found) setMidiState("Circuit Rhythm conectado", "Circuit Rhythm connected", "ok");
  else setMidiState("no se encuentra el Circuit Rhythm: revisa el cable o elige el puerto en Puertos", "Circuit Rhythm not found: check the cable or pick the port under Ports", "warn");
  updateSend();
}
const outPort = () => midi && midi.outputs.get($("outSel").value);
const inPort = () => midi && midi.inputs.get($("inSel").value);
function idDone(msg, cls) { if (!idPending) return; const { t, inp, out, h } = idPending; idPending = null;
  clearTimeout(t); inp.removeEventListener("midimessage", h); closePort(inp); closePort(out); if (msg) { $("idState").textContent = msg; $("idState").className = cls; } }
$("btnId").onclick = () => {
  const out = outPort(), inp = inPort(); if (!out || !inp || idPending || xfer) return;
  $("idState").textContent = t("esperando respuesta…", "waiting for an answer…"); $("idState").className = "";
  function h(ev) { const d = ev.data;
    if (d.length === 17 && d[0] === 0xF0 && d[1] === 0x7E && d[3] === 0x06 && d[4] === 0x02) {
      const mode = d[9] === 1 ? "firmware" : d[9] === 17 ? "bootloader" : t("modo ", "mode ") + d[9]; const build = d[14] * 128 + d[15];
      idDone(`Circuit Rhythm · ${mode} · build ${build}`, "ok"); } }
  idPending = { inp, out, h, t: setTimeout(() => idDone(t("sin respuesta", "no answer"), "bad"), 2000) };
  inp.addEventListener("midimessage", h);
  openPorts(inp, out).then(() => { if (idPending && idPending.h === h) out.send([0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7]); }).catch(e => idDone(t("no se pudo abrir el puerto: ", "could not open the port: ") + e.message, "bad"));
};
// ---------- every build but the official firmware asks for the backup tick
const needsAck = v => v !== "Oficial";
function updateAck(reset) { const need = needsAck(chosen); $("ackRow").style.display = need ? "flex" : "none"; if (reset || !need) $("ack").checked = false; }
$("ack").onchange = () => updateSend();
function updateSend() { updateAck(false); $("ack").disabled = !!xfer;
  $("btnSend").disabled = !(packets && outPort() && inPort() && !xfer && !idPending && (!needsAck(chosen) || $("ack").checked)); marks(); }

// ---------- transfer (pull protocol, as Components does)
const STATUS = { 0: ["inicio de actualización", "update started"], 1: ["esperando confirmación: PULSA PLAY en el Circuit Rhythm", "waiting for confirmation: PRESS PLAY on the Circuit Rhythm"],
  16: ["cancelado en el dispositivo", "cancelled on the device"], 17: ["se agotó el tiempo de confirmación", "the confirmation timed out"], 124: ["FALLO (composición no viable)", "FAILED (composition not viable)"],
  125: ["recibido (composición no viable)", "received (composition not viable)"], 126: ["FALLO (CRC)", "FAILED (CRC)"], 127: ["ÉXITO", "SUCCESS"] };
$("btnSend").onclick = () => {
  const name = $("outSel").selectedOptions[0].textContent, v = chosen;
  const what = v === "Oficial" ? t("el firmware oficial", "The official firmware") : v === "Custom" ? custom.name : v;
  if (!confirm(t(`Se instalará ${what} en: ${name}\n\nNo desconectes el Circuit Rhythm hasta que termine. ¿Continuar?`,
    `${what} will be installed on: ${name}\n\nDo not disconnect the Circuit Rhythm until it ends. Continue?`))) return;
  start();
};
$("btnAbort").onclick = () => finish(t("cancelado (el aparato descartará la actualización incompleta)", "cancelled (the device discards the incomplete update)"), "warn");
function start() {
  const out = outPort(), inp = inPort(); if (!out || !inp || xfer) return;
  if (idPending) idDone("", "");
  xfer = { out, inp, next: 0, last: -1, timer: null };
  $("btnSend").disabled = true; $("btnAbort").disabled = false; $("file").disabled = true; delete $("c4").dataset.done;
  $("phase").className = ""; inp.addEventListener("midimessage", onMsg);
  const me = xfer;
  openPorts(inp, out).then(() => { if (xfer !== me) return;
    log(`${t("Inicio", "Start")}: ${packets.length} ${t("mensajes", "messages")} → ${out.name}`); sendNext(); if (packets[xfer.next] && packets[xfer.next][5] === 0x7C) sendNext(); arm(25000);
  }).catch(e => finish(t("no se pudo abrir el puerto: ", "could not open the port: ") + e.message, "bad"));
}
function arm(ms) { clearTimeout(xfer.timer); xfer.timer = setTimeout(() => finish(t("tiempo de espera agotado; no se envió nada más", "timed out; nothing more was sent"), "bad"), ms); }
function sendNext() {
  const p = packets[xfer.next++]; xfer.out.send(p);
  $("prog").style.width = Math.round(100 * xfer.next / packets.length) + "%";
  if (xfer.next === packets.length) { $("phase").textContent = t("Enviado. Esperando la respuesta del aparato…", "Sent. Waiting for the device’s answer…"); arm(30000); }
}
function onMsg(ev) {
  const d = ev.data; if (!xfer || d[0] !== 0xF0) return;
  for (let k = 0; k < 5; k++) if (d[k] !== NOV[k]) return;
  if (d[5] === 0x72) {
    let n = null;
    if (d.length === 10) n = d[6] + (d[7] << 7) + (d[8] << 14);
    else if (d.length === 15) { const s = d.slice(6, 14); n = s[7] + (s[6] << 4) + (s[5] << 8); }
    if (n === null) return;
    if ((n > xfer.last || n === 0) && xfer.next < packets.length) { xfer.last = n; $("phase").textContent = t("Instalando…", "Installing…"); $("phase").className = ""; sendNext(); if (xfer.next < packets.length) arm(10000); }
  } else if (d[5] === 0x73 && d.length === 10) {
    const c = d[6]; log(`← ${t("estado", "status")} ${c}: ${STATUS[c] ? t(...STATUS[c]) : "?"}`, c === 127 ? "ok" : (c >= 124 || c === 16 || c === 17) ? "bad" : "");
    if (c === 1) { $("phase").textContent = t("Pulsa PLAY en el Circuit Rhythm para confirmar", "Press PLAY on the Circuit Rhythm to confirm"); $("phase").className = "warn"; arm(25000); }
    else if (c === 0) arm(25000);
    else if (c === 127) { $("c4").dataset.done = "1"; finish(t("Hecho. El Circuit Rhythm se reinicia e instala el firmware: espera a que arranque.", "Done. The Circuit Rhythm restarts and installs the firmware: wait until it starts."), "ok"); dropMidi("el aparato se reinicia: cuando arranque, pulsa Conectar", "the device restarts: when it has started, press Connect"); }
    else if (c === 125) arm(30000);
    else if (c === 16 || c === 17 || c === 124 || c === 126) finish(t("El aparato rechazó la actualización; el firmware actual no cambia.", "The device refused the update; the current firmware does not change."), "bad");
  }
}
function finish(msg, cls) {
  if (!xfer) return; const { inp, out } = xfer;
  clearTimeout(xfer.timer); inp.removeEventListener("midimessage", onMsg); xfer = null; closePort(inp); closePort(out);
  $("phase").textContent = msg; $("phase").className = cls; log(msg, cls);
  $("btnAbort").disabled = true; $("file").disabled = false; updateSend();
}
$("outSel").onchange = $("inSel").onchange = updateSend;
setMidiState("sin conectar", "not connected", "");
if (!navigator.requestMIDIAccess) setMidiState("este navegador no tiene Web MIDI: usa Chrome o Edge", "this browser has no Web MIDI: use Chrome or Edge", "bad");
setLang(LANG); updateAck(true); updateSend();
