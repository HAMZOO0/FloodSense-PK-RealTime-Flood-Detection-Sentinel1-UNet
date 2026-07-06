import { useQuery } from "@tanstack/react-query"
import { LogIn, UserPlus } from "lucide-react"
import * as React from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input, Select } from "@/components/ui/input"
import { api, ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"

export function AuthDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { login, register } = useAuth()
  const [mode, setMode] = React.useState<"login" | "register">("login")
  const [username, setUsername] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [district, setDistrict] = React.useState("")
  const [busy, setBusy] = React.useState(false)

  const districts = useQuery({
    queryKey: ["districts", false],
    queryFn: () => api.districts(false),
    staleTime: Infinity,
    enabled: open && mode === "register",
  })

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      if (mode === "login") await login(username, password)
      else await register(username, password, district || undefined)
      toast.success(mode === "login" ? "Signed in" : "Account created")
      onOpenChange(false)
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Authentication failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {mode === "login" ? "Sign in" : "Create an account"}
          </DialogTitle>
          <DialogDescription>
            {mode === "login"
              ? "Authenticate to issue alerts and follow your home district."
              : "Register with an optional home district for personalised alerts."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-3">
          <Input
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
            required
            minLength={3}
          />
          <Input
            type="password"
            placeholder="Password (min 6 chars)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
          />
          {mode === "register" && (
            <Select value={district} onChange={(e) => setDistrict(e.target.value)}>
              <option value="">Home district (optional)</option>
              {districts.data?.districts.map((d) => (
                <option key={d.name} value={d.name}>
                  {d.name}
                </option>
              ))}
            </Select>
          )}
          <Button type="submit" disabled={busy}>
            {mode === "login" ? <LogIn /> : <UserPlus />}
            {busy ? "Working…" : mode === "login" ? "Sign in" : "Register"}
          </Button>
        </form>

        <button
          type="button"
          className="mt-3 text-xs text-ink-muted transition-colors hover:text-accent-bright"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login"
            ? "No account? Register instead"
            : "Already registered? Sign in"}
        </button>
      </DialogContent>
    </Dialog>
  )
}
