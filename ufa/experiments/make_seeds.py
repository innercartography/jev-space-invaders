"""One-off: create the frozen DEVELOPMENT and HOLDOUT seed sets (run once on 2026-09-27).

Every seed used before this point is below 1000, so both sets are drawn from [1000, 2^31-1).
Re-running would create different sets; don't. The holdout file's SHA-256 is recorded in the
development ledger so any later edit is detectable.
"""
import datetime
import json
import secrets
from pathlib import Path

HERE = Path(__file__).resolve().parent

if __name__ == "__main__":
    for f in ("seeds_dev.json", "seeds_holdout.json"):
        if (HERE / f).exists():
            raise SystemExit(f"{f} exists; the seed sets are frozen")
    rng = secrets.SystemRandom()
    pool = set()
    while len(pool) < 400:
        pool.add(rng.randrange(1000, 2**31 - 1))
    pool = list(pool)
    rng.shuffle(pool)
    meta = {"created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "generator": "secrets.SystemRandom over [1000, 2^31-1); all earlier seeds are < 1000"}
    (HERE / "seeds_dev.json").write_text(json.dumps(
        {**meta, "purpose": "DEVELOPMENT: tuning and candidate selection", "seeds": sorted(pool[:300])}, indent=1))
    (HERE / "seeds_holdout.json").write_text(json.dumps(
        {**meta, "purpose": "FROZEN HOLDOUT: run once, after candidate selection is complete. Never tune on it.",
         "seeds": sorted(pool[300:])}, indent=1))
    print("dev 300, holdout 100")
