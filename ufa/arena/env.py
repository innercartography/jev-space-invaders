"""Environment construction. The only place that knows about gymnasium/ALE."""
import gymnasium as gym
import ale_py

gym.register_envs(ale_py)

ENV_DEFAULTS = {
    "env_id": "ALE/SpaceInvaders-v5",
    "obs_type": "ram",
    "frameskip": 4,
    "repeat_action_probability": 0.25,
    "full_action_space": False,
    "max_num_frames_per_episode": 108000,
}

# ALE runs at 60 frames/s, so one env step (frameskip frames) is this long in game time.
FRAME_MS = 1000 / 60


def env_config(overrides=None):
    cfg = dict(ENV_DEFAULTS)
    cfg.update(overrides or {})
    return cfg


def make_env(cfg):
    env = gym.make(
        cfg["env_id"],
        obs_type=cfg["obs_type"],
        frameskip=cfg["frameskip"],
        repeat_action_probability=cfg["repeat_action_probability"],
        full_action_space=cfg["full_action_space"],
        max_num_frames_per_episode=cfg["max_num_frames_per_episode"],
        # game variation, only when a config names one (the swarm experiment's regime B); default game otherwise
        **{k: cfg[k] for k in ("mode", "difficulty") if k in cfg},
    )
    return env


def action_names(env):
    return list(env.unwrapped.get_action_meanings())


def screen(env):
    """RGB frame (210x160x3) of the last emulated frame."""
    return env.unwrapped.ale.getScreenRGB()


class FrameTap:
    """Read-only proxy around the ALE interface that keeps the last two emulated frames.

    Space Invaders draws enemy bullets only on odd frames and the player's shot only
    on even frames, and with frameskip=4 the observed frame is always even. So without
    this tap, enemy bullets are never seen. Reading the screen has no side effects:
    actions, RNG and rewards are unchanged. AtariEnv.step calls ale.act() once per frame.
    """

    def __init__(self, ale):
        self._ale = ale
        self.frames = []

    def act(self, *args, **kwargs):
        r = self._ale.act(*args, **kwargs)
        self.frames.append(self._ale.getScreenRGB())
        del self.frames[:-2]
        return r

    def __getattr__(self, name):
        return getattr(self._ale, name)


def install_tap(env):
    u = env.unwrapped
    if not isinstance(u.ale, FrameTap):
        u.ale = FrameTap(u.ale)
    return u.ale


def last_two_frames(env):
    """(odd_frame, even_frame) of the last step, labelled by episode frame parity."""
    tap = env.unwrapped.ale
    frames = tap.frames if isinstance(tap, FrameTap) else []
    if len(frames) < 2:
        cur = screen(env)
        return cur, cur
    n = env.unwrapped.ale.getEpisodeFrameNumber()
    last, before = frames[-1], frames[-2]
    return (last, before) if n % 2 == 1 else (before, last)


def versions():
    import importlib.metadata as md

    return {"ale_py_version": md.version("ale-py"), "gymnasium_version": md.version("gymnasium")}
