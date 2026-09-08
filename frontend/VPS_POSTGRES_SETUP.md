# VPS-e PostgreSQL Setup (FRESH DB) + Account CSV Backup

> ## ⚡ EKHONKAR OBOSTHA: DATABASE = **NEON** (VPS Postgres NA)
>
> Apni Neon-e-i rakhte bolechen, tai panel ekhon ei Neon project-e cholche:
>
> ```
> postgresql://neondb_owner:npg_n2FcR4WUlraY@ep-still-dream-b3639i2s-pooler.c-4.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
> ```
>
> * Neon-e schema (18 table + 39 index) **already toiri** — panel nijei baniye niyeche
> * `LS_Python/.env` o **ei same Neon URL** e set kora ache
> * **STEP 1 theke 9 apnar ekhon lagbe NA** (oi gula VPS-e self-hosted Postgres
>   banano-r jonno). Bhobishyote VPS-e nite chaile oi step gula ready ache.
> * **Ja ekhon-o kaje lagbe:** **STEP 10** (account CSV auto-backup) ar
>   **STEP 11** (LS_Python agent chalu kora).
>
> ### Neon-er sathe CSV backup (STEP 10-er Neon version)
>
> VPS-e `postgresql-client` ar script-ta nin:
>
> ```bash
> sudo apt install -y postgresql-client-17
> mkdir -p /root/scripts && cd /root/scripts
> curl -fO https://autovr-portal.preview.emergentagent.com/api/setup/export_accounts_csv.sh
> chmod +x export_accounts_csv.sh
> ```
>
> Cron wrapper (Neon URL diye):
>
> ```bash
> cat > /root/scripts/tgpro-csv-cron.sh <<'EOF'
> #!/usr/bin/env bash
> export DATABASE_URL='postgresql://neondb_owner:npg_n2FcR4WUlraY@ep-still-dream-b3639i2s-pooler.c-4.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
> exec /root/scripts/export_accounts_csv.sh
> EOF
> chmod 700 /root/scripts/tgpro-csv-cron.sh
> /root/scripts/tgpro-csv-cron.sh          # ekbar test
> ```
>
> Tarpor `sudo crontab -e` -> `0 * * * * /root/scripts/tgpro-csv-cron.sh >> /var/log/tgpro-csv.log 2>&1`
>
> Neon-er password-e `@ #` nei, tai ekhane percent-encoding-er jhamela **nei**.
> CSV gula `/var/backups/tgpro-csv/` e jombe — Neon project kono din harale oi
> CSV theke sob account phire ashbe.

---

## (Niche theke: VPS-e self-hosted PostgreSQL banano-r puro guide — ekhon optional)


Apni VPS-e **ekdom notun, faka PostgreSQL** banaben. Purono Neon-er kono data ana
hobe **na** — sob notun data ekhon theke ei VPS DB-tei jombe.

Git clone lagbe **na**. Script gula `/root/scripts` folder-e curl diye niye
nebo, okhan theke-i chalabo.

Sob command **Ubuntu 22.04 / 24.04 ba Debian 12** e `root` diye chalabe.

---

## Apnar Credentials (ei guide-e joto jaygay lage)

| Ki | Value |
|---|---|
| DB user | `tguser` |
| DB password | `Iamhear@#tgallkm1234` |
| DB name | `tgpro` |
| Scripts folder | `/root/scripts` |
| CSV backup folder | `/var/backups/tgpro-csv` |

### ⚠️ PASSWORD NIYE EKTA JORURI JINIS — POREI NIN

Apnar password-e **`@`** ar **`#`** ache. URL-er moddhe ei dui-ta character-er
alada mane ache:
* `@` = user ar host-er majhkhaner separator
* `#` = fragment-er shuru

Tai password-ta **hubohu** URL-e boshalei connection venge jabe. Ami test kore
dekhiyechi:

```
# BHUL (ja shobai kore):
psql "postgresql://tguser:Iamhear@#tgallkm1234@127.0.0.1:5432/tgpro"
  -> psql: error: could not translate host name "#tgallkm1234@127.0.0.1" to address
```

**Somadhan:** URL-er moddhe `@` -> `%40` ar `#` -> `%23` likhte hobe
(percent-encoding). Password nijei bodlacche na — sudhu URL-e lekhar niyom.

```
Iamhear@#tgallkm1234   ->   Iamhear%40%23tgallkm1234
```

```
# THIK (test kora, kaj kore):
psql "postgresql://tguser:Iamhear%40%23tgallkm1234@127.0.0.1:5432/tgpro"
  -> CONNECTED
```

**Mone rakhben:**
* **URL / DATABASE_URL** er moddhe → `Iamhear%40%23tgallkm1234`
* **`CREATE ROLE` / `PGPASSWORD`** e (mane URL na, direct password) → asol
  `Iamhear@#tgallkm1234`, single quote `'...'` er moddhe

---

## Overview

| Ki | Kothay cholbe |
|---|---|
| Next.js panel (website) | Emergent preview (already live) |
| PostgreSQL (notun, faka) | **apnar VPS** |
| LS_Python agent | apnar VPS (same machine) |
| Account CSV backup | **apnar VPS** (`/var/backups/tgpro-csv`) |

---

## STEP 1 — PostgreSQL 17 install

```bash
sudo apt update
sudo apt install -y curl ca-certificates
sudo install -d /usr/share/postgresql-common/pgdg
sudo curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc --fail \
  https://www.postgresql.org/media/keys/ACCC4CF8.asc
. /etc/os-release
echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
  | sudo tee /etc/apt/sources.list.d/pgdg.list
sudo apt update
sudo apt install -y postgresql-17 postgresql-client-17
```

Chalu ache kina:

```bash
sudo systemctl enable --now postgresql
sudo systemctl status postgresql --no-pager
psql --version      # 17.x
```

> Niche path-e `/etc/postgresql/17/main/` dhore lekha. Apnar version onno hole
> sei number use korben (`ls /etc/postgresql/` diye dekhben).

---

## STEP 2 — Database + User (owner kore)

> **SOB THEKE GURUTTOPURNO STEP.** Database-ta **OWNER tguser** diye banate
> HOBE. Karon website-er `lib/db.ts` prottek boot-e nije migration (CREATE
> TABLE / ALTER TABLE) chalay. Owner na hole
> `permission denied for table telegram_accounts` error ashe ar panel kaj kore
> na. Sudhu `GRANT ALL` diye hoy **NA**.

Ekhane password **asol roop-e** (encode na), single quote er moddhe:

```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE tguser LOGIN PASSWORD 'Iamhear@#tgallkm1234';
CREATE DATABASE tgpro OWNER tguser;
SQL
```

Check — `tgpro | tguser` dekhale thik:

```bash
sudo -u postgres psql -c "\l" | grep tgpro
```

---

## STEP 3 — Script gula `/root/scripts` e nin (git clone chhara)

Duita file lagbe. Sorasori download korun (git lagbe na):

```bash
mkdir -p /root/scripts && cd /root/scripts

curl -fO https://autovr-portal.preview.emergentagent.com/api/setup/all_tg.sql
curl -fO https://autovr-portal.preview.emergentagent.com/api/setup/export_accounts_csv.sh

chmod +x export_accounts_csv.sh
ls -lh
```

Thik moto eseche kina milie nin:

```bash
wc -l all_tg.sql            # 505 line asha uchit
grep -c "CREATE TABLE" all_tg.sql   # 18
```

> **Ei file gula sob shomoy latest.** Panel ja chalacche thik oi file-i serve
> kore. Ami kono script update korle apni sudhu abar `curl -fO` chalaben.
>
> **Kheyal korben:** GitHub repo-r `scripts/all_tg.sql` ta **purono** —
> okhane sudhu migration 001-008 ache, 009/010/011 nei. Tai GitHub theke na
> niye ei URL theke-i niben.

---

## STEP 4 — Schema banano (`all_tg.sql`)

Ei ek file-e **protita migration (001 -> 011) merge** kora — **18 table + 39
index**. Fresh DB-te ekbar chalalei puro schema toiri.

Chalan — **`tguser` hisebe** (`postgres` hisebe NA, tahole table gula
postgres-er malikanay chole jabe ar abar permission error hobe):

```bash
cd /root/scripts
PGPASSWORD='Iamhear@#tgallkm1234' psql -h 127.0.0.1 -U tguser -d tgpro \
  -v ON_ERROR_STOP=1 -f all_tg.sql
```

Verify — **18** asha uchit:

```bash
PGPASSWORD='Iamhear@#tgallkm1234' psql -h 127.0.0.1 -U tguser -d tgpro \
  -c "SELECT count(*) FROM pg_tables WHERE schemaname='public';"

PGPASSWORD='Iamhear@#tgallkm1234' psql -h 127.0.0.1 -U tguser -d tgpro -c "\dt"
```

Table gula: `telegram_accounts, jobs, agents, agent_pacing, livestream_targets,
livestream_participants, view_targets, vote_targets, vote_casts,
reaction_targets, profile_assets, profile_updates, account_messages,
channel_join_targets, channel_join_participants, message_assets,
message_campaigns, message_sends`

> File ta **idempotent** — joto bar chalan, kono khoti hoy na, data-o mochhe na.
> **VERIFIED:** ami faka PostgreSQL-e chaliye dekhechi — 0 error, dui-bar
> chalieo 0 error.

---

## STEP 5 — Remote connection chalu (website-er jonno)

**5a. `postgresql.conf`:**

```bash
sudo nano /etc/postgresql/17/main/postgresql.conf
```

Edit korun (samner `#` tule din):

```
listen_addresses = '*'
max_connections = 200
```

`max_connections` keno 200 — STEP 8 dekhun.

**5b. `pg_hba.conf`:**

```bash
sudo nano /etc/postgresql/17/main/pg_hba.conf
```

File-er **sob theke niche** add korun:

```
host    tgpro    tguser    0.0.0.0/0    scram-sha-256
```

**5c. Restart:**

```bash
sudo systemctl restart postgresql
```

---

## STEP 6 — Firewall

```bash
sudo ufw allow 5432/tcp
sudo ufw status
```

Cloud provider (DigitalOcean / AWS / Vultr / Hetzner / Contabo) hole **panel-er
Firewall / Security Group** theke-o port **5432** khulte hobe — na hole ufw
khola thakleo connection ashbe na.

> **Security:** port 5432 baire khola thakche. `tguser`-er sudhu `tgpro` DB-te
> access ache. Aro secure korte chaile STEP 9 (SSL) dekhun.

---

## STEP 7 — DATABASE_URL (encoded password soho) + test

VPS IP ber korun:

```bash
curl -4 ifconfig.me
```

Apnar URL (`YOUR_VPS_IP` bodle din) — password ekhane **encoded**:

```
postgresql://tguser:Iamhear%40%23tgallkm1234@YOUR_VPS_IP:5432/tgpro?sslmode=disable
```

Test korun:

```bash
psql "postgresql://tguser:Iamhear%40%23tgallkm1234@YOUR_VPS_IP:5432/tgpro?sslmode=disable" -c "SELECT now();"
```

Time ashle **kaj hocche** — ei URL-ta amake pathiye din, ami `.env` e boshiye
dibo.

> `%40%23` bhul kore `@#` likhle error ashbe:
> `could not translate host name "#tgallkm1234@..."` — tokhon STEP 0-r
> encoding niyom-ta abar dekhun.

---

## STEP 8 — Scale tuning (500–1000 bot hole MUST)

Koto connection lage:

| Kothay | Koto |
|---|---|
| LS_Python: `AGENT_DB_POOL_MAX=10` x `LS_WORKER_SHARDS=7` | **70** |
| Website pool (`lib/db.ts`, max 5) | 5 |
| Apnar psql / backup | ~5 |
| **Total** | **~80** |

Default `max_connections = 100` mane **80% bhorti** — ektu spike-e-i
`FATAL: too many connections for role`, tokhon agent job nite pare na ar panel-e
"No agent online" ashe. Tai `/etc/postgresql/17/main/postgresql.conf`:

```
max_connections = 200
shared_buffers = 512MB          # RAM-er ~25% (2GB RAM hole 512MB)
effective_cache_size = 1536MB   # RAM-er ~75%
work_mem = 8MB
maintenance_work_mem = 128MB
```

```bash
sudo systemctl restart postgresql
```

1GB RAM hole `shared_buffers = 256MB`.

---

## STEP 9 — (Optional) SSL

```bash
sudo -u postgres bash -c 'cd /var/lib/postgresql/17/main && openssl req -new -x509 -days 3650 -nodes -text -subj "/CN=tgpro" -out server.crt -keyout server.key && chmod 600 server.key'
```

`postgresql.conf`:

```
ssl = on
ssl_cert_file = '/var/lib/postgresql/17/main/server.crt'
ssl_key_file = '/var/lib/postgresql/17/main/server.key'
```

Restart korun, ar URL-e `?sslmode=require` din.

---

## STEP 10 — Account CSV auto-backup

Joto telegram account add hobe, sob-gulo automatic ekta CSV file-e jomta thakbe
apnar VPS-e — **panel-er "Import CSV" jei format chay hubohu sei format-e**. Tai
kono din DB noshto hole ba notun VPS-e jete hole, oi file-ta upload korlei sob
account (session + api key soho) phire ashe.

### 10a. Ekbar hate chalie dekhun

Script `/root/scripts` e already ache (STEP 3). Password-e `@#` ache tai URL-e
**encoded** roop din:

```bash
cd /root/scripts
DATABASE_URL='postgresql://tguser:Iamhear%40%23tgallkm1234@127.0.0.1:5432/tgpro' \
  ./export_accounts_csv.sh
```

Output:

```
[tgpro-csv] 2026-09-04 15:10:02  total=210  ready=207  -> /var/backups/tgpro-csv/accounts_2026-09-04_1510.csv
```

Ki toiri hoy (`/var/backups/tgpro-csv/`):

| File | Ki ache |
|---|---|
| `accounts_<date>_<time>.csv` | oi somoy-er snapshot (history) |
| `accounts_latest.csv` | **SOB** account, sob shomoy newest |
| `accounts_ready_latest.csv` | **sudhu `logged_in`** (kaj korar upojukto) account |

Onno folder-e rakhte chaile:

```bash
OUT_DIR=/root/tg-csv KEEP=100 DATABASE_URL='...' ./export_accounts_csv.sh
```

### 10b. Cron — prottek ghontay automatic

Password bar bar na likhe, ekta chhoto wrapper banie nin (shob theke poriskar):

```bash
cat > /root/scripts/tgpro-csv-cron.sh <<'EOF'
#!/usr/bin/env bash
export DATABASE_URL='postgresql://tguser:Iamhear%40%23tgallkm1234@127.0.0.1:5432/tgpro'
exec /root/scripts/export_accounts_csv.sh
EOF
chmod 700 /root/scripts/tgpro-csv-cron.sh
```

Tarpor cron:

```bash
sudo crontab -e
```

Ei line add korun:

```
0 * * * * /root/scripts/tgpro-csv-cron.sh >> /var/log/tgpro-csv.log 2>&1
```

Prottek 15 minute-e chaile: `*/15 * * * *`.

Check:

```bash
tail -f /var/log/tgpro-csv.log
ls -lh /var/backups/tgpro-csv/
```

Purono snapshot nijei chhaTai hoy (default sesh **48** ta thake, `KEEP` diye
bodlano jay), tai disk bhorti hobe na.

> LS_Python-er `.env` e DATABASE_URL boshanor por (STEP 11) script ta nijei oi
> file theke URL niye nite pare — tokhon wrapper-o lagbe na, sudhu
> `/root/scripts/export_accounts_csv.sh` cron-e diyei hobe. Kintu tar jonno
> script-ta LS_Python folder-er pashe thakte hobe; alada `/root/scripts` e
> rakhle wrapper-i shoja.

### 10c. CSV-r column

```
phone_number, label, app_title, short_name, api_id, api_hash,
session_string, status, two_factor_required, last_error,
mtproto_hash, login_hash
```

`phone_number` chhara baki sob optional. Comma / quote / newline-wala text
(jemon `last_error`) thik moto quote hoy, tai Excel ar panel duitatei khole.

### 10d. Kivabe phire anben (restore)

1. Panel-e login korun
2. **Userbots** tab -> **Import CSV**
3. `accounts_latest.csv` (ba `accounts_ready_latest.csv`) upload korun
4. **Import accounts** chapun

Phone number diye match hoy — purono account **update** hoy, notun ta **add**
hoy. Duibar import korleo duplicate hoy na.

> **VERIFIED:** ami puro round-trip test korechi — export -> DB-r sob account
> delete -> CSV import -> sob account (session_string, api_id, api_hash,
> mtproto_hash, login_hash, status, 2FA flag, emonki quote/comma/newline-wala
> label ar error text) **hubohu** phire eseche.

### 10e. Panel theke direct download

Cron-er upor nirbhor na kore panel theke-o ek click-e namate paren:
**Userbots** tab -> **Export CSV**. Sudhu kaj korar account chaile:
`/api/accounts/export?ready=1`.

> Ei CSV-te **asol session string ar api key** thake — mane ei file diye kew
> apnar account gula chalate pare. Script nijei `chmod 600` kore dey; public
> folder / git-e rakhben na.

---

## STEP 11 — LS_Python agent-er `.env`

Agent same VPS-e cholbe, tai **localhost** use korun (druto, network-e jay na).
Apnar `LS_Python/.env` file-e:

```
DATABASE_URL=postgresql://tguser:Iamhear%40%23tgallkm1234@127.0.0.1:5432/tgpro
```

Purono Neon line-ta comment (`#`) kore din. Baki sob value (`AGENT_*`,
`TGLION_*`, `LS_WORKER_SHARDS` ...) jemon ache temon-i thakuk.

Agent chalu:

```bash
cd /root/LS_Python        # apnar LS_Python folder jekhane rakhben
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m agent.supervisor
```

Panel-e **"7 agents online"** dekhale sob thik.

> Python **3.11 ba 3.12** use korben — 3.13/3.14 e `py-tgcalls` stable noy
> (requirements.txt-eও lekha ache).

---

## STEP 12 — Amake ki pathaben

Sudhu ei ek line (IP boshiye):

```
DATABASE_URL=postgresql://tguser:Iamhear%40%23tgallkm1234@YOUR_VPS_IP:5432/tgpro?sslmode=disable
```

Ami `.env` e boshiye restart kore dibo → panel apnar VPS DB-te live.

---

## Trouble hole

| Error | Karon / Somadhan |
|---|---|
| `could not translate host name "#tgallkm1234@..."` | URL-e password encode koren ni. `@#` -> `%40%23` |
| `password authentication failed for user "tguser"` | URL-e encoded roop din (`%40%23`), ar `PGPASSWORD`/`CREATE ROLE` e asol roop `Iamhear@#tgallkm1234` |
| `permission denied for table telegram_accounts` | DB owner `tguser` na. `sudo -u postgres psql -c "ALTER DATABASE tgpro OWNER TO tguser;"` ar `sudo -u postgres psql -d tgpro -c "REASSIGN OWNED BY postgres TO tguser;"` |
| `Connection refused` | `listen_addresses = '*'` hoy ni / restart hoy ni / firewall-security group bondho |
| `no pg_hba.conf entry for host` | STEP 5b-r line add hoy ni |
| `too many connections` | `max_connections = 200` (STEP 8) |
| `server does not support SSL` | URL-e `?sslmode=disable` din |
| `curl: (22) ... 404` script namate | File name bhul. Sudhu `all_tg.sql`, `export_accounts_csv.sh`, `dev_local_pg.sh` — ei tin-ta available |
| Panel-e "No agent online" | Agent bondho, ba agent onno DB-te point korche |
| Panel-e lal banner "Database not connected" | Banner-e-i asol karon ar korniyo lekha thake — porei bujhben |
| `export_accounts_csv.sh: DATABASE_URL pawa gelo na` | Script-ke direct din: `DATABASE_URL='...' ./export_accounts_csv.sh` (STEP 10a) |
| CSV import-e `CSV must include a 'phone_number' column` | Header line muche gache / onno file upload hoyeche |
