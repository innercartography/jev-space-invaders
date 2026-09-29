# Memory Helps. Until the World Changes.

JEV flies Space Invaders at ~101 ms a decision, then governs a swarm of disposable Tenki workers whose findings survive worker death in Mitosis memory. This lets us watch what happens when inherited knowledge stops fitting the world.

Entry for the UFA JEV Bake-Off (Space Invaders). **Track: Pilot.** JEV chooses every move.

**Site:** https://innercartography.github.io/jev-space-invaders/ · **Demo:** [presentation cut](https://innercartography.github.io/jev-space-invaders/?demo=1) (1:45) · **Full write-up:** [docs/DETAILS.md](docs/DETAILS.md)

## What this is

We started with a practical question: can JEV make Space Invaders decisions fast enough to matter? It could. On 100 untouched seeds it averaged 709, at 101 ms per decision.

Along the way we found that the form of the information we gave the model shaped its behaviour more than anything else. Simple deterministic controls, a sweep bot and a left-wall bot, falsified several of our early explanations. The winning setup tells JEV *which moves are safe* rather than *where the bullets are*.

Then we asked whether experience could accumulate across agents. Tenki gave us disposable workers. Mitosis let their findings survive worker death. JEV supplied fast, typed judgements about which inherited findings still deserved trust. Shared memory made the search much better while the game stayed the same. When the game changed, the old knowledge became *memory drag*.

In the original swarm run, JEV reduced that drag, but a simple threshold rule did slightly better. In the final, fully distributed Tenki validation, JEV's recovery **did not replicate**. That run exposed a confound in our own retrieval adapter: under parallel load it returned an incomplete subset of the stored findings. **Memory is not only what a system stores. It is what it can recover when it matters.**

## Results (Pilot, frozen)

| Player | Games | Mean score | p50 per decision | $ per game |
|---|---|---|---|---|
| **JEV (jev-1.13.0), final** | 100 holdout seeds | **709** (median 620) | **101 ms** | $0.034 |
| Claude Haiku 4.5, same view and question | 5 (first 5 holdout seeds) | 364 | 957 ms | $0.99 |
| Sweep bot (no model) | 100 | 326 | - | $0 |
| Random | 100 | 143 | - | $0 |

- **Turn-based, same 5 seeds:** JEV beat Haiku on 5 of 5.
- **Real-time clock** (the game does not wait for the model; first 20 holdout seeds): JEV beat Haiku on 19 of 20, 441 vs 110. Each JEV decision is about 9× faster (101 vs 957 ms p50), so JEV made 531 decisions per game to Haiku's 33.
- The holdout seeds were drawn once, never used in development, and run once after the configuration was frozen. The development estimate was 711.
- Every game is replay-verified: **305/305** recorded games re-derive to the same score from seed and action log.

Full tables and 95% intervals: [docs/DETAILS.md](docs/DETAILS.md#1-player-pilot) and [`analysis/`](analysis/).

## Watch the demo

- **Scroll story:** https://innercartography.github.io/jev-space-invaders/
- **Presentation cut** (1:45; Space pauses, ← → step through scenes, Esc exits): https://innercartography.github.io/jev-space-invaders/?demo=1
- **Video:** a screen recording of the same cut accompanies the entry.

All game footage is exact emulator replay of recorded games, not live inference. Every number on the site is generated from committed result files by `site/tools/build_data.py`.

## Run it

Python 3.12+.

```bash
git clone https://github.com/innercartography/jev-space-invaders
```

```bash
cd jev-space-invaders
```

```bash
pip install -r requirements.txt
```

View the site locally:

```bash
python -m http.server 8000 -d site
```

Then open http://localhost:8000, or http://localhost:8000/?demo=1 for the presentation cut.

## Reproduce official results

No key needed. This re-derives every game in `results.json` from its seed and action log, then checks `results.json` against the replays:

```bash
python -m ufa.verify_replay check replays/holdout.json --out verify_report.json
```

```bash
python -m ufa.ci_check --results results.json --replays replays/holdout.json --report verify_report.json
```

`ufa.ci_check` exits 1 on any mismatch; change one score in `results.json` and it fails. To play new holdout games with the model (needs `TYPESAFE_API_KEY`; JEV is not deterministic, so new runs vary around the mean):

```bash
python -m ufa.local_batch --config ufa/experiments/exp008_holdout.json --arms jev_final --seeds-file ufa/experiments/seeds_holdout.json --holdout --parallel 8
```

Regenerate the site's numbers from the committed result files (the output should match the committed `site/data/results.js` byte for byte):

```bash
python site/tools/build_data.py
```

## Tenki replay

The same replay check, run in fresh Tenki sandboxes (5 shards; no model and no model key). Needs `TENKI_API_KEY`:

```bash
python -m ufa.tenki.verify --replays replays/holdout.json --shards 5
```

CI runs this in [`.github/workflows/tenki-replay.yml`](.github/workflows/tenki-replay.yml), on manual dispatch or on a push to main that changes the results or game code. The last saved run matched 305/305 games in 33 s, for about $0.006 of compute ([`verification/tenki_verify_holdout.json`](verification/tenki_verify_holdout.json)).

## Swarm experiment

A Squad-style side study, pre-registered in [`ufa/squad/swarm/PREREG.md`](ufa/squad/swarm/PREREG.md). Four disposable workers search 12 rule-based player setups; each worker plays one real game per round. Workers are retired every 5 rounds, and all four at the change. Findings go to Mitosis with provenance, and inherited findings count as evidence, not facts.

**Stable world, then memory benefit, then regime change, then memory drag.** Numbers are the average points the swarm's current pick sits below the best setup (lower is better); 40 paired trials:

| Condition | Before the change | After the change |
|---|---|---|
| Workers alone, no memory | 123 | 48 |
| Workers + Mitosis memory | **56** | 96 |
| JEV governance + memory | 56 | 49 |
| Simple threshold rule + memory | 51 | **40** |

- **Memory helps:** 123 → 56 before the change, better in 39 of 40 trials. About 18 fewer games per trial went to retesting setups already known to be bad.
- **Then the game changes** (official game mode 1: the shields move). The old #1 setup falls to #7, and memory turns into drag: 48 → 96.
- **JEV reduced the drag (96 → 49), but the simple rule did slightly better (40).** The rule beat JEV. In the example on the site, JEV marks an inherited finding (685 points in the old game, 308 now) as contradicted, with p = 0.89.

Reproduce from the saved runs (no key): `python -m ufa.squad.swarm_analysis --run s1`.

## Final distributed validation

Everything ran on Tenki: one coordinator sandbox and four disposable worker sandboxes, replaced on the experiment's schedule and all replaced again at the change. There were 30 worker sandboxes and **2,400 games**, played remotely by the workers. Workers held no keys and were checked empty at birth. Across all attempts, 4,440 games ran on Tenki. 150 sampled games were replayed locally, and 150/150 matched.

Result (10 fresh-seed paired trials, JEV + memory vs JEV without memory):

- **Memory benefit replicated:** 128 → 95 before the change (better in 9 of 10).
- **JEV's recovery did not replicate:** the drag came back after the change, +35 [+17, +52] (worse in 8 of 10).
- **Confound found:** our search-based retrieval adapter read a trial's findings with one query over a feed shared by 10 parallel trials. In 92% of reads, at least one of the trial's own findings was missing. So JEV often could not see the stale finding it needed to challenge. This is a limit of our read path, not evidence about Mitosis storage.

Reproduce the analysis (no key): `python -m ufa.squad.swarm_validation --run v4 --replay 150`. Attempt log: [`ufa/squad/swarm/validation/attempts.json`](ufa/squad/swarm/validation/attempts.json).

## Sponsor stack

- **JEV (TypeSafe System One): the fast, bounded decision layer.** It flies the ship (one typed `choice` per game step, ~101 ms), and it makes the swarm's typed governance calls: explore or coordinate, which inherited finding is contradicted, stop or not. Code computes facts; JEV chooses.
- **Tenki: gave the swarm bodies.** It was the execution substrate:
  - a disposable sandbox for every worker, where worker death is real and everything on its disk is gone;
  - the coordinator sandbox;
  - tournament sharding (`ufa/tenki/remote_batch.py`);
  - the replay CI.
  The engineering it took is in the code (`ufa/squad/swarm_tenki.py`): detached execution, short retryable polls, resilient collection after long-running connections failed. The algorithm itself does not require Tenki.
- **Mitosis: gave the swarm inheritance.** Findings are written with game version, games, mean, interval, status and provenance (`ufa/mitosis/cortex.py`, plain HTTP). Mitosis is the only way a finding outlives its worker. Without it, the swarm's search error roughly doubles in the stable world.

## Controls and falsified hypotheses

- **Sweep bot** (no model: sweep side to side and shoot). It falsified "JEV with the raw threat view beats a dumb bot": the difference was -3 [-39, +34] on 50 new seeds. That result drove the switch to the `move_is_safe` view.
- **Left-wall bot.** It falsified "it wins by hiding at the wall" (180 on all 205 seeds).
- **Simple threshold rule governor** (no model). It beat JEV at governing the swarm after the change (40 vs 49; better in 33 of 40 trials overall).
- The full falsification ladder is in [docs/DETAILS.md](docs/DETAILS.md#1-player-pilot).

## Limitations

- The swarm's *players* are rule-based setups: JEV governs the swarm, it does not fly the ship there.
- The simple rule beat JEV as swarm governor, and the rule was written by us alongside JEV's questions.
- The distributed validation is 10 paired trials per condition, and its memory read was incomplete (see above).
- **Option order matters on borderline JEV calls.** Swapping explore/coordinate flipped 29% of borderline states, against 8% on a plain repeat. The stop call never flipped.
- JEV's `confidence` field is a spread summary of its distribution, not a probability of being right. Every probability quoted here comes from the returned distributions.
- Tenki capacity failures stopped three earlier validation attempts before any trial finished (logged in `attempts.json`). The successful run needed 1 retried call.
- Turn-based Haiku comparison: 5 games (cost-limited). In real time, JEV vs the sweep bot is +107 [-3, +218] on 20 seeds, which is not significant.
- `move_is_safe` is hand-written code (a 12-step physics projection). It agrees with the emulator 85-93% of the time on critical moments.
- JEV is not deterministic. Replays prove the recorded games; new runs vary around the mean.

## Repo map

| Path | What |
|---|---|
| `results.json`, `replays/holdout.json` | Official per-game records and action logs (the files CI verifies) |
| `ufa/arena/` | Game environment, views, JEV and LLM players |
| `ufa/verify_replay.py`, `ufa/ci_check.py` | Replay verification and the results check |
| `ufa/tenki/` | Tenki sharding and replay verification |
| `ufa/squad/` | Lab manager, swarm (`swarm.py`), Tenki swarm (`swarm_tenki.py`), analyses, JEV audits |
| `ufa/squad/swarm/` | Pre-registration, landscapes, saved runs (`s1` main, `v4` Tenki validation), validation audits |
| `ufa/mitosis/` | Mitosis adapter |
| `ufa/experiments/` | Frozen configs and seed lists (including the holdout seeds) |
| `analysis/`, `bench/`, `squad/`, `verification/` | Saved summaries quoted in this README |
| `site/` | The story site; `site/data/results.js` is generated by `site/tools/build_data.py` |
| `docs/DETAILS.md` | Full write-up: every table, the Eval and lab-manager studies |

## License

MIT. See [LICENSE](LICENSE). It covers the code and data authored for this project. It does not cover Space Invaders, its ROM (not included; installed with `ale-py`) or game imagery, or third-party dependencies.
