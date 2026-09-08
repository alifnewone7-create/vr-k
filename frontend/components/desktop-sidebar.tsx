"use client"

import { PanelLeftClose, PanelLeftOpen, LogOut } from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { logoutAction } from "@/app/actions/auth"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"

interface NavItem {
  value: string
  label: string
  icon: LucideIcon
}

interface DesktopSidebarProps {
  nav: readonly NavItem[]
  activeTab: string
  onTabChange: (tab: string) => void
  collapsed: boolean
  onToggle: () => void
}

export function DesktopSidebar({ nav, activeTab, onTabChange, collapsed, onToggle }: DesktopSidebarProps) {
  return (
    <aside
      data-testid="desktop-sidebar"
      data-collapsed={collapsed}
      className={`sticky top-0 hidden h-screen shrink-0 flex-col border-r border-border/60 glass-strong transition-[width] duration-300 ease-out md:flex ${
        collapsed ? "w-[76px]" : "w-64"
      }`}
    >
      {/* Brand */}
      <div className={`flex items-center gap-3 border-b border-border/60 px-4 py-4 ${collapsed ? "justify-center px-0" : ""}`}>
        <div className="relative shrink-0">
          <div className="absolute inset-0 rounded-xl bg-primary/40 blur-md" aria-hidden />
          <img
            src="/telegram-ultra.png"
            alt="Telegram Ultra"
            className="relative size-9 rounded-xl object-cover ring-1 ring-white/10"
          />
        </div>
        {!collapsed ? (
          <div className="min-w-0">
            <p className="font-heading text-sm font-bold leading-tight tracking-tight">Telegram Ultra</p>
            <p className="truncate text-xs text-muted-foreground">Control Panel</p>
          </div>
        ) : null}
      </div>

      {/* Nav */}
      <nav className="scrollbar-thin flex flex-1 flex-col gap-1 overflow-y-auto p-3">
        {!collapsed ? (
          <p className="px-3 py-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
            Sections
          </p>
        ) : null}
        {nav.map((n) => {
          const isActive = activeTab === n.value
          return (
            <button
              key={n.value}
              onClick={() => onTabChange(n.value)}
              data-testid={`sidebar-nav-${n.value}`}
              className={`group relative flex items-center gap-3 rounded-md py-2.5 text-sm font-medium transition-colors ${
                collapsed ? "justify-center px-0" : "px-3"
              } ${
                isActive
                  ? "bg-primary text-primary-foreground shadow-lg shadow-primary/25"
                  : "text-foreground/90 hover:bg-accent"
              }`}
            >
              <n.icon
                className={`size-[18px] shrink-0 ${
                  isActive ? "text-primary-foreground" : "text-muted-foreground group-hover:text-foreground"
                }`}
              />
              {!collapsed ? <span className="truncate">{n.label}</span> : null}
            </button>
          )
        })}
      </nav>

      {/* Footer: collapse toggle + logout */}
      <div className={`flex flex-col gap-2 border-t border-border/60 p-3 ${collapsed ? "items-center" : ""}`}>
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggle}
          data-testid="sidebar-toggle"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={`gap-2 text-muted-foreground hover:text-foreground ${collapsed ? "size-10 p-0" : "justify-start"}`}
        >
          {collapsed ? <PanelLeftOpen className="size-[18px]" /> : <PanelLeftClose className="size-[18px]" />}
          {!collapsed ? <span>Collapse</span> : null}
        </Button>

        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              data-testid="sign-out-button"
              title={collapsed ? "Sign out" : undefined}
              className={`gap-2 text-muted-foreground hover:text-foreground ${collapsed ? "size-10 p-0" : "justify-start"}`}
            >
              <LogOut className="size-[18px]" />
              {!collapsed ? <span>Sign out</span> : null}
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Sign out?</AlertDialogTitle>
              <AlertDialogDescription>
                You will be signed out of the Telegram Ultra control panel and returned to the login screen.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <form action={logoutAction}>
                <AlertDialogAction type="submit" className="w-full">
                  Sign out
                </AlertDialogAction>
              </form>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </aside>
  )
}
