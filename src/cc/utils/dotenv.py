"""
Load environment variables from ~/.cc-cli/.env.

Simple KEY=VALUE parser — no shell expansion, no quotes required.
Lines starting with # are comments. Blank lines are ignored.
Only sets vars that are not already in the environment (env vars take precedence).
"""
import os

from cc.utils.constants import Constants

_ENV_FILE = os.path.join(Constants.PATH_USER_DATA, ".env")


def load():
    if not os.path.isfile(_ENV_FILE):
        return

    with open(_ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value
