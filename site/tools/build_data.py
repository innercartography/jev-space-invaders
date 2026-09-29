"""Build site/data/results.js: the ONE place the public site gets its numbers from.

Every value is read from a committed result file in the public repo (paths below are
public-repo paths). Nothing here is typed in by hand except labels and rounding.

    python site/tools/build_data.py            (in the public repo: reads the files next to site/)
"""
import argparse
import glob
import json
import statistics as st
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    # in the public repo the result files sit next to site/; in the private lab, in the sibling export folder
    default = SITE.parent if (SITE.parent / "results.json").exists() else SITE.parents[1] / "ufa-jev-export"
    ap.add_argument("--src", default=str(default))
    a = ap.parse_args()
    S = Path(a.src)

    def J(p):
        return json.loads((S / p).read_text())

    src = {}

    # ---------- Pilot ----------
    P = "analysis/tournament_holdout.json"
    ho = J(P)["arms"]
    jev, sweep, rnd = ho["jev_final"], ho["control_sweep"], ho["random__raw"]
    PH = "analysis/tournament_holdout_vs_haiku.json"
    hh = J(PH)["arms"]
    PRT = "analysis/tournament_holdout_rt_vs_haiku.json"
    rt = J(PRT)["arms"]
    res = J("results.json")
    jev_runs = [r for r in res["runs"] if r.get("arm") == "jev_final"]
    pilot = {
        "model": jev_runs[0]["served_model"],
        "holdout_games": jev["n_games"],
        "mean": jev["performance"]["score_mean"],
        "median": jev["performance"]["score_median"],
        "mean_ex_bonus": jev["performance"]["score_ex_bonus_mean"],
        "sweep_mean": sweep["performance"]["score_mean"],
        "random_mean": rnd["performance"]["score_mean"],
        "latency_ms_p50": jev["system"]["latency_p50_ms_median_of_games"],
        "cost_per_game": jev["system"]["cost_per_game_usd"],
        "haiku_games": hh["haiku_final"]["n_games"],
        "haiku_mean": hh["haiku_final"]["performance"]["score_mean"],
        "haiku_latency_ms_p50": hh["haiku_final"]["system"]["latency_p50_ms_median_of_games"],
        "haiku_cost_per_game": hh["haiku_final"]["system"]["cost_per_game_usd"],
        "jev_mean_same5": hh["jev_final"]["performance"]["score_mean"],
        "rt_games": rt["jev_final_rt"]["n_games"],
        "rt_jev_mean": rt["jev_final_rt"]["performance"]["score_mean"],
        "rt_haiku_mean": rt["haiku_final_rt"]["performance"]["score_mean"],
        "rt_jev_decisions": rt["jev_final_rt"]["system"]["model_calls_per_game"],
        "rt_haiku_decisions": rt["haiku_final_rt"]["system"]["model_calls_per_game"],
    }
    # win counts are in the markdown tables (W/T/L column); read them from there
    def wtl(md, arm):
        for line in (S / md).read_text().splitlines():
            if line.startswith(f"| {arm} |"):
                return line.split("|")[8].strip()
    pilot["vs_haiku_wtl"] = wtl("analysis/tournament_holdout_vs_haiku.md", "jev_final")        # 5/0/0
    pilot["rt_vs_haiku_wtl"] = wtl("analysis/tournament_holdout_rt_vs_haiku.md", "jev_final_rt")  # 19/0/1
    pilot["vs_sweep_wtl"] = wtl("analysis/tournament_holdout.md", "jev_final")                  # 92/0/8
    pilot["speed_ratio"] = pilot["haiku_latency_ms_p50"] / pilot["latency_ms_p50"]
    pilot["cost_ratio"] = pilot["haiku_cost_per_game"] / pilot["cost_per_game"]
    src["pilot"] = [P, PH, PRT, "results.json"]

    # ---------- representation (same model, different view) ----------
    D = J("demo/assets/data.json")
    rep = {k: D["fig1"][k] for k in ("RAW view", "THREAT view", "SAFE view", "FINAL")}
    src["representation"] = ["demo/assets/data.json (fig1)"]
    ladder = J("demo/ladder.json")
    src["ladder"] = ["demo/ladder.json"]
    evalb = D["fig3"]
    src["eval"] = ["demo/assets/data.json (fig3)", "bench/results/*.json"]

    # ---------- swarm main run (s1) ----------
    A1 = "ufa/squad/swarm/runs/s1/analysis.json"
    s1 = J(A1)
    C = s1["conditions"]
    names = {"A": "Workers alone, no memory", "B": "Workers + Mitosis memory", "C": "Fixed coordinator + memory",
             "D": "JEV governance + memory", "E": "JEV governance, no memory", "F": "Simple threshold rule + memory"}
    main = {k: {"name": names[k], "ph1": C[k]["ph1_regret_auc"], "ph2": C[k]["ph2_regret_auc"],
                "ph2_first5": C[k]["ph2_regret_first5"]} for k in C}
    pr = s1["paired"]
    meta = J("ufa/squad/swarm/runs/s1/meta.json")
    mit_calls = 0
    for f in glob.glob(str(S / "ufa/squad/swarm/runs/s1/[A-F]_t*.json")):
        m = json.loads(Path(f).read_text()).get("mitosis") or {}
        mit_calls += m.get("write_calls", 0) + m.get("read_calls", 0)
    swarm = {
        "trials": meta["trials"], "W": meta["W"], "R": meta["R"], "L": meta["L"], "conditions": main,
        "benefit_ph1": pr["B-A ph1_regret_auc"], "drag_ph2": pr["B-A ph2_regret_auc"],
        "jev_vs_mem_ph2": pr["D-B ph2_regret_auc"], "jev_vs_rule_total": pr["D-F total_regret_auc"],
        "jev_vs_rule_ph2": pr["D-F ph2_regret_auc"], "jev_drag_ph2": pr["D-E ph2_regret_auc"],
        "rediscovery_avoided_ph1": s1["memory"]["decentralized"]["rediscovery_avoided_ph1"],
        "curves": s1["mean_regret_curves"], "mitosis_calls": mit_calls,
        "first_stale_challenge_round_D": C["D"]["first_stale_challenge_round"],
        "landscape_games": J("ufa/squad/swarm/landscape/tenki_run.json")["games_returned"],
    }
    src["swarm"] = [A1, "ufa/squad/swarm/runs/s1/meta.json", "ufa/squad/swarm/runs/s1/*_t*.json (mitosis calls)",
                    "ufa/squad/swarm/landscape/tenki_run.json", "ufa/squad/swarm/PREREG.md"]

    # ---------- the two game variations: true means per setup ----------
    land = {}
    for reg in "AB":
        L = J(f"ufa/squad/swarm/landscape/{reg}.json")
        by = {}
        for g in L["games"]:
            by.setdefault(g["config"], []).append(g["score_ex_bonus"])  # truth = ex-bonus mean (as in swarm.py)
        truth = {c: round(st.fmean(v), 1) for c, v in by.items()}
        rank = sorted(truth, key=lambda c: -truth[c])
        land[reg] = {"regime": L["regime"], "truth": truth, "rank": rank, "games_per_config": len(next(iter(by.values())))}
    src["landscape"] = ["ufa/squad/swarm/landscape/A.json", "ufa/squad/swarm/landscape/B.json"]

    # ---------- a real JEV challenge (Tenki validation, trial 502, round 4 after the change) ----------
    T = "ufa/squad/swarm/runs/v4/D_t502.json"
    t = J(T)["governor"]
    dec = next(x for x in t["decisions"] if x["q"] == "memory" and x["choice"] == "still-on-ready")
    state = t["states"][dec["state_sha"]]
    row = next(c for c in state["configurations"] if c["config"] == "still-on-ready")
    challenge = {"trial": 502, "round": dec["round"], "probabilities": dec["probabilities"], "choice": dec["choice"],
                 "latency_ms": dec["latency_ms"], "inherited": row["inherited"], "games_now": row["games_now"],
                 "mean_now": row["mean_now"], "ci95_now": row["ci95_now"], "instructions": dec["question"]["instructions"],
                 "findings": [{"config": c["config"], **c["inherited"]} for c in state["configurations"] if "inherited" in c]}
    src["challenge"] = [T + " (governor.decisions / governor.states)"]

    # ---------- Tenki-native validation (v4) ----------
    V = "ufa/squad/swarm/runs/v4/validation_analysis.json"
    v = J(V)
    vc = v["conditions"]
    att = J("ufa/squad/swarm/validation/attempts.json")
    ver = J("verification/tenki_verify_holdout.json")
    val = {
        "trials": v["trials"]["D"],
        "D": {"ph1": vc["D"]["ph1_regret_auc"], "ph2": vc["D"]["ph2_regret_auc"]},
        "E": {"ph1": vc["E"]["ph1_regret_auc"], "ph2": vc["E"]["ph2_regret_auc"]},
        "benefit_ph1": v["paired"]["D-E ph1_regret_auc"], "drag_ph2": v["paired"]["D-E ph2_regret_auc"],
        "first_stale_challenge_round": vc["D"]["first_stale_challenge_round"],
        "tenki": v["tenki"], "mitosis": v["mitosis"], "jev_totals": v["jev_totals"], "replay": v["replay"],
        "curves": v["mean_regret_curves"], "memory_question": v["jev"]["memory_question"],
        "stop_question": v["jev"]["stop_question_phase1"],
        "attempts": att["attempts"], "attempts_totals": att["totals"],
        "official_replay": {k: ver[k] for k in ("games", "verified", "matched", "wall_s", "compute_cost_usd_estimate")},
        "freeze_commit": J("ufa/squad/swarm/validation/FREEZE.json")["commit"][:7],
    }
    src["validation"] = [V, "ufa/squad/swarm/validation/attempts.json", "ufa/squad/swarm/validation/FREEZE.json",
                         "verification/tenki_verify_holdout.json"]

    # ---------- JEV audits ----------
    au = {"structure": J("ufa/squad/swarm/validation/audit_structure.json")["summary"],
          "order": J("ufa/squad/swarm/validation/audit_order.json")["summary"]}
    src["audit"] = ["ufa/squad/swarm/validation/audit_structure.json", "ufa/squad/swarm/validation/audit_order.json"]

    footage = json.loads((SITE / "assets/footage_manifest.json").read_text())
    src["footage"] = ["site/assets/footage_manifest.json (replayed from replays/holdout.json and the landscape files)"]

    R = {"pilot": pilot, "representation": rep, "ladder": ladder, "eval": evalb, "swarm": swarm, "landscape": land,
         "challenge": challenge, "validation": val, "audit": au, "footage": footage}
    out = SITE / "data" / "results.js"
    out.parent.mkdir(exist_ok=True)
    out.write_text(
        "// GENERATED by site/tools/build_data.py from committed result files. Do not edit by hand.\n"
        "// SOURCES lists the public-repo file behind every group of numbers.\n"
        f"export const R = {json.dumps(R, indent=1)};\n\nexport const SOURCES = {json.dumps(src, indent=1)};\n")
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    print(json.dumps({k: pilot[k] for k in pilot}, indent=0))


if __name__ == "__main__":
    main()
