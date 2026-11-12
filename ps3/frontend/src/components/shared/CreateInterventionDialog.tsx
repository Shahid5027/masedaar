"use client";

import * as React from "react";
import { X } from "lucide-react";
import { interventionService } from "@/services/interventionService";
import { InterventionPriority, InterventionRecordOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Alert } from "@/components/ui/feedback";

const INTERVENTION_TYPES = [
  { value: "advisor_outreach", label: "Advisor Outreach" },
  { value: "faculty_check_in", label: "Faculty Check-In" },
  { value: "assignment_planning", label: "Assignment Planning" },
  { value: "subject_tutoring", label: "Subject Tutoring" },
  { value: "time_management_coaching", label: "Time Management Coaching" },
  { value: "access_and_engagement_check", label: "Access & Engagement Check" },
  { value: "academic_advising", label: "Academic Advising" },
  { value: "counselor_review", label: "Counselor Review" },
];

interface CreateInterventionDialogProps {
  open: boolean;
  initialStudentId?: string;
  initialPredictionId?: number | null;
  initialType?: string;
  initialPriority?: InterventionPriority;
  initialAction?: string;
  onClose: () => void;
  onCreated: (created: InterventionRecordOut) => void;
}

export function CreateInterventionDialog({
  open,
  initialStudentId = "",
  initialPredictionId = null,
  initialType = "advisor_outreach",
  initialPriority = "medium",
  initialAction = "",
  onClose,
  onCreated,
}: CreateInterventionDialogProps) {
  const [studentId, setStudentId] = React.useState(initialStudentId);
  const [interventionType, setInterventionType] = React.useState(initialType);
  const [priority, setPriority] = React.useState<InterventionPriority>(initialPriority);
  const [recommendedAction, setRecommendedAction] = React.useState(initialAction);
  const [assignedTo, setAssignedTo] = React.useState("");
  const [followUpDate, setFollowUpDate] = React.useState("");
  const [notes, setNotes] = React.useState("");
  const [actorId, setActorId] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setStudentId(initialStudentId);
      setInterventionType(initialType || "advisor_outreach");
      setPriority(initialPriority || "medium");
      setRecommendedAction(initialAction);
      setAssignedTo("");
      setFollowUpDate("");
      setNotes("");
      setError(null);
    }
  }, [open, initialStudentId, initialType, initialPriority, initialAction]);

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!studentId.trim() || !recommendedAction.trim()) {
      setError("Student ID and recommended action description are required.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const res = await interventionService.createIntervention({
        student_id: studentId.trim(),
        prediction_id: initialPredictionId ?? undefined,
        intervention_type: interventionType,
        recommended_action: recommendedAction.trim(),
        priority,
        assigned_to: assignedTo.trim() || undefined,
        follow_up_date: followUpDate ? new Date(`${followUpDate}T12:00:00Z`).toISOString() : undefined,
        notes: notes.trim() || undefined,
        actor_id: actorId.trim() || undefined,
      });
      onCreated(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create intervention.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-intervention-title"
    >
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="create-intervention-title" className="text-lg font-semibold text-navy-900">
              Create Human-Reviewed Intervention
            </h2>
            <p className="mt-0.5 text-xs text-slate-600">
              AI predictions are advisory only; counsellor approval creates this case record.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            aria-label="Close intervention dialog"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={(e) => void handleSubmit(e)} className="mt-4 space-y-3.5">
          {error && (
            <Alert variant="error">
              <p className="text-xs font-medium">{error}</p>
            </Alert>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label
                htmlFor="intr-student-id"
                className="mb-1 block text-xs font-semibold text-slate-700"
              >
                Student ID *
              </label>
              <Input
                id="intr-student-id"
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
                placeholder="e.g. STU-1001"
                required
              />
            </div>

            <div>
              <label
                htmlFor="intr-priority"
                className="mb-1 block text-xs font-semibold text-slate-700"
              >
                Priority
              </label>
              <Select
                id="intr-priority"
                value={priority}
                onChange={(e) => setPriority(e.target.value as InterventionPriority)}
              >
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </Select>
            </div>
          </div>

          <div>
            <label htmlFor="intr-type" className="mb-1 block text-xs font-semibold text-slate-700">
              Intervention Category
            </label>
            <Select
              id="intr-type"
              value={interventionType}
              onChange={(e) => setInterventionType(e.target.value)}
            >
              {INTERVENTION_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </Select>
          </div>

          <div>
            <label
              htmlFor="intr-action"
              className="mb-1 block text-xs font-semibold text-slate-700"
            >
              Action Description *
            </label>
            <textarea
              id="intr-action"
              rows={3}
              required
              value={recommendedAction}
              onChange={(e) => setRecommendedAction(e.target.value)}
              placeholder="Describe the outreach step or support plan reviewed by the counsellor..."
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600/20"
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label
                htmlFor="intr-assignee"
                className="mb-1 block text-xs font-semibold text-slate-700"
              >
                Assign Counsellor (optional)
              </label>
              <Input
                id="intr-assignee"
                value={assignedTo}
                onChange={(e) => setAssignedTo(e.target.value)}
                placeholder="e.g. advisor.smith"
              />
            </div>

            <div>
              <label
                htmlFor="intr-followup"
                className="mb-1 block text-xs font-semibold text-slate-700"
              >
                Follow-Up Date (optional)
              </label>
              <Input
                id="intr-followup"
                type="date"
                value={followUpDate}
                onChange={(e) => setFollowUpDate(e.target.value)}
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label
                htmlFor="intr-actor"
                className="mb-1 block text-xs font-semibold text-slate-700"
              >
                Recorded By (optional label)
              </label>
              <Input
                id="intr-actor"
                value={actorId}
                onChange={(e) => setActorId(e.target.value)}
                placeholder="Unauthenticated session if blank"
              />
            </div>
            <div>
              <label
                htmlFor="intr-notes"
                className="mb-1 block text-xs font-semibold text-slate-700"
              >
                Counsellor Notes (optional)
              </label>
              <Input
                id="intr-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Initial advising context..."
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Creating..." : "Create Intervention"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

