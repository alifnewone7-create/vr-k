"use client"

import { useActionState } from "react"
import { loginAction } from "@/app/actions/auth"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { AlertCircle, User, Lock, KeyRound, LogIn, Loader2 } from "lucide-react"

export function LoginForm() {
  const [state, formAction, pending] = useActionState(loginAction, undefined)

  return (
    <Card className="glass-strong border-border/60 shadow-2xl">
      <CardContent className="p-6">
        <form action={formAction} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="username" className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Username
            </Label>
            <div className="relative">
              <User className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                placeholder="Enter username"
                required
                autoFocus
                data-testid="login-username-input"
                className="h-11 pl-9 transition-colors focus:border-primary focus-visible:ring-primary/30"
              />
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="password" className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Password
            </Label>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                placeholder="Enter password"
                required
                data-testid="login-password-input"
                className="h-11 pl-9 transition-colors focus:border-primary focus-visible:ring-primary/30"
              />
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="secret" className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Secret
            </Label>
            <div className="relative">
              <KeyRound className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="secret"
                name="secret"
                type="password"
                autoComplete="one-time-code"
                placeholder="Enter secret"
                required
                data-testid="login-secret-input"
                className="h-11 pl-9 transition-colors focus:border-primary focus-visible:ring-primary/30"
              />
            </div>
          </div>
          {state?.error ? (
            <p
              data-testid="login-error"
              className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
            >
              <AlertCircle className="size-4 shrink-0" />
              {state.error}
            </p>
          ) : null}
          <Button
            type="submit"
            disabled={pending}
            data-testid="login-submit-button"
            className="mt-1 h-11 w-full gap-2 font-semibold transition-transform active:scale-[0.98]"
          >
            {pending ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Signing in...
              </>
            ) : (
              <>
                <LogIn className="size-4" />
                Sign in
              </>
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
