/** Domain widgets shared across pages: severity chips, risk gauge, stat tiles. */
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Flame,
  Inbox,
  ShieldAlert,
} from "lucide-react"
import * as React from "react"

import { Badge } from "@/components/ui/badge"
import type { Severity } from "@/lib/api"
import { cn } from "@/lib/utils"

/* Status colors are never color-alone: each chip pairs an icon + label. */

export function SeverityBadge({ severity }: { severity: Severity | string }) {
  const sev = String(severity).toUpperCase()
  if (sev === "HIGH")
    return (
      <Badge variant="critical">
        <ShieldAlert /> High
      </Badge>
    )
  if (sev === "MODERATE")
    return (
      <Badge variant="warning">
        <AlertTriangle /> Moderate
      </Badge>
    )
  return (
    <Badge variant="good">
      <CheckCircle2 /> Low
    </Badge>
  )
}

export function RiverStatusBadge({ status }: { status?: string }) {
  const s = String(status ?? "UNKNOWN").toUpperCase()
  if (s === "EXTREME")
    return (
      <Badge variant="critical">
        <Flame /> Extreme
      </Badge>
    )
  if (s === "HIGH")
    return (
      <Badge variant="serious">
        <AlertTriangle /> High
      </Badge>
    )
  if (s === "NORMAL")
    return (
      <Badge variant="good">
        <CheckCircle2 /> Normal
      </Badge>
    )
  return <Badge>{s}</Badge>
}

export function TrendChip({ trend }: { trend?: string }) {
  const t = String(trend ?? "").toLowerCase()
  if (t.includes("ris") || t.includes("up") || t.includes("increas"))
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-status-serious">
        <ArrowUpRight className="size-3.5" /> Rising
      </span>
    )
  if (t.includes("fall") || t.includes("down") || t.includes("decreas") || t.includes("reced"))
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-aqua">
        <ArrowDownRight className="size-3.5" /> Falling
      </span>
    )
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-ink-muted">
      <ArrowRight className="size-3.5" /> Steady
    </span>
  )
}

/** Risk bands share the severity semantics (icon + label shown next to the gauge). */
export function riskColor(score: number): string {
  if (score >= 7) return "var(--color-status-critical)"
  if (score >= 4) return "var(--color-status-warning)"
  return "var(--color-status-good)"
}

export function riskLabel(score: number): string {
  if (score >= 7) return "HIGH"
  if (score >= 4) return "MODERATE"
  return "LOW"
}

/** SVG arc gauge for the 1–10 defensible risk score. */
export function RiskGauge({ score, size = 172 }: { score: number; size?: number }) {
  const clamped = Math.min(10, Math.max(0, score))
  const r = 64
  const cx = 80
  const cy = 78
  // 240° arc from 150° to 390° (i.e. -30°), sweeping clockwise
  const startAngle = 150
  const sweep = 240 * (clamped / 10)
  const polar = (deg: number) => {
    const rad = (deg * Math.PI) / 180
    return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)]
  }
  const [sx, sy] = polar(startAngle)
  const [ex, ey] = polar(startAngle + sweep)
  const [tx, ty] = polar(startAngle + 240)
  const large = sweep > 180 ? 1 : 0
  const color = riskColor(clamped)

  return (
    <svg
      width={size}
      height={size * 0.75}
      viewBox="0 0 160 120"
      role="img"
      aria-label={`Risk score ${clamped.toFixed(1)} out of 10 — ${riskLabel(clamped)}`}
    >
      {/* Track */}
      <path
        d={`M ${sx} ${sy} A ${r} ${r} 0 1 1 ${tx} ${ty}`}
        fill="none"
        stroke="var(--color-raised)"
        strokeWidth={10}
        strokeLinecap="round"
      />
      {/* Value */}
      {sweep > 0.5 && (
        <path
          d={`M ${sx} ${sy} A ${r} ${r} 0 ${large} 1 ${ex} ${ey}`}
          fill="none"
          stroke={color}
          strokeWidth={10}
          strokeLinecap="round"
        />
      )}
      <text
        x={cx}
        y={cy - 2}
        textAnchor="middle"
        fill="var(--color-ink)"
        fontSize="30"
        fontWeight="650"
        fontFamily="var(--font-display)"
      >
        {clamped.toFixed(1)}
      </text>
      <text
        x={cx}
        y={cy + 16}
        textAnchor="middle"
        fill="var(--color-ink-muted)"
        fontSize="10"
        letterSpacing="2"
      >
        / 10 RISK
      </text>
    </svg>
  )
}

export function StatTile({
  label,
  value,
  hint,
  icon,
  tone,
  className,
}: {
  label: string
  value: React.ReactNode
  hint?: React.ReactNode
  icon?: React.ReactNode
  tone?: "accent" | "good" | "warning" | "critical"
  className?: string
}) {
  const toneColor =
    tone === "good"
      ? "text-status-good"
      : tone === "warning"
        ? "text-status-warning"
        : tone === "critical"
          ? "text-[#e46666]"
          : "text-accent-bright"
  return (
    <div
      className={cn(
        "rounded-card border border-line bg-surface px-5 py-4",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold tracking-wider text-ink-muted uppercase">
          {label}
        </p>
        {icon && <span className={cn("[&_svg]:size-4", toneColor)}>{icon}</span>}
      </div>
      <p className="mt-2 font-display text-[26px] leading-none font-semibold text-ink">
        {value}
      </p>
      {hint && <div className="mt-2 text-xs text-ink-muted">{hint}</div>}
    </div>
  )
}

export function EmptyState({
  title,
  hint,
  icon,
}: {
  title: string
  hint?: React.ReactNode
  icon?: React.ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-card border border-dashed border-line-strong px-6 py-12 text-center">
      <span className="text-ink-muted [&_svg]:size-8">{icon ?? <Inbox />}</span>
      <p className="text-sm font-medium text-ink-secondary">{title}</p>
      {hint && <div className="max-w-sm text-xs text-ink-muted">{hint}</div>}
    </div>
  )
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string
  subtitle?: React.ReactNode
  actions?: React.ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="font-display text-xl font-semibold tracking-tight text-ink">
          {title}
        </h1>
        {subtitle && <p className="mt-1 max-w-2xl text-xs text-ink-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}

export function timeAgo(iso?: string): string {
  if (!iso) return "—"
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return "—"
  const mins = Math.max(0, Math.round((Date.now() - then) / 60000))
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.round(hrs / 24)}d ago`
}
