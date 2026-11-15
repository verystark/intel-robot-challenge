// CELL 01 operator screen (ISA-101 style). Renders the state run_cell.py streams on /api/events.
// Plain DOM and SVG, no libraries. Grey when normal; colour only for alarms and abnormal states.
"use strict";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const num = (v, d = 0) => (v === null || v === undefined || Number.isNaN(Number(v)) ? "–" : Number(v).toFixed(d));
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const deg = (n) => String(n).replace(" deg", "°");
const JOINTS = ["J1 PAN", "J2 LIFT", "J3 ELBOW", "J4 WR.FLEX", "J5 WR.ROLL", "J6 GRIP"];
const STEPS = [[10, "HOME"], [20, "PICK"], [30, "SHOW"], [40, "INSPECT"], [50, "HOME"], [60, "SORT"]];
const VERDICT = { GOOD: "GOOD", DEFECTIVE: "REJECT", UNSURE: "UNSURE" };
let tab = "overview";
let last = null;
let lastMsg = 0;

// ---- size an SVG to its real pixels so lines and text stay crisp -------------------------
function canvas(id) {
  const svg = $(id);
  const W = Math.max(50, Math.round(svg.clientWidth)), H = Math.max(20, Math.round(svg.clientHeight));
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  return { svg, W, H };
}
const T = (x, y, s, o = {}) => `<text x="${x}" y="${y}" font-size="${o.size || 11}" fill="${o.fill || css("--text")}" font-family="${o.mono ? css("--mono") : css("--sans")}" font-weight="${o.bold ? 700 : 400}" text-anchor="${o.anchor || "start"}">${esc(s)}</text>`;
const L = (x1, y1, x2, y2, o = {}) => `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${o.stroke || css("--line")}" stroke-width="${o.w || 1}" ${o.dash ? `stroke-dasharray="${o.dash}"` : ""}/>`;
const R = (x, y, w, h, o = {}) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${o.fill || "none"}" stroke="${o.stroke || "none"}" stroke-width="${o.w || 1}" ${o.dash ? `stroke-dasharray="${o.dash}"` : ""}/>`;

// ---- clock and camera OSD ----------------------------------------------------------------
function pad(n) { return String(n).padStart(2, "0"); }
function tick() {
  const d = new Date();
  const stamp = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  $("clock").textContent = stamp;
  for (const o of document.querySelectorAll(".osd")) o.textContent = `${o.dataset.cam}  ${stamp}`;
  const lost = Date.now() - lastMsg > 3000;
  $("conn").textContent = lost ? "NO LINK TO CONTROLLER" : "LINK OK";
  $("conn").classList.toggle("lost", lost);
}
tick();
setInterval(tick, 500);

// ---- commands and navigation -----------------------------------------------------------
const post = (path, body) => fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : "" });
function command(c) {
  if (c === "full") { if (!document.fullscreenElement) document.documentElement.requestFullscreen().catch(() => {}); else document.exitFullscreen(); return; }
  post(`/api/${c}`);
}
function show(t) {
  tab = t;
  for (const b of document.querySelectorAll(".tab")) b.classList.toggle("on", b.dataset.tab === t);
  for (const sc of document.querySelectorAll(".screen")) sc.classList.toggle("on", sc.id === `tab-${t}`);
  $("screenName").textContent = { overview: "OVERVIEW", alarms: "ALARMS / EVENTS", trends: "TRENDS" }[t];
  history.replaceState(null, "", `#${t}`);
  if (last) render(last);
}
for (const b of document.querySelectorAll("[data-tab]")) b.addEventListener("click", () => show(b.dataset.tab));
// #alarms or #trends in the URL opens that screen (e.g. a second monitor pinned to the trends)
if (["#alarms", "#trends", "#overview"].includes(location.hash)) show(location.hash.slice(1));
for (const b of document.querySelectorAll("[data-cmd]")) b.addEventListener("click", () => command(b.dataset.cmd));
document.addEventListener("keydown", (e) => {
  const map = { F1: "resume", F2: "pause", F3: "stop", F5: "ack", F11: "full", Escape: "stop" };
  const tabs = { F6: "overview", F7: "alarms", F8: "trends" };
  if (map[e.key]) { command(map[e.key]); e.preventDefault(); }
  else if (tabs[e.key]) { show(tabs[e.key]); e.preventDefault(); }
  else if (e.key === "s" || e.key === "S") command("stop");
  else if (e.key === "r" || e.key === "R") command("resume");
  else if (e.key === " ") { command("pause"); e.preventDefault(); }
});

// ---- measured placement (newest benchmark) ---------------------------------------------
function loadBench() {
  fetch("/api/bench").then((r) => r.json()).then(renderBench).catch(() => {});
}
function renderBench(bench) {
  {
    const lines = [];
    const line = (label, rows) => {
      const ok = rows.filter((r) => !r.error && r.median_ms);
      if (!rows.length) return;
      const best = ok.length ? Math.min(...ok.map((r) => r.median_ms)) : null;
      lines.push(`<b>${esc(label)}</b> ` + rows.map((r) => {
        const v = r.error ? "n/a" : r.median_ms >= 1000 ? `${(r.median_ms / 1000).toFixed(1)} s` : `${Math.round(r.median_ms)} ms`;
        return `<span class="${r.median_ms === best ? "best" : ""}">${r.device} ${v}</span>`;
      }).join(" · "));
    };
    if (bench.anomaly) line("ANOMALIB", bench.anomaly.rows.filter((r) => r.model === "FP32"));
    if (bench.policy) for (const m of [...new Set(bench.policy.rows.map((r) => r.model))]) line(m.toUpperCase(), bench.policy.rows.filter((r) => r.model === m));
    $("placement").innerHTML = lines.length ? `MEASURED LATENCY PER CALL (fastest underlined):<br>${lines.join("<br>")}` : "";
  }
}
loadBench();
setInterval(loadBench, 60000);

// ---- event stream ----------------------------------------------------------------------
if (window.INITIAL_STATE) {
  lastMsg = Date.now(); last = window.INITIAL_STATE; render(last); tick();
  if (last.bench) renderBench(last.bench);
}
const es = new EventSource("/api/events");
es.onmessage = (ev) => { lastMsg = Date.now(); last = JSON.parse(ev.data); render(last); };

function render(s) {
  header(s);
  banner(s);
  if (tab === "overview") {
    mimic(s); sequence(s); inspection(s); vla(s); production(s); events(s, $("evRecent"), 8, false); node(s);
    $("osdLive").textContent = (s.live && s.live.age_s < 1.5 && ["SHOW", "INSPECT"].includes(s.stage))
      ? `LIVE SCORE ${num(s.live.score, 2)}${s.live.moving ? "  ARM MOVING · NOT USED" : `  ${VERDICT[s.live.label] || s.live.label}`}` : "";
  } else if (tab === "alarms") {
    events(s, $("evAll"), 200, true);
  } else {
    trends(s);
  }
}

function header(s) {
  $("mode").textContent = { SIMULATION: "SIM", LIVE: "AUTO", "INSPECT ONLY": "INSP ONLY" }[s.mode] || s.mode;
  const st = $("state");
  st.textContent = s.run_state;
  st.className = `v ${s.run_state === "STOPPED" ? "stopped" : s.run_state === "PAUSED" ? "paused" : ""}`;
  $("almCount").textContent = s.unacked;
  const prios = s.events.filter((e) => !e.acked).map((e) => e.prio);
  const box = $("almBox");
  box.className = `hbox alm ${prios.includes(1) ? "p1" : prios.includes(2) ? "p2" : ""} ${prios.length ? "blink" : ""}`;
  document.querySelector('.tab[data-tab="alarms"]').innerHTML = `ALARMS / EVENTS${s.unacked ? ` (${s.unacked})` : ""} <small>F7</small>`;
}

function banner(s) {
  const b = $("banner");
  if (!s.banner) { b.className = "banner"; b.textContent = "NO UNACKNOWLEDGED ALARMS"; return; }
  const e = s.banner;
  b.className = `banner p${e.prio}`;
  b.innerHTML = `<span>${esc(e.time)}</span><span>P${e.prio}</span><span>${esc(e.tag)}</span><span>${esc(e.msg)}</span><span class="ack">F5 ACKNOWLEDGE</span>`;
}

// ---- process mimic ---------------------------------------------------------------------
function mimic(s) {
  const { svg, W, H } = canvas("mimic");
  const ink = css("--text"), mute = css("--muted"), line = css("--line"), strong = css("--line-strong"), on = css("--on"), disp = css("--display");
  const running = s.run_state === "RUNNING";
  const st = s.stage;
  const cy = H * 0.47;
  const pick = { x: W * 0.02, w: W * 0.15 }, rob = { x: W * 0.235, w: W * 0.17 }, ins = { x: W * 0.47, w: W * 0.16 };
  const bh = Math.min(H * 0.42, 130), top = cy - bh / 2;
  const dia = { x: W * 0.725, r: Math.min(H * 0.13, 34) };
  const bin = { x: W * 0.845, w: W * 0.14, h: Math.min(H * 0.30, 92) };
  const gy = H * 0.07, ry = H * 0.93 - bin.h;
  const robotOn = running && ["PICK", "SHOW", "HOME", "SORT"].includes(st);
  const inspOn = running && ["SHOW", "INSPECT"].includes(st);
  const toBin = running && st === "SORT" || (st === "HOME" && s.verdict);
  const vgood = s.verdict === "GOOD";
  let o = "";

  const flow = (pts, active) => `<polyline points="${pts.map((p) => p.join(",")).join(" ")}" fill="none" stroke="${active ? ink : line}" stroke-width="${active ? 3 : 2}"/>` +
    (() => { const [a, b] = pts.slice(-2); const ang = Math.atan2(b[1] - a[1], b[0] - a[0]); const s1 = 7;
      return `<polygon points="${b[0]},${b[1]} ${b[0] - s1 * Math.cos(ang - 0.45)},${b[1] - s1 * Math.sin(ang - 0.45)} ${b[0] - s1 * Math.cos(ang + 0.45)},${b[1] - s1 * Math.sin(ang + 0.45)}" fill="${active ? ink : line}"/>`; })();
  const tag = (x, y, k, v, w = 150) => {
    const room = Math.max(3, Math.floor((w - 12 - k.length * 6) / 6.7));  // characters that fit beside the key
    const val = String(v).length > room ? String(v).slice(0, room - 1) + "…" : String(v);
    return R(x, y, w, 16, { fill: disp, stroke: line }) + T(x + 4, y + 12, k, { size: 9, fill: mute, bold: true }) + T(x + w - 4, y + 12, val, { mono: true, anchor: "end", size: 11 });
  };

  // flow lines
  o += flow([[pick.x + pick.w, cy], [rob.x, cy]], running && st === "PICK");
  o += flow([[rob.x + rob.w, cy], [ins.x, cy]], running && st === "SHOW");
  o += flow([[ins.x + ins.w, cy], [dia.x - dia.r, cy]], running && st === "INSPECT");
  o += flow([[dia.x, cy - dia.r], [dia.x, gy + bin.h / 2], [bin.x, gy + bin.h / 2]], toBin && vgood);
  o += flow([[dia.x, cy + dia.r], [dia.x, ry + bin.h / 2], [bin.x, ry + bin.h / 2]], toBin && !vgood && !!s.verdict);
  o += T(bin.x - 6, gy + bin.h / 2 - 5, "“…green plate.”", { size: 10, fill: toBin && vgood ? ink : mute, mono: true, anchor: "end" });
  o += T(bin.x - 6, ry + bin.h / 2 - 5, "“…orange plate.”", { size: 10, fill: toBin && !vgood && s.verdict ? ink : mute, mono: true, anchor: "end" });
  o += T(dia.x + dia.r + 5, cy - 5, "TASK → VLA", { size: 9, fill: mute, bold: true });

  // pick area (an area, so dashed)
  o += R(pick.x, top, pick.w, bh, { stroke: strong, dash: "5 4", w: 1.5 });
  o += T(pick.x + pick.w / 2, top + 16, "PICK AREA", { anchor: "middle", bold: true });
  o += T(pick.x + pick.w / 2, top + 31, "bricks at random", { anchor: "middle", size: 10, fill: mute });
  o += T(pick.x + pick.w / 2, top + 44, "positions", { anchor: "middle", size: 10, fill: mute });

  // robot
  o += R(rob.x, top, rob.w, bh, { fill: robotOn ? on : "none", stroke: strong, w: 1.5 });
  const rc = robotOn ? "#fff" : ink;
  o += T(rob.x + rob.w / 2, top + 16, "SO-101 ARM", { anchor: "middle", bold: true, fill: rc });
  const ax = rob.x + rob.w / 2 - 22, ay = top + bh - 18;
  o += `<g stroke="${rc}" stroke-width="2" fill="none"><rect x="${ax - 8}" y="${ay}" width="16" height="8"/><polyline points="${ax},${ay} ${ax + 8},${ay - 30} ${ax + 34},${ay - 38}"/><polyline points="${ax + 34},${ay - 44} ${ax + 40},${ay - 38} ${ax + 34},${ay - 32}"/></g>`;
  o += T(rob.x + rob.w / 2, top + 31, robotOn ? (["PICK", "SORT"].includes(st) ? "VLA CONTROL" : "SCRIPTED MOVE") : "IDLE", { anchor: "middle", size: 10, fill: robotOn ? "#e0e0e0" : mute });

  // inspection station
  o += R(ins.x, top, ins.w, bh, { fill: inspOn ? on : "none", stroke: strong, w: 1.5 });
  const ic = inspOn ? "#fff" : ink;
  o += T(ins.x + ins.w / 2, top + 16, "INSPECTION STN", { anchor: "middle", bold: true, fill: ic });
  const cx = ins.x + ins.w / 2, cyy = top + bh - 30;
  o += `<g stroke="${ic}" stroke-width="2" fill="none"><rect x="${cx - 16}" y="${cyy - 9}" width="24" height="18"/><polygon points="${cx + 8},${cyy - 5} ${cx + 18},${cyy - 10} ${cx + 18},${cyy + 10} ${cx + 8},${cyy + 5}"/></g>`;
  o += T(ins.x + ins.w / 2, top + 31, inspOn ? (s.step.detail || "SHOWING BRICK") : "ANOMALIB · CAM 03", { anchor: "middle", size: 10, fill: inspOn ? "#e0e0e0" : mute });

  // verdict diamond
  o += `<polygon points="${dia.x},${cy - dia.r} ${dia.x + dia.r},${cy} ${dia.x},${cy + dia.r} ${dia.x - dia.r},${cy}" fill="${s.verdict ? on : "none"}" stroke="${strong}" stroke-width="1.5"/>`;
  o += T(dia.x, cy + 4, s.verdict ? (VERDICT[s.verdict] || s.verdict) : "VERDICT", { anchor: "middle", bold: true, size: 10, fill: s.verdict ? "#fff" : ink });

  // bins with plate swatches and counts
  const binDraw = (y, name, plate, colour, count, active) => {
    let b = R(bin.x, y, bin.w, bin.h, { fill: active ? on : "none", stroke: strong, w: 1.5 });
    const c = active ? "#fff" : ink;
    b += R(bin.x + 6, y + 7, 10, 10, { fill: colour, stroke: strong });
    b += T(bin.x + 22, y + 16, name, { bold: true, fill: c });
    b += T(bin.x + 22, y + 29, plate, { size: 10, fill: active ? "#e0e0e0" : mute });
    b += T(bin.x + bin.w - 8, y + bin.h - 10, String(count).padStart(4, "0"), { mono: true, size: 22, anchor: "end", fill: c });
    return b;
  };
  o += binDraw(gy, "GOOD", "green plate", css("--good"), s.production.good, toBin && vgood);
  o += binDraw(ry, "REJECT", "orange plate", css("--reject"), s.production.reject, toBin && !vgood && !!s.verdict);

  // live tags under the blocks
  const pickModel = s.devices.pick, sortModel = s.devices.sort;
  const tagY = top + bh + 8;
  o += tag(pick.x, tagY, "POLICY", pickModel.model, Math.min(pick.w, 170));
  o += tag(pick.x, tagY + 19, "DEVICE", pickModel.device, Math.min(pick.w, 170));
  o += tag(rob.x, tagY, "STEP", s.step.no ? `${s.step.no} ${s.step.name}` : "–", rob.w);
  o += tag(rob.x, tagY + 19, "VLA LAT", s.chunk_ms.pick || s.chunk_ms.sort ? `${num(s.stage === "SORT" ? s.chunk_ms.sort : s.chunk_ms.pick || s.chunk_ms.sort)} ms` : "–", rob.w);
  const worst = s.stops.filter((x) => x.score !== null).reduce((m, x) => Math.max(m, x.score), -1);
  o += tag(ins.x, tagY, "INSP.SCORE", worst >= 0 ? num(worst, 2) : "–", ins.w);
  o += tag(ins.x, tagY + 19, "DEVICE", s.devices.anomaly, ins.w);
  o += T(rob.x, top - 8, `SORT POLICY: ${sortModel.model} · ${sortModel.device}`, { size: 10, fill: mute });

  // brick token where the brick is
  let tok = null;
  if (running && st === "PICK") tok = [pick.x + pick.w * 0.7, cy];
  else if (running && ["SHOW", "INSPECT"].includes(st)) tok = [ins.x + ins.w * 0.5, top + bh * 0.62];
  else if (toBin) tok = vgood ? [bin.x - 14, gy + bin.h / 2] : [bin.x - 14, ry + bin.h / 2];
  if (tok) o += `<rect x="${tok[0] - 6}" y="${tok[1] - 6}" width="12" height="12" fill="${ink}" stroke="#fff" stroke-width="1.5"/>`;
  svg.innerHTML = o;
}

// ---- sequence --------------------------------------------------------------------------
function sequence(s) {
  const cur = s.step.no;
  $("steps").innerHTML = STEPS.map(([n, name]) =>
    `<div class="step ${n === cur ? "on" : cur && n < cur ? "done" : ""}"><b>${n}</b>${name}</div>`).join("");
  let line = cur ? `STEP ${cur} ${s.step.name}${s.step.detail ? " · " + s.step.detail : ""} · ${num(s.stage_elapsed, 1)} s` : (s.run_state === "STARTING" ? "LOADING MODELS" : `IDLE · ${s.run_state}`);
  let bar = "";
  if (s.step.timeout_s) {
    const f = Math.min(1, s.stage_elapsed / s.step.timeout_s);
    bar = `<svg viewBox="0 0 200 12" preserveAspectRatio="none">${R(0, 2, 200, 8, { fill: css("--display"), stroke: css("--line") })}${R(0, 2, 200 * f, 8, { fill: f > 0.8 ? css("--p2") : css("--on") })}</svg><span>TIMEOUT ${s.step.timeout_s} s</span>`;
  }
  $("seqLine").innerHTML = `<span>${esc(line)}</span>${bar}`;
}

// ---- inspection faceplate ---------------------------------------------------------------
function inspection(s) {
  $("inspHead").textContent = `INSPECTION STATION · ANOMALIB PATCHCORE · OPENVINO ${s.devices.anomaly}`;
  const v = s.verdict;
  $("verdict").textContent = v ? VERDICT[v] || v : (["SHOW", "INSPECT"].includes(s.stage) ? "INSPECTING" : "—");
  $("vdSwatch").style.background = v === "GOOD" ? css("--good") : v === "DEFECTIVE" ? css("--reject") : "transparent";
  $("verdictSub").textContent = s.verdict_sub || "";
  $("task").textContent = s.sentence ? `“${s.sentence}”` : "–";

  // gauge: 0..1 with the good range shaded (normal operating range) and both limits marked
  const { svg, W, H } = canvas("gauge");
  const [lo, hi] = s.bands, x0 = 10, x1 = W - 10, X = (v2) => x0 + (x1 - x0) * Math.min(Math.max(v2, 0), 1);
  const yb = 18;
  let o = R(x0, yb, x1 - x0, 10, { fill: css("--display"), stroke: css("--line") }) + R(x0, yb, X(lo) - x0, 10, { fill: css("--range") });
  o += L(X(lo), yb - 4, X(lo), yb + 14, { stroke: css("--line-strong"), w: 1.5 }) + L(X(hi), yb - 4, X(hi), yb + 14, { stroke: css("--line-strong"), w: 1.5 });
  o += T(X(lo), yb + 25, `GOOD ≤ ${lo.toFixed(2)}`, { size: 9, anchor: "middle", fill: css("--muted") });
  o += T(X(hi), yb + 25, `REJECT ≥ ${hi.toFixed(2)}`, { size: 9, anchor: "middle", fill: css("--muted") });
  for (const t of [0, 0.5, 1]) o += T(X(t), yb + 25, t === 0.5 ? "" : t.toFixed(1), { size: 9, anchor: t === 0 ? "start" : "end", fill: css("--faint") });
  const marks = s.stops.filter((x) => x.score !== null);
  marks.forEach((m, i) => {
    const px = X(m.score);
    o += `<polygon points="${px},${yb + 10} ${px - 5},${yb + 18} ${px + 5},${yb + 18}" fill="${css("--text")}"/>`;
    o += T(px, yb - 6 - (i % 2) * 0, deg(m.name), { size: 9, anchor: "middle", mono: true });
  });
  if (s.live && s.live.age_s < 1.5 && ["SHOW", "INSPECT"].includes(s.stage)) {
    const px = X(s.live.score);
    o += `<polygon points="${px},${yb} ${px - 5},${yb - 8} ${px + 5},${yb - 8}" fill="none" stroke="${css("--text")}"/>`;
  }
  svg.innerHTML = o;

  const planned = s.stops_planned.length ? s.stops_planned : ["0 deg", "90 deg", "180 deg"];
  $("stops").innerHTML = planned.map((name, i) => {
    const st = s.stops[i];
    if (!st) {
      const why = s.early_reject && s.stops.length ? "SKIPPED (DEFECT FOUND)" : "—";
      return `<tr class="skipped"><td>${deg(name)}</td><td></td><td>–</td><td>–</td><td>${why}</td></tr>`;
    }
    const img = s.tiles[i] !== undefined ? `<img src="/api/tile/${i}.jpg?v=${s.tiles[i]}" alt="">` : "";
    return `<tr><td>${deg(name)}${st.second ? " ·2ND" : ""}</td><td>${img}</td><td>${st.score === null ? "…" : st.score.toFixed(3)}</td><td>3</td><td><b>${st.label ? VERDICT[st.label] || st.label : "SCORING"}</b></td></tr>`;
  }).join("");
}

// ---- VLA controller ----------------------------------------------------------------------
function spark(values, plan, planStart, planDt, lo, hi) {
  const W = 200, H = 14, t0 = -4, t1 = 2;
  const X = (t) => (t - t0) / (t1 - t0) * W, Y = (v) => H - 1 - (H - 2) * (v - lo) / (hi - lo || 1);
  let o = L(X(0), 0, X(0), H, { stroke: css("--faint"), dash: "2 2" });
  if (values.length > 1) o += `<polyline fill="none" stroke="${css("--text")}" stroke-width="1.2" points="${values.map(([t, v]) => `${X(t).toFixed(1)},${Y(v).toFixed(1)}`).join(" ")}"/>`;
  if (plan.length > 1) o += `<polyline fill="none" stroke="${css("--info")}" stroke-width="1.2" stroke-dasharray="3 2" points="${plan.map((v, i) => `${X(planStart + i * planDt).toFixed(1)},${Y(v).toFixed(1)}`).join(" ")}"/>`;
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${o}</svg>`;
}

function vla(s) {
  const policy = ["PICK", "SORT"].includes(s.stage) && s.run_state === "RUNNING";
  const m = s.stage === "SORT" ? s.devices.sort : s.devices.pick;
  $("vlaHead").textContent = `VLA CONTROLLER · ${m.model} · OPENVINO ${m.device}`;
  const c = s.chunk;
  const fresh = c && c.age_s < 2.5 && policy;
  $("vlaLine").textContent = policy && c
    ? `STATE ACTIVE · PLAN ${c.n} ACT / ${(c.n / 30).toFixed(1)} s · LAT ${num(c.ms)} ms · ASYNC · 30 Hz`
    : `STATE ${s.run_state === "RUNNING" ? "STANDBY · SCRIPTED MOVE" : s.run_state} · LAST LAT ${num(s.chunk_ms.sort || s.chunk_ms.pick)} ms`;
  const trace = s.trace.filter((p) => p[0] >= -4);
  const act = trace.length ? trace[trace.length - 1][1] : null;
  const cmd = s.command;
  $("joints").innerHTML = JOINTS.map((name, j) => {
    const vals = trace.map((p) => [p[0], p[1][j]]);
    const plan = fresh ? c.actions.map((a) => a[j]) : [];
    const all = vals.map((x) => x[1]).concat(plan);
    let lo = all.length ? Math.min(...all) : -1, hi = all.length ? Math.max(...all) : 1;
    if (hi - lo < 10) { const mid = (hi + lo) / 2; lo = mid - 5; hi = mid + 5; }
    const a = act ? act[j] : null, k = cmd ? cmd[j] : null;
    const dev = a !== null && k !== null ? a - k : null;
    const bar = dev === null ? "" : `<span class="dev-bar"><i style="width:${Math.min(100, Math.abs(dev) * 5)}%"></i></span>`;
    return `<tr><td>${name}</td><td>${num(a, 1)}</td><td>${num(k, 1)}</td><td>${num(dev, 1)} ${bar}</td><td class="w">${spark(vals, plan, fresh ? -c.age_s : 0, fresh ? c.every / 30 : 0, lo, hi)}</td></tr>`;
  }).join("");
}

// ---- production -------------------------------------------------------------------------
function hms(sec) { sec = Math.floor(sec || 0); return `${pad(Math.floor(sec / 3600))}:${pad(Math.floor(sec / 60) % 60)}:${pad(sec % 60)}`; }
function production(s) {
  const p = s.production, n = s.cycles_done || 0;
  const rate = n ? (p.reject / n * 100) : null;
  const rows = [
    ["INSPECTED", n], ["GOOD", p.good], ["REJECT", p.reject], ["REJECT RATE", rate === null ? "–" : `${rate.toFixed(1)} %`],
    ["SECOND LOOKS", p.second_looks], ["THROUGHPUT", p.throughput_h ? `${p.throughput_h.toFixed(0)} /h` : "–"],
    ["MEDIAN CYCLE", s.median_cycle_s ? `${s.median_cycle_s.toFixed(1)} s` : "–"], ["RUN TIME", hms(p.runtime_s)],
    ["SORTED OK (CHECKED)", s.success.marked ? `${s.success.ok} / ${s.success.marked}` : "–"],
  ];
  $("prodTbl").innerHTML = rows.map(([k, v]) => `<tr><td>${k}</td><td>${esc(v)}</td></tr>`).join("");
  const key = JSON.stringify(s.history.slice(-5));
  if ($("lastBricks").dataset.key !== key) {
    $("lastBricks").dataset.key = key;
    $("lastBricks").innerHTML = s.history.slice(-5).reverse().map((h) => {
      const col = h.verdict === "GOOD" ? css("--good") : css("--reject");
      return `<div class="last-row"><span>#${String(h.cycle).padStart(3, "0")}</span><span class="sw" style="background:${col}"></span><span class="vv">${VERDICT[h.verdict] || h.verdict}</span><span>${h.worst.toFixed(2)}</span><span>${h.cycle_s.toFixed(0)}s</span>
        <span class="btns"><button class="ok ${h.mark === true ? "on" : ""}" data-c="${h.cycle}" data-ok="1" title="Landed on the right plate">✓</button><button class="bad ${h.mark === false ? "on" : ""}" data-c="${h.cycle}" data-ok="0" title="Wrong plate or dropped">✗</button></span></div>`;
    }).join("") || `<div class="last-row" style="color:var(--muted)">no bricks yet</div>`;
    for (const b of $("lastBricks").querySelectorAll("button")) {
      b.addEventListener("click", () => post("/api/mark", { cycle: Number(b.dataset.c), ok: b.classList.contains("on") ? null : b.dataset.ok === "1" }));
    }
  }
}

// ---- events -----------------------------------------------------------------------------
function events(s, body, max, withState) {
  body.innerHTML = s.events.slice(0, max).map((e) => {
    const p = e.prio === 3 ? "INFO" : `P${e.prio}`;
    const state = withState ? `<td>${e.prio === 3 ? "—" : e.acked ? "ACK" : "UNACK"}</td>` : "";
    return `<tr class="p${e.prio} ${e.acked ? "" : "unack"}"><td class="time">${esc(e.time)}</td><td class="p">${p}</td>${state}<td class="tag">${esc(e.tag)}</td><td class="msg">${esc(e.msg)}</td></tr>`;
  }).join("");
}

// ---- compute node -----------------------------------------------------------------------
function bar(value, max, o = {}) {
  const W = 200, f = value === null || value === undefined ? 0 : Math.min(1, Math.max(0, value / max));
  let b = R(0, 1, W, 10, { fill: css("--display"), stroke: css("--line") });
  if (o.normal) b += R(0, 1, W * o.normal / max, 10, { fill: css("--range") });
  b += R(0, 3, W * f, 6, { fill: o.alarm ? css("--p2") : css("--on") });
  if (o.limit) b += L(W * o.limit / max, 0, W * o.limit / max, 12, { stroke: css("--p1"), w: 1.5 });
  return `<svg viewBox="0 0 ${W} 12" preserveAspectRatio="none">${b}</svg>`;
}
function node(s) {
  const last1 = (a) => { for (let i = (a || []).length - 1; i >= 0; i--) if (a[i] !== null) return a[i]; return null; };
  const users = { GPU: [], NPU: [], CPU: ["control loop", "scripted moves", "camera I/O"] };
  const add = (d, l) => (users[d] || users.CPU).push(l);
  add(s.devices.anomaly, "Anomalib");
  if (s.devices.pick.model === s.devices.sort.model && s.devices.pick.device === s.devices.sort.device) add(s.devices.pick.device, s.devices.pick.model);
  else { add(s.devices.pick.device, `${s.devices.pick.model} (pick)`); add(s.devices.sort.device, `${s.devices.sort.model} (sort)`); }
  const sys = s.sys;
  const temp = last1(sys.pkg_temp_c), pw = last1(sys.pkg_w), bat = last1(sys.battery_w);
  const rows = ["GPU", "NPU", "CPU"].map((d) => {
    const v = last1(sys[`${d.toLowerCase()}_pct`]);
    return `<div class="nrow"><span class="n">${d}</span>${bar(v, 100)}<span class="val">${num(v)} %</span><span class="who" title="${esc(users[d].join(" · "))}">${esc(users[d].join(" · ") || "idle")}</span></div>`;
  });
  rows.push(`<div class="nrow"><span class="n">TEMP</span>${bar(temp, 110, { normal: 85, limit: 90, alarm: temp > 90 })}<span class="val">${num(temp)} °C</span><span class="who">normal ≤ 85 · alarm 90</span></div>`);
  rows.push(`<div class="nrow"><span class="n">POWER</span><span class="pw">${pw !== null ? `${num(pw, 1)} W package` : bat !== null ? `${num(bat, 1)} W laptop (battery)` : "n/a · needs RAPL access"}</span></div>`);
  $("node").innerHTML = rows.join("");
}

// ---- trends -----------------------------------------------------------------------------
function axes(W, H, m, xs, ys, xLabel) {
  let o = R(m.l, m.t, W - m.l - m.r, H - m.t - m.b, { fill: css("--display"), stroke: css("--line") });
  for (const [v, y] of ys) o += L(m.l, y, W - m.r, y, { stroke: "#d2d2d2" }) + T(m.l - 4, y + 3, v, { size: 9, anchor: "end", mono: true, fill: css("--muted") });
  for (const [v, x] of xs) o += T(x, H - m.b + 12, v, { size: 9, anchor: "middle", mono: true, fill: css("--muted") });
  if (xLabel) o += T(W - m.r, H - 3, xLabel, { size: 9, anchor: "end", fill: css("--muted") });
  return o;
}
function trends(s) {
  const m = { l: 40, r: 12, t: 10, b: 24 };
  // score per brick
  {
    const { svg, W, H } = canvas("trScore");
    const n = s.scores.length, [lo, hi] = s.bands;
    const X = (i) => m.l + (W - m.l - m.r) * (n <= 1 ? 0.5 : i / (n - 1)), Y = (v) => H - m.b - (H - m.t - m.b) * v;
    let o = axes(W, H, m, s.scores.filter((_, i) => n < 12 || i % Math.ceil(n / 10) === 0).map((p) => [`#${p.cycle}`, X(s.scores.indexOf(p))]), [0, 0.5, 1].map((v) => [v.toFixed(1), Y(v)]), "brick");
    o += R(m.l, Y(lo), W - m.l - m.r, Y(0) - Y(lo), { fill: css("--range") });
    o += L(m.l, Y(lo), W - m.r, Y(lo), { stroke: css("--line-strong"), dash: "4 3" }) + L(m.l, Y(hi), W - m.r, Y(hi), { stroke: css("--line-strong"), dash: "4 3" });
    o += T(W - m.r - 4, Y(hi) - 3, `REJECT ≥ ${hi.toFixed(2)}`, { size: 9, anchor: "end", fill: css("--muted") }) + T(W - m.r - 4, Y(lo) + 11, `GOOD ≤ ${lo.toFixed(2)}`, { size: 9, anchor: "end", fill: css("--muted") });
    if (n > 1) o += `<polyline fill="none" stroke="${css("--line")}" points="${s.scores.map((p, i) => `${X(i)},${Y(Math.min(p.worst, 1))}`).join(" ")}"/>`;
    s.scores.forEach((p, i) => {
      const x = X(i), y = Y(Math.min(p.worst, 1));
      o += p.verdict === "GOOD" ? `<circle cx="${x}" cy="${y}" r="4" fill="${css("--display")}" stroke="${css("--text")}" stroke-width="1.5"/>` : R(x - 4, y - 4, 8, 8, { fill: css("--text") });
    });
    o += T(m.l + 6, m.t + 12, "○ GOOD  ■ REJECT", { size: 9, fill: css("--muted") });
    svg.innerHTML = o;
  }
  // cycle time per brick
  {
    const { svg, W, H } = canvas("trCycle");
    const n = s.scores.length, max = Math.max(30, ...s.scores.map((p) => p.cycle_s));
    const bw = Math.min(36, (W - m.l - m.r) / Math.max(n, 1)), Y = (v) => H - m.b - (H - m.t - m.b) * v / max;
    let o = axes(W, H, m, [], [0, max / 2, max].map((v) => [v.toFixed(0), Y(v)]), "brick");
    s.scores.forEach((p, i) => { o += R(m.l + i * bw + 2, Y(p.cycle_s), Math.max(2, bw - 4), Y(0) - Y(p.cycle_s), { fill: css("--on") }); });
    if (s.median_cycle_s) o += L(m.l, Y(s.median_cycle_s), W - m.r, Y(s.median_cycle_s), { stroke: css("--info"), dash: "4 3" }) + T(W - m.r - 4, Y(s.median_cycle_s) - 3, `median ${s.median_cycle_s.toFixed(1)} s`, { size: 9, anchor: "end", fill: css("--info") });
    svg.innerHTML = o;
  }
  // node load and temperature over time
  const longSeries = (id, keys, max, extra) => {
    const { svg, W, H } = canvas(id);
    const ages = s.sys_long.age_s || [];
    const tmin = Math.min(-60, ...ages);
    const X = (t) => m.l + (W - m.l - m.r) * (t - tmin) / (0 - tmin), Y = (v) => H - m.b - (H - m.t - m.b) * Math.min(v, max) / max;
    let o = axes(W, H, m, [[`${Math.round(tmin / 60)} min`, X(tmin)], ["now", X(0)]], [0, max / 2, max].map((v) => [v.toFixed(0), Y(v)]), "");
    if (extra) o += extra(X, Y, W);
    keys.forEach(([k, label, dash, colour], i) => {
      const pts = (s.sys_long[k] || []).map((v, j) => (v === null ? null : `${X(ages[j]).toFixed(1)},${Y(v).toFixed(1)}`)).filter(Boolean);
      if (pts.length > 1) o += `<polyline fill="none" stroke="${colour}" stroke-width="1.4" ${dash ? `stroke-dasharray="${dash}"` : ""} points="${pts.join(" ")}"/>`;
      o += L(m.l + 8 + i * 70, m.t + 9, m.l + 26 + i * 70, m.t + 9, { stroke: colour, w: 1.4, dash }) + T(m.l + 30 + i * 70, m.t + 12, label, { size: 9 });
    });
    svg.innerHTML = o;
  };
  longSeries("trLoad", [["gpu_pct", "GPU", "", css("--text")], ["npu_pct", "NPU", "5 3", css("--text")], ["cpu_pct", "CPU", "", css("--faint")]], 100);
  longSeries("trTemp", [["pkg_temp_c", "PACKAGE", "", css("--text")]], 110, (X, Y, W) =>
    R(m.l, Y(85), W - m.l - m.r, Y(0) - Y(85), { fill: css("--range") }) + L(m.l, Y(90), W - m.r, Y(90), { stroke: css("--p1"), dash: "4 3" }) + T(W - m.r - 4, Y(90) - 3, "ALARM 90 °C", { size: 9, anchor: "end", fill: css("--p1") }));
}
