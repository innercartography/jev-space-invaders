// The presentation cut (?demo=1). A separate layer over the page: one idea per scene,
// large type, one number at a time. Every number comes from R (data/results.js).
//   ?demo=1               autoplay
//   ?demo=1&autoplay=0    each scene plays its beats, then waits for →
//   ?demo=1&scene=4&t=9   start at scene 4 (0-based), 9 s in (used for stills; add &still=1 to freeze)
// Keys: Space pause/resume · → next scene · ← previous scene · Esc exit
import { R } from "./data/results.js";

const Q = new URLSearchParams(location.search);
const AUTOPLAY = Q.get("autoplay") !== "0";
const STILL = Q.has("still");
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const NS = "http://www.w3.org/2000/svg";
const r0 = (v) => String(Math.round(v));
const wins = (s) => { const [w, t, l] = s.split("/").map(Number); return `${w}/${w + t + l}`; };
const WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
const svgEl = (tag, attrs = {}, parent) => {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (parent) parent.appendChild(el);
  return el;
};

// ---------- numbers used in the cut (all derived from R) ----------
const C = R.swarm.conditions;
const N = {
  mean: r0(R.pilot.mean),
  speed: String(Math.floor(R.pilot.speed_ratio)),
  rt: wins(R.pilot.rt_vs_haiku_wtl),
  noMem1: C.A.ph1[0], mem1: C.B.ph1[0],
  cut: Math.round((1 - C.B.ph1[0] / C.A.ph1[0]) * 100),
  better: `${R.swarm.benefit_ph1.x_better_trials}/${R.swarm.benefit_ph1.n}`,
  noMem2: C.A.ph2[0], mem2: C.B.ph2[0], jev2: C.D.ph2[0], rule2: C.F.ph2[0],
  champ: R.landscape.A.rank[0],
  games: R.validation.tenki.games.toLocaleString("en-US"),
  replay: `${R.validation.official_replay.matched}/${R.validation.official_replay.games}`,
  L: WORDS[R.swarm.L], W: WORDS[R.swarm.W],
};
N.champOld = R.landscape.A.truth[N.champ];
N.champNew = R.landscape.B.truth[N.champ];
N.rankNew = R.landscape.B.rank.indexOf(N.champ) + 1;
const CH = R.challenge;
N.pChal = CH.probabilities[CH.choice];
const sweep = R.ladder.find((x) => /sweep bot/i.test(x.belief));
N.sweepDiff = (sweep.evidence.match(/(-?\d+) \[/) || [])[1];
N.sweepSeeds = (sweep.evidence.match(/(\d+) new seeds/) || [])[1];

// ---------- helpers ----------
function tween(el, from, to, ms, fmt = r0) {
  if (STILL) { el.textContent = fmt(to); return; }
  const t0 = performance.now();
  const f = () => {
    const k = Math.min(1, (performance.now() - t0) / ms), e = 1 - Math.pow(1 - k, 3);
    el.textContent = fmt(from + (to - from) * e);
    if (k < 1) setTimeout(f, 16);
  };
  f();
}
function chart(host) {
  const svg = svgEl("svg", { viewBox: "0 0 1000 520", class: "d-chart" }, host);
  const rounds = 30, ph = 15, L = 20, Rt = 250, T = 30, B = 70, ymax = 200;
  const x = (i) => L + (i / (rounds - 1)) * (1000 - L - Rt), y = (v) => T + (1 - v / ymax) * (520 - T - B);
  const band = svgEl("rect", { x: x(ph - 0.5), y: T, width: x(rounds - 1) - x(ph - 0.5), height: 520 - T - B, class: "d-band" }, svg);
  svgEl("line", { x1: x(ph - 0.5), x2: x(ph - 0.5), y1: T, y2: 520 - B, class: "d-axis" }, svg);
  svgEl("line", { x1: L, x2: x(rounds - 1), y1: 520 - B, y2: 520 - B, class: "d-axis" }, svg);
  svgEl("text", { x: x(ph / 2 - 0.5), y: 520 - 26, "text-anchor": "middle", class: "d-ax" }, svg).textContent = "same game";
  svgEl("text", { x: x(ph + (rounds - ph) / 2 - 0.5), y: 520 - 26, "text-anchor": "middle", class: "d-ax shift" }, svg).textContent = "world changed";
  const lines = {};
  for (const [k, cls, label] of [["A", "nomem", "no memory"], ["B", "mem", "shared memory"]]) {
    const seg = (a, b) => {
      const p = svgEl("polyline", { points: R.swarm.curves[k].slice(a, b).map((v, i) => `${x(a + i)},${y(v)}`).join(" "), class: `d-line ${cls}` }, svg);
      const len = p.getTotalLength(); p.style.strokeDasharray = `${len} ${len}`; p.style.strokeDashoffset = len;
      return p;
    };
    const t1 = svgEl("text", { x: x(ph - 1) + 12, y: y(R.swarm.curves[k][ph - 1]) + 8, class: `d-lbl ${cls}` }, svg);
    const t2 = svgEl("text", { x: x(rounds - 1) + 12, y: y(R.swarm.curves[k][rounds - 1]) + 8, class: `d-lbl ${cls}` }, svg);
    t1.textContent = t2.textContent = label;
    lines[k] = { a: seg(0, ph), b: seg(ph - 1, rounds), t1, t2 };
  }
  return {
    phase1() { for (const l of Object.values(lines)) { l.a.style.strokeDashoffset = 0; l.t1.classList.add("in"); } },
    phase2() { band.classList.add("in"); for (const l of Object.values(lines)) { l.a.style.strokeDashoffset = 0; l.b.style.strokeDashoffset = 0; l.t1.classList.remove("in"); l.t2.classList.add("in"); } },
  };
}
const cfgShort = (c) => { const [mv, d] = c.split("-"); return `${mv} + ${d === "on" ? "dodge" : "no dodge"}`; };

// ---------- scenes: [seconds, html, beats(root) -> [[t, fn]...]] ----------
const SCENES = [
  { name: "Hook", dur: 10.5, html: `
    <div class="d-cols">
      <div class="d-slots">
        <p class="d-big d-el" data-k="q1">Can a fast model play Space&nbsp;Invaders? <span class="d-yes d-el" data-k="y1">Yes.</span></p>
        <p class="d-big d-el" data-k="q2">Can experience make it better? <span class="d-yes d-el" data-k="y2">Yes.</span></p>
        <p class="d-big d-el" data-k="q3">Can what it learned become wrong? <span class="d-yes d-el" data-k="y3">Yes.</span></p>
        <h1 class="d-huge d-el" data-k="th">Memory helps.<br><em class="d-el" data-k="th2">Until the world changes.</em></h1>
      </div>
      <figure class="d-screen"><video src="assets/pilot.mp4" muted playsinline loop autoplay></video>
        <figcaption>recorded replay · JEV playing</figcaption></figure>
    </div>`,
    beats: (s) => [[0.3, s.on("q1")], [1.4, s.on("y1")], [2.6, s.swap("q1", "q2")], [3.6, s.on("y2")], [4.8, s.swap("q2", "q3")], [5.8, s.on("y3")],
      [7.0, s.swap("q3", "th")], [8.1, s.on("th2")]] },

  { name: "Pilot", dur: 12, html: `
    <div class="d-cols flip">
      <figure class="d-screen"><video src="assets/pilot.mp4" muted playsinline loop autoplay></video><div class="d-act">NOOP</div>
        <figcaption>recorded replay · every move chosen by JEV</figcaption></figure>
      <div class="d-slots">
        <div class="d-el" data-k="a"><p class="d-num jev" data-k="mean">0</p><p class="d-cap">average score · ${R.pilot.holdout_games} untouched seeds</p></div>
        <div class="d-el" data-k="b"><p class="d-num jev">${N.speed}×</p><p class="d-cap">faster per decision than Haiku 4.5</p></div>
        <div class="d-el" data-k="c"><p class="d-num jev">${N.rt}</p><p class="d-cap">real-time head-to-head wins vs Haiku 4.5</p>
          <p class="d-line d-el" data-k="line">JEV could make a decision while the frame still&nbsp;mattered.</p></div>
      </div>
    </div>`,
    beats: (s) => [[0.3, () => { s.on("a")(); tween(s.k("mean"), 0, R.pilot.mean, 1500); }], [3.8, s.swap("a", "b")], [7.0, s.swap("b", "c")], [8.6, s.on("line")]],
    start: (root) => syncActions($("video", root), $(".d-act", root)) },

  { name: "Falsified", dur: 12, html: `
    <div class="d-center">
      <div class="d-slots">
        <div class="d-el" data-k="a"><p class="d-big">Same model. Same game.</p><p class="d-big d-el" data-k="a2">Different representation.</p><p class="d-big d-el jev" data-k="a3">Different policy.</p></div>
        <div class="d-el" data-k="b">
          <div class="d-lane"><span class="d-tag shift">raw state → fire jitter</span><div class="d-track" data-k="raw"><i class="d-ship"></i></div></div>
          <div class="d-lane"><span class="d-tag jev">compressed state → persistent motion</span><div class="d-track" data-k="comp"><i class="d-ship"></i></div></div>
          <p class="d-note">motion driven by each view's measured reversal and fire rates</p>
        </div>
        <div class="d-el" data-k="c">
          <div class="d-lane"><span class="d-tag">sweep bot · no model</span><div class="d-track sweep"><i class="d-ship dim"></i></div></div>
          <p class="d-big">The dumb rule tied&nbsp;it.</p>
          <p class="d-cap">${N.sweepSeeds} fresh seeds · JEV ${N.sweepDiff.replace("-", "−")} points vs the sweep bot</p>
          <p class="d-line d-el" data-k="line">High score wasn't enough evidence of understanding.</p>
        </div>
      </div>
    </div>`,
    beats: (s) => [[0.3, s.on("a")], [1.6, s.on("a2")], [2.8, s.on("a3")], [4.4, s.swap("a", "b")], [7.6, s.swap("b", "c")], [9.4, s.on("line")]],
    start: (root) => jitter(root) },

  { name: "Swarm", dur: 17, html: `
    <div class="d-full">
      <svg class="d-swarm" viewBox="0 0 1000 600" data-k="svg"></svg>
      <div class="d-over">
        <p class="d-big d-el" data-k="five">${N.L[0].toUpperCase() + N.L.slice(1)} rounds later…</p>
        <div class="d-el d-slogan" data-k="slo"><p><span class="tenki">Tenki</span> gave the swarm bodies.</p><p class="d-el" data-k="slo2"><span class="mem">Mitosis</span> gave it inheritance.</p></div>
        <p class="d-huge d-el" data-k="forgot">The workers forgot.<br><em>The swarm didn't.</em></p>
      </div>
    </div>`,
    beats: (s) => {
      const sw = swarm(s.k("svg"));
      return [[0.3, sw.birth(1)], [2.2, sw.mitosis], [2.6, sw.chip(0)], [3.3, sw.chip(1)], [4.0, sw.chip(2)], [4.7, sw.chip(3)],
        [6.0, s.on("five")], [7.0, sw.kill], [9.4, () => { s.off("five")(); sw.birth(2)(); }], [10.4, sw.inherit],
        [11.6, () => { s.on("slo")(); sw.dim(); }], [12.9, s.on("slo2")], [14.6, s.swap("slo", "forgot")]];
    },
    stop: () => clearInterval(swarmTimer) },

  { name: "Memory helps", dur: 9.5, html: `
    <div class="d-cols flip">
      <div>
        <div class="d-row d-el" data-k="a"><span class="d-lab">No memory</span><span class="d-n">${r0(N.noMem1)}</span></div>
        <div class="d-row mem d-el" data-k="b"><span class="d-lab">Shared memory</span><span class="d-n" data-k="bn">${r0(N.noMem1)}</span></div>
        <p class="d-line d-el" data-k="cut">${N.cut}% less search error.</p>
        <p class="d-cap d-el" data-k="tr">${N.better} trials improved</p>
      </div>
      <div data-k="chart"></div>
    </div>`,
    beats: (s) => { const c = chart(s.k("chart")); return [[0.3, () => { s.on("a")(); c.phase1(); }], [1.3, () => { s.on("b")(); tween(s.k("bn"), N.noMem1, N.mem1, 1600); }], [4.0, s.on("cut")], [6.4, s.on("tr")]]; } },

  { name: "Change the world", dur: 12, html: `
    <div class="d-cols">
      <div class="d-slots">
        <figure class="d-screen d-el" data-k="scr"><video data-k="va" src="assets/regime_A.mp4" muted playsinline loop autoplay></video><video data-k="vb" class="d-el" src="assets/regime_B.mp4" muted playsinline loop></video>
          <figcaption data-k="cap">the standard game</figcaption></figure>
        <div class="d-el" data-k="chart"></div>
      </div>
      <div class="d-slots">
        <div class="d-el d-champ" data-k="champ">
          <p class="d-cap" data-k="world">old world · the best setup</p>
          <p class="d-num" data-k="rank">#1</p>
          <p class="d-big mem" data-k="name">${cfgShort(N.champ)}</p>
          <p class="d-score" data-k="score">${r0(N.champOld)}</p>
        </div>
        <div class="d-el" data-k="drag">
          <div class="d-row"><span class="d-lab">No memory</span><span class="d-n">${r0(N.noMem2)}</span></div>
          <div class="d-row bad"><span class="d-lab">Inherited memory</span><span class="d-n">${r0(N.mem2)}</span></div>
          <p class="d-big d-el" data-k="inertia"><em>Inheritance became inertia.</em></p>
        </div>
      </div>
    </div>`,
    beats: (s) => {
      let c;
      return [[0.2, () => { s.on("scr")(); s.on("champ")(); c = chart(s.k("chart")); c.phase1(); }],
        [3.0, () => { s.on("vb")(); s.k("vb").play().catch(() => {}); s.k("cap").textContent = "variation 1 · the shields move"; s.k("cap").classList.add("shift");
          s.k("world").textContent = "new world · same setup"; s.k("champ").classList.add("fallen");
          tween(s.k("rank"), 1, N.rankNew, 1400, (v) => "#" + Math.round(v)); tween(s.k("score"), N.champOld, N.champNew, 1400); }],
        [6.8, () => { s.swap("champ", "drag")(); s.swap("scr", "chart")(); setTimeout(() => c.phase2(), 300); }], [9.2, s.on("inertia")]];
    } },

  { name: "Change its mind", dur: 10.5, html: `
    <div class="d-center">
      <div class="d-slots">
        <div class="d-el d-card" data-k="card">
          <p class="d-cap">one inherited Mitosis finding</p>
          <p class="d-big mem d-strike" data-k="name">${cfgShort(CH.choice)}</p>
          <div class="d-kv"><span>inherited</span><b>${r0(CH.inherited.mean)}</b></div>
          <div class="d-kv d-el" data-k="now"><span>this world</span><b>${r0(CH.mean_now)}</b></div>
          <div class="d-kv d-el" data-k="p"><span>JEV · contradicted</span><span class="d-pb"><i data-k="pb"></i></span><b>p ${N.pChal.toFixed(2)}</b></div>
          <p class="d-status">status: <b data-k="st">ACTIVE</b></p>
          <p class="d-note">a real JEV decision, logged on Tenki (trial ${CH.trial})</p>
        </div>
        <div class="d-el" data-k="res">
          <div class="d-row jev"><span class="d-lab">JEV + memory</span><span class="d-n">${r0(N.jev2)}</span></div>
          <div class="d-row"><span class="d-lab">Simple rule + memory</span><span class="d-n">${r0(N.rule2)}</span></div>
          <p class="d-huge d-el" data-k="beat">The rule beat JEV.</p>
          <p class="d-cap d-el" data-k="good">Good. The experiment was supposed to teach us something.</p>
        </div>
      </div>
    </div>`,
    beats: (s) => [[0.3, s.on("card")], [1.8, s.on("now")], [3.2, () => { s.on("p")(); s.k("pb").style.width = N.pChal * 100 + "%"; }],
      [4.6, () => { s.k("st").textContent = "CHALLENGED"; s.k("card").classList.add("chal"); }],
      [6.2, s.swap("card", "res")], [7.6, s.on("beat")], [8.6, s.on("good")]] },

  { name: "Final validation", dur: 13, html: `
    <div class="d-full">
      <svg class="d-topo d-el" viewBox="0 0 1000 380" data-k="topo"></svg>
      <div class="d-bottom d-slots">
        <div class="d-el" data-k="g"><p class="d-num tenki">${N.games}</p><p class="d-cap">Tenki games in the distributed validation</p></div>
        <div class="d-el" data-k="r"><p class="d-num tenki">${N.replay}</p><p class="d-cap">official games independently replayed</p></div>
      </div>
      <div class="d-over d-slots">
        <div class="d-el" data-k="nr"><p class="d-big shift">The original JEV recovery did not&nbsp;replicate.</p>
          <p class="d-line">Our retrieval path was returning only part of the inherited memory.</p></div>
        <p class="d-huge d-el" data-k="th">Memory isn't only what you store.<br><em>It's what you can recover when it matters.</em></p>
      </div>
    </div>`,
    beats: (s) => { const t = topo(s.k("topo")); return [[0.2, () => { s.on("topo")(); t.start(); }], [1.0, s.on("g")], [3.8, s.swap("g", "r")],
      [6.6, () => { s.off("topo")(); s.off("r")(); t.stop(); }], [7.2, s.on("nr")], [10.2, s.swap("nr", "th")]]; },
    stop: () => clearInterval(topoTimer) },

  { name: "Close", dur: 8.5, html: `
    <div class="d-center d-close">
      <svg class="d-shipbig d-el" data-k="ship" viewBox="0 0 16 10"><path d="M7 0h2v2h1v1h3v1h2v6H1V4h2V3h3V2h1z"/></svg>
      <p class="d-huge d-el" data-k="a">Self-improvement isn't remembering everything.</p>
      <p class="d-huge d-el" data-k="b"><em>It's getting better at knowing what still applies.</em></p>
      <p class="d-cap d-el" data-k="c">JEV × Mitosis × Tenki</p>
      <a class="d-cta d-el" data-k="cta" href="./">Explore the full experiment ↓</a>
    </div>`,
    beats: (s) => [[0.2, s.on("ship")], [0.8, s.on("a")], [3.6, s.on("b")], [6.2, () => { s.on("c")(); s.on("cta")(); }]] },
];

// ---------- scene visuals ----------
let actTimer = 0;
function syncActions(video, label) {
  fetch("assets/pilot_actions.json").then((r) => r.json()).then((A) => {
    let last = 37;
    clearInterval(actTimer);
    actTimer = setInterval(() => {
      const i = Math.min(A.actions.length - 1, Math.floor(video.currentTime * A.fps));
      label.textContent = A.actions[i];
      const x = A.ship_x[i] ?? last; last = x;
      label.style.left = (x / A.width) * 100 + "%";
    }, 50);
  });
}
let jitTimer = 0;
function jitter(root) {
  // ships move with each view's measured behaviour: reversal probability per move and fire-while-in-flight rate
  const raw = R.representation["RAW view"], comp = R.representation["THREAT view"];
  const lanes = [[$("[data-k=raw] .d-ship", root), raw], [$("[data-k=comp] .d-ship", root), comp]].map(([el, m]) => ({ el, m, x: 50, d: 1 }));
  const sw = { el: $(".sweep .d-ship", root), x: 0, d: 1 };
  clearInterval(jitTimer);
  jitTimer = setInterval(() => {
    for (const L of lanes) {
      if (Math.random() < L.m.direction_flip_rate_per_move) L.d *= -1;
      L.x += L.d * 2.2; if (L.x < 2 || L.x > 98) { L.d *= -1; L.x = Math.max(2, Math.min(98, L.x)); }
      L.el.style.left = L.x + "%";
      L.el.classList.toggle("fire", Math.random() < L.m.p_fire_shot_in_flight * 0.5);
    }
    sw.x += sw.d * 1.6; if (sw.x < 0 || sw.x > 100) { sw.d *= -1; sw.x = Math.max(0, Math.min(100, sw.x)); }
    sw.el.style.left = sw.x + "%";
  }, 90);
}
let swarmTimer = 0;
function swarm(svg) {
  const X = [10, 260, 510, 760], W = 230, H = 160, Y = 40;
  const gen = { 1: [], 2: [] };
  const mk = (k, g) => {
    const n = svgEl("g", { class: "d-node", transform: `translate(${X[k]},${Y})` }, svg);
    svgEl("rect", { class: "d-body", width: W, height: H, rx: 4 }, n);
    svgEl("text", { x: 14, y: 26, class: "d-t tenki" }, n).textContent = `TENKI WORKER 0${k + 1}`;
    svgEl("text", { x: 14, y: 46, class: "d-t dim" }, n).textContent = g === 1 ? "generation 1" : "gen 2 · born empty";
    const al = svgEl("g", { class: "d-aliens" }, n);
    for (let r = 0; r < 3; r++) for (let c = 0; c < 5; c++) svgEl("rect", { x: 44 + c * 24, y: 62 + r * 15, width: 12, height: 7 }, al);
    svgEl("rect", { class: "d-shipr", x: 94, y: 126, width: 14, height: 7 }, n);
    const dead = svgEl("text", { x: W / 2, y: H / 2 + 8, "text-anchor": "middle", class: "d-t shift d-dead" }, n);
    dead.textContent = "terminated";
    gen[g].push(n);
    return n;
  };
  [0, 1, 2, 3].forEach((k) => { mk(k, 1); mk(k, 2); });
  const mit = svgEl("g", { class: "d-mit" }, svg);
  svgEl("rect", { x: 100, y: 440, width: 800, height: 130, rx: 4, class: "d-mitr" }, mit);
  svgEl("text", { x: 124, y: 474, class: "d-t mem big" }, mit).textContent = "MITOSIS · shared findings";
  const up = X.map((x) => svgEl("path", { d: `M500,440 C500,340 ${x + W / 2},330 ${x + W / 2},${Y + H}`, class: "d-link" }, svg));
  const F = [...R.challenge.findings].sort((a, b) => b.mean - a.mean).slice(0, 4);
  const chips = F.map((f, i) => {
    const g = svgEl("g", { class: "d-chip" }, svg);
    g.style.transform = `translate(${X[i] + 20}px, ${Y + H - 20}px)`;
    svgEl("text", { class: "d-t" }, g).textContent = `${cfgShort(f.config)} · ${Math.round(f.mean)}`;
    g.dataset.tx = 124 + (i % 2) * 400; g.dataset.ty = 512 + Math.floor(i / 2) * 34;
    return g;
  });
  let round = 0;
  return {
    birth: (g) => () => {
      gen[g].forEach((n, i) => setTimeout(() => n.classList.add("in"), STILL ? 0 : i * 180));
      clearInterval(swarmTimer);
      swarmTimer = setInterval(() => { round = (round % 5) + 1; $$(".d-aliens", svg).forEach((a) => a.setAttribute("transform", `translate(${(round % 2) * 8},0)`)); }, 600);
    },
    mitosis: () => mit.classList.add("in"),
    chip: (i) => () => {
      const c = chips[i], go = () => { c.style.transform = `translate(${c.dataset.tx}px, ${c.dataset.ty}px)`; };
      c.classList.add("in"); if (STILL) go(); else setTimeout(go, 80);
    },
    kill: () => gen[1].forEach((n, i) => setTimeout(() => { n.classList.add("dying"); setTimeout(() => n.classList.add("gone"), STILL ? 0 : 700); }, STILL ? 0 : i * 350)),
    inherit: () => { mit.classList.add("lit"); up.forEach((p) => p.classList.add("in")); },
    dim: () => svg.classList.add("dimmed"),
  };
}
let topoTimer = 0;
function topo(svg) {
  const box = (x, y, w, h, label, cls, sub) => {
    const g = svgEl("g", { transform: `translate(${x},${y})`, class: "d-box " + cls }, svg);
    svgEl("rect", { width: w, height: h, rx: 4 }, g);
    svgEl("text", { x: 16, y: 30, class: "d-t" }, g).textContent = label;
    const s = svgEl("text", { x: 16, y: 54, class: "d-t dim" }, g); s.textContent = sub || "";
    return { g, s };
  };
  const line = (x1, y1, x2, y2) => svgEl("path", { d: `M${x1},${y1} L${x2},${y2}`, class: "d-wire" }, svg);
  [0, 1, 2, 3].forEach((k) => line(500, 130, 10 + k * 250 + 115, 250));
  line(390, 95, 250, 70); line(610, 95, 750, 70);
  box(370, 60, 260, 72, "TENKI COORDINATOR", "tenki");
  box(20, 30, 230, 64, "MITOSIS", "mem");
  box(750, 30, 230, 64, "JEV", "jev");
  const gens = [1, 1, 1, 1];
  const ws = [0, 1, 2, 3].map((k) => box(10 + k * 250, 250, 230, 84, `WORKER 0${k + 1}`, "tenki", "gen 1"));
  let j = 0;
  return {
    start() {
      clearInterval(topoTimer);
      topoTimer = setInterval(() => {
        const k = j++ % 4, w = ws[k];
        w.g.classList.add("dying");
        setTimeout(() => { gens[k]++; w.s.textContent = `gen ${gens[k]} · empty`; w.g.classList.remove("dying"); }, 500);
      }, 700);
    },
    stop() { clearInterval(topoTimer); },
  };
}

// ---------- controller ----------
document.body.classList.add("demo");
const deck = document.createElement("div");
deck.id = "deck";
deck.innerHTML = `<div class="d-stage"></div><div class="d-bar"><span></span></div><div class="d-hud"></div>`;
document.body.appendChild(deck);
const stage = $(".d-stage", deck), bar = $(".d-bar span", deck), hud = $(".d-hud", deck);
const TOTAL = SCENES.reduce((a, s) => a + s.dur, 0);
const START = SCENES.map((_, i) => SCENES.slice(0, i).reduce((a, s) => a + s.dur, 0));
let idx = -1, elapsed = 0, paused = false, last = performance.now(), beats = [], cur = null;

function show(i) {
  if (cur?.stop) cur.stop();
  clearInterval(actTimer); clearInterval(jitTimer);
  idx = Math.max(0, Math.min(SCENES.length - 1, i));
  cur = SCENES[idx];
  const root = document.createElement("section");
  root.className = "d-scene";
  root.innerHTML = cur.html;
  stage.replaceChildren(root);
  const k = (key) => $(`[data-k="${key}"]`, root);
  const s = {
    k,
    on: (key) => () => k(key).classList.add("in"),
    off: (key) => () => k(key).classList.remove("in"),
    // out first, then in: no double exposure
    swap: (a, b) => () => { k(a).classList.remove("in"); setTimeout(() => k(b).classList.add("in"), STILL ? 0 : 450); },
  };
  beats = cur.beats(s).map(([t, fn]) => ({ t, fn, done: false }));
  cur.start?.(root);
  elapsed = 0;
  hud.textContent = `${idx + 1}/${SCENES.length} · ${cur.name}${AUTOPLAY ? "" : " · → next"}`;
}
function tick() {
  const now = performance.now();
  if (!paused) elapsed += (now - last) / 1000;
  last = now;
  for (const b of beats) if (!b.done && elapsed >= b.t) { b.done = true; b.fn(); }
  const inScene = Math.min(elapsed, cur.dur);
  bar.style.width = ((START[idx] + inScene) / TOTAL) * 100 + "%";
  if (AUTOPLAY && !paused && elapsed >= cur.dur && idx < SCENES.length - 1) show(idx + 1);
}
addEventListener("keydown", (e) => {
  if (e.code === "Space") { paused = !paused; deck.classList.toggle("paused", paused); e.preventDefault(); }
  else if (e.code === "ArrowRight") show(idx + 1);
  else if (e.code === "ArrowLeft") show(idx - 1);
  else if (e.code === "Escape") location.href = location.pathname;
});
scrollTo(0, 0);
show(+Q.get("scene") || 0);
if (Q.get("t")) { elapsed = +Q.get("t"); if (STILL) { deck.classList.add("still"); paused = true; } }
setInterval(tick, 40);
tick();
window.__demo = { TOTAL, START, SCENES: SCENES.map((s) => [s.name, s.dur]) };
