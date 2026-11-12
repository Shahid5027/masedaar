import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors",
  {
    variants: {
      variant: {
        default: "border-slate-200 bg-slate-100 text-slate-800",
        primary: "border-blue-200 bg-blue-50 text-blue-700",
        low: "border-emerald-200 bg-emerald-50 text-emerald-800",
        medium: "border-amber-200 bg-amber-50 text-amber-800",
        high: "border-red-200 bg-red-50 text-red-800",
        demo: "border-violet-200 bg-violet-50 text-violet-800",
        real: "border-sky-200 bg-sky-50 text-sky-800",
        outline: "border-slate-300 bg-white text-slate-700",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

