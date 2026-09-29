#!/usr/bin/env python3
"""Smallest possible direct JEV call: list models, then ask one bounded question.

Stdlib only. Reads TYPESAFE_API_KEY from the environment, or from an env file
passed with --env-file. Never prints the key. Writes one trace JSON per run.

    python3 ufa/jev/smoke_test.py --env-file .env
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.typesafe.ai/v1"
ACTIONS = ["NOOP", "FIRE", "RIGHT", "LEFT", "RIGHTFIRE", "LEFTFIRE"]


def load_key(env_file):
    key = os.environ.get("TYPESAFE_API_KEY", "")
    if not key and env_file:
        for line in Path(env_file).expanduser().read_text().splitlines():
            if line.startswith("TYPESAFE_API_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        sys.exit("TYPESAFE_API_KEY not set (env var or --env-file).")
    return key


def call(method, path, key, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status, payload = r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        status, payload = e.code, {"error": e.read().decode(errors="replace")[:500]}
    return status, payload, round((time.perf_counter() - t0) * 1000, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file")
    ap.add_argument("--model", default="jev-latest")
    ap.add_argument("--trace-dir", default=str(Path(__file__).resolve().parents[1] / "traces"))
    args = ap.parse_args()
    key = load_key(args.env_file)

    status, models, ms = call("GET", "/models", key)
    print(f"GET /models -> {status} in {ms} ms")
    if status != 200:
        sys.exit(f"auth/models check failed: {models}")
    print("  models:", [m.get("name") for m in models.get("models", [])])

    state = (
        "Space Invaders. Player cannon at x=40 of 160. Nearest invader column at x=72, "
        "descending, 3 rows left. An enemy bullet is falling at x=44, close above the player. "
        "Player has no shot currently in flight."
    )
    request = {
        "state": state,
        "model": args.model,
        "questions": {
            "action": {
                "type": "choice",
                "instructions": "Pick the best next move: survive first, then line up shots.",
                "criteria": {a: None for a in ACTIONS},
            },
            "danger": {
                "type": "noul",
                "instructions": "Is the player in immediate danger of being hit?",
            },
        },
    }
    status, resp, ms = call("POST", "/systemone", key, request)
    print(f"POST /systemone -> {status} in {ms} ms")
    print(json.dumps(resp, indent=2))

    trace_dir = Path(args.trace_dir)
    trace_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    trace = {"ts": stamp, "latency_ms": ms, "status": status, "request": request, "response": resp}
    (trace_dir / f"jev_smoke_{stamp}.json").write_text(json.dumps(trace, indent=2))
    print(f"trace -> {trace_dir / f'jev_smoke_{stamp}.json'}")
    sys.exit(0 if status == 200 else 1)


if __name__ == "__main__":
    main()
