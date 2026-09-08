import { NextResponse } from "next/server"
import { isAuthenticated } from "@/lib/auth"
import { availableCountries, getBalance, TgLionError } from "@/lib/tglion"

// Returns the tg-lion balance + available countries for the "Buy account" panel.
// Credentials come ONLY from the server env (TGLION_API_KEY / TGLION_USER_ID /
// TGLION_BASE_URL) — the browser never sends or sees them.
// Errors are passed back so the dialog can show the real reason instead of an
// empty country list that looks like a broken panel.
export async function GET() {
  if (!(await isAuthenticated())) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }
  try {
    const [balance, countries] = await Promise.all([getBalance(), availableCountries()])
    const list = Object.values(countries).sort((a, b) => a.name.localeCompare(b.name))
    return NextResponse.json({ balance, countries: list })
  } catch (e: any) {
    const message = e instanceof TgLionError ? e.message : (e?.message ?? "Failed to reach tg-lion.")
    // HTTP 200 with an `error` field: the route itself worked, tg-lion did not.
    return NextResponse.json({ error: message, countries: [] }, { status: 200 })
  }
}
