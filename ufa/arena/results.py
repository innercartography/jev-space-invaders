"""Build the official results.json (schema_version 2) from episode traces.

    python -m ufa.arena.results ufa/traces/<exp> --decider-arm jev_basic__raw \
        --baseline-arm baseline_llm__raw --out results.json

Only runs that exist in traces are written; every number comes from the
episode summaries (measured in code or read from API responses).
Git commit/push is intentionally NOT done here: publishing needs the owner's consent.
"""
import argparse
import json
from pathlib import Path

from .compare import load

RUN_FIELDS = ["seed", "score", "steps", "frames", "lives_lost", "terminated", "truncated", "model_calls",
              "input_tokens", "output_tokens", "latency_ms_p50", "latency_ms_p95", "latency_ms_total",
              "errors_by_status", "retries", "fallback_actions", "mean_confidence", "low_conf_rate",
              "cost_usd", "wall_clock_s", "served_model", "notes"]
EXTRA_FIELDS = ["episode_id", "arm", "representation", "question_set", "termination_reason", "cost_per_decision_usd",
                "decision_interval_steps", "clock"]


def run_record(s):
    r = {k: s[k] for k in RUN_FIELDS if s.get(k) is not None}
    r.update({k: s[k] for k in EXTRA_FIELDS if s.get(k) is not None})
    # `steps` is environment steps. On the realtime clock the loop's own counter is decisions, and
    # the steps played while a decision was being computed (lag) are added.
    r["decisions"] = s.get("decisions", s["steps"])
    r["steps"] = s.get("env_steps") or (s["steps"] + (s.get("lag_steps_total") or 0))
    return r


def check(r):
    """The consistency checks the judges say they run."""
    problems = []
    if r.get("latency_ms_p50") is not None and r.get("latency_ms_p95") is not None and r["latency_ms_p95"] < r["latency_ms_p50"]:
        problems.append("p95 < p50")
    if r.get("model_calls", 0) > r.get("steps", 0):
        problems.append("model_calls > steps")
    return problems


def model_entry(e, role):
    p = e["policy"]
    return {"role": role, "provider": p.get("provider"), "requested_model": p.get("requested_model"),
            "served_model": e["summary"].get("served_model"), "sdk_package": p.get("sdk_package"),
            "sdk_version": p.get("sdk_version")}


def build(eps, decider_arm, baseline_arm):
    dec = sorted([e for e in eps if e["summary"]["arm"] == decider_arm], key=lambda e: e["summary"]["started_at"])
    base = sorted([e for e in eps if e["summary"]["arm"] == baseline_arm], key=lambda e: e["summary"]["started_at"])
    if not dec:
        raise SystemExit(f"no episodes for decider arm {decider_arm}")
    first = dec[0]
    envc = first["env"]
    maxes = {e["summary"].get("max_steps") for e in dec + base}
    config = {
        "env_id": envc["env_id"], "frameskip": envc["frameskip"],
        "repeat_action_probability": envc["repeat_action_probability"],
        "full_action_space": envc["full_action_space"],
        "max_num_frames_per_episode": envc["max_num_frames_per_episode"], "obs_type": envc["obs_type"],
        "wrappers": [], "decision_interval_steps": first["summary"].get("decision_interval_steps", 1),
        "state_encoding": ("ALE screen + RAM decoded by deterministic code (ufa/arena/extract.py) to ship x, "
                           f"alien grid, tracked bullets with vy, shields, lives; representation '{first['summary']['representation']}'"),
        **first["versions"],
        "clock": first["summary"]["clock"],
    }
    if maxes - {None}:
        config["max_steps"] = sorted(maxes - {None})[-1]
    out = {"schema_version": 2, "models": [model_entry(first, "decider")] + ([model_entry(base[0], "baseline")] if base else []),
           "config": config, "runs": [run_record(e["summary"]) for e in dec]}
    if base:
        out["baseline"] = {"model": base[0]["summary"].get("served_model") or base[0]["policy"].get("requested_model"),
                           "runs": [run_record(e["summary"]) for e in base]}
    flagged = {r["episode_id"]: check(r) for r in out["runs"] + out.get("baseline", {}).get("runs", []) if check(r)}
    return out, flagged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exp_dir", nargs="+", help="one or more experiment trace dirs")
    ap.add_argument("--decider-arm", required=True)
    ap.add_argument("--baseline-arm")
    ap.add_argument("--out", default="results.json")
    args = ap.parse_args()
    out, flagged = build([e for d in args.exp_dir for e in load(d)], args.decider_arm, args.baseline_arm)
    Path(args.out).write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {args.out}: {len(out['runs'])} decider runs, {len(out.get('baseline', {}).get('runs', []))} baseline runs")
    if flagged:
        print("FLAGGED:", json.dumps(flagged))


if __name__ == "__main__":
    main()
