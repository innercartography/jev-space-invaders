"""Compare arms of one experiment from their episode.json files. Measurements only.

    python -m ufa.arena.compare ufa/traces/exp001_first_light [--reference baseline_llm__raw]

Writes compare.json and compare.md next to the traces. Every episode found is
included, failed or short ones too; nothing is filtered out. Interpretation is
left to a human (or a later analysis step), and is kept separate from these numbers.
"""
import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


def load(exp_dir):
    eps = []
    for p in sorted(Path(exp_dir).glob("*/seed*/episode.json")):
        e = json.loads(p.read_text())
        e["_path"] = str(p.parent)
        eps.append(e)
    return eps


def _stats(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    out = {"n": len(vals), "mean": round(statistics.fmean(vals), 3), "median": round(statistics.median(vals), 3),
           "min": min(vals), "max": max(vals)}
    if len(vals) > 1:
        out["stdev"] = round(statistics.stdev(vals), 3)
    return out


def summarize(eps):
    by_arm = defaultdict(list)
    for e in eps:
        by_arm[e["summary"]["arm"]].append(e)
    arms = {}
    for arm, lst in sorted(by_arm.items()):
        S = [e["summary"] for e in lst]
        decisions = sum(s["steps"] for s in S)
        cost = [s["cost_usd"] for s in S]
        arms[arm] = {
            "policy": S[0]["policy"], "representation": S[0]["representation"],
            "question_set": S[0]["question_set"], "served_models": sorted({str(s["served_model"]) for s in S}),
            "episodes": len(S), "seeds": sorted(s["seed"] for s in S),
            "config_hashes": sorted({e["config_hash"] for e in lst}), "code_hashes": sorted({e["code_hash"] for e in lst}),
            "score": _stats([s["score"] for s in S]),
            "steps": _stats([s["steps"] for s in S]),
            "lives_lost": _stats([s["lives_lost"] for s in S]),
            "reward_events": _stats([s["reward_events"] for s in S]),
            "decision_ms_p50": _stats([s["latency_ms_p50"] for s in S]),
            "decision_ms_p95": _stats([s["latency_ms_p95"] for s in S]),
            "wall_clock_s": _stats([s["wall_clock_s"] for s in S]),
            "cost_usd_total": round(sum(c for c in cost if c is not None), 6) if any(c is not None for c in cost) else None,
            "cost_per_decision_usd": (round(sum(c for c in cost if c is not None) / decisions, 8)
                                      if decisions and all(c is not None for c in cost) else None),
            "input_tokens_total": sum(s["input_tokens"] or 0 for s in S),
            "output_tokens_total": sum(s["output_tokens"] or 0 for s in S),
            "rep_chars_mean": _stats([s["rep_chars_mean"] for s in S]),
            "mean_confidence": _stats([s["mean_confidence"] for s in S]),
            "fallback_rate": round(sum(s["fallback_actions"] for s in S) / decisions, 4) if decisions else None,
            "errors_by_status": _merge([s["errors_by_status"] for s in S]),
            "score_per_1k_rep_chars": _stats([s["score"] / (s["rep_chars_total"] / 1000) if s["rep_chars_total"] else None for s in S]),
            "termination": _merge([{s["termination_reason"]: 1} for s in S]),
        }
    return arms


def paired(eps, ref):
    """Per-seed differences against a reference arm (same seed, latest episode each)."""
    latest = {}
    for e in eps:
        s = e["summary"]
        key = (s["arm"], s["seed"])
        if key not in latest or s["started_at"] > latest[key]["started_at"]:
            latest[key] = s
    out = defaultdict(list)
    for (arm, seed), s in sorted(latest.items()):
        if arm == ref or (ref, seed) not in latest:
            continue
        r = latest[(ref, seed)]
        out[arm].append({"seed": seed, "score_delta": s["score"] - r["score"],
                         "p50_ratio": (round(r["latency_ms_p50"] / s["latency_ms_p50"], 2)
                                       if s["latency_ms_p50"] and r["latency_ms_p50"] else None)})
    return dict(out)


def _merge(dicts):
    m = defaultdict(int)
    for d in dicts:
        for k, v in (d or {}).items():
            m[k] += v
    return dict(m)


def to_md(exp_dir, arms, pairs, ref):
    f = lambda st, k="median": "-" if not st else st[k]
    lines = [f"# Comparison: {Path(exp_dir).name}", "",
             "Measured numbers only. n = episodes. Score and latency cells show median (mean).", "",
             "| arm | n | score | steps | lives lost | decision p50 ms | p95 ms | $/decision | $ total | repr chars | mean conf | fallback | termination |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for arm, a in arms.items():
        lines.append(f"| {arm} | {a['episodes']} | {f(a['score'])} ({f(a['score'],'mean')}) | {f(a['steps'])} | "
                     f"{f(a['lives_lost'])} | {f(a['decision_ms_p50'])} | {f(a['decision_ms_p95'])} | "
                     f"{a['cost_per_decision_usd']} | {a['cost_usd_total']} | {f(a['rep_chars_mean'])} | "
                     f"{f(a['mean_confidence'])} | {a['fallback_rate']} | {a['termination']} |")
    if pairs:
        lines += ["", f"Paired by seed against `{ref}` (score delta; latency ratio = ref p50 / arm p50):", ""]
        for arm, rows in pairs.items():
            lines.append(f"- {arm}: " + ", ".join(f"seed {r['seed']}: {r['score_delta']:+g} pts, {r['p50_ratio']}x" for r in rows))
    small = [arm for arm, a in arms.items() if a["episodes"] < 5]
    if small:
        lines += ["", f"Caution: fewer than 5 episodes for {', '.join(small)}. Too few to conclude anything."]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exp_dir")
    ap.add_argument("--reference", help="arm to pair against (default: first baseline_llm arm)")
    args = ap.parse_args()
    eps = load(args.exp_dir)
    if not eps:
        raise SystemExit(f"no episode.json under {args.exp_dir}")
    arms = summarize(eps)
    ref = args.reference or next((k for k, a in arms.items() if a["policy"] == "baseline_llm"), None)
    pairs = paired(eps, ref) if ref else {}
    out = {"experiment_dir": args.exp_dir, "reference": ref, "arms": arms, "paired": pairs}
    Path(args.exp_dir, "compare.json").write_text(json.dumps(out, indent=2))
    md = to_md(args.exp_dir, arms, pairs, ref)
    Path(args.exp_dir, "compare.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
