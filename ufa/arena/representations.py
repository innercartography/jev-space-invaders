"""Representations: extracted state -> the JSON the decider actually sees.

Three separate operations (kept apart on purpose):
  PERCEPTION            extract.py: pixels/RAM -> what exists (ship, aliens, bullets, shields)
  COMPRESSION/FOVEATION a representation's choice of which extracted state to expose
  AFFORDANCE EXTRACTION hints(): relations derived for the decision (lane danger, shot ready...)
raw = all state, no hints; raw_hints = all state + hints; threat = compressed state + hints.

Every representation gets the same extracted state, so comparing two of them
on the same seeds changes only what the model is shown.

To add one (foveated, temporal, affordance, hierarchical, uncertainty, hybrid),
write a function `name(state, history) -> dict` and register it in REGISTRY.
`history` is the list of earlier extracted states in this episode, oldest first.
"""
from .extract import move_safety, threat_analysis


def raw(state, history):
    """Essentially everything the extractor knows, lightly organised."""
    return {
        "game": "Space Invaders (Atari). Screen x 0..159 left to right, y grows downward; ship row y=185..194.",
        "score": state["score"],
        "lives": state["lives"],
        "prev_action": state["prev_action"],
        "ship": {"x": state["player"]["x"], "vx": state["player"]["vx"]},
        "aliens": [[a["x"], a["y"]] for a in state["aliens"]],
        "alien_summary": state["alien_summary"],
        "projectiles": [
            {"x": s["x"], "y": s["y"], "y_bottom": s["y_bottom"], "vy": s["vy"], "owner": s["owner"]}
            for s in state["projectiles"]
        ],
        "shields": [{"x_min": s["x_min"], "x_max": s["x_max"], "integrity": s["integrity"]} for s in state["shields"]],
    }


def hints(state):
    """AFFORDANCE EXTRACTION: decision-relevant relations derived from the extracted state
    (extract.threat_analysis). This is the single implementation of the hints; every
    representation that exposes hints must call this, so they are identical across views."""
    t = threat_analysis(state)
    return {
        "incoming": t["threats"][:3],  # dx: bullet x minus ship x; dy: pixels above ship
        "lane_danger": t["lane_danger"],  # true = a falling bullet is in that lane
        "nearest_alien_dx": t["nearest_alien_dx"],
        "alien_above": t["alien_above"],
        "shot_ready": not t["shot_in_flight"],
    }


def threat(state, history):
    """COMPRESSION + hints: only ship x and lives from the raw state, plus the hints.
    No alien grid, no shields list, no score."""
    return {"ship_x": state["player"]["x"], "lives": state["lives"], **hints(state)}


def raw_hints(state, history):
    """No compression + hints: the unchanged raw view with the same hints appended."""
    return {**raw(state, history), **hints(state)}


# ---- exp006 tournament candidates: each differs from `threat` in ONE named dimension ----

def _moving(state):
    a = state.get("prev_action") or ""
    return "left" if "LEFT" in a else ("right" if "RIGHT" in a else "none")


def threat_momentum(state, history):
    """TEMPORAL: `threat` + which way the ship moved on the previous step (its momentum)."""
    return {**threat(state, history), "moving": _moving(state)}


def threat_safe(state, history):
    """AFFORDANCE: `threat` with lane_danger (is a bullet in this lane now) replaced by
    move_is_safe (does holding this move for the next 12 steps avoid every projected bullet)."""
    rep = threat(state, history)
    rep.pop("lane_danger")
    rep["move_is_safe"] = move_safety(state)
    return rep


def threat_minimal(state, history):
    """COMPRESSION: `threat` without the raw incoming-bullet list and lives; affordances kept."""
    rep = threat(state, history)
    rep.pop("incoming")
    rep.pop("lives")
    return rep


def threat_safe_min(state, history):
    """COMPRESSION on top of threat_safe: drop the raw incoming-bullet list and lives, keep the
    projected move_is_safe affordance. Tests whether the affordance alone is sufficient."""
    rep = threat_safe(state, history)
    rep.pop("incoming")
    rep.pop("lives")
    return rep


REGISTRY = {"raw": raw, "threat": threat, "raw_hints": raw_hints, "threat_momentum": threat_momentum,
            "threat_safe": threat_safe, "threat_minimal": threat_minimal, "threat_safe_min": threat_safe_min}


def get(name):
    if name not in REGISTRY:
        raise KeyError(f"unknown representation {name!r}; known: {sorted(REGISTRY)}")
    return REGISTRY[name]
