import { useQuery, useQueryClient } from "@tanstack/react-query"
import {
  CalendarRange,
  Cpu,
  Droplets,
  Gauge as GaugeIcon,
  Loader2,
  MapPinned,
  Play,
  Satellite,
  Waves,
} from "lucide-react"
import * as React from "react"
import { useSearchParams } from "react-router-dom"
import { toast } from "sonner"

import {
  EmptyState,
  PageHeader,
  RiskGauge,
  RiverStatusBadge,
  SeverityBadge,
  StatTile,
  TrendChip,
  riskLabel,
} from "@/components/domain"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Select } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { api, ApiError } from "@/lib/api"

type RunState =
  | { phase: "idle" }
  | { phase: "queued" | "running"; jobId: string }
  | { phase: "failed"; error: string }

export function DetectionPage() {
  const [params, setParams] = useSearchParams()
  const district = params.get("district") ?? ""
  const [priorityOnly, setPriorityOnly] = React.useState(true)
  const [run, setRun] = React.useState<RunState>({ phase: "idle" })
  const queryClient = useQueryClient()

  const districts = useQuery({
    queryKey: ["districts", priorityOnly],
    queryFn: () => api.districts(priorityOnly),
    staleTime: Infinity,
  })

  const latest = useQuery({
    queryKey: ["analysis", district],
    queryFn: () => api.latestAnalysis(district),
    enabled: !!district,
    retry: false,
  })

  // Poll the background job until it completes, then refresh the analysis.
  React.useEffect(() => {
    if (run.phase !== "queued" && run.phase !== "running") return
    const id = setInterval(async () => {
      try {
        const { job } = await api.job(run.jobId)
        if (job.status === "complete") {
          setRun({ phase: "idle" })
          toast.success(`Analysis complete for ${district}`)
          queryClient.invalidateQueries({ queryKey: ["analysis", district] })
          queryClient.invalidateQueries({ queryKey: ["analyses"] })
        } else if (job.status === "failed") {
          setRun({ phase: "failed", error: job.error ?? "Analysis job failed" })
          toast.error(job.error ?? "Analysis job failed")
        } else {
          setRun({ phase: job.status === "running" ? "running" : "queued", jobId: run.jobId })
        }
      } catch {
        /* transient poll error — keep polling */
      }
    }, 4000)
    return () => clearInterval(id)
  }, [run, district, queryClient])

  async function startRun() {
    if (!district) return
    try {
      const res = await api.startAnalysis(district)
      setRun({ phase: "queued", jobId: res.job_id })
      toast.info(`Analysis queued for ${district} — SAR fetch + U-Net inference takes a few minutes.`)
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not start analysis")
    }
  }

  const a = latest.data?.analysis
  const running = run.phase === "queued" || run.phase === "running"

  return (
    <>
      <PageHeader
        title="Satellite Flood Detection"
        subtitle="Sentinel-1 SAR imagery through the U-Net (ResNet-34) segmentation model, benchmarked against the 2010 Landsat-5 MNDWI flood maximum."
      />

      {/* Control row */}
      <Card>
        <CardContent className="flex flex-wrap items-end gap-3">
          <div className="min-w-56 flex-1">
            <label className="mb-1 block text-[11px] font-semibold tracking-wider text-ink-muted uppercase">
              District
            </label>
            <Select
              value={district}
              onChange={(e) => {
                setRun({ phase: "idle" })
                setParams(e.target.value ? { district: e.target.value } : {})
              }}
            >
              <option value="">Select a district…</option>
              {districts.data?.districts.map((d) => (
                <option key={d.name} value={d.name}>
                  {d.name}
                  {d.is_priority ? "  ★" : ""}
                </option>
              ))}
            </Select>
          </div>
          <label className="flex h-9 cursor-pointer items-center gap-2 text-xs text-ink-secondary select-none">
            <input
              type="checkbox"
              checked={priorityOnly}
              onChange={(e) => setPriorityOnly(e.target.checked)}
              className="size-3.5 accent-[var(--color-accent)]"
            />
            Priority districts only
          </label>
          <Button onClick={startRun} disabled={!district || running}>
            {running ? <Loader2 className="animate-spin" /> : <Play />}
            {running
              ? run.phase === "queued"
                ? "Queued…"
                : "Analysing…"
              : "Run analysis"}
          </Button>
        </CardContent>
      </Card>

      {!district && (
        <div className="mt-4">
          <EmptyState
            icon={<Satellite />}
            title="Pick a district to begin"
            hint="Choose a district above, then run a full SAR + U-Net analysis or view its last stored result."
          />
        </div>
      )}

      {district && latest.isPending && (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-80" />
          <Skeleton className="h-80" />
        </div>
      )}

      {district && latest.isError && !running && (
        <div className="mt-4">
          <EmptyState
            icon={<Satellite />}
            title={`No stored analysis for ${district}`}
            hint='Click "Run analysis" to queue one — results appear here automatically when the job completes.'
          />
        </div>
      )}

      {running && (
        <Card className="mt-4 border-accent/30">
          <CardContent className="flex items-center gap-3 py-4">
            <Loader2 className="size-4 animate-spin text-accent-bright" />
            <div>
              <p className="text-sm font-medium text-ink">
                {run.phase === "queued" ? "Job queued" : "Analysis running"} for{" "}
                {district}
              </p>
              <p className="text-xs text-ink-muted">
                Fetching Sentinel-1 SAR → tiled U-Net inference → 2010 benchmark →
                weighted risk score. This page polls the job every 4 s.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {a && (
        <>
          {/* Metric tiles */}
          <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile
              label="Current flood extent"
              value={`${a.flood_pct_current?.toFixed(2)}%`}
              icon={<Droplets />}
              hint="of district area (U-Net on SAR)"
            />
            <StatTile
              label="2010 benchmark"
              value={`${a.flood_pct_2010?.toFixed(2)}%`}
              icon={<CalendarRange />}
              hint="Landsat-5 MNDWI maximum"
            />
            <StatTile
              label="Δ vs 2010"
              value={`${a.delta_vs_2010 > 0 ? "+" : ""}${a.delta_vs_2010?.toFixed(2)} pp`}
              tone={a.delta_vs_2010 > 0 ? "critical" : "good"}
              icon={<GaugeIcon />}
              hint={a.delta_vs_2010 > 0 ? "worse than 2010 peak" : "below 2010 peak"}
            />
            <StatTile
              label="Affected area"
              value={`${Math.round(a.affected_area_km2).toLocaleString()} km²`}
              icon={<MapPinned />}
              hint={`${a.flood_pixels?.toLocaleString()} flood pixels`}
            />
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_340px]">
            {/* Flood map */}
            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <div>
                  <CardTitle>Flood overlay — {a.district}</CardTitle>
                  <CardDescription>
                    Sentinel-1 SAR {a.sar_window?.start} → {a.sar_window?.end} · U-Net
                    water mask in blue
                  </CardDescription>
                </div>
                <SeverityBadge severity={riskLabel(a.risk_score)} />
              </CardHeader>
              <CardContent>
                <img
                  key={a.created_at}
                  src={`${api.analysisImageUrl(a.district)}?t=${a.created_at ?? ""}`}
                  alt={`Flood detection overlay for ${a.district}`}
                  className="w-full rounded-lg border border-line"
                />
              </CardContent>
            </Card>

            {/* Risk panel */}
            <div className="flex flex-col gap-4">
              <Card>
                <CardHeader>
                  <CardTitle>Defensible risk score</CardTitle>
                  <CardDescription>
                    extent 40% · Δ vs 2010 30% · hydraulics 30%
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col items-center gap-2">
                  <RiskGauge score={a.risk_score} />
                  <SeverityBadge severity={riskLabel(a.risk_score)} />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Model & data</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-2 text-xs">
                  <Row icon={<Cpu />} k="Model" v={String(a.model_used ?? "U-Net ResNet-34")} />
                  <Row
                    icon={<GaugeIcon />}
                    k="Confidence"
                    v={
                      typeof a.confidence === "number"
                        ? `${(a.confidence * 100).toFixed(0)}%`
                        : String(a.confidence ?? "—")
                    }
                  />
                  <Row
                    icon={<MapPinned />}
                    k="Settlement risk"
                    v={String(a.settlement_risk ?? "—")}
                  />
                  <Row
                    icon={<Satellite />}
                    k="SAR window"
                    v={`${a.sar_window?.start ?? "—"} → ${a.sar_window?.end ?? "—"}`}
                  />
                </CardContent>
              </Card>

              {a.river && (
                <Card>
                  <CardHeader className="flex-row items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      <Waves className="size-4 text-accent-bright" /> Matched gauge
                    </CardTitle>
                    <RiverStatusBadge status={a.river.status} />
                  </CardHeader>
                  <CardContent className="text-xs">
                    <p className="font-medium text-ink">
                      {a.river.station ?? a.river.name}
                    </p>
                    <div className="mt-2 flex items-center justify-between text-ink-secondary">
                      <span>
                        Inflow{" "}
                        <span className="font-semibold text-ink tabular-nums">
                          {Number(a.river.inflow ?? 0).toLocaleString()}
                        </span>{" "}
                        cusecs
                      </span>
                      <TrendChip trend={a.river.inflow_trend ?? a.river.trend} />
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </>
      )}
    </>
  )
}

function Row({
  icon,
  k,
  v,
}: {
  icon: React.ReactNode
  k: string
  v: string
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="flex items-center gap-2 text-ink-muted [&_svg]:size-3.5">
        {icon}
        {k}
      </span>
      <span className="text-right font-medium text-ink">{v}</span>
    </div>
  )
}
