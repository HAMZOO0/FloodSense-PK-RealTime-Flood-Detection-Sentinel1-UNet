import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Loader2, RefreshCw, Waves } from "lucide-react"
import * as React from "react"
import { toast } from "sonner"

import {
  EmptyState,
  PageHeader,
  RiverStatusBadge,
  StatTile,
  TrendChip,
} from "@/components/domain"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { api } from "@/lib/api"

function num(v: unknown): number {
  const n = typeof v === "string" ? Number(v.replace(/,/g, "")) : Number(v)
  return Number.isFinite(n) ? n : 0
}

export function RiversPage() {
  const queryClient = useQueryClient()
  const [refreshing, setRefreshing] = React.useState(false)

  const rivers = useQuery({
    queryKey: ["rivers"],
    queryFn: () => api.rivers(false),
    refetchInterval: 5 * 60_000,
  })

  async function forceRefresh() {
    setRefreshing(true)
    try {
      const fresh = await api.rivers(true)
      queryClient.setQueryData(["rivers"], fresh)
      toast.success("Live FFD data refreshed")
    } catch {
      toast.error("Could not refresh river data")
    } finally {
      setRefreshing(false)
    }
  }

  const stations = rivers.data?.stations ?? []
  const extreme = stations.filter((s) => String(s.status).toUpperCase() === "EXTREME")
  const high = stations.filter((s) => String(s.status).toUpperCase() === "HIGH")
  const maxInflow = Math.max(1, ...stations.map((s) => num(s.inflow)))

  return (
    <>
      <PageHeader
        title="Hydraulic Intelligence"
        subtitle="Live Federal Flood Division discharge data for Indus barrages and gauges — inflow, outflow, trend and flood status."
        actions={
          <Button variant="secondary" size="sm" onClick={forceRefresh} disabled={refreshing}>
            {refreshing ? <Loader2 className="animate-spin" /> : <RefreshCw />}
            Force live refresh
          </Button>
        }
      />

      <div className="grid grid-cols-3 gap-3">
        <StatTile
          label="Stations reporting"
          value={rivers.isPending ? "…" : stations.length}
          icon={<Waves />}
        />
        <StatTile
          label="High flow"
          value={rivers.isPending ? "…" : high.length}
          tone={high.length ? "warning" : "good"}
          hint="FFD status HIGH"
        />
        <StatTile
          label="Extreme flow"
          value={rivers.isPending ? "…" : extreme.length}
          tone={extreme.length ? "critical" : "good"}
          hint="FFD status EXTREME"
        />
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Station discharge</CardTitle>
          <CardDescription>
            Values in cusecs · bar shows inflow relative to the busiest station
            {rivers.data?.scraped_at ? ` · scraped ${rivers.data.scraped_at}` : ""}
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {rivers.isPending && (
            <div className="flex flex-col gap-2 p-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          )}
          {rivers.isError && (
            <div className="p-4">
              <EmptyState
                title="River data unavailable"
                hint="The FFD scraper may be down or the backend is unreachable."
              />
            </div>
          )}
          {rivers.isSuccess && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Station</TableHead>
                  <TableHead>River</TableHead>
                  <TableHead className="text-right">Inflow</TableHead>
                  <TableHead className="w-40">Relative</TableHead>
                  <TableHead className="text-right">Outflow</TableHead>
                  <TableHead>Trend</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stations.map((s, i) => {
                  const name = String(s.station ?? s.name ?? `Station ${i + 1}`)
                  return (
                    <TableRow key={name}>
                      <TableCell className="font-medium text-ink">{name}</TableCell>
                      <TableCell className="text-ink-secondary">
                        {String(s.river ?? "—")}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {num(s.inflow).toLocaleString()}
                      </TableCell>
                      <TableCell>
                        {/* single-hue magnitude bar */}
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-raised">
                          <div
                            className="h-full rounded-full bg-accent"
                            style={{ width: `${(num(s.inflow) / maxInflow) * 100}%` }}
                          />
                        </div>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {num(s.outflow).toLocaleString()}
                      </TableCell>
                      <TableCell>
                        <TrendChip trend={s.inflow_trend ?? s.trend} />
                      </TableCell>
                      <TableCell>
                        <RiverStatusBadge status={s.status} />
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </>
  )
}
