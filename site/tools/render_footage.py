"""Render real footage for the public site from recorded games (no model, no key).

Every clip is an exact emulator replay of a recorded game: seed + logged action string.
The script checks the replayed score against the recorded one before writing anything.

    python site/tools/render_footage.py
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from PIL import Image  # noqa: E402

from ufa.arena import env as envmod  # noqa: E402
from ufa.verify_replay import ALPHABET  # noqa: E402
from ufa.arena.extract import PLAYER_RGB, SHIP_BOTTOM, SHIP_TOP, _mask  # noqa: E402
import numpy as np  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "site" / "assets"
FFMPEG = shutil.which("ffmpeg")
SCALE = 3


def replay_frames(env_over, seed, actions, names, max_steps=None):
    env = envmod.make_env(envmod.env_config(env_over))
    assert envmod.action_names(env) == names, "action set differs"
    env.reset(seed=seed)
    ale = env.unwrapped.ale
    frames, acts, score, steps = [ale.getScreenRGB().copy()], [], 0.0, 0
    for ch in actions:
        _, r, term, trunc, info = env.step(ALPHABET.index(ch))
        score += r
        steps += 1
        if max_steps is None or steps <= max_steps:
            frames.append(ale.getScreenRGB().copy())
            acts.append(names[ALPHABET.index(ch)])
        if term or trunc:
            break
    env.close()
    return frames, acts, score, steps


def ship_x(frame):
    cols = np.nonzero(_mask(frame[SHIP_TOP:SHIP_BOTTOM + 1], PLAYER_RGB).any(axis=0))[0]
    return int(round((cols[0] + cols[-1]) / 2)) if len(cols) else None


def encode(frames, path, fps=15):
    with tempfile.TemporaryDirectory() as td:
        for i, f in enumerate(frames):
            im = Image.fromarray(f)
            im = im.resize((im.width * SCALE, im.height * SCALE), Image.NEAREST)
            im.save(f"{td}/{i:05d}.png")
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", f"{td}/%05d.png",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "24", "-preset", "slow",
                        "-movflags", "+faststart", str(path)], check=True)


def still(frame, path):
    im = Image.fromarray(frame)
    im.resize((im.width * SCALE, im.height * SCALE), Image.NEAREST).save(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    # 1. a JEV holdout game near the holdout mean (709): seed 1895794344, recorded 705
    rp = json.loads(next(p for p in (REPO / "ufa/replays/holdout.json", REPO / "replays/holdout.json") if p.exists()).read_text())
    g = next(x for x in rp["games"] if x["arm"] == "jev_final" and str(x["seed"]) == "1895794344")
    env_over = g["env"] if isinstance(g["env"], dict) else eval(g["env"])  # packed as a dict
    names = g["action_names"] if isinstance(g["action_names"], list) else eval(g["action_names"])
    frames, acts, score, steps = replay_frames(env_over, int(g["seed"]), g["actions"], names, max_steps=750)
    exp = g["expected"] if isinstance(g["expected"], dict) else eval(g["expected"])
    assert score == exp["score"] and steps == exp["steps"], (score, steps, exp)
    encode(frames, OUT / "pilot.mp4")
    still(frames[400], OUT / "pilot_still.png")
    # frame i+1 shows the result of action i; the label for frame i is the action JEV chose there
    (OUT / "pilot_actions.json").write_text(json.dumps({"fps": 15, "width": 160, "actions": acts,
                                                        "ship_x": [ship_x(f) for f in frames]}))
    manifest["pilot"] = {"source": "ufa/replays/holdout.json", "episode_id": g["episode_id"], "seed": g["seed"],
                         "recorded_score": exp["score"], "replayed_score": score, "steps_total": steps,
                         "steps_shown": len(acts), "matched": True}
    # 2. the swarm's two game variations: the old champion (still-on-ready), same seed, each regime
    for reg in ("A", "B"):
        land = json.loads((REPO / f"ufa/squad/swarm/landscape/{reg}.json").read_text())
        lg = next(x for x in land["games"] if x["config"] == "still-on-ready" and x["seed"] == 100)
        fr, _, sc, st = replay_frames(dict(lg["regime"]), lg["seed"], lg["actions"], lg["action_names"], max_steps=300)
        assert sc == lg["score"] and st == lg["steps"], (reg, sc, st, lg["score"], lg["steps"])
        encode(fr, OUT / f"regime_{reg}.mp4")
        still(fr[200], OUT / f"regime_{reg}.png")
        manifest[f"regime_{reg}"] = {"source": f"ufa/squad/swarm/landscape/{reg}.json", "config": lg["config"],
                                     "seed": lg["seed"], "regime": lg["regime"], "recorded_score": lg["score"],
                                     "replayed_score": sc, "matched": True}
    (OUT / "footage_manifest.json").write_text(json.dumps(manifest, indent=1))
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
