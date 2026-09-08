import { NextResponse } from "next/server"
import { readFile } from "node:fs/promises"
import { execFile } from "node:child_process"
import { promisify } from "node:util"
import path from "node:path"

// Serves the VPS setup files as plain text (and the agent source as a tarball)
// so a server can pull them with curl, without cloning the repo:
//
//   # Postgres schema + CSV backup tooling
//   curl -fO https://<app>/api/setup/all_tg.sql
//   curl -fO https://<app>/api/setup/export_accounts_csv.sh
//
//   # systemd unit
//   curl -fO https://<app>/api/setup/tgultra.service
//
//   # the whole Python agent into /root/tgultra
//   mkdir -p /root/tgultra && cd /root/tgultra
//   curl -fsSL https://<app>/api/setup/LS_Python.tar.gz | tar xz --strip-components=1
//
// Reads straight off disk so a download is always the current file.
// Intentionally unauthenticated, so NOTHING secret may be served here:
// the tarball explicitly excludes LS_Python/.env (Telegram API keys, tg-lion
// key, DATABASE_URL). Only the exact names below are allowed, so there is no
// path traversal.

const execFileAsync = promisify(execFile)

const ROOT = process.cwd()

// name -> absolute path on disk
const TEXT_FILES: Record<string, string> = {
  "all_tg.sql": path.join(ROOT, "scripts", "all_tg.sql"),
  "export_accounts_csv.sh": path.join(ROOT, "scripts", "export_accounts_csv.sh"),
  "dev_local_pg.sh": path.join(ROOT, "scripts", "dev_local_pg.sh"),
  "tgultra.service": path.join(ROOT, "LS_Python", "tgultra.service"),
}

const TARBALL = "LS_Python.tar.gz"

// Never ship secrets or build junk inside the tarball.
const TAR_EXCLUDES = [
  "--exclude=LS_Python/.env",
  "--exclude=LS_Python/.venv",
  "--exclude=__pycache__",
  "--exclude=*.pyc",
  "--exclude=*.session",
]

export async function GET(_request: Request, { params }: { params: Promise<{ file: string }> }) {
  const { file } = await params

  // basename() strips any ../ before the allow-list check.
  const name = path.basename(file ?? "")

  if (name === TARBALL) {
    try {
      const { stdout } = await execFileAsync(
        "tar",
        ["-czf", "-", "-C", ROOT, ...TAR_EXCLUDES, "LS_Python"],
        { encoding: "buffer", maxBuffer: 128 * 1024 * 1024 },
      )
      return new NextResponse(new Uint8Array(stdout as unknown as Buffer), {
        status: 200,
        headers: {
          "Content-Type": "application/gzip",
          "Content-Disposition": `attachment; filename="${TARBALL}"`,
          "Cache-Control": "no-store",
        },
      })
    } catch (err: any) {
      return NextResponse.json({ error: "Could not build tarball", detail: String(err?.message ?? err) }, { status: 500 })
    }
  }

  const diskPath = TEXT_FILES[name]
  if (!diskPath) {
    return NextResponse.json(
      { error: "Not found", available: [...Object.keys(TEXT_FILES), TARBALL] },
      { status: 404 },
    )
  }

  try {
    const body = await readFile(diskPath, "utf8")
    return new NextResponse(body, {
      status: 200,
      headers: {
        // text/plain so `curl` and browsers both show it as-is.
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Disposition": `attachment; filename="${name}"`,
        "Cache-Control": "no-store",
      },
    })
  } catch {
    return NextResponse.json({ error: `Could not read ${name}` }, { status: 500 })
  }
}
