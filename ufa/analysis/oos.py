"""exp005 analysis: out-of-sample JEV THREAT vs the deterministic sweep control.

    python -m ufa.analysis.oos --jev ufa/traces/exp005_out_of_sample \
        --controls ufa/traces/exp004_scripted_controls --exp003 ufa/traces/exp003_hint_decomposition

Parts:
  1. paired seed-by-seed JEV vs sweep (with and without bonus-ship points)
  2. action persistence vs score across arms and within JEV episodes (association only)
  3. branch test: replay a JEV game's recorded actions up to step t in the emulator (exact, the env
     is deterministic), then let the sweep control play the next W steps from that identical state.
     Compares JEV's recorded next W steps with sweep's (points exclude the bonus ship). $0: no model calls.
  4. bonus-ship hits: where, and JEV's fire timing around them
Writes <jev>/analysis/oos.json and oos.md.
"""
import argparse
import json
import math
import random
import statistics
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

from ufa.analysis.behavior import d as move_dir
from ufa.analysis.behavior import episode_metrics
from ufa.arena import env as envmod
from ufa.arena.compare import load
from ufa.arena.extract import Extractor, threat_analysis
from ufa.arena.policies import ScriptedPolicy
from ufa.arena.representations import threat as threat_rep

LO, HI = ScriptedPolicy.X_LIMITS
BONUS = 50  # any single reward >= 50 is the bonus ship; aliens are worth 5-30
W_SHORT, W_LONG = 60, 150
BRANCH_EVERY, BRANCH_FROM = 30, 20


def region(x):
    if x is None:
        return "unknown"
    return "left_wall" if x <= LO + 3 else ("right_wall" if x >= HI - 3 else "middle")


def ep_metrics(e):
    s = e["summary"]
    m, rows = episode_metrics(e["_path"])
    rew = [r["reward"] for r in rows]
    xs = m.pop("_xs")
    # fire timing: steps from "shot ready" (no own shot in flight) to the first FIRE press
    lat, wait = [], None
    for r in rows:
        ready = not threat_analysis(r["state"])["shot_in_flight"]
        if ready:
            wait = 0 if wait is None else wait + 1
            if "FIRE" in r["action"]:
                lat.append(wait)
                wait = None
        else:
            wait = None
    m.update({
        "arm": s["arm"], "seed": s["seed"], "score": s["score"], "steps": s["steps"],
        "cost_usd": s.get("cost_usd"), "wall_clock_s": s.get("wall_clock_s"), "served_model": s.get("served_model"),
        "bonus_hits": sum(x >= BONUS for x in rew), "bonus_pts": sum(x for x in rew if x >= BONUS),
        "top_row_kills": sum(x == 30 for x in rew),
        "left_wall_share": round(sum(x <= LO + 3 for x in xs) / len(xs), 4) if xs else None,
        "right_wall_share": round(sum(x >= HI - 3 for x in xs) / len(xs), 4) if xs else None,
        "fire_latency_mean": round(statistics.fmean(lat), 2) if lat else None,
        "fire_immediately_share": round(sum(x == 0 for x in lat) / len(lat), 4) if lat else None,
        "steps_per_life_ep": round(s["steps"] / max(len(m["deaths"]), 1), 1),
        "path": e["_path"],
    })
    m["score_ex_bonus"] = m["score"] - m["bonus_pts"]
    return m


# ---------- statistics ----------
def rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2
        i = j + 1
    return r


def spearman(x, y):
    p = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if len(p) < 3:
        return None
    rx, ry = rank([a for a, _ in p]), rank([b for _, b in p])
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return {"rho": round(num / den, 3) if den else None, "n": len(p)}


def paired(dv, iters=20000):
    rng = random.Random(0)
    n = len(dv)
    obs = statistics.fmean(dv)
    sd = statistics.stdev(dv)
    flips = sum(abs(statistics.fmean(x if rng.random() < 0.5 else -x for x in dv)) >= abs(obs) - 1e-9 for _ in range(iters))
    boots = sorted(statistics.fmean(rng.choice(dv) for _ in range(n)) for _ in range(10000))
    w, l = sum(x > 0 for x in dv), sum(x < 0 for x in dv)
    k = min(w, l)
    sign_p = min(1.0, 2 * sum(math.comb(w + l, i) for i in range(k + 1)) / 2 ** (w + l)) if w + l else 1.0
    return {"n": n, "mean": round(obs, 1), "median": round(statistics.median(dv), 1), "sd": round(sd, 1),
            "ci95_bootstrap": [round(boots[250], 1), round(boots[9749], 1)],
            "effect_size_dz": round(obs / sd, 2) if sd else None,
            "jev_wins": w, "ties": n - w - l, "jev_losses": l,
            "sign_flip_p": round((flips + 1) / (iters + 1), 4), "sign_test_p": round(sign_p, 4)}


# ---------- branch test ----------
def branch_job(args):
    path, seed, env_cfg, ts = args
    rows = [json.loads(l) for l in open(Path(path) / "steps.jsonl")]
    acts = [r["action"] for r in rows]
    out = []
    for t in ts:
        env = envmod.make_env(env_cfg)
        names = envmod.action_names(env)
        ram, info = env.reset(seed=seed)
        score = rows[t]["state"]["score"]
        for i in range(t):
            if i == t - 3:
                envmod.install_tap(env)
            ram, _, term, trunc, info = env.step(names.index(acts[i]))
        ex = Extractor()
        rec_state = rows[t]["state"]
        ok = int(info.get("episode_frame_number", 0)) == rec_state["frame"] and int(info.get("lives", 0)) == rec_state["lives"]
        pol = ScriptedPolicy({"control": "sweep"}, 0)
        last = next((move_dir(a) for a in reversed(acts[:t]) if move_dir(a)), 1)
        pol.dir = "LEFT" if last < 0 else "RIGHT"
        lives0 = rec_state["lives"]
        pts = {W_SHORT: 0.0, W_LONG: 0.0}
        died = {W_SHORT: False, W_LONG: False}
        first_action = None
        prev = acts[t - 1] if t else None
        for k in range(W_LONG):
            st = ex.extract(*envmod.last_two_frames(env), ram, info, score, t + k, prev)
            a = pol.decide(threat_rep(st, []), names)["action"]
            first_action = first_action or a
            ram, r, term, trunc, info = env.step(names.index(a))
            score += r
            prev = a
            lost = int(info.get("lives", 0)) < lives0 or term
            for w in (W_SHORT, W_LONG):
                if k < w:
                    pts[w] += r if r < BONUS else 0  # bonus-ship points excluded
                    died[w] = died[w] or lost
            if term or trunc:
                break
        env.close()
        # JEV's recorded continuation from the same state
        jpts, jdied = {}, {}
        for w in (W_SHORT, W_LONG):
            seg = rows[t:t + w]
            jpts[w] = sum(r["reward"] for r in seg if r["reward"] < BONUS)
            jdied[w] = any(r["lives"] < lives0 for r in seg) or (t + w > len(rows))
        th = threat_analysis(rec_state)
        out.append({"seed": seed, "path": path, "t": t, "integrity_ok": ok, "region": region(rec_state["player"]["x"]),
                    "threatened": bool(th["lane_danger"]["stay"]), "jev_action": acts[t], "sweep_action": first_action,
                    "same_first_action": acts[t] == first_action,
                    "jev_move_matches": move_dir(acts[t]) == move_dir(first_action),
                    **{f"jev_pts_{w}": jpts[w] for w in (W_SHORT, W_LONG)},
                    **{f"sweep_pts_{w}": pts[w] for w in (W_SHORT, W_LONG)},
                    **{f"jev_died_{w}": jdied[w] for w in (W_SHORT, W_LONG)},
                    **{f"sweep_died_{w}": died[w] for w in (W_SHORT, W_LONG)}})
    return out


def branch_summary(B, w):
    if not B:
        return None
    return {"n": len(B),
            "jev_pts_mean": round(statistics.fmean(b[f"jev_pts_{w}"] for b in B), 2),
            "sweep_pts_mean": round(statistics.fmean(b[f"sweep_pts_{w}"] for b in B), 2),
            "jev_death_rate": round(statistics.fmean(b[f"jev_died_{w}"] for b in B), 3),
            "sweep_death_rate": round(statistics.fmean(b[f"sweep_died_{w}"] for b in B), 3),
            "jev_better_pts": sum(b[f"jev_pts_{w}"] > b[f"sweep_pts_{w}"] for b in B),
            "sweep_better_pts": sum(b[f"jev_pts_{w}"] < b[f"sweep_pts_{w}"] for b in B),
            "jev_survived_sweep_died": sum(b[f"sweep_died_{w}"] and not b[f"jev_died_{w}"] for b in B),
            "sweep_survived_jev_died": sum(b[f"jev_died_{w}"] and not b[f"sweep_died_{w}"] for b in B)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jev", required=True)
    ap.add_argument("--controls", required=True)
    ap.add_argument("--exp003", required=True)
    ap.add_argument("--procs", type=int, default=20)
    args = ap.parse_args()

    jev_eps = load(args.jev)
    new_seeds = {e["summary"]["seed"] for e in jev_eps}
    ctl_eps = [e for e in load(args.controls) if e["summary"]["seed"] in new_seeds | {1, 2, 3, 4, 5}]
    e3 = load(args.exp003)
    for e in e3:
        e["summary"]["arm"] = e["summary"]["arm"] + "@exp003"
    for e in jev_eps:
        e["summary"]["arm"] = e["summary"]["arm"] + "@exp005"
    with Pool(args.procs) as pool:
        ms = pool.map(ep_metrics, jev_eps + ctl_eps + e3, chunksize=4)
    by = defaultdict(list)
    for m in ms:
        by[m["arm"]].append(m)
    J = {m["seed"]: m for m in by["jev_basic__threat@exp005"]}
    S = {m["seed"]: m for m in by["control_sweep"] if m["seed"] in J}
    seeds = sorted(set(J) & set(S))
    out = {"n_seeds": len(seeds), "seeds": seeds}

    # 1. paired
    cols = ["score", "score_ex_bonus", "steps", "steps_per_life_ep", "points_per_100_steps", "kills_per_100_steps",
            "points_per_kill", "direction_flip_rate_per_move", "move_run_len_mean", "bonus_hits", "top_row_kills",
            "left_wall_share", "right_wall_share", "fire_rate", "p_fire_shot_in_flight", "fire_latency_mean",
            "fire_immediately_share"]
    out["per_seed"] = [{"seed": s, **{f"jev_{c}": J[s][c] for c in cols}, **{f"sweep_{c}": S[s][c] for c in cols},
                        "diff": J[s]["score"] - S[s]["score"], "diff_ex_bonus": J[s]["score_ex_bonus"] - S[s]["score_ex_bonus"]}
                       for s in seeds]
    out["paired_score"] = paired([J[s]["score"] - S[s]["score"] for s in seeds])
    out["paired_score_ex_bonus"] = paired([J[s]["score_ex_bonus"] - S[s]["score_ex_bonus"] for s in seeds])
    agg = lambda E, c: round(statistics.fmean(e[c] for e in E if e[c] is not None), 3) if any(e[c] is not None for e in E) else None
    out["means"] = {name: {c: agg(E, c) for c in cols} | {"steps_per_life_pooled": round(sum(e["steps"] for e in E) / max(sum(len(e["deaths"]) for e in E), 1), 1)}
                    for name, E in (("jev", [J[s] for s in seeds]), ("sweep", [S[s] for s in seeds]))}
    out["means"]["jev"]["cost_usd_total"] = round(sum(J[s]["cost_usd"] or 0 for s in seeds), 4)
    out["served_models"] = sorted({str(J[s]["served_model"]) for s in seeds})
    out["bonus_games"] = {"jev": sum(J[s]["bonus_hits"] > 0 for s in seeds), "sweep": sum(S[s]["bonus_hits"] > 0 for s in seeds)}

    # 2. persistence vs score
    table = {}
    for arm, E in sorted(by.items()):
        E2 = [e for e in E if e["seed"] in new_seeds] if not arm.endswith("@exp003") else E
        if arm.startswith("control_") or arm.startswith("random"):
            E2 = [e for e in E if e["seed"] in new_seeds]
        if not E2:
            continue
        table[arm] = {"n": len(E2), "score": agg(E2, "score"), "score_ex_bonus": agg(E2, "score_ex_bonus"),
                      "points_per_100_steps": agg(E2, "points_per_100_steps"),
                      "flip_rate": agg(E2, "direction_flip_rate_per_move"), "run_len": agg(E2, "move_run_len_mean"),
                      "steps": agg(E2, "steps"), "p_fire_shot_in_flight": agg(E2, "p_fire_shot_in_flight")}
    out["persistence_by_arm"] = table
    jev_all = [m for a, E in by.items() if a.startswith("jev_") for m in E]
    thr_all = by["jev_basic__threat@exp003"] + by["jev_basic__threat@exp005"]
    out["persistence_within"] = {
        name: {f"{y}~{x}": spearman([e[x] for e in E], [e[y] for e in E])
               for x in ("direction_flip_rate_per_move", "move_run_len_mean", "p_fire_shot_in_flight", "left_wall_share")
               for y in ("score", "score_ex_bonus", "points_per_100_steps", "steps")}
        for name, E in (("all_jev_episodes", jev_all), ("jev_threat_episodes", thr_all))}

    # 3. branch test on every JEV THREAT game (exp003 seeds 1-5 and exp005)
    env_cfg = envmod.env_config(json.loads(Path(jev_eps[0]["_path"], "episode.json").read_text())["env"])
    jobs = []
    for m in thr_all:
        ts = list(range(BRANCH_FROM, m["n_steps"] - 1, BRANCH_EVERY))
        jobs.append((m["path"], m["seed"], env_cfg, ts))
    with Pool(args.procs) as pool:
        B = [b for chunk in pool.map(branch_job, jobs, chunksize=1) for b in chunk]
    out["branch_integrity"] = {"branches": len(B), "prefix_replay_matched": sum(b["integrity_ok"] for b in B)}
    B = [b for b in B if b["integrity_ok"]]
    groups = {"all": B,
              "jev_move_differs": [b for b in B if not b["jev_move_matches"]],
              "jev_move_same": [b for b in B if b["jev_move_matches"]]}
    for reg in ("left_wall", "middle", "right_wall"):
        groups[f"at_{reg}"] = [b for b in B if b["region"] == reg]
    groups["threatened"] = [b for b in B if b["threatened"]]
    groups["threatened_move_differs"] = [b for b in B if b["threatened"] and not b["jev_move_matches"]]
    groups["not_threatened"] = [b for b in B if not b["threatened"]]
    out["branch"] = {w: {g: branch_summary(v, w) for g, v in groups.items()} for w in (W_SHORT, W_LONG)}
    key = lambda b: (b[f"jev_pts_{W_LONG}"] - b[f"sweep_pts_{W_LONG}"]) + 100 * (b[f"sweep_died_{W_LONG}"] - b[f"jev_died_{W_LONG}"])
    rk = sorted(B, key=key)
    slim = lambda b: {k: v for k, v in b.items() if k != "path"} | {"episode": Path(b["path"]).name}
    out["branch_examples"] = {"jev_best": [slim(b) for b in rk[-5:][::-1]], "jev_worst": [slim(b) for b in rk[:5]]}

    # 4. bonus hits
    hits = []
    for m in thr_all:
        rows = [json.loads(l) for l in open(Path(m["path"]) / "steps.jsonl")]
        top0 = min((a["y"] for a in rows[0]["state"]["aliens"]), default=None)
        for i, r in enumerate(rows):
            if r["reward"] >= BONUS:
                # launch = last FIRE press before i made while no own shot was in flight
                launch = next((j for j in range(i - 1, max(i - 40, 0), -1)
                               if "FIRE" in rows[j]["action"] and not threat_analysis(rows[j]["state"])["shot_in_flight"]), None)
                wait = None
                if launch is not None:
                    j = launch
                    while j > 0 and not threat_analysis(rows[j - 1]["state"])["shot_in_flight"]:
                        j -= 1
                    wait = launch - j
                ufo_seen = any(a["y"] < top0 - 4 for k in range(max(i - 15, 0), i + 1) for a in rows[k]["state"]["aliens"]) if top0 else None
                hits.append({"seed": m["seed"], "arm": m["arm"], "step": i, "reward": r["reward"],
                             "x": r["state"]["player"]["x"], "region": region(r["state"]["player"]["x"]),
                             "launch_step": launch, "ready_to_fire_wait_steps": wait,
                             "moves_before_launch": [rows[k]["action"] for k in range(max((launch or i) - 6, 0), (launch or i) + 1)],
                             "object_above_alien_grid_in_state": ufo_seen})
    out["bonus_hits"] = hits
    out["jev_fire_latency_typical"] = {"mean": agg(thr_all, "fire_latency_mean"), "immediate_share": agg(thr_all, "fire_immediately_share")}

    od = Path(args.jev) / "analysis"
    od.mkdir(exist_ok=True)
    (od / "oos.json").write_text(json.dumps(out, indent=1, default=str))
    L = ["| seed | JEV | sweep | diff | diff ex-bonus | JEV moves | sweep moves | JEV flips | JEV run | JEV bonus | sweep bonus | JEV top-row | sweep top-row | JEV left wall |",
         "|---|" + "---|" * 13]
    for p in out["per_seed"]:
        L.append(f"| {p['seed']} | {p['jev_score']:.0f} | {p['sweep_score']:.0f} | {p['diff']:+.0f} | {p['diff_ex_bonus']:+.0f} | {p['jev_steps']} | {p['sweep_steps']} | "
                 f"{p['jev_direction_flip_rate_per_move']} | {p['jev_move_run_len_mean']} | {p['jev_bonus_hits']} | {p['sweep_bonus_hits']} | "
                 f"{p['jev_top_row_kills']} | {p['sweep_top_row_kills']} | {p['jev_left_wall_share']} |")
    for k in ("paired_score", "paired_score_ex_bonus", "means", "served_models", "bonus_games", "persistence_by_arm",
              "persistence_within", "branch_integrity", "branch", "branch_examples", "bonus_hits", "jev_fire_latency_typical"):
        L += ["", f"## {k}", "```", json.dumps(out[k], indent=1, default=str), "```"]
    (od / "oos.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
