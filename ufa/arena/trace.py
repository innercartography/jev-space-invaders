"""Trace files. One directory per episode, never overwritten:

    <out>/<experiment_id>/<arm>/seed<seed>__<utc stamp>/
        episode.json   config, versions, policy description, initial state, summary
        steps.jsonl    one JSON object per decision step

Every line is checked against the loaded secret values before it is written.
"""
import json
from datetime import datetime, timezone
from pathlib import Path


class SecretLeak(RuntimeError):
    pass


def utc_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")[:-4] + "Z"


class EpisodeTrace:
    def __init__(self, out_root, experiment_id, arm_name, seed, secret_values=()):
        self.stamp = utc_stamp()
        self.episode_id = f"{experiment_id}/{arm_name}/seed{seed}__{self.stamp}"
        self.dir = Path(out_root) / experiment_id / arm_name / f"seed{seed}__{self.stamp}"
        self.dir.mkdir(parents=True, exist_ok=False)
        self._secrets = [s for s in secret_values if s and len(s) >= 8]
        self._steps = open(self.dir / "steps.jsonl", "w", encoding="utf-8")

    def _dump(self, obj, **kw):
        text = json.dumps(obj, default=_default, **kw)
        for s in self._secrets:
            if s in text:
                raise SecretLeak("a secret value reached a trace record; write blocked")
        return text

    def step(self, record):
        self._steps.write(self._dump(record, separators=(",", ":")) + "\n")

    def episode(self, record):
        (self.dir / "episode.json").write_text(self._dump(record, indent=2), encoding="utf-8")

    def close(self):
        self._steps.close()


def _default(o):
    try:
        import numpy as np

        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
    except ImportError:
        pass
    return str(o)
