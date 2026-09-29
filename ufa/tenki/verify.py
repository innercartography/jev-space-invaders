"""Clean-room replay verification in Tenki sandboxes: re-derive every recorded score from seed + actions.

    python -m ufa.tenki.verify --replays replays.json --shards 3 --out ufa/traces-remote/verify

Each shard is a fresh Ubuntu sandbox that receives only the environment code, the verifier, pinned
emulator dependencies and its share of the replay file. No API key of any kind is sent: the check
needs no model. The sandbox is destroyed afterwards. Shard reports are merged into one
verify_<utc>.json with per-game results, sandbox ids, timings and an estimated compute cost.
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
from ufa.tenki.remote_episode import RATE_GIB_S, RATE_VCPU_S

REPO = Path(__file__).resolve().parents[2]
REQS = "gymnasium==1.3.0\nale-py==0.12.1\nnumpy==2.5.3\n"


def bundle(games):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for p in [REPO / "ufa" / "__init__.py", REPO / "ufa" / "arena" / "__init__.py", REPO / "ufa" / "arena" / "env.py",
                  REPO / "ufa" / "verify_replay.py"]:
            tar.add(p, arcname=str(p.relative_to(REPO)))
        for name, data in (("requirements-verify.txt", REQS.encode()),
                           ("replays.json", json.dumps({"format": "ufa-replay-1", "games": games}).encode())):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def run_shard(i, games, cpu, mem):
    from tenki import Sandbox

    rec = {"shard": i, "games": len(games), "timings_s": {}}
    T = rec["timings_s"]
    t = time.perf_counter()
    sb = Sandbox.create(name=f"ufa-verify-{i}", cpu_cores=cpu, memory_mb=mem, max_duration=1800,
                        allow_inbound=False, tags=["ufa", "verify"], metadata={"shard": str(i)})
    T["create_to_ready"] = round(time.perf_counter() - t, 2)
    rec["sandbox_id"] = sb.id
    t_alive = time.perf_counter()
    try:
        t = time.perf_counter()
        r = sb.exec("bash", "-lc", "base64 -d > job.tgz && mkdir -p job && tar -xzf job.tgz -C job",
                    input=base64.b64encode(bundle(games)), timeout=120)
        T["upload"] = round(time.perf_counter() - t, 2)
        if not r.ok:
            raise RuntimeError(f"upload failed: {r.stderr_text[-400:]}")
        t = time.perf_counter()
        r = sb.exec("bash", "-lc", "cd job && uv venv -q .venv && uv pip install -q -p .venv -r requirements-verify.txt", timeout=600)
        T["install_deps"] = round(time.perf_counter() - t, 2)
        if not r.ok:
            raise RuntimeError(f"install failed: {r.stderr_text[-600:]}")
        t = time.perf_counter()
        r = sb.exec("bash", "-lc", "cd job && .venv/bin/python -m ufa.verify_replay check replays.json --out report.json >/dev/null 2>&1; cat report.json",
                    timeout=1500)
        T["verify"] = round(time.perf_counter() - t, 2)
        rec["report"] = json.loads(r.stdout_text)
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
    ap.add_argument("--replays", required=True)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--cpu", type=int, default=2)
    ap.add_argument("--memory-mb", type=int, default=2048)
    ap.add_argument("--out", default=str(REPO / "ufa" / "traces-remote" / "verify"))
    args = ap.parse_args()
    keys.load(["TENKI_API_KEY"])  # into os.environ for the SDK; never sent to a sandbox
    games = json.loads(Path(args.replays).read_text())["games"]
    shards = [games[i::args.shards] for i in range(args.shards)]
    t = time.perf_counter()
    with ThreadPoolExecutor(args.shards) as pool:
        recs = list(pool.map(lambda a: run_shard(a[0], a[1], args.cpu, args.memory_mb), enumerate(shards)))
    results = [g for r in recs for g in ((r.get("report") or {}).get("results") or [])]
    out = {"started_utc": datetime.now(timezone.utc).isoformat(), "replays": args.replays, "games": len(games),
           "verified": len(results), "matched": sum(g["ok"] for g in results),
           "mismatched": [g for g in results if not g["ok"]],
           "wall_s": round(time.perf_counter() - t, 2),
           "compute_cost_usd_estimate": round(sum(r["compute_cost_usd_estimate"] for r in recs), 6),
           "shards": [{k: v for k, v in r.items() if k != "report"} |
                      {"platform": (r.get("report") or {}).get("platform"), "matched": (r.get("report") or {}).get("matched")}
                      for r in recs],
           "results": results}
    od = Path(args.out)
    od.mkdir(parents=True, exist_ok=True)
    f = od / f"verify_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    f.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k not in ("results",)}, indent=1))
    print(f"-> {f}")


if __name__ == "__main__":
    main()
