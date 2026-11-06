"""Settings from .env (KEY=VALUE per line); a real environment variable wins."""
import os

from paths import ROOT

ENV_PATH = ROOT / ".env"


def get(name):
    if name in os.environ:
        return os.environ[name]
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == name:
                return value.strip().strip("'\"")
    return ""
