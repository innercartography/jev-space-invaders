"""Run an experiment: every arm x every seed, one traced episode each.

    python -m ufa.arena.run --config ufa/experiments/exp001_first_light.json
    python -m ufa.arena.run --config ... --arms jev_basic__raw --seeds 1 --max-steps 300

Arms in a config differ in exactly the dimensions you name (policy, representation,
question set, model). Env settings, seeds and the clock are shared by all arms.
"""
import argparse
import hashlib
import json
import platform
import socket
import statistics
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import env as envmod
from . import keys, policies, pricing, representations
from .extract import Extractor
from .trace import EpisodeTrace

REPO = Path(__file__).resolve().parents[2]
ARENA = Path(__file__).resolve().parent
HISTORY_KEEP = 16


def code_hash():
    h = hashlib.sha256()
    for p in sorted(ARENA.glob("*.py")):
        h.update(p.name.encode())
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:12]


def source_commit():
    try:
        out = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "ufa/arena"],
                                   capture_output=True, text=True, timeout=5).stdout.strip()
            return out.stdout.strip()[:12] + ("-dirty" if dirty else "")
    except (OSError, subprocess.SubprocessError):
        pass
    f = REPO / ".source_commit"
    return f.read_text().strip() if f.exists() else None


def config_hash(cfg):
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:12]


def pct(values, q):
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * q
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[f] + (s[c] - s[f]) * (k - f), 2)


def run_episode(cfg, arm, seed, out_root, secret_values, max_steps=None, replicate=0):
    env_cfg = envmod.env_config(cfg.get("env"))
    clock = cfg.get("clock", "turn_based")
    low_conf = cfg.get("low_conf_threshold", 0.5)
    max_steps = max_steps or cfg.get("max_steps")
    step_ms = envmod.FRAME_MS * env_cfg["frameskip"]

    env = envmod.make_env(env_cfg)
    actions = envmod.action_names(env)
    # The env is always seeded with `seed`. `replicate` labels a run; only the random
    # policy's own RNG uses it (JEV is stochastic on its own, the env is not).
    policy_seed = seed if not replicate else seed * 1000 + replicate
    policy = policies.build(arm, policy_seed)
    rep_fn = representations.get(arm.get("representation", "raw"))
    trace = EpisodeTrace(out_root, cfg["experiment_id"], arm["name"], seed, secret_values)

    started_at = datetime.now(timezone.utc).isoformat()
    t_start = time.perf_counter()
    ram, info = env.reset(seed=seed)
    tap = envmod.install_tap(env)
    tap.frames.clear()
    ex = Extractor()
    history = []
    score, step, prev_action = 0.0, 0, None
    lives = int(info.get("lives", 0))
    lives_lost = 0
    decision_ms, lat_model, confidences = [], [], []
    rep_chars = []
    counts = Counter()
    held = Counter()
    statuses = Counter()
    in_tok = out_tok = 0
    tok_known = True
    served = None
    retries = fallbacks = model_calls = reward_events = lag_total = env_steps = 0
    env_ms = 0.0
    terminated = truncated = False
    reason = None

    initial_state = ex.extract(*envmod.last_two_frames(env), ram, info, score, step, prev_action)
    ex = Extractor()  # fresh tracker so step 0 is not "tracked" against itself
    initial = {"ram_hex": bytes(ram).hex(), "info": {k: v for k, v in info.items() if k != "seeds"},
               "extracted": initial_state}

    while True:
        te = time.perf_counter()
        st = ex.extract(*envmod.last_two_frames(env), ram, info, score, step, prev_action)
        rep = rep_fn(st, history)
        rep_text = json.dumps(rep, separators=(",", ":"))
        env_ms += (time.perf_counter() - te) * 1000

        t0 = time.perf_counter()
        d = policy.decide(rep, actions)
        dms = (time.perf_counter() - t0) * 1000
        action = d["action"]
        counts[action] += 1
        dec = d.get("decider")
        if d.get("held"):
            held[d["held"]] += 1
        # latency and input size are per decision: a step that repeats an earlier answer (decision
        # interval) makes no decision and no call, so it isn't counted
        if not (policy.uses_model and dec is None):
            decision_ms.append(dms)
            rep_chars.append(len(rep_text))
        if policy.uses_model:
            if dec:
                model_calls += 1
                lat_model.append(dec["latency_ms"])
                served = dec.get("served_model") or served
                retries += dec.get("retries") or 0
                for s in dec.get("statuses") or []:
                    if s != 200:
                        statuses[str(s)] += 1
                if dec.get("error"):
                    statuses[str(dec["error"].get("status") or dec["error"]["type"])] += 1
                if dec.get("input_tokens") is None:
                    tok_known = False
                else:
                    in_tok += dec["input_tokens"]
                    out_tok += dec.get("output_tokens") or 0
        if d["fallback"]:
            fallbacks += 1
        if d.get("confidence") is not None:
            confidences.append(d["confidence"])

        # Realtime clock: while the decider was thinking, the game kept running with the old action.
        lag_steps, lag_reward = 0, 0.0
        te = time.perf_counter()
        if clock == "realtime":
            lag_steps = int(dms // step_ms)
            hold = actions.index(prev_action) if prev_action else 0
            for _ in range(lag_steps):
                ram, r, terminated, truncated, info = env.step(hold)
                env_steps += 1
                lag_reward += r
                if terminated or truncated:
                    break
            lag_total += lag_steps
        if not (terminated or truncated):
            ram, r, terminated, truncated, info = env.step(actions.index(action))
            env_steps += 1
        else:
            r = 0.0
        env_ms += (time.perf_counter() - te) * 1000
        reward = r + lag_reward
        score += reward
        if reward > 0:
            reward_events += 1
        new_lives = int(info.get("lives", 0))
        if new_lives < lives:
            lives_lost += lives - new_lives
        lives = new_lives

        trace.step({
            "step": step, "t_ms": round((time.perf_counter() - t_start) * 1000, 1),
            "state": st, "representation": rep, "rep_chars": len(rep_text),
            "action": action, "fallback": d["fallback"], "confidence": d.get("confidence"),
            "decision_ms": round(dms, 2), "decider": dec, "held": d.get("held"),
            "lag_steps": lag_steps, "reward": reward, "score": score, "lives": lives,
            "frame": int(info.get("episode_frame_number", 0)),
        })
        history.append(st)
        del history[:-HISTORY_KEEP]
        prev_action = action
        step += 1
        if terminated:
            reason = "game_over"
        elif truncated:
            reason = "env_truncated"
        elif max_steps and step >= max_steps:
            reason = "max_steps"
        if reason:
            break

    wall = time.perf_counter() - t_start
    desc = policy.describe()
    policy.close()
    trace.close()
    env.close()
    served = served or desc.get("served_model")
    cost = pricing.cost_usd(served or desc.get("requested_model"), in_tok, out_tok) if (policy.uses_model and tok_known) else (0.0 if not policy.uses_model else None)

    summary = {
        # official results.json run fields
        "seed": seed, "score": score, "steps": step, "frames": int(info.get("episode_frame_number", 0)),
        "lives_lost": lives_lost, "terminated": bool(terminated), "truncated": bool(truncated),
        "model_calls": model_calls,
        "input_tokens": in_tok if (policy.uses_model and tok_known) else (0 if not policy.uses_model else None),
        "output_tokens": out_tok if (policy.uses_model and tok_known) else (0 if not policy.uses_model else None),
        "latency_ms_p50": pct(decision_ms, 0.5), "latency_ms_p95": pct(decision_ms, 0.95),
        "latency_ms_total": round(sum(decision_ms), 1),
        "errors_by_status": dict(statuses), "retries": retries, "fallback_actions": fallbacks,
        "mean_confidence": round(statistics.fmean(confidences), 4) if confidences else None,
        "low_conf_rate": round(sum(c < low_conf for c in confidences) / len(confidences), 4) if confidences else None,
        "cost_usd": round(cost, 6) if cost is not None else None,
        "wall_clock_s": round(wall, 2), "served_model": served,
        "notes": arm.get("notes", ""),
        # arena extras
        "episode_id": trace.episode_id, "arm": arm["name"], "policy": arm["policy"],
        "rep": replicate, "policy_seed": policy_seed,
        "representation": arm.get("representation", "raw"), "question_set": desc.get("question_set"),
        "requested_model": desc.get("requested_model"), "provider": desc.get("provider"),
        "started_at": started_at, "ended_at": datetime.now(timezone.utc).isoformat(),
        "termination_reason": reason, "max_steps": max_steps, "clock": clock, "lag_steps_total": lag_total,
        "model_latency_ms_p50": pct(lat_model, 0.5), "model_latency_ms_p95": pct(lat_model, 0.95),
        "env_and_extract_ms_total": round(env_ms, 1),
        "cost_per_decision_usd": round(cost / model_calls, 8) if (cost is not None and model_calls) else (0.0 if cost == 0 else None),
        "cost_per_step_usd": round(cost / step, 8) if (cost is not None and step) else None,
        "decisions": step, "env_steps": env_steps,  # realtime: env steps include the lag steps played while deciding
        "decision_interval_steps": desc.get("decision_interval", 1), "held_steps": dict(held),
        "reward_events": reward_events, "fire_actions": sum(v for k, v in counts.items() if "FIRE" in k),
        "player_shots_seen": ex.shots_seen, "action_counts": dict(counts),
        "rep_chars_mean": round(statistics.fmean(rep_chars), 1) if rep_chars else None,
        "rep_chars_total": sum(rep_chars),
        "orchestration": {"workers": 1, "subagent_calls": 0, "tool_calls": 0, "inter_agent_messages": 0},
        "compute_host": {"hostname": socket.gethostname(), "platform": platform.platform(),
                         "python": platform.python_version()},
    }
    trace.episode({
        "episode_id": trace.episode_id, "experiment_id": cfg["experiment_id"],
        "config_hash": config_hash(cfg), "code_hash": code_hash(), "source_commit": source_commit(),
        "env": env_cfg, "versions": envmod.versions(), "arm": arm, "policy": desc,
        "candidate_actions": actions, "pricing_as_of": pricing.AS_OF,
        "initial": initial, "summary": summary,
    })
    return trace.dir, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--arms", help="comma-separated arm names (default: all)")
    ap.add_argument("--seeds", help="comma-separated seeds (default: config seeds)")
    ap.add_argument("--max-steps", type=int)
    ap.add_argument("--reps", default="0", help="replicate labels, e.g. 1,2,3 or 1-10 (default: 0)")
    ap.add_argument("--env-file")
    ap.add_argument("--out", default=str(REPO / "ufa" / "traces"))
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    arms = cfg["arms"]
    if args.arms:
        want = args.arms.split(",")
        arms = [a for a in arms if a["name"] in want]
    seeds = [int(s) for s in args.seeds.split(",")] if args.seeds else cfg["seeds"]

    needed = sorted({k for a in arms for k in policies.SECRETS[a["policy"]]})
    secret_values = keys.load(needed, args.env_file)

    a, _, b = args.reps.partition("-")
    reps = list(range(int(a), int(b) + 1)) if b else [int(r) for r in args.reps.split(",")]

    for rep, seed, arm in [(r, s, a) for r in reps for s in seeds for a in arms]:
        path, s = run_episode(cfg, arm, seed, args.out, secret_values, args.max_steps, rep)
        print(json.dumps({"arm": arm["name"], "seed": seed, "rep": rep, "score": s["score"], "steps": s["steps"],
                          "lives_lost": s["lives_lost"], "p50_ms": s["latency_ms_p50"],
                          "p95_ms": s["latency_ms_p95"], "cost_usd": s["cost_usd"],
                          "fallbacks": s["fallback_actions"], "reason": s["termination_reason"],
                          "trace": str(path)}), flush=True)


if __name__ == "__main__":
    main()
