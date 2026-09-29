"""Analyse the Tenki-native validation run: replication of the frozen findings, Tenki layout, Mitosis staleness,
JEV raw-distribution behaviour against objective labels, and an exact local replay of a sample of Tenki games.

    python -m ufa.squad.swarm_validation --run v1 [--replay 120]

Objective labels only (derived from the frozen landscape, never from the swarm's own evidence):
    memory question  an inherited finding is STALE if |inherited mean - true mean in the new variation| > 50
                     (the main run's definition). Event forecast: q = 1 - p(NONE) = P(some contested finding is
                     contradicted); label = at least one contested finding is stale.
    stop question    p(YES) against "the current leader is near-best" (true regret <= NEAR = 10), i.e. whether a
                     stop now would have committed to a near-best configuration. The question asks about evidence,
                     not truth, so this is a descriptive check, not a calibration target.
"""
import argparse
import json
import random
import statistics
from pathlib import Path

from ufa.squad.swarm import HERE, NEAR, R, load_landscape
from ufa.squad.swarm_analysis import boot, load, metrics


def ece(ps, ys, bins=10):
    B = [[] for _ in range(bins)]
    for p, y in zip(ps, ys):
        B[min(int(p * bins), bins - 1)].append((p, y))
    rows = [{"bin": f"{i / bins:.1f}-{(i + 1) / bins:.1f}", "n": len(b), "mean_p": round(statistics.fmean(p for p, _ in b), 3),
             "freq": round(statistics.fmean(y for _, y in b), 3)} for i, b in enumerate(B) if b]
    n = len(ps)
    return round(sum(r["n"] / n * abs(r["mean_p"] - r["freq"]) for r in rows), 4), rows


def brier(ps, ys):
    return round(statistics.fmean((p - y) ** 2 for p, y in zip(ps, ys)), 4) if ps else None


def jev_labels(data, land):
    truth = {1: land[0]["truth"], 2: land[1]["truth"]}
    mem, stop, conf_check = [], [], []
    for c in ("D", "E"):
        for t, d in (data.get(c) or {}).items():
            g = d["governor"]
            for rec in g["decisions"]:
                P = rec.get("probabilities") or {}
                if P and rec.get("confidence") is not None and rec["choice"]:
                    K = len(rec["options"])
                    conf_check.append(abs(rec["confidence"] - (max(P.values()) - 1 / K) / (1 - 1 / K)))
                st = g["states"][rec["state_sha"]]
                if rec["q"] == "memory" and P:
                    rows = {r["config"]: r for r in st["configurations"]}
                    stale = {o: abs(rows[o]["inherited"]["mean"] - truth[2][o]) > 50 for o in rec["options"] if o != "NONE"}
                    anyst = any(stale.values())
                    ch = rec["choice"]
                    mem.append({"cond": c, "trial": t, "round": rec["round"], "q": 1 - P.get("NONE", 0), "y": int(anyst),
                                "choice": ch, "p_choice": P.get(ch), "n_options": len(rec["options"]),
                                "stale_options": sum(stale.values()),
                                "correct": (stale.get(ch, False) if ch != "NONE" else not anyst) if ch else None,
                                "false_challenge": ch not in (None, "NONE") and not stale[ch],
                                "missed_stale": ch == "NONE" and anyst,
                                "stale_mass_share": (sum(P.get(o, 0) for o, s in stale.items() if s) / (1 - P.get("NONE", 0))
                                                     if P.get("NONE", 0) < 1 else None)})
                if rec["q"] == "stop" and P and st["swarm"]["leader"]:
                    ph = rec["phase"]
                    best = max(truth[ph].values())
                    stop.append({"cond": c, "phase": ph, "round": rec["round"], "p_yes": P.get("YES", 0),
                                 "y": int(best - truth[ph][st["swarm"]["leader"]] <= NEAR), "choice": rec["choice"]})
    out = {"confidence_field_vs_formula_max_abs_diff": round(max(conf_check), 4) if conf_check else None,
           "confidence_field_note": "confidence = (p_max - 1/K)/(1 - 1/K): a spread summary of the distribution, "
                                    "not a probability of being right; all analysis below uses the probabilities"}
    if mem:
        qs, ys = [m["q"] for m in mem], [m["y"] for m in mem]
        e, rows = ece(qs, ys)
        early = [m for m in mem if m["round"] < 5]
        late = [m for m in mem if m["round"] >= 10]

        def block(ms):
            return {"n": len(ms), "accuracy_argmax": round(statistics.fmean(m["correct"] for m in ms if m["correct"] is not None), 3),
                    "base_rate_any_stale": round(statistics.fmean(m["y"] for m in ms), 3),
                    "mean_q_contradicted": round(statistics.fmean(m["q"] for m in ms), 3),
                    "brier_q": brier([m["q"] for m in ms], [m["y"] for m in ms]),
                    "false_challenges": sum(m["false_challenge"] for m in ms), "missed_stale": sum(m["missed_stale"] for m in ms),
                    "mean_stale_mass_share_when_stale_present": round(statistics.fmean(
                        m["stale_mass_share"] for m in ms if m["y"] and m["stale_mass_share"] is not None), 3)
                    if any(m["y"] and m["stale_mass_share"] is not None for m in ms) else None,
                    "mean_p_choice": round(statistics.fmean(m["p_choice"] for m in ms if m["p_choice"] is not None), 3)}
        out["memory_question"] = {"all_phase2": block(mem) | {"ece_10bin_q": e, "reliability_bins_q": rows},
                                  "rounds_0_4": block(early) if early else None, "rounds_10_14": block(late) if late else None,
                                  "note": "asked only after the game changes (no inherited findings exist before), so the "
                                          "pre-vs-post comparison is early vs late after the change"}
    for ph in (1, 2):
        S = [s for s in stop if s["phase"] == ph]
        if S:
            e, rows = ece([s["p_yes"] for s in S], [s["y"] for s in S])
            out[f"stop_question_phase{ph}"] = {"n": len(S), "said_yes": sum(s["choice"] == "YES" for s in S),
                                               "mean_p_yes": round(statistics.fmean(s["p_yes"] for s in S), 4),
                                               "max_p_yes": round(max(s["p_yes"] for s in S), 3),
                                               "leader_near_best_rate": round(statistics.fmean(s["y"] for s in S), 3),
                                               "mean_p_yes_when_leader_near_best": round(statistics.fmean([s["p_yes"] for s in S if s["y"]] or [0]), 4),
                                               "mean_p_yes_when_not": round(statistics.fmean([s["p_yes"] for s in S if not s["y"]] or [0]), 4),
                                               "brier": brier([s["p_yes"] for s in S], [s["y"] for s in S]), "ece_10bin": e,
                                               "bins": rows}
    mode = {}
    for c in ("D", "E"):
        for ph in (1, 2):
            ps = [rec["probabilities"].get("COORDINATE", 0) for d in (data.get(c) or {}).values()
                  for rec in d["governor"]["decisions"] if rec["q"] == "mode" and rec["phase"] == ph and rec.get("probabilities")]
            if ps:
                mode[f"{c}_phase{ph}"] = {"n": len(ps), "mean_p_coordinate": round(statistics.fmean(ps), 3),
                                          "share_p_between_0.3_0.7": round(statistics.fmean(0.3 <= p <= 0.7 for p in ps), 3)}
    out["mode_question_descriptive"] = mode
    return out


def mitosis(data):
    reads, behind, vers, stal, unknown, cf_j, cf_a = 0, 0, [], [], 0, {}, []
    for c in ("B", "D"):
        for d in (data.get(c) or {}).values():
            m = d["mitosis"]
            for rl in m["read_log"]:
                if not rl["findings_acked"]:
                    continue
                reads += 1
                behind += bool(rl["behind"])
                for b in rl["behind"]:
                    vers.append(b["versions_behind"])
                    unknown += b["unknown_version"]
                    if b["staleness_s"] is not None:
                        stal.append(b["staleness_s"])
            for cf in m["stale_read_counterfactuals"]:
                cf_a.append((c, cf["alloc_differs"]))
                for q, v in (cf.get("judgments_differ") or {}).items():
                    cf_j.setdefault(q, []).append(v)
    return {"reads_with_acked_findings": reads, "reads_behind": behind, "stale_read_rate": round(behind / reads, 3) if reads else None,
            "stale_findings": len(vers), "versions_behind_median": statistics.median(vers) if vers else None,
            "versions_behind_max": max(vers) if vers else None,
            "staleness_s_median": round(statistics.median(stal), 2) if stal else None,
            "staleness_s_p95": round(sorted(stal)[int(0.95 * (len(stal) - 1))], 2) if stal else None,
            "staleness_s_max": round(max(stal), 2) if stal else None, "unknown_versions": unknown,
            "stale_rounds_allocation_would_differ": {c: [sum(v for cc, v in cf_a if cc == c), sum(1 for cc, _ in cf_a if cc == c)]
                                                     for c in ("B", "D")},
            "stale_rounds_jev_judgment_would_differ": {q: [sum(v), len(v)] for q, v in cf_j.items()},
            "note": "staleness_s = read start minus the ack time of the first acknowledged write the read did not reflect; "
                    "counterfactuals re-ask JEV / re-draw the allocation (same rng state) on the current surface and are "
                    "never acted on; JEV answers also vary request to request, so a differing judgment is an upper bound"}


def replay_sample(run, n, seed=0):
    from ufa.verify_replay import replay

    games = [json.loads(line) for line in open(HERE / "runs" / run / "games.jsonl")]
    sample = random.Random(seed).sample(games, min(n, len(games)))
    res = []
    for g in sample:
        r = replay({"env": g["regime"], "action_names": g["action_names"], "seed": g["seed"], "actions": g["actions"],
                    "expected": {k: g[k] for k in ("score", "steps", "frames", "lives_lost")}})
        res.append({"sandbox_id": g["sandbox_id"], "config": g["config"], "seed": g["seed"], "regime": g["regime"], **r})
    return {"games_in_run": len(games), "sampled": len(res), "matched": sum(r["ok"] for r in res),
            "sandboxes_covered": len({r["sandbox_id"] for r in res}), "mismatched": [r for r in res if not r["ok"]]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="v1")
    ap.add_argument("--replay", type=int, default=120)
    a = ap.parse_args()
    land = load_landscape()
    data = load(a.run)
    s1 = json.loads((HERE / "runs" / "s1" / "analysis.json").read_text())
    M = {c: {t: metrics(d) for t, d in ts.items()} for c, ts in data.items()}
    keys = ("ph1_regret_auc", "ph2_regret_auc", "total_regret_auc", "ph2_regret_first5", "ph2_found_best", "ph1_rediscovery_games",
            "ph2_stale_led_games", "ph1_coordinate_share", "ph2_coordinate_share", "challenges", "challenges_of_stale",
            "challenges_of_valid", "first_stale_challenge_round", "jev_calls", "jev_cost_usd")
    summ = {}
    for c in sorted(M):
        summ[c] = {"trials": len(M[c])}
        for k in keys:
            xs = [v[k] for v in M[c].values() if v.get(k) is not None]
            if xs:
                summ[c][k] = boot(xs)
                if k in s1["conditions"].get(c, {}):
                    summ[c][k + "_s1"] = s1["conditions"][c][k][0]

    def paired(x, y, k):
        ts = sorted(set(M[x]) & set(M[y]))
        diffs = [M[x][t][k] - M[y][t][k] for t in ts]
        return {"diff": boot(diffs), "x_better": sum(d < 0 for d in diffs), "y_better": sum(d > 0 for d in diffs), "n": len(ts)}
    comps = {}
    for x, y in (("D", "E"), ("B", "E"), ("D", "B")):
        if x in M and y in M:
            for k in ("ph1_regret_auc", "ph2_regret_auc", "total_regret_auc", "ph2_regret_first5"):
                comps[f"{x}-{y} {k}"] = paired(x, y, k)
    meta = json.loads((HERE / "runs" / a.run / "meta.json").read_text())
    launcher = json.loads((HERE / "runs" / a.run / "launcher.json").read_text())
    tk = meta["tenki"]
    ws = tk["workers"]
    play = [x for w in ws for x in w.get("play_s", [])]
    tenki = {"coordinator_sandbox": launcher["coordinator_sandbox_id"], "worker_sandboxes_created": tk["worker_sandboxes_created"],
             "sandboxes_total": tk["worker_sandboxes_created"] + 1, "generations_per_slot": tk["generations_per_slot"],
             "planned_replacements": tk["planned_replacements"], "unplanned_replacements": sum(1 for w in ws if w["why"] not in (
                 "first population", "game changed: whole population replaced", "lifetime over")),
             "games": tk["games"], "games_per_worker_sandbox": {"min": min(w["games"] for w in ws), "max": max(w["games"] for w in ws),
                                                                  "mean": round(statistics.fmean(w["games"] for w in ws), 1)},
             "worker_jobs_ok": sum(w["jobs_ok"] for w in ws), "retries": tk["retries"], "failures": len(tk["failures"]),
             "max_concurrent_sandboxes": 5, "wall_s": meta["wall_s"], "coordinator_alive_s": launcher["coordinator_alive_s"],
             "worker_play_exec_s_p50": statistics.median(play) if play else None,
             "games_per_sandbox_second": round(tk["games"] / sum(w.get("alive_s", 0) for w in ws), 3),
             "cost_usd_estimate": {"workers": tk["worker_cost_usd_estimate"], "coordinator": launcher["coordinator_cost_usd_estimate"],
                                   "total": round(tk["worker_cost_usd_estimate"] + launcher["coordinator_cost_usd_estimate"], 4)},
             "birth_audit_all_empty": all(w["birth_audit"]["local_knowledge"] == {} for w in ws),
             "worker_env_secret_names": sorted({n for w in ws for n in w["birth_audit"]["env_names"]
                                                 if any(s in n for s in ("KEY", "TOKEN", "SECRET", "MITOSIS", "TYPESAFE"))}),
             "egress_allowlist_applied": sum(1 for w in ws if w.get("egress_allowlist"))}
    out = {"run": a.run, "trials": {c: len(v) for c, v in M.items()}, "conditions": summ, "paired": comps, "tenki": tenki,
           "mitosis": mitosis(data), "jev": jev_labels(data, land),
           "jev_totals": {"calls": sum(len(d["governor"]["decisions"]) for c in ("D", "E") for d in (data.get(c) or {}).values()),
                          "counterfactual_calls": sum(len(d["governor"]["counterfactual_decisions"]) for c in ("D", "E") for d in (data.get(c) or {}).values()),
                          "cost_usd": round(sum(d["governor"]["cost_usd"] or 0 for c in ("D", "E") for d in (data.get(c) or {}).values()), 4),
                          "latency_ms_p50": statistics.median([x["latency_ms"] for c in ("D", "E") for d in (data.get(c) or {}).values() for x in d["governor"]["decisions"]]),
                          "errors": sum(1 for c in ("D", "E") for d in (data.get(c) or {}).values() for x in d["governor"]["decisions"] if x["error"])},
           "mean_regret_curves": {c: [round(statistics.fmean(d["phases"][i // R]["regret_curve"][i % R] for d in data[c].values()), 1)
                                      for i in range(2 * R)] for c in data}}
    if a.replay:
        out["replay"] = replay_sample(a.run, a.replay)
    (HERE / "runs" / a.run / "validation_analysis.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("trials", "paired", "tenki", "mitosis")}, indent=1))
    for c, s in summ.items():
        print(c, {k: v for k, v in s.items() if k in ("ph1_regret_auc", "ph1_regret_auc_s1", "ph2_regret_auc", "ph2_regret_auc_s1", "ph2_regret_first5")})
    print(json.dumps(out["jev"], indent=1)[:3000])
    print(json.dumps(out.get("replay", {}), indent=1)[:600])


if __name__ == "__main__":
    main()
