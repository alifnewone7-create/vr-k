# PRD — Telegram Ultra (cloned repo deployment)

## Original problem statement
Clone https://github.com/alifnewone7-create/a-v-k.git (public), copy all files/folders into /app, run the frontend, change nothing. Frontend .env already contains backend (Neon Postgres) connection.

## What was done (2026-09-08)
- Cloned the repo and copied all files/folders (frontend, backend, tests, test_reports, memory, design_guidelines.json, README) into /app, replacing the default template.
- Frontend: Next.js 16 app (app router), deps installed with pnpm 9 using the repo's pnpm-lock.yaml (frozen). Runs on port 3000 via supervisor (`yarn start` -> `next dev`).
- Backend: FastAPI transparent reverse proxy on :8001 forwarding /api/* to Next.js :3000 (installed `httpx`).
- No repo file was modified (pnpm-workspace.yaml was only temporarily moved during install, then restored).
- Verified: https://2dce9fe2-b84d-4144-a79b-cec13960e418.preview.emergentagent.com redirects to /login and renders the Telegram Ultra login page; /api proxy responds (401 without session = auth working).

## Data
- Neon Postgres via DATABASE_URL in /app/frontend/.env (external, managed by repo owner).
- TGLion API credentials in same .env.

## Bug fix (2026-09-08): login did not redirect after sign in
- RCA: Next.js 16 Server Actions aborted because ingress sent x-forwarded-host=*.preview.emergentagent.com while browser Origin was *.cluster-5.preview.emergentcf.cloud (two-level subdomain not covered by existing wildcards).
- Fix: added `*.cluster-5.preview.emergentagent.com` and `*.cluster-5.preview.emergentcf.cloud` to `allowedDevOrigins` and `experimental.serverActions.allowedOrigins` in /app/frontend/next.config.mjs; restarted frontend.
- Verified by testing agent (iteration_3.json, 100% frontend pass): correct creds redirect to dashboard, wrong creds show error, all 8 sidebar sections render. Sign-out (2-step confirm dialog) verified via playwright. Login creds in /app/memory/test_credentials.md.

## Known notes / backlog
- HMR websocket from the preview domain is blocked (allowedDevOrigins wildcard doesn't cover two-level subdomain `avk-preview.cluster-5.preview.emergentcf.cloud`). App works fine; only dev hot-reload affected. Left unchanged per "do not change anything".
- P0 remaining: none. P1: none requested.

## Reverted to the auto-km agent base + kept the channel cache/membership map (2026-06)
User instruction: `auto-km/frontend/LS_Python/agent` er file gulo copy kore use koro, **shudhu channel resolve cache + channel_members map rakho**.

- Copied all 7 files of `auto-km/frontend/LS_Python/agent` over `/app/frontend/LS_Python/agent` (fixed the repo's stray `+` on worker.py line 1).
- Dropped with it (was in the previous a-v-k build): combined `engage_post` job (multi-post + vote in one visit), `engage_posts_scheduled`, scoped `action_turn`, `agent_pacing_scopes` per-task gate, `job_pacing_scope`, `get_pending_vote_for_chat` / `get_vote_cast_status`, `enqueue_engage_job`. `lib/types.ts` reverted (no `engage_post` job type).
- Re-applied on top (user asked to keep): channel info cache (`_CHANNEL_INFO`, `AGENT_CHANNEL_INFO_TTL`, resolve fast path, cache on join/get_chat, `cached_chat_id`) and the membership map (`channel_members` table + `remember/forget/get_channel_member_ids`, `set_membership_sink`, `_note_membership`, `_is_not_member_error`, `_member_pool`, wired into `view_post_scheduled` / `react_post_scheduled` / `handle_join_channel` / worker `main()`).
- Kept from the user's earlier explicit asks: `LS_WORKER_SHARDS` default **10**, and the per-action console logs (`[view]/[react]/[vote]` lines + summaries, `AGENT_VERBOSE`, line-buffered stdout in `agent/__init__.py`), `[OK] job ...` lines now carry the counts.
- Pacing is now purely auto-km's: per-account stable 3-20s window, sequential drip inside one post (`AGENT_SEQUENTIAL_ACTIONS`), single shared `agent_pacing` gate at 3-5s for per-account jobs.

Verification
- `python -m tests.test_engage_flow` — 30 checks (fake pyrogram): pacing profile, member pool, not-member detection, channel cache, view learns/prunes membership, view amount, reaction flow + blocked-channel probe, shard split of amounts, one-by-one drip, two channels in parallel.
- `DATABASE_URL=... python -m tests.test_db_pacing` — 15 checks (real Postgres): shared pacing gate, membership map, view/react job payloads, vote cast bookkeeping.
- `DATABASE_URL=... python -m tests.test_worker_jobs` — real Postgres + fake Telegram: `handle_view_post` / `handle_react_post` use only stored members, learn/prune, bump counters.

## Agent speed + combined-engagement rework (2026-06, LS_Python)
User report: "new task ashle ager gulo onek slow kore kaj kore" + wants multi-post/vote done in one channel visit, shard 7 -> 10, and everything visible in the VPS console. Reference repo for pacing logic: https://github.com/alifnewone7-create/auto-km.git (`frontend/LS_Python/agent`).

RCA (why it was slow)
1. `userbot.action_turn` had a FLEET-WIDE global lock (`AGENT_GLOBAL_ONE_BY_ONE=1`): only one userbot in the whole agent could act, then 4-5s of silence. 2 channels x 3 posts x 50 accounts = 300 turns in ONE line (~22 min); a new task queued behind all of it.
2. `db.reserve_paced_slot` was ONE shared row (`agent_pacing` id=1): across all shards only 1 per-account job (vote/join/DM) could start per gap -> ~13 actions/min for the whole fleet, and every task competed in the same line.
3. One job per post: the same account re-opened the channel for every post and paid the gap again each time.

What changed
- `userbot.py`: restored the repo's per-account STABLE delay window (`AGENT_ACCOUNT_DELAY_MIN/MAX`, default 3-20s, derived from account id). `action_turn(account_id, scope)` is now SCOPED (default scope = `chat:<id>`): one-by-one inside a channel/task, different channels/tasks in parallel. `AGENT_GLOBAL_ONE_BY_ONE=1` restores the old single line.
- `userbot.engage_posts_scheduled(chat_id, message_ids, ..., vote=..., vote_sink=...)`: ONE visit per userbot = view + react for EVERY new post + its pending poll vote. `engage_post_scheduled` is now a single-post wrapper. Reaction preset (fast/medium/slow/custom) still spreads the visits when the window is wider than the natural gaps.
- `worker.py`: `dispatch_views_for_target` / `dispatch_reactions_for_target` queue ONE `engage_post` job for the whole batch of posts (view-only, reaction-only and combined all go through it). `handle_engage_post` looks up `db.get_pending_vote_for_chat` and casts votes in the same visit; `handle_cast_vote` skips a cast that is already `voted`. New `job_pacing_scope(job)` gives every task its own paced line (`vote:<id>`, `join:<id>`, `live:<id>`, `dm:<id>`, `profile`). Dispatch gap back to repo default 3-5s.
- `db.py`: `reserve_paced_slot(gap, scope)` now uses a new agent-owned table `agent_pacing_scopes` (idempotent, created at startup); added `get_pending_vote_for_chat`, `get_vote_cast_status`; `enqueue_engage_job` takes `message_ids` + nullable view/reaction target ids.
- `supervisor.py` + docs: default `LS_WORKER_SHARDS=10` (docs recommend `AGENT_DB_POOL_MAX=6` -> 60 connections).
- Console logging: `AGENT_VERBOSE=1` (default) prints every view/react/vote per account with the exact Telegram error on failure, plus per-post/visit summaries; `agent/__init__.py` line-buffers stdout/stderr; job completion lines now include the counts.

Verification (no Telegram/Neon needed)
- `python -m tests.test_engage_flow` (39 checks, fake pyrogram) — pacing profile, shard split, membership pool, channel cache, one-visit engage, multi-post single visit, vote in same visit, same-channel gap kept, different channels run in parallel.
- `DATABASE_URL=... python -m tests.test_db_pacing` (21 checks, real Postgres) — scoped pacing gate, membership map, engage job payload, pending-vote lookup.
- `DATABASE_URL=... python -m tests.test_engage_job` (real Postgres + fake Telegram) — full job flow incl. counters, vote_casts, cast_vote skip, reaction-only mode.

## Next action items
- User to sign in with their username/password/secret to use the dashboard.
