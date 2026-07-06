import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Bot,
  Check,
  ChevronRight,
  Database,
  Landmark,
  Loader2,
  Megaphone,
  Play,
  TrendingUp,
  Users,
  Waves,
} from "lucide-react"
import * as React from "react"
import { useSearchParams } from "react-router-dom"
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { toast } from "sonner"

import { EmptyState, PageHeader, SeverityBadge, StatTile } from "@/components/domain"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input, Select } from "@/components/ui/input"
import { api, ApiError } from "@/lib/api"
import { cn } from "@/lib/utils"

const AGENTS = [
  { name: "Data Fusion", icon: Database, desc: "Satellite + hydraulic + historical" },
  { name: "Intelligence", icon: Bot, desc: "Risk assessment & classification" },
  { name: "Simulation", icon: TrendingUp, desc: "Flood progression projection" },
  { name: "Response", icon: Megaphone, desc: "Citizen & authority alerts" },
] as const

interface Projection {
  horizon_hours: number
  projected_coverage_percentage: number
  projected_affected_area_km2: number
}

interface PipelinePayload {
  district?: string
  population_at_risk?: number
  rag_sources?: string[]
  citizen_alert?: string
  authority_alert?: string
  assessment?: {
    risk_level?: string
    flood_coverage_percentage?: number
    explanation?: string
    recommended_action?: string
    [k: string]: unknown
  }
  progression?: {
    projections?: Projection[]
    peak_coverage_percentage?: number
    downstream_risks?: { district: string; eta_hours: number }[]
    [k: string]: unknown
  }
  [k: string]: unknown
}

function severityFromRiskLevel(level?: string): "LOW" | "MODERATE" | "HIGH" {
  const l = String(level ?? "").toUpperCase()
  if (l.includes("HIGH") || l.includes("SEVERE") || l.includes("CRITICAL")) return "HIGH"
  if (l.includes("MODERATE") || l.includes("MEDIUM")) return "MODERATE"
  return "LOW"
}

export function WorkflowPage() {
  const [params, setParams] = useSearchParams()
  const district = params.get("district") ?? ""
  const [population, setPopulation] = React.useState("")
  const queryClient = useQueryClient()

  const analyses = useQuery({
    queryKey: ["analyses"],
    queryFn: () => api.latestAnalyses(200),
  })

  const pipeline = useMutation({
    mutationFn: () =>
      api.runPipeline(district, population ? Number(population) : undefined),
    onSuccess: () => {
      toast.success(`Workflow complete for ${district} — alerts persisted`)
      queryClient.invalidateQueries({ queryKey: ["alerts"] })
    },
    onError: (err) =>
      toast.error(
        err instanceof ApiError
          ? err.message
          : "Pipeline failed — has this district been analysed?",
      ),
  })

  const result = (pipeline.data?.pipeline ?? null) as PipelinePayload | null
  const running = pipeline.isPending
  const analysed = analyses.data?.analyses ?? []
  const projections = result?.progression?.projections ?? []
  const chartData = projections.map((p) => ({
    hours: p.horizon_hours,
    coverage: p.projected_coverage_percentage,
    area: p.projected_affected_area_km2,
  }))

  return (
    <>
      <PageHeader
        title="Agentic Command Center"
        subtitle="Four cooperating agents turn the latest analysis into a risk assessment, a flood progression forecast, and ready-to-send alerts."
      />

      {/* Controls */}
      <Card>
        <CardContent className="flex flex-wrap items-end gap-3">
          <div className="min-w-56 flex-1">
            <label className="mb-1 block text-[11px] font-semibold tracking-wider text-ink-muted uppercase">
              Analysed district
            </label>
            <Select
              value={district}
              onChange={(e) => {
                pipeline.reset()
                setParams(e.target.value ? { district: e.target.value } : {})
              }}
            >
              <option value="">Select a district with a stored analysis…</option>
              {analysed.map((a) => (
                <option key={a.district} value={a.district}>
                  {a.district} — risk {a.risk_score?.toFixed(1)}/10
                </option>
              ))}
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-semibold tracking-wider text-ink-muted uppercase">
              Population override
            </label>
            <Input
              type="number"
              min={0}
              placeholder="auto (km² × 350)"
              className="w-44"
              value={population}
              onChange={(e) => setPopulation(e.target.value)}
            />
          </div>
          <Button disabled={!district || running} onClick={() => pipeline.mutate()}>
            {running ? <Loader2 className="animate-spin" /> : <Play />}
            {running ? "Agents working…" : "Run workflow"}
          </Button>
        </CardContent>
      </Card>

      {/* Agent stepper */}
      <div className="mt-4 grid grid-cols-2 gap-2 lg:grid-cols-4">
        {AGENTS.map(({ name, icon: Icon, desc }, i) => {
          const done = !!result
          return (
            <div
              key={name}
              className={cn(
                "relative flex items-start gap-3 rounded-card border px-4 py-3 transition-colors",
                done
                  ? "border-aqua/40 bg-aqua/5"
                  : running
                    ? "border-accent/40 bg-accent/5"
                    : "border-line bg-surface",
              )}
            >
              <div
                className={cn(
                  "grid size-8 shrink-0 place-items-center rounded-lg",
                  done
                    ? "bg-aqua/15 text-aqua"
                    : running
                      ? "bg-accent/15 text-accent-bright"
                      : "bg-raised text-ink-muted",
                )}
              >
                {done ? (
                  <Check className="size-4" />
                ) : running ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Icon className="size-4" />
                )}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold text-ink">
                  {i + 1}. {name}
                </p>
                <p className="text-[11px] leading-snug text-ink-muted">{desc}</p>
              </div>
              {i < AGENTS.length - 1 && (
                <ChevronRight className="absolute top-1/2 -right-2 hidden size-4 -translate-y-1/2 text-ink-muted lg:block" />
              )}
            </div>
          )
        })}
      </div>

      {!result && !running && (
        <div className="mt-4">
          <EmptyState
            icon={<Bot />}
            title="Run the workflow to generate a disaster response"
            hint="Requires a completed analysis — the agents consume its satellite, hydraulic and historical intelligence."
          />
        </div>
      )}

      {result && (
        <>
          {/* Assessment */}
          <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile
              label="Risk level"
              value={
                <SeverityBadge
                  severity={severityFromRiskLevel(result.assessment?.risk_level)}
                />
              }
              hint={String(result.assessment?.risk_level ?? "")}
            />
            <StatTile
              label="Flood coverage"
              value={`${Number(result.assessment?.flood_coverage_percentage ?? 0).toFixed(1)}%`}
              icon={<Waves />}
            />
            <StatTile
              label="Population at risk"
              value={Number(result.population_at_risk ?? 0).toLocaleString()}
              icon={<Users />}
              tone="warning"
            />
            <StatTile
              label="Peak projected coverage"
              value={`${Number(result.progression?.peak_coverage_percentage ?? 0).toFixed(1)}%`}
              icon={<TrendingUp />}
              tone="critical"
            />
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            {/* Projection chart */}
            <Card>
              <CardHeader>
                <CardTitle>Projected flood coverage</CardTitle>
                <CardDescription>
                  Simulation Agent forecast, % of district area under water
                </CardDescription>
              </CardHeader>
              <CardContent>
                {chartData.length === 0 ? (
                  <EmptyState title="No projection data" />
                ) : (
                  <div className="h-56">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                        <CartesianGrid stroke="var(--color-line)" vertical={false} />
                        <XAxis
                          dataKey="hours"
                          tickFormatter={(h) => `+${h}h`}
                          stroke="var(--color-ink-muted)"
                          fontSize={11}
                          tickLine={false}
                          axisLine={{ stroke: "var(--color-line-strong)" }}
                        />
                        <YAxis
                          unit="%"
                          stroke="var(--color-ink-muted)"
                          fontSize={11}
                          tickLine={false}
                          axisLine={false}
                        />
                        <Tooltip
                          contentStyle={{
                            background: "var(--color-raised)",
                            border: "1px solid var(--color-line-strong)",
                            borderRadius: 8,
                            fontSize: 12,
                          }}
                          labelFormatter={(h) => `+${h} hours`}
                          formatter={(value, key) =>
                            key === "coverage"
                              ? [`${Number(value).toFixed(1)}%`, "Coverage"]
                              : [`${Math.round(Number(value)).toLocaleString()} km²`, "Area"]
                          }
                        />
                        <Line
                          type="monotone"
                          dataKey="coverage"
                          stroke="var(--color-accent)"
                          strokeWidth={2}
                          dot={{ r: 3, fill: "var(--color-accent)", strokeWidth: 0 }}
                          activeDot={{ r: 5, stroke: "var(--color-base)", strokeWidth: 2 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}
                {(result.progression?.downstream_risks?.length ?? 0) > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {result.progression!.downstream_risks!.map((d) => (
                      <Badge key={d.district} variant="serious">
                        <Waves /> {d.district} ~{Math.round(d.eta_hours)}h
                      </Badge>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Assessment detail */}
            <Card>
              <CardHeader>
                <CardTitle>Intelligence assessment</CardTitle>
                <CardDescription>Explanation & recommended action</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 text-sm text-ink-secondary">
                <p>{String(result.assessment?.explanation ?? "—")}</p>
                <div className="rounded-lg border border-accent/30 bg-accent/8 px-4 py-3">
                  <p className="text-[11px] font-semibold tracking-wider text-accent-bright uppercase">
                    Recommended action
                  </p>
                  <p className="mt-1 text-ink">
                    {String(result.assessment?.recommended_action ?? "—")}
                  </p>
                </div>
                {(result.rag_sources?.length ?? 0) > 0 && (
                  <p className="text-[11px] text-ink-muted">
                    Grounded in: {result.rag_sources!.join(" · ")}
                  </p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Alerts */}
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="size-4 text-accent-bright" /> Citizen alert
                </CardTitle>
                <CardDescription>Public-facing evacuation message</CardDescription>
              </CardHeader>
              <CardContent className="text-sm whitespace-pre-wrap text-ink-secondary">
                {String(result.citizen_alert ?? "—")}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Landmark className="size-4 text-accent-bright" /> Authority alert
                </CardTitle>
                <CardDescription>Operational situation report</CardDescription>
              </CardHeader>
              <CardContent className="text-sm whitespace-pre-wrap text-ink-secondary">
                {String(result.authority_alert ?? "—")}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </>
  )
}
