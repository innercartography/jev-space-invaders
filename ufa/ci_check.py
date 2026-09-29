"""CI gate: does results.json agree with the replays, and did every replay match?

    python -m ufa.ci_check --results results.json --replays replays/holdout.json [--report verify_report.json]

Checks, all from files in the repo (no model, no key):
  1. every run in results.json (decider and baseline) has a replay with the same episode, seed, score and steps;
  2. the judges' consistency rules hold per run: p95 >= p50 latency, model calls <= decisions, cost >= 0,
     served model recorded;
  3. with --report (from `ufa.verify_replay check` or `ufa.tenki.verify`): every replayed game matched.
Prints a markdown summary (append it to $GITHUB_STEP_SUMMARY) and exits 1 on any failure.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results.json")
    ap.add_argument("--replays", nargs="+", default=["replays/holdout.json"])
    ap.add_argument("--report", help="verify report JSON (local check or Tenki merge)")
    a = ap.parse_args()

    res = json.loads(Path(a.results).read_text())
    games = {g["episode_id"]: g for f in a.replays for g in json.loads(Path(f).read_text())["games"]}
    runs = [("decider", r) for r in res.get("runs", [])] + [("baseline", r) for r in (res.get("baseline") or {}).get("runs", [])]
    problems = []
    for role, r in runs:
        eid = r.get("episode_id")
        g = games.get(eid)
        if g is None:
            problems.append(f"{role} {eid}: no replay")
            continue
        exp = g["expected"]
        if g["seed"] != r["seed"] or exp["score"] != r["score"] or exp["steps"] != r.get("steps", exp["steps"]):
            problems.append(f"{role} {eid}: results.json {r['score']}/{r.get('steps')} vs replay {exp['score']}/{exp['steps']}")
        p50, p95 = r.get("latency_ms_p50"), r.get("latency_ms_p95")
        if p50 is not None and p95 is not None and p95 < p50:
            problems.append(f"{role} {eid}: p95 < p50")
        if (r.get("model_calls") or 0) > r.get("decisions", r.get("steps", 0)):
            problems.append(f"{role} {eid}: more model calls than decisions")
        if (r.get("cost_usd") or 0) < 0:
            problems.append(f"{role} {eid}: negative cost")
        if not r.get("served_model"):
            problems.append(f"{role} {eid}: served_model missing")
    verified = None
    if a.report:
        rep = json.loads(Path(a.report).read_text())
        verified = (rep.get("matched"), rep.get("games"))
        if rep.get("matched") != rep.get("games"):
            problems.append(f"replay report: {rep.get('matched')}/{rep.get('games')} matched")
        where = rep.get("platform") or ", ".join(sorted({s.get("platform", "?") for s in rep.get("shards", [])}))

    dec = [r["score"] for role, r in runs if role == "decider"]
    base = [r["score"] for role, r in runs if role == "baseline"]
    L = ["## UFA JEV entry: CI check", "",
         f"- results.json runs: {len(dec)} JEV, {len(base)} baseline",
         f"- JEV mean score: {statistics.fmean(dec):.1f}" if dec else "- JEV runs: none",
         f"- baseline mean score: {statistics.fmean(base):.1f}" if base else "- baseline runs: none"]
    if verified:
        L.append(f"- replayed from seed + action log: {verified[0]}/{verified[1]} matched ({where})")
    L.append("- result: **PASS**" if not problems else f"- result: **FAIL** ({len(problems)} problems)")
    L += [f"  - {p}" for p in problems[:50]]
    print("\n".join(L))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
