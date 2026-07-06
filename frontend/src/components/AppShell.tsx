import { useQuery } from "@tanstack/react-query"
import {
  Bell,
  Bot,
  LogOut,
  MessageSquareText,
  Radar,
  Satellite,
  Sparkles,
  UserRound,
  Waves,
} from "lucide-react"
import * as React from "react"
import { NavLink, Outlet } from "react-router-dom"

import { AuthDialog } from "@/components/AuthDialog"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { cn } from "@/lib/utils"

const NAV = [
  { to: "/", label: "Overview", icon: Radar, end: true },
  { to: "/detection", label: "Detection", icon: Satellite },
  { to: "/rivers", label: "River Flows", icon: Waves },
  { to: "/intelligence", label: "AI Intelligence", icon: Sparkles },
  { to: "/workflow", label: "Agentic Workflow", icon: Bot },
  { to: "/alerts", label: "Alerts", icon: Bell },
  { to: "/assistant", label: "Knowledge Assistant", icon: MessageSquareText },
]

function HealthPill() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 30_000,
    retry: 1,
  })
  const online = health.isSuccess
  return (
    <div
      className="flex items-center gap-2 rounded-full border border-line bg-raised px-3 py-1"
      title={online ? "Backend API reachable" : "Backend API unreachable"}
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          online ? "animate-pulse-dot bg-status-good" : "bg-status-critical",
        )}
      />
      <span className="text-[11px] font-medium tracking-wide text-ink-secondary">
        {online ? "SYSTEM LIVE" : "API OFFLINE"}
      </span>
    </div>
  )
}

export function AppShell() {
  const { user, logout } = useAuth()
  const [authOpen, setAuthOpen] = React.useState(false)

  return (
    <div className="flex min-h-svh bg-base">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-line bg-surface/70 backdrop-blur">
        <div className="flex items-center gap-2.5 border-b border-line px-5 py-4">
          <div className="grid size-8 place-items-center rounded-lg bg-accent/15 text-accent-bright">
            <Waves className="size-4.5" />
          </div>
          <div className="leading-tight">
            <p className="font-display text-sm font-bold tracking-wide text-ink">
              FloodSense<span className="text-accent-bright">-PK</span>
            </p>
            <p className="text-[10px] tracking-widest text-ink-muted uppercase">
              Flood Intelligence
            </p>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-3">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] font-medium transition-colors",
                  isActive
                    ? "bg-accent/15 text-accent-bright"
                    : "text-ink-secondary hover:bg-raised hover:text-ink",
                )
              }
            >
              <Icon className="size-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-line p-3">
          {user ? (
            <div className="flex items-center justify-between gap-2 rounded-md bg-raised px-3 py-2">
              <div className="min-w-0 leading-tight">
                <p className="truncate text-xs font-semibold text-ink">
                  {user.username}
                </p>
                <p className="truncate text-[10px] text-ink-muted">
                  {user.district ?? "No home district"}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={logout}
                title="Sign out"
                className="size-7"
              >
                <LogOut />
              </Button>
            </div>
          ) : (
            <Button
              variant="secondary"
              className="w-full"
              size="sm"
              onClick={() => setAuthOpen(true)}
            >
              <UserRound /> Sign in
            </Button>
          )}
        </div>
      </aside>

      {/* Main */}
      <div className="backdrop-grid ml-60 flex min-h-svh flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-base/80 px-6 py-3 backdrop-blur">
          <p className="text-xs text-ink-muted">
            National Flood Intelligence &amp; Early Warning —{" "}
            <span className="text-ink-secondary">Pakistan</span>
          </p>
          <HealthPill />
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-6">
          <Outlet />
        </main>
      </div>

      <AuthDialog open={authOpen} onOpenChange={setAuthOpen} />
    </div>
  )
}
