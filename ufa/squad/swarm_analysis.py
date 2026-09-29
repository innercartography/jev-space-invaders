"""Analyse a swarm run: per-condition metrics with bootstrap CIs, pre-registered paired comparisons, one figure.

    python -m ufa.squad.swarm_analysis --run s1
"""
import argparse
import json
import random
import statistics
from pathlib import Path

from ufa.squad.swarm import CONDS, HERE, NEAR, R, W

NAMES = {"A": "No shared memory (decentralized)", "B": "Shared Mitosis memory (decentralized)",
         "C": "Fixed hierarchy + Mitosis", "D": "Adaptive JEV governance + Mitosis",
         "E": "Adaptive JEV, no Mitosis", "F": "Adaptive rule (no model) + Mitosis"}
PAIRS = [("D", "B"), ("D", "C"), ("D", "F"), ("B", "A"), ("D", "E"), ("C", "B")]


def boot(xs, n=5000, seed=0):
    rng = random.Random(seed)
    m = statistics.fmean(xs)
    bs = sorted(statistics.fmean(rng.choices(xs, k=len(xs))) for _ in range(n))
    return round(m, 1), [round(bs[int(0.025 * n)], 1), round(bs[int(0.975 * n) - 1], 1)]


def load(run):
    out = {}
    for f in sorted((HERE / "runs" / run).glob("*_t*.json")):
        d = json.loads(f.read_text())
        out.setdefault(d["condition"], {})[d["trial"]] = d
    return out


def metrics(d):
    p1, p2 = d["phases"]
    m = {"ph1_regret_auc": p1["regret_auc"], "ph2_regret_auc": p2["regret_auc"],
         "total_regret_auc": (p1["regret_auc"] + p2["regret_auc"]) / 2,
         "ph1_final_regret": p1["final_regret"], "ph2_final_regret": p2["final_regret"],
         "ph1_found_best": float(p1["final_regret"] <= NEAR), "ph2_found_best": float(p2["final_regret"] <= NEAR),
         "ph1_rounds_to_best": p1["rounds_to_near_best"] or R + 1, "ph2_rounds_to_best": p2["rounds_to_near_best"] or R + 1,
         "ph2_rounds_to_within_50": p2["rounds_to_within_50"] or R + 1,
         "ph1_dominated_games": p1["dominated_games"], "ph2_dominated_games": p2["dominated_games"],
         "ph1_rediscovery_games": p1["rediscovery_games"], "ph2_rediscovery_games": p2["rediscovery_games"],
         "ph1_duplicate_games": p1["duplicate_games"], "ph2_duplicate_games": p2["duplicate_games"],
         "ph1_unique_configs": p1["unique_configs"], "ph2_unique_configs": p2["unique_configs"],
         "ph1_entropy_bits": p1["alloc_entropy_bits"], "ph2_entropy_bits": p2["alloc_entropy_bits"],
         "ph2_stale_led_games": p2["stale_led_games"],
         "ph2_regret_first5": statistics.fmean(p2["regret_curve"][:5]),
         "coordinate_share": (p1["mode_rounds"]["COORDINATE"] + p2["mode_rounds"]["COORDINATE"]) / (2 * R),
         "ph1_coordinate_share": p1["mode_rounds"]["COORDINATE"] / R, "ph2_coordinate_share": p2["mode_rounds"]["COORDINATE"] / R,
         "transitions": p1["transitions"] + p2["transitions"]}
    for i, p in ((1, p1), (2, p2)):
        m[f"ph{i}_stopped"] = float(p["stop_round"] is not None)
        m[f"ph{i}_premature_stop"] = float(bool(p["premature_stop"]))
        m[f"ph{i}_rule_stopped"] = float(p["rule_stop_round"] is not None)
    ret = p2.get("retrieved_inherited")
    if ret:
        m["retrieved_findings"] = len(ret)
        m["retrieved_stale"] = sum(1 for v in ret.values() if v["stale"])
        chall = [h["judgments"].get("challenge") for h in p2["rounds"] if h["judgments"].get("challenge") not in (None, "NONE")]
        # the rule governor's judgments are in the round log too (condition F)
        m["challenges"] = len(chall)
        m["challenges_of_stale"] = sum(1 for c in chall if ret.get(c, {}).get("stale"))
        m["challenges_of_valid"] = len(chall) - m["challenges_of_stale"]
        first = next((h["round"] for h in p2["rounds"] if ret.get(h["judgments"].get("challenge") or "", {}).get("stale")), None)
        m["first_stale_challenge_round"] = first if first is not None else R
        st = p2.get("inherited_final_status") or {}
        for s in ("ACTIVE", "CHALLENGED", "FALSIFIED", "SUPERSEDED"):
            m[f"final_status_{s}"] = sum(1 for v in st.values() if v == s)
    g = d.get("governor")
    if g and g["kind"] == "adaptive_jev":
        m["jev_calls"] = g["calls"]
        m["jev_cost_usd"] = g["cost_usd"] or 0
        m["jev_errors"] = g["errors"] + g["unanswered"]
    mi = d.get("mitosis")
    if mi:
        m["mitosis_ops"] = mi["write_calls"] + mi["read_calls"]
        m["mitosis_read_ms_p50"] = mi["read_ms_p50"]
        m["mitosis_read_mismatch"] = mi["read_mismatch"]
        m["mitosis_fail"] = mi["read_fail"] + mi["write_fail"]
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="s1")
    ap.add_argument("--fig", default=str(Path("demo/assets/fig8_swarm_memory_drag.png")))
    a = ap.parse_args()
    data = load(a.run)
    M = {c: {t: metrics(d) for t, d in ts.items()} for c, ts in data.items()}
    summary = {}
    for c in sorted(M):
        keys = sorted({k for v in M[c].values() for k in v})
        summary[c] = {"name": NAMES[c], "trials": len(M[c])}
        for k in keys:
            xs = [v[k] for v in M[c].values() if v.get(k) is not None]
            if xs:
                summary[c][k] = boot(xs)
    comps = {}
    for x, y in PAIRS:
        if x not in M or y not in M:
            continue
        ts = sorted(set(M[x]) & set(M[y]))
        for k in ("ph1_regret_auc", "ph2_regret_auc", "total_regret_auc", "ph2_stale_led_games", "ph1_dominated_games",
                  "ph2_dominated_games", "ph2_regret_first5"):
            diffs = [M[x][t][k] - M[y][t][k] for t in ts]
            comps[f"{x}-{y} {k}"] = {"diff": boot(diffs), "x_better_trials": sum(d < 0 for d in diffs),
                                    "y_better_trials": sum(d > 0 for d in diffs), "n": len(ts)}
    # memory benefit (phase 1) and drag (phase 2): no-memory minus memory, same governance
    mem = {}
    for nomem, withmem, label in (("A", "B", "decentralized"), ("E", "D", "adaptive JEV")):
        if nomem in M and withmem in M:
            ts = sorted(set(M[nomem]) & set(M[withmem]))
            mem[label] = {
                "memory_benefit_ph1_auc": boot([M[nomem][t]["ph1_regret_auc"] - M[withmem][t]["ph1_regret_auc"] for t in ts]),
                "memory_drag_ph2_auc": boot([M[withmem][t]["ph2_regret_auc"] - M[nomem][t]["ph2_regret_auc"] for t in ts]),
                "memory_drag_ph2_first5": boot([M[withmem][t]["ph2_regret_first5"] - M[nomem][t]["ph2_regret_first5"] for t in ts]),
                "rediscovery_avoided_ph1": boot([M[nomem][t]["ph1_rediscovery_games"] - M[withmem][t]["ph1_rediscovery_games"] for t in ts])}
    curves = {c: [statistics.fmean(d["phases"][0]["regret_curve"][i] if i < R else d["phases"][1]["regret_curve"][i - R]
                                   for d in data[c].values()) for i in range(2 * R)] for c in data}
    out = {"run": a.run, "conditions": summary, "paired": comps, "memory": mem, "mean_regret_curves": {c: [round(x, 1) for x in v] for c, v in curves.items()}}
    (HERE / "runs" / a.run / "analysis.json").write_text(json.dumps(out, indent=1))
    figure(curves, a.fig, {c: len(data[c]) for c in data})
    for c in sorted(summary):
        s = summary[c]
        print(c, s["name"], "n", s["trials"], "| ph1 AUC", s["ph1_regret_auc"], "| ph2 AUC", s["ph2_regret_auc"],
              "| total", s["total_regret_auc"], "| ph2 found best", s["ph2_found_best"][0], "| stale games", s["ph2_stale_led_games"][0])
    print(json.dumps(mem, indent=1))


def figure(curves, path, ns):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    style = {"A": ("#7f8c8d", "-", 2.2), "B": ("#2e86c1", "-", 2.2), "C": ("#8e44ad", "-", 2.2), "D": ("#e08e0b", "-", 3.2),
             "E": ("#e08e0b", ":", 1.6), "F": ("#27ae60", "--", 1.6)}
    fig, ax = plt.subplots(figsize=(10, 6.2), dpi=150)
    xs = list(range(1, 2 * R + 1))
    for c in ("A", "B", "C", "F", "D"):  # E (JEV, no memory) overlaps A; in the table
        if c in curves:
            col, ls, lw = style[c]
            ax.plot(xs[:R], curves[c][:R], ls, color=col, lw=lw, label=f"{NAMES[c]} (n={ns[c]})")
            ax.plot(xs[R:], curves[c][R:], ls, color=col, lw=lw)  # separate line: a different game
    ax.axvline(R + 0.5, color="#c0392b", lw=1.5, ls="--")
    ax.text(R + 0.8, ax.get_ylim()[1] * 0.95, "game variation changes", color="#c0392b", va="top", fontsize=10)
    ax.set_xlabel(f"round (each round = {W} games, one per worker)")
    ax.set_ylabel("points below the best configuration\n(swarm's current pick; lower is better)")
    ax.set_title("Squad swarm: how far the swarm's pick is from the best, before and after the game changes", fontsize=11, loc="left")
    ax.set_xlim(1, 2 * R)
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2, frameon=False)
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    print(f"-> {path}")


if __name__ == "__main__":
    main()
