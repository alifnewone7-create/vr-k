"""
End-to-end check of the view / reaction jobs against a REAL Postgres.

Telegram is faked (pyrogram is stubbed, the userbot pool is filled with fake
clients), the database is real, so this exercises the actual flow:

    new post -> view_post / react_post job -> only the userbots stored as
    members of that channel act -> counters update and the membership map
    learns/prunes accounts by itself.

Run with a throwaway database:
    DATABASE_URL=postgresql://postgres:pg@localhost:5432/tgtest \
      python -m tests.test_worker_jobs
"""

from __future__ import annotations

import asyncio
import os
import sys
import types
from unittest.mock import MagicMock

if not os.environ.get("DATABASE_URL"):
    print("DATABASE_URL is required")
    sys.exit(2)


class _AnyModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        sub = _AnyModule(f"{self.__name__}.{name}")
        setattr(self, name, sub)
        return sub


class _Finder:
    PREFIXES = ("pyrogram", "pytgcalls", "ntgcalls", "tgcrypto")

    def find_module(self, fullname, path=None):
        return self if fullname.split(".")[0] in self.PREFIXES else None

    def load_module(self, fullname):
        mod = _AnyModule(fullname)
        mod.__path__ = []
        sys.modules[fullname] = mod
        return mod


sys.meta_path.insert(0, _Finder())
sys.path.insert(0, ".")

from agent import db, userbot, worker  # noqa: E402

userbot.Client = MagicMock  # type: ignore[assignment]
userbot.GetMessagesViews = lambda **kw: kw  # type: ignore[assignment]
userbot._account_pacing_delay = lambda _acc: 0.0  # type: ignore[assignment]


def check(name: str, ok: bool) -> None:
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        raise SystemExit(1)


class FakeClient:
    def __init__(self, acc_id: int, *, member: bool = True):
        self.acc_id = acc_id
        self.member = member
        self.calls: list[str] = []

    async def resolve_peer(self, chat_id):
        return f"peer:{chat_id}"

    async def invoke(self, _q):
        self.calls.append("view")
        if not self.member:
            raise RuntimeError("[400 CHANNEL_PRIVATE] the channel is private")
        return True

    async def send_reaction(self, chat_id, message_id, emoji=None):
        self.calls.append("react")
        return True


def setup_schema() -> None:
    db.query(
        "DROP TABLE IF EXISTS channel_members, jobs, reaction_targets, view_targets, "
        "telegram_accounts CASCADE"
    )
    db.query(
        "CREATE TABLE telegram_accounts (id SERIAL PRIMARY KEY, status TEXT NOT NULL "
        "DEFAULT 'logged_in', updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    db.query(
        "CREATE TABLE jobs (id SERIAL PRIMARY KEY, type TEXT NOT NULL, account_id INTEGER, "
        "payload JSONB NOT NULL DEFAULT '{}'::jsonb, status TEXT NOT NULL DEFAULT 'queued', "
        "result JSONB, error TEXT, attempts INTEGER NOT NULL DEFAULT 0, claimed_at TIMESTAMPTZ, "
        "run_after TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), "
        "updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    db.query(
        "CREATE TABLE view_targets (id SERIAL PRIMARY KEY, views_sent INTEGER NOT NULL DEFAULT 0, "
        "last_error TEXT, last_checked_at TIMESTAMPTZ, updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    db.query(
        "CREATE TABLE reaction_targets (id SERIAL PRIMARY KEY, reactions_sent INTEGER NOT NULL "
        "DEFAULT 0, last_error TEXT, last_checked_at TIMESTAMPTZ, "
        "updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    db.query("INSERT INTO telegram_accounts (status) SELECT 'logged_in' FROM generate_series(1, 4)")
    db.query("INSERT INTO view_targets (id) VALUES (1)")
    db.query("INSERT INTO reaction_targets (id) VALUES (1)")
    db._CHANNEL_MEMBERS_READY = False


def main() -> None:
    setup_schema()

    clients = {}
    userbot._POOL.clear()
    for i in (1, 2, 3):
        clients[i] = FakeClient(i)
        userbot._POOL[i] = {"client": clients[i]}
    clients[4] = FakeClient(4, member=False)  # left the channel
    userbot._POOL[4] = {"client": clients[4]}
    userbot.set_membership_sink(worker.remember_membership)

    # Nothing learned yet -> the whole warm pool is tried and the map fills in.
    db.enqueue_view_job(-100123, 31, 1, 0, 0)
    row = db.query("SELECT id, type, payload FROM jobs ORDER BY id DESC LIMIT 1")[0]
    result = asyncio.run(worker.handle_view_post({"id": row["id"], "type": row["type"], "payload": row["payload"]}))
    check(f"3 real members registered a view ({result})", result["views"] == 3)
    check("membership map learned the 3 members", db.get_channel_member_ids(-100123) == [1, 2, 3])
    check(
        f"view counter bumped ({db.query('SELECT views_sent FROM view_targets WHERE id = 1')[0]})",
        int(db.query("SELECT views_sent FROM view_targets WHERE id = 1")[0]["views_sent"]) == 3,
    )

    # Second post: the pruned account #4 must not be tried again.
    for c in clients.values():
        c.calls.clear()
    db.enqueue_view_job(-100123, 32, 1, 0, 0)
    row = db.query("SELECT id, type, payload FROM jobs ORDER BY id DESC LIMIT 1")[0]
    result = asyncio.run(worker.handle_view_post({"id": row["id"], "type": row["type"], "payload": row["payload"]}))
    check(f"only the stored members viewed ({result})", result["views"] == 3)
    check("the non-member was NOT tried again", clients[4].calls == [])

    # Reactions use the same membership map.
    for c in clients.values():
        c.calls.clear()
    db.enqueue_reaction_job(-100123, 33, 1, ["🔥"], "fast", 5, 0, 0)
    row = db.query("SELECT id, type, payload FROM jobs ORDER BY id DESC LIMIT 1")[0]
    result = asyncio.run(worker.handle_react_post({"id": row["id"], "type": row["type"], "payload": row["payload"]}))
    check(f"3 members reacted ({result})", result["reactions"] == 3)
    check("non-member not asked to react", clients[4].calls == [])
    check(
        "reaction counter bumped",
        int(db.query("SELECT reactions_sent FROM reaction_targets WHERE id = 1")[0]["reactions_sent"]) == 3,
    )

    print("\nALL WORKER JOB CHECKS PASSED")


if __name__ == "__main__":
    main()
