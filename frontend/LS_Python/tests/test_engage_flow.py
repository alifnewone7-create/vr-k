"""
Offline checks for the pacing / channel-cache / combined-engagement logic.

Pyrogram + pytgcalls are NOT installed here (they only live on the VPS), so the
telegram libs are stubbed and the agent's pure logic is exercised with fake
clients. Run with:  python -m tests.test_engage_flow   (from LS_Python/)
"""

from __future__ import annotations

import asyncio
import sys
import types
from unittest.mock import MagicMock


# --- stub the telegram libraries so agent.userbot can be imported ------------
class _AnyModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        sub = _AnyModule(f"{self.__name__}.{name}")
        setattr(self, name, sub)
        return sub


class _Finder:
    PREFIXES = ("pyrogram", "pytgcalls", "ntgcalls", "tgcrypto", "psycopg", "psycopg_pool", "dotenv")

    def find_module(self, fullname, path=None):
        return self if fullname.split(".")[0] in self.PREFIXES else None

    def load_module(self, fullname):
        mod = _AnyModule(fullname)
        mod.__path__ = []
        sys.modules[fullname] = mod
        return mod


sys.meta_path.insert(0, _Finder())
sys.modules.setdefault("agent", types.ModuleType("agent"))
sys.modules["agent"].__path__ = ["agent"]

from agent import userbot  # noqa: E402

# The Client symbol is only used for type hints at runtime here.
userbot.Client = MagicMock  # type: ignore[assignment]
# Raw TL constructor -> plain dict so the fake client can be invoked.
userbot.GetMessagesViews = lambda **kw: kw  # type: ignore[assignment]


class FakeClient:
    """Minimal stand-in for a warm pyrogram client."""

    def __init__(self, acc_id: int, *, member: bool = True, can_react: bool = True):
        self.acc_id = acc_id
        self.member = member
        self.can_react = can_react
        self.calls: list[str] = []

    async def resolve_peer(self, chat_id):
        return f"peer:{chat_id}"

    async def invoke(self, _query):
        self.calls.append("view")
        if not self.member:
            raise RuntimeError("[400 CHANNEL_PRIVATE] the channel is private")
        return True

    async def send_reaction(self, chat_id, message_id, emoji=None):
        self.calls.append("react")
        if not self.can_react:
            raise RuntimeError("[400 REACTIONS_ALL_DISABLED]")
        return True

    async def get_chat(self, ref):
        self.calls.append(f"get_chat:{ref}")
        chat = MagicMock()
        chat.id = -100123
        chat.title = "Demo Channel"
        chat.username = "demo"
        return chat

    def get_chat_history(self, chat_id, limit=1):
        self.calls.append("history")

        async def _gen():
            msg = MagicMock()
            msg.id = 42
            yield msg

        return _gen()


def check(name: str, ok: bool) -> None:
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        raise SystemExit(1)


def test_pacing_gap() -> None:
    check("gap defaults to 4-4.5s", (userbot.ACCOUNT_GAP_MIN, userbot.ACCOUNT_GAP_MAX) == (4.0, 4.5))
    delays = [userbot._account_pacing_delay(i) for i in range(50)]
    check("every pacing delay is inside 4-4.5s", all(4.0 <= d <= 4.5 for d in delays))


def test_shard_share() -> None:
    check("view_max=0 means everyone", userbot._shard_share(0, 0, "k", 0, 1, 10) is None)
    n = userbot._shard_share(5, 5, "k", 0, 1, 50)
    check("fixed range gives exact count", n == 5)
    shares = [userbot._shard_share(7, 7, "k", i, 3, 50) for i in range(3)]
    check(f"shares split across shards sum to total ({shares})", sum(shares) == 7)
    capped = userbot._shard_share(40, 40, "k", 0, 1, 6)
    check("count is capped by the member pool", capped == 6)


def test_member_pool() -> None:
    userbot._POOL.clear()
    for i in (1, 2, 3, 4):
        userbot._POOL[i] = {"client": FakeClient(i)}
    check("no member map -> whole warm pool", len(userbot._member_pool(None)) == 4)
    pool = userbot._member_pool([2, 3, 99])
    check("member map filters the pool", sorted(a for a, _ in pool) == [2, 3])
    check("members warm on another shard -> empty", userbot._member_pool([99]) == [])


def test_channel_cache() -> None:
    userbot._CHANNEL_INFO.clear()
    userbot._POOL.clear()
    c = FakeClient(1)
    userbot._POOL[1] = {"client": c}

    chat_id, title, latest = asyncio.run(userbot.resolve_channel_latest("t.me/demo"))
    check("first resolve returns channel info", (chat_id, title, latest) == (-100123, "Demo Channel", 42))
    check("first resolve used get_chat", any(x.startswith("get_chat") for x in c.calls))

    c.calls.clear()
    chat_id2, title2, latest2 = asyncio.run(userbot.resolve_channel_latest("t.me/demo"))
    check("cached resolve returns the same info", (chat_id2, title2, latest2) == (chat_id, title, 42))
    check(
        "cached resolve makes NO GetFullChannel call",
        c.calls == ["history"],
    )
    check("cached_chat_id() exposes the id", userbot.cached_chat_id("t.me/demo") == -100123)


def test_engage_one_visit() -> None:
    userbot._POOL.clear()
    clients = {}
    for i in (1, 2, 3):
        clients[i] = FakeClient(i)
        userbot._POOL[i] = {"client": clients[i]}
    # A 4th account that is NOT in the channel any more.
    clients[4] = FakeClient(4, member=False)
    userbot._POOL[4] = {"client": clients[4]}

    # Keep the test fast: 0s gap instead of the real 4s.
    userbot.ACCOUNT_GAP_MIN = userbot.ACCOUNT_GAP_MAX = 0.0

    seen: dict = {}

    async def sink(chat_id, ok_ids, bad_ids):
        seen["chat_id"] = chat_id
        seen["ok"] = ok_ids
        seen["bad"] = bad_ids

    userbot.set_membership_sink(sink)

    result = asyncio.run(
        userbot.engage_post_scheduled(
            -100123,
            555,
            emojis=["👍"],
            member_ids=[1, 2, 3, 4],
        )
    )
    check(f"3 members viewed ({result})", result["views"] == 3)
    check("3 members reacted", result["reactions"] == 3)
    for i in (1, 2, 3):
        check(f"account {i} viewed then reacted in ONE visit", clients[i].calls == ["view", "react"])
    check("non-member did not get a reaction attempt", clients[4].calls == ["view"])
    check("membership learned for the 3 real members", seen["ok"] == [1, 2, 3])
    check("non-member pruned from the map", seen["bad"] == [4])

    userbot.ACCOUNT_GAP_MIN, userbot.ACCOUNT_GAP_MAX = 4.0, 4.5


def test_engage_respects_amounts() -> None:
    userbot._POOL.clear()
    for i in range(1, 11):
        userbot._POOL[i] = {"client": FakeClient(i)}
    userbot.ACCOUNT_GAP_MIN = userbot.ACCOUNT_GAP_MAX = 0.0
    userbot.set_membership_sink(None)

    result = asyncio.run(
        userbot.engage_post_scheduled(
            -100123,
            777,
            view_min=4,
            view_max=4,
            emojis=["🔥"],
            react_min=2,
            react_max=2,
            member_ids=list(range(1, 11)),
        )
    )
    check(f"exactly 4 views ({result})", result["views"] == 4)
    check("exactly 2 reactions", result["reactions"] == 2)
    userbot.ACCOUNT_GAP_MIN, userbot.ACCOUNT_GAP_MAX = 4.0, 4.5


def test_two_posts_keep_the_gap() -> None:
    """Two posts arriving together must NOT make one account act twice at once."""
    userbot._POOL.clear()
    stamps: dict[int, list[float]] = {1: [], 2: []}

    class StampClient(FakeClient):
        async def invoke(self, _query):
            stamps[self.acc_id].append(asyncio.get_running_loop().time())
            return True

    for i in (1, 2):
        userbot._POOL[i] = {"client": StampClient(i)}

    gap = 0.3
    userbot.ACCOUNT_GAP_MIN = userbot.ACCOUNT_GAP_MAX = gap
    userbot._ACCOUNT_NEXT_FREE.clear()
    userbot.set_membership_sink(None)

    async def _both():
        await asyncio.gather(
            userbot.engage_post_scheduled(-100123, 901, emojis=[], member_ids=[1, 2]),
            userbot.engage_post_scheduled(-100123, 902, emojis=[], member_ids=[1, 2]),
        )

    asyncio.run(_both())
    ok = all(len(v) == 2 and (v[1] - v[0]) >= gap * 0.9 for v in stamps.values())
    check(f"same account's two posts are >= gap apart ({stamps})", ok)
    userbot.ACCOUNT_GAP_MIN, userbot.ACCOUNT_GAP_MAX = 4.0, 4.5


if __name__ == "__main__":
    test_pacing_gap()
    test_shard_share()
    test_member_pool()
    test_channel_cache()
    test_engage_one_visit()
    test_engage_respects_amounts()
    test_two_posts_keep_the_gap()
    print("\nALL CHECKS PASSED")
