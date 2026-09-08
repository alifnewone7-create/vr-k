import { NextResponse } from "next/server"
import { query } from "@/lib/db"
import { isAuthenticated } from "@/lib/auth"

// Exports every telegram account as a CSV in EXACTLY the column order that
// importAccountsCsv() (app/actions/accounts.ts) expects, so a file downloaded
// here can be fed straight back into the "Import CSV" dialog with zero editing.
//
//   GET /api/accounts/export            -> all accounts
//   GET /api/accounts/export?ready=1    -> only logged-in (usable) accounts
//
// Sessions and API keys are included in full — this is a restore file, so keep
// it private.

// Must stay in sync with the importer's recognised headers.
const COLUMNS = [
  "phone_number",
  "label",
  "app_title",
  "short_name",
  "api_id",
  "api_hash",
  "session_string",
  "status",
  "two_factor_required",
  "last_error",
  "mtproto_hash",
  "login_hash",
] as const

// RFC-4180 style escaping: wrap in quotes when the value contains a comma,
// quote, CR or LF, and double up any embedded quotes.
function csvCell(value: unknown): string {
  if (value === null || value === undefined) return ""
  let s: string
  if (typeof value === "boolean") s = value ? "true" : "false"
  else s = String(value)
  if (/[",\r\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

export async function GET(request: Request) {
  if (!(await isAuthenticated())) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const url = new URL(request.url)
  const readyOnly = url.searchParams.get("ready") === "1"

  const rows = await query<Record<string, unknown>>(
    `SELECT phone_number, label, app_title, short_name, api_id, api_hash,
            session_string, status, two_factor_required, last_error,
            mtproto_hash, login_hash
       FROM telegram_accounts
      ${readyOnly ? `WHERE status = 'logged_in'` : ``}
      ORDER BY id`,
  )

  const lines: string[] = [COLUMNS.join(",")]
  for (const row of rows ?? []) {
    lines.push(COLUMNS.map((c) => csvCell(row?.[c])).join(","))
  }
  // Trailing newline keeps the file POSIX-friendly.
  const csv = lines.join("\n") + "\n"

  const stamp = new Date().toISOString().slice(0, 10)
  const name = readyOnly ? `accounts_ready_${stamp}.csv` : `accounts_${stamp}.csv`

  return new NextResponse(csv, {
    status: 200,
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${name}"`,
      "Cache-Control": "no-store",
    },
  })
}
