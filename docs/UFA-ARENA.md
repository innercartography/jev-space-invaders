# UFA arena: how it works

This is the pipeline, one file per stage (`ufa/arena/`):

```
env.py -> extract.py -> representations.py -> policies.py + deciders.py -> env.step
                                                  |
                                     trace.py -> compare.py / results.py
```

| Dimension | Where | Chosen by |
|---|---|---|
| Game and env settings | `env.py` | config `env` |
| Seed | runner | config `seeds` / `--seeds` |
| State extraction (deterministic code) | `extract.py` | fixed; its hash is recorded |
| Representation (what the model sees) | `representations.py` (`raw`, `raw_hints`, `threat`) | arm `representation` |
| Decision policy | `policies.py` (`random`, `jev_basic`, `baseline_llm`) | arm `policy` |
| Model | `deciders.py`, the single JEV/LLM adapter | arm `model` / `provider` |
| Questions | `questions.py` (`move_v1`) | arm `question_set` |
| Clock | runner (`turn_based` or `realtime`) | config `clock` |
| Remote compute | `ufa/tenki/remote_episode.py` | CLI |

There are three operations, and each lives in its own place:

- **Perception** (`extract.py`): what exists in the game (ship, aliens, bullets, shields).
- **Compression / foveation** (the choice inside each representation function): which of that state the model sees.
- **Affordance extraction** (`representations.hints()`, built on `extract.threat_analysis`): relations derived for the decision.
  - `lane_danger`, `shot_ready`, `alien_above`, `nearest_alien_dx`, `incoming`.
  - This is the only implementation of these hints. `raw_hints` and `threat` both call it.

How the three views compare:

- `raw`: no compression, no hints.
- `raw_hints`: no compression, with hints.
- `threat`: compressed, with hints.

To change one thing, add an arm that differs in only that field. Seeds and env settings are shared by every arm.

## Commands (run from the repo root with the virtualenv active)

```
python -m ufa.arena.run --config ufa/experiments/exp001_first_light.json [--arms A,B] [--seeds 1,2] [--max-steps N]
python -m ufa.arena.compare ufa/traces/exp001_first_light
python -m ufa.arena.results ufa/traces/<exp> --decider-arm jev_basic__threat --baseline-arm baseline_llm__raw --out results.json
python -m ufa.tenki.remote_episode --config <cfg> --arm jev_basic__threat --seed 1
```

## Experiment config (JSON, in `ufa/experiments/`)

- **Top-level fields:** `experiment_id`, `description`, `env`, `clock`, `low_conf_threshold` and `seeds`.
- **`arms[]`:** each arm has `{name, policy, representation, question_set, model, provider?, notes?}`.
- **Versioning:** the config hash is recorded with every episode. Change a config by writing a new file, not by editing one that already has results.

## Trace schema

Each episode gets its own directory, `ufa/traces/<exp>/<arm>/seed<N>__<utc>/`. Directories are never overwritten, and failed runs are kept.

- **`episode.json`** holds:
  - `episode_id`, `config_hash`, `code_hash`, `source_commit`
  - `env`, `versions`, `arm`, and `policy` (including the exact questions and their hash)
  - `candidate_actions`
  - `initial` (the RAM as hex, plus the extracted state)
  - `summary`. It uses every official `results.json` run field, plus:
    - termination reason and action counts
    - representation size
    - model latency, compared with total decision latency
    - env time
    - cost per decision
    - orchestration counters (workers, subagents, tools, messages)
    - compute host
- **`steps.jsonl`** has one line per decision. Each line contains:
  - `state` (extracted) and `representation` (exactly what was sent), with its `rep_chars`
  - `action`, `fallback`, `confidence` and `decision_ms`
  - `decider`, which holds `answers` (typed, with probabilities), `served_model`, tokens, `retries`, HTTP `statuses`, `error` and `latency_ms`
  - `reward`, `score`, `lives`, `frame` and `lag_steps`
- **Leak guard:** every line is checked against the loaded secret values before it's written.

## Measured facts (read these before trusting any number)

1. **Enemy bullets never appear in the frame the environment returns.**
   - The Atari draws enemy bullets on odd frames and the player's shot on even ones, and with frameskip 4 the returned frame is always even.
   - `env.FrameTap` keeps the last two frames with a read-only proxy on `ale.act`. With it, the game runs identically: same score, frame count and RAM.
   - Parity was checked over 5 games: 5,667 of 5,671 odd-frame bullets were falling, and 2,997 of 2,998 even-frame bullets were rising.
2. **JEV is not deterministic.**
   - On identical inputs, 0 of 36 probability vectors matched exactly. Near-ties flip.
   - Replaying the same seed gave 210 points one time and 470 the next.
   - Reproducibility therefore has to be **statistical**: many episodes per arm, reported as a distribution.
