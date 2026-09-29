"""Tournament report: every arm of an experiment on a common seed set, one yardstick.

    python -m ufa.analysis.tournament --exp ufa/traces/exp006_tournament --ref ref --control control_sweep \
        --seeds-file ufa/experiments/seeds_dev.json --seed-range 0:20 --tag stageA

For each arm: performance (with and without bonus-ship points), behavior, system (calls, latency,
tokens, cost, failures), and paired seed-by-seed comparisons against the reference arm and the
sweep control. Paired comparisons use only seeds both arms played. Where an arm has several games
on one seed, the seed's mean is used. Reads traces only: no games, no model calls.
Writes <exp>/analysis/tournament_<tag>.json and .md.
"""
import argparse
import json
import statistics
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

from ufa.analysis.behavior import d as move_dir
from ufa.analysis.oos import BONUS, ep_metrics, paired, region
from ufa.arena.compare import load
from ufa.arena.extract import move_safety


def extra_metrics(path):
    """Projected-threat response (uses extract.move_safety on the recorded state, for every arm) and
    confidence by outcome."""
    rows = [json.loads(l) for l in open(Path(path) / "steps.jsonl")]
    thr = took_safe = had_safe = 0
    conf_all = []
    for r in rows:
        ms = move_safety(r["state"])
        if r.get("confidence") is not None:
            conf_all.append(r["confidence"])
        if ms and not ms["stay"]:
            thr += 1
            if ms["left"] or ms["right"]:
                had_safe += 1
                took_safe += ms[{-1: "left", 0: "stay", 1: "right"}[move_dir(r["action"])]]
    return {"proj_threat_steps": thr, "proj_threat_share": round(thr / len(rows), 4) if rows else None,
            "proj_safe_pick_rate": round(took_safe / had_safe, 4) if had_safe else None,
            "mean_confidence_steps": round(statistics.fmean(conf_all), 4) if conf_all else None}


def metrics(e):
    m = ep_metrics(e)
    m.update(extra_metrics(e["_path"]))
    s = e["summary"]
    for k in ("model_calls", "input_tokens", "latency_ms_p50", "latency_ms_p95", "fallback_actions", "errors_by_status",
              "retries", "rep_chars_mean", "cost_per_decision_usd", "decision_interval_steps", "held_steps",
              "mean_confidence", "wall_clock_s"):
        m[k] = s.get(k)
    m["death_regions"] = Counter(region(x["hit_x"]) for x in m["deaths"])
    m.pop("action_freq", None)
    return m


def q(v, p):
    s = sorted(v)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return round(s[f] + (s[c] - s[f]) * (k - f), 1)


def arm_summary(E):
    sc = [e["score"] for e in E]
    xb = [e["score_ex_bonus"] for e in E]
    mean = lambda k: (round(statistics.fmean(v), 4) if (v := [e[k] for e in E if e.get(k) is not None]) else None)
    calls = [e["model_calls"] for e in E if e.get("model_calls") is not None]
    toks = sum(e["input_tokens"] or 0 for e in E if e.get("input_tokens") is not None)
    cost = [e["cost_usd"] for e in E if e.get("cost_usd") is not None]
    deaths = Counter()
    for e in E:
        deaths.update(e["death_regions"])
    errs = Counter()
    for e in E:
        errs.update(e.get("errors_by_status") or {})
    return {
        "n_games": len(E),
        "performance": {
            "score_mean": round(statistics.fmean(sc), 1), "score_median": statistics.median(sc),
            "score_sd": round(statistics.stdev(sc), 1) if len(sc) > 1 else None,
            "score_q10_q25_q75_q90": [q(sc, p) for p in (0.1, 0.25, 0.75, 0.9)], "score_min": min(sc), "score_max": max(sc),
            "score_ex_bonus_mean": round(statistics.fmean(xb), 1), "score_ex_bonus_median": statistics.median(xb),
            "bonus_pts_per_game": round(statistics.fmean(e["bonus_pts"] for e in E), 1),
            "games_with_bonus": sum(e["bonus_hits"] > 0 for e in E),
            "steps_per_game": mean("steps"), "steps_per_life": round(sum(e["steps"] for e in E) / max(sum(len(e["deaths"]) for e in E), 1), 1),
            "points_per_100_steps": mean("points_per_100_steps"), "kills_per_100_steps": mean("kills_per_100_steps"),
            "top_row_kills_per_game": mean("top_row_kills")},
        "behavior": {
            "reversal_rate": mean("direction_flip_rate_per_move"), "run_length": mean("move_run_len_mean"),
            "move_rate": mean("move_rate"), "fire_occupancy": mean("fire_rate"),
            "fire_while_shot_active": mean("p_fire_shot_in_flight"), "fire_immediately_when_ready": mean("fire_immediately_share"),
            "left_wall_share": mean("left_wall_share"), "right_wall_share": mean("right_wall_share"),
            "lane_threat_evasion_rate": mean("evasion_rate"), "projected_threat_share": mean("proj_threat_share"),
            "projected_threat_safe_pick_rate": mean("proj_safe_pick_rate"),
            "deaths_by_region": dict(deaths)},
        "system": {
            "model_calls_per_game": round(statistics.fmean(calls), 1) if calls else None,
            "calls_per_step": round(sum(calls) / sum(e["steps"] for e in E), 3) if calls else None,
            "latency_p50_ms_median_of_games": round(statistics.median(v), 1) if (v := [e["latency_ms_p50"] for e in E if e.get("latency_ms_p50") is not None]) else None,
            "latency_p95_ms_median_of_games": round(statistics.median(v), 1) if (v := [e["latency_ms_p95"] for e in E if e.get("latency_ms_p95") is not None]) else None,
            "input_chars_per_decision": mean("rep_chars_mean"),
            "input_tokens_per_call": round(toks / sum(calls), 1) if calls and sum(calls) else None,
            "cost_per_decision_usd": round(sum(cost) / sum(calls), 8) if cost and calls and sum(calls) else None,
            "cost_per_game_usd": round(statistics.fmean(cost), 5) if cost else None, "cost_total_usd": round(sum(cost), 4) if cost else None,
            "fallbacks_total": sum(e.get("fallback_actions") or 0 for e in E), "errors_by_status": dict(errs),
            "retries_total": sum(e.get("retries") or 0 for e in E),
            "mean_confidence": mean("mean_confidence"),
            "served_models": sorted({str(e.get("served_model")) for e in E})},
    }


def by_seed(E, k):
    d = defaultdict(list)
    for e in E:
        d[e["seed"]].append(e[k])
    return {s: statistics.fmean(v) for s, v in d.items()}


def paired_vs(A, B):
    out = {}
    for k in ("score", "score_ex_bonus"):
        a, b = by_seed(A, k), by_seed(B, k)
        seeds = sorted(set(a) & set(b))
        if len(seeds) >= 3:
            out[k] = paired([a[s] - b[s] for s in seeds])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", required=True, nargs="+", help="experiment trace dir(s)")
    ap.add_argument("--ref", default="ref")
    ap.add_argument("--control", default="control_sweep")
    ap.add_argument("--arms", help="comma-separated arms to include (default: all)")
    ap.add_argument("--seeds-file")
    ap.add_argument("--seed-range", default=":")
    ap.add_argument("--tag", default="all")
    ap.add_argument("--procs", type=int, default=20)
    args = ap.parse_args()

    eps = [e for d in args.exp for e in load(d)]
    if args.seeds_file:
        lo, _, hi = args.seed_range.partition(":")
        keep = set(json.loads(Path(args.seeds_file).read_text())["seeds"][int(lo) if lo else None:int(hi) if hi else None])
        eps = [e for e in eps if e["summary"]["seed"] in keep]
    if args.arms:
        want = set(args.arms.split(","))
        eps = [e for e in eps if e["summary"]["arm"] in want]
    with Pool(args.procs) as pool:
        ms = pool.map(metrics, eps, chunksize=2)
    by = defaultdict(list)
    for m in ms:
        by[m["arm"]].append(m)
    out = {"tag": args.tag, "exp": args.exp, "arms": {}}
    for arm, E in sorted(by.items()):
        out["arms"][arm] = arm_summary(E)
        if arm != args.ref and args.ref in by:
            out["arms"][arm]["vs_ref"] = paired_vs(E, by[args.ref])
        if arm != args.control and args.control in by:
            out["arms"][arm]["vs_sweep"] = paired_vs(E, by[args.control])
    od = Path(args.exp[0]) / "analysis"
    od.mkdir(exist_ok=True)
    (od / f"tournament_{args.tag}.json").write_text(json.dumps(out, indent=1, default=str))

    L = [f"# Tournament {args.tag}", "",
         "| arm | n | score | ex-bonus | median | SD | vs ref (ex-bonus) | W/T/L vs ref | vs sweep (ex-bonus) | flips | run | fire in flight | proj. safe pick | steps | calls/game | p50 ms | $/game |",
         "|---|" + "---|" * 16]
    rank = sorted(out["arms"].items(), key=lambda kv: -kv[1]["performance"]["score_ex_bonus_mean"])
    for arm, a in rank:
        P, B, S = a["performance"], a["behavior"], a["system"]
        vr = a.get("vs_ref", {})
        vs = a.get("vs_sweep", {})
        f = lambda p: f"{p['mean']:+.0f} [{p['ci95_bootstrap'][0]:+.0f},{p['ci95_bootstrap'][1]:+.0f}]" if p else "-"
        wtl = lambda p: f"{p['jev_wins']}/{p['ties']}/{p['jev_losses']}" if p else "-"
        cols = [arm, a["n_games"], f"{P['score_mean']:.0f}", f"{P['score_ex_bonus_mean']:.0f}", f"{P['score_median']:.0f}",
                P["score_sd"], f"{f(vr.get('score_ex_bonus'))} (all: {f(vr.get('score'))})", wtl(vr.get("score")),
                f(vs.get("score_ex_bonus")), B["reversal_rate"], B["run_length"], B["fire_while_shot_active"],
                B["projected_threat_safe_pick_rate"], f"{P['steps_per_game']:.0f}", S["model_calls_per_game"],
                S["latency_p50_ms_median_of_games"], S["cost_per_game_usd"]]
        L.append("| " + " | ".join(str(c) for c in cols) + " |")
    L += ["", "Brackets: bootstrap 95% CI of the paired mean difference. Ex-bonus = score minus bonus-ship (>=50 pt) rewards.",
          "", "```", json.dumps(out, indent=1, default=str), "```"]
    (od / f"tournament_{args.tag}.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:len(rank) + 6]))


if __name__ == "__main__":
    main()
