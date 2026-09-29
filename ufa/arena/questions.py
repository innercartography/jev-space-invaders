"""Question sets: versioned, plain-JSON question specs shared by JEV and the LLM baseline.

A question set is part of the experiment's identity. Don't edit one in place
after results exist: add a new version (move_v2, ...) so older runs stay comparable.
"""
import copy
import hashlib
import json

MOVE_CRITERIA = {
    "NOOP": "Stay still and do not shoot.",
    "FIRE": "Stay still and shoot straight up.",
    "RIGHT": "Move right (toward larger x) without shooting.",
    "LEFT": "Move left (toward smaller x) without shooting.",
    "RIGHTFIRE": "Move right and shoot.",
    "LEFTFIRE": "Move left and shoot.",
}

SETS = {
    # The official recommended shape: one choice question over the six ALE actions.
    "move_v1": {
        "action": {
            "type": "choice",
            "instructions": (
                "You control the laser cannon (the ship) at the bottom of Space Invaders. "
                "Choose the best action for the next moment. First, do not get hit by an enemy "
                "bullet falling toward the ship. Then line up under aliens and shoot them. "
                "Only one of your shots can be on screen at a time."
            ),
            "criteria": MOVE_CRITERIA,
        }
    },
    # exp006: the same information as move_v1, split into two typed answers in ONE request.
    # The move answer and the fire answer are combined into one of the six ALE actions.
    "split_v1": {
        "move": {
            "type": "choice",
            "instructions": (
                "You control the laser cannon (the ship) at the bottom of Space Invaders. "
                "Choose how the ship should move for the next moment. First, do not get hit by an enemy "
                "bullet falling toward the ship. Then line up under aliens."
            ),
            "criteria": {
                "LEFT": "Move left (toward smaller x).",
                "RIGHT": "Move right (toward larger x).",
                "STAY": "Do not move.",
            },
        },
        "fire": {
            "type": "choice",
            "instructions": (
                "You control the laser cannon (the ship) at the bottom of Space Invaders. "
                "Decide whether to shoot straight up now. Only one of your shots can be on screen at a time."
            ),
            "criteria": {"FIRE": "Shoot now.", "HOLD": "Do not shoot."},
        },
    },
    # exp006: move_v1 with a strategy stated in the instructions (steady sweeping). Same options.
    "sweep_words_v1": {
        "action": {
            "type": "choice",
            "instructions": (
                "You control the laser cannon (the ship) at the bottom of Space Invaders. "
                "Choose the best action for the next moment. Keep moving steadily in one direction, and "
                "reverse only at the edge of your range or to get out of the path of a falling enemy bullet. "
                "Shoot whenever your shot is ready. Only one of your shots can be on screen at a time."
            ),
            "criteria": MOVE_CRITERIA,
        }
    },
}

PRIMARY = {"move_v1": "action", "split_v1": ("move", "fire"), "sweep_words_v1": "action"}  # which answer(s) pick the move


def get(name):
    if name not in SETS:
        raise KeyError(f"unknown question set {name!r}; known: {sorted(SETS)}")
    return copy.deepcopy(SETS[name])


def fingerprint(spec):
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:12]


def to_sdk(spec):
    """Plain spec -> typesafe_sdk question objects (the adapter accepts the same types)."""
    from typesafe_sdk import Choice, Noul, Score

    out = {}
    for qid, q in spec.items():
        if q["type"] == "choice":
            out[qid] = Choice(instructions=q["instructions"], criteria=q["criteria"])
        elif q["type"] == "score":
            out[qid] = Score(instructions=q["instructions"], criteria=q["criteria"])
        elif q["type"] == "noul":
            out[qid] = Noul(instructions=q["instructions"], criteria=q.get("criteria"))
    return out
