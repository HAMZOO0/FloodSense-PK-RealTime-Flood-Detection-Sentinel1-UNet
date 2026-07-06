import { BookOpenText, Loader2, MessageSquareText, Send, User } from "lucide-react"
import * as React from "react"

import { PageHeader } from "@/components/domain"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { api, ApiError, type ChatSource } from "@/lib/api"
import { RichText } from "@/pages/IntelligencePage"
import { cn } from "@/lib/utils"

interface Message {
  role: "user" | "assistant"
  text: string
  sources?: ChatSource[]
  error?: boolean
}

const SUGGESTIONS = [
  "What should citizens do during a HIGH flood alert?",
  "How does the 2010 flood benchmark work?",
  "Which districts are most flood-prone in Sindh?",
  "How is the risk score calculated?",
]

export function AssistantPage() {
  const [messages, setMessages] = React.useState<Message[]>([])
  const [input, setInput] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const endRef = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, busy])

  async function ask(question: string) {
    const q = question.trim()
    if (!q || busy) return
    setInput("")
    setMessages((m) => [...m, { role: "user", text: q }])
    setBusy(true)
    try {
      const res = await api.chat(q)
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: String(res.answer ?? res.response ?? "No answer returned."),
          sources: res.sources,
        },
      ])
    } catch (err) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          error: true,
          text:
            err instanceof ApiError
              ? err.message
              : "The knowledge assistant is unavailable. The first question can take ~30 s while the knowledge base loads — try again.",
        },
      ])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex h-[calc(100svh-8.5rem)] flex-col">
      <PageHeader
        title="Knowledge Assistant"
        subtitle="RAG-grounded Q&A over the flood knowledge base — every answer cites its sources."
      />

      <Card className="flex min-h-0 flex-1 flex-col">
        <CardContent className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto py-5">
          {messages.length === 0 && (
            <div className="m-auto flex max-w-md flex-col items-center gap-4 text-center">
              <div className="grid size-12 place-items-center rounded-2xl bg-accent/15 text-accent-bright">
                <MessageSquareText className="size-6" />
              </div>
              <p className="text-sm text-ink-secondary">
                Ask about flood safety, districts, the detection pipeline, or
                emergency procedures. Answers are retrieved from the curated
                knowledge base — not free-form generation.
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => ask(s)}
                    className="rounded-full border border-line bg-raised px-3 py-1.5 text-xs text-ink-secondary transition-colors hover:border-accent/50 hover:text-ink"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div
              key={i}
              className={cn("flex gap-3", m.role === "user" && "flex-row-reverse")}
            >
              <div
                className={cn(
                  "grid size-7 shrink-0 place-items-center rounded-lg",
                  m.role === "user"
                    ? "bg-raised text-ink-secondary"
                    : "bg-accent/15 text-accent-bright",
                )}
              >
                {m.role === "user" ? (
                  <User className="size-3.5" />
                ) : (
                  <MessageSquareText className="size-3.5" />
                )}
              </div>
              <div
                className={cn(
                  "max-w-[75%] rounded-xl px-4 py-3",
                  m.role === "user"
                    ? "rounded-tr-sm bg-accent/15 text-sm text-ink"
                    : m.error
                      ? "rounded-tl-sm border border-status-critical/30 bg-status-critical/8 text-sm text-ink-secondary"
                      : "rounded-tl-sm border border-line bg-base/60",
                )}
              >
                {m.role === "assistant" && !m.error ? (
                  <RichText text={m.text} />
                ) : (
                  m.text
                )}
                {(m.sources?.length ?? 0) > 0 && (
                  <div className="mt-3 flex flex-col gap-1 border-t border-line pt-2">
                    <p className="flex items-center gap-1 text-[10px] font-semibold tracking-wider text-ink-muted uppercase">
                      <BookOpenText className="size-3" /> Sources
                    </p>
                    {m.sources!.map((s, j) => (
                      <p key={j} className="truncate text-[11px] text-ink-muted">
                        {String(s.title ?? s.source ?? JSON.stringify(s)).slice(0, 120)}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {busy && (
            <div className="flex items-center gap-2 text-xs text-ink-muted">
              <Loader2 className="size-3.5 animate-spin text-accent-bright" />
              Retrieving from the knowledge base…
            </div>
          )}
          <div ref={endRef} />
        </CardContent>

        <form
          className="flex items-center gap-2 border-t border-line px-4 py-3"
          onSubmit={(e) => {
            e.preventDefault()
            ask(input)
          }}
        >
          <Input
            placeholder="Ask the flood knowledge base…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={busy}
          />
          <Button type="submit" size="icon" disabled={busy || !input.trim()}>
            <Send />
          </Button>
        </form>
      </Card>
    </div>
  )
}
