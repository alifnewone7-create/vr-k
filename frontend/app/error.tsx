"use client"

import { useEffect } from "react"
import { AlertTriangle, RotateCcw } from "lucide-react"
import { Button } from "@/components/ui/button"

// Root error boundary. Without this a server-side failure (usually an
// unreachable database) renders a blank white page, which is impossible to
// debug from the browser.
export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("[app error]", error)
  }, [error])

  const raw = String(error?.message ?? "")
  const looksLikeDb =
    /ECONNREFUSED|ENOTFOUND|ETIMEDOUT|password authentication|does not exist|DATABASE_URL|permission denied for/i.test(
      raw,
    )

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4 text-foreground">
      <div className="w-full max-w-lg space-y-4 rounded-lg border border-border bg-card p-6">
        <div className="flex items-center gap-3">
          <AlertTriangle className="size-6 text-destructive" />
          <h1 className="text-lg font-semibold">Something went wrong</h1>
        </div>

        {looksLikeDb ? (
          <div className="space-y-2 text-sm text-muted-foreground">
            <p className="text-foreground">The app could not talk to its PostgreSQL database.</p>
            <p>
              Check <code className="rounded bg-muted px-1 py-0.5 text-xs">DATABASE_URL</code> in your{" "}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">.env</code> file, make sure PostgreSQL is running
              and reachable, then reload. Nothing has been deleted.
            </p>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">An unexpected error occurred while rendering this page.</p>
        )}

        <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded bg-muted p-3 text-xs text-muted-foreground">
          {raw || "No error message available."}
        </pre>

        <div className="flex gap-2">
          <Button onClick={() => reset()} className="gap-2">
            <RotateCcw className="size-4" />
            Try again
          </Button>
          <Button variant="outline" onClick={() => (window.location.href = "/login")}>
            Back to login
          </Button>
        </div>
      </div>
    </div>
  )
}
