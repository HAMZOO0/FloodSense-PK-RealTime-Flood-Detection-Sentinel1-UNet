import { cva, type VariantProps } from "class-variance-authority"
import * as React from "react"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold tracking-wide uppercase [&_svg]:size-3",
  {
    variants: {
      variant: {
        default: "border-line-strong bg-raised text-ink-secondary",
        accent: "border-accent/40 bg-accent/15 text-accent-bright",
        good: "border-status-good/40 bg-status-good/12 text-status-good",
        warning: "border-status-warning/40 bg-status-warning/12 text-status-warning",
        serious: "border-status-serious/40 bg-status-serious/12 text-status-serious",
        critical:
          "border-status-critical/45 bg-status-critical/15 text-[#e46666]",
      },
    },
    defaultVariants: { variant: "default" },
  },
)

function Badge({
  className,
  variant,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
