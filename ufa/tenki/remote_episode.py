"""Run ONE arena episode inside a disposable Tenki sandbox, bring the trace home, destroy the sandbox.

    python -m ufa.tenki.remote_episode --config ufa/experiments/exp001_first_light.json \
        --arm jev_basic__threat --seed 1

The DigitalOcean host stays the controller; the sandbox is throwaway compute.
Least privilege for the worker:
  - it receives only the arena code, one experiment config and requirements-worker.txt
    (no .env, no other project files, no git credentials, no host access);
  - only JEV arms may run remotely, and the only secret sent is TYPESAFE_API_KEY, passed
    in the env of the single run command (not the session env; Tenki's docs warn against
    long-lived credentials in session env). Upgrade path: a dedicated, revocable JEV key
    for workers, delivered with Tenki's runtime secret files;
  - inbound networking is off; an outbound allowlist is requested when the workspace supports it;
  - a hard max_duration caps the cost if cleanup ever fails.
Timings, sandbox spec, estimated compute cost and teardown status go to tenki_run.json
next to the downloaded trace.
"""
import argparse
import base64
import io
import json
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

from ufa.arena import keys, policies

REPO = Path(__file__).resolve().parents[2]
EGRESS = ["pypi.org", "files.pythonhosted.org", "api.typesafe.ai"]
# Starter plan rates, tenki.cloud/docs/pricing.md (checked 2026-09-27)
RATE_VCPU_S = 0.000014
RATE_GIB_S = 0.0000045


def bundle(config_path):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for p in [REPO / "ufa" / "__init__.py", *sorted((REPO / "ufa" / "arena").glob("*.py")),
                  REPO / "requirements-worker.txt", REPO / ".source_commit"]:
            if p.exists():
                tar.add(p, arcname=str(p.relative_to(REPO)))
        tar.add(config_path, arcname="experiment.json")
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--max-steps", type=int)
    ap.add_argument("--rep", type=int, default=0)
    ap.add_argument("--cpu", type=int, default=2)
    ap.add_argument("--memory-mb", type=int, default=2048)
    ap.add_argument("--max-duration-s", type=int, default=1800)
    ap.add_argument("--out", default=str(REPO / "ufa" / "traces-remote" / "tenki"))
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    arm = next(a for a in cfg["arms"] if a["name"] == args.arm)
    if arm["policy"] not in ("jev_basic", "random"):
        raise SystemExit("only JEV (or random) arms run on Tenki workers; LLM keys never leave the controller")
    secret_values = keys.load(["TENKI_API_KEY"] + policies.SECRETS[arm["policy"]])
    run_env = {k: v for k, v in zip(["TENKI_API_KEY"] + policies.SECRETS[arm["policy"]], secret_values) if k != "TENKI_API_KEY"}

    from tenki import Sandbox

    rec = {"started_at": datetime.now(timezone.utc).isoformat(), "experiment_id": cfg["experiment_id"],
           "arm": args.arm, "seed": args.seed, "rep": args.rep, "games_in_sandbox": 1,
           "spec": {"cpu_cores": args.cpu, "memory_mb": args.memory_mb, "max_duration_s": args.max_duration_s,
                    "allow_inbound": False}, "timings_s": {}}
    T = rec["timings_s"]
    payload = bundle(args.config)
    rec["bundle_bytes"] = len(payload)
    name = f"ufa-{cfg['experiment_id']}-{args.arm}-s{args.seed}-r{args.rep}".replace("_", "-")[:60]
    common = dict(name=name, cpu_cores=args.cpu, memory_mb=args.memory_mb, max_duration=args.max_duration_s,
                  allow_inbound=False, tags=["ufa", "arena"],
                  metadata={"experiment": cfg["experiment_id"], "arm": args.arm, "seed": str(args.seed),
                            "rep": str(args.rep)})

    t = time.perf_counter()
    try:
        sb = Sandbox.create(allow_domains=EGRESS, **common)
        rec["egress_allowlist"] = EGRESS
    except Exception as e:  # workspace may not have egress policies enabled
        rec["egress_allowlist"] = None
        rec["egress_allowlist_error"] = f"{type(e).__name__}: {str(e)[:200]}"
        t = time.perf_counter()
        sb = Sandbox.create(**common)
    T["create_to_ready"] = round(time.perf_counter() - t, 2)
    rec["sandbox_id"] = sb.id
    t_alive = time.perf_counter()
    try:
        t = time.perf_counter()
        r = sb.exec("bash", "-lc", "base64 -d > job.tgz && mkdir -p job && tar -xzf job.tgz -C job && ls job",
                    input=base64.b64encode(payload), timeout=120)
        T["upload"] = round(time.perf_counter() - t, 2)
        if not r.ok:
            raise RuntimeError(f"upload failed: {r.stderr_text[-500:]}")

        t = time.perf_counter()
        r = sb.exec("bash", "-lc", "cd job && uv venv -q .venv && uv pip install -q -p .venv -r requirements-worker.txt && .venv/bin/python -c 'import ale_py, typesafe_sdk; print(ale_py.__version__)'",
                    timeout=600)
        T["install_deps"] = round(time.perf_counter() - t, 2)
        if not r.ok:
            raise RuntimeError(f"install failed: {r.stderr_text[-800:]}")

        cmd = f"cd job && .venv/bin/python -m ufa.arena.run --config experiment.json --arms {args.arm} --seeds {args.seed} --reps {args.rep} --out traces"
        if args.max_steps:
            cmd += f" --max-steps {args.max_steps}"
        t = time.perf_counter()
        r = sb.exec("bash", "-lc", cmd, env=run_env, timeout=args.max_duration_s - 120)
        T["episode"] = round(time.perf_counter() - t, 2)
        rec["worker_stdout_tail"] = r.stdout_text[-600:]
        if not r.ok:
            raise RuntimeError(f"episode failed: {r.stderr_text[-800:]}")

        t = time.perf_counter()
        r = sb.exec("bash", "-lc", "cd job && tar -czf - traces | base64 -w0", timeout=300)
        blob = base64.b64decode(r.stdout_text)
        T["download"] = round(time.perf_counter() - t, 2)
        rec["trace_tgz_bytes"] = len(blob)
        for s in secret_values:
            if s.encode() in blob:
                raise RuntimeError("secret found in returned traces; not saving")
        out = Path(args.out) / sb.id
        out.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
            tar.extractall(out, filter="data")
        rec["local_trace_root"] = str(out)
        eps = list(out.glob("traces/*/*/seed*/episode.json"))
        rec["episode_summary"] = json.loads(eps[0].read_text())["summary"] if eps else None
        try:
            m = sb.metrics()
            rec["metrics"] = json.loads(json.dumps(m, default=lambda o: getattr(o, "__dict__", str(o))))
        except Exception as e:
            rec["metrics"] = f"unavailable: {type(e).__name__}"
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {str(e)[:800]}"
    finally:
        t = time.perf_counter()
        try:
            sb.close()
            rec["teardown"] = "close() returned"
        except Exception as e:
            rec["teardown"] = f"close() raised {type(e).__name__}: {str(e)[:200]}"
        T["teardown"] = round(time.perf_counter() - t, 2)
        alive = time.perf_counter() - t_alive + T["create_to_ready"]
        T["billable_estimate"] = round(alive, 2)
        rec["compute_cost_usd_estimate"] = round(alive * (args.cpu * RATE_VCPU_S + args.memory_mb / 1024 * RATE_GIB_S), 6)
        try:
            from tenki import Client

            with Client() as c:
                rec["state_after_close"] = str(c.get(sb.id).state)
        except Exception as e:
            rec["state_after_close"] = f"lookup: {type(e).__name__}: {str(e)[:200]}"

    out = Path(args.out) / rec.get("sandbox_id", "failed")
    out.mkdir(parents=True, exist_ok=True)
    text = json.dumps(rec, indent=2, default=str)
    for s in secret_values:
        if s in text:
            raise SystemExit("secret value reached tenki_run.json; not writing")
    (out / "tenki_run.json").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
