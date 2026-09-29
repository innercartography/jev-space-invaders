"""Numerical demo assets (plots + data) from traces and analysis outputs. No model calls.

    python -m ufa.analysis.demo_assets --out demo/assets

Every number is read from traces or analysis JSON written by other scripts; nothing is typed in.
Figures:
  fig1_same_model_different_view  ship x over time, same seed: RAW view vs THREAT vs SAFE (jitter
                                   is visible), with score / reversal / wasted-fire panels
  fig2_falsification              what we believed, what the evidence said
  fig3_decision_bench             accuracy on critical moments, latency, cost: JEV vs Haiku, two views
  fig4_realtime                   the game doesn't wait: JEV vs Haiku on the real-time clock
  fig5_tournament                 dev tournament, paired effect vs the reference (with and without bonus)
"""
import argparse
import json
import random
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from ufa.analysis.behavior import episode_metrics  # noqa: E402
from ufa.arena.compare import load  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
C = {"raw": "#b8b8b8", "threat": "#6c8ebf", "safe": "#d4553a", "haiku": "#7a5195", "sweep": "#58a55c", "final": "#e08e0b", "ink": "#222"}
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 150})


def xs(path, n=400):
    rows = [json.loads(l) for l in open(Path(path) / "steps.jsonl")][:n]
    return [r["state"]["player"]["x"] for r in rows]


def fig1(out, exp3, exp6):
    e3 = load(exp3)
    e6 = [e for e in load(exp6) if e["summary"]["arm"] in ("safe", "ref", "safe_sweepwords")]
    groups = {"RAW view": [e for e in e3 if e["summary"]["arm"] == "jev_basic__raw"],
              "THREAT view": [e for e in e3 if e["summary"]["arm"] == "jev_basic__threat"],
              "SAFE view": [e for e in e6 if e["summary"]["arm"] == "safe"],
              "FINAL": [e for e in e6 if e["summary"]["arm"] == "safe_sweepwords"]}
    ms = {k: [episode_metrics(e["_path"])[0] | {"score": e["summary"]["score"], "steps": e["summary"]["steps"]} for e in v] for k, v in groups.items()}
    fig = plt.figure(figsize=(12, 7.6))
    gs = fig.add_gridspec(4, 3, width_ratios=[2.2, 1, 1], hspace=0.7, wspace=0.45, top=0.88)
    seed = 1
    tr = {"RAW view": next(e for e in groups["RAW view"] if e["summary"]["seed"] == seed),
          "THREAT view": next(e for e in groups["THREAT view"] if e["summary"]["seed"] == seed)}
    col = {"RAW view": C["raw"], "THREAT view": C["threat"], "SAFE view": C["safe"], "FINAL": C["final"]}
    fin = {e["summary"]["seed"]: e for e in groups["FINAL"]}
    s = sorted((e for e in groups["SAFE view"] if e["summary"]["seed"] in fin), key=lambda e: e["summary"]["seed"])[0]
    tr["SAFE view"] = s
    tr["FINAL"] = fin[s["summary"]["seed"]]
    N = 200
    for i, (k, e) in enumerate(tr.items()):
        ax = fig.add_subplot(gs[i, 0])
        acts = [json.loads(l)["action"] for l in open(Path(e["_path"]) / "steps.jsonl")][:N]
        d = [(-1 if "LEFT" in a else 1 if "RIGHT" in a else 0) for a in acts]
        cmap = {-1: "#2c7bb6", 1: "#fdae61", 0: "#eeeeee"}
        ax.bar(range(len(d)), [1] * len(d), width=1.0, color=[cmap[v] for v in d])
        flips = sum(1 for j in range(1, len(d)) if d[j] and d[j - 1] and d[j] != d[j - 1])
        ax.set_yticks([])
        ax.set_xlim(0, N)
        ax.set_title(f"{k}: first {N} moves, {flips} instant reversals", loc="left", fontsize=10)
    ax.set_xlabel("decision   (blue = left, orange = right, gray = no move)")
    names = list(groups)
    for j, (key, lab) in enumerate((("score", "mean score"), ("direction_flip_rate_per_move", "reversal rate"),
                                     ("p_fire_shot_in_flight", "fires while shot in flight"), ("steps", "steps survived"))):
        ax = fig.add_subplot(gs[j, 1:])
        vals = [statistics.fmean(m[key] for m in ms[k] if m.get(key) is not None) for k in names]
        ax.barh(names, vals, color=[col[k] for k in names])
        for y, v in enumerate(vals):
            ax.text(v, y, f" {v:.2f}" if v < 5 else f" {v:.0f}", va="center", fontsize=9)
        ax.set_title(lab, loc="left", fontsize=10)
        ax.invert_yaxis()
    fig.suptitle("Same model (jev-1.13.0), same game. Only the view changes.", x=0.01, y=0.985, ha="left", fontsize=14, weight="bold")
    fig.text(0.01, 0.005, f"RAW/THREAT: exp003 seeds 1-5 x3 (n={len(groups['RAW view'])}, {len(groups['THREAT view'])}); "
             f"SAFE, FINAL (= SAFE view + sweep wording in the question): exp006 development seeds (n={len(groups['SAFE view'])}, {len(groups['FINAL'])}).", fontsize=8, color="#555")
    fig.savefig(out / "fig1_same_model_different_view.png", bbox_inches="tight")
    plt.close(fig)
    return {k: {"n": len(v), **{key: round(statistics.fmean(m[key] for m in v if m.get(key) is not None), 3)
                                for key in ("score", "direction_flip_rate_per_move", "p_fire_shot_in_flight")}}
            for k, v in ms.items()}


def fig2(out, ladder):
    fig, ax = plt.subplots(figsize=(11, 0.75 * len(ladder) + 1))
    for i, r in enumerate(ladder):
        color = {"FALSIFIED": "#c0392b", "SURVIVED": "#27ae60", "PENDING": "#999", "DEPENDS": "#d68910"}[r["status"]]
        ax.text(0.0, -i, r["belief"], fontsize=11, va="center")
        ax.text(0.62, -i, r["status"], fontsize=11, va="center", color=color, weight="bold")
        ax.text(0.76, -i, r["evidence"], fontsize=9, va="center", color="#444")
    ax.set_ylim(-len(ladder) + 0.4, 0.8)
    ax.axis("off")
    ax.set_title("We thought we knew why. So we tried to prove ourselves wrong.", loc="left", fontsize=13, weight="bold")
    fig.savefig(out / "fig2_falsification.png", bbox_inches="tight")
    plt.close(fig)


def fig3(out, bench_files):
    rows = []
    for label, f in bench_files.items():
        s = json.loads(Path(f).read_text())["summary"]
        rows.append((label, s))
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.8))
    labels = [r[0] for r in rows]
    cols = [C["safe"] if "JEV" in l and "safe" in l else C["threat"] if "JEV" in l else C["haiku"] for l in labels]
    for ax, (key, title, fmt) in zip(axs, (("accuracy", "chose a survivable action", "{:.0%}"),
                                           ("latency_ms_p50", "median decision latency (ms)", "{:.0f}"),
                                           ("cost_per_decision_usd", "cost per decision (USD)", "${:.6f}"))):
        v = [r[1][key] for r in rows]
        ax.barh(labels, v, color=cols)
        for y, x in enumerate(v):
            ax.text(x, y, " " + fmt.format(x), va="center", fontsize=9)
        ax.set_title(title, loc="left", fontsize=10)
        ax.invert_yaxis()
        if key == "accuracy":
            ax.axvline(rows[0][1]["random_accuracy"], color="#999", ls="--", lw=1)
            ax.text(rows[0][1]["random_accuracy"], len(v) - 0.4, " random", color="#777", fontsize=8)
            ax.set_xlim(0, 1.15)
        else:
            ax.set_yticklabels([])
            ax.set_xticks([])
            ax.set_xlim(0, max(v) * 1.45)
    n = rows[0][1]["n"]
    fig.suptitle(f"Eval: {n} unseen critical moments (the wrong action loses a life), exact labels from the emulator", x=0.01, ha="left",
                 fontsize=12, weight="bold")
    fig.savefig(out / "fig3_decision_bench.png", bbox_inches="tight")
    plt.close(fig)
    return {l: {k: s[k] for k in ("n", "accuracy", "random_accuracy", "confidence_auc_right_vs_wrong", "latency_ms_p50",
                                  "latency_ms_p95", "cost_per_decision_usd", "served_model")} for l, s in rows}


def fig4(out, exp7):
    eps = load(exp7)
    by = {}
    for e in eps:
        by.setdefault(e["summary"]["arm"], []).append(e["summary"])
    lab = {"jev_safe_rt": "JEV", "haiku_safe_rt": "Haiku 4.5", "control_sweep_rt": "sweep (no model)",
           "jev_final_rt": "JEV", "haiku_final_rt": "Haiku 4.5"}
    keys = [k for k in ("jev_safe_rt", "jev_final_rt", "haiku_safe_rt", "haiku_final_rt", "control_sweep_rt") if k in by]
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.4))
    for i, k in enumerate(keys):
        sc = [s["score"] for s in by[k]]
        axs[0].scatter([statistics.fmean(sc)] * 0 + sc, [i] * len(sc), color=[C["safe"], C["haiku"], C["sweep"]][i], alpha=0.6)
        axs[0].plot([statistics.fmean(sc)] * 2, [i - 0.3, i + 0.3], color=C["ink"], lw=2)
        axs[0].text(statistics.fmean(sc), i + 0.35, f"mean {statistics.fmean(sc):.0f} (n={len(sc)})", fontsize=9, ha="center")
    axs[0].set_yticks(range(len(keys)), [lab[k] for k in keys])
    axs[0].set_title("score when the game doesn't wait", loc="left", fontsize=10)
    axs[0].invert_yaxis()
    dec = [statistics.fmean(s.get("decisions", s["steps"]) for s in by[k]) for k in keys if k != "control_sweep_rt"]
    lat = [statistics.median(s["latency_ms_p50"] for s in by[k]) for k in keys if k != "control_sweep_rt"]
    names = [lab[k] for k in keys if k != "control_sweep_rt"]
    axs[1].barh(names, dec, color=[C["safe"], C["haiku"]][:len(names)])
    for y, (d, l) in enumerate(zip(dec, lat)):
        axs[1].text(d, y, f" {d:.0f} decisions/game at {l:.0f} ms", va="center", fontsize=9)
    axs[1].set_title("decisions it got to make", loc="left", fontsize=10)
    axs[1].invert_yaxis()
    fig.suptitle("Real-time clock: the previous action keeps playing while the model thinks", x=0.01, ha="left",
                 fontsize=12, weight="bold")
    fig.savefig(out / "fig4_realtime.png", bbox_inches="tight")
    plt.close(fig)
    return {lab[k]: {"n": len(by[k]), "score_mean": round(statistics.fmean(s["score"] for s in by[k]), 1),
                     "decisions_mean": round(statistics.fmean(s.get("decisions", s["steps"]) for s in by[k]), 1)} for k in keys}


def fig5(out, tjson):
    d = json.loads(Path(tjson).read_text())
    arms = [(k, v) for k, v in d["arms"].items() if v.get("vs_ref")]
    arms.sort(key=lambda kv: -kv[1]["vs_ref"]["score_ex_bonus"]["mean"])
    fig, ax = plt.subplots(figsize=(9, 0.45 * len(arms) + 1.2))
    for i, (k, v) in enumerate(arms):
        p = v["vs_ref"]["score_ex_bonus"]
        ax.plot(p["ci95_bootstrap"], [i, i], color="#888", lw=2)
        ax.plot([p["mean"]], [i], "o", color=C["safe"] if p["ci95_bootstrap"][0] > 0 else (C["raw"] if p["ci95_bootstrap"][1] > 0 else "#555"))
    ax.axvline(0, color="#999", lw=1)
    ax.set_yticks(range(len(arms)), [f"{k} (n={v['vs_ref']['score_ex_bonus']['n']})" for k, v in arms])
    ax.invert_yaxis()
    ax.set_xlabel("paired score difference vs reference JEV, bonus ship excluded (95% bootstrap CI)")
    ax.set_title(f"Development tournament ({d['tag']})", loc="left", fontsize=12, weight="bold")
    fig.savefig(out / "fig5_tournament.png", bbox_inches="tight")
    plt.close(fig)


def fig6(out, exp8):
    by = {}
    for e in load(exp8):
        by.setdefault(e["summary"]["arm"], []).append(e["summary"]["score"])
    lab = {"jev_final": "JEV (final)", "haiku_final": "Haiku 4.5, same view + question", "control_sweep": "sweep bot (no model)",
           "random__raw": "random"}
    col = {"jev_final": C["final"], "haiku_final": C["haiku"], "control_sweep": C["sweep"], "random__raw": C["raw"]}
    keys = [k for k in lab if k in by]
    fig, ax = plt.subplots(figsize=(10, 0.8 * len(keys) + 1.2))
    rng = random.Random(0)
    for i, k in enumerate(keys):
        sc = by[k]
        ax.scatter(sc, [i + rng.uniform(-0.18, 0.18) for _ in sc], s=12, alpha=0.5, color=col[k])
        m = statistics.fmean(sc)
        ax.plot([m, m], [i - 0.3, i + 0.3], color=C["ink"], lw=2.5)
        ax.text(m, i - 0.38, f"mean {m:.0f}  (n={len(sc)})", ha="center", fontsize=9)
    ax.set_yticks(range(len(keys)), [lab[k] for k in keys])
    ax.invert_yaxis()
    ax.set_xlabel("score per game")
    ax.set_title("Frozen holdout: 100 seeds never seen during development, run once", loc="left", fontsize=12, weight="bold")
    fig.savefig(out / "fig6_holdout.png", bbox_inches="tight")
    plt.close(fig)
    return {k: {"n": len(v), "mean": round(statistics.fmean(v), 1)} for k, v in by.items()}


def fig7(out, squad_dir):
    """Squad: the lab manager. Right winner, games spent, and decision speed, per manager, with/without memory."""
    rows = []
    for label, f in (("halving rule (no model)", "round2_halving_memoff_v1_b36"),
                     ("equal games (no model)", "round2_uniform_memoff_v1_b36"),
                     ("Haiku 4.5", "round2_haiku_memoff_v3_b36"), ("Haiku 4.5 + Mitosis memory", "round2_haiku_memon_v3_b36"),
                     ("JEV", "round2_jev_memoff_v3_b36"), ("JEV + Mitosis memory", "round2_jev_memon_v3_b36")):
        path = Path(squad_dir) / f"{f}.json"
        if path.exists():
            rows.append((label, json.loads(path.read_text())["summary"]))
    if not rows:
        return None
    col = lambda l: C["final"] if l.startswith("JEV") else C["haiku"] if l.startswith("Haiku") else C["sweep"]
    fig, axs = plt.subplots(1, 3, figsize=(13, 3.9))
    for ax, (key, title, fmt) in zip(axs, (("accuracy", "found the true best configuration", "{:.0%}"),
                                           ("games_used_mean", "games spent per search", "{:.1f}"),
                                           ("latency_ms_p50", "median time per manager decision (ms)", "{:.0f}"))):
        v = [r[1].get(key) or 0 for r in rows]
        bars = ax.barh([r[0] for r in rows], v, color=[col(r[0]) for r in rows])
        for bar, r in zip(bars, rows):
            if "memory" in r[0]:
                bar.set_hatch("//")
                bar.set_edgecolor("white")
        for y, x in enumerate(v):
            ax.text(x, y, " " + (fmt.format(x) if x else "no model"), va="center", fontsize=9)
        ax.set_title(title, loc="left", fontsize=10)
        ax.invert_yaxis()
        ax.set_xlim(0, (1.2 if key == "accuracy" else max(v) * 1.4))
        if key != "accuracy":
            ax.set_yticklabels([])
        ax.set_xticks([])
    fig.suptitle("Squad: JEV runs the lab. It picks which configuration gets the next games and when to stop.",
                 x=0.01, ha="left", fontsize=12, weight="bold")
    fig.text(0.01, -0.04, "Round 2 of the tournament replayed from 140 real recorded games; 7 configurations, budget 36 games, "
             "paired trials. Memory = round-1 findings stored in and retrieved from Mitosis Cortex.", fontsize=8, color="#555")
    fig.savefig(out / "fig7_lab_manager.png", bbox_inches="tight")
    plt.close(fig)
    return {l: {k: s.get(k) for k in ("trials", "accuracy", "regret_mean", "games_used_mean", "latency_ms_p50",
                                      "orchestration_cost_usd_per_trial")} for l, s in rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "demo" / "assets"))
    ap.add_argument("--exp3", default=str(REPO / "ufa/traces/exp003_hint_decomposition"))
    ap.add_argument("--exp6", default=str(REPO / "ufa/traces/exp006_tournament"))
    ap.add_argument("--exp7", default=str(REPO / "ufa/traces/exp009_holdout_realtime"))
    ap.add_argument("--holdout", default=str(REPO / "ufa/traces/exp008_holdout"))
    ap.add_argument("--tournament", default=str(REPO / "ufa/traces/exp006_tournament/analysis/tournament_stageA.json"))
    ap.add_argument("--ladder", default=str(REPO / "demo/ladder.json"))
    ap.add_argument("--squad", default=str(REPO / "ufa/squad/results"))
    ap.add_argument("--bench", nargs="*", default=[f"{l}={REPO}/ufa/bench/results/{f}.json" for l, f in
                                                   (("JEV, THREAT view", "test_jev_threat_s500"), ("JEV, SAFE view", "test_jev_threat_safe_s500"),
                                                    ("Haiku, THREAT view", "test_haiku_threat"), ("Haiku, SAFE view", "test_haiku_threat_safe"))])
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    data = {"fig1": fig1(out, a.exp3, a.exp6)}
    if Path(a.ladder).exists():
        fig2(out, json.loads(Path(a.ladder).read_text()))
    data["fig3"] = fig3(out, dict(x.split("=", 1) for x in a.bench))
    if Path(a.exp7).exists():
        data["fig4"] = fig4(out, a.exp7)
    fig5(out, a.tournament)
    if Path(a.holdout).exists():
        data["fig6"] = fig6(out, a.holdout)
    data["fig7"] = fig7(out, a.squad)
    (out / "data.json").write_text(json.dumps(data, indent=1))
    print(json.dumps(data, indent=1))


if __name__ == "__main__":
    main()
