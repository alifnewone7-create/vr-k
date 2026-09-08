"""
SQL checks for the agent-owned tables / queries against a REAL Postgres.

Run with a throwaway database:
    DATABASE_URL=postgresql://postgres:pg@localhost:5432/tgtest \
      python -m tests.test_db_pacing

It creates a minimal slice of the panel schema (accounts / jobs / vote tables),
then exercises the queries the agent adds on top of it: the per-task pacing gate,
the channel membership map, the combined engage job and the pending-vote lookup.
"""

from __future__ import annotations

import json
import os
import sys
import time

if not os.environ.get("DATABASE_URL"):
    print("DATABASE_URL is required")
    sys.exit(2)

sys.path.insert(0, ".")
from agent import db  # noqa: E402


def check(name: str, ok: bool) -> None:
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        raise SystemExit(1)


def setup_schema() -> None:
    db.query("DROP TABLE IF EXISTS vote_casts, vote_targets, channel_members, jobs, telegram_accounts, agent_pacing_scopes CASCADE")
    db.query(
        """
        CREATE TABLE telegram_accounts (
          id SERIAL PRIMARY KEY,
          status TEXT NOT NULL DEFAULT 'logged_in',
          last_action_at TIMESTAMPTZ,
          cooldown_until TIMESTAMPTZ,
          flood_until TIMESTAMPTZ,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    db.query(
        """
        CREATE TABLE jobs (
          id SERIAL PRIMARY KEY,
          type TEXT NOT NULL,
          account_id INTEGER,
          payload JSONB NOT NULL DEFAULT '{}'::jsonb,
          status TEXT NOT NULL DEFAULT 'queued',
          result JSONB,
          error TEXT,
          attempts INTEGER NOT NULL DEFAULT 0,
          claimed_at TIMESTAMPTZ,
          run_after TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    db.query(
        """
        CREATE TABLE vote_targets (
          id SERIAL PRIMARY KEY,
          poll_link TEXT NOT NULL,
          chat_id BIGINT,
          message_id BIGINT,
          poll_id TEXT,
          status TEXT NOT NULL DEFAULT 'ready',
          last_error TEXT,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    db.query(
        """
        CREATE TABLE vote_casts (
          id SERIAL PRIMARY KEY,
          target_id INTEGER NOT NULL REFERENCES vote_targets(id) ON DELETE CASCADE,
          account_id INTEGER NOT NULL REFERENCES telegram_accounts(id) ON DELETE CASCADE,
          option_index INTEGER NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending',
          last_error TEXT,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE (target_id, account_id)
        )
        """
    )
    db.query("INSERT INTO telegram_accounts (status) SELECT 'logged_in' FROM generate_series(1, 5)")


def test_pacing_scopes() -> None:
    db._PACING_SCOPES_READY = False
    first = db.reserve_paced_slot(2.0, "join:1")
    second = db.reserve_paced_slot(2.0, "join:1")
    third = db.reserve_paced_slot(2.0, "vote:9")
    check(f"first caller of a scope waits ~0s ({first:.2f})", first < 0.5)
    check(f"second caller of the SAME scope waits the gap ({second:.2f})", 1.5 <= second <= 2.5)
    check(f"another task's scope is NOT blocked ({third:.2f})", third < 0.5)
    # Two callers already queued this scope up to +4s; once that has elapsed the
    # gate is idle again and a fresh caller starts immediately.
    time.sleep(4.2)
    again = db.reserve_paced_slot(2.0, "join:1")
    check(f"an idle scope's gate is free again ({again:.2f})", again < 0.5)


def test_channel_members() -> None:
    db._CHANNEL_MEMBERS_READY = False
    db.remember_channel_members(-100123, [1, 2, 3])
    db.remember_channel_members(-100123, [3])  # upsert must not duplicate
    check("members stored", db.get_channel_member_ids(-100123) == [1, 2, 3])
    db.forget_channel_members(-100123, [2])
    check("non-member pruned", db.get_channel_member_ids(-100123) == [1, 3])
    db.query("UPDATE telegram_accounts SET status = 'frozen' WHERE id = 1")
    check("frozen account is not returned", db.get_channel_member_ids(-100123) == [3])
    db.query("UPDATE telegram_accounts SET status = 'logged_in' WHERE id = 1")
    check("unknown channel -> empty", db.get_channel_member_ids(-100999) == [])


def test_engage_job() -> None:
    db.enqueue_engage_job(-100123, [11, 12, 10], 4, 5, 9, 7, ["🔥"], "medium", 5, 1, 2)
    row = db.query("SELECT type, payload FROM jobs ORDER BY id DESC LIMIT 1")[0]
    payload = row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"])
    check("engage job queued", row["type"] == "engage_post")
    check(f"all posts in ONE job, sorted ({payload['message_ids']})", payload["message_ids"] == [10, 11, 12])
    check("legacy message_id kept", payload["message_id"] == 12)
    check("targets carried", (payload["view_target_id"], payload["reaction_target_id"]) == (4, 7))
    db.enqueue_engage_job(-100123, [], 4, 5, 9, 7, [], "medium", 5, 0, 0)
    count = db.query("SELECT count(*) AS n FROM jobs WHERE type = 'engage_post'")[0]["n"]
    check("empty post list queues nothing", int(count) == 1)


def test_pending_vote_lookup() -> None:
    db.query(
        "INSERT INTO vote_targets (id, poll_link, chat_id, message_id, status) "
        "VALUES (1, 'https://t.me/demo/5', -100123, 555, 'ready')"
    )
    db.query(
        "INSERT INTO vote_casts (target_id, account_id, option_index, status) VALUES "
        "(1, 1, 2, 'pending'), (1, 2, 0, 'pending'), (1, 3, 1, 'voted')"
    )
    vote = db.get_pending_vote_for_chat(-100123)
    check(f"pending vote found ({vote})", vote is not None)
    check("only PENDING casts are included", vote["assignments"] == {1: 2, 2: 0})
    check("poll message id carried", vote["message_id"] == 555)
    check("already voted account status", db.get_vote_cast_status(1, 3) == "voted")
    check("unknown cast -> None", db.get_vote_cast_status(1, 5) is None)

    db.set_vote_cast(1, 1, "voted", None)
    vote = db.get_pending_vote_for_chat(-100123)
    check("voted cast drops out of the pending set", vote["assignments"] == {2: 0})
    db.query("UPDATE vote_casts SET status = 'voted' WHERE target_id = 1")
    check("nothing pending -> None", db.get_pending_vote_for_chat(-100123) is None)
    check("other channel -> None", db.get_pending_vote_for_chat(-100777) is None)


if __name__ == "__main__":
    setup_schema()
    test_pacing_scopes()
    test_channel_members()
    test_engage_job()
    test_pending_vote_lookup()
    print("\nALL DB CHECKS PASSED")
