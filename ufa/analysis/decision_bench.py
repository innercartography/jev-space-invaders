"""Decision benchmark: game moments with exact counterfactual labels, for scoring single decisions.

    python -m ufa.analysis.decision_bench build --exp ufa/traces/exp006_tournament --arms ref,safe,control_sweep \
        --seeds-file ufa/experiments/seeds_dev.json --seed-range 0:20 --out ufa/bench/critical_dev.json

For each sampled step t of a recorded game, the emulator is replayed to exactly that moment and
its state is saved (with the sticky-action RNG). Then each of the six actions is tried:
    take action a for COMMIT steps, then play the best of three simple continuations
    (hold LEFT / hold RIGHT / stay, pressing FIRE every other step) for HORIZON steps.
    survive(a) = at least one continuation keeps every life for COMMIT + HORIZON steps.
A moment is CRITICAL when at least one action survives and at least one does not: the decision
matters, and the right answer is known exactly. The label depends on the continuation set, which
is stated with the data. Holdout seeds are refused. No model calls.
"""
import argparse
import json
import random
import statistics
import time
from multiprocessing import Pool
from pathlib import Path

from ufa.arena import env as envmod
from ufa.arena.compare import load
from ufa.arena.extract import move_safety

COMMIT, HORIZON = 3, 30
EVERY, FROM = 15, 20
BONUS = 50
CONTS = ("LEFT", "RIGHT", "STAY")


def _cont_action(c, k):
    fire = k % 2 == 0
    if c == "STAY":
        return "FIRE" if fire else "NOOP"
    return c + ("FIRE" if fire else "")


def label_episode(args):
    """Two emulators. MAIN only ever steps the recorded actions, so it never leaves the recorded game.
    BRANCH explores. ALE's saved state holds the RNG but not the last joystick input (the sticky-action
    memory), so before every restore BRANCH first takes the action that preceded the saved moment
    ("priming"); the restore then resets everything else. Each start is checked against MAIN's RAM
    and frame number, and dropped if it differs."""
    path, seed, env_cfg, commit = args
    rows = [json.loads(l) for l in open(Path(path) / "steps.jsonl")]
    env = envmod.make_env(env_cfg)
    names = envmod.action_names(env)
    ale = env.unwrapped.ale
    benv = envmod.make_env(env_cfg)
    bu = benv.unwrapped
    bale = bu.ale
    benv.reset(seed=seed)
    env.reset(seed=seed)
    out = []
    ts = set(range(max(FROM, 2), len(rows) - commit - HORIZON, EVERY))
    snaps = {}
    for t, r in enumerate(rows):
        snaps = {t: ale.cloneState(include_rng=True)}
        if t in ts:
            ram_t, frame_t, lives0 = bytes(ale.getRAM()), ale.getEpisodeFrameNumber(), ale.lives()
            ok = frame_t == r["state"]["frame"] and lives0 == r["state"]["lives"]

            def start():
                bu.step(names.index(rows[t - 1]["action"]))  # prime the last-input memory
                bale.restoreState(snaps[t])
                return bytes(bale.getRAM()) == ram_t and bale.getEpisodeFrameNumber() == frame_t

            lab = {}
            for a in names:
                ok = start() and ok
                pts, dead = 0.0, False
                for i in range(commit):
                    _, rew, term, trunc, _ = bu.step(names.index(a))
                    pts += rew if rew < BONUS else 0
                    if bale.lives() < lives0 or term:
                        dead = True
                        break
                best = None
                if not dead:
                    s1 = bale.cloneState(include_rng=True)
                    for c in CONTS:
                        bu.step(names.index(a))  # prime: the last input before s1 was `a`
                        bale.restoreState(s1)
                        p2, d2 = pts, False
                        for k in range(HORIZON):
                            _, rew, term, trunc, _ = bu.step(names.index(_cont_action(c, k)))
                            p2 += rew if rew < BONUS else 0
                            if bale.lives() < lives0 or term:
                                d2 = True
                                break
                        if not d2 and (best is None or p2 > best):
                            best = p2
                lab[a] = {"survive": best is not None, "pts": best}
            surv = [a for a in names if lab[a]["survive"]]
            ms = move_safety(r["state"])
            out.append({"id": f"{r['state']['frame']}@{seed}@{Path(path).name}", "seed": seed, "t": t, "source": path,
                        "source_arm": Path(path).parent.name, "integrity_ok": ok, "state": r["state"],
                        "recorded_action": r["action"], "labels": lab, "safe_actions": surv,
                        "critical": 0 < len(surv) < len(names), "affordance_move_is_safe": ms})
        _, _, term, trunc, _ = env.step(names.index(r["action"]))
        if term or trunc:
            break
    env.close()
    benv.close()
    return out


def build(args):
    eps = [e for d in args.exp for e in load(d)]
    keep = None
    if args.seeds_file:
        if "holdout" in Path(args.seeds_file).name:
            raise SystemExit("the holdout seeds are never used for development benchmarks")
        lo, _, hi = args.seed_range.partition(":")
        keep = set(json.loads(Path(args.seeds_file).read_text())["seeds"][int(lo) if lo else None:int(hi) if hi else None])
    arms = set(args.arms.split(",")) if args.arms else None
    holdout = set(json.loads((Path(__file__).resolve().parents[1] / "experiments" / "seeds_holdout.json").read_text())["seeds"])
    if any(e["summary"]["seed"] in holdout for e in eps) and not args.holdout_spent:
        raise SystemExit("these traces contain holdout seeds; only after the holdout has been run once (config frozen) "
                         "may they become a TEST set: pass --holdout-spent")
    jobs = []
    for e in eps:
        s = e["summary"]
        if (keep and s["seed"] not in keep) or (arms and s["arm"] not in arms) or s.get("clock") != "turn_based":
            continue
        env_cfg = json.loads((Path(e["_path"]) / "episode.json").read_text())["env"]
        jobs.append((e["_path"], s["seed"], envmod.env_config(env_cfg), args.commit))
    with Pool(args.procs) as pool:
        items = [x for chunk in pool.map(label_episode, jobs, chunksize=1) for x in chunk]
    bad = sum(not x["integrity_ok"] for x in items)
    items = [x for x in items if x["integrity_ok"]]
    crit = [x for x in items if x["critical"]]
    # how often the move_is_safe affordance agrees with the emulator's ground truth (by move direction)
    agree = n = 0
    for x in crit:
        ms = x["affordance_move_is_safe"]
        if not ms:
            continue
        for mv, acts in (("left", ("LEFT", "LEFTFIRE")), ("stay", ("NOOP", "FIRE")), ("right", ("RIGHT", "RIGHTFIRE"))):
            truth = any(x["labels"][a]["survive"] for a in acts)
            agree += ms[mv] == truth
            n += 1
    meta = {"format": "ufa-decision-bench-1", "commit_steps": args.commit, "horizon_steps": HORIZON, "continuations": list(CONTS),
            "continuation_fire": "FIRE pressed every other step", "sample_every": EVERY, "sample_from": FROM,
            "bonus_excluded_from_pts": True, "sources": args.exp, "arms": sorted(arms) if arms else None,
            "seeds_file": args.seeds_file, "seed_range": args.seed_range, "episodes": len(jobs),
            "moments": len(items), "critical": len(crit), "replay_mismatch_dropped": bad,
            "critical_safe_action_count": {k: sum(len(x["safe_actions"]) == k for x in crit) for k in range(1, 6)},
            "affordance_agreement_on_critical": round(agree / n, 4) if n else None}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"meta": meta, "items": crit if args.critical_only else items}, separators=(",", ":")))
    print(json.dumps(meta, indent=1))


def case_text(item):
    """A labelled past moment as memory text: the situation (THREAT view) and which moves survived."""
    from ufa.arena import representations

    sit = json.dumps(representations.get("threat")(item["state"], []), separators=(",", ":"))
    return sit, f"Situation: {sit}. Moves that survived: {', '.join(item['safe_actions'])}."


def memorize(args):
    """Ingest a DEVELOPMENT bench's critical moments into the lab's Cortex memory (feed --feed)."""
    from ufa.mitosis.cortex import Cortex

    data = json.loads(Path(args.bench).read_text())
    if any("holdout" in (x.get("source") or "") for x in data["items"]):
        raise SystemExit("memory is built from development moments only")
    rows = []
    for x in data["items"]:
        if x["critical"]:
            _, text = case_text(x)
            rows.append({"external_id": f"case:{x['id']}", "title": f"past moment {x['id'][:40]}", "content": text,
                         "modality": "note", "metadata": {"safe_actions": x["safe_actions"], "seed": x["seed"]}})
    n = Cortex(timeout=120).ingest(args.feed, rows)
    print(f"ingested {n} dev moments into feed {args.feed}")


def _ask(job):
    item, dec, rep_fn, qspec, primary = job[:5]
    memory = job[5] if len(job) > 5 else None
    from ufa.arena.policies import SystemOneChoicePolicy

    rep = rep_fn(item["state"], [])
    mem_ms = None
    if memory is not None:
        cortex, feed, k = memory
        sit, _ = case_text(item)
        t = time.perf_counter()
        try:
            out = cortex.answer(f"Situation: {sit}", limit=k, integration_id=feed, include_raw=True)
            rep["similar_past_moments"] = [((r.get("raw") or {}).get("content") or r.get("preview") or "")[:600]
                                           for r in out.get("results", [])]
        except Exception as e:
            rep["similar_past_moments"] = []
        mem_ms = round((time.perf_counter() - t) * 1000, 1)
    rec = dec.ask(rep, qspec)
    pol = SystemOneChoicePolicy.__new__(SystemOneChoicePolicy)
    pol.primary = primary
    action, conf = pol._read(rec, list(item["labels"]))
    probs = None
    if rec["ok"] and not isinstance(primary, tuple):
        probs = (rec["answers"].get(primary) or {}).get("probabilities")
    return {"id": item["id"], "choice": action, "confidence": conf, "correct": (action in item["safe_actions"]) if action else None,
            "p_safe": round(sum(v for k, v in probs.items() if k in item["safe_actions"]), 4) if probs else None,
            "latency_ms": rec["latency_ms"], "input_tokens": rec["input_tokens"], "output_tokens": rec["output_tokens"],
            "served_model": rec["served_model"], "error": rec["error"], "memory_ms": mem_ms,
            "memory_hits": len(rep.get("similar_past_moments", [])) if memory is not None else None}


def evaluate(args):
    from concurrent.futures import ThreadPoolExecutor

    from ufa.arena import keys, pricing
    from ufa.arena import questions as qmod
    from ufa.arena import representations
    from ufa.arena.deciders import Decider

    data = json.loads(Path(args.bench).read_text())
    items = [x for x in data["items"] if x["critical"]]
    if args.sample:
        items = random.Random(args.sample_seed).sample(items, min(args.sample, len(items)))
    items = items[: args.limit or None]
    if args.backend == "jev":
        keys.load(["TYPESAFE_API_KEY"])
        make = lambda: Decider("jev", args.model)
    else:
        keys.load(["ANTHROPIC_API_KEY"])
        make = lambda: Decider("llm", args.model, provider="anthropic")
    rep_fn = representations.get(args.representation)
    qspec = qmod.get(args.question_set)
    primary = qmod.PRIMARY[args.question_set]
    pool_dec = [make() for _ in range(args.parallel)]
    memory = None
    if args.memory_feed:
        from ufa.mitosis.cortex import Cortex

        memory = (Cortex(timeout=60), args.memory_feed, args.memory_k)
    jobs = [(x, pool_dec[i % args.parallel], rep_fn, qspec, primary, memory) for i, x in enumerate(items)]
    t = time.perf_counter()
    with ThreadPoolExecutor(args.parallel) as ex:
        res = list(ex.map(_ask, jobs))
    wall = time.perf_counter() - t
    for d in pool_dec:
        d.close()
    ok = [r for r in res if r["choice"] is not None]
    lat = sorted(r["latency_ms"] for r in res)
    served = next((r["served_model"] for r in ok if r["served_model"]), None)
    tin = sum(r["input_tokens"] or 0 for r in ok)
    tout = sum(r["output_tokens"] or 0 for r in ok)
    cost = pricing.cost_usd(served or args.model, tin, tout)
    # calibration: confidence as the predicted probability that the choice is safe
    bins = [(0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, 1.01)]
    cal = []
    for lo, hi in bins:
        B = [r for r in ok if r["confidence"] is not None and lo <= r["confidence"] < hi]
        if B:
            cal.append({"bin": [lo, min(hi, 1)], "n": len(B), "mean_conf": round(statistics.fmean(r["confidence"] for r in B), 3),
                        "accuracy": round(statistics.fmean(r["correct"] for r in B), 3)})
    wc = [r for r in ok if r["confidence"] is not None]
    ece = sum(c["n"] * abs(c["mean_conf"] - c["accuracy"]) for c in cal) / len(wc) if wc else None
    right = [r["confidence"] for r in wc if r["correct"]]
    wrong = [r["confidence"] for r in wc if not r["correct"]]
    auc = None
    if right and wrong:
        auc = sum((a > b) + 0.5 * (a == b) for a in right for b in wrong) / (len(right) * len(wrong))
    summ = {"bench": args.bench, "bench_meta": data["meta"], "backend": args.backend, "requested_model": args.model,
            "served_model": served, "representation": args.representation, "question_set": args.question_set,
            "n": len(items), "answered": len(ok), "errors": len(res) - len(ok),
            "accuracy": round(statistics.fmean(r["correct"] for r in ok), 4) if ok else None,
            "random_accuracy": round(statistics.fmean(len(x["safe_actions"]) / 6 for x in items), 4),
            "mean_p_safe": round(statistics.fmean(r["p_safe"] for r in ok if r["p_safe"] is not None), 4) if any(r["p_safe"] is not None for r in ok) else None,
            "mean_confidence": round(statistics.fmean(r["confidence"] for r in wc), 4) if wc else None,
            "calibration_bins": cal, "ece": round(ece, 4) if ece is not None else None,
            "confidence_auc_right_vs_wrong": round(auc, 4) if auc is not None else None,
            "latency_ms_p50": lat[len(lat) // 2] if lat else None, "latency_ms_p95": lat[int(len(lat) * .95)] if lat else None,
            "input_tokens": tin, "output_tokens": tout, "cost_usd": round(cost, 6) if cost is not None else None,
            "cost_per_decision_usd": round(cost / len(ok), 8) if (cost is not None and ok) else None,
            "wall_s": round(wall, 1), "parallel": args.parallel, "memory_feed": args.memory_feed,
            "memory_k": args.memory_k if args.memory_feed else None}
    mm = sorted(r["memory_ms"] for r in res if r.get("memory_ms") is not None)
    if mm:
        summ.update({"memory_ms_p50": mm[len(mm) // 2], "memory_ms_p95": mm[int(len(mm) * .95)],
                     "memory_hits_mean": round(statistics.fmean(r["memory_hits"] for r in res), 2)})
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"summary": summ, "results": res}, indent=1))
    print(json.dumps({k: v for k, v in summ.items() if k != "bench_meta"}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    ev = sub.add_parser("eval")
    ev.add_argument("--bench", required=True)
    ev.add_argument("--backend", choices=["jev", "llm"], required=True)
    ev.add_argument("--model", required=True)
    ev.add_argument("--representation", default="threat")
    ev.add_argument("--question-set", default="move_v1")
    ev.add_argument("--parallel", type=int, default=8)
    ev.add_argument("--limit", type=int)
    ev.add_argument("--memory-feed", help="Cortex feed of labelled DEV moments; retrieved per decision")
    ev.add_argument("--memory-k", type=int, default=3)
    ev.add_argument("--sample", type=int, help="random subsample of the critical items (fixed --sample-seed)")
    ev.add_argument("--sample-seed", type=int, default=0)
    ev.add_argument("--out", required=True)
    b = sub.add_parser("build")
    b.add_argument("--exp", nargs="+", required=True)
    b.add_argument("--arms")
    b.add_argument("--seeds-file")
    b.add_argument("--seed-range", default=":")
    b.add_argument("--out", required=True)
    b.add_argument("--critical-only", action="store_true")
    b.add_argument("--commit", type=int, default=COMMIT, help="steps the tested action is held (>= 2)")
    b.add_argument("--procs", type=int, default=20)
    b.add_argument("--holdout-spent", action="store_true",
                   help="allow holdout traces: only after the frozen holdout run, to build a TEST set")
    m = sub.add_parser("memorize")
    m.add_argument("--bench", required=True, help="a DEVELOPMENT bench")
    m.add_argument("--feed", default="bench_dev_cases")
    a = ap.parse_args()
    {"build": build, "eval": evaluate, "memorize": memorize}[a.cmd](a)


if __name__ == "__main__":
    main()
