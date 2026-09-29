"""Decision policies: representation JSON -> one action name.

A policy owns *how* a decision is made; the representation owns *what* it sees.
Registered today:
    random        harness test only (served_model "random-policy", not a JEV run)
    jev_basic     one JEV choice question per step, take the top choice
    baseline_llm  the same question through the System One adapter on an LLM
    scripted      fixed-rule controls (left wall, right wall, sweep, still); falsification only

To add a policy, write a class with decide()/describe()/close() and register a
builder in REGISTRY.
Rule: in jev_* policies only JEV may choose the move. Code can shape the input
and apply confidence rules, but an LLM must never pick the action.
"""
import random

from . import questions as qmod
from .deciders import Decider


class RandomPolicy:
    uses_model = False

    def __init__(self, arm, seed):
        self.rng = random.Random(seed)
        self.arm = arm

    def decide(self, rep, actions):
        return {"action": self.rng.choice(actions), "fallback": False, "confidence": None, "decider": None}

    def describe(self):
        return {"policy": "random", "provider": "none", "requested_model": "random-policy", "served_model": "random-policy"}

    def close(self):
        pass


class ScriptedPolicy:
    """Deliberately dumb deterministic controls (exp004). No model. They read only `ship_x` and
    `shot_ready` from the `threat` representation, i.e. from the one `hints()` implementation.
        left / right  push toward that wall forever
        sweep         move one way, reverse only at the ship's x limits
        still         never move
    All fire whenever shot_ready is true."""

    uses_model = False
    X_LIMITS = (37, 108)  # smallest / largest ship x seen in exp003 traces

    def __init__(self, arm, seed):
        self.arm = arm
        self.mode = arm["control"]
        self.dir = "RIGHT"

    def decide(self, rep, actions):
        x = rep.get("ship_x")
        if self.mode == "sweep" and x is not None:
            if x <= self.X_LIMITS[0] + 1:
                self.dir = "RIGHT"
            elif x >= self.X_LIMITS[1] - 1:
                self.dir = "LEFT"
        move = {"left": "LEFT", "right": "RIGHT", "sweep": self.dir, "still": ""}[self.mode]
        fire = "FIRE" if rep.get("shot_ready") else ""
        action = (move + fire) or "NOOP"
        return {"action": action, "fallback": False, "confidence": None, "decider": None}

    def describe(self):
        return {"policy": "scripted", "control": self.mode, "provider": "none",
                "requested_model": f"scripted-{self.mode}", "served_model": f"scripted-{self.mode}"}

    def close(self):
        pass


class SystemOneChoicePolicy:
    """Ask the question set, act on the primary choice answer. On any error: NOOP (counted as fallback).

    Optional arm settings (exp006). Both only ever repeat an action the decider itself chose:
      decision_interval k   ask once every k env steps and repeat that answer in between
                            (results.json config.decision_interval_steps)
      hold_below_conf tau   if the answer's confidence is below tau, keep the previous action
                            (the rules' own example of using confidence)
    A split question set (move + fire) is combined into one of the six actions."""

    uses_model = True
    MOVE_FIRE = {("LEFT", "FIRE"): "LEFTFIRE", ("RIGHT", "FIRE"): "RIGHTFIRE", ("STAY", "FIRE"): "FIRE",
                 ("LEFT", "HOLD"): "LEFT", ("RIGHT", "HOLD"): "RIGHT", ("STAY", "HOLD"): "NOOP"}

    def __init__(self, arm, decider, fallback_action="NOOP"):
        self.arm = arm
        self.decider = decider
        self.qset_name = arm.get("question_set", "move_v1")
        self.qspec = qmod.get(self.qset_name)
        self.primary = qmod.PRIMARY[self.qset_name]
        self.fallback_action = fallback_action
        self.interval = int(arm.get("decision_interval", 1))
        self.hold_tau = arm.get("hold_below_conf")
        self.last_action = None
        self.since_ask = 0

    def _read(self, rec, actions):
        """-> (action or None, confidence)"""
        if not rec["ok"]:
            return None, None
        if isinstance(self.primary, tuple):
            m, f = (rec["answers"].get(q) or {} for q in self.primary)
            action = self.MOVE_FIRE.get((m.get("choice"), f.get("choice")))
            return (action if action in actions else None), m.get("confidence")
        ans = rec["answers"].get(self.primary) or {}
        choice = ans.get("choice")
        return (choice if choice in actions else None), ans.get("confidence")

    def decide(self, rep, actions):
        if self.last_action is not None and self.since_ask < self.interval:
            self.since_ask += 1
            return {"action": self.last_action, "fallback": False, "confidence": None, "decider": None,
                    "held": "interval"}
        rec = self.decider.ask(rep, self.qspec)
        self.since_ask = 1
        action, conf = self._read(rec, actions)
        if action is None:
            self.last_action = self.fallback_action
            return {"action": self.fallback_action, "fallback": True, "confidence": None, "decider": rec}
        held = None
        if self.hold_tau is not None and self.last_action is not None and conf is not None and conf < self.hold_tau:
            action, held = self.last_action, "low_confidence"
        self.last_action = action
        return {"action": action, "fallback": False, "confidence": conf, "decider": rec, "held": held}

    def describe(self):
        d = self.decider.describe()
        d.update({"policy": self.arm["policy"], "question_set": self.qset_name,
                  "question_set_hash": qmod.fingerprint(self.qspec), "questions": self.qspec,
                  "fallback_action": self.fallback_action, "decision_interval": self.interval,
                  "hold_below_conf": self.hold_tau})
        return d

    def close(self):
        self.decider.close()


def _jev_basic(arm, seed):
    return SystemOneChoicePolicy(arm, Decider("jev", arm.get("model", "jev-latest")))


def _baseline_llm(arm, seed):
    return SystemOneChoicePolicy(arm, Decider("llm", arm.get("model", "claude-haiku-4-5"),
                                              provider=arm.get("provider", "anthropic"),
                                              llm_options=arm.get("llm_options")))


REGISTRY = {"random": lambda arm, seed: RandomPolicy(arm, seed), "jev_basic": _jev_basic, "baseline_llm": _baseline_llm,
            "scripted": ScriptedPolicy}

# Which secret each policy needs. The runner loads only these (least privilege).
SECRETS = {"random": [], "jev_basic": ["TYPESAFE_API_KEY"], "baseline_llm": ["ANTHROPIC_API_KEY"], "scripted": []}


def build(arm, seed):
    if arm["policy"] not in REGISTRY:
        raise KeyError(f"unknown policy {arm['policy']!r}; known: {sorted(REGISTRY)}")
    return REGISTRY[arm["policy"]](arm, seed)
