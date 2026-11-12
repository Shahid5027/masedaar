import * as React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  accent?: "default" | "blue" | "green" | "amber" | "red" | "violet";
  badge?: React.ReactNode;
}

const accentRing: Record<NonNullable<MetricCardProps["accent"]>, string> = {
  default: "border-slate-200",
  blue: "border-l-4 border-l-blue-600",
  green: "border-l-4 border-l-emerald-600",
  amber: "border-l-4 border-l-amber-500",
  red: "border-l-4 border-l-red-600",
  violet: "border-l-4 border-l-violet-600",
};

export function MetricCard({
  title,
  value,
  subtitle,
  icon,
  accent = "default",
  badge,
}: MetricCardProps) {
  return (
    <Card className={cn("transition-shadow hover:shadow-md", accentRing[accent])}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              {title}
            </p>
            <p className="mt-2 text-2xl font-bold tracking-tight text-navy-900">{value}</p>
          </div>
          {icon && (
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-navy-800">
              {icon}
            </div>
          )}
        </div>
        {(subtitle || badge) && (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
            {badge}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

