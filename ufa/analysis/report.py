"""Experiment report: per-condition stats, representation accounting, paired seed comparison, Tenki usage.

    python -m ufa.analysis.report ufa/traces/exp002_repr_check --a jev_basic__raw --b jev_basic__threat \
        --tenki ufa/traces-remote/tenki

Reads episode.json + steps.jsonl (every episode found, failures included) and tenki_run.json.
Writes <exp_dir>/analysis/report.json and report.md. Numbers only; no conclusions are written here
beyond what the arithmetic says.
"""
import argparse
import itertools
import json
import statistics
from collections import defaultdict
from pathlib import Path

from ufa.arena.compare import load
from ufa.arena.run import pct


def leaves(x):
    if isinstance(x, dict):
        return sum(leaves(v) for v in x.values())
    if isinstance(x, list):
        return sum(leaves(v) for v in x)
    return 1


def st(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return {"n": len(vals), "mean": round(statistics.fmean(vals), 2), "median": round(statistics.median(vals), 2),
            "stdev": round(statistics.stdev(vals), 2) if len(vals) > 1 else None, "min": min(vals), "max": max(vals)}


def per_episode_steps(path):
    dms, chars, byts, fields, top = [], [], [], [], []
    with open(Path(path) / "steps.jsonl") as f:
        for line in f:
            r = json.loads(line)
            dms.append(r["decision_ms"])
            txt = json.dumps(r["representation"], separators=(",", ":"))
            chars.append(len(txt))
            byts.append(len(txt.encode()))
            fields.append(leaves(r["representation"]))
            top.append(len(r["representation"]))
    return dms, chars, byts, fields, top


def condition(eps):
    S = [e["summary"] for e in eps]
    all_dms, chars, byts, fields, top = [], [], [], [], []
    for e in eps:
        d, c, b, f, t = per_episode_steps(e["_path"])
        all_dms += d; chars += c; byts += b; fields += f; top += t
    decisions = sum(s["steps"] for s in S)
    calls = sum(s["model_calls"] for s in S)
    costs = [s["cost_usd"] for s in S if s["cost_usd"] is not None]
    errors = defaultdict(int)
    for s in S:
        for k, v in (s["errors_by_status"] or {}).items():
            errors[k] += v
    return {
        "N": len(S), "seeds": sorted({s["seed"] for s in S}),
        "code_hashes": sorted({e["code_hash"] for e in eps}), "source_commits": sorted({str(e["source_commit"]) for e in eps}),
        "question_set_hash": sorted({str(e["policy"].get("question_set_hash")) for e in eps}),
        "representation": S[0]["representation"],
        "served_models": sorted({str(s["served_model"]) for s in S}),
        "score": st([s["score"] for s in S]),
        "steps": st([s["steps"] for s in S]),
        "decision_ms_mean": round(statistics.fmean(all_dms), 2) if all_dms else None,
        "decision_ms_p50_pooled": pct(all_dms, 0.5), "decision_ms_p95_pooled": pct(all_dms, 0.95),
        "game_runtime_s": st([s["wall_clock_s"] for s in S]),
        "cost_per_game_usd": round(statistics.fmean(costs), 5) if costs else None,
        "cost_per_decision_usd": round(sum(costs) / decisions, 8) if costs and decisions else None,
        "cost_total_usd": round(sum(costs), 4) if costs else None,
        "api_errors": dict(errors), "retries": sum(s["retries"] or 0 for s in S),
        "fallback_actions": sum(s["fallback_actions"] for s in S),
        "terminations": dict(sorted({t: sum(1 for s in S if s["termination_reason"] == t)
                                     for t in {s["termination_reason"] for s in S}}.items())),
        "rep": {"chars_per_decision": round(statistics.fmean(chars), 1), "bytes_per_decision": round(statistics.fmean(byts), 1),
                "top_level_fields": round(statistics.fmean(top), 2), "scalar_values_per_decision": round(statistics.fmean(fields), 1),
                "input_tokens_per_call": round(sum(s["input_tokens"] or 0 for s in S) / calls, 1) if calls else None},
        "mean_confidence": st([s["mean_confidence"] for s in S]),
    }


def paired(eps, a, b):
    by = defaultdict(lambda: defaultdict(list))
    for e in eps:
        s = e["summary"]
        if s["arm"] in (a, b):
            by[s["seed"]][s["arm"]].append(s["score"])
    rows = []
    for seed in sorted(by):
        A, B = by[seed][a], by[seed][b]
        if A and B:
            rows.append({"seed": seed, f"{a}_scores": A, f"{b}_scores": B, f"{a}_mean": round(statistics.fmean(A), 1),
                         f"{b}_mean": round(statistics.fmean(B), 1), "delta_b_minus_a": round(statistics.fmean(B) - statistics.fmean(A), 1)})
    d = [r["delta_b_minus_a"] for r in rows]
    out = {"a": a, "b": b, "rows": rows, "seeds_paired": len(d)}
    if d:
        obs = statistics.fmean(d)
        # exact sign-flip permutation test over seeds (seed = unit; reps averaged within seed)
        flips = [statistics.fmean(x * s for x, s in zip(d, signs)) for signs in itertools.product([1, -1], repeat=len(d))]
        out.update({"mean_delta": round(obs, 1), "median_delta": round(statistics.median(d), 1),
                    "seeds_b_higher": sum(x > 0 for x in d), "seeds_a_higher": sum(x < 0 for x in d), "seeds_tied": sum(x == 0 for x in d),
                    "perm_p_two_sided": round(sum(abs(f) >= abs(obs) - 1e-9 for f in flips) / len(flips), 4),
                    "perm_min_possible_p": round(2 / len(flips), 4)})
    # within-seed spread: how much reps of the same arm+seed disagree
    for arm in (a, b):
        sds = [statistics.stdev(by[s][arm]) for s in by if len(by[s][arm]) > 1]
        out[f"{arm}_within_seed_sd_mean"] = round(statistics.fmean(sds), 1) if sds else None
    return out


def tenki(root, exp_id):
    recs = []
    for p in Path(root).glob("*/tenki_run.json"):
        r = json.loads(p.read_text())
        if r.get("experiment_id") == exp_id:
            recs.append(r)
    if not recs:
        return None
    T = [r.get("timings_s", {}) for r in recs]
    return {
        "sandboxes_provisioned": sum(1 for r in recs if r.get("sandbox_id")),
        "games_per_sandbox": sorted({r.get("games_in_sandbox", 1) for r in recs}),
        "failures": [{"arm": r["arm"], "seed": r["seed"], "rep": r.get("rep"), "error": r["error"]} for r in recs if r.get("error")],
        "create_to_ready_s": st([t.get("create_to_ready") for t in T]),
        "install_deps_s": st([t.get("install_deps") for t in T]),
        "episode_s": st([t.get("episode") for t in T]),
        "billable_s_total": round(sum(t.get("billable_estimate") or 0 for t in T), 1),
        "compute_cost_usd_estimate_total": round(sum(r.get("compute_cost_usd_estimate") or 0 for r in recs), 4),
        "egress_allowlist_applied": sum(1 for r in recs if r.get("egress_allowlist")),
        "state_after_close": dict(sorted({s: sum(1 for r in recs if r.get("state_after_close") == s)
                                          for s in {r.get("state_after_close") for r in recs}}.items())),
    }


def to_md(rep):
    L = [f"# {rep['experiment_id']}: results", "", "Every episode found is included. Scores are game points.", ""]
    L += ["| condition | N | mean | median | sd | min–max | mean steps | mean ms | p50 ms | p95 ms | game s (mean) | $/game | $/decision | errors | retries | fallbacks |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for arm, c in rep["conditions"].items():
        s = c["score"]
        L.append(f"| {arm} | {c['N']} | {s['mean']} | {s['median']} | {s['stdev']} | {s['min']:g}–{s['max']:g} | {c['steps']['mean']} | "
                 f"{c['decision_ms_mean']} | {c['decision_ms_p50_pooled']} | {c['decision_ms_p95_pooled']} | {c['game_runtime_s']['mean']} | "
                 f"{c['cost_per_game_usd']} | {c['cost_per_decision_usd']} | {c['api_errors'] or 0} | {c['retries']} | {c['fallback_actions']} |")
    L += ["", "## What each representation sends (per decision, mean)", "",
          "| condition | chars | bytes | top-level fields | scalar values | input tokens/call (incl. question) |", "|---|---|---|---|---|---|"]
    for arm, c in rep["conditions"].items():
        r = c["rep"]
        L.append(f"| {arm} | {r['chars_per_decision']} | {r['bytes_per_decision']} | {r['top_level_fields']} | {r['scalar_values_per_decision']} | {r['input_tokens_per_call']} |")
    p = rep["paired"]
    if p and p.get("rows"):
        a, b = p["a"], p["b"]
        L += ["", f"## Paired by seed: {b} minus {a} (mean of reps within each seed)", "",
              f"| seed | {a} scores | {b} scores | {a} mean | {b} mean | delta |", "|---|---|---|---|---|---|"]
        for r in p["rows"]:
            L.append(f"| {r['seed']} | {r[f'{a}_scores']} | {r[f'{b}_scores']} | {r[f'{a}_mean']} | {r[f'{b}_mean']} | {r['delta_b_minus_a']:+g} |")
        L += ["", f"- Mean delta {p['mean_delta']:+g}, median {p['median_delta']:+g}. {b} higher on {p['seeds_b_higher']}/{p['seeds_paired']} seeds, "
                  f"{a} higher on {p['seeds_a_higher']}, tied {p['seeds_tied']}.",
              f"- Exact sign-flip permutation p (two-sided, seeds as units) = {p['perm_p_two_sided']} "
              f"(smallest possible with {p['seeds_paired']} seeds: {p['perm_min_possible_p']}).",
              f"- Mean within-seed SD across reps: {a} {p[f'{a}_within_seed_sd_mean']}, {b} {p[f'{b}_within_seed_sd_mean']}."]
    if rep.get("tenki"):
        t = rep["tenki"]
        L += ["", "## Tenki", "", "```", json.dumps(t, indent=2), "```"]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exp_dir")
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--tenki")
    args = ap.parse_args()
    eps = load(args.exp_dir)
    exp_id = eps[0]["experiment_id"]
    eps = [e for e in eps if e["experiment_id"] == exp_id]
    by = defaultdict(list)
    for e in eps:
        by[e["summary"]["arm"]].append(e)
    rep = {"experiment_id": exp_id, "conditions": {arm: condition(lst) for arm, lst in sorted(by.items())},
           "paired": paired(eps, args.a, args.b), "tenki": tenki(args.tenki, exp_id) if args.tenki else None}
    out = Path(args.exp_dir) / "analysis"
    out.mkdir(exist_ok=True)
    (out / "report.json").write_text(json.dumps(rep, indent=2))
    md = to_md(rep)
    (out / "report.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
