"""Capture what the model actually saw: the RAW, THREAT and SAFE views of ONE real frame of the
recorded JEV holdout game shown on the site (seed 1895794344), computed by the same extractor and
representation code the games used. No model call.

    python site/tools/render_views.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from PIL import Image  # noqa: E402

from ufa.arena import env as envmod, representations  # noqa: E402
from ufa.arena.extract import Extractor  # noqa: E402
from ufa.verify_replay import ALPHABET  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "site" / "assets"


def main():
    rp = json.loads(next(p for p in (REPO / "ufa/replays/holdout.json", REPO / "replays/holdout.json") if p.exists()).read_text())
    g = next(x for x in rp["games"] if x["arm"] == "jev_final" and str(x["seed"]) == "1895794344")
    env = envmod.make_env(envmod.env_config(g["env"]))
    names = envmod.action_names(env)
    ram, info = env.reset(seed=int(g["seed"]))
    envmod.install_tap(env)
    ex = Extractor()
    ex.extract(*envmod.last_two_frames(env), ram, info, 0.0, 0, None)
    ex = Extractor()
    score, prev, hist, pick = 0.0, None, [], None
    for step, ch in enumerate(g["actions"]):
        st = ex.extract(*envmod.last_two_frames(env), ram, info, score, step, prev)
        enemy = [p for p in st["projectiles"] if p["owner"] == "enemy"]
        if step >= 380 and len(enemy) >= 2 and pick is None:
            pick = step
            views = {k: representations.get(k)(st, hist) for k in ("raw", "threat", "threat_safe")}
            Image.fromarray(env.unwrapped.ale.getScreenRGB()).resize((480, 630), Image.NEAREST).save(OUT / "view_frame.png")
            chosen = names[ALPHABET.index(ch)]
            break
        hist.append(st)
        ram, r, term, trunc, info = env.step(ALPHABET.index(ch))
        score += r
        prev = names[ALPHABET.index(ch)]
    env.close()
    out = {"source": "replays/holdout.json", "episode_id": g["episode_id"], "step": pick, "jev_action": chosen,
           "chars": {k: len(json.dumps(v, separators=(",", ":"))) for k, v in views.items()}, "views": views}
    (OUT / "views.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("step", "jev_action", "chars")}))


if __name__ == "__main__":
    main()
