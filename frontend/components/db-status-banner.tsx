"use client"

import useSWR from "swr"
import { AlertTriangle } from "lucide-react"

type Health = { db: "ok" | "error"; code?: string | null; message?: string; hint?: string }

const fetcher = (url: string) => fetch(url).then((r) => r.json())

/**
 * Shows a loud banner when the database is unreachable.
 *
 * Without this the dashboard just renders empty panels ("0 accounts") when
 * DATABASE_URL is wrong or Postgres is down, which looks like data loss.
 */
export function DbStatusBanner() {
  const { data } = useSWR<Health>("/api/health", fetcher, {
    refreshInterval: 15000,
    revalidateOnFocus: true,
  })

  if (!data || data.db !== "error") return null

  return (
    <div className="border-b border-destructive/40 bg-destructive/10">
      <div className="mx-auto flex max-w-6xl items-start gap-3 px-4 py-3 sm:px-6">
        <AlertTriangle className="mt-0.5 size-5 shrink-0 text-destructive" />
        <div className="min-w-0 space-y-1">
          <p className="text-sm font-semibold text-destructive">Database not connected</p>
          <p className="break-words text-sm text-foreground/80">{data.message}</p>
          {data.hint ? <p className="break-words text-xs text-muted-foreground">{data.hint}</p> : null}
          <p className="text-xs text-muted-foreground">
            Accounts and jobs stay hidden until the database is reachable — nothing has been deleted.
          </p>
        </div>
      </div>
    </div>
  )
}
