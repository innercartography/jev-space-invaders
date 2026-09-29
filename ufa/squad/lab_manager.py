"""Squad: JEV as the lab manager. It decides which configuration gets the next games and when to stop.

The task is the one we did by hand in exp006: find the best configuration in a pool, spending as few
games as possible. Every "game" is a real recorded game (dev seeds, exp006 traces), so the search can
be replayed many times at no game cost, with the seed order shuffled per trial. Trials are paired:
trial t uses the same seed order for every manager.

    python -m ufa.squad.lab_manager build-pool --out ufa/squad/pool_dev20.json
    python -m ufa.squad.lab_manager remember --pool ufa/squad/pool_dev20.json      # round-1 findings -> Mitosis Cortex
    python -m ufa.squad.lab_manager run --pool ufa/squad/pool_dev20.json --round 2 --manager jev --memory on --trials 40

Managers:
    jev      JEV answers two typed questions: "which configuration gets the next games, or STOP?" and,
             at the end, "which configuration is best?". Code only runs the games it chose.
    haiku    the identical questions and state through the System One adapter (claude-haiku-4-5).
    halving  successive halving, no model (the rule we used by hand).
    uniform  equal games for every configuration, no model.
Memory (--memory on): before the search, each configuration's description is looked up in the lab's
Cortex memory (findings written from round 1, with sources). The retrieved evidence is added to the
state. With memory off the state is identical except for that field.
"""
import argparse
import json
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EXP = REPO / "ufa" / "traces" / "exp006_tournament"
CONFIG = REPO / "ufa" / "experiments" / "exp006_tournament.json"

ROUNDS = {
    1: ["ref", "momentum", "safe", "minimal", "split", "hold17", "k2", "k4", "sweepwords"],
    2: ["safe", "safe_sweepwords", "safe_min", "safe_k2", "safe_k4", "safe_hold17", "safe_split"],
}
# What each configuration changes, in plain words. Round 2 = the round-1 change applied on top of `safe`.
CHANGE = {
    "ref": "reference: THREAT view (bullet list, lane danger), one move question",
    "momentum": "adds the ship's previous move direction to the view",
    "safe": "replaces lane danger with move_is_safe: whether each move avoids every projected bullet",
    "minimal": "removes the incoming-bullet list and lives from the view",
    "split": "asks move and fire as two separate typed answers",
    "hold17": "keeps the last action when the answer's confidence is below 0.17",
    "k2": "asks once every 2 steps and repeats the answer in between",
    "k4": "asks once every 4 steps and repeats the answer in between",
    "sweepwords": "question wording tells it to keep sweeping steadily and reverse only at edges or to dodge",
    "safe_sweepwords": "move_is_safe view + question wording to keep sweeping steadily, reverse only at edges or to dodge",
    "safe_min": "move_is_safe view, with the incoming-bullet list and lives removed",
    "safe_k2": "move_is_safe view, asks once every 2 steps and repeats the answer in between",
    "safe_k4": "move_is_safe view, asks once every 4 steps and repeats the answer in between",
    "safe_hold17": "move_is_safe view, keeps the last action when the answer's confidence is below 0.17",
    "safe_split": "move_is_safe view, asks move and fire as two separate typed answers",
}
NEXT_Q = ("You run a search for the Space Invaders player configuration with the highest mean score. "
          "Choose which configuration gets the next {batch} paired games, or STOP. Spend games where they can still change "
          "which configuration is best: one that could be the best and is still uncertain. Configurations with 0 games "
          "have no data yet. Avoid spending on configurations that are clearly worse. {mem}"
          "Choose STOP when one configuration is clearly best, or when the remaining budget cannot change the answer.")
MEM_HINT = ("`memory` holds findings from an earlier search where the same changes were tested on a different base "
            "configuration; treat them as prior evidence, not as results for these configurations. ")
NEXT_Q3 = ("You run a search for the Space Invaders player configuration with the highest mean score. "
           "Choose which configuration gets the next {batch} paired games, or STOP. First give every untested configuration "
           "one run: any of them could be the best. After that, spend games only on configurations that could still be the "
           "best (could_be_best), preferring the least certain of them. {mem}"
           "Choose STOP only when exactly one configuration could still be the best, or when the remaining budget cannot "
           "change the answer.")
BEST_Q = ("The search is over. Which configuration has the highest true mean score? "
          "Consider both its mean and how many games support it.")


def ex_bonus(path):
    s, bonus = 0.0, 0.0
    for line in open(Path(path) / "steps.jsonl"):
        r = json.loads(line).get("reward") or 0.0
        s += r
        if r >= 50:
            bonus += r
    return s - bonus


def build_pool(args):
    from ufa.arena.compare import load

    seeds = json.loads((REPO / "ufa/experiments/seeds_dev.json").read_text())["seeds"][:20]
    arms = sorted({a for r in ROUNDS.values() for a in r})
    pool = {}
    for e in load(str(EXP)):
        s = e["summary"]
        if s["arm"] in arms and s["seed"] in seeds and s.get("clock", "turn_based") == "turn_based":
            p = pool.setdefault(s["arm"], {"change": CHANGE[s["arm"]], "games": {}})
            p["games"][str(s["seed"])] = {"ex_bonus": ex_bonus(e["_path"]), "score": s["score"],
                                          "cost_usd": s.get("cost_usd") or 0.0, "wall_clock_s": s.get("wall_clock_s")}
    missing = {a: 20 - len(pool.get(a, {}).get("games", {})) for a in arms if len(pool.get(a, {}).get("games", {})) < 20}
    if missing:
        print(f"WARNING arms incomplete (rounds using them can't run yet): {missing}")
    pool = {a: p for a, p in pool.items() if len(p["games"]) == 20}
    for a, p in pool.items():
        xs = [g["ex_bonus"] for g in p["games"].values()]
        p["true_mean"] = round(statistics.fmean(xs), 2)
    Path(args.out).write_text(json.dumps({"seeds": seeds, "rounds": ROUNDS, "arms": pool}, indent=1))
    for r, names in ROUNDS.items():
        if all(a in pool for a in names):
            print(f"round {r}:", sorted(((pool[a]["true_mean"], a) for a in names), reverse=True))


def paired_ci(a, b, n_boot=4000, seed=0):
    d = [x - y for x, y in zip(a, b)]
    rng = random.Random(seed)
    boots = sorted(statistics.fmean(rng.choices(d, k=len(d))) for _ in range(n_boot))
    return statistics.fmean(d), boots[int(0.025 * n_boot)], boots[int(0.975 * n_boot)]


def remember(args):
    """Write round-1 findings (full 20-seed data, paired vs ref) into the lab's Cortex memory."""
    from ufa.mitosis.cortex import Cortex

    pool = json.loads(Path(args.pool).read_text())
    seeds = [str(s) for s in pool["seeds"]]
    A = pool["arms"]
    ref = [A["ref"]["games"][s]["ex_bonus"] for s in seeds]
    rows = []
    for arm in ROUNDS[1]:
        if arm == "ref":
            continue
        xs = [A[arm]["games"][s]["ex_bonus"] for s in seeds]
        m, lo, hi = paired_ci(xs, ref)
        verdict = "helped" if lo > 0 else ("hurt" if hi < 0 else "no clear effect")
        text = (f"Round-1 finding: the change '{CHANGE[arm]}' ({arm}) {verdict} compared with the reference "
                f"configuration: {m:+.0f} points per game (95% CI {lo:+.0f} to {hi:+.0f}, bonus ship excluded), "
                f"20 paired games on development seeds.")
        rows.append({"external_id": f"round1:{arm}", "title": f"Round 1: {arm}", "content": text,
                     "modality": "note", "metadata": {"arm": arm, "diff": round(m, 1), "ci": [round(lo, 1), round(hi, 1)],
                                                      "n": 20, "verdict": verdict, "source": "exp006 stage A traces"}})
    c = Cortex()
    n = c.ingest("lab_round1", rows)
    for r in rows:
        c.remember("lab-manager", r["content"], kind="finding", confidence=0.9,
                   metadata={"arm": r["metadata"]["arm"], "round": 1})
    print(f"ingested {n} rows and remembered {len(rows)} findings; calls: {c.calls}")


def retrieve_memory(arms, limit=2):
    from ufa.mitosis.cortex import Cortex

    c = Cortex()
    mem, lat = {}, []
    for a in arms:
        t = time.perf_counter()
        # the lab-manager's remembered findings only (source_table "memories"), full text via include_raw
        out = c.answer(f"effect of this change: {CHANGE[a]}", limit=limit, source_table="memories", include_raw=True)
        lat.append(round((time.perf_counter() - t) * 1000, 1))
        mem[a] = [{"evidence": ((r.get("raw") or {}).get("text") or r.get("preview") or "")[:400],
                   "source": r.get("universal_id"), "score": r.get("score")} for r in (out or {}).get("results", [])]
    return mem, lat


class ModelManager:
    def __init__(self, backend, memory, state_version="v1", rng=None):
        from ufa.arena import keys
        from ufa.arena.deciders import Decider

        keys.load(["TYPESAFE_API_KEY"] if backend == "jev" else ["ANTHROPIC_API_KEY"])  # only the key this manager needs
        self.backend = backend
        self.decider = (Decider("jev", "jev-latest") if backend == "jev"
                        else Decider("llm", "claude-haiku-4-5", provider="anthropic"))
        self.memory = memory
        self.version = state_version
        self.rng = rng
        self.recs = []

    def _ask(self, state, instructions, options, qid):
        spec = {qid: {"type": "choice", "instructions": instructions, "criteria": {o: None for o in options}}}
        rec = self.decider.ask(state, spec)
        self.recs.append(rec)
        ans = (rec.get("answers") or {}).get(qid) or {}
        ch = ans.get("choice")
        return (ch if ch in options else None), ans.get("confidence")

    def state(self, st, budget_left, batch, stage):
        cfgs = []
        names = list(st)
        if self.version in ("v1s", "v2", "v3"):  # shuffled order: no position cue
            self.rng.shuffle(names)
        leader = max((statistics.fmean(xs) for xs in st.values() if xs), default=None)
        for a in names:
            xs = st[a]
            d = {"name": a, "change": CHANGE[a], "games": len(xs)}
            if xs:
                d["mean"] = round(statistics.fmean(xs), 1)
            if len(xs) > 1:
                sd = statistics.stdev(xs)
                d["sd"] = round(sd, 1)
                d["ci95"] = [round(d["mean"] - 1.96 * sd / len(xs) ** 0.5), round(d["mean"] + 1.96 * sd / len(xs) ** 0.5)]
            if self.version in ("v2", "v3"):  # decision facts computed by code; the choice stays with the model
                d["untested"] = not xs
                if len(xs) > 1 and leader is not None:
                    d["could_be_best"] = d["ci95"][1] >= leader
                elif not xs:
                    d["could_be_best"] = True
            cfgs.append(d)
        s = {"task": "find the configuration with the highest mean score per game (bonus ship excluded)",
             "stage": stage, "budget_left_games": budget_left, "games_per_run": batch, "configurations": cfgs}
        if self.version in ("v2", "v3"):
            s["configurations_that_could_be_best"] = sum(1 for d in cfgs if d.get("could_be_best", True) and d["games"] != 1)
        if self.memory is not None:
            s["memory"] = {a: [m["evidence"] for m in self.memory.get(a, [])] for a in st}
        return s

    def next(self, st, budget_left, batch, max_games):
        opts = [a for a, xs in st.items() if len(xs) + batch <= max_games] + ["STOP"]
        q = (NEXT_Q3 if self.version == "v3" else NEXT_Q).format(batch=batch, mem=MEM_HINT if self.memory is not None else "")
        ch, _ = self._ask(self.state(st, budget_left, batch, "choose next"), q, opts, "next")
        return ch

    def best(self, st, batch):
        tried = [a for a, xs in st.items() if xs]
        if len(tried) == 1:  # nothing to choose between; a one-option choice is not a decision
            return tried[0]
        ch, _ = self._ask(self.state(st, 0, batch, "declare best"), BEST_Q, tried, "best")
        return ch


def run_trial(pool, arms, trial, manager, memory, budget, batch, state_version="v1"):
    rng = random.Random(1000 + trial)
    order = [str(s) for s in pool["seeds"]]
    rng.shuffle(order)
    A = pool["arms"]
    max_games = len(order)
    st = {a: [] for a in arms}
    used, game_cost, fallbacks, decisions = 0, 0.0, 0, []
    mm = ModelManager(manager, memory, state_version, random.Random(5000 + trial)) if manager in ("jev", "haiku") else None

    def play(a, k):
        nonlocal used, game_cost
        for _ in range(k):
            s = order[len(st[a])]
            g = A[a]["games"][s]
            st[a].append(g["ex_bonus"])
            game_cost += g["cost_usd"]
            used += 1

    if manager == "uniform":
        while used + batch <= budget:
            a = min((x for x in arms if len(st[x]) + batch <= max_games), key=lambda x: len(st[x]), default=None)
            if a is None:
                break
            play(a, batch)
        winner = max(arms, key=lambda a: statistics.fmean(st[a]) if st[a] else -1e9)
    elif manager == "halving":
        alive = list(arms)
        rounds = max(1, (len(arms) - 1).bit_length())
        for r in range(rounds):
            per = max(1, (budget // rounds) // len(alive))
            for a in alive:
                play(a, min(per, max_games - len(st[a])))
            alive = sorted(alive, key=lambda a: -statistics.fmean(st[a]))[: max(1, (len(alive) + 1) // 2)]
            if len(alive) == 1:
                break
        winner = alive[0]
    else:
        while used + batch <= budget:
            ch = mm.next(st, budget - used, batch, max_games)
            if ch is None:
                fallbacks += 1
                ch = min(st, key=lambda x: len(st[x]))
            decisions.append(ch)
            if ch == "STOP":
                break
            play(ch, batch)
        winner = mm.best(st, batch) if any(st.values()) else None
        if winner is None:
            fallbacks += 1
            winner = max((a for a in arms if st[a]), key=lambda a: statistics.fmean(st[a]))
    truth = {a: A[a]["true_mean"] for a in arms}
    best = max(truth, key=truth.get)
    out = {"trial": trial, "manager": manager, "memory": memory is not None, "winner": winner, "correct": winner == best,
           "regret": round(truth[best] - truth[winner], 2), "games_used": used, "game_cost_usd": round(game_cost, 5),
           "games_per_arm": {a: len(xs) for a, xs in st.items()}, "decisions": decisions, "fallbacks": fallbacks}
    if mm:
        from ufa.arena.pricing import cost_usd

        R = mm.recs
        lat = [r["latency_ms"] for r in R]
        out.update({"model_calls": len(R), "errors": sum(not r["ok"] for r in R),
                    "served_model": next((r["served_model"] for r in R if r.get("served_model")), None),
                    "latency_ms": lat,
                    "input_tokens": sum(r.get("input_tokens") or 0 for r in R),
                    "output_tokens": sum(r.get("output_tokens") or 0 for r in R)})
        out["orchestration_cost_usd"] = cost_usd(out["served_model"] or ("jev-latest" if manager == "jev" else "claude-haiku-4-5"),
                                                 out["input_tokens"], out["output_tokens"])
        mm.decider.close()
    return out


def run(args):
    pool = json.loads(Path(args.pool).read_text())
    arms = pool["rounds"][str(args.round)]
    memory, mem_lat = (None, [])
    if args.memory == "on":
        memory, mem_lat = retrieve_memory(arms)
    t0 = time.perf_counter()
    with ThreadPoolExecutor(args.parallel) as ex:
        res = list(ex.map(lambda t: run_trial(pool, arms, t, args.manager, memory, args.budget, args.batch, args.state),
                          range(args.trials)))
    wall = round(time.perf_counter() - t0, 1)
    lat = [x for r in res for x in r.get("latency_ms", [])]
    summ = {"round": args.round, "manager": args.manager, "memory": args.memory, "state": args.state, "trials": args.trials,
            "budget": args.budget, "batch": args.batch, "true_best": max(arms, key=lambda a: pool["arms"][a]["true_mean"]),
            "accuracy": round(statistics.fmean(r["correct"] for r in res), 3),
            "regret_mean": round(statistics.fmean(r["regret"] for r in res), 1),
            "games_used_mean": round(statistics.fmean(r["games_used"] for r in res), 1),
            "game_cost_usd_mean": round(statistics.fmean(r["game_cost_usd"] for r in res), 4),
            "fallbacks": sum(r["fallbacks"] for r in res), "wall_s": wall}
    if lat:
        lat.sort()
        summ.update({"model_calls_per_trial": round(statistics.fmean(r["model_calls"] for r in res), 1),
                     "latency_ms_p50": lat[len(lat) // 2], "latency_ms_p95": lat[int(0.95 * (len(lat) - 1))],
                     "orchestration_cost_usd_per_trial": round(statistics.fmean(r["orchestration_cost_usd"] or 0 for r in res), 6),
                     "errors": sum(r["errors"] for r in res), "served_model": res[0].get("served_model")})
    if memory is not None:
        summ["memory_lookup_ms"] = mem_lat
        summ["memory_evidence"] = memory
    out = Path(args.out) / f"round{args.round}_{args.manager}_mem{args.memory}_{args.state}_b{args.budget}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summ, "trials": res}, indent=1))
    print(json.dumps({k: v for k, v in summ.items() if k != "memory_evidence"}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build-pool")
    b.add_argument("--out", default=str(REPO / "ufa/squad/pool_dev20.json"))
    m = sub.add_parser("remember")
    m.add_argument("--pool", default=str(REPO / "ufa/squad/pool_dev20.json"))
    r = sub.add_parser("run")
    r.add_argument("--pool", default=str(REPO / "ufa/squad/pool_dev20.json"))
    r.add_argument("--round", type=int, choices=[1, 2], required=True)
    r.add_argument("--manager", choices=["jev", "haiku", "halving", "uniform"], required=True)
    r.add_argument("--memory", choices=["on", "off"], default="off")
    r.add_argument("--trials", type=int, default=40)
    r.add_argument("--budget", type=int, default=36)
    r.add_argument("--batch", type=int, default=3)
    r.add_argument("--state", choices=["v1", "v1s", "v2", "v3"], default="v1",
                   help="v1 plain; v1s shuffled order; v2 shuffled + computed facts (untested, could_be_best); v3 = v2 + explore-first wording")
    r.add_argument("--parallel", type=int, default=8)
    r.add_argument("--out", default=str(REPO / "ufa/squad/results"))
    a = ap.parse_args()
    {"build-pool": build_pool, "remember": remember, "run": run}[a.cmd](a)


if __name__ == "__main__":
    main()
