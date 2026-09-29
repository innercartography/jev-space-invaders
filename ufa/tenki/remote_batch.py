"""Run a block of arena games inside Tenki sandboxes: seeds are sharded across sandboxes, and each
sandbox plays its arms x seeds with its own bounded concurrency (ufa.local_batch inside the VM).

    python -m ufa.tenki.remote_batch --config ufa/experiments/exp006_tournament.json --arms ref,k2 \
        --seeds-file ufa/experiments/seeds_dev.json --seed-range 20:50 --sandboxes 5 --inner-parallel 4

Same least-privilege rules as remote_episode: the sandbox gets the arena code, the batch runner,
one config and requirements-worker.txt; only JEV/scripted/random arms; the only secret is
TYPESAFE_API_KEY, passed in the env of the single run command; inbound networking off; hard
max_duration. Traces come home into ufa/traces/<experiment>/..., exactly where a local run puts
them, with compute_host showing the sandbox. A per-sandbox record goes to traces-remote/tenki_batches.
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
from ufa.arena import run as run_mod
from ufa.tenki.remote_episode import RATE_GIB_S, RATE_VCPU_S

REPO = Path(__file__).resolve().parents[2]
ALLOWED = {"jev_basic", "scripted", "random"}


def bundle(config_path):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for p in [REPO / "ufa" / "__init__.py", REPO / "ufa" / "local_batch.py", *sorted((REPO / "ufa" / "arena").glob("*.py")),
                  REPO / "requirements-worker.txt"]:
            tar.add(p, arcname=str(p.relative_to(REPO)))
        tar.add(config_path, arcname="experiment.json")
        commit = (run_mod.source_commit() or "unknown").encode()  # the sandbox has no git; run.py reads this file
        info = tarfile.TarInfo(".source_commit")
        info.size = len(commit)
        tar.addfile(info, io.BytesIO(commit))
    return buf.getvalue()


def run_sandbox(i, cfg, payload, arms, seeds, inner, secret_env, secret_values, cpu, mem, max_s):
    from tenki import Sandbox

    rec = {"sandbox": i, "arms": arms, "seeds": seeds, "inner_parallel": inner, "timings_s": {}}
    T = rec["timings_s"]
    t = time.perf_counter()
    sb = Sandbox.create(name=f"ufa-{cfg['experiment_id']}-b{i}".replace("_", "-")[:60], cpu_cores=cpu, memory_mb=mem,
                        max_duration=max_s, allow_inbound=False, tags=["ufa", "arena", "batch"],
                        metadata={"experiment": cfg["experiment_id"], "block": str(i)})
    T["create_to_ready"] = round(time.perf_counter() - t, 2)
    rec["sandbox_id"] = sb.id
    t_alive = time.perf_counter()
    try:
        r = sb.exec("bash", "-lc", "base64 -d > job.tgz && mkdir -p job && tar -xzf job.tgz -C job",
                    input=base64.b64encode(payload), timeout=120)
        if not r.ok:
            raise RuntimeError(f"upload failed: {r.stderr_text[-400:]}")
        t = time.perf_counter()
        r = sb.exec("bash", "-lc", "cd job && uv venv -q .venv && uv pip install -q -p .venv -r requirements-worker.txt", timeout=600)
        T["install_deps"] = round(time.perf_counter() - t, 2)
        if not r.ok:
            raise RuntimeError(f"install failed: {r.stderr_text[-600:]}")
        cmd = (f"cd job && .venv/bin/python -m ufa.local_batch --config experiment.json --arms {','.join(arms)} "
               f"--seeds {','.join(map(str, seeds))} --reps 0 --parallel {inner} --out traces > batch.log 2>&1; tail -c 400 batch.log")
        t = time.perf_counter()
        r = sb.exec("bash", "-lc", cmd, env=secret_env, timeout=max_s - 180)
        T["games"] = round(time.perf_counter() - t, 2)
        rec["batch_tail"] = r.stdout_text[-400:]
        t = time.perf_counter()
        r = sb.exec("bash", "-lc", "cd job && tar -czf - traces | base64 -w0", timeout=600)
        blob = base64.b64decode(r.stdout_text)
        T["download"] = round(time.perf_counter() - t, 2)
        for s in secret_values:
            if s.encode() in blob:
                raise RuntimeError("secret found in returned traces; not saving")
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
            members = [m for m in tar.getmembers() if m.name.startswith("traces/") and "local_batch" not in m.name]
            for m in members:
                m.name = m.name[len("traces/"):]
            tar.extractall(REPO / "ufa" / "traces", members=members, filter="data")
        rec["episodes_returned"] = sum(1 for m in members if m.name.endswith("episode.json"))
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {str(e)[:600]}"
    finally:
        try:
            sb.close()
            rec["teardown"] = "close() returned"
        except Exception as e:
            rec["teardown"] = f"close() raised {type(e).__name__}"
        alive = time.perf_counter() - t_alive + T["create_to_ready"]
        T["billable_estimate"] = round(alive, 2)
        rec["compute_cost_usd_estimate"] = round(alive * (cpu * RATE_VCPU_S + mem / 1024 * RATE_GIB_S), 6)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--arms", required=True)
    ap.add_argument("--seeds")
    ap.add_argument("--seeds-file")
    ap.add_argument("--seed-range", default=":")
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--sandboxes", type=int, default=5)
    ap.add_argument("--inner-parallel", type=int, default=4)
    ap.add_argument("--cpu", type=int, default=2)  # workspace limit (Starter): 2 cores
    ap.add_argument("--memory-mb", type=int, default=2048)
    ap.add_argument("--max-duration-s", type=int, default=3600)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    arms = args.arms.split(",")
    by = {a["name"]: a for a in cfg["arms"]}
    if any(by[a]["policy"] not in ALLOWED for a in arms):
        raise SystemExit("only JEV, scripted or random arms run on Tenki; LLM keys never leave the controller")
    if args.seeds_file:
        if "holdout" in Path(args.seeds_file).name and not args.holdout:
            raise SystemExit("holdout seeds need --holdout")
        lo, _, hi = args.seed_range.partition(":")
        seeds = json.loads(Path(args.seeds_file).read_text())["seeds"][int(lo) if lo else None:int(hi) if hi else None]
    else:
        seeds = [int(s) for s in args.seeds.split(",")]
    names = sorted({k for a in arms for k in {"jev_basic": ["TYPESAFE_API_KEY"]}.get(by[a]["policy"], [])})
    values = keys.load(["TENKI_API_KEY"] + names)
    secret_env = dict(zip(names, values[1:]))
    payload = bundle(args.config)
    blocks = [seeds[i::args.sandboxes] for i in range(args.sandboxes)]
    t = time.perf_counter()
    with ThreadPoolExecutor(args.sandboxes) as pool:
        recs = list(pool.map(lambda ib: run_sandbox(ib[0], cfg, payload, arms, ib[1], args.inner_parallel, secret_env,
                                                     values, args.cpu, args.memory_mb, args.max_duration_s),
                             enumerate(blocks)))
    out = {"started_utc": datetime.now(timezone.utc).isoformat(), "experiment_id": cfg["experiment_id"], "arms": arms,
           "n_seeds": len(seeds), "sandboxes": args.sandboxes, "inner_parallel": args.inner_parallel,
           "games_expected": len(arms) * len(seeds), "games_returned": sum(r.get("episodes_returned", 0) for r in recs),
           "wall_s": round(time.perf_counter() - t, 2),
           "compute_cost_usd_estimate": round(sum(r["compute_cost_usd_estimate"] for r in recs), 6), "blocks": recs}
    od = REPO / "ufa" / "traces-remote" / "tenki_batches"
    od.mkdir(parents=True, exist_ok=True)
    text = json.dumps(out, indent=1, default=str)
    for s in values:
        if s in text:
            raise SystemExit("secret value reached the batch record; not writing")
    (od / f"{cfg['experiment_id']}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json").write_text(text)
    print(json.dumps({k: v for k, v in out.items() if k != "blocks"}, indent=1))


if __name__ == "__main__":
    main()
