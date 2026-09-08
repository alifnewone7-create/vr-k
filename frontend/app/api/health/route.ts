import { NextResponse } from "next/server"
import { query } from "@/lib/db"
import { isAuthenticated } from "@/lib/auth"

// Lightweight database reachability probe. The dashboard polls this so a broken
// DATABASE_URL shows up as a clear banner instead of every panel silently
// rendering "0 accounts".
export const dynamic = "force-dynamic"

// Turn raw driver errors into something a human can act on.
function explain(err: any): { message: string; hint: string } {
  const code = err?.code ?? ""
  const raw = String(err?.message ?? err ?? "Unknown error")

  if (code === "ECONNREFUSED") {
    return {
      message: `Cannot reach the database at ${err?.address ?? "?"}:${err?.port ?? "?"} (connection refused).`,
      hint: "PostgreSQL is not running at that address, or DATABASE_URL points somewhere else. Set DATABASE_URL to your VPS Postgres URL.",
    }
  }
  if (code === "ENOTFOUND" || code === "EAI_AGAIN") {
    return {
      message: "The database host in DATABASE_URL could not be resolved.",
      hint: "Check the hostname / IP in DATABASE_URL.",
    }
  }
  if (code === "ETIMEDOUT" || code === "ECONNRESET") {
    return {
      message: "The database did not answer in time.",
      hint: "Open port 5432 in your firewall / cloud security group, and set listen_addresses = '*' in postgresql.conf.",
    }
  }
  if (code === "28P01") {
    return { message: "Database password was rejected.", hint: "Check the user and password in DATABASE_URL." }
  }
  if (code === "3D000") {
    return { message: raw, hint: "Create the database first: CREATE DATABASE tgpro OWNER tguser;" }
  }
  if (code === "42501") {
    return {
      message: raw,
      hint: "The database user must OWN the database, because the app applies its own migrations. Use: CREATE DATABASE tgpro OWNER tguser;",
    }
  }
  if (raw.includes("DATABASE_URL")) {
    return { message: raw, hint: "Add DATABASE_URL to your .env file, then restart." }
  }
  return { message: raw, hint: "See VPS_POSTGRES_SETUP.md for the full setup steps." }
}

export async function GET() {
  if (!(await isAuthenticated())) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  try {
    await query("SELECT 1")
    return NextResponse.json({ db: "ok" })
  } catch (err: any) {
    const { message, hint } = explain(err)
    // 200 on purpose: this endpoint reports health, it is not itself failing.
    return NextResponse.json({ db: "error", code: err?.code ?? null, message, hint })
  }
}
