"""Run many arena games on this host concurrently, with a fixed cap. For API-bound arms (e.g. the
Haiku baseline): the host mostly waits on the network, so games overlap instead of queueing.

    python -m ufa.local_batch --config ufa/experiments/exp002_repr_check.json \
        --arms baseline_llm__raw --seeds 1,2,3,4,5 --reps 1 --parallel 5

Each job is its own `ufa.arena.run` process with one arm, one seed and one rep, so every game keeps
its own seed, trace directory and config hash, exactly as a serial run would. Only scheduling
changes. It lives outside ufa/arena on purpose, so the arena code hash is unchanged.
Failed jobs are logged, not retried. Writes <out>/<exp>/local_batch_<utc>.json.
"""
import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def run_job(job, config, out, log_dir, timeout_s=None):
    """One game in its own process. A game that exceeds timeout_s (a hung API call) is killed and
    logged as exit 'timeout'; its partial trace has no episode.json, so analyses skip it."""
    arm, seed, rep = job
    cmd = [sys.executable, "-m", "ufa.arena.run", "--config", config, "--arms", arm,
           "--seeds", str(seed), "--reps", str(rep), "--out", out]
    t = time.perf_counter()
    try:
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=timeout_s)
        code, so, se = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        code = "timeout"
        so = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        se = (e.stderr or b"").decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
    log = log_dir / f"{arm}__s{seed}__r{rep}.log"
    log.write_text(so[-20000:] + "\n--- stderr ---\n" + se[-20000:])
    rec = {"arm": arm, "seed": seed, "rep": rep, "exit": code, "wall_s": round(time.perf_counter() - t, 2)}
    lines = [l for l in so.splitlines() if l.startswith("{")]
    if lines:
        rec.update({k: json.loads(lines[-1]).get(k) for k in ("score", "steps", "p50_ms", "trace")})
    print(json.dumps(rec), flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--arms", required=True)
    ap.add_argument("--seeds", help="comma-separated seeds")
    ap.add_argument("--seeds-file", help="JSON file with a 'seeds' list (e.g. ufa/experiments/seeds_dev.json)")
    ap.add_argument("--seed-range", default=":", help="python slice into --seeds-file, e.g. 0:20")
    ap.add_argument("--reps", default="1")
    ap.add_argument("--parallel", type=int, default=5)
    ap.add_argument("--holdout", action="store_true", help="required to use the frozen holdout seed file")
    ap.add_argument("--game-timeout-s", type=float, default=1500, help="kill a game after this long (hung API call)")
    ap.add_argument("--out", default=str(REPO / "ufa" / "traces"))
    args = ap.parse_args()
    exp = json.loads(Path(args.config).read_text())["experiment_id"]
    if args.seeds_file:
        if "holdout" in Path(args.seeds_file).name and not args.holdout:
            raise SystemExit("holdout seeds need --holdout (run once, after candidate selection)")
        lo, _, hi = args.seed_range.partition(":")
        seeds = json.loads(Path(args.seeds_file).read_text())["seeds"][int(lo) if lo else None:int(hi) if hi else None]
    else:
        seeds = [int(s) for s in args.seeds.split(",")]
    jobs = [(a, int(s), int(r)) for r in args.reps.split(",") for s in seeds for a in args.arms.split(",")]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_dir = Path(args.out) / exp / f"local_batch_{stamp}_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    t = time.perf_counter()
    with ThreadPoolExecutor(args.parallel) as pool:
        recs = list(pool.map(lambda j: run_job(j, args.config, args.out, log_dir, args.game_timeout_s), jobs))
    out = {"started": stamp, "config": args.config, "parallel": args.parallel, "jobs": recs,
           "wall_s": round(time.perf_counter() - t, 2), "failed": sum(1 for r in recs if r["exit"] != 0)}
    (Path(args.out) / exp / f"local_batch_{stamp}.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != "jobs"}))


if __name__ == "__main__":
    main()
