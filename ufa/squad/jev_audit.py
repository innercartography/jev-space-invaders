"""Analysis-only JEV audits of the swarm governor, on SAVED governance states (nothing here drives a live decision).

    python -m ufa.squad.jev_audit structure --out ufa/squad/swarm/validation/audit_structure.json
    python -m ufa.squad.jev_audit order --out ufa/squad/swarm/validation/audit_order.json [--extra-run v1]

structure: the frozen governor sends its three judgments (mode, memory, stop) as three separate requests over the
    same state. JEV's interface also takes one shared state with several isolated questions. Both structures are
    asked on the same saved states; each is asked twice so request-to-request noise is measured, not assumed.
order: every choice question is re-asked with its options in another order (evidence and wording identical);
    answers are mapped back to the option labels. Binary questions: both orders. The memory question (inherited
    findings + NONE): all cyclic rotations of one random order, so every option sits in every position once.

Saved states: every state the main run (s1) logged at a mode transition (state_seen), plus, with --extra-run,
the states the validation run logged for its memory questions.
"""
import argparse
import json
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ufa.squad.swarm import HERE, MEM_Q, MODE_Q, STOP_Q, W

QS = {"mode": MODE_Q.format(w=W), "memory": MEM_Q, "stop": STOP_Q}


def saved_states(extra_run=None, max_extra=60, seed=0):
    out = []
    for f in sorted((HERE / "runs" / "s1").glob("*_t*.json")):
        d = json.loads(f.read_text())
        for p in d["phases"]:
            for i, tr in enumerate(p["transition_log"]):
                out.append({"id": f"s1/{d['condition']}/t{d['trial']}/p{p['phase']}/r{tr['round']}", "phase": p["phase"],
                            "state": tr["state_seen"]})
    if extra_run:
        ex = []
        for f in sorted((HERE / "runs" / extra_run).glob("D_t*.json")):
            d = json.loads(f.read_text())
            g = d["governor"]
            for rec in g["decisions"]:
                if rec["q"] == "memory":
                    ex.append({"id": f"{extra_run}/D/t{d['trial']}/p{rec['phase']}/r{rec['round']}", "phase": rec["phase"],
                               "state": g["states"][rec["state_sha"]]})
        random.Random(seed).shuffle(ex)
        out += ex[:max_extra]
    return out


def options(state):
    rows = state["configurations"]
    q = {"mode": ["EXPLORE", "COORDINATE"]}
    contested = [r["config"] for r in rows if (r.get("inherited") or {}).get("status") == "ACTIVE" and r["games_now"] > 0]
    if contested:
        # the live governor lists them in the order Mitosis returned them; the saved state keeps table order
        q["memory"] = contested + ["NONE"]
    if sum(1 for r in rows if r["games_now"] > 0) >= 2:
        q["stop"] = ["YES", "NO"]
    return q


def spec(qid, opts):
    return {"type": "choice", "instructions": QS[qid], "criteria": {o: None for o in opts}}


def rec_of(r, qid, opts):
    a = (r.get("answers") or {}).get(qid) or {}
    return {"choice": a.get("choice"), "probabilities": a.get("probabilities"), "confidence": a.get("confidence"),
            "options_sent": opts}


def structure(a, dec):
    states = saved_states()

    def one(s):
        q = options(s["state"])
        res = {"id": s["id"], "phase": s["phase"], "questions": list(q)}
        for rep in (1, 2):
            sep, lat, tok = {}, 0.0, 0
            for qid, opts in q.items():
                r = dec.ask(s["state"], {qid: spec(qid, opts)})
                sep[qid] = rec_of(r, qid, opts)
                lat += r["latency_ms"]
                tok += r.get("input_tokens") or 0
                sep[qid]["error"] = r.get("error")
            res[f"separate_{rep}"] = {"answers": sep, "latency_ms_total": round(lat, 1), "input_tokens": tok}
            r = dec.ask(s["state"], {qid: spec(qid, opts) for qid, opts in q.items()})
            res[f"batched_{rep}"] = {"answers": {qid: rec_of(r, qid, opts) for qid, opts in q.items()},
                                     "latency_ms": r["latency_ms"], "input_tokens": r.get("input_tokens"), "error": r.get("error")}
        return res
    with ThreadPoolExecutor(a.parallel) as pool:
        rows = list(pool.map(one, states))
    return {"states": len(rows), "rows": rows, "summary": summarize_structure(rows)}


def pdiff(p, q):
    if not p or not q:
        return None
    return max(abs(p.get(k, 0) - q.get(k, 0)) for k in set(p) | set(q))


def summarize_structure(rows):
    out = {}
    pairs = {"separate_vs_separate": ("separate_1", "separate_2"), "batched_vs_batched": ("batched_1", "batched_2"),
             "separate_vs_batched": ("separate_1", "batched_1"), "separate2_vs_batched2": ("separate_2", "batched_2")}
    for qid in ("mode", "memory", "stop"):
        o = {}
        for name, (x, y) in pairs.items():
            agree, diffs = [], []
            for r in rows:
                if qid not in r["questions"]:
                    continue
                A, B = r[x]["answers"][qid], r[y]["answers"][qid]
                if A["choice"] and B["choice"]:
                    agree.append(A["choice"] == B["choice"])
                d = pdiff(A["probabilities"], B["probabilities"])
                if d is not None:
                    diffs.append(d)
            o[name] = {"n": len(agree), "agreement": round(sum(agree) / len(agree), 3) if agree else None,
                       "max_abs_prob_diff_mean": round(statistics.fmean(diffs), 4) if diffs else None,
                       "max_abs_prob_diff_max": round(max(diffs), 4) if diffs else None}
        out[qid] = o
    lat_s = [r[f"separate_{i}"]["latency_ms_total"] for r in rows for i in (1, 2)]
    lat_b = [r[f"batched_{i}"]["latency_ms"] for r in rows for i in (1, 2)]
    tok_s = [r[f"separate_{i}"]["input_tokens"] for r in rows for i in (1, 2)]
    tok_b = [r[f"batched_{i}"]["input_tokens"] or 0 for r in rows for i in (1, 2)]
    out["per_round"] = {"separate": {"requests": round(statistics.fmean(len(r["questions"]) for r in rows), 2),
                                     "latency_ms_p50_sum": statistics.median(lat_s), "input_tokens_mean": round(statistics.fmean(tok_s))},
                        "batched": {"requests": 1, "latency_ms_p50": statistics.median(lat_b), "input_tokens_mean": round(statistics.fmean(tok_b))}}
    out["errors"] = {"separate": sum(1 for r in rows for i in (1, 2) for v in r[f"separate_{i}"]["answers"].values() if v.get("error")),
                     "batched": sum(1 for r in rows for i in (1, 2) if r[f"batched_{i}"]["error"])}
    return out


def order(a, dec):
    states = saved_states(a.extra_run)
    rng = random.Random(1)
    jobs = []
    for s in states:
        for qid, opts in options(s["state"]).items():
            if qid == "memory":
                base = opts[:]
                rng.shuffle(base)
                perms = [base[i:] + base[:i] for i in range(len(base))]
                perms = [opts] + perms  # the logged order first, as the reference
            else:
                perms = [opts, opts[::-1]]
            jobs.append((s, qid, perms))

    def one(job):
        s, qid, perms = job
        rs = []
        for p in perms + [perms[0]]:  # the reference order again at the end: request noise, same order
            r = dec.ask(s["state"], {qid: spec(qid, p)})
            rs.append(rec_of(r, qid, p) | {"latency_ms": r["latency_ms"], "error": r.get("error")})
        return {"id": s["id"], "phase": s["phase"], "q": qid, "k": len(perms[0]), "answers": rs}
    with ThreadPoolExecutor(a.parallel) as pool:
        rows = list(pool.map(one, jobs))
    return {"rows": rows, "summary": summarize_order(rows)}


def summarize_order(rows):
    out = {}
    for qid in ("mode", "stop", "memory"):
        R_ = [r for r in rows if r["q"] == qid]
        flips, drift, noise_flip, noise_drift, pos_first = [], [], [], [], []
        for r in R_:
            ref, perms, again = r["answers"][0], r["answers"][1:-1], r["answers"][-1]
            if not ref["choice"]:
                continue
            for p in perms:
                if p["options_sent"] == ref["options_sent"] or not p["choice"]:
                    continue
                flips.append(p["choice"] != ref["choice"])
                d = pdiff(ref["probabilities"], p["probabilities"])
                if d is not None:
                    drift.append(d)
                if p["probabilities"]:
                    pos_first.append(p["probabilities"].get(p["options_sent"][0], 0))
            if again["choice"]:
                noise_flip.append(again["choice"] != ref["choice"])
                d = pdiff(ref["probabilities"], again["probabilities"])
                if d is not None:
                    noise_drift.append(d)
        out[qid] = {"states": len(R_), "permuted_requests": len(flips),
                    "flip_rate": round(sum(flips) / len(flips), 3) if flips else None,
                    "prob_drift_mean": round(statistics.fmean(drift), 4) if drift else None,
                    "prob_drift_max": round(max(drift), 4) if drift else None,
                    "same_order_repeat_flip_rate": round(sum(noise_flip) / len(noise_flip), 3) if noise_flip else None,
                    "same_order_repeat_drift_mean": round(statistics.fmean(noise_drift), 4) if noise_drift else None,
                    "mean_prob_on_first_listed_option": round(statistics.fmean(pos_first), 3) if pos_first else None,
                    "note": "the governor acts on the argmax only; no probability threshold, so a threshold crossing is a flip"}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["structure", "order"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--extra-run")
    ap.add_argument("--parallel", type=int, default=8)
    a = ap.parse_args()
    from ufa.arena import keys
    from ufa.arena.deciders import Decider
    from ufa.arena.pricing import cost_usd

    keys.load(["TYPESAFE_API_KEY"])
    dec = Decider("jev", "jev-latest")
    t = time.time()
    calls = []
    inner = dec.ask

    def counted(*x, **y):
        r = inner(*x, **y)
        calls.append((r.get("input_tokens") or 0, r.get("served_model")))
        return r
    dec.ask = counted
    res = (structure if a.cmd == "structure" else order)(a, dec)
    res["jev_calls"] = len(calls)
    res["served_model"] = next((m for _, m in calls if m), None)
    res["input_tokens"] = sum(n for n, _ in calls)
    res["cost_usd"] = cost_usd(res["served_model"] or "jev-latest", res["input_tokens"], 0)
    res["wall_s"] = round(time.time() - t, 1)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
