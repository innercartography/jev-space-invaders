"""Run many single-game Tenki jobs, a few at a time. Plain fan-out, nothing adaptive.

    python -m ufa.tenki.batch --config ufa/experiments/exp002_repr_check.json \
        --arms jev_basic__raw,jev_basic__threat --seeds 1,2,3,4,5 --reps 1,2,3 --parallel 5

Each job is one `ufa.tenki.remote_episode` process: one sandbox, one game, destroyed after.
Jobs are ordered rep -> seed -> arm, so every wave mixes arms (no arm runs only at one time
of day). A failed job is logged and kept; it is not retried, so failures stay visible.
Writes <out>/batch_<utc>.json with one line per job.
"""
import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def run_job(job, config, log_dir):
    arm, seed, rep = job
    cmd = [sys.executable, "-m", "ufa.tenki.remote_episode", "--config", config,
           "--arm", arm, "--seed", str(seed), "--rep", str(rep)]
    t = time.perf_counter()
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    log = log_dir / f"{arm}__s{seed}__r{rep}.log"
    log.write_text(p.stdout[-20000:] + "\n--- stderr ---\n" + p.stderr[-20000:])
    rec = {"arm": arm, "seed": seed, "rep": rep, "exit": p.returncode, "wall_s": round(time.perf_counter() - t, 2),
           "log": str(log)}
    try:
        tr = json.loads(p.stdout[p.stdout.rindex("\n{\n") + 1:] if "\n{\n" in p.stdout else p.stdout[p.stdout.index("{\n"):])
        rec.update({"sandbox_id": tr.get("sandbox_id"), "error": tr.get("error"),
                    "score": (tr.get("episode_summary") or {}).get("score")})
    except ValueError:
        rec["error"] = rec.get("error") or "no tenki_run.json output"
    print(json.dumps(rec), flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--arms", required=True)
    ap.add_argument("--seeds", required=True)
    ap.add_argument("--reps", default="1")
    ap.add_argument("--parallel", type=int, default=5)
    ap.add_argument("--out", default=str(REPO / "ufa" / "traces-remote" / "tenki"))
    args = ap.parse_args()
    jobs = [(a, int(s), int(r)) for r in args.reps.split(",") for s in args.seeds.split(",")
            for a in args.arms.split(",")]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_dir = Path(args.out) / f"batch_{stamp}_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    t = time.perf_counter()
    with ThreadPoolExecutor(args.parallel) as pool:
        recs = list(pool.map(lambda j: run_job(j, args.config, log_dir), jobs))
    out = {"started": stamp, "config": args.config, "parallel": args.parallel, "jobs": recs,
           "wall_s": round(time.perf_counter() - t, 2),
           "failed": sum(1 for r in recs if r["exit"] != 0 or r.get("error"))}
    (Path(args.out) / f"batch_{stamp}.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != "jobs"}))


if __name__ == "__main__":
    main()
