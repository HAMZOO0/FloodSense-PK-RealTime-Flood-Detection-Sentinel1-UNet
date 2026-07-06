import { useQuery } from "@tanstack/react-query"
import { Loader2, RefreshCw, Sparkles } from "lucide-react"
import * as React from "react"
import { useSearchParams } from "react-router-dom"

import { EmptyState, PageHeader } from "@/components/domain"
import { Badge } from "@/components/ui/badge"
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
import { api } from "@/lib/api"

/** Light markdown-ish renderer: paragraphs, **bold**, headings, bullets. */
export function RichText({ text }: { text: string }) {
  const blocks = text.split(/\n{2,}/)
  return (
    <div className="flex flex-col gap-3 text-sm leading-relaxed text-ink-secondary">
      {blocks.map((block, i) => {
        const lines = block.split("\n")
        const isList = lines.every((l) => /^\s*([-*•]|\d+[.)])\s+/.test(l.trim()) || !l.trim())
        if (isList) {
          return (
            <ul key={i} className="ml-4 flex list-disc flex-col gap-1 marker:text-accent-bright">
              {lines
                .filter((l) => l.trim())
                .map((l, j) => (
                  <li key={j}>{inline(l.replace(/^\s*([-*•]|\d+[.)])\s+/, ""))}</li>
                ))}
            </ul>
          )
        }
        const heading = block.match(/^#{1,4}\s+(.*)/)
        if (heading) {
          return (
            <h4 key={i} className="font-display text-sm font-semibold text-ink">
              {inline(heading[1])}
            </h4>
          )
        }
        return <p key={i}>{inline(block)}</p>
      })}
    </div>
  )
}

function inline(s: string): React.ReactNode {
  // **bold** segments become emphasised ink
  const parts = s.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((p, i) =>
    p.startsWith("**") && p.endsWith("**") ? (
      <strong key={i} className="font-semibold text-ink">
        {p.slice(2, -2)}
      </strong>
    ) : (
      p
    ),
  )
}

export function IntelligencePage() {
  const [params, setParams] = useSearchParams()
  const district = params.get("district") ?? ""

  const analyses = useQuery({
    queryKey: ["analyses"],
    queryFn: () => api.latestAnalyses(200),
  })

  const insights = useQuery({
    queryKey: ["insights", district],
    queryFn: () => api.insights(district),
    enabled: !!district,
    staleTime: 5 * 60_000,
    retry: false,
  })

  const analysed = analyses.data?.analyses ?? []

  return (
    <>
      <PageHeader
        title="AI Tactical Intelligence"
        subtitle="Gemini / Groq strategic report grounded in the latest satellite analysis, the 2010 benchmark and live river hydraulics."
      />

      <Card>
        <CardContent className="flex flex-wrap items-end gap-3">
          <div className="min-w-56 flex-1">
            <label className="mb-1 block text-[11px] font-semibold tracking-wider text-ink-muted uppercase">
              Analysed district
            </label>
            <Select
              value={district}
              onChange={(e) =>
                setParams(e.target.value ? { district: e.target.value } : {})
              }
            >
              <option value="">Select a district with a stored analysis…</option>
              {analysed.map((a) => (
                <option key={a.district} value={a.district}>
                  {a.district} — risk {a.risk_score?.toFixed(1)}/10
                </option>
              ))}
            </Select>
          </div>
          <Button
            variant="secondary"
            disabled={!district || insights.isFetching}
            onClick={() => insights.refetch()}
          >
            {insights.isFetching ? <Loader2 className="animate-spin" /> : <RefreshCw />}
            Regenerate
          </Button>
        </CardContent>
      </Card>

      {!district && (
        <div className="mt-4">
          <EmptyState
            icon={<Sparkles />}
            title="Select an analysed district"
            hint="The report is grounded in a stored analysis — run one on the Detection page first."
          />
        </div>
      )}

      {district && insights.isPending && (
        <Card className="mt-4">
          <CardContent className="flex flex-col gap-3 py-6">
            <div className="flex items-center gap-2 text-sm text-ink-secondary">
              <Loader2 className="size-4 animate-spin text-accent-bright" />
              Generating grounded report for {district}…
            </div>
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
          </CardContent>
        </Card>
      )}

      {district && insights.isError && (
        <div className="mt-4">
          <EmptyState
            title={`No insights available for ${district}`}
            hint="Make sure this district has a completed analysis, then regenerate."
          />
        </div>
      )}

      {district && insights.isSuccess && (
        <Card className="mt-4">
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="size-4 text-accent-bright" />
                Tactical report — {district}
              </CardTitle>
              <CardDescription>
                Grounded in the latest stored analysis and FFD river data
              </CardDescription>
            </div>
            <Badge variant={insights.data.llm_used ? "accent" : "default"}>
              {insights.data.llm_used ? "LLM-generated" : "Simulated fallback"}
            </Badge>
          </CardHeader>
          <CardContent>
            <RichText text={String(insights.data.insights ?? "No report content.")} />
          </CardContent>
        </Card>
      )}
    </>
  )
}
