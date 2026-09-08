import { isAuthenticated } from "@/lib/auth"
import { redirect } from "next/navigation"
import { LoginForm } from "@/components/login-form"

export default async function LoginPage() {
  if (await isAuthenticated()) redirect("/")

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-5 py-12">
      {/* Ambient glow backdrop */}
      <div className="pointer-events-none absolute inset-0 bg-ambient" aria-hidden />
      <div
        className="pointer-events-none absolute -top-40 left-1/2 h-80 w-80 -translate-x-1/2 rounded-full bg-primary/20 blur-3xl"
        aria-hidden
      />

      <div className="relative z-10 w-full max-w-sm animate-rise">
        <div className="mb-8 flex flex-col items-center gap-4 text-center">
          <div className="relative">
            <div className="absolute inset-0 rounded-3xl bg-primary/30 blur-2xl" aria-hidden />
            <img
              src="/telegram-ultra.png"
              alt="Telegram Ultra"
              className="relative size-20 rounded-3xl object-cover shadow-2xl ring-1 ring-white/10"
            />
          </div>
          <div className="space-y-1.5">
            <h1
              data-testid="brand-title"
              className="font-heading text-3xl font-extrabold tracking-tight text-foreground text-glow"
            >
              Telegram Ultra
            </h1>
            <p className="text-sm text-muted-foreground">
              Sign in to your control panel
            </p>
          </div>
        </div>
        <LoginForm />
        <p className="mt-6 text-center text-xs text-muted-foreground/70">
          Secured access · Authorized operators only
        </p>
      </div>
    </main>
  )
}
