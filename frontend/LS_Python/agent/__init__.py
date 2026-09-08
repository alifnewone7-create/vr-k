# Iamhear userbot agent package.
#
# CONFIG LOADING HAPPENS HERE, ONCE.
#
# It must happen in this file (and not in each entrypoint) because
# `agent/db.py` reads DATABASE_URL at *import* time. Every way of starting the
# agent goes through this package first:
#
#     python -m agent.worker
#     python -m agent.supervisor
#
# ...so both of them now see exactly the same config. Previously only
# `agent/worker.py` loaded the env files, which meant `agent/supervisor.py`
# silently ignored `LS_WORKER_SHARDS` / `LS_SHARD_RESTART_BACKOFF` from `.env`
# when started by systemd (no shell env to inherit).
#
# PRIORITY (highest first):
#   1. Real process environment  (systemd `Environment=`, or `FOO=1 python -m ...`)
#   2. `.env`            <- THE config file. Edit this one.
#   3. `.env.vps`        <- optional legacy extra; only fills values `.env` did
#                           not set. It can no longer override `.env`.
#   4. `.env` in the current working directory (last resort)
#
# NOTE: `.env.vps.example` is only a template full of placeholders
# (ep-xxxxxxxxxxxx.neon.tech ...) and is never loaded.

from pathlib import Path

from dotenv import load_dotenv

_LS_ROOT = Path(__file__).resolve().parent.parent

# 2) Main config. `override=False` keeps the real environment on top.
load_dotenv(_LS_ROOT / ".env")

# 3) Optional legacy `.env.vps`. Loaded WITHOUT override, so `.env` wins.
_vps_env = _LS_ROOT / ".env.vps"
if _vps_env.exists():
    load_dotenv(_vps_env)

# 4) Whatever `.env` sits in the current working directory.
load_dotenv()
