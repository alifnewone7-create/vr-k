"use client"

import { useEffect, useState } from "react"
import { Radio, Users, Eye, Vote, Smile, UserCog, UserPlus, Trash2, MessageSquare } from "lucide-react"
import { Tabs, TabsContent } from "@/components/ui/tabs"
import { MobileNav } from "@/components/mobile-nav"
import { DesktopSidebar } from "@/components/desktop-sidebar"
import { AgentStatusBar } from "@/components/agent-status-bar"
import { DbStatusBanner } from "@/components/db-status-banner"
import { AccountsSection } from "@/components/accounts-section"
import { LivestreamSection } from "@/components/livestream-section"
import { ViewTargetsSection } from "@/components/view-targets-section"
import { VoteSection } from "@/components/vote-section"
import { ReactionsSection } from "@/components/reactions-section"
import { ChannelJoinSection } from "@/components/channel-join-section"
import { ProfileSection } from "@/components/profile-section"
import { PrpDeleteSection } from "@/components/prp-delete-section"
import { ReviewSection } from "@/components/review-section"

const NAV = [
  { value: "accounts", label: "Users", icon: Users },
  { value: "channel-join", label: "Channel Join", icon: UserPlus },
  { value: "livestream", label: "Live Stream", icon: Radio },
  { value: "view", label: "Live View", icon: Eye },
  { value: "vote", label: "Vote", icon: Vote },
  { value: "reactions", label: "Reactions", icon: Smile },
  { value: "profile", label: "Profile", icon: UserCog },
  { value: "prp-delete", label: "Prp Delete", icon: Trash2 },
  { value: "review", label: "Review", icon: MessageSquare },
] as const

const STORAGE_KEY = "tu-sidebar-collapsed"

export function Dashboard() {
  const [activeTab, setActiveTab] = useState("accounts")
  const [collapsed, setCollapsed] = useState(false)
  const active = NAV.find((n) => n.value === activeTab)

  useEffect(() => {
    if (localStorage.getItem(STORAGE_KEY) === "1") setCollapsed(true)
  }, [])

  const toggleSidebar = () => {
    setCollapsed((prev) => {
      const next = !prev
      localStorage.setItem(STORAGE_KEY, next ? "1" : "0")
      return next
    })
  }

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <DesktopSidebar
        nav={NAV}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        collapsed={collapsed}
        onToggle={toggleSidebar}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Sticky glass header */}
        <header
          data-testid="app-header"
          className="sticky top-0 z-40 border-b border-border/60 glass-strong md:hidden"
        >
          <div className="flex items-center justify-between gap-3 px-4 py-3 sm:px-6">
            <div className="flex min-w-0 items-center gap-2 sm:gap-3">
              <MobileNav activeTab={activeTab} onTabChange={setActiveTab} />

              {/* Mobile brand (desktop brand lives in the sidebar) */}
              <div className="relative shrink-0 md:hidden">
                <div className="absolute inset-0 rounded-xl bg-primary/40 blur-md" aria-hidden />
                <img
                  src="/telegram-ultra.png"
                  alt="Telegram Ultra"
                  className="relative size-9 rounded-xl object-cover ring-1 ring-white/10"
                />
              </div>
              <h1
                data-testid="brand-title"
                className="font-heading text-base font-bold leading-tight tracking-tight md:hidden"
              >
                Telegram Ultra
              </h1>

              {/* Desktop: current section title */}
            </div>

            <div className="flex items-center gap-2">
              {/* Active section pill (mobile) */}
              {active ? (
                <span className="inline-flex items-center gap-1.5 rounded-full border border-border/60 bg-secondary/60 px-2.5 py-1 text-xs font-medium text-secondary-foreground md:hidden">
                  <active.icon className="size-3.5 text-primary" />
                  {active.label}
                </span>
              ) : null}
            </div>
          </div>
        </header>

        <DbStatusBanner />

        {/* Ambient top glow */}
        <div className="relative flex-1">
          <div className="pointer-events-none absolute inset-x-0 top-0 h-64 bg-ambient" aria-hidden />

          <main className="relative mx-auto max-w-6xl px-4 py-6 sm:px-6">
            <div className={activeTab === "accounts" ? "" : "hidden md:block"}>
              <AgentStatusBar />
            </div>

            <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-6">
              <TabsContent value="accounts" className="animate-rise">
                <AccountsSection />
              </TabsContent>
              <TabsContent value="channel-join" className="animate-rise">
                <ChannelJoinSection />
              </TabsContent>
              <TabsContent value="livestream" className="animate-rise">
                <LivestreamSection />
              </TabsContent>
              <TabsContent value="view" className="animate-rise">
                <ViewTargetsSection />
              </TabsContent>
              <TabsContent value="vote" className="animate-rise">
                <VoteSection />
              </TabsContent>
              <TabsContent value="reactions" className="animate-rise">
                <ReactionsSection />
              </TabsContent>
              <TabsContent value="profile" className="animate-rise">
                <ProfileSection />
              </TabsContent>
              <TabsContent value="prp-delete" className="animate-rise">
                <PrpDeleteSection />
              </TabsContent>
              <TabsContent value="review" className="animate-rise">
                <ReviewSection />
              </TabsContent>
            </Tabs>
          </main>
        </div>
      </div>
    </div>
  )
}
