"""Deterministic state extraction: ALE screen + RAM + info -> plain dict.

No model is involved here. Colors and screen bands were measured on
ALE/SpaceInvaders-v5 (ale-py 0.12.1); see docs/UFA-ARENA.md.

All bullets are gray 1px-wide lines. The Atari draws enemy bullets only on odd
frames and the player's shot only on even frames (checked over 5 full games:
5667/5671 odd-frame bullets moved down, 2997/2998 even-frame bullets moved up).
So the extractor reads two frames per step: enemy bullets from the odd one,
everything else from the even one (see env.FrameTap).
"""
import numpy as np

BLACK = (0, 0, 0)
PLAYER_RGB = (50, 132, 50)
ALIEN_RGB = (134, 134, 29)
SHIELD_RGB = (181, 83, 40)
SHOT_RGB = (142, 142, 142)

PLAY_TOP, PLAY_BOTTOM = 20, 195      # rows between the score bar and the ground
SHIP_TOP, SHIP_BOTTOM = 185, 194     # rows the ship occupies
SHIELD_TOP, SHIELD_BOTTOM = 157, 174
SHIP_HALF_WIDTH = 4
WIDTH = 160


def _mask(img, rgb):
    return (img[..., 0] == rgb[0]) & (img[..., 1] == rgb[1]) & (img[..., 2] == rgb[2])


def _thin(img):
    """Gray 1-2px wide vertical lines in the play area -> (y0, y1, x0, x1)."""
    out = []
    for y0, y1, x0, x1, n in _components(_mask(img[PLAY_TOP:PLAY_BOTTOM], SHOT_RGB)):
        if x1 - x0 + 1 <= 2 and y1 - y0 + 1 >= 3:
            out.append((y0 + PLAY_TOP, y1 + PLAY_TOP, x0, x1))
    return out


def _components(mask):
    """8-connected components -> list of (y0, y1, x0, x1, n_pixels)."""
    seen = np.zeros_like(mask, dtype=bool)
    H, W = mask.shape
    out = []
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        stack = [(y, x)]
        seen[y, x] = True
        y0 = y1 = y
        x0 = x1 = x
        n = 0
        while stack:
            cy, cx = stack.pop()
            n += 1
            y0, y1, x0, x1 = min(y0, cy), max(y1, cy), min(x0, cx), max(x1, cx)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        out.append((int(y0), int(y1), int(x0), int(x1), n))
    return out


class Extractor:
    """Stateful only for tracking: it remembers the previous step's projectiles
    and aliens to estimate velocities. One instance per episode."""

    def __init__(self):
        self.prev_shots = {"enemy": [], "player": []}
        self.prev_alien_left = None
        self.prev_player_x = None
        self.shield_full = None
        self.shots_seen = 0  # player shots that newly appeared

    def extract(self, odd_img, img, ram, info, score, step, prev_action):
        """odd_img: last odd frame (enemy bullets). img: last even frame (everything else)."""
        play = img[PLAY_TOP:PLAY_BOTTOM]

        # Ship: green pixels inside the ship band.
        ship_cols = np.nonzero(_mask(img[SHIP_TOP:SHIP_BOTTOM + 1], PLAYER_RGB).any(axis=0))[0]
        player_x = int(round((ship_cols[0] + ship_cols[-1]) / 2)) if len(ship_cols) else None
        player_vx = (player_x - self.prev_player_x) if (player_x is not None and self.prev_player_x is not None) else None

        # Aliens are wide yellow blobs.
        aliens = []
        for y0, y1, x0, x1, n in _components(_mask(play, ALIEN_RGB)):
            if x1 - x0 + 1 >= 5:
                aliens.append({"x": (x0 + x1) // 2, "y": (y0 + y1) // 2 + PLAY_TOP, "y_bottom": y1 + PLAY_TOP})

        shots = (self._track(_thin(odd_img), "enemy", player_x)
                 + self._track(_thin(img), "player", player_x))

        alien_summary = None
        if aliens:
            xs = [a["x"] for a in aliens]
            left = min(xs)
            alien_summary = {
                "count": len(aliens),
                "leftmost_x": left,
                "rightmost_x": max(xs),
                "lowest_y": max(a["y_bottom"] for a in aliens),
                "vx": (left - self.prev_alien_left) if self.prev_alien_left is not None else None,
            }
            self.prev_alien_left = left

        shields = self._shields(img)

        self.prev_player_x = player_x
        return {
            "step": step,
            "score": score,
            "lives": int(info.get("lives", 0)),
            "frame": int(info.get("episode_frame_number", 0)),
            "prev_action": prev_action,
            "player": {"x": player_x, "vx": player_vx, "visible": player_x is not None},
            "aliens": sorted(aliens, key=lambda a: (a["y"], a["x"])),
            "alien_summary": alien_summary,
            "projectiles": shots,
            "shields": shields,
            "ram_invaders_byte17": int(ram[17]),  # AtariARI label: invaders_left_count
        }

    def _track(self, thin, owner, player_x):
        """Match this step's bullets of one owner to last step's to get vy (pixels per step)."""
        shots = []
        used = set()
        prev = self.prev_shots[owner]
        for y0, y1, x0, x1 in thin:
            x = (x0 + x1) // 2
            best = None
            for i, p in enumerate(prev):
                if i in used or abs(p["x"] - x) > 3:
                    continue
                dy = y0 - p["y"]
                if (dy > 0 if owner == "enemy" else dy < 0) and abs(dy) <= 40 and (best is None or abs(dy) < best[1]):
                    best = (i, abs(dy))
            if best is not None:
                used.add(best[0])
                vy = y0 - prev[best[0]]["y"]
            else:
                vy = None
                if owner == "player":
                    self.shots_seen += 1
            shots.append({"x": x, "y": y0, "y_bottom": y1, "vy": vy, "owner": owner, "tracked": vy is not None})
        self.prev_shots[owner] = shots
        return shots

    def _shields(self, img):
        band = _mask(img[SHIELD_TOP:SHIELD_BOTTOM + 1], SHIELD_RGB)
        cols = band.any(axis=0)
        groups, start = [], None
        for x in range(WIDTH + 1):
            on = x < WIDTH and cols[x]
            if on and start is None:
                start = x
            elif not on and start is not None:
                groups.append((start, x - 1))
                start = None
        out = []
        for x0, x1 in groups:
            out.append({"x_min": x0, "x_max": x1, "pixels": int(band[:, x0:x1 + 1].sum())})
        if self.shield_full is None and out:
            self.shield_full = max(s["pixels"] for s in out)
        for s in out:
            s["integrity"] = round(s["pixels"] / self.shield_full, 2) if self.shield_full else None
        return out


SHIP_X_MIN, SHIP_X_MAX = 37, 108  # ship x range seen in 1,000+ games (exp003/exp004)
SHIP_SPEED = 2                    # pixels per env step while LEFT/RIGHT is held (measured, exp004 sweep)
DEFAULT_BULLET_VY = 4             # most common enemy bullet speed; used when a bullet isn't tracked yet


def move_safety(state, horizon=12):
    """For each move held for the next `horizon` steps (left / stay / right), will a falling enemy
    bullet reach the ship? Projects every enemy bullet straight down at its measured speed and the
    ship sideways at SHIP_SPEED, clamped to its x range. Bullets above a shield's x span that haven't
    reached the shield row are assumed blocked (same rule as lane_danger). Deterministic, no model."""
    px = state["player"]["x"]
    if px is None:
        return None
    enemy = []
    for s in state["projectiles"]:
        if s["owner"] != "enemy":
            continue
        if s["y_bottom"] < SHIELD_TOP and any(sh["x_min"] <= s["x"] <= sh["x_max"] for sh in state["shields"]):
            continue
        vy = s["vy"] if (s["vy"] and s["vy"] > 0) else DEFAULT_BULLET_VY
        enemy.append((s["x"], s["y"], s["y_bottom"], vy))
    out = {}
    for name, m in (("left", -1), ("stay", 0), ("right", 1)):
        safe = True
        for t in range(0, horizon + 1):
            sx = min(max(px + m * SHIP_SPEED * t, SHIP_X_MIN), SHIP_X_MAX)
            for bx, y0, y1, vy in enemy:
                if y1 + vy * t >= SHIP_TOP and y0 + vy * t <= SHIP_BOTTOM and abs(bx - sx) <= SHIP_HALF_WIDTH + 1:
                    safe = False
                    break
            if not safe:
                break
        out[name] = safe
    return out


def threat_analysis(state):
    """Derived, deterministic hazard features. Used by reduced representations."""
    px = state["player"]["x"]
    enemy = [s for s in state["projectiles"] if s["owner"] == "enemy"]
    threats = []
    for s in enemy:
        if px is None:
            break
        dy = SHIP_TOP - s["y_bottom"]
        if dy < -10:
            continue  # already below the ship
        steps = round(max(dy, 0) / s["vy"], 1) if (s["vy"] and s["vy"] > 0) else None
        threats.append({"dx": s["x"] - px, "dy": dy, "steps_to_ship_row": steps})
    threats.sort(key=lambda t: (t["dy"], abs(t["dx"])))

    def lane_blocked(offset):
        if px is None:
            return None
        cx = px + offset
        for s in enemy:
            dy = SHIP_TOP - s["y_bottom"]
            if -10 <= dy <= 60 and abs(s["x"] - cx) <= SHIP_HALF_WIDTH + 2:  # -10: already inside the ship rows
                under_shield = any(sh["x_min"] <= s["x"] <= sh["x_max"] for sh in state["shields"]) and s["y_bottom"] < SHIELD_TOP
                if not under_shield:
                    return True
        return False

    lanes = {"left": lane_blocked(-8), "stay": lane_blocked(0), "right": lane_blocked(8)}
    aliens = state["aliens"]
    nearest_dx = min((a["x"] - px for a in aliens), key=abs) if (aliens and px is not None) else None
    shot_in_flight = any(s["owner"] == "player" for s in state["projectiles"])
    return {
        "threats": threats,
        "lane_danger": lanes,
        "nearest_alien_dx": nearest_dx,
        "alien_above": nearest_dx is not None and abs(nearest_dx) <= 4,
        "shot_in_flight": shot_in_flight,
    }
