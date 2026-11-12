import React from "react";
import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  status: string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const normalized = status.toLowerCase();

  let styles = "bg-slate-100 text-slate-700 border-slate-200";
  let label = status;

  if (normalized === "evaluated" || normalized === "approved" || normalized === "healthy") {
    styles = "bg-emerald-50 text-emerald-700 border-emerald-200";
    label = normalized === "healthy" ? "Backend Online" : "Evaluated";
  } else if (normalized === "flagged_for_review" || normalized === "flagged" || normalized === "pending") {
    styles = "bg-amber-50 text-amber-700 border-amber-200";
    label = "Review Needed";
  } else if (normalized === "overridden" || normalized === "moderated") {
    styles = "bg-purple-50 text-purple-700 border-purple-200";
    label = "Moderated";
  } else if (normalized === "submitted" || normalized === "processing") {
    styles = "bg-blue-50 text-blue-700 border-blue-200";
    label = normalized === "processing" ? "Grading..." : "Submitted";
  } else if (normalized === "offline" || normalized === "error") {
    styles = "bg-rose-50 text-rose-700 border-rose-200";
    label = "Offline";
  }

  return (
    <span className={cn("inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border", styles)}>
      <span className="w-1.5 h-1.5 rounded-full mr-1.5 bg-current" />
      {label}
    </span>
  );
}

