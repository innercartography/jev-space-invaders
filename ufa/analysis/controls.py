"""exp004 analysis: scripted controls vs JEV (exp003). Reads traces only; no games, no model calls.

    python -m ufa.analysis.controls ufa/traces/exp004_scripted_controls \
        --jev ufa/traces/exp003_hint_decomposition --core-seeds 1,2,3,4,5

"core" = the seeds JEV was run on; "extra" = every other control seed. The controls and the env are
deterministic, so each control has exactly one game per seed.
Writes <exp004>/analysis/controls.json and controls.md.
"""
import argparse
import json
import random
import statistics
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

from ufa.analysis.behavior import compare_pair, episode_metrics, st
from ufa.arena.compare import load

KEYS = ["score", "steps", "points_per_100_steps", "kills_per_100_steps", "points_per_kill",
        "left_wall_share", "right_wall_share", "fire_rate", "p_fire_shot_in_flight",
        "direction_flip_rate_per_move", "move_run_len_mean"]
REGIONS = ["left_wall", "middle", "right_wall"]


def one(e):
    s = e["summary"]
    m, _ = episode_metrics(e["_path"])
    m.update({"seed": s["seed"], "score": s["score"], "steps": s["steps"], "arm": s["arm"]})
    return m


def region(x, lo, hi):
    if x is None:
        return "unknown"
    return "left_wall" if x <= lo + 3 else ("right_wall" if x >= hi - 3 else "middle")


def summarize(E, lo, hi):
    agg = {k: st([e[k] for e in E]) for k in KEYS}
    D = [x for e in E for x in e["deaths"]]
    agg["steps_per_life"] = round(sum(e["n_steps"] for e in E) / max(len(D), 1), 1)
    occ = Counter(region(x, lo, hi) for e in E for x in e["_xs"])
    died = Counter(region(x["hit_x"], lo, hi) for x in D)
    agg["deaths_by_region"] = {r: {"deaths": died[r], "share_of_deaths": round(died[r] / max(len(D), 1), 3),
                                   "share_of_time": round(occ[r] / max(sum(occ.values()), 1), 3),
                                   "deaths_per_100_steps_there": round(100 * died[r] / occ[r], 3) if occ[r] else None}
                               for r in REGIONS}
    return agg


def paired_vs(E_b, E_a, iters=20000):
    """b minus a on the seeds both have; random sign-flip permutation test (fixed RNG)."""
    a = {e["seed"]: statistics.fmean(x["score"] for x in E_a if x["seed"] == e["seed"]) for e in E_a}
    b = {e["seed"]: statistics.fmean(x["score"] for x in E_b if x["seed"] == e["seed"]) for e in E_b}
    dv = [b[s] - a[s] for s in sorted(set(a) & set(b))]
    obs = statistics.fmean(dv)
    rng = random.Random(0)
    hits = sum(abs(statistics.fmean(x if rng.random() < 0.5 else -x for x in dv)) >= abs(obs) - 1e-9 for _ in range(iters))
    return {"n_seeds": len(dv), "mean_delta": round(obs, 1), "seeds_b_higher": sum(x > 0 for x in dv),
            "seeds_tied": sum(x == 0 for x in dv), "p": round((hits + 1) / (iters + 1), 5)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exp_dir")
    ap.add_argument("--jev", required=True)
    ap.add_argument("--core-seeds", default="1,2,3,4,5")
    ap.add_argument("--procs", type=int, default=16)
    args = ap.parse_args()
    core = {int(s) for s in args.core_seeds.split(",")}

    eps = load(args.exp_dir) + [e for e in load(args.jev) if e["summary"]["seed"] in core]
    with Pool(args.procs) as pool:
        ms = pool.map(one, eps, chunksize=8)
    arms = defaultdict(list)
    for m in ms:
        arms[m["arm"]].append(m)
    allx = [x for m in ms for x in m["_xs"]]
    lo, hi = min(allx), max(allx)
    for m in ms:
        xs = m["_xs"]
        m["left_wall_share"] = round(sum(x <= lo + 3 for x in xs) / len(xs), 4) if xs else None
        m["right_wall_share"] = round(sum(x >= hi - 3 for x in xs) / len(xs), 4) if xs else None

    jev = sorted(a for a in arms if a.startswith("jev_"))
    ctl = sorted(a for a in arms if not a.startswith("jev_"))
    out = {"ship_x_range": [lo, hi], "core_seeds": sorted(core), "core": {}, "extra": {}, "all": {},
           "core_vs_threat": {}, "explained": {}, "extra_vs_random": {}, "extra_pairwise": {}, "core_typicality": {}}
    for a in jev + ctl:
        c = [e for e in arms[a] if e["seed"] in core]
        x = [e for e in arms[a] if e["seed"] not in core]
        out["core"][a] = summarize(c, lo, hi)
        out["core"][a]["by_seed"] = {s: [e["score"] for e in c if e["seed"] == s] for s in sorted(core)}
        if x:
            out["extra"][a] = summarize(x, lo, hi)
            out["all"][a] = summarize(arms[a], lo, hi)

    T, R = arms.get("jev_basic__threat"), arms.get("jev_basic__raw")
    mean = lambda E: statistics.fmean(e["score"] for e in E)
    rnd_all = mean(arms["random__raw"]) if "random__raw" in arms else None
    for a in ctl:
        c = [e for e in arms[a] if e["seed"] in core]
        if T:
            out["core_vs_threat"][a] = compare_pair(T, c)  # control minus THREAT
            ex = {"control_over_threat_score": round(mean(c) / mean(T), 3)}
            if R:
                ex["share_of_threat_gain_over_raw"] = round((mean(c) - mean(R)) / (mean(T) - mean(R)), 3)
            if rnd_all is not None:
                ex["share_of_threat_gain_over_random_floor"] = round((mean(c) - rnd_all) / (mean(T) - rnd_all), 3)
            out["explained"][a] = ex
        x = sorted(e["score"] for e in arms[a] if e["seed"] not in core)
        if x:
            cm = mean(c)
            out["core_typicality"][a] = {"core_mean": round(cm, 1), "extra_mean": round(statistics.fmean(x), 1),
                                         "extra_seeds_below_core_mean": round(sum(v < cm for v in x) / len(x), 3)}
    if "random__raw" in arms:
        rx = [e for e in arms["random__raw"] if e["seed"] not in core]
        for a in ctl:
            if a != "random__raw":
                out["extra_vs_random"][a] = paired_vs([e for e in arms[a] if e["seed"] not in core], rx)
    names = [a for a in ctl if a != "random__raw"]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            out["extra_pairwise"][f"{b} minus {a}"] = paired_vs([e for e in arms[b] if e["seed"] not in core],
                                                                 [e for e in arms[a] if e["seed"] not in core])

    od = Path(args.exp_dir) / "analysis"
    od.mkdir(exist_ok=True)
    (od / "controls.json").write_text(json.dumps(out, indent=2, default=str))
    L = []
    for sub in ("core", "extra"):
        names_s = list(out[sub])
        L += [f"## {sub} seeds", "| metric (episode mean) | " + " | ".join(names_s) + " |", "|---|" + "---|" * len(names_s)]
        for k in KEYS:
            L.append(f"| {k} | " + " | ".join(str((out[sub][a][k] or {}).get("mean")) for a in names_s) + " |")
        L.append("| score median | " + " | ".join(str(out[sub][a]["score"]["median"]) for a in names_s) + " |")
        L.append("| score sd | " + " | ".join(str(out[sub][a]["score"]["sd"]) for a in names_s) + " |")
        L.append("| steps_per_life | " + " | ".join(str(out[sub][a]["steps_per_life"]) for a in names_s) + " |")
        for r in REGIONS:
            L.append(f"| deaths/100 steps at {r} (time share) | " + " | ".join(
                f"{out[sub][a]['deaths_by_region'][r]['deaths_per_100_steps_there']} ({out[sub][a]['deaths_by_region'][r]['share_of_time']})"
                for a in names_s) + " |")
        L.append("")
    for k in ("core_vs_threat", "explained", "core_typicality", "extra_vs_random", "extra_pairwise"):
        L += [f"## {k}", "```", json.dumps(out[k], indent=1, default=str), "```", ""]
    L += ["## core by seed", "```", json.dumps({a: out["core"][a]["by_seed"] for a in out["core"]}), "```"]
    md = "\n".join(L) + "\n"
    (od / "controls.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
