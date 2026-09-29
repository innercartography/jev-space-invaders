import { R, SOURCES } from "./data/results.js";

// Set this to the public repository URL once it exists; receipts then link to each source file.
const REPO_URL = "https://github.com/innercartography/jev-space-invaders";
const SHOT = new URLSearchParams(location.search).has("shot");  // screenshot mode: final states, no motion
const REDUCE = SHOT || matchMedia("(prefers-reduced-motion: reduce)").matches;
if (SHOT) document.documentElement.classList.add("shot");
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const NS = "http://www.w3.org/2000/svg";

// ---------- values: every number on the page comes from R ----------
const get = (path) => path.split(".").reduce((o, k) => (o == null ? o : o[k]), R);
const WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
function fmt(v, f) {
  if (v == null) return "–";
  switch (f) {
    case "0": return String(Math.round(v));
    case "1": return v.toFixed(1);
    case "int": return Math.round(v).toLocaleString("en-US");
    case "pct": return Math.round(v * 100) + "%";
    case "pct1": return (v * 100).toFixed(1) + "%";
    case "usd3": return "$" + v.toFixed(3);
    case "usd2": return "$" + v.toFixed(2);
    case "floor": return String(Math.floor(v));
    case "wins": { const [w, t, l] = String(v).split("/").map(Number); return `${w}/${w + t + l}`; }
    case "words": { const w = WORDS[v] || String(v); return w[0].toUpperCase() + w.slice(1); }
    default: return String(v);
  }
}
function fillValues(root = document) {
  for (const el of $$("[data-v]", root)) el.textContent = fmt(get(el.dataset.v), el.dataset.f);
}
function tween(el, to, f = "0", dur = 900) {
  const from = parseFloat(el.dataset.cur ?? to);
  el.dataset.cur = to;
  if (REDUCE || from === to) { el.textContent = fmt(to, f); return; }
  const t0 = performance.now();
  const tick = (t) => {
    const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
    el.textContent = fmt(from + (to - from) * e, f);
    if (k < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}
const cfgName = (c) => {
  const [mv, dodge, fire] = c.split("-");
  return `${mv} · ${dodge === "on" ? "dodge" : "no dodge"} · ${fire === "ready" ? "fire when ready" : "aimed fire"}`;
};
const svg = (tag, attrs = {}, parent) => {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (parent) parent.appendChild(el);
  return el;
};

// ---------- scroll scenes ----------
const scenes = $$(".scene").map((el) => ({ el, id: el.id, steps: +el.dataset.steps, step: -1, active: false }));
for (const s of scenes) s.el.style.setProperty("--steps", s.steps);
const handlers = {};

function applyBeats(scene) {
  for (const el of $$("[data-in]", scene.el)) {
    const a = +el.dataset.in, b = el.dataset.out == null ? Infinity : +el.dataset.out;
    el.classList.toggle("on", scene.step >= a && scene.step < b);
    el.classList.toggle("gone", scene.step >= b);
  }
}
function onScroll() {
  const vh = innerHeight;
  for (const s of scenes) {
    const r = s.el.getBoundingClientRect();
    const active = r.top < vh && r.bottom > 0;
    if (active !== s.active) { s.active = active; handlers[s.id]?.active?.(active, s); }
    const span = s.el.offsetHeight - vh;
    const p = Math.min(1, Math.max(0, -r.top / span));
    const step = Math.min(s.steps - 1, Math.floor(p * s.steps));
    if (step !== s.step) { s.step = step; applyBeats(s); handlers[s.id]?.step?.(step, s); }
  }
}
function playOnly(videos, which) {
  for (const v of videos) {
    const on = v === which;
    v.classList.toggle("show", on);
    if (on && !REDUCE) v.play().catch(() => {}); else v.pause();
  }
}

// ---------- 1. hook ----------
{
  const vp = $("#hook-v-pilot"), va = $("#hook-v-a"), vb = $("#hook-v-b");
  const S = R.swarm.conditions;
  const max = Math.max(S.A.ph1[0], S.B.ph1[0], S.A.ph2[0], S.B.ph2[0]) * 1.08;
  const nA = $("#hook-n-a"), nB = $("#hook-n-b"), bA = $("#hook-bar-a"), bB = $("#hook-bar-b");
  let cur = 0;
  handlers.hook = {
    active(on) { if (!on) [vp, va, vb].forEach((v) => v.pause()); else handlers.hook.step(cur); },
    step(k) {
      cur = k;
      const stage = $("#hook .stage");
      $$("#hook .qs li").forEach((li, i, all) => li.classList.toggle("past", all.slice(i + 1).some((x) => x.classList.contains("on"))));
      playOnly([vp, va, vb], k < 7 ? vp : k === 7 ? va : vb);
      const changed = k >= 8;
      stage.classList.toggle("world-changed", changed);
      $("#hook-world").textContent = changed ? "the game changed" : "stable world";
      $("#hook-lbl-b").textContent = changed ? "Inherited memory" : "Mitosis memory";
      if (k >= 7) {
        const a = changed ? S.A.ph2[0] : S.A.ph1[0], b = changed ? S.B.ph2[0] : S.B.ph1[0];
        tween(nA, a); tween(nB, b);
        bA.style.width = (a / max) * 100 + "%"; bB.style.width = (b / max) * 100 + "%";
      } else { bA.style.width = bB.style.width = "0%"; }
    },
  };
}

// ---------- 2. pilot ----------
{
  const v = $("#pilot-v"), act = $("#pilot-act");
  let A = null, raf = 0, raceRaf = 0, last = 37;
  fetch("assets/pilot_actions.json").then((r) => r.json()).then((d) => (A = d));
  const sync = () => {
    if (A) {
      const i = Math.min(A.actions.length - 1, Math.floor(v.currentTime * A.fps));
      act.textContent = A.actions[i];
      const x = A.ship_x[i] ?? last; last = x;
      act.style.left = (x / A.width) * 100 + "%";
    }
    raf = requestAnimationFrame(sync);
  };
  // latency race: one second of play, slowed ~3.5x, ticks at each decision's median latency
  const lanes = [["#race-jev", R.pilot.latency_ms_p50], ["#race-haiku", R.pilot.haiku_latency_ms_p50]].map(([sel, ms]) => {
    const tr = $(sel); tr.innerHTML = "";
    const ticks = [];
    for (let t = ms; t <= 1000; t += ms) { const i = document.createElement("i"); i.style.left = (t / 10) + "%"; tr.appendChild(i); ticks.push([t, i]); }
    const head = document.createElement("span"); head.className = "head"; tr.appendChild(head);
    return { ticks, head };
  });
  const race = (t0) => (t) => {
    const ms = ((t - t0) / 3.5) % 1150;
    for (const L of lanes) {
      L.head.style.left = Math.min(ms, 1000) / 10 + "%";
      for (const [tt, i] of L.ticks) i.classList.toggle("hit", ms >= tt);
    }
    raceRaf = requestAnimationFrame(race(t0));
  };
  handlers.pilot = {
    active(on) {
      cancelAnimationFrame(raf);
      if (on) { if (!REDUCE) v.play().catch(() => {}); v.classList.add("show"); sync(); } else v.pause();
    },
    step(k) {
      cancelAnimationFrame(raceRaf);
      if (k >= 1 && k <= 2) {
        if (REDUCE) lanes.forEach((L) => L.ticks.forEach(([, i]) => i.classList.add("hit")));
        else raceRaf = requestAnimationFrame(race(performance.now()));
      }
      if (k === 4) { const el = $("#pilot [data-count]"); el.dataset.cur = 0; tween(el, R.pilot.mean, "0", 1400); }
    },
  };
  $("#pilot-receipt").innerHTML = table(["", "games", "mean", "p50 / decision", "$ / game"], [
    ["JEV (final)", R.pilot.holdout_games, Math.round(R.pilot.mean), R.pilot.latency_ms_p50 + " ms", "$" + R.pilot.cost_per_game.toFixed(3)],
    ["Haiku 4.5, same view + question", R.pilot.haiku_games, Math.round(R.pilot.haiku_mean), R.pilot.haiku_latency_ms_p50 + " ms", "$" + R.pilot.haiku_cost_per_game.toFixed(2)],
    ["Sweep bot (no model)", R.pilot.holdout_games, Math.round(R.pilot.sweep_mean), "–", "$0"],
    ["Random", R.pilot.holdout_games, Math.round(R.pilot.random_mean), "–", "$0"],
  ]) + `<p>Real time (game does not wait), first ${R.pilot.rt_games} holdout seeds: JEV ${fmt(R.pilot.rt_jev_mean, "0")} vs Haiku ${fmt(R.pilot.rt_haiku_mean, "0")}; JEV made ${fmt(R.pilot.rt_jev_decisions, "0")} decisions a game, Haiku ${fmt(R.pilot.rt_haiku_decisions, "0")}. Haiku turn-based comparison: first ${R.pilot.haiku_games} seeds only (cost).</p>` + srcLine("pilot");
}

// ---------- 3. argue ----------
{
  fetch("assets/views.json").then((r) => r.json()).then((d) => {
    $("#raw-json").textContent = JSON.stringify(d.views.raw).replace(/,"/g, ', "');
    $("#threat-json").textContent = JSON.stringify(d.views.threat, null, 1);
    $("#raw-chars").textContent = `· ${d.chars.raw} characters`;
    $("#threat-chars").textContent = `· ${d.chars.threat} characters`;
  });
  const sweep = R.ladder.find((x) => /sweep bot/i.test(x.belief));
  const m = sweep && sweep.evidence.match(/(-?\d+) \[(-?\d+),\s*\+?(-?\d+)\]/);
  if (m) $("#sweep-verdict").innerHTML = `JEV − sweep bot: ${m[1].replace("-", "−")} points<small>95% interval ${m[2].replace("-", "−")} to +${m[3]} · a tie</small>`;
  $("#ladder").innerHTML = R.ladder.map((x) => `<li><span class="st ${x.status}">${x.status}</span><span>${x.belief}<small>${x.evidence}</small></span></li>`).join("");
  handlers.argue = { step() {} };
}

// ---------- 5. bodies (centerpiece) ----------
{
  const root = $("#swarm-svg"), gW = $("#workers"), gF = $("#findings"), gL = $("#links"), term = $("#term");
  const X = [70, 305, 540, 775], W = 190, H = 150, Y = 40;
  const mk = (k, gen) => {
    const g = svg("g", { class: "node", transform: `translate(${X[k]},${Y})` }, gW);
    svg("rect", { class: "body", width: W, height: H, rx: 3 }, g);
    svg("text", { x: 12, y: 20 }, g).textContent = `TENKI WORKER 0${k + 1}`;
    svg("text", { x: 12, y: 36, class: "gen" }, g).textContent = gen === 1 ? "generation 1" : `gen ${gen} · born empty`;
    const al = svg("g", { class: "aliens" }, g);
    for (let r = 0; r < 3; r++) for (let c = 0; c < 5; c++) svg("rect", { x: 40 + c * 24, y: 52 + r * 16, width: 12, height: 7 }, al);
    svg("rect", { class: "ship", x: 88 + (k - 1.5) * 18, y: 124, width: 14, height: 7 }, g);
    const t = svg("text", { x: W - 12, y: H - 10, class: "count", "text-anchor": "end" }, g);
    return { g, t };
  };
  let gen1 = [0, 1, 2, 3].map((k) => mk(k, 1));
  let gen2 = [0, 1, 2, 3].map((k) => mk(k, 2));
  gen2.forEach((n) => n.g.classList.add("newborn"));
  // real inherited findings (Tenki validation, trial 502), best first
  const F = [...R.challenge.findings].sort((a, b) => b.mean - a.mean).slice(0, 6);
  F.forEach((f, i) => {
    const g = svg("g", { class: "finding", transform: `translate(${140 + (i % 2) * 370},${474 + Math.floor(i / 2) * 20})` }, gF);
    svg("text", {}, g).textContent = cfgName(f.config);
    svg("text", { x: 230, class: "fm" }, g).textContent = `mean ${Math.round(f.mean)} · ${f.games} games`;
  });
  const down = X.map((x) => svg("path", { d: `M${x + W / 2},${Y + H} C${x + W / 2},${Y + H + 90} 500,${Y + H + 60} 500,430`, class: "down" }, gL));
  const up = X.map((x) => svg("path", { d: `M500,430 C500,${Y + H + 60} ${x + W / 2},${Y + H + 90} ${x + W / 2},${Y + H}` }, gL));
  gL.classList.add("links");
  let tick = 0, timer = 0, typer = 0;
  const lines = [0, 1, 2, 3].map((k) => `worker_0${k + 1} terminated`);
  const run = (nodes) => { clearInterval(timer); if (REDUCE) { nodes.forEach((n) => (n.t.textContent = "round 5")); return; } tick = 0; timer = setInterval(() => { tick = (tick % 5) + 1; nodes.forEach((n) => (n.t.textContent = `round ${tick}`)); }, 700); };
  handlers.bodies = {
    active(on) { if (!on) clearInterval(timer); },
    step(k) {
      const stage = $("#bodies .stage");
      clearInterval(timer); clearTimeout(typer);
      gen1.forEach((n, i) => {
        n.g.classList.toggle("newborn", k < 1);
        n.g.classList.toggle("dying", k === 3);
        n.g.classList.toggle("dead", k >= 4);
        n.g.style.transitionDelay = k === 3 ? `${0.3 + i * 0.35}s` : "0s";
      });
      gen2.forEach((n, i) => { n.g.classList.toggle("newborn", k < 4); n.g.style.transitionDelay = k === 4 ? `${i * 0.18}s` : "0s"; n.t.textContent = "round 0"; });
      if (k === 3) gen1.forEach((n) => n.g.classList.add("dead"));
      root.classList.toggle("has-mem", k >= 2);
      root.classList.toggle("lit", k >= 5);
      $$(".finding", gF).forEach((f, i) => { f.classList.toggle("on", k >= 2); f.style.transitionDelay = k === 2 ? `${i * 0.25}s` : "0s"; });
      down.forEach((p) => (p.style.opacity = k === 2 ? 0.6 : 0));
      up.forEach((p) => (p.style.opacity = k >= 5 && k < 6 ? 0.8 : 0));
      stage.classList.toggle("slogan-up", k >= 6);
      if (k === 1 || k === 2) run(gen1);
      if (k === 5) run(gen2);
      if (k === 3) {
        term.textContent = "";
        let i = 0;
        const next = () => { if (i < lines.length) { term.textContent += lines[i++] + "\n"; typer = setTimeout(next, REDUCE ? 0 : 350); } };
        typer = setTimeout(next, REDUCE ? 0 : 300);
      } else term.textContent = k === 4 ? lines.join("\n") + "\nworker_05..08 created · local memory: empty" : "";
    },
  };
}

// ---------- charts ----------
function chart(el, curves, keys, { rounds = 30, phaseLine = 15, labels = {} } = {}) {
  el.innerHTML = ""; el.classList.add("chart");
  const w = 1000, h = 440, L = 56, Rt = 150, T = 20, B = 44;
  const ymax = 200, x = (i) => L + (i / (rounds - 1)) * (w - L - Rt), y = (v) => T + (1 - v / ymax) * (h - T - B);
  for (const v of [0, 50, 100, 150, 200]) {
    svg("line", { x1: L, x2: w - Rt, y1: y(v), y2: y(v), class: "grid" }, el);
    svg("text", { x: L - 10, y: y(v) + 4, "text-anchor": "end" }, el).textContent = v;
  }
  const band = svg("rect", { x: x(phaseLine - 0.5), y: T, width: x(rounds - 1) - x(phaseLine - 0.5), height: h - T - B, class: "band" }, el);
  svg("line", { x1: x(phaseLine - 0.5), x2: x(phaseLine - 0.5), y1: T, y2: h - B, class: "axis" }, el);
  svg("text", { x: x(3), y: h - 14 }, el).textContent = "rounds 1–15 · standard game";
  svg("text", { x: x(phaseLine + 1), y: h - 14 }, el).textContent = "rounds 16–30 · after the change";
  const paths = {};
  for (const k of keys) {
    const seg = (a, b) => {
      const pts = curves[k].slice(a, b).map((v, i) => `${x(a + i)},${y(v)}`).join(" ");
      const p = svg("polyline", { points: pts, class: `line ${k}` }, el);
      const len = p.getTotalLength?.() || 2000;
      p.style.strokeDasharray = `${len} ${len}`; p.style.strokeDashoffset = len;
      return { p, len };
    };
    const s1 = seg(0, phaseLine), s2 = seg(phaseLine - 1, rounds);
    const color = getComputedStyle(s1.p).stroke;
    const t1 = svg("text", { x: x(phaseLine - 1) + 8, y: y(curves[k][phaseLine - 1]) + 4, class: "lbl-line", fill: color }, el);
    const t2 = svg("text", { x: w - Rt + 10, y: y(curves[k][rounds - 1]) + 4, class: "lbl-line", fill: color }, el);
    t1.textContent = t2.textContent = labels[k] || k;
    for (const t of [t1, t2]) { t.style.opacity = 0; t.style.transition = "opacity .6s"; }
    paths[k] = { s1, s2, t1, t2 };
  }
  return {
    show(k, upto) { // upto: 0 none, 1 before the change, 2 whole run
      const P = paths[k];
      P.s1.p.style.strokeDashoffset = upto >= 1 ? 0 : P.s1.len;
      P.s2.p.style.strokeDashoffset = upto >= 2 ? 0 : P.s2.len;
      P.t1.style.opacity = upto === 1 ? 1 : 0; P.t2.style.opacity = upto >= 2 ? 1 : 0;
    },
    band(on) { band.classList.toggle("on", on); },
  };
}
{
  const c = chart($("#chart-main"), R.swarm.curves, ["A", "B"], { labels: { A: "no memory", B: "shared memory" } });
  handlers.works = { step() { c.show("A", 1); c.show("B", 1); } };
}

// ---------- 7. change ----------
{
  const va = $("#change-v-a"), vb = $("#change-v-b");
  let cur = 0;
  const LA = R.landscape.A, LB = R.landscape.B, champ = LA.rank[0];
  const maxS = Math.max(...Object.values(LA.truth), ...Object.values(LB.truth));
  const board = $("#board");
  const rows = LA.rank.map((c) => {
    const li = document.createElement("li");
    li.className = (c === champ ? "champ " : "") + (c.includes("-on-") ? "dodge" : "");
    li.innerHTML = `<span class="rk"></span><span class="nm">${cfgName(c)}</span><span class="bar"></span><span class="sc"></span>`;
    board.appendChild(li);
    return [c, li];
  });
  let topDodge = 0; while (topDodge < LB.rank.length && LB.rank[topDodge].includes("-on-")) topDodge++;
  $("#dodge-note").textContent = `Dodging still helped: the top ${WORDS[topDodge]} setups in the new world all dodge.`;
  const place = (L, n) => rows.forEach(([c, li]) => {
    const r = L.rank.indexOf(c);
    li.style.top = `calc(${r} * 2.1rem)`;
    li.querySelector(".rk").textContent = "#" + (r + 1);
    li.querySelector(".bar").style.width = (L.truth[c] / maxS) * 100 + "%";
    li.querySelector(".sc").textContent = Math.round(L.truth[c]);
  });
  handlers.change = {
    active(on) { if (!on) [va, vb].forEach((v) => v.pause()); else handlers.change.step(Math.max(0, cur)); },
    step(k) {
      cur = k;
      playOnly([va, vb], k < 1 ? va : vb);
      const stage = $("#change .stage");
      place(k >= 2 ? LB : LA);
      stage.classList.toggle("shifted", k >= 2);
      stage.classList.toggle("dodge-lit", k >= 3);
      $("#board-eyebrow").textContent = k >= 2 ? "new world · the same setups, re-measured" : "old world · true mean score of each setup";
    },
  };
}

// ---------- 8. ancestors ----------
{
  const C = R.challenge, I = C.inherited;
  $("#fc-inh").textContent = `mean ${Math.round(I.mean)} · ${I.games} games · ${I.status}`;
  $("#fc-now").textContent = `mean ${Math.round(C.mean_now)} · ${C.games_now} games · 95% CI ${C.ci95_now[0]}–${C.ci95_now[1]}`;
  const P = Object.entries(C.probabilities).sort((a, b) => b[1] - a[1]);
  $("#fc-probs").innerHTML = `<p class="eyebrow" style="margin:0 0 .4rem">JEV · which inherited finding is most contradicted?</p>` +
    P.map(([k, p], i) => `<div class="prob ${i === 0 ? "lead" : ""}"><span>${k === "NONE" ? "none yet" : cfgName(k)}</span><span class="pb"><i data-w="${p}"></i></span><span class="pv">${p.toFixed(2)}</span></div>`).join("");
  $("#fc-cap").textContent = `A real decision, logged in the Tenki validation (trial ${C.trial}, round ${C.round + 1} after the change, ${Math.round(C.latency_ms)} ms). A CHALLENGED finding stops counting, so the swarm explores again.`;
  handlers.ancestors = {
    step(k) {
      $$("#fc-probs i").forEach((i) => (i.style.width = k >= 3 ? i.dataset.w * 100 + "%" : "0%"));
      $("#fcard").classList.toggle("challenged", k >= 3);
      $("#fc-status b").textContent = k >= 3 ? "CHALLENGED" : "ACTIVE";
    },
  };
}

// ---------- 9. real ----------
{
  const T = $("#topo");
  const box = (x, y, w, h, label, color, sub) => {
    const g = svg("g", { transform: `translate(${x},${y})` }, T);
    svg("rect", { width: w, height: h, rx: 3, fill: "#0d0f11", stroke: color }, g);
    svg("text", { x: 14, y: 24, fill: color }, g).textContent = label;
    if (sub) svg("text", { x: 14, y: 42, fill: "#928c80" }, g).textContent = sub;
    return g;
  };
  const line = (x1, y1, x2, y2, c) => svg("path", { d: `M${x1},${y1} L${x2},${y2}`, stroke: c, "stroke-dasharray": "3 5", fill: "none" }, T);
  line(500, 110, 160, 60, "#e7a64a"); line(500, 110, 840, 60, "#86d99d");
  [0, 1, 2, 3].forEach((k) => line(500, 140, 40 + k * 240 + 90, 260, "#a9c6ff"));
  box(390, 70, 220, 70, "TENKI COORDINATOR", "#a9c6ff", "round loop · no games");
  box(40, 30, 240, 60, "MITOSIS", "#e7a64a", "shared findings");
  box(720, 30, 240, 60, "JEV", "#86d99d", "typed judgments");
  const gens = [1, 1, 1, 1];
  const workers = [0, 1, 2, 3].map((k) => box(40 + k * 240, 260, 180, 80, `WORKER 0${k + 1}`, "#a9c6ff", "gen 1"));
  svg("text", { x: 500, y: 390, fill: "#928c80", "text-anchor": "middle" }, T).textContent = "workers play every game · hold no keys · are destroyed on schedule";
  let timer = 0, j = 0;
  handlers.real = {
    active(on) { if (!on) clearInterval(timer); },
    step(k) {
      clearInterval(timer);
      if ((k === 1 || k === 2) && !REDUCE) timer = setInterval(() => {
        const w = workers[j % 4], r = w.querySelector("rect"), sub = w.querySelectorAll("text")[1];
        r.setAttribute("stroke", "#e5603a"); w.style.opacity = 0.2;
        const idx = j % 4; j++;
        setTimeout(() => { gens[idx]++; sub.textContent = `gen ${gens[idx]} · born empty`; r.setAttribute("stroke", "#a9c6ff"); w.style.opacity = 1; }, 600);
      }, 1100);
      drawRetrieval(k);
    },
  };
  // schematic: one shared feed holds every trial's findings; a top-k search returns a slice
  const RT = $("#retrieval");
  const trials = R.validation.trials, per = 12, dots = [];
  for (let t = 0; t < trials; t++) for (let i = 0; i < per; i++) {
    const own = t === 3;
    dots.push({ own, el: svg("circle", { cx: 60 + t * 50 + (i % 3) * 13, cy: 60 + Math.floor(i / 3) * 22, r: 4.5, class: "dot", fill: own ? "#e7a64a" : "#6b6558" }, RT) });
  }
  svg("text", { x: 60, y: 30 }, RT).textContent = `ONE MITOSIS FEED · FINDINGS FROM ${trials} PARALLEL TRIALS · SCHEMATIC`;
  svg("rect", { x: 200, y: 47, width: 46, height: 90, fill: "none", stroke: "#e7a64a", "stroke-opacity": .5 }, RT);
  svg("text", { x: 60, y: 175 }, RT).textContent = "one trial's own findings are highlighted; a top-k search returns only some of them";
  svg("text", { x: 60, y: 200 }, RT).textContent = `median missing per read: ${R.validation.mitosis.versions_behind_median} · reads missing at least one: ${fmt(R.validation.mitosis.stale_read_rate, "pct")}`;
  const own = dots.filter((d) => d.own);
  function drawRetrieval(k) {
    own.forEach((d, i) => { d.el.classList.toggle("got", k >= 5 && i % 4 !== 1); d.el.classList.toggle("miss", k >= 5 && i % 4 === 1); });
  }
}

// ---------- reveal-on-scroll for flowing sections ----------
const io = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && e.target.classList.add("seen")), { threshold: 0.2 });
$$(".r").forEach((el) => io.observe(el));

// ---------- receipts ----------
function table(head, rows) {
  return `<table><thead><tr>${head.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c, i) => `<td class="${i && typeof c === "number" ? "n" : ""}">${typeof c === "number" ? fmt(c, Number.isInteger(c) ? "int" : "1") : c}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}
function srcLine(key) {
  const files = SOURCES[key] || [];
  return `<p class="src">source: ${files.map((f) => { const p = f.split(" ")[0]; return REPO_URL && !p.includes("*") ? `<a href="${REPO_URL}/blob/main/${p}">${f}</a>` : `<code>${f}</code>`; }).join(" · ")}</p>`;
}
const ci = (a) => `${fmt(a[0], "1")} [${fmt(a[1][0], "1")}, ${fmt(a[1][1], "1")}]`;
const TABS = {
  pilot: ["Pilot", () => `
    <h4>Holdout: 100 seeds drawn once, never used in development, run once</h4>
    ${$("#pilot-receipt").innerHTML}`],
  swarm: ["Swarm", () => {
    const C = R.swarm.conditions;
    return `<h4>Main run · pre-registered · ${R.swarm.trials} paired trials per condition · ${R.swarm.W} workers, ${R.swarm.R} rounds per game version, retired every ${R.swarm.L} rounds</h4>
    ${table(["condition", "before the change", "after the change"], Object.keys(C).map((k) => [C[k].name, ci(C[k].ph1), ci(C[k].ph2)]))}
    <p>Average points the swarm's current pick is below the best setup, per round (lower is better). Brackets: 95% bootstrap intervals. Games are replayed from ${fmt(R.swarm.landscape_games, "int")} real games played on Tenki.</p>
    <p><b>Memory helps first:</b> ${ci(R.swarm.benefit_ph1.diff)} (memory better in ${R.swarm.benefit_ph1.x_better_trials}/${R.swarm.benefit_ph1.n}). <b>Then it drags:</b> +${ci(R.swarm.drag_ph2.diff)}. <b>JEV removed the drag:</b> JEV + memory vs JEV alone after the change ${ci(R.swarm.jev_drag_ph2.diff)}. <b>The rule did slightly better:</b> JEV − rule over the whole run ${ci(R.swarm.jev_vs_rule_total.diff)}, rule better in ${R.swarm.jev_vs_rule_total.y_better_trials}/${R.swarm.jev_vs_rule_total.n}.</p>
    <svg class="chart" id="chart-full" viewBox="0 0 1000 440" style="max-width:980px;margin-top:1.4rem"></svg>
    <h4>The two game versions (true mean per setup, without bonus ship)</h4>
    ${table(["setup", "standard game", "rank", "variation 1", "rank"], R.landscape.A.rank.map((c) => [cfgName(c), R.landscape.A.truth[c], "#" + (R.landscape.A.rank.indexOf(c) + 1), R.landscape.B.truth[c], "#" + (R.landscape.B.rank.indexOf(c) + 1)]))}
    ${srcLine("swarm")}${srcLine("landscape")}`;
  }],
  tenki: ["Tenki", () => {
    const t = R.validation.tenki, a = R.validation.attempts_totals, o = R.validation.official_replay;
    return `<h4>Distributed validation (run v4)</h4>
    ${table(["", ""], [
      ["sandboxes", `1 coordinator + ${t.worker_sandboxes_created} workers (${t.sandboxes_total})`],
      ["worker generations per slot", Object.values(t.generations_per_slot).join(" / ")],
      ["replacements", `${t.planned_replacements} planned, ${t.unplanned_replacements} unplanned`],
      ["games", fmt(t.games, "int")],
      ["worker jobs", `${t.worker_jobs_ok} ok · ${t.retries} retried call`],
      ["wall time", `${fmt(t.wall_s, "int")} s`],
      ["throughput", `${t.games_per_sandbox_second} games per sandbox-second`],
      ["compute cost (estimate)", "$" + t.cost_usd_estimate.total.toFixed(2)],
      ["birth audit", t.birth_audit_all_empty ? "every new worker started empty; no secret env names on workers" : "see file"],
      ["replay", `${R.validation.replay.matched}/${R.validation.replay.sampled} sampled games re-derived locally across ${R.validation.replay.sandboxes_covered} sandboxes`],
    ])}
    <h4>All attempts</h4>
    ${table(["run", "what happened", "games on Tenki", "sandboxes"], R.validation.attempts.map((x) => [x.run, x.what, x.games_played_on_tenki, x.sandboxes]))}
    <p>Total: ${fmt(a.games_played_on_tenki, "int")} games on Tenki, ${a.sandboxes} sandboxes, about $${a.cost_usd_estimate.toFixed(2)}. Three runs stopped on infrastructure (a timeout, HTTP 502s, then about seven minutes with no capacity). The fixes: detached batches, short retried polls, failure-tolerant orchestration.</p>
    <h4>Replay CI</h4>
    <p>Every official game re-derived from seed and action log in clean Tenki sandboxes, no model and no key: <b>${o.matched}/${o.games}</b> matched in ${fmt(o.wall_s, "0")} s for $${o.compute_cost_usd_estimate.toFixed(3)}.</p>
    ${srcLine("validation")}`;
  }],
  mitosis: ["Mitosis", () => {
    const m = R.validation.mitosis;
    return `<h4>Main run</h4><p><b>${fmt(R.swarm.mitosis_calls, "int")}</b> Mitosis calls. Findings (setup, game version, games, mean, interval, status, provenance) are the only way knowledge survives a worker's retirement; without them, search error before the change is ${fmt(R.swarm.conditions.A.ph1[0], "0")} instead of ${fmt(R.swarm.conditions.B.ph1[0], "0")}.</p>
    <h4>Distributed validation: the read path</h4>
    ${table(["", ""], [
      ["reads missing ≥1 of the trial's own acknowledged findings", `${m.reads_behind}/${m.reads_with_acked_findings} (${fmt(m.stale_read_rate, "pct")})`],
      ["findings missing, summed over reads", m.stale_findings],
      ["returned findings that were an older version", m.unknown_versions],
      ["missing per read", `median ${m.versions_behind_median}, max ${m.versions_behind_max}`],
      ["allocation would differ with the full surface (JEV + memory rounds)", `${m.stale_rounds_allocation_would_differ.D[0]}/${m.stale_rounds_allocation_would_differ.D[1]}`],
      ["JEV challenge judgment would differ (upper bound)", `${m.stale_rounds_jev_judgment_would_differ.challenge[0]}/${m.stale_rounds_jev_judgment_would_differ.challenge[1]}`],
    ])}
    <p>Our adapter read a trial's findings with a search call that returns its top matches, over one feed shared by ${R.validation.trials} parallel trials. That access pattern, not storage, was the bottleneck: nothing returned was out of date; findings were simply not returned. Counterfactuals were computed on the full surface and never acted on.</p>
    ${srcLine("validation")}`;
  }],
  audit: ["JEV audit", () => {
    const s = R.audit.structure, o = R.audit.order;
    return `<h4>Three separate requests vs one request with three questions (same saved states)</h4>
    ${table(["question", "separate vs batched", "separate vs separate (repeat)"], ["mode", "memory", "stop"].map((q) => [q, fmt(s[q].separate_vs_batched.agreement, "pct"), fmt(s[q].separate_vs_separate.agreement, "pct")]))}
    <p>Batched: ${fmt(s.per_round.batched.input_tokens_mean, "int")} vs ${fmt(s.per_round.separate.input_tokens_mean, "int")} input tokens, ${fmt(s.per_round.batched.latency_ms_p50, "0")} vs ${fmt(s.per_round.separate.latency_ms_p50_sum, "0")} ms. The frozen validation kept the original three requests.</p>
    <h4>Option order (permuted, same saved states)</h4>
    ${table(["question", "flip rate", "repeat noise", "mean prob. drift (max)"], ["mode", "memory", "stop"].map((q) => [q === "mode" ? "explore / coordinate" : q === "memory" ? "which finding is contradicted" : "stop", fmt(o[q].flip_rate, "pct"), fmt(o[q].same_order_repeat_flip_rate, "pct"), `${o[q].prob_drift_mean.toFixed(3)} (${o[q].prob_drift_max})`]))}
    <p>The explore / coordinate states were deliberately borderline (saved transition states), so that flip rate overstates the typical case. The governor acts on the top answer only, so a crossing is a flip. The API's <code>confidence</code> field is a spread summary, (p_max − 1/K)/(1 − 1/K), not a probability of being right; everything here uses the returned distributions.</p>
    <h4>Stop, against truth</h4><p>JEV never said stop (mean p(yes) ${R.validation.stop_question.mean_p_yes.toFixed(3)}), whether or not the leader was truly best.</p>
    ${srcLine("audit")}`;
  }],
  repro: ["Reproduce", () => `
    <h4>No key needed</h4>
    <pre class="cmd">pip install -r requirements.txt</pre>
    <pre class="cmd">python -m ufa.verify_replay check replays/holdout.json</pre>
    <pre class="cmd">python -m ufa.ci_check --results results.json --replays replays/holdout.json</pre>
    <p>Re-derives every official score from its seed and action log and checks <code>results.json</code> against the replays. A tampered score makes <code>ci_check</code> exit 1.</p>
    <pre class="cmd">python -m ufa.squad.swarm_analysis --run s1</pre>
    <pre class="cmd">python -m ufa.squad.swarm_validation --run v4</pre>
    <h4>This page</h4>
    <pre class="cmd">python site/tools/build_data.py</pre>
    <p>Regenerates <code>site/data/results.js</code>, the only source of numbers on this page, from the committed files. Footage: <code>python site/tools/render_footage.py</code> replays recorded games in the emulator and refuses to write a clip whose score doesn't match the record.</p>
    <p class="src">science frozen at commit <code>${R.validation.freeze_commit}</code> (<code>ufa/squad/swarm/validation/FREEZE.json</code>)</p>`],
  limits: ["Limitations", () => `
    <ul class="lim">
      <li><b>The swarm's players are rule-based setups.</b> JEV governs the swarm; it does not fly the ship there.</li>
      <li><b>One game change</b> (standard game → variation 1).</li>
      <li><b>The simple rule beat the JEV governor</b> (better in ${R.swarm.jev_vs_rule_total.y_better_trials}/${R.swarm.jev_vs_rule_total.n} trials overall). We wrote the rule alongside JEV's questions.</li>
      <li><b>The distributed JEV recovery did not replicate:</b> after the change, JEV + memory ${fmt(R.validation.D.ph2[0], "0")} vs ${fmt(R.validation.E.ph2[0], "0")} without memory.</li>
      <li><b>Our Mitosis retrieval adapter was incomplete under parallel trials</b> (${fmt(R.validation.mitosis.stale_read_rate, "pct")} of reads missed a finding), which confounds the distributed governance result.</li>
      <li><b>Only ${R.validation.trials} paired trials</b> per condition in the distributed validation.</li>
      <li><b>Option order changes borderline choices</b> (explore / coordinate ${fmt(R.audit.order.mode.flip_rate, "pct")} flips on borderline states vs ${fmt(R.audit.order.mode.same_order_repeat_flip_rate, "pct")} repeat noise).</li>
      <li><b>Turn-based Haiku comparison is ${R.pilot.haiku_games} games</b>, limited by cost. In real time JEV scores lower (${fmt(R.pilot.rt_jev_mean, "0")}).</li>
      <li><b><code>move_is_safe</code> is hand-written code</b>, a 12-step projection from measured physics. JEV chooses every move; code computes the facts it sees.</li>
      <li><b>JEV is not deterministic.</b> Replays prove the recorded games; new runs vary around the mean.</li>
    </ul>`],
};
{
  const tabs = $("#tabs"), panel = $("#panel");
  const show = (key) => {
    $$("button", tabs).forEach((b) => b.setAttribute("aria-selected", b.dataset.k === key));
    panel.innerHTML = TABS[key][1]();
    const cf = $("#chart-full", panel);
    if (cf) { const c = chart(cf, R.swarm.curves, ["A", "B", "D", "F"], { labels: { A: "no memory", B: "memory", D: "JEV + memory", F: "rule + memory" } }); ["A", "B", "D", "F"].forEach((k) => c.show(k, 2)); c.band(true); }
  };
  for (const [k, [label]] of Object.entries(TABS)) {
    const b = document.createElement("button");
    b.textContent = label; b.dataset.k = k; b.setAttribute("role", "tab");
    b.onclick = () => show(k);
    tabs.appendChild(b);
  }
  show("pilot");
  $$("a[data-tab]").forEach((a) => a.addEventListener("click", () => show(a.dataset.tab)));
  const code = $("#cta-code");
  if (REPO_URL) code.href = REPO_URL; else code.classList.add("off");
}

// ---------- deep links (?at=scene.step) ----------
function scrollToStep(id, step) {
  const s = scenes.find((x) => x.id === id);
  const span = s.el.offsetHeight - innerHeight;
  return s.el.offsetTop + span * ((step + 0.5) / s.steps);
}
// ---------- boot ----------
fillValues();
addEventListener("scroll", onScroll, { passive: true });
addEventListener("resize", onScroll);
onScroll();
const Q = new URLSearchParams(location.search);
if (Q.get("shot")) {
  // screenshot mode: render one beat on its own, no scrolling (headless capture ignores scroll)
  const [id, st] = Q.get("shot").split(".");
  removeEventListener("scroll", onScroll); removeEventListener("resize", onScroll);
  for (const sec of $$("main > section")) if (sec.id !== id) sec.style.display = "none";
  const s = scenes.find((x) => x.id === id);
  if (s) {
    s.el.style.height = "100vh"; s.el.querySelector(".stage").style.position = "relative";
    s.step = +st || 0; applyBeats(s); handlers[id]?.active?.(true, s); handlers[id]?.step?.(s.step, s);
  } else $$(".r").forEach((el) => el.classList.add("seen"));
  scrollTo(0, 0);
} else if (Q.get("demo") === "1") import("./demo.js");  // the curated presentation cut
else if (Q.get("at")) {
  const [id, st] = Q.get("at").split(".");
  const target = scenes.find((x) => x.id === id) ? scrollToStep(id, +st || 0) : ($("#" + id)?.offsetTop ?? 0);
  requestAnimationFrame(() => { scrollTo(0, target); onScroll(); $$(".r").forEach((el) => { const r = el.getBoundingClientRect(); if (r.top < innerHeight) el.classList.add("seen"); }); });
}
