import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return `${value.toFixed(digits)}%`;
}

export function formatProbability(prob: number | null | undefined): string {
  if (prob === null || prob === undefined || Number.isNaN(prob)) {
    return "—";
  }
  return `${(prob * 100).toFixed(1)}%`;
}

export function formatDateTime(isoString: string | null | undefined): string {
  if (!isoString) {
    return "—";
  }
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return isoString;
  }
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function humanizeFeatureName(feature: string): string {
  const labels: Record<string, string> = {
    attendance_rate: "Attendance Rate",
    average_grade: "Average Grade",
    late_assignments: "Late Assignments",
    missing_assignments: "Missing Assignments",
    lms_logins_30d: "LMS Logins (30d)",
    engagement_change_pct: "Engagement Change %",
    previous_failure_count: "Previous Failures",
  };
  return labels[feature] ?? feature.replace(/_/g, " ");
}

export function humanizeInterventionType(type: string): string {
  return type
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

