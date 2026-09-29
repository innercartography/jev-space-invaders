"""The single adapter between the arena and System One style deciders.

Both backends take the same state and the same typed questions, and both return
the same record:
    backend "jev": TypeSafe JEV via typesafe-sdk (TypeSafeClient.system_one)
    backend "llm": an LLM via system-one-adapter (the official drop-in baseline)

This is the only file that talks to JEV or to an LLM. Secrets come from the
environment; they are never written into returned records.
"""
import time

from . import questions as qmod


class _StatusRecorder:
    """Wraps the HTTP transport to see every attempt's status code (for retries/errors)."""

    def __init__(self):
        import httpx2

        self.inner = httpx2.HTTPTransport()
        self.statuses = []

    def handle_request(self, request):
        try:
            resp = self.inner.handle_request(request)
        except Exception as e:
            self.statuses.append(type(e).__name__)
            raise
        self.statuses.append(resp.status_code)
        return resp

    def close(self):
        self.inner.close()


def _make_transport():
    import httpx2

    rec = _StatusRecorder()

    class T(httpx2.BaseTransport):
        def handle_request(self, request):
            return rec.handle_request(request)

        def close(self):
            rec.close()

    return T(), rec


class Decider:
    def __init__(self, backend, model, provider=None, llm_options=None, timeout_s=30.0):
        self.backend = backend
        self.model = model
        self.provider = provider
        self.llm_options = dict(llm_options or {})
        self.timeout_s = timeout_s
        self._rec = None
        if backend == "jev":
            from typesafe_sdk import TypeSafeClient

            transport, self._rec = _make_transport()
            self.client = TypeSafeClient(model=model, transport=transport, timeout=timeout_s)
            self.sdk = ("typesafe-sdk", _ver("typesafe-sdk"))
        elif backend == "llm":
            from system_one_adapter import SystemOneAdapterClient

            opts = {"structured_outputs": True, "llm_answer_mode": "probabilities",
                    "normalize_probabilities": True, "n_retry_malformed_structure": 2}
            opts.update(self.llm_options)
            self.llm_options = opts
            self.client = SystemOneAdapterClient(provider=provider, model=model, **opts)
            self.sdk = ("system-one-adapter", _ver("system-one-adapter"))
        else:
            raise ValueError(f"unknown backend {backend!r}")

    def describe(self):
        return {"backend": self.backend, "provider": self.provider or "typesafe", "requested_model": self.model,
                "sdk_package": self.sdk[0], "sdk_version": self.sdk[1], "llm_options": self.llm_options or None}

    def ask(self, state, question_spec):
        """One decision request. Never raises: errors come back in the record."""
        sdk_questions = qmod.to_sdk(question_spec)
        if self._rec:
            self._rec.statuses = []
        t0 = time.perf_counter()
        rec = {"ok": False, "answers": {}, "served_model": None, "input_tokens": None, "output_tokens": None,
               "retries": 0, "statuses": [], "error": None}
        try:
            resp = self.client.system_one(state=state, questions=sdk_questions)
            rec["ok"] = True
            rec["served_model"] = getattr(resp, "model", None)
            rec["answers"] = {k: _answer(v) for k, v in resp.answers.items()}
            u = resp.usage
            if self.backend == "llm":
                rec["input_tokens"] = getattr(u, "input_tokens_total", None)
                rec["output_tokens"] = getattr(u, "output_tokens_total", None)
                rec["retries"] = (getattr(u, "n_retries", 0) or 0)
                rec["provider_latency_s"] = getattr(u, "latency", None)
            else:
                rec["input_tokens"] = getattr(u, "input_tokens", None)
                rec["output_tokens"] = getattr(u, "output_tokens", None)
        except Exception as e:  # recorded, the policy falls back
            status = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
            rec["error"] = {"type": type(e).__name__, "status": status, "message": str(e)[:300]}
        rec["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        if self._rec:
            rec["statuses"] = list(self._rec.statuses)
            rec["retries"] = max(0, len(self._rec.statuses) - 1)
        return rec

    def close(self):
        try:
            self.client.close()
        except Exception:
            pass


def _answer(a):
    d = a.model_dump() if hasattr(a, "model_dump") else dict(a)
    if isinstance(d.get("probabilities"), dict):
        d["probabilities"] = {k: round(float(v), 4) for k, v in d["probabilities"].items()}
    return d


def _ver(pkg):
    import importlib.metadata as md

    try:
        return md.version(pkg)
    except md.PackageNotFoundError:
        return None
