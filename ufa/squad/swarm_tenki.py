"""Tenki-native validation of the frozen swarm experiment: the swarm's population is real, disposable sandboxes.

    python -m ufa.squad.swarm_tenki launch --run v1 --conds B,D,E --trials 10 --first-trial 500

Layout (all on Tenki):
    coordinator sandbox   owns the round loop (the frozen ufa/squad/swarm.run_trial), reads and writes Mitosis,
                          asks JEV, creates and destroys the workers, aggregates results, writes the artifacts
    worker sandboxes 1-4  worker slot k is one sandbox; it plays that slot's games (every trial, every condition,
                          in lockstep) and nothing else. Slot k is destroyed and replaced by a brand-new sandbox
                          exactly when the frozen design retires worker k (every L rounds, staggered), and all
                          four are replaced at the game change.

Workers get no key of any kind: a job is (condition, trial, configuration, seed, game variation). A memoryless
swarm (condition E) keeps its knowledge in a file on its workers' own disks; the coordinator asks the living
workers for it at the start of every round, so when a sandbox is destroyed what it learned is gone. A swarm
with memory (B, D) takes its knowledge from what Mitosis returns, as in the main run.

The coordinator holds TENKI_API_KEY (to create workers), TYPESAFE_API_KEY and the lab Mitosis key + office id.
They are passed in the env of the single command that starts it (never in a file, a command line, a log or
the session env) and die with the sandbox. The local PC only launches, watches and downloads; it plays no game.
Fresh validation seeds; truth (for regret) is the frozen landscape's mean per configuration, from other seeds.
"""
import argparse
import base64
import io
import json
import os
import shlex
import sys
import tarfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RATE_VCPU_S, RATE_GIB_S = 0.000014, 0.0000045   # Tenki starter plan, as in ufa/tenki/remote_episode.py
WORKER_REQS = "gymnasium==1.3.0\nale-py==0.12.1\nnumpy==2.5.3\n"
COORD_REQS = "tenki==1.3.0\ntypesafe-sdk==0.7.2\n"
WORKER_FILES = ["ufa/__init__.py", "ufa/arena/__init__.py", "ufa/arena/env.py", "ufa/arena/extract.py",
                "ufa/arena/representations.py", "ufa/squad/__init__.py", "ufa/squad/landscape.py"]
COORD_FILES = sorted(set(WORKER_FILES + [
    "ufa/arena/keys.py", "ufa/arena/deciders.py", "ufa/arena/questions.py", "ufa/arena/pricing.py",
    "ufa/mitosis/__init__.py", "ufa/mitosis/cortex.py", "ufa/squad/swarm.py", "ufa/squad/swarm_tenki.py",
    "ufa/squad/swarm/landscape/A.json", "ufa/squad/swarm/landscape/B.json"]))
SECRETS = ["TENKI_API_KEY", "TYPESAFE_API_KEY", "MITOSIS_API_KEY", "MITOSIS_OFFICE_ID"]
WORKER_EGRESS = ["pypi.org", "files.pythonhosted.org"]

WORKER_PY = r'''
import json, os, sys
from concurrent.futures import ProcessPoolExecutor
from ufa.squad.landscape import _job
LOCAL = "local_knowledge.json"   # this worker's own observations (memoryless conditions only); dies with the sandbox


def load():
    return json.load(open(LOCAL)) if os.path.exists(LOCAL) else {}


def main():
    if sys.argv[1] == "knowledge":
        print(json.dumps(load()))
        return
    # play <procs> <jobs file> <result file>: runs detached; the result file appears (atomically) when done
    jobs = json.load(open(sys.argv[3]))
    with ProcessPoolExecutor(int(sys.argv[2])) as pool:
        outs = list(pool.map(_job, [(j["config"], j["seed"], j["regime"]) for j in jobs]))
    K = load()
    for j, o in zip(jobs, outs):
        if j["keep_local"]:
            k = K.setdefault(j["key"], {}).setdefault(j["config"], [0, 0.0, 0.0])
            x = o["score_ex_bonus"]
            k[0] += 1; k[1] += x; k[2] += x * x
    json.dump(K, open(LOCAL + ".tmp", "w")); os.replace(LOCAL + ".tmp", LOCAL)
    json.dump(outs, open(sys.argv[4] + ".tmp", "w"), separators=(",", ":")); os.replace(sys.argv[4] + ".tmp", sys.argv[4])


if __name__ == "__main__":
    main()
'''


def tar_bytes(files, extra):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for p in files:
            tar.add(REPO / p, arcname=p)
        for name, data in extra.items():
            data = data.encode() if isinstance(data, str) else data
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def cost(alive_s, cpu, mem):
    return alive_s * (cpu * RATE_VCPU_S + mem / 1024 * RATE_GIB_S)


# ------------------------------------------------------------------ coordinator side (runs inside Tenki)

class TenkiSubstrate:
    """Lockstep over all trials: every trial thread arrives at the same (phase, round) stage, one thread performs the
    stage for everyone (replace due workers + collect local knowledge, or play all games), then all continue."""

    def __init__(self, parties, seeds, land, cpu, mem, procs, out):
        from ufa.squad.swarm import L, W
        self.W, self.L = W, L
        self.seeds, self.land, self.cpu, self.mem, self.procs, self.out = seeds, land, cpu, mem, procs, out
        self.lock = threading.Lock()
        self.barrier = threading.Barrier(parties, action=self._action, timeout=1800)
        self.stage, self.pending, self.results = None, {}, {}
        self.slots = [None] * W                       # current worker sandbox per slot
        self.sandboxes = []                           # every worker sandbox ever created
        self.events, self.retries, self.failures = [], 0, []
        self.games_f = open(out / "games.jsonl", "w")
        self.n_games = 0
        self.t0 = time.time()
        self.bundle = tar_bytes(WORKER_FILES, {"requirements.txt": WORKER_REQS, "worker.py": WORKER_PY})

    # ---- trial-thread API (called from ufa.squad.swarm.run_trial)
    def round_start(self, cond, trial, ph, r, need_local):
        return self._arrive(("start", ph, r), (cond, trial), need_local)

    def play(self, cond, trial, ph, r, plan, keep_local):
        return self._arrive(("play", ph, r), (cond, trial), {"plan": plan, "keep_local": keep_local})

    def _arrive(self, stage, key, req):
        with self.lock:
            if self.stage is None:
                self.stage = stage
            assert self.stage == stage, f"lockstep broken: {stage} vs {self.stage}"
            self.pending[key] = req
        self.barrier.wait()
        with self.lock:
            return self.results.pop((stage, key))

    def _action(self):
        stage, pend = self.stage, self.pending
        self.stage, self.pending = None, {}
        if stage[0] == "start":
            self._start(stage[1], stage[2], pend)
        else:
            self._play(stage[1], stage[2], pend)
        self._progress(stage)

    # ---- workers
    def _new_worker(self, k, ph, r, why):
        from tenki import Sandbox
        rec = {"slot": k, "generation": sum(1 for s in self.sandboxes if s["slot"] == k) + 1, "born": [ph + 1, r],
               "why": why, "games": 0, "jobs_ok": 0, "jobs_failed": 0, "timings_s": {}}
        common = dict(name=f"ufa-swarm-v-w{k}", cpu_cores=self.cpu, memory_mb=self.mem, max_duration=1800,
                      allow_inbound=False, tags=["ufa", "swarm-validation", "worker"],
                      metadata={"slot": str(k), "generation": str(rec["generation"])})
        t = time.perf_counter()
        for attempt in range(20):  # the workspace allows 5 sandboxes at once; a just-closed one can take a moment
            try:
                try:
                    sb = Sandbox.create(allow_domains=WORKER_EGRESS, **common)
                    rec["egress_allowlist"] = WORKER_EGRESS
                except Exception as e:  # this workspace refuses egress policies ("requires a mesh-connected host")
                    rec["egress_allowlist"] = None
                    rec["egress_allowlist_error"] = f"{type(e).__name__}: {str(e)[:160]}"
                    sb = Sandbox.create(**common)
                break
            except Exception as e:
                self.retries += 1
                if attempt == 19:
                    raise
                self.events.append({"t": round(time.time() - self.t0, 1), "event": "create_retry", "slot": k,
                                    "error": f"{type(e).__name__}: {str(e)[:160]}"})
                time.sleep(min(10 * (attempt + 1), 60))
        rec["timings_s"]["create"] = round(time.perf_counter() - t, 2)
        rec["sandbox_id"], rec["t_alive"] = sb.id, time.time()
        t = time.perf_counter()
        r1 = self._retry(sb, "base64 -d > job.tgz && mkdir -p job && tar -xzf job.tgz -C job", base64.b64encode(self.bundle), 120)
        r2 = self._retry(sb, "cd job && { [ -d .venv ] || uv venv -q .venv; } && uv pip install -q -p .venv -r requirements.txt", None, 600)
        if not (r1.ok and r2.ok):
            raise RuntimeError(f"worker setup failed: {(r1.stderr_text + r2.stderr_text)[-400:]}")
        # audit: a new worker must start with no experimental memory at all
        r3 = self._retry(sb, "cd job && ls -a; .venv/bin/python worker.py knowledge; env | cut -d= -f1 | sort | tr '\\n' ' '", None, 60)
        lines = r3.stdout_text.strip().splitlines()
        rec["birth_audit"] = {"files": sorted(x for x in lines[:-2] if x not in (".", "..")),
                              "local_knowledge": json.loads(lines[-2]), "env_names": lines[-1].split()}
        assert rec["birth_audit"]["local_knowledge"] == {}, "a new worker already had local knowledge"
        rec["timings_s"]["setup"] = round(time.perf_counter() - t, 2)
        rec["_sb"] = sb
        self.sandboxes.append(rec)
        return rec

    def _retire(self, rec, why):
        t = time.time()
        try:
            rec["_sb"].close()
            rec["teardown"] = "close() returned"
        except Exception as e:
            rec["teardown"] = f"close() raised {type(e).__name__}"
        rec["retired"], rec["retire_why"] = [self._stage_ph + 1, self._stage_r] if why != "end" else "end", why
        rec["alive_s"] = round(t - rec["t_alive"], 1)
        rec["cost_usd_estimate"] = round(cost(rec["alive_s"], self.cpu, self.mem), 6)

    def _start(self, ph, r, pend):
        self._stage_ph, self._stage_r = ph, r
        due = list(range(self.W)) if r == 0 else [k for k in range(self.W) if (r + k) % self.L == 0]
        why = ("first population" if ph == 0 else "game changed: whole population replaced") if r == 0 else "lifetime over"
        for k in due:
            if self.slots[k]:
                self._retire(self.slots[k], why)
        with ThreadPoolExecutor(len(due) or 1) as pool:
            new = list(pool.map(lambda k: self._new_worker(k, ph, r, why), due))
        for k, rec in zip(due, new):
            self.slots[k] = rec
        if due:
            self.events.append({"t": round(time.time() - self.t0, 1), "event": "replaced", "phase": ph + 1, "round": r,
                                "slots": due, "why": why, "sandboxes": [x["sandbox_id"] for x in new]})
        need = [key for key, v in pend.items() if v]
        known = [{} for _ in range(self.W)]
        if need:  # ask every living worker what it knows
            def ask(k):
                res = self._exec(k, "cd job && .venv/bin/python worker.py knowledge", None, 120)
                return json.loads(res)
            known = list(ThreadPoolExecutor(self.W).map(ask, range(self.W)))
        for key, v in pend.items():
            self.results[(("start", ph, r), key)] = [known[k].get(f"{key[0]}|{key[1]}", {}) for k in range(self.W)] if v else None

    WAITS = (3, 6, 12, 20, 30, 45)

    def _retry(self, sb, cmd, data, timeout, slot=None):
        """Only for idempotent commands: transient Tenki errors (502, stream resets) are retried with backoff."""
        for attempt in range(len(self.WAITS) + 1):
            try:
                res = sb.exec("bash", "-lc", cmd, input=data, timeout=timeout)
                if res.ok:
                    return res
                raise RuntimeError(f"exit {res.exit_code}: {res.stderr_text[-300:]}")
            except Exception as e:
                self.retries += 1
                self.failures.append({"slot": slot, "sandbox_id": sb.id, "attempt": attempt + 1,
                                      "stage": [getattr(self, "_stage_ph", 0) + 1, getattr(self, "_stage_r", 0)],
                                      "error": f"{type(e).__name__}: {str(e)[:200]}"})
                if attempt == len(self.WAITS):
                    raise
                time.sleep(self.WAITS[attempt])

    def _exec(self, k, cmd, data, timeout):
        return self._retry(self.slots[k]["_sb"], cmd, data, timeout, slot=k).stdout_text

    def _play(self, ph, r, pend):
        reg = self.land[ph]["regime"]
        by_slot = {k: [] for k in range(self.W)}
        for (cond, trial), req in pend.items():
            for i, (k, c, s) in enumerate(req["plan"]):
                by_slot[k].append({"key": f"{cond}|{trial}", "cond": cond, "trial": trial, "i": i, "config": c, "seed": s,
                                   "regime": reg, "keep_local": req["keep_local"]})

        def run(k):
            jobs = by_slot[k]
            t = time.perf_counter()
            i = f"p{ph + 1}r{r}"  # the batch runs detached on the worker; short polls collect it (every call idempotent)
            self._exec(k, f"cd job && cat > jobs_{i}.json", json.dumps(jobs), 120)
            self._exec(k, f"cd job || exit 1; [ -e started_{i} ] || {{ touch started_{i}; setsid nohup .venv/bin/python worker.py "
                          f"play {self.procs} jobs_{i}.json res_{i}.json > /dev/null 2> err_{i}.txt < /dev/null & }}; echo ok", None, 60)
            while True:
                time.sleep(3)
                o = self._exec(k, f"cd job; if [ -e res_{i}.json ]; then cat res_{i}.json; elif pgrep -f '[w]orker.py play [0-9]* jobs_{i}' "
                                  f">/dev/null; then echo RUNNING; else echo DEAD; tail -c 300 err_{i}.txt; fi", None, 120)
                if o.startswith("RUNNING"):
                    if time.perf_counter() - t > 1500:
                        raise RuntimeError(f"slot {k} batch {i} still running after 1500 s")
                    continue
                if o.startswith("DEAD"):
                    raise RuntimeError(f"slot {k} batch {i} died: {o[-300:]}")
                outs = json.loads(o)
                break
            rec = self.slots[k]
            rec["games"] += len(outs)
            rec["jobs_ok"] += 1
            rec.setdefault("play_s", []).append(round(time.perf_counter() - t, 1))
            return jobs, outs, rec
        res = list(ThreadPoolExecutor(self.W).map(run, range(self.W)))
        got = {key: [None] * len(req["plan"]) for key, req in pend.items()}
        for jobs, outs, rec in res:
            for j, o in zip(jobs, outs):
                assert (o["config"], o["seed"]) == (j["config"], j["seed"])
                got[(j["cond"], j["trial"])][j["i"]] = o["score_ex_bonus"]
                self.games_f.write(json.dumps({"cond": j["cond"], "trial": j["trial"], "phase": ph + 1, "round": r,
                                               "slot": rec["slot"], "generation": rec["generation"],
                                               "sandbox_id": rec["sandbox_id"], **o}, separators=(",", ":")) + "\n")
                self.n_games += 1
        self.games_f.flush()
        for key in pend:
            self.results[(("play", ph, r), key)] = got[key]

    def _progress(self, stage):
        (self.out / "progress.json").write_text(json.dumps({
            "stage": list(stage), "elapsed_s": round(time.time() - self.t0, 1), "games": self.n_games,
            "sandboxes_created": len(self.sandboxes), "retries": self.retries, "failures": len(self.failures)}))

    def close(self):
        for rec in self.slots:
            if rec and "retired" not in rec:
                self._retire(rec, "end")
        self.games_f.close()
        return {"worker_sandboxes": [{k: v for k, v in s.items() if not k.startswith("_") and k != "t_alive"} for s in self.sandboxes],
                "events": self.events, "retries": self.retries, "failures": self.failures, "games": self.n_games}


def coordinate(a):
    from ufa.mitosis.cortex import Cortex
    from ufa.squad import swarm

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    land = swarm.load_landscape()
    seeds = {ph: list(range(*map(int, s.split(":")))) for ph, s in enumerate(a.seeds.split(","))}
    conds = a.conds.split(",")
    cortex = Cortex()
    for c in conds:  # isolation: every memory condition's feed must start empty
        if swarm.CONDS[c][1]:
            feed = f"swarm_{a.run}_{c}".lower()
            cortex.ensure_feed(feed)
            pre = cortex.answer(f"swarm {a.run} {c} trial finding", limit=40, integration_id=feed, include_raw=True)
            if pre.get("results"):
                raise SystemExit(f"feed {feed} is not empty: pick a new --run id")
    jobs = [(c, t) for t in range(a.first_trial, a.first_trial + a.trials) for c in conds]
    sub = TenkiSubstrate(len(jobs), seeds, land, a.cpu, a.memory_mb, a.procs, out)
    t0 = time.time()
    errors = []

    def one(job):
        c, t = job
        try:
            ts = time.time()
            res = swarm.run_trial(c, t, land, a.run, cortex, a.commit, sub=sub)
            res["wall_s"] = round(time.time() - ts, 1)
            (out / f"{c}_t{t:03d}.json").write_text(json.dumps(res, separators=(",", ":")))
        except Exception as e:
            errors.append(f"{c} t{t}: {type(e).__name__}: {str(e)[:300]}")
            sub.barrier.abort()
            raise

    try:
        with ThreadPoolExecutor(len(jobs)) as pool:
            list(pool.map(one, jobs))
    finally:
        topo = sub.close()
        workers = topo["worker_sandboxes"]
        meta = {"run": a.run, "conds": conds, "trials": a.trials, "first_trial": a.first_trial,
                "W": swarm.W, "R": swarm.R, "L": swarm.L, "commit": a.commit, "validation_seeds": a.seeds,
                "landscape_truth_from": {k: {kk: v[kk] for kk in ("name", "regime", "file", "sha256", "best")} for k, v in land.items()},
                "wall_s": round(time.time() - t0, 1), "errors": errors,
                "coordinator": {"python": sys.version.split()[0], "host": os.uname().nodename if hasattr(os, "uname") else None,
                                "env_names_seen": sorted(k for k in os.environ if k in SECRETS)},
                "cortex_calls": len(cortex.calls), "cortex_http_errors": sum(1 for c in cortex.calls if c[1] >= 400),
                "tenki": {"worker_sandboxes_created": len(workers),
                          "generations_per_slot": {k: sum(1 for w in workers if w["slot"] == k) for k in range(swarm.W)},
                          "planned_replacements": sum(1 for w in workers if w["generation"] > 1),
                          "games": topo["games"], "retries": topo["retries"], "failures": topo["failures"],
                          "worker_cost_usd_estimate": round(sum(w.get("cost_usd_estimate", 0) for w in workers), 6),
                          "events": topo["events"], "workers": workers}}
        (out / "meta.json").write_text(json.dumps(meta, indent=1))
        (out / "DONE").write_text("ok" if not errors else "errors")


# ------------------------------------------------------------------ launcher side (runs on the PC)

def launch(a):
    from tenki import Sandbox

    from ufa.arena import keys

    vals = keys.load(SECRETS)  # values stay in memory; passed only in the env of the one start command
    secret_env = dict(zip(SECRETS, vals))
    commit = os.popen(f'git -C "{REPO}" rev-parse --short HEAD').read().strip()
    local = REPO / "ufa" / "squad" / "swarm" / "runs" / a.run
    if local.exists() and any(local.iterdir()):
        raise SystemExit(f"{local} exists: pick a new --run id")
    local.mkdir(parents=True, exist_ok=True)
    rec = {"started_utc": datetime.now(timezone.utc).isoformat(), "commit": commit, "timings_s": {}}
    t = time.perf_counter()
    sb = Sandbox.create(name="ufa-swarm-v-coordinator", cpu_cores=2, memory_mb=2048, max_duration=a.max_duration,
                        allow_inbound=False, tags=["ufa", "swarm-validation", "coordinator"])
    rec["coordinator_sandbox_id"] = sb.id
    t_alive = time.time()
    rec["timings_s"]["create"] = round(time.perf_counter() - t, 2)
    log = open(local / "launcher.log", "a")

    def say(msg):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()
    try:
        r = sb.exec("bash", "-lc", "base64 -d > job.tgz && mkdir -p job && tar -xzf job.tgz -C job",
                    input=base64.b64encode(tar_bytes(COORD_FILES, {"requirements.txt": COORD_REQS})), timeout=120)
        assert r.ok, r.stderr_text[-400:]
        r = sb.exec("bash", "-lc", "cd job && uv venv -q .venv && uv pip install -q -p .venv -r requirements.txt", timeout=600)
        assert r.ok, r.stderr_text[-600:]
        args = (f"--run {a.run} --conds {a.conds} --trials {a.trials} --first-trial {a.first_trial} --seeds {a.seeds} "
                f"--commit {commit} --procs {a.procs} --out out")
        # not `cd && cmd &`: that backgrounds a subshell holding this exec's stdout open until the run ends
        start = ("cd job || exit 1; setsid nohup .venv/bin/python -m ufa.squad.swarm_tenki coordinate " + args +
                 " > coord.log 2>&1 < /dev/null & echo started")
        r = sb.exec("bash", "-lc", start, env=secret_env, timeout=60)
        assert r.ok and "started" in r.stdout_text, f"start failed: exit {getattr(r, 'exit_code', None)} {r.stdout_text[-300:]} {r.stderr_text[-300:]}"
        say(f"coordinator {sb.id} started: {args}")
        last, misses = None, 0
        while True:
            time.sleep(30)
            try:  # a watch call can fail transiently; that must never end the run
                r = sb.exec("bash", "-lc", "cd job && cat out/progress.json 2>/dev/null; echo; ls out/DONE 2>/dev/null; "
                            "pgrep -f '[s]warm_tenki coordinate' >/dev/null && echo alive || echo dead", timeout=60)
                misses = 0
            except Exception as e:
                misses += 1
                rec["watch_errors"] = rec.get("watch_errors", 0) + 1
                say(f"watch call failed ({type(e).__name__}), {misses} in a row")
                if misses < 30:
                    continue
                raise
            s = r.stdout_text.strip()
            if s != last:
                say(s.replace("\n", " | "))
                last = s
            if "out/DONE" in s or s.endswith("dead"):
                break
        def retry(cmd, timeout):
            for i in range(5):
                try:
                    return sb.exec("bash", "-lc", cmd, timeout=timeout)
                except Exception:
                    if i == 4:
                        raise
                    time.sleep(10)
        r = retry("cd job && tail -c 3000 coord.log", 60)
        (local / "coordinator_log_tail.txt").write_text(r.stdout_text)
        r = retry("cd job/out && tar -czf - . | base64 -w0", 600)
        with tarfile.open(fileobj=io.BytesIO(base64.b64decode(r.stdout_text)), mode="r:gz") as tar:
            tar.extractall(local, filter="data")
        say(f"downloaded results to {local}")
    finally:
        try:
            sb.close()
            rec["teardown"] = "close() returned"
        except Exception as e:
            rec["teardown"] = f"close() raised {type(e).__name__}"
        rec["coordinator_alive_s"] = round(time.time() - t_alive, 1)
        rec["coordinator_cost_usd_estimate"] = round(cost(rec["coordinator_alive_s"], 2, 2048), 6)
        (local / "launcher.json").write_text(json.dumps(rec, indent=1))
        say(json.dumps(rec))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("launch", "coordinate"):
        p = sub.add_parser(name)
        p.add_argument("--run", required=True)
        p.add_argument("--conds", default="B,D,E")
        p.add_argument("--trials", type=int, default=10)
        p.add_argument("--first-trial", type=int, default=500)
        p.add_argument("--seeds", default="7000:7040,7000:7040", help="fresh validation seeds, phase 1 and phase 2")
        p.add_argument("--procs", type=int, default=2)
        if name == "launch":
            p.add_argument("--max-duration", type=int, default=7200)
        else:
            p.add_argument("--commit", default=None)
            p.add_argument("--cpu", type=int, default=2)
            p.add_argument("--memory-mb", type=int, default=2048)
            p.add_argument("--out", default="out")
    a = ap.parse_args()
    (launch if a.cmd == "launch" else coordinate)(a)


if __name__ == "__main__":
    main()
