"""
Offline checks for the pacing / channel-cache / membership-map logic.

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

_REAL_PACING_DELAY = userbot._account_pacing_delay


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

    async def vote_poll(self, chat_id, message_id, option_index):
        self.calls.append(f"vote:{option_index}")
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


def _fast_pacing(gap: float = 0.0) -> None:
    """Force a tiny fixed pacing gap so the tests run instantly."""
    userbot._account_pacing_delay = lambda _acc, _gap=gap: _gap  # type: ignore[assignment]
    userbot._ACCOUNT_NEXT_FREE.clear()


def _real_pacing() -> None:
    userbot._account_pacing_delay = _REAL_PACING_DELAY  # type: ignore[assignment]


def test_pacing_profile() -> None:
    _real_pacing()
    check(
        "delay window defaults to 3-20s",
        (userbot.ACCOUNT_DELAY_MIN, userbot.ACCOUNT_DELAY_MAX) == (3.0, 20.0),
    )
    delays = [userbot._account_pacing_delay(i) for i in range(1, 60)]
    check("no pacing delay is below the 3s floor", all(d >= 3.0 for d in delays))
    prof = userbot._account_delay_profile(101)
    check("an account's window is STABLE", prof == userbot._account_delay_profile(101))
    windows = {userbot._account_delay_profile(i) for i in range(1, 30)}
    check(f"different accounts get different windows ({len(windows)} of 29)", len(windows) > 20)


def test_member_pool() -> None:
    userbot._POOL.clear()
    for i in (1, 2, 3, 4):
        userbot._POOL[i] = {"client": FakeClient(i)}
    check("no member map -> whole warm pool", len(userbot._member_pool(None)) == 4)
    pool = userbot._member_pool([2, 3, 99])
    check("member map filters the pool", sorted(a for a, _ in pool) == [2, 3])
    check("members warm on another shard -> empty", userbot._member_pool([99]) == [])


def test_not_member_detection() -> None:
    check(
        "CHANNEL_PRIVATE means not a member",
        userbot._is_not_member_error(RuntimeError("[400 CHANNEL_PRIVATE] the channel is private")),
    )
    check(
        "USER_BANNED_IN_CHANNEL means not a member",
        userbot._is_not_member_error(RuntimeError("[400 USER_BANNED_IN_CHANNEL]")),
    )
    check(
        "a flood wait is NOT a membership problem",
        not userbot._is_not_member_error(RuntimeError("[420 FLOOD_WAIT_X] wait 30 seconds")),
    )


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
    check("cached resolve makes NO GetFullChannel call", c.calls == ["history"])
    check("cached_chat_id() exposes the id", userbot.cached_chat_id("t.me/demo") == -100123)


def test_view_uses_members_and_learns() -> None:
    userbot._POOL.clear()
    clients = {}
    for i in (1, 2, 3):
        clients[i] = FakeClient(i)
        userbot._POOL[i] = {"client": clients[i]}
    # A 4th account that is NOT in the channel any more.
    clients[4] = FakeClient(4, member=False)
    userbot._POOL[4] = {"client": clients[4]}

    _fast_pacing()
    seen: dict = {}

    async def sink(chat_id, ok_ids, bad_ids):
        seen["chat_id"] = chat_id
        seen["ok"] = ok_ids
        seen["bad"] = bad_ids

    userbot.set_membership_sink(sink)

    count = asyncio.run(userbot.view_post_scheduled(-100123, 555, 0.0, member_ids=[1, 2, 3, 4]))
    check(f"3 members viewed ({count})", count == 3)
    check("membership learned for the 3 real members", seen["ok"] == [1, 2, 3])
    check("non-member pruned from the map", seen["bad"] == [4])
    check("the sink got the right channel", seen["chat_id"] == -100123)

    # Only the stored members are used, never the whole fleet.
    for c in clients.values():
        c.calls.clear()
    count = asyncio.run(userbot.view_post_scheduled(-100123, 556, 0.0, member_ids=[1, 2]))
    check(f"only the 2 stored members viewed ({count})", count == 2)
    check("account 3 was not touched", clients[3].calls == [])
    _real_pacing()


def test_view_respects_amount() -> None:
    userbot._POOL.clear()
    for i in range(1, 11):
        userbot._POOL[i] = {"client": FakeClient(i)}
    _fast_pacing()
    userbot.set_membership_sink(None)
    count = asyncio.run(
        userbot.view_post_scheduled(-100123, 777, 0.0, 4, 4, 0, 1, list(range(1, 11)))
    )
    check(f"exactly 4 views for view_min=view_max=4 ({count})", count == 4)
    _real_pacing()


def test_react_flow() -> None:
    userbot._POOL.clear()
    clients = {}
    for i in (1, 2, 3, 4):
        clients[i] = FakeClient(i)
        userbot._POOL[i] = {"client": clients[i]}
    _fast_pacing()

    seen: dict = {}

    async def sink(chat_id, ok_ids, bad_ids):
        seen["ok"] = ok_ids

    userbot.set_membership_sink(sink)
    count = asyncio.run(
        userbot.react_post_scheduled(-100123, 601, ["🔥"], 0.0, 0, 0, 0, 1, [1, 2, 3, 4])
    )
    check(f"every member reacted ({count})", count == 4)
    check("reactors are learned as members", seen["ok"] == [1, 2, 3, 4])

    # Channel with reactions disabled: the 2 probes are blocked and the rest is
    # skipped instead of hammering the post.
    userbot._POOL.clear()
    blocked = {}
    for i in (1, 2, 3, 4, 5):
        blocked[i] = FakeClient(i, can_react=False)
        userbot._POOL[i] = {"client": blocked[i]}
    count = asyncio.run(
        userbot.react_post_scheduled(-100123, 602, ["🔥"], 0.0, 0, 0, 0, 1, [1, 2, 3, 4, 5])
    )
    check(f"blocked channel -> 0 reactions ({count})", count == 0)
    tried = sum(1 for c in blocked.values() if c.calls)
    check(f"only the 2 probes were tried, not all 5 ({tried})", tried == 2)
    _real_pacing()


def test_react_amount_split_across_shards() -> None:
    userbot._POOL.clear()
    for i in range(1, 21):
        userbot._POOL[i] = {"client": FakeClient(i)}
    _fast_pacing()
    userbot.set_membership_sink(None)
    totals = []
    for shard in range(3):
        totals.append(
            asyncio.run(
                userbot.react_post_scheduled(
                    -100123, 900, ["👍"], 0.0, 7, 7, shard, 3, list(range(1, 21))
                )
            )
        )
    check(f"3 shards together send exactly 7 reactions ({totals})", sum(totals) == 7)
    _real_pacing()


def test_accounts_act_one_by_one() -> None:
    """Inside one post the userbots drip in order, each after its own gap."""
    userbot._POOL.clear()
    stamps: list[tuple[int, float]] = []

    class StampClient(FakeClient):
        async def invoke(self, _query):
            stamps.append((self.acc_id, asyncio.get_running_loop().time()))
            return True

    for i in (1, 2, 3):
        userbot._POOL[i] = {"client": StampClient(i)}

    gap = 0.3
    _fast_pacing(gap)
    userbot.set_membership_sink(None)
    asyncio.run(userbot.view_post_scheduled(-100123, 700, 0.0, member_ids=[1, 2, 3]))
    check(f"all 3 acted ({stamps})", len(stamps) == 3)
    ok = all(stamps[i + 1][1] - stamps[i][1] >= gap * 0.9 for i in range(len(stamps) - 1))
    check("each userbot acted at least one gap after the previous one", ok)
    _real_pacing()


def test_two_channels_run_in_parallel() -> None:
    """A second channel's task must not queue behind the first one's whole run."""
    userbot._POOL.clear()
    for i in range(1, 5):
        userbot._POOL[i] = {"client": FakeClient(i)}
    gap = 0.3
    _fast_pacing(gap)
    userbot.set_membership_sink(None)

    async def _two_channels():
        started = asyncio.get_running_loop().time()
        await asyncio.gather(
            userbot.view_post_scheduled(-100111, 1, 0.0, member_ids=[1, 2, 3, 4]),
            userbot.view_post_scheduled(-100222, 1, 0.0, member_ids=[1, 2, 3, 4]),
        )
        return asyncio.get_running_loop().time() - started

    elapsed = asyncio.run(_two_channels())
    # Serialised fleet-wide this would take ~8 gaps; in parallel it is ~4.
    check(f"two channels finish in parallel ({elapsed:.2f}s < {gap * 7:.2f}s)", elapsed < gap * 7)
    _real_pacing()


if __name__ == "__main__":
    test_pacing_profile()
    test_member_pool()
    test_not_member_detection()
    test_channel_cache()
    test_view_uses_members_and_learns()
    test_view_respects_amount()
    test_react_flow()
    test_react_amount_split_across_shards()
    test_accounts_act_one_by_one()
    test_two_channels_run_in_parallel()
    print("\nALL CHECKS PASSED")
