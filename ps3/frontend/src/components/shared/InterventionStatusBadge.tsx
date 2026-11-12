import { Badge } from "@/components/ui/badge";
import { InterventionStatus } from "@/lib/types";

const STATUS_STYLE: Record<
  InterventionStatus,
  { label: string; className: string }
> = {
  PENDING: {
    label: "Pending Review",
    className: "border-slate-300 bg-slate-100 text-slate-800",
  },
  ASSIGNED: {
    label: "Assigned",
    className: "border-blue-200 bg-blue-50 text-blue-800",
  },
  IN_PROGRESS: {
    label: "In Progress",
    className: "border-indigo-200 bg-indigo-50 text-indigo-800",
  },
  FOLLOW_UP_REQUIRED: {
    label: "Follow-Up Required",
    className: "border-amber-300 bg-amber-50 text-amber-900",
  },
  COMPLETED: {
    label: "Completed",
    className: "border-emerald-200 bg-emerald-50 text-emerald-800",
  },
  CANCELLED: {
    label: "Cancelled",
    className: "border-slate-200 bg-slate-50 text-slate-500 line-through",
  },
};

export function InterventionStatusBadge({ status }: { status: InterventionStatus | string }) {
  const normalized = (status || "PENDING").toUpperCase() as InterventionStatus;
  const meta = STATUS_STYLE[normalized] ?? STATUS_STYLE.PENDING;
  return (
    <Badge variant="outline" className={meta.className}>
      {meta.label}
    </Badge>
  );
}

