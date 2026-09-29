"""The swarm experiment's search landscape: 12 rule-based player configurations x seeds x two regimes.

The swarm study (ufa/squad/swarm.py) is about how a population searches, not about who flies the
ship, so the candidates are cheap deterministic controllers (no model): every game can be re-derived
from seed + action log, and hundreds of games cost nothing but emulator time. JEV is the swarm's
governance layer; it never picks a move here.

A configuration is three choices, so findings can generalize ("dodging helps") and can go stale:
    move   sweep | track | still   sweep = wall to wall; track = toward the nearest alien column
    dodge  off | on                on = if the planned move is projected unsafe (move_is_safe), take a safe one
    fire   ready | aimed           ready = whenever a shot is available; aimed = only with an alien above

Regimes are official ALE SpaceInvaders game variations (same ROM, the cartridge's own game-select):
    A  mode 0, difficulty 0   the standard game (the competition setting)
    B  set by --regime-b after screening (see the ledger); the swarm is told the context changed,
       never which old conclusions are now wrong.

    python -m ufa.squad.landscape gen --regime A --seeds 0:40 --out ufa/squad/landscape/A.json --procs 8
    python -m ufa.squad.landscape screen --modes 0,2,4,8 --seeds 0:6
"""
import argparse
import itertools
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ALPHABET = "0123456789"
MOVES, DODGES, FIRES = ("sweep", "track", "still"), ("off", "on"), ("ready", "aimed")
CONFIGS = {f"{m}-{d}-{f}": {"move": m, "dodge": d, "fire": f} for m, d, f in itertools.product(MOVES, DODGES, FIRES)}
REGIMES = {"A": {"mode": 0, "difficulty": 0}}
BONUS_MIN = 50  # a single reward >= 50 is the mothership bonus; ex-bonus score removes that luck


class RulePolicy:
    X_LIMITS = (37, 108)

    def __init__(self, cfg):
        self.c = cfg
        self.dir = "right"

    def decide(self, rep):
        x = rep.get("ship_x")
        if x is None:
            return "FIRE" if rep.get("shot_ready") else "NOOP"
        if self.c["move"] == "sweep":
            if x <= self.X_LIMITS[0] + 1:
                self.dir = "right"
            elif x >= self.X_LIMITS[1] - 1:
                self.dir = "left"
            move = self.dir
        elif self.c["move"] == "track":
            dx = rep.get("nearest_alien_dx")
            move = "stay" if (dx is None or abs(dx) <= 2) else ("right" if dx > 0 else "left")
        else:
            move = "stay"
        safe = rep.get("move_is_safe") or {}
        if self.c["dodge"] == "on" and safe.get(move) is False:
            for alt in [m for m in ("stay", self.dir, "left", "right") if m != move]:
                if safe.get(alt):
                    move = alt
                    break
        fire = rep.get("shot_ready") and (self.c["fire"] == "ready" or rep.get("alien_above"))
        name = {"left": "LEFT", "right": "RIGHT", "stay": ""}[move] + ("FIRE" if fire else "")
        return name or "NOOP"


def env_cfg(regime):
    from ufa.arena import env as envmod
    return envmod.env_config(regime)


def play(config, seed, regime):
    """One game. Returns outcome + action log (replayable with the same env settings)."""
    import gymnasium as gym
    from ufa.arena import env as envmod
    from ufa.arena.extract import Extractor
    from ufa.arena.representations import threat_safe

    ec = env_cfg(regime)
    env = gym.make(ec["env_id"], obs_type=ec["obs_type"], frameskip=ec["frameskip"],
                   repeat_action_probability=ec["repeat_action_probability"], full_action_space=ec["full_action_space"],
                   max_num_frames_per_episode=ec["max_num_frames_per_episode"],
                   mode=regime["mode"], difficulty=regime["difficulty"])
    names = envmod.action_names(env)
    pol = RulePolicy(CONFIGS[config])
    ram, info = env.reset(seed=seed)
    envmod.install_tap(env).frames.clear()
    ex = Extractor()
    score = exb = 0.0
    step, prev, acts, lives, lost = 0, None, [], int(info.get("lives", 0)), 0
    while True:
        st = ex.extract(*envmod.last_two_frames(env), ram, info, score, step, prev)
        a = pol.decide(threat_safe(st, []))
        ram, r, term, trunc, info = env.step(names.index(a))
        acts.append(ALPHABET[names.index(a)])
        score += r
        exb += r if r < BONUS_MIN else 0
        nl = int(info.get("lives", 0))
        lost += max(lives - nl, 0)
        lives, prev, step = nl, a, step + 1
        if term or trunc:
            break
    frames = int(info.get("episode_frame_number", 0))
    env.close()
    return {"config": config, "seed": seed, "regime": regime, "score": score, "score_ex_bonus": exb,
            "steps": step, "frames": frames, "lives_lost": lost, "action_names": names, "actions": "".join(acts)}


def _job(args):
    t = time.perf_counter()
    out = play(*args)
    out["wall_s"] = round(time.perf_counter() - t, 2)
    return out


def seeds_arg(s):
    a, b = s.split(":")
    return list(range(int(a), int(b)))


def run_jobs(jobs, procs):
    with ProcessPoolExecutor(procs) as pool:
        return list(pool.map(_job, jobs))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen")
    g.add_argument("--mode", type=int, default=0)
    g.add_argument("--difficulty", type=int, default=0)
    g.add_argument("--seeds", default="0:40")
    g.add_argument("--configs", default=",".join(CONFIGS))
    g.add_argument("--out", required=True)
    g.add_argument("--procs", type=int, default=8)
    s = sub.add_parser("screen")
    s.add_argument("--variants", default="0/0,0/1,2/0,4/0,6/0,1/0")
    s.add_argument("--seeds", default="0:6")
    s.add_argument("--out", required=True)
    s.add_argument("--procs", type=int, default=8)
    a = ap.parse_args()
    t = time.perf_counter()
    if a.cmd == "gen":
        reg = {"mode": a.mode, "difficulty": a.difficulty}
        games = run_jobs([(c, sd, reg) for c in a.configs.split(",") for sd in seeds_arg(a.seeds)], a.procs)
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps({"regime": reg, "env": env_cfg(reg), "games": games}, separators=(",", ":")))
    else:
        variants = [dict(zip(("mode", "difficulty"), map(int, v.split("/")))) for v in a.variants.split(",")]
        games = run_jobs([(c, sd, v) for v in variants for c in CONFIGS for sd in seeds_arg(a.seeds)], a.procs)
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps({"games": [{k: v for k, v in x.items() if k != "actions"} for x in games]}))
    print(f"{len(games)} games in {time.perf_counter() - t:.0f}s -> {a.out}")


if __name__ == "__main__":
    main()
