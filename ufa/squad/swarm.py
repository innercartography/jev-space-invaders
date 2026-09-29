"""Squad swarm experiment: can JEV govern when a swarm explores on its own vs. coordinates, and what does
inherited Mitosis memory do before and after the game changes?

A swarm of W workers searches 12 player configurations (ufa/squad/landscape.py) for the highest mean
score. Each round every worker plays one game. Games are replayed from the Tenki-generated landscape
(every game is a real, replayable ALE game), so a trial costs no emulator time and trials are paired:
trial t draws the same seed order in every condition.

Two phases of R rounds. Phase 1 = regime A (standard game). Phase 2 = regime B (another official game
variation). The swarm is told the context changed (it is observable: the cartridge's game select), never
which conclusions are now wrong. Workers are ephemeral (like sandboxes): each is replaced every L rounds
(staggered), and the whole population is replaced at the phase change. Without Mitosis, knowledge dies
with the worker that gathered it.

Conditions
    A  decentralized, no Mitosis     each worker Thompson-samples from its own games only
    B  decentralized + Mitosis       each worker Thompson-samples from the shared surface (Mitosis)
    C  fixed hierarchy + Mitosis     coordinator: test everything twice, then all workers on the top 2
    D  adaptive JEV + Mitosis        JEV chooses EXPLORE (B's rule) or COORDINATE (top 2) every round,
                                     and which inherited finding is contradicted (-> CHALLENGED)
    E  adaptive JEV, no Mitosis      as D, but workers only know their own games, coordinator only live workers'
    F  adaptive rule + Mitosis       as D, same state and same three judgments, answered by fixed thresholds

The shared surface is Mitosis Cortex: after each round the round's games are distilled into one finding
per configuration and upserted to a per-condition feed; before each round the swarm reads the surface back
with /v1/answer. Decisions use what Mitosis returned (a local mirror is kept only to measure fidelity).
Inherited findings are evidence with provenance, not facts: while ACTIVE they count as prior games; once
CHALLENGED they count for nothing.

    python -m ufa.squad.swarm run --conds A,B,C,D,E,F --trials 40 --run s1 --parallel 10
    python -m ufa.squad.swarm run --conds A,B,C,D,E,F --trials 3 --run p1 --no-mitosis-check
"""
import argparse
import hashlib
import json
import math
import random
import statistics
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = REPO / "ufa" / "squad" / "swarm"
W, R, L = 4, 15, 5          # workers, rounds per phase, worker lifetime (rounds)
SIGMA, PRIOR_MU, PRIOR_N = 150.0, 400.0, 0.25  # Thompson: per-game sd, optimistic prior mean, prior weight
NEAR = 10                   # near-best: regret <= 10 points (pre-registered); 50 reported as secondary
DOMINATED = 100             # a config is dominated if its true mean is > 100 below the best
CONDS = {"A": ("decentral", False), "B": ("decentral", True), "C": ("hierarchy", True),
         "D": ("adaptive_jev", True), "E": ("adaptive_jev", False), "F": ("adaptive_rule", True)}
CTX = {0: "first variation (standard game)", 1: "second variation (the game select changed)"}

MODE_Q = ("You govern a swarm of {w} workers searching for the configuration with the highest mean score. Choose how the "
          "swarm works next round. EXPLORE: each worker picks its own experiment from the shared evidence (more diversity, "
          "more duplication). COORDINATE: all workers are put on the two leading configurations to confirm them (less "
          "waste, no exploration). Coordinate when the evidence has converged on a few candidates or exploring is wasting "
          "games; explore while it is still unclear which configurations could be best, or when current evidence "
          "disagrees with what was believed before.")
MEM_Q = ("Inherited findings were observed in an earlier game variation. They are evidence, not facts. Which inherited "
         "finding is most contradicted by the evidence gathered in the current variation? Choose NONE if no inherited "
         "finding is clearly contradicted yet.")
STOP_Q = ("Is the evidence already sufficient to stop testing in this variation and commit to the current leader? "
          "YES only if the leader is clearly better than every configuration that could still be the best.")


# ---------------------------------------------------------------- landscape

def load_landscape():
    L_ = {}
    for i, name in enumerate(("A", "B")):
        p = HERE / "landscape" / f"{name}.json"
        d = json.loads(p.read_text())
        by = {}
        for g in d["games"]:
            by.setdefault(g["config"], {})[g["seed"]] = g["score_ex_bonus"]
        seeds = sorted(next(iter(by.values())))
        truth = {c: statistics.fmean(v.values()) for c, v in by.items()}
        L_[i] = {"name": name, "regime": d["regime"], "scores": by, "seeds": seeds, "truth": truth,
                 "best": max(truth.values()), "file": str(p.relative_to(REPO)).replace("\\", "/"),
                 "sha256": hashlib.sha256(p.read_bytes()).hexdigest()[:16]}
    return L_


def commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    except Exception:
        return None


# ---------------------------------------------------------------- knowledge = {config: [n, sum, sumsq]}

def add(K, c, x):
    k = K.setdefault(c, [0, 0.0, 0.0])
    k[0] += 1
    k[1] += x
    k[2] += x * x


def merge(*Ks):
    out = {}
    for K in Ks:
        for c, (n, s, q) in K.items():
            k = out.setdefault(c, [0, 0.0, 0.0])
            k[0] += n
            k[1] += s
            k[2] += q
    return out


def stats(k):
    n, s, q = k
    m = s / n
    sd = math.sqrt(max(q / n - m * m, 0) * n / (n - 1)) if n > 1 else None
    return n, m, sd


def combined(K, inh, c):
    """(effective n, mean) of current evidence plus ACTIVE inherited evidence."""
    n, s = (K[c][0], K[c][1]) if c in K else (0, 0.0)
    f = inh.get(c)
    if f and f["status"] == "ACTIVE":
        n, s = n + f["games"], s + f["games"] * f["mean"]
    return n, (s / n if n else None)


def pick(K, inh, configs):
    best = None
    for c in configs:
        n, m = combined(K, inh, c)
        if n and (best is None or m > best[1]):
            best = (c, m)
    return best[0] if best else None


def thompson(K, inh, configs, rng):
    def draw(c):
        n, m = combined(K, inh, c)
        mu = (PRIOR_N * PRIOR_MU + n * (m or 0)) / (PRIOR_N + n)
        return rng.gauss(mu, SIGMA / math.sqrt(PRIOR_N + n))
    return max(configs, key=draw)


def top2(K, inh, configs, rng):
    ranked = sorted([c for c in configs if combined(K, inh, c)[0]], key=lambda c: -combined(K, inh, c)[1])
    while len(ranked) < 2:
        ranked.append(thompson(K, inh, [c for c in configs if c not in ranked], rng))
    return [ranked[i % 2] for i in range(W)]


def hierarchy(K, inh, configs, rng):
    low = [c for c in configs if combined(K, inh, c)[0] < 2]
    if low:
        rng.shuffle(low)
        low.sort(key=lambda c: combined(K, inh, c)[0])
        return [low[i % len(low)] for i in range(W)]
    return top2(K, inh, configs, rng)


def ci(k):
    n, m, sd = stats(k)
    if sd is None:
        return None
    h = 1.96 * sd / math.sqrt(n)
    return [round(m - h), round(m + h)]


# ---------------------------------------------------------------- the shared surface (Mitosis)

class Surface:
    """Per-condition feed in the lab's own Mitosis office. Findings are upserted by external_id
    (run-cond-trial-context-config). Reads go through /v1/answer; decisions use what came back."""

    lock = threading.Lock()

    def __init__(self, run, cond, trial, cortex, land, cm):
        self.run, self.cond, self.trial, self.cx, self.land, self.commit = run, cond, trial, cortex, land, cm
        self.feed = f"swarm_{run}_{cond}".lower()
        self.mirror = {}          # (ctx, config) -> finding (for fidelity only)
        self.ops = {"write_calls": 0, "rows_written": 0, "read_calls": 0, "read_ms": [], "write_ms": [],
                    "read_mismatch": 0, "read_fail": 0, "write_fail": 0}
        self.last = {}
        # observability only (validation run): every acknowledged version of every finding, and per read how far
        # behind the returned surface was. A finding's version = its (games, status); games only ever grow.
        self.acked = {}           # (ctx, config) -> [(games, status, ack_unix_s)]
        self.read_log = []
        self.at = None            # (phase, round) of the caller, for the logs
        self.last_behind = False

    def finding(self, ctx, c, k, status, order, seeds):
        n, m, sd = stats(k)
        return {"run": self.run, "condition": self.cond, "trial": self.trial, "experiment_id": c, "config": c,
                "context": self.land[ctx]["name"], "context_label": CTX[ctx],
                "hypothesis": f"configuration {c} scores about {round(m)} per game (bonus excluded) in this variation",
                "evidence": {"games": n, "mean": round(m, 1), "sd": round(sd, 1) if sd else None, "ci95": ci(k)},
                "result": f"{n} games, mean {round(m, 1)}", "confidence": "low" if n < 3 else ("medium" if n < 8 else "high"),
                "order": order, "status": status,
                "provenance": {"landscape": self.land[ctx]["file"], "landscape_sha256": self.land[ctx]["sha256"],
                               "commit": self.commit, "seeds": sorted(seeds)}}

    def write(self, rows):
        if not rows:
            return
        for f in rows:
            self.mirror[(f["context"], f["config"])] = f
        payload = [{"external_id": f"{self.run}-{self.cond}-t{self.trial}-{f['context']}-{f['config']}",
                    "title": f"swarm {self.run} {self.cond} trial {self.trial} finding {f['config']} context {f['context']}",
                    "content": json.dumps(f, separators=(",", ":")), "modality": "text",
                    "imported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())} for f in rows]
        t = time.perf_counter()
        try:
            self.cx.ingest(self.feed, payload, batch=24, ensure=False)
            self.ops["rows_written"] += len(rows)
            ts = time.time()
            for f in rows:
                self.acked.setdefault((f["context"], f["config"]), []).append((f["evidence"]["games"], f["status"], ts))
        except Exception:
            self.ops["write_fail"] += 1
        self.ops["write_calls"] += 1
        self.ops["write_ms"].append(round((time.perf_counter() - t) * 1000))

    def read(self):
        t = time.perf_counter()
        t_read = time.time()
        self.ops["read_calls"] += 1
        try:
            out = self.cx.answer(f"swarm {self.run} {self.cond} trial {self.trial} finding", limit=40,
                                 integration_id=self.feed, include_raw=True)
            got = {}
            for r in out.get("results") or []:
                try:
                    f = json.loads((r.get("raw") or {}).get("content") or "{}")
                except ValueError:
                    continue
                if f.get("trial") == self.trial and f.get("condition") == self.cond and f.get("run") == self.run:
                    got[(f["context"], f["config"])] = f
            self.last = got
        except Exception:
            self.ops["read_fail"] += 1
            got = self.last  # stale surface: the last successful read
        self.ops["read_ms"].append(round((time.perf_counter() - t) * 1000))
        if {k: v["evidence"]["games"] for k, v in got.items()} != {k: v["evidence"]["games"] for k, v in self.mirror.items()} or \
                {k: v["status"] for k, v in got.items()} != {k: v["status"] for k, v in self.mirror.items()}:
            self.ops["read_mismatch"] += 1
        self._observe(got, t_read)
        return got

    def _observe(self, got, t_read):
        behind = []
        for key, vers in self.acked.items():
            vers = [v for v in vers if v[2] <= t_read]  # only writes acknowledged before this read began
            if not vers:
                continue
            g = got.get(key)
            rec = (g["evidence"]["games"], g["status"]) if g else None
            if rec == vers[-1][:2]:
                continue
            idx = max((i for i, v in enumerate(vers) if v[:2] == rec), default=-1)
            missed = vers[idx + 1:]
            behind.append({"finding": f"{key[0]}:{key[1]}", "received": list(rec) if rec else None,
                           "latest_acked": list(vers[-1][:2]), "versions_behind": len(missed),
                           "staleness_s": round(t_read - missed[0][2], 3) if missed else None,
                           "unknown_version": idx == -1 and rec is not None})
        self.last_behind = bool(behind)
        self.read_log.append({"at": self.at, "t": round(t_read, 3), "findings_acked": sum(1 for v in self.acked.values()
                              if any(x[2] <= t_read for x in v)), "behind": behind})


def from_findings(found, ctx_name):
    """Surface findings -> (current knowledge, inherited findings)."""
    K, inh = {}, {}
    for (cx, c), f in found.items():
        e = f["evidence"]
        if cx == ctx_name:
            n, m, sd = e["games"], e["mean"], e["sd"] or 0.0
            K[c] = [n, n * m, (sd * sd * (n - 1) + n * m * m) if n > 1 else m * m]
        else:
            inh[c] = {"games": e["games"], "mean": e["mean"], "sd": e["sd"], "status": f["status"], "ci95": e["ci95"]}
    return K, inh


# ---------------------------------------------------------------- governance

class Governor:
    """Three bounded judgments per round: mode, which inherited finding is contradicted, stop (counterfactual)."""

    def __init__(self, kind, seed):
        self.kind = kind
        self.recs = []
        self.cf_recs, self.states, self.at = [], {}, (0, 0)
        self.rng = random.Random(seed)
        if kind == "adaptive_jev":
            from ufa.arena import keys
            from ufa.arena.deciders import Decider
            keys.load(["TYPESAFE_API_KEY"])  # only the key the governor needs
            self.d = Decider("jev", "jev-latest")

    def state(self, K, inh, configs, phase, r, hist):
        rows = []
        for c in configs:
            d = {"config": c}
            if c in K:
                n, m, _ = stats(K[c])
                d.update(games_now=n, mean_now=round(m, 1), ci95_now=ci(K[c]))
            else:
                d["games_now"] = 0
            if c in inh:
                f = inh[c]
                d["inherited"] = {"games": f["games"], "mean": f["mean"], "ci95": f["ci95"], "status": f["status"],
                                  "observed_in": "earlier variation"}
            rows.append(d)
        rows.sort(key=lambda d: -(combined(K, inh, d["config"])[1] or -1))
        leaders = [h["pick"] for h in hist[-3:]]
        cis = sorted([(K[c][1] / K[c][0], ci(K[c])) for c in K if ci(K[c])], key=lambda x: -x[0])
        s = {"task": f"{W} workers search {len(configs)} player configurations for the highest mean score; each round "
                     f"every worker plays one game", "context": CTX[phase], "round": r, "rounds_left": R - r,
             "configurations": rows,
             "swarm": {"untested_now": sum(1 for c in configs if c not in K),
                       "leader": pick(K, inh, configs), "leader_changes_last_3_rounds": sum(a != b for a, b in zip(leaders, leaders[1:])),
                       "top2_ci_overlap": (cis[0][1][0] <= cis[1][1][1]) if len(cis) > 1 else None,
                       "duplicate_games_last_round": (W - len(set(hist[-1]["alloc"]))) if hist else 0,
                       "distinct_configs_last_3_rounds": len({c for h in hist[-3:] for c in h["alloc"]})}}
        if inh:
            s["note"] = "Inherited findings come from an earlier variation: evidence, not facts."
        return s

    def _ask(self, state, q, options, qid):
        rec = self.d.ask(state, {qid: {"type": "choice", "instructions": q, "criteria": {o: None for o in options}}})
        ans = (rec.get("answers") or {}).get(qid) or {}
        ch = ans.get("choice") if ans.get("choice") in options else None
        # logging only: the full answer distribution, the question as sent and the state it saw (by hash)
        sh = hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()[:16]
        self.states[sh] = state
        self.recs.append({"q": qid, "choice": ch, "confidence": ans.get("confidence"), "latency_ms": rec["latency_ms"],
                          "input_tokens": rec.get("input_tokens"), "served_model": rec.get("served_model"),
                          "error": rec.get("error"), "phase": self.at[0] + 1, "round": self.at[1], "options": list(options),
                          "probabilities": ans.get("probabilities"), "state_sha": sh,
                          "question": {"type": "choice", "instructions": q}})
        return ch, ans.get("confidence")

    def counterfactual(self, *a):
        """The same judgments on another state, logged apart and never acted on (stale-read instrumentation)."""
        saved, self.recs = self.recs, []
        try:
            out = self.decide(*a)
        finally:
            cf, self.recs = self.recs, saved
        self.cf_recs.extend(cf)
        return out

    def decide(self, K, inh, configs, phase, r, hist):
        self.at = (phase, r)
        st = self.state(K, inh, configs, phase, r, hist)
        out = {"state": st}
        contested = [c for c, f in inh.items() if f["status"] == "ACTIVE" and c in K]
        tested = [c for c in configs if c in K]
        if self.kind == "adaptive_jev":
            out["mode"], out["mode_conf"] = self._ask(st, MODE_Q.format(w=W), ["EXPLORE", "COORDINATE"], "mode")
            if contested:
                out["challenge"], _ = self._ask(st, MEM_Q, contested + ["NONE"], "memory")
            if len(tested) >= 2:
                out["stop"], _ = self._ask(st, STOP_Q, ["YES", "NO"], "stop")
            out["mode"] = out["mode"] or "EXPLORE"  # an unanswered call keeps the default
        else:
            out.update(rule_judgments(K, inh, configs, hist, contested, tested))
        return out


def rule_judgments(K, inh, configs, hist, contested, tested):
    """The same three judgments by fixed thresholds (condition F; also the counterfactual stop for A-C)."""
    out = {}
    stable = len(hist) >= 2 and hist[-1]["pick"] == hist[-2]["pick"]
    out["mode"] = "COORDINATE" if (all(c in K for c in configs) and stable) else "EXPLORE"
    best_z, ch = 2.0, None
    for c in contested:
        n, m, sd = stats(K[c])
        f = inh[c]
        if n < 2:
            continue
        se = math.sqrt(((sd or SIGMA) ** 2) / n + ((f["sd"] or SIGMA) ** 2) / max(f["games"], 1))
        z = abs(m - f["mean"]) / se if se else 0
        if z > best_z:
            best_z, ch = z, c
    if contested:
        out["challenge"] = ch or "NONE"
    if len(tested) >= 2:
        lead = pick(K, {}, configs)
        lo = ci(K[lead])
        others = [ci(K[c]) for c in configs if c != lead and c in K]
        out["stop"] = "YES" if (lo and all(c in K for c in configs) and all(o and o[1] < lo[0] for o in others)) else "NO"
    return out


# ---------------------------------------------------------------- one trial

def allocate(gov_kind, mode, memory, K, inh, local, configs, rng):
    if gov_kind == "hierarchy":
        return hierarchy(K, inh, configs, rng)
    if mode == "COORDINATE":
        return top2(K, inh, configs, rng)
    if memory:
        return [thompson(K, inh, configs, rng) for _ in range(W)]
    return [thompson(local[k], {}, configs, rng) for k in range(W)]


def run_trial(cond, trial, land, run, cortex, cm, sub=None):
    """sub=None: games are replayed from the landscape (the main experiment). sub=a substrate (validation): games are
    played live by ephemeral workers and a memoryless swarm's knowledge lives only on its living workers."""
    gov_kind, memory = CONDS[cond]
    configs = sorted(land[0]["truth"])
    order_rng = random.Random(trial)
    pool = sub.seeds if sub else {ph: land[ph]["seeds"] for ph in (0, 1)}
    seed_order = {ph: {c: order_rng.sample(pool[ph], len(pool[ph])) for c in configs} for ph in (0, 1)}
    cf_log = []
    rng = random.Random(10_000 + trial)  # worker randomness; same stream start in every condition
    gov = Governor(gov_kind, 20_000 + trial) if gov_kind.startswith("adaptive") else None
    surf = Surface(run, cond, trial, cortex, land, cm) if memory else None
    phases, timeline = [], []
    challenged_total = 0
    for ph in (0, 1):
        truth, best = land[ph]["truth"], land[ph]["best"]
        ctx_name = land[ph]["name"]
        used = {c: 0 for c in configs}
        seeds_used = {c: [] for c in configs}
        Kall = {}                              # everything played this phase (ground-truth log, not a knowledge source)
        local = [dict() for _ in range(W)]     # worker-local knowledge (A, E)
        hist, mode_rounds = [], {"EXPLORE": 0, "COORDINATE": 0}
        transitions, stop_round, stop_regret, rule_stop_round = [], None, None, None
        rediscovery = dominated_games = stale_games = 0
        retrieved = None
        prev_mode = None
        for r in range(R):
            if sub:  # the substrate replaces the workers due now; a memoryless swarm asks its living workers
                got = sub.round_start(cond, trial, ph, r, need_local=not memory)
                if not memory:
                    local = got
            else:
                for k in range(W):  # staggered replacement of ephemeral workers
                    if r > 0 and (r + k) % L == 0:
                        local[k] = {}
            if memory:
                surf.at = (ph + 1, r)
                found = surf.read()
                K, inh = from_findings(found, ctx_name)
                if ph == 1 and retrieved is None:
                    retrieved = dict(inh)
            else:
                K, inh = merge(*local), {}
            dec = gov.decide(K, inh, configs, ph, r, hist) if gov else None
            cf = None
            if sub and memory and surf.last_behind:  # instrumentation: what if the read had been current?
                Kc, inhc = from_findings(dict(surf.mirror), ctx_name)
                cf = {"phase": ph + 1, "round": r, "K": Kc, "inh": inhc}
                if gov and gov_kind == "adaptive_jev":
                    d2 = gov.counterfactual(Kc, inhc, configs, ph, r, hist)
                    cf["judgments_differ"] = {q: d2.get(q) != dec.get(q) for q in ("mode", "challenge", "stop")
                                              if q in d2 or q in dec}
            rj = rule_judgments(K, inh, configs, hist, [c for c, f in inh.items() if f["status"] == "ACTIVE" and c in K],
                                [c for c in configs if c in K])
            if rule_stop_round is None and rj.get("stop") == "YES":
                rule_stop_round = r
            if dec and dec.get("challenge") not in (None, "NONE"):
                c = dec["challenge"]
                inh[c]["status"] = "CHALLENGED"
                challenged_total += 1
                f = surf.mirror[(land[0]["name"], c)]
                surf.write([{**f, "status": "CHALLENGED", "order": f"challenged in round {r} of phase 2"}])
            if dec and dec.get("stop") == "YES" and stop_round is None:
                stop_round, p = r, pick(K, inh, configs)
                stop_regret = round(best - truth[p], 1) if p else None
            mode = dec["mode"] if dec else ("COORDINATE" if gov_kind == "hierarchy" else "EXPLORE")
            mode_rounds[mode] += 1
            if dec and prev_mode is not None and mode != prev_mode:
                transitions.append({"round": r, "from": prev_mode, "to": mode, "state_seen": dec["state"]})
            prev_mode = mode
            # allocation
            if cf is not None:  # same rng state, current surface (challenge applied the same way); rng restored
                st_ = rng.getstate()
                inhc = cf.pop("inh")
                if dec and dec.get("challenge") not in (None, "NONE") and dec["challenge"] in inhc:
                    inhc[dec["challenge"]]["status"] = "CHALLENGED"
                alloc_cf = allocate(gov_kind, mode, memory, cf.pop("K"), inhc, None, configs, rng)
                rng.setstate(st_)
            alloc = allocate(gov_kind, mode, memory, K, inh, local, configs, rng)
            if cf is not None:
                cf["alloc_differs"] = sorted(alloc_cf) != sorted(alloc)
                cf_log.append(cf)
            # play the games (replayed from the landscape, or live on the substrate's workers)
            plan = []
            for k, c in enumerate(alloc):
                s = seed_order[ph][c][used[c] % len(seed_order[ph][c])]
                used[c] += 1
                plan.append((k, c, s))
            xs = sub.play(cond, trial, ph, r, plan, keep_local=not memory) if sub else [land[ph]["scores"][c][s] for _, c, s in plan]
            touched = set()
            for (k, c, s), x in zip(plan, xs):
                if truth[c] < best - DOMINATED:
                    dominated_games += 1
                    if Kall.get(c, [0])[0] >= 2:
                        rediscovery += 1
                if ph == 1 and land[0]["truth"][c] - truth[c] > DOMINATED and truth[c] < best - DOMINATED:
                    stale_games += 1
                add(Kall, c, x)
                add(local[k], c, x)
                seeds_used[c].append(s)
                touched.add(c)
            if memory:  # distill this round into findings and upsert them
                # a touched config's finding is rebuilt from every game played on it this phase, so it is exact
                rows = [surf.finding(ph, c, Kall[c], "ACTIVE", f"phase {ph + 1} round {r}", seeds_used[c]) for c in sorted(touched)]
                surf.write(rows)
                Kview = merge({c: v for c, v in K.items() if c not in touched}, {c: Kall[c] for c in touched})
            else:
                Kview = merge(*local)
            p = pick(Kview, inh, configs)
            regret = round(best - truth[p], 1) if p else round(best - statistics.fmean(truth.values()), 1)
            hist.append({"round": r, "mode": mode, "alloc": alloc, "pick": p, "regret": regret,
                         "judgments": {k: v for k, v in (dec or {}).items() if k in ("mode", "challenge", "stop", "mode_conf")}})
        regrets = [h["regret"] for h in hist]

        def settle(th):
            for i in range(R):
                if all(x <= th for x in regrets[i:]):
                    return i + 1
            return None
        alloc_counts = [sum(1 for h in hist for c in h["alloc"] if c == x) for x in configs]
        tot = sum(alloc_counts)
        phases.append({
            "phase": ph + 1, "regime": land[ph]["name"], "regret_curve": regrets, "final_regret": regrets[-1],
            "regret_auc": round(statistics.fmean(regrets), 1), "rounds_to_near_best": settle(NEAR),
            "rounds_to_within_50": settle(50), "final_pick": hist[-1]["pick"],
            "games": R * W, "unique_configs": sum(1 for x in alloc_counts if x),
            "alloc_entropy_bits": round(-sum(x / tot * math.log2(x / tot) for x in alloc_counts if x), 3),
            "duplicate_games": sum(W - len(set(h["alloc"])) for h in hist),
            "dominated_games": dominated_games, "rediscovery_games": rediscovery, "stale_led_games": stale_games,
            "mode_rounds": mode_rounds, "transitions": len(transitions), "transition_log": transitions,
            "stop_round": stop_round, "stop_regret": stop_regret, "premature_stop": (stop_regret is not None and stop_regret > NEAR),
            "rule_stop_round": rule_stop_round,
            "retrieved_inherited": ({c: {"mean": f["mean"], "games": f["games"],
                                         "stale": abs(f["mean"] - truth[c]) > 50} for c, f in (retrieved or {}).items()} if ph == 1 else None),
            "rounds": hist})
    # final statuses of inherited findings (phase 2), written back to Mitosis
    if memory:
        found = surf.read()
        K, inh = from_findings(found, land[1]["name"])
        final = []
        for c, f in inh.items():
            st = f["status"]
            if c in K and K[c][0] >= 3:
                lo_hi = ci(K[c])
                st = "FALSIFIED" if not (lo_hi[0] <= f["mean"] <= lo_hi[1]) else "SUPERSEDED"
            final.append((c, st))
            base = surf.mirror[(land[0]["name"], c)]
            if st != base["status"]:
                surf.write([{**base, "status": st, "order": "end of phase 2"}])
        phases[1]["inherited_final_status"] = dict(final)
    out = {"condition": cond, "trial": trial, "governance": gov_kind, "memory": memory, "phases": phases,
           "challenges": challenged_total}
    if gov:
        out["governor"] = {"kind": gov_kind, "calls": len(gov.recs) if gov_kind == "adaptive_jev" else 0,
                           "latency_ms": [x["latency_ms"] for x in gov.recs], "errors": sum(1 for x in gov.recs if x["error"]),
                           "unanswered": sum(1 for x in gov.recs if x["choice"] is None),
                           "input_tokens": sum(x["input_tokens"] or 0 for x in gov.recs),
                           "served_model": next((x["served_model"] for x in gov.recs if x["served_model"]), None)}
        if gov_kind == "adaptive_jev":
            from ufa.arena.pricing import cost_usd
            out["governor"]["cost_usd"] = cost_usd(out["governor"]["served_model"] or "jev-latest", out["governor"]["input_tokens"], 0)
            if sub:  # validation logging: every decision with its raw distribution, the states, counterfactuals
                out["governor"]["decisions"] = gov.recs
                out["governor"]["counterfactual_decisions"] = gov.cf_recs
                out["governor"]["counterfactual_input_tokens"] = sum(x["input_tokens"] or 0 for x in gov.cf_recs)
                out["governor"]["states"] = gov.states
    if surf:
        o = surf.ops
        out["mitosis"] = {k: v for k, v in o.items() if not k.endswith("_ms")} | {
            "read_ms_p50": statistics.median(o["read_ms"]) if o["read_ms"] else None,
            "write_ms_p50": statistics.median(o["write_ms"]) if o["write_ms"] else None}
        if sub:
            out["mitosis"]["read_log"] = surf.read_log
            out["mitosis"]["stale_read_counterfactuals"] = cf_log
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--conds", default="A,B,C,D,E,F")
    r.add_argument("--trials", type=int, default=40)
    r.add_argument("--first-trial", type=int, default=0)
    r.add_argument("--run", required=True, help="run id; each run+condition gets its own fresh Mitosis feed")
    r.add_argument("--parallel", type=int, default=10)
    a = ap.parse_args()
    from ufa.mitosis.cortex import Cortex

    land = load_landscape()
    cm = commit()
    conds = a.conds.split(",")
    cortex = None
    if any(CONDS[c][1] for c in conds):
        cortex = Cortex()
        for c in conds:  # isolation: every condition's feed must start empty
            if CONDS[c][1]:
                feed = f"swarm_{a.run}_{c}".lower()
                cortex.ensure_feed(feed)
                pre = cortex.answer(f"swarm {a.run} {c} trial finding", limit=40, integration_id=feed, include_raw=True)
                n = len(pre.get("results") or [])
                if n:
                    raise SystemExit(f"feed {feed} is not empty ({n} rows): pick a new --run id")
    od = HERE / "runs" / a.run
    od.mkdir(parents=True, exist_ok=True)
    jobs = [(c, t) for t in range(a.first_trial, a.first_trial + a.trials) for c in conds]
    t0 = time.perf_counter()
    done = []

    def one(job):
        c, t = job
        f = od / f"{c}_t{t:03d}.json"
        if f.exists():
            return json.loads(f.read_text())
        ts = time.perf_counter()
        res = run_trial(c, t, land, a.run, cortex, cm)
        res["wall_s"] = round(time.perf_counter() - ts, 1)
        f.write_text(json.dumps(res, separators=(",", ":")))
        done.append(job)
        if len(done) % 10 == 0:
            print(f"{len(done)}/{len(jobs)} trials, {time.perf_counter() - t0:.0f}s", flush=True)
        return res

    with ThreadPoolExecutor(a.parallel) as pool:
        list(pool.map(one, jobs))
    meta = {"run": a.run, "conds": conds, "trials": a.trials, "W": W, "R": R, "L": L, "commit": cm,
            "landscape": {k: {kk: v[kk] for kk in ("name", "regime", "file", "sha256", "best")} for k, v in land.items()},
            "wall_s": round(time.perf_counter() - t0, 1)}
    (od / "meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
