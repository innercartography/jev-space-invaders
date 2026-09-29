"""Generate the swarm landscape in parallel Tenki sandboxes (one sandbox = one worker's share of games).

    python -m ufa.squad.tenki_landscape --regimes A=0/0,B=1/0 --seeds 100:140 --workers 8 --out ufa/squad/swarm/landscape

Each sandbox gets only the environment + extraction code and the rule controllers (no model, no key of
any kind), plays its share of (config, seed, regime) games and returns scores and action logs. The
merged file is replayable: every score can be re-derived from seed + actions with ufa.verify_replay.
"""
import argparse
import base64
import io
import json
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from ufa.arena import keys
from ufa.squad.landscape import CONFIGS, seeds_arg
from ufa.tenki.remote_episode import RATE_GIB_S, RATE_VCPU_S

REPO = Path(__file__).resolve().parents[2]
REQS = "gymnasium==1.3.0\nale-py==0.12.1\nnumpy==2.5.3\n"
FILES = ["ufa/__init__.py", "ufa/arena/__init__.py", "ufa/arena/env.py", "ufa/arena/extract.py",
         "ufa/arena/representations.py", "ufa/squad/__init__.py", "ufa/squad/landscape.py"]
RUNNER = """
import json, sys
from ufa.squad.landscape import run_jobs
jobs = [tuple(j) for j in json.load(open('jobs.json'))]
json.dump(run_jobs(jobs, int(sys.argv[1])), open('out.json', 'w'), separators=(',', ':'))
"""


def bundle(jobs):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for p in FILES:
            tar.add(REPO / p, arcname=p)
        for name, data in (("requirements.txt", REQS.encode()), ("jobs.json", json.dumps(jobs).encode()),
                           ("runner.py", RUNNER.encode())):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def run_worker(i, jobs, cpu, mem):
    from tenki import Sandbox

    rec = {"worker": i, "jobs": len(jobs), "timings_s": {}}
    T = rec["timings_s"]
    t = time.perf_counter()
    try:
        sb = Sandbox.create(name=f"ufa-swarm-w{i}", cpu_cores=cpu, memory_mb=mem, max_duration=1800,
                            allow_inbound=False, tags=["ufa", "swarm"], metadata={"worker": str(i)})
    except Exception as e:
        return {**rec, "error": f"create: {type(e).__name__}: {str(e)[:300]}", "compute_cost_usd_estimate": 0.0}
    T["create_to_ready"] = round(time.perf_counter() - t, 2)
    rec["sandbox_id"] = sb.id
    t_alive = time.perf_counter()
    try:
        t = time.perf_counter()
        r = sb.exec("bash", "-lc", "base64 -d > job.tgz && mkdir -p job && tar -xzf job.tgz -C job",
                    input=base64.b64encode(bundle(jobs)), timeout=120)
        T["upload"] = round(time.perf_counter() - t, 2)
        if not r.ok:
            raise RuntimeError(f"upload failed: {r.stderr_text[-400:]}")
        t = time.perf_counter()
        r = sb.exec("bash", "-lc", "cd job && uv venv -q .venv && uv pip install -q -p .venv -r requirements.txt", timeout=600)
        T["install_deps"] = round(time.perf_counter() - t, 2)
        if not r.ok:
            raise RuntimeError(f"install failed: {r.stderr_text[-600:]}")
        t = time.perf_counter()
        r = sb.exec("bash", "-lc", f"cd job && .venv/bin/python runner.py {cpu} >/dev/null 2>err.txt; tail -c 400 err.txt >&2; cat out.json",
                    timeout=1500)
        T["play"] = round(time.perf_counter() - t, 2)
        rec["games"] = json.loads(r.stdout_text)
        for g in rec["games"]:
            g["tenki_worker"] = i
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {str(e)[:600]}"
    finally:
        try:
            sb.close()
            rec["teardown"] = "close() returned"
        except Exception as e:
            rec["teardown"] = f"close() raised {type(e).__name__}"
        alive = time.perf_counter() - t_alive + T["create_to_ready"]
        rec["compute_cost_usd_estimate"] = round(alive * (cpu * RATE_VCPU_S + mem / 1024 * RATE_GIB_S), 6)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regimes", default="A=0/0,B=1/0")
    ap.add_argument("--seeds", default="100:140")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--cpu", type=int, default=2)  # workspace limit
    ap.add_argument("--memory-mb", type=int, default=2048)
    ap.add_argument("--out", default=str(REPO / "ufa" / "squad" / "swarm" / "landscape"))
    a = ap.parse_args()
    keys.load(["TENKI_API_KEY"])  # into os.environ for the SDK; never sent to a sandbox
    regimes = {k: dict(zip(("mode", "difficulty"), map(int, v.split("/")))) for k, v in (x.split("=") for x in a.regimes.split(","))}
    jobs = [(c, s, r) for r in regimes.values() for s in seeds_arg(a.seeds) for c in CONFIGS]
    shares = [jobs[i::a.workers] for i in range(a.workers)]
    t = time.perf_counter()
    with ThreadPoolExecutor(a.workers) as pool:
        recs = list(pool.map(lambda x: run_worker(x[0], x[1], a.cpu, a.memory_mb), enumerate(shares)))
    wall = round(time.perf_counter() - t, 2)
    games = [g for r in recs for g in r.get("games", [])]
    od = Path(a.out)
    od.mkdir(parents=True, exist_ok=True)
    for name, reg in regimes.items():
        gs = sorted([g for g in games if g["regime"] == reg], key=lambda g: (g["config"], g["seed"]))
        (od / f"{name}.json").write_text(json.dumps({"regime_name": name, "regime": reg, "games": gs}, separators=(",", ":")))
    run = {"started_utc": datetime.now(timezone.utc).isoformat(), "regimes": regimes, "jobs": len(jobs),
           "games_returned": len(games), "workers": a.workers, "cpu_per_worker": a.cpu, "wall_s": wall,
           "game_seconds_total": round(sum(g["wall_s"] for g in games), 1),
           "compute_cost_usd_estimate": round(sum(r["compute_cost_usd_estimate"] for r in recs), 6),
           "failures": [{"worker": r["worker"], "error": r["error"]} for r in recs if r.get("error")],
           "workers_detail": [{k: v for k, v in r.items() if k != "games"} for r in recs]}
    (od / "tenki_run.json").write_text(json.dumps(run, indent=1))
    print(json.dumps({k: v for k, v in run.items() if k != "workers_detail"}, indent=1))


if __name__ == "__main__":
    main()
