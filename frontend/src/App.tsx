import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, Route, Routes } from "react-router-dom"
import { Toaster } from "sonner"

import { AppShell } from "@/components/AppShell"
import { AuthProvider } from "@/lib/auth"
import { AlertsPage } from "@/pages/AlertsPage"
import { AssistantPage } from "@/pages/AssistantPage"
import { DetectionPage } from "@/pages/DetectionPage"
import { IntelligencePage } from "@/pages/IntelligencePage"
import { OverviewPage } from "@/pages/OverviewPage"
import { RiversPage } from "@/pages/RiversPage"
import { WorkflowPage } from "@/pages/WorkflowPage"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 60_000 },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<OverviewPage />} />
              <Route path="detection" element={<DetectionPage />} />
              <Route path="rivers" element={<RiversPage />} />
              <Route path="intelligence" element={<IntelligencePage />} />
              <Route path="workflow" element={<WorkflowPage />} />
              <Route path="alerts" element={<AlertsPage />} />
              <Route path="assistant" element={<AssistantPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster
          position="bottom-right"
          theme="dark"
          toastOptions={{
            style: {
              background: "var(--color-raised)",
              border: "1px solid var(--color-line-strong)",
              color: "var(--color-ink)",
            },
          }}
        />
      </AuthProvider>
    </QueryClientProvider>
  )
}
