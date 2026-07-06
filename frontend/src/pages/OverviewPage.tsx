import { useQuery } from "@tanstack/react-query"
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Bell,
  MapPinned,
  Satellite,
  ShieldAlert,
} from "lucide-react"
import { Link } from "react-router-dom"

import {
  EmptyState,
  PageHeader,
  SeverityBadge,
  StatTile,
  riskColor,
  timeAgo,
} from "@/components/domain"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"

export function OverviewPage() {
  const analyses = useQuery({
    queryKey: ["analyses"],
    queryFn: () => api.latestAnalyses(200),
  })
  const alerts = useQuery({
    queryKey: ["alerts", "recent"],
    queryFn: () => api.alerts({ limit: 8 }),
  })

  const rows = analyses.data?.analyses ?? []
  const highRisk = rows.filter((a) => a.risk_score >= 7)
  const avgRisk = rows.length
    ? rows.reduce((s, a) => s + (a.risk_score ?? 0), 0) / rows.length
    : 0
  const worst = rows[0]

  return (
    <>
      <PageHeader
        title="National Command Overview"
        subtitle="Latest satellite analysis per district, ranked by defensible risk score — SAR + U-Net detection fused with the 2010 benchmark and live river hydraulics."
        actions={
          <Button asChild size="sm">
            <Link to="/detection">
              <Satellite /> Run new analysis
            </Link>
          </Button>
        }
      />

      {/* Stat tiles */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="Districts analysed"
          value={analyses.isPending ? "…" : rows.length}
          icon={<MapPinned />}
          hint="with a stored satellite analysis"
        />
        <StatTile
          label="High-risk districts"
          value={analyses.isPending ? "…" : highRisk.length}
          icon={<ShieldAlert />}
          tone={highRisk.length > 0 ? "critical" : "good"}
          hint="risk score ≥ 7 / 10"
        />
        <StatTile
          label="Mean risk score"
          value={analyses.isPending ? "…" : avgRisk.toFixed(1)}
          icon={<Activity />}
          tone={avgRisk >= 7 ? "critical" : avgRisk >= 4 ? "warning" : "good"}
          hint="across analysed districts"
        />
        <StatTile
          label="Active alerts"
          value={alerts.isPending ? "…" : (alerts.data?.count ?? 0)}
          icon={<Bell />}
          tone={(alerts.data?.count ?? 0) > 0 ? "warning" : "good"}
          hint="latest issued alerts"
        />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_360px]">
        {/* Risk ranking */}
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle>District risk ranking</CardTitle>
              <CardDescription>
                Newest analysis per district, highest risk first
              </CardDescription>
            </div>
            {worst && (
              <Badge variant={worst.risk_score >= 7 ? "critical" : "warning"}>
                <ShieldAlert /> Worst: {worst.district}
              </Badge>
            )}
          </CardHeader>
          <CardContent className="flex flex-col gap-1 p-3">
            {analyses.isPending &&
              Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            {analyses.isError && (
              <EmptyState
                title="Could not load analyses"
                hint="Is the backend running? Start it with: uvicorn backend.app:app --port 8000"
              />
            )}
            {analyses.isSuccess && rows.length === 0 && (
              <EmptyState
                title="No analyses yet"
                hint={
                  <>
                    Run your first district analysis from the{" "}
                    <Link className="text-accent-bright underline" to="/detection">
                      Detection
                    </Link>{" "}
                    page.
                  </>
                }
              />
            )}
            {rows.slice(0, 12).map((a) => (
              <Link
                key={a.district}
                to={`/detection?district=${encodeURIComponent(a.district)}`}
                className="group grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 rounded-lg px-3 py-2 transition-colors hover:bg-raised"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <p className="truncate text-sm font-medium text-ink group-hover:text-accent-bright">
                    {a.district}
                  </p>
                  <p className="text-xs text-ink-muted">
                    {a.flood_pct_current?.toFixed(1)}% flooded ·{" "}
                    {timeAgo(a.created_at)}
                  </p>
                </div>
                <p
                  className="w-14 text-right font-display text-sm font-semibold tabular-nums"
                  style={{ color: riskColor(a.risk_score) }}
                >
                  {a.risk_score?.toFixed(1)}
                  <span className="text-[10px] text-ink-muted"> /10</span>
                </p>
                {/* Magnitude bar — single-hue, thin mark */}
                <div className="col-span-2 h-1 overflow-hidden rounded-full bg-raised">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${(Math.min(10, a.risk_score) / 10) * 100}%`,
                      background: riskColor(a.risk_score),
                    }}
                  />
                </div>
              </Link>
            ))}
          </CardContent>
        </Card>

        {/* Recent alerts */}
        <Card className="self-start">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Recent alerts</CardTitle>
            <Button asChild variant="ghost" size="sm">
              <Link to="/alerts">View all</Link>
            </Button>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {alerts.isPending &&
              Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            {alerts.isSuccess && (alerts.data?.alerts.length ?? 0) === 0 && (
              <EmptyState title="No alerts issued" hint="All monitored districts are quiet." />
            )}
            {alerts.data?.alerts.map((al, i) => (
              <div
                key={al.id ?? i}
                className="rounded-lg border border-line bg-base/60 px-3 py-2.5"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold text-ink">{al.district}</p>
                  <SeverityBadge severity={al.severity} />
                </div>
                <p className="mt-1 line-clamp-2 text-xs text-ink-secondary">
                  {al.message}
                </p>
                <p className="mt-1 text-[10px] text-ink-muted">
                  {al.source === "manual" ? `by ${al.issued_by}` : "auto-generated"} ·{" "}
                  {timeAgo(al.created_at)}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Delta strip */}
      {rows.length > 0 && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle>Change vs 2010 benchmark</CardTitle>
            <CardDescription>
              Current flood extent minus the 2010 historical maximum (Landsat-5 MNDWI)
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {rows.slice(0, 10).map((a) => {
              const worse = a.delta_vs_2010 > 0
              return (
                <div
                  key={a.district}
                  className="flex items-center gap-2 rounded-md border border-line bg-base/60 px-3 py-1.5"
                >
                  <span className="text-xs text-ink-secondary">{a.district}</span>
                  <span
                    className={`inline-flex items-center gap-0.5 text-xs font-semibold tabular-nums ${
                      worse ? "text-status-serious" : "text-aqua"
                    }`}
                  >
                    {worse ? (
                      <ArrowUpRight className="size-3.5" />
                    ) : (
                      <ArrowDownRight className="size-3.5" />
                    )}
                    {worse ? "+" : ""}
                    {a.delta_vs_2010?.toFixed(1)} pp
                  </span>
                </div>
              )
            })}
          </CardContent>
        </Card>
      )}
    </>
  )
}
