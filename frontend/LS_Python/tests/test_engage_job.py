"""
End-to-end check of the combined engage job against a REAL Postgres.

Telegram is faked (pyrogram is stubbed, the userbot pool is filled with fake
clients), the database is real, so this exercises the actual flow:

    new posts -> ONE engage job -> every userbot visits the channel ONCE and
    views + reacts to all the posts and casts its pending poll vote -> counters
    and vote_casts are updated.

Run with a throwaway database:
    DATABASE_URL=postgresql://postgres:pg@localhost:5432/tgtest \
      python -m tests.test_engage_job
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
    def __init__(self, acc_id: int):
        self.acc_id = acc_id
        self.calls: list[str] = []

    async def resolve_peer(self, chat_id):
        return f"peer:{chat_id}"

    async def invoke(self, _q):
        self.calls.append("view")
        return True

    async def send_reaction(self, chat_id, message_id, emoji=None):
        self.calls.append("react")
        return True

    async def vote_poll(self, chat_id, message_id, option_index):
        self.calls.append(f"vote:{option_index}")
        return True


def setup_schema() -> None:
    db.query(
        "DROP TABLE IF EXISTS vote_casts, vote_targets, channel_members, jobs, "
        "reaction_targets, view_targets, telegram_accounts, agent_pacing_scopes CASCADE"
    )
    db.query(
        "CREATE TABLE telegram_accounts (id SERIAL PRIMARY KEY, status TEXT NOT NULL DEFAULT 'logged_in', "
        "updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"
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
        "CREATE TABLE reaction_targets (id SERIAL PRIMARY KEY, reactions_sent INTEGER NOT NULL DEFAULT 0, "
        "last_error TEXT, last_checked_at TIMESTAMPTZ, updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    db.query(
        "CREATE TABLE vote_targets (id SERIAL PRIMARY KEY, poll_link TEXT NOT NULL, chat_id BIGINT, "
        "message_id BIGINT, status TEXT NOT NULL DEFAULT 'ready', updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    db.query(
        "CREATE TABLE vote_casts (id SERIAL PRIMARY KEY, "
        "target_id INTEGER NOT NULL REFERENCES vote_targets(id) ON DELETE CASCADE, "
        "account_id INTEGER NOT NULL REFERENCES telegram_accounts(id) ON DELETE CASCADE, "
        "option_index INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', last_error TEXT, "
        "updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE (target_id, account_id))"
    )
    db.query("INSERT INTO telegram_accounts (status) SELECT 'logged_in' FROM generate_series(1, 3)")
    db.query("INSERT INTO view_targets (id) VALUES (1)")
    db.query("INSERT INTO reaction_targets (id) VALUES (1)")
    db.query(
        "INSERT INTO vote_targets (id, poll_link, chat_id, message_id, status) "
        "VALUES (1, 'https://t.me/demo/9', -100123, 900, 'ready')"
    )
    db.query(
        "INSERT INTO vote_casts (target_id, account_id, option_index, status) VALUES "
        "(1, 1, 1, 'pending'), (1, 2, 0, 'pending')"
    )
    db._CHANNEL_MEMBERS_READY = False
    db._PACING_SCOPES_READY = False
    db.remember_channel_members(-100123, [1, 2, 3])


def main() -> None:
    setup_schema()

    clients = {}
    userbot._POOL.clear()
    for i in (1, 2, 3):
        clients[i] = FakeClient(i)
        userbot._POOL[i] = {"client": clients[i]}
    userbot.set_membership_sink(worker.remember_membership)

    # What the view poller queues when 2 posts land on a channel that has BOTH
    # auto-view and auto-reaction on.
    db.enqueue_engage_job(-100123, [31, 32], 1, 0, 0, 1, ["🔥"], "fast", 5, 0, 0)
    row = db.query("SELECT id, type, payload FROM jobs ORDER BY id DESC LIMIT 1")[0]
    check("exactly ONE job for both posts", int(db.query("SELECT count(*) AS n FROM jobs")[0]["n"]) == 1)

    result = asyncio.run(worker.handle_engage_post({"id": row["id"], "type": "engage_post", "payload": row["payload"]}))
    print("job result:", result)

    check(f"3 userbots x 2 posts = 6 views ({result})", result["views"] == 6)
    check("3 userbots x 2 posts = 6 reactions", result["reactions"] == 6)
    check("2 pending votes were cast in the same visit", result["votes"] == 2)
    check(
        "account 1 did both posts and its vote in ONE visit",
        clients[1].calls == ["view", "react", "view", "react", "vote:1"],
    )
    check("account 3 had no vote pending", clients[3].calls == ["view", "react", "view", "react"])

    views_sent = db.query("SELECT views_sent FROM view_targets WHERE id = 1")[0]["views_sent"]
    reactions_sent = db.query("SELECT reactions_sent FROM reaction_targets WHERE id = 1")[0]["reactions_sent"]
    check(f"view counter bumped ({views_sent})", int(views_sent) == 6)
    check(f"reaction counter bumped ({reactions_sent})", int(reactions_sent) == 6)
    check("cast rows marked voted", db.get_vote_cast_status(1, 1) == "voted" and db.get_vote_cast_status(1, 2) == "voted")
    check("nothing pending left on the poll", db.get_pending_vote_for_chat(-100123) is None)

    # The separate cast_vote job that the website queued must now do NOTHING.
    skipped = asyncio.run(
        worker.handle_cast_vote(
            {
                "id": 999,
                "type": "cast_vote",
                "account_id": 1,
                "payload": {"target_id": 1, "chat_id": -100123, "message_id": 900, "option_index": 1},
            }
        )
    )
    check(f"queued cast_vote job skips the already-cast vote ({skipped})", skipped["stage"] == "already_voted")

    # Reaction-only channel: no view target -> no views, reactions only.
    for c in clients.values():
        c.calls.clear()
    db.enqueue_engage_job(-100123, [40], None, 0, 0, 1, ["👍"], "fast", 5, 0, 0)
    row = db.query("SELECT id, payload FROM jobs ORDER BY id DESC LIMIT 1")[0]
    result = asyncio.run(worker.handle_engage_post({"id": row["id"], "type": "engage_post", "payload": row["payload"]}))
    check(f"reaction-only job registers no views ({result})", result["views"] == 0)
    check("reaction-only job reacts from every member", result["reactions"] == 3)
    check("no view call was made", all(c.calls == ["react"] for c in clients.values()))

    print("\nALL ENGAGE JOB CHECKS PASSED")


if __name__ == "__main__":
    main()
