# tgultra — VPS Setup & Run Guide (LS_Python agent)

Ei agent-ta VPS-e **`/root/tgultra`** folder-e source hisebe chole, ar
**`systemd`** diye 24/7 chalu thake (service name: **`tgultra`**).

Panel (website) job DB-te likhe, ei agent shei job gula tule Telegram-e kaj kore.
Duijon **ekoi PostgreSQL/Neon DB** share kore — tai `DATABASE_URL` duijoner ek-i
hote HOBE.

---

## 0. Ki lagbe

| Ki | Koto |
|---|---|
| OS | Ubuntu 22.04 / 24.04 ba Debian 12 |
| Python | **3.11 ba 3.12** (3.13/3.14 e `py-tgcalls` stable noy) |
| CPU | 500-1000 bot-er jonno 8 core bhalo (`LS_WORKER_SHARDS=10`) |
| RAM | 4 GB+ |
| DB | Panel jei `DATABASE_URL` use korche, hubohu shei ta |

Python version check:

```bash
python3 --version
```

3.13+ dekhale 3.12 boshiye nin:

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv
```

---

## 1. Dorkari package

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip curl build-essential
```

---

## 2. File gula `/root/tgultra` e nin (git clone chhara)

Panel theke-i puro agent source ek command-e nemano jay:

```bash
mkdir -p /root/tgultra && cd /root/tgultra
curl -fsSL https://autovr-portal.preview.emergentagent.com/api/setup/LS_Python.tar.gz \
  | tar xz --strip-components=1
ls -l
```

Ekhon emon dekhabe:

```
/root/tgultra/agent/            <- python code (supervisor, worker, userbot ...)
/root/tgultra/requirements.txt
/root/tgultra/tgultra.service   <- systemd unit
/root/tgultra/.env.vps.example
/root/tgultra/setup.md          <- ei file
```

> **`.env` file-ta tarball-e ICCHA KORE deya hoy NA** — ote apnar DATABASE_URL,
> tg-lion key, 2FA password thake, ar ei download link public. Tai `.env` ta
> apni nijei banaben (porer step).

---

## 3. `.env` banano (SOB THEKE JORURI STEP)

`/root/tgultra/.env` file-e configuration boshate hobe. Sob theke joruri ekta
line: **`DATABASE_URL`** — panel jeta use korche, hubohu shei ta.

```bash
nano /root/tgultra/.env
```

Minimum ja lagbe:

```ini
# Panel-er sathe SAME database (na milale agent job-i dekhte pabe na)
DATABASE_URL=<panel-er DATABASE_URL hubohu ekhane>

# Ei VPS-er unique nam
AGENT_ID=vps-main

# tg-lion (panel theke account kinle lagbe)
TGLION_API_KEY=<apnar tg-lion api key>
TGLION_USER_ID=<apnar tg-lion user id>
TGLION_BASE_URL=https://tg-lion.net
TGLION_NEW_2FA_PASSWORD=<sob kena account-e jei 2FA password boshbe>

# Sharding — default 10 shard (beshi process = ek channel-er kaj onno
# channel-ke ar slow kore na)
LS_WORKER_SHARDS=10
LS_SOFT_MAX_PER_SHARD=70

# DB pool — 10 shard x 6 = 60 connection (max_connections=100 hole nirapod)
AGENT_DB_POOL_MIN=2
AGENT_DB_POOL_MAX=6

# Console log — protita view/react/vote line-by-line dekhabe (0 dile sudhu
# summary + error)
AGENT_VERBOSE=1
```

`.env.vps.example` file-e **protita option-er byakkha** ache (pacing, join
throttle, keep-alive, profile limit ...). Beshirbhag default-i thik ache — sudhu
upor-er gula boshalei chole.

> ### Kon file agent pore? — **`.env`**
>
> `.env` **i** asol config file, ar eta-i **jete**. Agent-er env loading ekhon
> ek jaygay hoy (`agent/__init__.py`), tai `python -m agent.worker` ar
> `python -m agent.supervisor` — duitai hubohu ek config dekhe.
>
> Priority (upor theke):
> 1. Asol environment variable (systemd `Environment=`, ba `FOO=1 python -m ...`)
> 2. **`.env`**  <- ei ta edit korben
> 3. `.env.vps` — **optional**, sudhu `.env` e ja set kora hoy ni ta bhore dey.
>    Ei file **ar `.env`-ke override korte pare na**. Normal setup-e ei file-er
>    kono dorkar-i nei.
> 4. Current folder-er `.env`
>
> Age `.env.vps` `.env`-ke override korto, ar `supervisor.py` `.env` **poretoi
> na** (systemd-e `LS_WORKER_SHARDS` / `LS_SHARD_RESTART_BACKOFF` chup-chap
> agrahyo hoto) — duitai thik kora hoyeche.


File permission tight korun (secret ache):

```bash
chmod 600 /root/tgultra/.env
```

> **`max_connections` hishab:** `LS_WORKER_SHARDS` x `AGENT_DB_POOL_MAX` =
> 10 x 6 = **60** connection. Postgres-e `max_connections` 100 hole eta nirapod.
> `AGENT_DB_POOL_MAX=10` rakhle 10 x 10 = 100 hoye jabe — tokhon
> `max_connections` baran ba pool kamiye nin.

---

## 4. Virtualenv + dependency install

```bash
cd /root/tgultra
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Python 3.12 alada boshiye thakle:

```bash
python3.12 -m venv .venv
```

### Install thik hoyeche kina check

```bash
/root/tgultra/.venv/bin/python -c "import dotenv, pyrogram, psycopg, pytgcalls; print('all ok')"
```

`all ok` ele thik. (`pyrogram` name-e import hoy kintu asole **pyrofork** —
maintained fork, thik ache.)

### DB connection check

```bash
cd /root/tgultra
.venv/bin/python -c "
import os, psycopg
from dotenv import load_dotenv
load_dotenv('.env')
with psycopg.connect(os.environ['DATABASE_URL']) as c:
    print('DB OK:', c.execute('select count(*) from telegram_accounts').fetchone()[0], 'accounts')
"
```

Account count dekhale agent-er DB thik ache.

> `relation \"telegram_accounts\" does not exist` ele DB-te schema nei — panel-e
> ekbar login korun (panel nije schema banay), ba `all_tg.sql` chalan.

---

## 5. Ekbar hate chalie dekhun (systemd-r age)

```bash
cd /root/tgultra
.venv/bin/python -m agent.supervisor
```

Log-e shard gula chalu hote dekhben. Panel-er upore **"10 agents online"** (ba
apnar shard shonkha) dekhale sob thik.

`Ctrl+C` diye bondho korun — ekhon systemd-te bosabo.

---

## 6. systemd service (24/7 + auto-restart + boot-e auto-start)

```bash
cp /root/tgultra/tgultra.service /etc/systemd/system/tgultra.service
systemctl daemon-reload
systemctl enable --now tgultra
```

Byash. Ekhon:

* server reboot hole nijei chalu hobe
* crash korle 3 second por nijei restart hobe (`Restart=always`)
* bar bar crash korleo kokhono give up kore na (`StartLimitIntervalSec=0`)

### Chalu ache kina

```bash
systemctl status tgultra          # active (running) dekhar kotha
journalctl -u tgultra -f          # LIVE log (Ctrl+C diye ber hon)
journalctl -u tgultra -n 100      # sesh 100 line
```

---

## 7. Rojkar command gula

| Ki korte chan | Command |
|---|---|
| Live log dekha | `journalctl -u tgultra -f` |
| Restart | `systemctl restart tgultra` |
| Bondho | `systemctl stop tgultra` |
| Chalu | `systemctl start tgultra` |
| Boot-e auto-start bondho | `systemctl disable tgultra` |
| Status | `systemctl status tgultra` |
| Ajker error khoja | `journalctl -u tgultra --since today \| grep -i error` |

**`.env` bodlale:**

```bash
systemctl restart tgultra
```

**`tgultra.service` file bodlale:**

```bash
cp /root/tgultra/tgultra.service /etc/systemd/system/tgultra.service
systemctl daemon-reload
systemctl restart tgultra
```

---

## 8. Code update kora (notun version ele)

```bash
systemctl stop tgultra
cd /root/tgultra
curl -fsSL https://autovr-portal.preview.emergentagent.com/api/setup/LS_Python.tar.gz \
  | tar xz --strip-components=1
source .venv/bin/activate && pip install -r requirements.txt
systemctl start tgultra
```

`.env` overwrite hoy **na** (tarball-e `.env` nei), tai apnar config nirapod.

---

## 9. Chhoto setup: sudhu ek process

500-er kom account hole shard lagbe na:

`.env` e `LS_WORKER_SHARDS=1`, ar `tgultra.service` e:

```
ExecStart=/root/tgultra/.venv/bin/python -m agent.worker
```

Tarpor:

```bash
cp /root/tgultra/tgultra.service /etc/systemd/system/tgultra.service
systemctl daemon-reload && systemctl restart tgultra
```

---

## 10. Somossha hole

| Error / obostha | Karon ar somadhan |
|---|---|
| `.env` bodlaleo kichu bodlay na | `systemctl restart tgultra` korechen? Ar dekhun folder-e purono `.env.vps` ache kina — oita `.env`-e set na kora value bhorte pare (`ls -a /root/tgultra`). Na lagle `rm .env.vps` |
| Panel-e "No agent online" | Agent bondho, ba `DATABASE_URL` panel-er theke alada. `systemctl status tgultra` ar `journalctl -u tgultra -n 50` dekhun |
| `ModuleNotFoundError: No module named 'dotenv'` (ba onno module) | Dependency bhul python-e boseche. Step 4 abar korun, ar dekhun `ExecStart` = `/root/tgultra/.venv/bin/python` |
| `ModuleNotFoundError: No module named 'agent'` | `WorkingDirectory=/root/tgultra` thik ache kina dekhun |
| `psycopg.OperationalError: connection failed` | `DATABASE_URL` bhul / DB baire theke reachable na / Neon URL-e `?sslmode=require` nei |
| `relation "telegram_accounts" does not exist` | DB-te schema nei — panel-e ekbar login korun, ba `all_tg.sql` chalan |
| `too many connections` | `LS_WORKER_SHARDS` x `AGENT_DB_POOL_MAX` DB-r limit chariye gache. Ekta kamiye nin |
| Service bar bar restart | `journalctl -u tgultra -f` — prai missing dependency ba bhul `DATABASE_URL` |
| `py-tgcalls` install e fail | Python 3.13/3.14 use korchen. 3.11 ba 3.12 nin (Step 0) |
| Bot join kore tarpor drop hoy | `AGENT_JOIN_CONCURRENCY` kamiye (6-8), `LS_WORKER_SHARDS` bariye dekhun; byakkha `.env.vps.example` e ache |
| Account gula ekshathe burst kore | `AGENT_ACTION_DISPATCH_GAP_MIN/MAX` bariye din (per-account pacing) |
| Frozen/ban barche | Telegram rate limit. `AGENT_PROFILE_CONCURRENCY=1`, dispatch gap bariye din |

---

## 11. Account backup (recommend)

Account gula (session soho) niyomito CSV-te backup rakhun — DB harale panel-er
**Import CSV** diye sob phire ashe:

```bash
mkdir -p /root/scripts && cd /root/scripts
curl -fO https://autovr-portal.preview.emergentagent.com/api/setup/export_accounts_csv.sh
chmod +x export_accounts_csv.sh
```

Script `/root/tgultra/.env` er pashe thakle nijei `DATABASE_URL` khuje ney;
alada folder-e rakhle ekta wrapper banie cron-e din — bistarito
`VPS_POSTGRES_SETUP.md` (STEP 10) e ache.
