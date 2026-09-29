"""Behavior analysis of existing traces. No model calls, no games: reads steps.jsonl only.

    python -m ufa.analysis.behavior ufa/traces/exp002_repr_check

Every metric is recomputed from the recorded per-step state with the same deterministic
code for every arm (threat_analysis / representations.threat), so arms are judged by one
yardstick regardless of what their model was shown.
Writes <exp_dir>/analysis/behavior.json and behavior.md.
"""
import argparse
import itertools
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from ufa.arena.compare import load
from ufa.arena.extract import threat_analysis
from ufa.arena.representations import threat as threat_rep

ACTIONS = ["NOOP", "FIRE", "LEFT", "RIGHT", "LEFTFIRE", "RIGHTFIRE"]
PRE = 10  # steps before the hit examined


def d(a):
    return -1 if "LEFT" in a else (1 if "RIGHT" in a else 0)


def lane(a):
    return {-1: "left", 0: "stay", 1: "right"}[d(a)]


def fmean(v):
    v = [x for x in v if x is not None]
    return round(statistics.fmean(v), 4) if v else None


def st(v):
    v = [x for x in v if x is not None]
    if not v:
        return None
    return {"n": len(v), "mean": round(statistics.fmean(v), 2), "median": round(statistics.median(v), 2),
            "sd": round(statistics.stdev(v), 2) if len(v) > 1 else None, "min": min(v), "max": max(v)}


def probs_of(dec):
    try:
        a = dec["answers"]["action"]
    except (TypeError, KeyError):
        return None
    p = a.get("probabilities")
    if isinstance(p, dict):
        return [float(x) for x in p.values()]
    if isinstance(p, list):
        return [float(x["probability"] if isinstance(x, dict) else x) for x in p]
    return None


def episode_metrics(path):
    rows = [json.loads(l) for l in open(Path(path) / "steps.jsonl")]
    acts = [r["action"] for r in rows]
    n = len(acts)
    m = {"n_steps": n, "action_freq": {a: round(acts.count(a) / n, 4) for a in ACTIONS}}
    m["fire_rate"] = round(sum("FIRE" in a for a in acts) / n, 4)
    m["move_rate"] = round(sum(d(a) != 0 for a in acts) / n, 4)
    m["action_change_rate"] = round(sum(acts[i] != acts[i - 1] for i in range(1, n)) / max(n - 1, 1), 4)
    dirs = [d(a) for a in acts]
    moves = [x for x in dirs if x]
    m["direction_flip_rate_per_move"] = round(sum(moves[i] != moves[i - 1] for i in range(1, len(moves))) / max(len(moves) - 1, 1), 4)
    m["immediate_reversal_rate"] = round(sum(dirs[i] and dirs[i - 1] and dirs[i] != dirs[i - 1] for i in range(1, n)) / max(n - 1, 1), 4)
    m["aba_rate"] = round(sum(acts[i] == acts[i - 2] != acts[i - 1] for i in range(2, n)) / max(n - 2, 1), 4)
    runs, cur = [], 1
    for i in range(1, n):
        if dirs[i] == dirs[i - 1] and dirs[i]:
            cur += 1
        else:
            if dirs[i - 1]:
                runs.append(cur)
            cur = 1
    if n and dirs[-1]:
        runs.append(cur)
    m["move_run_len_mean"] = round(statistics.fmean(runs), 2) if runs else None
    xs = [r["state"]["player"]["x"] for r in rows if r["state"]["player"]["x"] is not None]
    m["ship_x_sd"] = round(statistics.pstdev(xs), 1) if len(xs) > 1 else None
    m["ship_abs_dx_per_step"] = round(statistics.fmean(abs(xs[i] - xs[i - 1]) for i in range(1, len(xs))), 2) if len(xs) > 1 else None

    # threat response, fire discipline, sensitivity to irrelevant change
    thr_steps = safe_pick = safe_avail = 0
    fire_ready_above = fire_ready_notabove = fire_inflight = 0
    c_ready_above = c_ready_notabove = c_inflight = 0
    same_rel = same_rel_changed = 0
    prev_rel = None
    probs_top, margins, ents = [], [], []
    for i, r in enumerate(rows):
        s = r["state"]
        t = threat_analysis(s)
        a = r["action"]
        ld = t["lane_danger"]
        if ld["stay"]:
            thr_steps += 1
            if ld["left"] is False or ld["right"] is False:
                safe_avail += 1
                if ld[lane(a)] is False:
                    safe_pick += 1
        f = "FIRE" in a
        if t["shot_in_flight"]:
            c_inflight += 1; fire_inflight += f
        elif t["alien_above"]:
            c_ready_above += 1; fire_ready_above += f
        else:
            c_ready_notabove += 1; fire_ready_notabove += f
        rel = json.dumps(threat_rep(s, []), sort_keys=True)
        if prev_rel is not None and rel == prev_rel:
            same_rel += 1
            same_rel_changed += a != rows[i - 1]["action"]
        prev_rel = rel
        p = probs_of(r.get("decider"))
        if p:
            q = sorted(p, reverse=True)
            probs_top.append(q[0]); margins.append(q[0] - (q[1] if len(q) > 1 else 0))
            ents.append(-sum(x * math.log(x) for x in p if x > 0))
    m.update({
        "threatened_steps": thr_steps, "threatened_with_safe_option": safe_avail,
        "evasion_rate": round(safe_pick / safe_avail, 4) if safe_avail else None,
        "p_fire_ready_alien_above": round(fire_ready_above / c_ready_above, 4) if c_ready_above else None,
        "p_fire_ready_not_above": round(fire_ready_notabove / c_ready_notabove, 4) if c_ready_notabove else None,
        "p_fire_shot_in_flight": round(fire_inflight / c_inflight, 4) if c_inflight else None,
        "share_steps_shot_ready_alien_above": round(c_ready_above / n, 4),
        "steps_relevant_state_unchanged": same_rel,
        "action_change_when_relevant_unchanged": round(same_rel_changed / same_rel, 4) if same_rel else None,
        "top_prob_mean": fmean(probs_top), "margin_mean": fmean(margins),
        "near_tie_rate": round(sum(x < 0.05 for x in margins) / len(margins), 4) if margins else None,
        "entropy_mean": fmean(ents),
    })

    # deaths: hit = start of the invisible-ship run that ends at the life decrement
    deaths = []
    for i, r in enumerate(rows):
        if r["lives"] < r["state"]["lives"]:
            h = i
            while h > 0 and not rows[h]["state"]["player"]["visible"]:
                h -= 1
            h = h + 1 if h < i else i
            if h == i:
                method, h = "fallback_minus_33", max(i - 33, 0)
            else:
                method = "invisible_run"
            win = rows[max(h - PRE, 0):h]
            tw = [threat_analysis(w["state"]) for w in win]
            seen = [bool(x["lane_danger"]["stay"]) for x in tw]
            had_safe = [bool(x["lane_danger"]["stay"] and (x["lane_danger"]["left"] is False or x["lane_danger"]["right"] is False)) for x in tw]
            took_safe = [hs and x["lane_danger"][lane(w["action"])] is False for hs, x, w in zip(had_safe, tw, win)]
            hit_x = next((rows[j]["state"]["player"]["x"] for j in range(h, -1, -1)
                          if rows[j]["state"]["player"]["x"] is not None), None)
            deaths.append({"decrement_step": i, "hit_step": h, "method": method, "hit_x": hit_x,
                           "threat_seen_in_window": any(seen), "steps_threatened": sum(seen),
                           "steps_with_safe_option": sum(had_safe), "steps_safe_taken": sum(took_safe),
                           "actions_before": [w["action"] for w in win]})
    m["deaths"] = deaths
    # scoring
    rew = [r["reward"] for r in rows]
    m["kills"] = sum(x > 0 for x in rew)
    m["kills_per_100_steps"] = round(100 * m["kills"] / n, 2) if n else None
    m["points_per_kill"] = round(sum(rew) / m["kills"], 2) if m["kills"] else None
    m["steps_per_life"] = round(n / max(len(deaths), 1), 1)
    m["_xs"] = xs
    m["points_per_100_steps"] = round(100 * sum(rew) / n, 2) if n else None
    m["first_kill_step"] = next((i for i, x in enumerate(rew) if x > 0), None)
    return m, rows


def mwu_perm(a, b, iters=20000, seed=0):
    """Two-sided permutation test on difference of means (fixed RNG, reproducible)."""
    rng = random.Random(seed)
    obs = abs(statistics.fmean(b) - statistics.fmean(a))
    pool, na, hits = a + b, len(a), 0
    for _ in range(iters):
        rng.shuffle(pool)
        if abs(statistics.fmean(pool[na:]) - statistics.fmean(pool[:na])) >= obs - 1e-9:
            hits += 1
    return round((hits + 1) / (iters + 1), 5)


def compare_pair(A, B):
    """B minus A, paired by seed (replicates averaged within seed) plus all-episode checks."""
    seeds = sorted({e["seed"] for e in A} & {e["seed"] for e in B})
    mean = lambda E, s, k="score": statistics.fmean(e[k] for e in E if e["seed"] == s)
    delta = {s: mean(B, s) - mean(A, s) for s in seeds}
    dv = list(delta.values())
    flips = [statistics.fmean(x * g for x, g in zip(dv, signs)) for signs in itertools.product([1, -1], repeat=len(dv))]
    obs = statistics.fmean(dv)
    pairs = [(bb["score"], aa["score"]) for s in seeds for bb in B if bb["seed"] == s for aa in A if aa["seed"] == s]
    return {"mean_a": round(statistics.fmean(e["score"] for e in A), 1), "mean_b": round(statistics.fmean(e["score"] for e in B), 1),
            "delta_by_seed": {s: round(v, 1) for s, v in delta.items()}, "mean_delta": round(obs, 1),
            "seeds_b_higher": sum(v > 0 for v in dv), "n_seeds": len(dv),
            "seed_perm_p": round(sum(abs(f) >= abs(obs) - 1e-9 for f in flips) / len(flips), 4),
            "episode_perm_p": mwu_perm([e["score"] for e in A], [e["score"] for e in B]),
            "same_seed_pairs_b_gt_a": f"{sum(x > y for x, y in pairs)}/{len(pairs)}",
            "leave_one_seed_out_mean_delta": {s: round(statistics.fmean(v for k, v in delta.items() if k != s), 1) for s in seeds},
            "steps_by_seed": {s: (round(mean(A, s, "steps")), round(mean(B, s, "steps"))) for s in seeds},
            "points_per_100_steps_by_seed": {s: (round(mean(A, s, "points_per_100_steps"), 1), round(mean(B, s, "points_per_100_steps"), 1)) for s in seeds}}


def ols(x, y):
    mx, my = statistics.fmean(x), statistics.fmean(y)
    sxx = sum((a - mx) ** 2 for a in x)
    b = sum((a - mx) * (c - my) for a, c in zip(x, y)) / sxx
    return round(my - b * mx, 1), round(b, 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exp_dir")
    ap.add_argument("--pairs", default="jev_basic__raw:jev_basic__threat", help="a:b,... (reports b minus a)")
    args = ap.parse_args()
    eps = load(args.exp_dir)
    arms = defaultdict(list)
    tok = defaultdict(lambda: ([], []))
    for e in eps:
        s = e["summary"]
        m, rows = episode_metrics(e["_path"])
        rep_idx = s["policy_seed"] - s["seed"] * 1000 if s["policy_seed"] >= 1000 else 0
        m.update({"seed": s["seed"], "replicate": rep_idx, "score": s["score"], "steps": s["steps"],
                  "wall_clock_s": s["wall_clock_s"], "cost_usd": s["cost_usd"], "p50": s["latency_ms_p50"],
                  "rep_chars_mean": s["rep_chars_mean"], "episode_id": s["episode_id"]})
        arms[s["arm"]].append(m)
        for r in rows:
            dec = r.get("decider")
            if dec and dec.get("input_tokens"):
                tok[s["arm"]][0].append(r["rep_chars"]); tok[s["arm"]][1].append(dec["input_tokens"])

    # wall occupancy: ship within 3 px of the smallest / largest x seen in any episode
    allx = [x for E in arms.values() for e in E for x in e["_xs"]]
    lo, hi = min(allx), max(allx)
    for E in arms.values():
        for e in E:
            xs = e.pop("_xs")
            e["left_wall_share"] = round(sum(x <= lo + 3 for x in xs) / len(xs), 4) if xs else None
            e["right_wall_share"] = round(sum(x >= hi - 3 for x in xs) / len(xs), 4) if xs else None
    out = {"conditions": {}, "robustness": {}, "token_fit": {}, "ship_x_range": [lo, hi]}
    for arm, E in sorted(arms.items()):
        agg = {k: st([e[k] for e in E]) for k in
               ["score", "steps", "wall_clock_s", "cost_usd", "kills", "points_per_100_steps", "first_kill_step",
                "kills_per_100_steps", "points_per_kill", "left_wall_share", "right_wall_share",
                "fire_rate", "move_rate", "action_change_rate", "direction_flip_rate_per_move", "immediate_reversal_rate",
                "aba_rate", "move_run_len_mean", "ship_x_sd", "ship_abs_dx_per_step", "evasion_rate",
                "p_fire_ready_alien_above", "p_fire_ready_not_above", "p_fire_shot_in_flight",
                "share_steps_shot_ready_alien_above", "action_change_when_relevant_unchanged",
                "top_prob_mean", "margin_mean", "near_tie_rate", "entropy_mean"]}
        tot = sum(e["n_steps"] for e in E)
        agg["action_freq_pooled"] = {a: round(sum(e["action_freq"][a] * e["n_steps"] for e in E) / tot, 4) for a in ACTIONS}
        agg["steps_per_life"] = round(tot / max(sum(len(e["deaths"]) for e in E), 1), 1)
        D = [x for e in E for x in e["deaths"]]
        agg["deaths"] = {"n": len(D), "hit_found_by_invisible_run": sum(x["method"] == "invisible_run" for x in D),
                         "threat_seen_before_hit": sum(x["threat_seen_in_window"] for x in D),
                         "had_safe_option_before_hit": sum(x["steps_with_safe_option"] > 0 for x in D),
                         "safe_option_taken_share": round(sum(x["steps_safe_taken"] for x in D) / max(sum(x["steps_with_safe_option"] for x in D), 1), 4),
                         "pre_hit_action_freq": {a: round(c / max(len(D) * PRE, 1), 4) for a, c in
                                                 Counter(a for x in D for a in x["actions_before"]).items()},
                         "pre_hit_move_rate": round(sum(d(a) != 0 for x in D for a in x["actions_before"]) / max(sum(len(x["actions_before"]) for x in D), 1), 4)}
        agg["by_seed"] = {s: [e["score"] for e in sorted(E, key=lambda e: e["replicate"]) if e["seed"] == s] for s in sorted({e["seed"] for e in E})}
        agg["by_replicate_mean"] = {r: round(statistics.fmean(e["score"] for e in E if e["replicate"] == r), 1) for r in sorted({e["replicate"] for e in E})}
        agg["episodes"] = [{k: e[k] for k in ("seed", "replicate", "score", "steps", "kills", "fire_rate", "evasion_rate", "episode_id")} for e in E]
        out["conditions"][arm] = agg
        if tok[arm][0]:
            out["token_fit"][arm] = dict(zip(["intercept_tokens", "tokens_per_char"], ols(*tok[arm])))

    for pair in args.pairs.split(","):
        a, b = pair.split(":")
        A, B = arms.get(a, []), arms.get(b, [])
        if A and B:
            out["robustness"][f"{b} minus {a}"] = compare_pair(A, B)

    od = Path(args.exp_dir) / "analysis"
    od.mkdir(exist_ok=True)
    (od / "behavior.json").write_text(json.dumps(out, indent=2, default=str))
    keys = ["score", "steps", "kills", "points_per_100_steps", "kills_per_100_steps", "points_per_kill",
            "left_wall_share", "right_wall_share", "fire_rate", "move_rate", "action_change_rate",
            "direction_flip_rate_per_move", "immediate_reversal_rate", "aba_rate", "move_run_len_mean", "ship_abs_dx_per_step",
            "evasion_rate", "p_fire_ready_alien_above", "p_fire_ready_not_above", "p_fire_shot_in_flight",
            "action_change_when_relevant_unchanged", "top_prob_mean", "near_tie_rate", "entropy_mean"]
    names = list(out["conditions"])
    L = ["| metric (episode mean) | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for k in keys:
        L.append(f"| {k} | " + " | ".join(str((out['conditions'][a][k] or {}).get('mean')) for a in names) + " |")
    L.append("| steps_per_life | " + " | ".join(str(out['conditions'][a]['steps_per_life']) for a in names) + " |")
    for a in names:
        L += ["", f"**{a}** actions {out['conditions'][a]['action_freq_pooled']}",
              f"deaths {json.dumps(out['conditions'][a]['deaths'])}",
              f"by seed {out['conditions'][a]['by_seed']}  by replicate {out['conditions'][a]['by_replicate_mean']}"]
    L += ["", "robustness " + json.dumps(out["robustness"], default=str), "", "token fit " + json.dumps(out["token_fit"])]
    md = "\n".join(L) + "\n"
    (od / "behavior.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
