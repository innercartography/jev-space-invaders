"""Load only the named secrets from the env file into os.environ. Never prints values."""
import os
from pathlib import Path

DEFAULT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def load(names, env_file=None):
    """Returns the loaded values (for the trace leak guard). Existing env vars win."""
    path = Path(env_file) if env_file else DEFAULT_ENV_FILE
    file_vals = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                file_vals[k.strip()] = v.strip().strip('"').strip("'")
    loaded = []
    for n in names:
        v = os.environ.get(n) or file_vals.get(n)
        if not v:
            raise SystemExit(f"{n} is not set (env var or {path}).")
        os.environ[n] = v
        loaded.append(v)
    return loaded
