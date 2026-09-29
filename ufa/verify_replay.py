"""Exact replay verification: every recorded game's score is re-derived from its seed and action log.

JEV is not deterministic, so a JEV game can't be re-run to the same score. The emulator is: the
same seed and the same action sequence always give the same game. So each recorded run can be
checked exactly by replaying its actions, with no model and no API key.

    python -m ufa.verify_replay pack --exp ufa/traces/exp006_tournament --out replays.json [--arms a,b]
    python -m ufa.verify_replay check replays.json --out verify_report.json

`pack` writes seeds, env settings, the action log (one character per step) and the recorded
outcome. `check` replays each game and compares score, steps, frames and lives lost.
"""
import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

ALPHABET = "0123456789"


def pack(exp_dirs, arms=None, seeds=None):
    from ufa.arena.compare import load

    games = []
    for d in exp_dirs:
        for e in load(d):
            s = e["summary"]
            if arms and s["arm"] not in arms:
                continue
            if seeds and s["seed"] not in seeds:
                continue
            ep = json.loads((Path(e["_path"]) / "episode.json").read_text())
            if s.get("clock") != "turn_based":
                continue  # a realtime game also steps during model latency; its log alone can't replay it
            names = ep["candidate_actions"]
            acts = [json.loads(l)["action"] for l in open(Path(e["_path"]) / "steps.jsonl")]
            games.append({"episode_id": s["episode_id"], "experiment_id": ep["experiment_id"], "arm": s["arm"],
                          "seed": s["seed"], "env": ep["env"], "action_names": names,
                          "actions": "".join(ALPHABET[names.index(a)] for a in acts),
                          "served_model": s.get("served_model"),
                          "expected": {k: s[k] for k in ("score", "steps", "frames", "lives_lost")}})
    return {"format": "ufa-replay-1", "games": games}


def replay(g):
    from ufa.arena import env as envmod

    env = envmod.make_env(envmod.env_config(g["env"]))
    names = envmod.action_names(env)
    if names != g["action_names"]:
        return {"ok": False, "why": "action set differs"}
    ram, info = env.reset(seed=g["seed"])
    lives0 = int(info.get("lives", 0))
    score, steps, lost, lives = 0.0, 0, 0, lives0
    for ch in g["actions"]:
        ram, r, term, trunc, info = env.step(ALPHABET.index(ch))
        score += r
        steps += 1
        nl = int(info.get("lives", 0))
        lost += max(lives - nl, 0)
        lives = nl
        if term or trunc:
            break
    got = {"score": score, "steps": steps, "frames": int(info.get("episode_frame_number", 0)), "lives_lost": lost}
    env.close()
    return {"ok": got == g["expected"], "got": got}


def check(path, out=None):
    import ale_py
    import gymnasium

    data = json.loads(Path(path).read_text())
    t = time.perf_counter()
    res = []
    for g in data["games"]:
        r = replay(g)
        res.append({"episode_id": g["episode_id"], "arm": g["arm"], "seed": g["seed"], "expected": g["expected"], **r})
    rep = {"input_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(), "games": len(res),
           "matched": sum(r["ok"] for r in res), "mismatched": [r for r in res if not r["ok"]],
           "wall_s": round(time.perf_counter() - t, 2), "host": platform.node(), "platform": platform.platform(),
           "python": platform.python_version(), "ale_py": ale_py.__version__, "gymnasium": gymnasium.__version__,
           "results": res}
    if out:
        Path(out).write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "results"}, indent=1))
    return rep


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack")
    p.add_argument("--exp", nargs="+", required=True)
    p.add_argument("--arms")
    p.add_argument("--out", required=True)
    c = sub.add_parser("check")
    c.add_argument("path")
    c.add_argument("--out")
    a = ap.parse_args()
    if a.cmd == "pack":
        d = pack(a.exp, set(a.arms.split(",")) if a.arms else None)
        Path(a.out).write_text(json.dumps(d, separators=(",", ":")))
        print(f"{len(d['games'])} games -> {a.out}")
    else:
        check(a.path, a.out)


if __name__ == "__main__":
    main()
