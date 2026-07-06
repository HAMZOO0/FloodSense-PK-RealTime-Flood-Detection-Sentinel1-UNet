import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { BellPlus, BellRing, Filter, Home } from "lucide-react"
import * as React from "react"
import { toast } from "sonner"

import { EmptyState, PageHeader, SeverityBadge, timeAgo } from "@/components/domain"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Select, Textarea } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { api, ApiError, type Severity } from "@/lib/api"
import { useAuth } from "@/lib/auth"

export function AlertsPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [severity, setSeverity] = React.useState<"" | Severity>("")
  const [district, setDistrict] = React.useState("")
  const [mineOnly, setMineOnly] = React.useState(false)

  // New-alert form
  const [formDistrict, setFormDistrict] = React.useState("")
  const [formSeverity, setFormSeverity] = React.useState<Severity>("MODERATE")
  const [formMessage, setFormMessage] = React.useState("")

  const districts = useQuery({
    queryKey: ["districts", false],
    queryFn: () => api.districts(false),
    staleTime: Infinity,
  })

  const alerts = useQuery({
    queryKey: ["alerts", { severity, district, mineOnly }],
    queryFn: () =>
      mineOnly
        ? api.myAlerts()
        : api.alerts({
            severity: severity || undefined,
            district: district || undefined,
            limit: 100,
          }),
  })

  const create = useMutation({
    mutationFn: () =>
      api.createAlert({
        district: formDistrict,
        severity: formSeverity,
        message: formMessage,
      }),
    onSuccess: () => {
      toast.success(`Alert issued for ${formDistrict}`)
      setFormMessage("")
      queryClient.invalidateQueries({ queryKey: ["alerts"] })
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Could not issue alert"),
  })

  const list = alerts.data?.alerts ?? []

  return (
    <>
      <PageHeader
        title="Alert Command"
        subtitle="Alerts auto-generated when an analysis crosses the risk threshold, plus manual advisories issued by authorities."
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        <Card>
          <CardHeader className="flex-row flex-wrap items-center gap-3">
            <CardTitle className="mr-auto flex items-center gap-2">
              <BellRing className="size-4 text-accent-bright" /> Alert feed
            </CardTitle>
            <div className="flex items-center gap-2">
              <Filter className="size-3.5 text-ink-muted" />
              <Select
                className="h-8 w-40 text-xs"
                value={district}
                disabled={mineOnly}
                onChange={(e) => setDistrict(e.target.value)}
              >
                <option value="">All districts</option>
                {districts.data?.districts.map((d) => (
                  <option key={d.name} value={d.name}>
                    {d.name}
                  </option>
                ))}
              </Select>
              <Select
                className="h-8 w-32 text-xs"
                value={severity}
                disabled={mineOnly}
                onChange={(e) => setSeverity(e.target.value as "" | Severity)}
              >
                <option value="">Any severity</option>
                <option value="HIGH">High</option>
                <option value="MODERATE">Moderate</option>
                <option value="LOW">Low</option>
              </Select>
              {user?.district && (
                <label className="flex cursor-pointer items-center gap-1.5 text-xs text-ink-secondary select-none">
                  <input
                    type="checkbox"
                    checked={mineOnly}
                    onChange={(e) => setMineOnly(e.target.checked)}
                    className="size-3.5 accent-[var(--color-accent)]"
                  />
                  <Home className="size-3.5" /> My district
                </label>
              )}
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 p-3">
            {alerts.isPending &&
              Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            {alerts.isError && (
              <EmptyState
                title="Could not load alerts"
                hint={
                  mineOnly
                    ? "Set a home district on your account first."
                    : "Is the backend API running?"
                }
              />
            )}
            {alerts.isSuccess && list.length === 0 && (
              <EmptyState title="No alerts match" hint="Adjust the filters, or issue one from the panel." />
            )}
            {list.map((al, i) => (
              <div
                key={al.id ?? i}
                className="rounded-lg border border-line bg-base/60 px-4 py-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-semibold text-ink">{al.district}</p>
                  <SeverityBadge severity={al.severity} />
                  {typeof al.risk_score === "number" && (
                    <span className="text-xs text-ink-muted tabular-nums">
                      risk {al.risk_score.toFixed(1)}/10
                    </span>
                  )}
                  <span className="ml-auto text-[11px] text-ink-muted">
                    {al.source === "manual"
                      ? `issued by ${al.issued_by}`
                      : "auto-generated"}{" "}
                    · {timeAgo(al.created_at)}
                  </span>
                </div>
                <p className="mt-1.5 text-sm text-ink-secondary">{al.message}</p>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Issue alert */}
        <Card className="self-start">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BellPlus className="size-4 text-accent-bright" /> Issue an alert
            </CardTitle>
            <CardDescription>
              {user
                ? "Manual advisory — persisted and pushed to the feed."
                : "Sign in (sidebar) to issue manual alerts."}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Select
              value={formDistrict}
              disabled={!user}
              onChange={(e) => setFormDistrict(e.target.value)}
            >
              <option value="">District…</option>
              {districts.data?.districts.map((d) => (
                <option key={d.name} value={d.name}>
                  {d.name}
                </option>
              ))}
            </Select>
            <Select
              value={formSeverity}
              disabled={!user}
              onChange={(e) => setFormSeverity(e.target.value as Severity)}
            >
              <option value="LOW">Low severity</option>
              <option value="MODERATE">Moderate severity</option>
              <option value="HIGH">High severity</option>
            </Select>
            <Textarea
              placeholder="Advisory message (min 5 characters)…"
              value={formMessage}
              disabled={!user}
              onChange={(e) => setFormMessage(e.target.value)}
            />
            <Button
              disabled={
                !user || !formDistrict || formMessage.trim().length < 5 || create.isPending
              }
              onClick={() => create.mutate()}
            >
              <BellPlus />
              {create.isPending ? "Issuing…" : "Issue alert"}
            </Button>
          </CardContent>
        </Card>
      </div>
    </>
  )
}
