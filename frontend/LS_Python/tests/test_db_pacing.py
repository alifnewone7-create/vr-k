"""
SQL checks for the agent-owned tables / queries against a REAL Postgres.

Run with a throwaway database:
    DATABASE_URL=postgresql://postgres:pg@localhost:5432/tgtest \
      python -m tests.test_db_pacing

It creates a minimal slice of the panel schema (accounts / jobs / vote tables),
then exercises the queries the agent relies on: the shared pacing gate, the
channel membership map, the view/reaction job payloads and the vote bookkeeping.
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
    db.query(
        "DROP TABLE IF EXISTS vote_casts, vote_targets, channel_members, jobs, "
        "telegram_accounts, agent_pacing CASCADE"
    )
    db.query(
        "CREATE TABLE agent_pacing (id INTEGER PRIMARY KEY, "
        "next_start_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    db.query("INSERT INTO agent_pacing (id) VALUES (1)")
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


def test_paced_slot() -> None:
    """The shared start gate: per-account actions start one-by-one, fleet-wide."""
    first = db.reserve_paced_slot(2.0)
    second = db.reserve_paced_slot(2.0)
    check(f"first caller waits ~0s ({first:.2f})", first < 0.5)
    check(f"the next caller waits the gap ({second:.2f})", 1.5 <= second <= 2.5)
    # Two callers already booked the gate up to +4s; once that has elapsed a
    # fresh caller starts immediately again.
    time.sleep(4.2)
    again = db.reserve_paced_slot(2.0)
    check(f"an idle gate is free again ({again:.2f})", again < 0.5)


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


def test_action_jobs() -> None:
    db.enqueue_view_job(-100123, 11, 4, 5, 9)
    row = db.query("SELECT type, payload FROM jobs ORDER BY id DESC LIMIT 1")[0]
    payload = row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"])
    check("view job queued", row["type"] == "view_post")
    check(f"view payload carries the post + range ({payload})", payload["message_id"] == 11)

    db.enqueue_reaction_job(-100123, 12, 7, ["🔥"], "medium", 5, 1, 2)
    row = db.query("SELECT type, payload FROM jobs ORDER BY id DESC LIMIT 1")[0]
    payload = row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"])
    check("reaction job queued", row["type"] == "react_post")
    check(f"reaction payload carries emojis + range ({payload})", payload["emojis"] == ["🔥"])


def test_vote_casts() -> None:
    db.query(
        "INSERT INTO vote_targets (id, poll_link, chat_id, message_id, status) "
        "VALUES (1, 'https://t.me/demo/5', -100123, 555, 'ready')"
    )
    db.query(
        "INSERT INTO vote_casts (target_id, account_id, option_index, status) VALUES "
        "(1, 1, 2, 'pending'), (1, 2, 0, 'pending')"
    )
    db.set_vote_cast(1, 1, "voted", None)
    rows = db.query("SELECT account_id, status FROM vote_casts WHERE target_id = 1 ORDER BY account_id")
    check(f"cast marked voted ({rows})", rows[0]["status"] == "voted")
    check("the other cast is untouched", rows[1]["status"] == "pending")
    db.set_vote_cast(1, 2, "failed", "POLL_OPTION_INVALID")
    row = db.query("SELECT status, last_error FROM vote_casts WHERE target_id = 1 AND account_id = 2")[0]
    check(f"failure + reason stored ({row})", row["status"] == "failed" and "POLL" in row["last_error"])


if __name__ == "__main__":
    setup_schema()
    test_paced_slot()
    test_channel_members()
    test_action_jobs()
    test_vote_casts()
    print("\nALL DB CHECKS PASSED")
