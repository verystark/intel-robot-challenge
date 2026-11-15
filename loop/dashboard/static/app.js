// Sorting cell dashboard: renders the state that run_cell.py streams on /api/events (5 Hz).
// No libraries: plain DOM and hand-made SVG.
"use strict";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmt = (v, d = 0, unit = "") => (v === null || v === undefined || Number.isNaN(v) ? "–" : `${Number(v).toFixed(d)}${unit}`);
const STAGES = ["PERCEIVE", "DETECT", "REASON", "ACT", "OPTIMIZE"];
const JOINTS = ["pan", "lift", "elbow", "wrist flex", "wrist roll", "gripper"];
let palette = null;
let lastNarr = "";
let lastTilesKey = "";
let lastCardsKey = "";
let lastMsg = 0;

// Colours: copy palette.json onto CSS variables (the CSS has the same defaults).
fetch("/static/palette.json").then((r) => r.json()).then((p) => {
  palette = p;
  const root = document.documentElement.style;
  root.setProperty("--bg", p.background);
  root.setProperty("--panel", p.panel);
  root.setProperty("--line", p.panel_line);
  root.setProperty("--text", p.text);
  root.setProperty("--muted", p.muted);
  for (const [k, v] of Object.entries(p.stages)) root.setProperty(`--${k.toLowerCase()}`, v);
  root.setProperty("--good", p.verdict.GOOD);
  root.setProperty("--defective", p.verdict.DEFECTIVE);
  root.setProperty("--unsure", p.verdict.UNSURE);
  root.setProperty("--stop", p.stop);
}).catch(() => {});

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const deg = (name) => String(name).replace(" deg", "°");

// --- commands -----------------------------------------------------------------------
const post = (path, body) => fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : "" });
$("stop").addEventListener("click", () => post("/api/stop"));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" || e.key === "s" || e.key === "S") { post("/api/stop"); e.preventDefault(); }
  else if (e.key === "r" || e.key === "R") post("/api/resume");
  else if (e.key === " ") { post("/api/pause"); e.preventDefault(); }
  else if (e.key === "f" || e.key === "F") {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen().catch(() => {});
    else document.exitFullscreen();
  }
});

// --- measured device placement (newest benchmark), refreshed every minute -------------------
function loadBench() {
  fetch("/api/bench").then((r) => r.json()).then(renderPlacement).catch(() => {});
}
loadBench();
setInterval(loadBench, 60000);

function renderPlacement(bench) {
  const lines = [];
  const line = (label, rows) => {
    if (!rows.length) return;
    const ok = rows.filter((r) => !r.error && r.median_ms);
    const best = ok.length ? Math.min(...ok.map((r) => r.median_ms)) : null;
    const parts = rows.map((r) => {
      const v = r.error ? "✗" : r.median_ms >= 1000 ? `${(r.median_ms / 1000).toFixed(1)} s` : `${Math.round(r.median_ms)} ms`;
      return `<span class="${r.median_ms === best ? "best" : ""}">${r.device} <span class="ms">${v}</span></span>`;
    });
    lines.push(`<b>${esc(label)}</b> ${parts.join(" · ")}`);
  };
  if (bench.anomaly) line("Anomalib", bench.anomaly.rows.filter((r) => r.model === "FP32"));
  if (bench.policy) {
    const models = [...new Set(bench.policy.rows.map((r) => r.model))];
    for (const m of models) line(m, bench.policy.rows.filter((r) => r.model === m));
  }
  const note = (bench.policy && bench.policy.contended) || (bench.anomaly && bench.anomaly.contended) ? " (measured while the laptop was busy)" : "";
  $("placement").innerHTML = lines.length ? `Measured per call${note}:<br>${lines.join("<br>")}` : "";
}

// --- the event stream ------------------------------------------------------------------
function connect() {
  const es = new EventSource("/api/events");
  es.onmessage = (ev) => { lastMsg = Date.now(); render(JSON.parse(ev.data)); };
  es.onerror = () => {};
}
connect();
setInterval(() => $("offline").classList.toggle("hidden", Date.now() - lastMsg < 3000), 1000);

function render(s) {
  renderPipeline(s);
  renderHeader(s);
  renderNarration(s);
  renderLive(s);
  renderVerdict(s);
  renderPlan(s);
  renderDevices(s);
  renderHistory(s);
}

function renderHeader(s) {
  const mode = $("mode");
  mode.textContent = s.mode;
  mode.className = `chip mode ${s.mode === "LIVE" ? "live" : "sim"}`;
  const rs = $("runstate");
  rs.textContent = s.run_state;
  rs.className = `runstate ${s.run_state}`;
  $("cycle").textContent = s.cycle || "–";
}

function renderPipeline(s) {
  const p = s.pipeline;
  for (const st of STAGES) {
    const el = document.querySelector(`.stage[data-stage="${st}"]`);
    el.classList.toggle("on", p.active.includes(st));
    $(`w-${st}`).textContent = p[st].what;
    $(`m-${st}`).textContent = p[st].meta;
  }
}

function renderNarration(s) {
  const narr = $("narration");
  if (s.narration !== lastNarr && lastNarr === "") {
    lastNarr = s.narration;
    narr.innerHTML = colourWords(esc(s.narration));
  } else if (s.narration !== lastNarr) {
    lastNarr = s.narration;
    narr.classList.add("fade");
    setTimeout(() => { narr.innerHTML = colourWords(esc(s.narration)); narr.classList.remove("fade"); }, 180);
  }
  const order = ["PICK", "SHOW", "INSPECT", "HOME", "SORT"];
  const at = order.indexOf(s.stage);
  for (const li of document.querySelectorAll("#steps li")) {
    const name = li.dataset.s;
    li.classList.toggle("on", name === s.stage);
    li.classList.toggle("done", at >= 0 && order.indexOf(name) < at);
    const t = name === s.stage ? s.stage_elapsed : s.stage_times[name];
    li.querySelector("span").textContent = t ? `${t.toFixed(1)} s` : "";
  }
}

// Colour the plate words in narration and sentences, so the crowd links screen and plate.
function colourWords(html) {
  return html
    .replace(/\b(green plate|good)\b/g, '<span class="good">$1</span>')
    .replace(/\b(orange plate|defective|Defect found)\b/g, '<span class="defective">$1</span>')
    .replace(/“([^”]*)”/g, "<q>$1</q>");
}

function renderLive(s) {
  const el = $("live");
  const live = s.live;
  if (!live || live.age_s > 1.5 || !["SHOW", "INSPECT"].includes(s.stage)) { el.classList.add("hidden"); return; }
  el.classList.remove("hidden");
  const col = live.moving ? css("--muted") : css(`--${(live.label || "unsure").toLowerCase()}`);
  el.innerHTML = `<span>live score <b>${fmt(live.score, 2)}</b></span>` +
    (live.moving ? `<span class="moving">arm moving · not used for the decision</span>`
                 : `<span class="lab" style="color:${col}">${esc(live.label)}</span><span class="moving">steady</span>`);
}

function renderVerdict(s) {
  const v = $("verdict");
  const verdict = s.verdict || "";
  const idle = { PICK: "Next brick", SHOW: "Inspecting…", INSPECT: "Inspecting…", HOME: "Next brick" };
  v.textContent = verdict ? (verdict === "UNSURE" ? "UNSURE…" : verdict) : (idle[s.stage] || "Waiting");
  v.className = `verdict ${verdict}`;
  $("verdictSub").textContent = s.verdict_sub || "";
  $("sentence").innerHTML = s.sentence ? colourWords(esc(`“${s.sentence}”`)) : "–";
  document.querySelector(".sentence-box .label").textContent = s.task_for ? `Task sent to ${s.task_for}` : "Task";

  // Stop tiles: the current cycle's photos (with heatmaps once scored), planned stops, skipped stops.
  const key = JSON.stringify([s.tiles, s.stops, s.stops_planned, s.early_reject]);
  if (key !== lastTilesKey) {
    lastTilesKey = key;
    const planned = s.stops_planned.length ? s.stops_planned : ["0 deg", "90 deg", "180 deg"];
    $("stops").innerHTML = planned.map((name, i) => {
      const st = s.stops[i];
      if (st) {
        const img = s.tiles[i] !== undefined ? `<img src="/api/tile/${i}.jpg?v=${s.tiles[i]}" alt="">` : `<div class="empty">photographing…</div>`;
        const score = st.score === null ? "scoring…" : st.score.toFixed(2);
        const badge = st.second ? `<span class="badge">2nd look</span>` : "";
        return `<div class="stop-tile ${st.label || ""}">${img}${badge}<div class="cap"><span>${esc(deg(name))}</span><span>${score} ${esc(st.label || "")}</span></div></div>`;
      }
      const why = s.early_reject && s.stops.length ? "skipped: a defect<br>was already found" : "not yet";
      return `<div class="stop-tile"><div class="empty">${why}</div><div class="cap"><span>${esc(deg(name))}</span><span></span></div></div>`;
    }).join("");
  }
  drawScoreBar(s);
}

function drawScoreBar(s) {
  const [lo, hi] = s.bands;
  const bar = $("scorebar");
  const W = Math.max(200, Math.round(bar.clientWidth || 420));
  bar.setAttribute("viewBox", `0 0 ${W} 58`);  // draw at the real pixel size: text stays crisp
  const x = (v) => 10 + (W - 20) * Math.min(Math.max(v, 0), 1);
  const g = css("--good"), u = css("--unsure"), d = css("--defective"), m = css("--muted"), t = css("--text");
  let svg = `<rect x="10" y="22" width="${x(lo) - 10}" height="10" fill="${g}" opacity=".85"/>` +
    `<rect x="${x(lo)}" y="22" width="${x(hi) - x(lo)}" height="10" fill="${u}" opacity=".85"/>` +
    `<rect x="${x(hi)}" y="22" width="${W - 10 - x(hi)}" height="10" fill="${d}" opacity=".85"/>` +
    `<text x="10" y="50" fill="${m}" font-size="11">good &lt; ${lo.toFixed(2)}</text>` +
    `<text x="${(x(lo) + x(hi)) / 2}" y="50" fill="${m}" font-size="11" text-anchor="middle">unsure: second look</text>` +
    `<text x="${W - 10}" y="50" fill="${m}" font-size="11" text-anchor="end">defective &gt; ${hi.toFixed(2)}</text>`;
  // Markers, with neighbouring labels pushed apart so they never overlap.
  const marks = s.stops.filter((st) => st.score !== null).map((st) => ({ px: x(st.score), name: deg(st.name), anchor: "middle", lx: x(st.score) }))
    .sort((a, b) => a.px - b.px);
  for (let i = 1; i < marks.length; i++) {
    if (marks[i].px - marks[i - 1].px < 30) {
      marks[i - 1].anchor = "end"; marks[i - 1].lx = marks[i - 1].px - 3;
      marks[i].anchor = "start"; marks[i].lx = Math.max(marks[i].px + 3, marks[i - 1].px + 3);
    }
  }
  for (const mk of marks) {
    svg += `<line x1="${mk.px}" x2="${mk.px}" y1="14" y2="38" stroke="${t}" stroke-width="2.5"/>` +
      `<text x="${mk.lx}" y="11" fill="${t}" font-size="11" text-anchor="${mk.anchor}">${esc(mk.name)}</text>`;
  }
  $("scorebar").innerHTML = svg;
}

// Policy plan: per joint, the measured position (last 4 s) and the plan the policy last made.
function renderPlan(s) {
  const svg = $("plan");
  const W = Math.max(240, Math.round(svg.clientWidth || 440)), H = Math.max(120, Math.round(svg.clientHeight || 170));
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);  // real pixel size: labels never stretch
  const left = 64, right = 8, rowH = H / 6;
  const policyStage = ["PICK", "SORT"].includes(s.stage);
  const chunk = s.chunk;
  const fresh = chunk && chunk.age_s < 2.5 && policyStage;
  const planS = fresh ? (chunk.n / 30) : 0;
  const t0 = -4, t1 = Math.max(planS - (fresh ? chunk.age_s : 0), 1.0);
  const X = (t) => left + (W - left - right) * (t - t0) / (t1 - t0);
  const meas = css("--text"), plan = css("--reason"), grid = css("--line"), m = css("--muted");
  let out = `<line x1="${X(0)}" x2="${X(0)}" y1="0" y2="${H}" stroke="${m}" stroke-width="1" stroke-dasharray="2 3"/>`;
  for (let j = 0; j < 6; j++) {
    const y0 = j * rowH, pad = 4;
    const trace = s.trace.filter((p) => p[0] >= t0);
    const vals = trace.map((p) => p[1][j]);
    const pv = fresh ? chunk.actions.map((a) => a[j]) : [];
    const all = vals.concat(pv);
    let lo = Math.min(...all), hi = Math.max(...all);
    if (!all.length) { lo = -1; hi = 1; }
    if (hi - lo < 10) { const c = (hi + lo) / 2; lo = c - 5; hi = c + 5; }
    const Y = (v) => y0 + pad + (rowH - 2 * pad) * (1 - (v - lo) / (hi - lo));
    out += `<line x1="${left}" x2="${W - right}" y1="${y0 + rowH}" y2="${y0 + rowH}" stroke="${grid}"/>`;
    out += `<text x="0" y="${y0 + rowH / 2 + 4}" fill="${m}" font-size="11">${JOINTS[j]}</text>`;
    if (trace.length > 1) {
      out += `<polyline fill="none" stroke="${meas}" stroke-width="1.6" points="${trace.map((p) => `${X(p[0]).toFixed(1)},${Y(p[1][j]).toFixed(1)}`).join(" ")}"/>`;
    }
    if (fresh && pv.length > 1) {
      const start = -chunk.age_s, dt = chunk.every / 30;
      out += `<polyline fill="none" stroke="${plan}" stroke-width="1.6" stroke-dasharray="4 3" points="${pv.map((v, i) => `${X(start + i * dt).toFixed(1)},${Y(v).toFixed(1)}`).join(" ")}"/>`;
    }
  }
  svg.innerHTML = out;
  const model = s.stage === "PICK" ? s.devices.pick : s.devices.sort;
  $("planTitle").innerHTML = policyStage && chunk
    ? `<b>${esc(model.model)}</b> plans ${(chunk.n / 30).toFixed(1)} s of motion per call · ${fmt(chunk.ms, 0)} ms on the ${esc(model.device)} · asynchronous, so the arm keeps moving`
    : `<b>Scripted move</b> · no policy running (show pose, wrist stops, home)`;
}

function sparkline(values, colour, max = 100) {
  const W = 110, H = 26;
  const pts = values.map((v, i) => [i, v]).filter((p) => p[1] !== null && p[1] !== undefined);
  if (pts.length < 2) return `<svg viewBox="0 0 ${W} ${H}"></svg>`;
  const n = values.length;
  const path = pts.map(([i, v]) => `${(W * i / (n - 1)).toFixed(1)},${(H - 2 - (H - 4) * Math.min(v, max) / max).toFixed(1)}`).join(" ");
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><polyline fill="none" stroke="${colour}" stroke-width="1.5" points="${path}"/></svg>`;
}

function renderDevices(s) {
  const d = s.devices, sys = s.sys;
  const users = { GPU: [], NPU: [], CPU: ["control loop", "scripted moves"] };
  const add = (dev, label) => { (users[dev] || users.CPU).push(label); };
  add(d.anomaly, "Anomalib");
  if (d.pick.model === d.sort.model && d.pick.device === d.sort.device) add(d.pick.device, d.pick.model);
  else { add(d.pick.device, `${d.pick.model} (pick)`); add(d.sort.device, `${d.sort.model} (sort)`); }
  const last = (arr) => { for (let i = arr.length - 1; i >= 0; i--) if (arr[i] !== null) return arr[i]; return null; };
  const rows = [["GPU", sys.gpu_pct, css("--perceive")], ["NPU", sys.npu_pct, css("--detect")], ["CPU", sys.cpu_pct, css("--optimize")]];
  $("devices").innerHTML = rows.map(([name, series, colour]) => {
    const who = users[name].length ? users[name].map((u) => `<span>${esc(u)}</span>`).join("") : `<span class="idle">idle</span>`;
    return `<div class="dev" style="--dc:${colour}"><span class="name">${name}</span><span class="who">${who}</span>${sparkline(series, colour)}<span class="pct">${fmt(last(series), 0, "%")}</span></div>`;
  }).join("");
  const temp = last(sys.pkg_temp_c), pkg = last(sys.pkg_w), bat = last(sys.battery_w);
  const power = pkg !== null ? `package ${fmt(pkg, 1, " W")}` : bat !== null ? `laptop ${fmt(bat, 1, " W")} (battery)` : "power: needs RAPL access";
  $("thermal").textContent = `package ${fmt(temp, 0, " °C")} · ${power} · last 60 s`;
}

function renderHistory(s) {
  const key = JSON.stringify(s.history);
  if (key !== lastCardsKey) {
    lastCardsKey = key;
    if (!s.history.length) { $("cards").innerHTML = `<div class="empty">No bricks yet</div>`; }
    else {
      $("cards").innerHTML = s.history.slice(-6).reverse().map((h) => `
        <div class="card">
          <img src="${h.thumb}" alt="">
          <div class="info">
            <div class="v ${h.verdict}">${h.verdict}</div>
            <div class="meta">#${h.cycle} · ${h.cycle_s.toFixed(1)} s<br>${h.worst.toFixed(2)} at ${h.worst_stop}${h.second_look ? " · 2nd" : ""}</div>
            <div class="marks">
              <button class="ok ${h.mark === true ? "on" : ""}" data-c="${h.cycle}" data-ok="1" title="Landed on the right plate">✓</button>
              <button class="bad ${h.mark === false ? "on" : ""}" data-c="${h.cycle}" data-ok="0" title="Wrong plate or dropped">✗</button>
            </div>
          </div>
        </div>`).join("");
      for (const b of document.querySelectorAll(".card .marks button")) {
        b.addEventListener("click", () => {
          const on = b.classList.contains("on");
          post("/api/mark", { cycle: Number(b.dataset.c), ok: on ? null : b.dataset.ok === "1" });
        });
      }
    }
  }
  const ok = s.success.ok, marked = s.success.marked;
  $("numOk").textContent = marked ? ok : "–";
  $("numMarked").textContent = marked ? marked : "";
  document.querySelector(".num-big .of").classList.toggle("hidden", !marked);
  document.querySelector(".num-label").innerHTML = marked
    ? `sorted onto the right plate <small>(checked by hand)</small>`
    : `sorted onto the right plate <small>(mark each brick ✓ or ✗)</small>`;
  const done = s.history.length ? s.cycles_done : 0;
  $("numSub").textContent = done ? `${done} brick${done === 1 ? "" : "s"} · median ${fmt(s.median_cycle_s, 1, " s")} per brick` : "no bricks yet";
}
