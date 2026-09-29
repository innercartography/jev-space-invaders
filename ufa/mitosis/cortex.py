"""Minimal Mitosis Cortex client (plain HTTP, stdlib only) for the lab's experiment memory.

The lab memory lives in its own office (MITOSIS_OFFICE_ID), separate from any personal memory.
Only MI_API_KEY (or MITOSIS_API_KEY) is read, and it is never printed or written to a trace.

    python -m ufa.mitosis.cortex status
    python -m ufa.mitosis.cortex ask "does holding the last action when unsure help?"

Routes follow https://mitosislabs.ai/developers (the "same loop over plain HTTP" section):
    POST {BASE}/v1/ingest    rows into a feed (external_id = idempotency key)
    POST {BASE}/v1/answer    hybrid retrieval, cited evidence, no LLM at query time
    POST {BASE}/v1/remember  one attributed fact, with the ids it was concluded from
"""
import argparse
import json
import os
import time
import urllib.error
import urllib.request

from ufa.arena import keys

ENDPOINT = "https://m.mitosislabs.ai/api/v1/offices/{office}/cortex"
UA = "ufa-jev-lab/0.1"  # the default Python user agent is refused by the CDN


class Cortex:
    def __init__(self, office=None, timeout=60):
        try:  # the Mitosis SDK/CLI name first, then ours
            (self.key,) = keys.load(["MI_API_KEY"])
        except SystemExit:
            (self.key,) = keys.load(["MITOSIS_API_KEY"])
        self.office = office or os.environ.get("MITOSIS_OFFICE_ID") or keys.load(["MITOSIS_OFFICE_ID"])[0]
        self.base = ENDPOINT.format(office=self.office)
        self.timeout = timeout
        self.calls = []  # (route, status, ms) for cost/latency accounting

    def _call(self, method, route, body=None):
        req = urllib.request.Request(self.base + route, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": f"Bearer {self.key}", "User-Agent": UA,
                                              "content-type": "application/json"})
        t = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                status, out = r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            status, out = e.code, {"error": e.read().decode(errors="replace")[:500]}
        self.calls.append((route, status, round((time.perf_counter() - t) * 1000, 1)))
        if status >= 400:
            raise RuntimeError(f"cortex {route} -> {status}: {str(out)[:300]}")
        return out

    def status(self):
        return self._call("GET", "/status")

    def ensure_feed(self, feed):
        """Create and register a custom feed (both idempotent), as the SDK's ensureFeed does (sdk 0.27.2)."""
        schema = f"ext_{feed}"
        self._call("POST", "/v1/feeds/ensure-table", {"target_schema": schema})
        self._call("POST", "/v1/feeds/register", {
            "integration_id": feed, "schema": schema, "table": "integration_feed", "primary_key_cols": ["external_id"],
            "embeddable_cols": ["title", "content"], "cursor_col": "imported_at", "modality_col": "modality",
            "drive_ref_col": "file_path"})
        return f"{schema}.integration_feed"

    def ingest(self, feed, rows, batch=20, ensure=True):
        """feed: short id, e.g. 'lab_round1'. Rows need external_id and content (same external_id = update)."""
        if ensure:
            self.ensure_feed(feed)
        n = 0
        for i in range(0, len(rows), batch):
            out = self._call("POST", "/v1/ingest", {"feed_key": f"ext_{feed}.integration_feed", "defer_embed": True,
                                                    "rows": rows[i:i + batch]})
            n += (out or {}).get("raw_persisted") or (out or {}).get("ingested") or len(rows[i:i + batch])
        return n

    def answer(self, query, limit=5, **filters):
        return self._call("POST", "/v1/answer", {"query": query, "limit": limit, **filters})

    def remember(self, agent, text, kind="observation", confidence=None, sources=None, metadata=None):
        body = {"agent": agent, "text": text, "kind": kind, "metadata": metadata or {}}
        if confidence is not None:
            body["confidence"] = confidence
        if sources:
            body["source_universal_ids"] = sources
        return self._call("POST", "/v1/remember", body)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    a = sub.add_parser("ask")
    a.add_argument("query")
    a.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()
    c = Cortex()
    out = c.status() if args.cmd == "status" else c.answer(args.query, args.limit)
    print(json.dumps(out, indent=1)[:4000])


if __name__ == "__main__":
    main()
