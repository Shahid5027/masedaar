"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  ArrowUpRight,
  BrainCircuit,
  CalendarClock,
  CheckCircle2,
  ClipboardCheck,
  History,
  Info,
  Play,
  Plus,
  ShieldAlert,
  UserCheck,
} from "lucide-react";
import { studentService } from "@/services/studentService";
import { predictionService } from "@/services/predictionService";
import { interventionService } from "@/services/interventionService";
import { ApiClientError } from "@/lib/api";
import {
  InterventionHistoryOut,
  InterventionPriority,
  InterventionRecordOut,
  StudentDetailData,
  StudentExplanationData,
  StudentInterventionsData,
} from "@/lib/types";
import {
  formatDateTime,
  formatPercent,
  formatProbability,
  humanizeFeatureName,
  humanizeInterventionType,
} from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/feedback";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { RiskBadge } from "@/components/shared/RiskBadge";
import {
  DemoDataBadge,
  ResponsibleAiFooterNotice,
  SyntheticBanner,
} from "@/components/shared/DemoDataBadge";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { useAuth } from "@/components/auth/AuthProvider";
import { ErrorState, PageLoadingSkeleton } from "@/components/shared/StateFeedback";
import { InterventionStatusBadge } from "@/components/shared/InterventionStatusBadge";
import { CreateInterventionDialog } from "@/components/shared/CreateInterventionDialog";

export default function StudentProfilePage() {
  return (
    <RoleGuard allowedRoles={["administrator", "counsellor"]} sectionTitle="Student Profile">
      <StudentProfileContent />
    </RoleGuard>
  );
}

function StudentProfileContent() {
  const { hasRole } = useAuth();
  const isAdmin = hasRole("administrator");
  const params = useParams<{ studentId: string }>();
  const studentId = React.useMemo(
    () => decodeURIComponent(params?.studentId || ""),
    [params?.studentId]
  );

  const [detail, setDetail] = React.useState<StudentDetailData | null>(null);
  const [explanationData, setExplanationData] = React.useState<StudentExplanationData | null>(null);
  const [studentInterventions, setStudentInterventions] =
    React.useState<StudentInterventionsData | null>(null);
  const [noPredictionYet, setNoPredictionYet] = React.useState(false);
  const [loading, setLoading] = React.useState(true);
  const [scoring, setScoring] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [notice, setNotice] = React.useState<{
    variant: "success" | "error";
    text: string;
  } | null>(null);

  const [createDialogOpen, setCreateDialogOpen] = React.useState(false);
  const [createDefaults, setCreateDefaults] = React.useState<{
    type: string;
    priority: InterventionPriority;
    action: string;
  }>({
    type: "advisor_outreach",
    priority: "medium",
    action: "",
  });

  const [expandedHistoryById, setExpandedHistoryById] = React.useState<
    Record<number, InterventionHistoryOut[]>
  >({});
  const [loadingHistoryId, setLoadingHistoryId] = React.useState<number | null>(null);

  const loadStudent = React.useCallback(async () => {
    if (!studentId) return;
    setLoading(true);
    setError(null);
    setNoPredictionYet(false);

    try {
      const [detailRes, expRes, intrRes] = await Promise.all([
        studentService.getStudentDetail(studentId),
        studentService.getStudentExplanation(studentId).catch((err: unknown) => {
          if (err instanceof ApiClientError && err.statusCode === 404) {
            return null;
          }
          throw err;
        }),
        interventionService.listStudentInterventions(studentId).catch(() => null),
      ]);

      setDetail(detailRes.data);
      setStudentInterventions(intrRes ? intrRes.data : null);
      if (expRes) {
        setExplanationData(expRes.data);
      } else {
        setExplanationData(null);
        setNoPredictionYet(true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load student profile.");
    } finally {
      setLoading(false);
    }
  }, [studentId]);

  React.useEffect(() => {
    void loadStudent();
  }, [loadStudent]);

  const handleScoreStudent = async () => {
    if (!studentId) return;
    setScoring(true);
    setNotice(null);
    try {
      const res = await predictionService.runPredictions({
        student_ids: [studentId],
        include_synthetic: true,
        persist_interventions: true,
      });
      setNotice({
        variant: "success",
        text: `Generated prediction with model ${res.data.model_version}.`,
      });
      await loadStudent();
    } catch (err) {
      setNotice({
        variant: "error",
        text:
          err instanceof Error
            ? err.message
            : "Could not score student. Ensure a trained model exists in Model Analytics.",
      });
    } finally {
      setScoring(false);
    }
  };

  const handleToggleHistory = async (interventionId: number) => {
    if (expandedHistoryById[interventionId]) {
      setExpandedHistoryById((prev) => {
        const next = { ...prev };
        delete next[interventionId];
        return next;
      });
      return;
    }

    setLoadingHistoryId(interventionId);
    try {
      const res = await interventionService.getInterventionHistory(interventionId);
      setExpandedHistoryById((prev) => ({
        ...prev,
        [interventionId]: res.data.items,
      }));
    } catch (err) {
      setNotice({
        variant: "error",
        text: err instanceof Error ? err.message : "Unable to load intervention history.",
      });
    } finally {
      setLoadingHistoryId(null);
    }
  };

  const openCreateFromRecommendation = (
    type: string,
    priority: InterventionPriority,
    action: string
  ) => {
    setCreateDefaults({ type, priority, action });
    setCreateDialogOpen(true);
  };

  if (loading) {
    return <PageLoadingSkeleton rows={4} />;
  }

  if (error || !detail) {
    return (
      <div className="space-y-4">
        <Link href="/students">
          <Button variant="outline" size="sm">
            <ArrowLeft className="h-4 w-4" />
            Back to Students
          </Button>
        </Link>
        <ErrorState
          title="Student Profile Unavailable"
          message={error || `Student ${studentId} was not found.`}
          onRetry={() => void loadStudent()}
        />
      </div>
    );
  }

  const latestFeatures = detail.latest_features;
  const prediction = explanationData?.prediction ?? null;
  const riskIncreasing =
    prediction?.explanation.indicators.filter((i) => i.direction === "increases_risk") ?? [];
  const protectiveOrNeutral =
    prediction?.explanation.indicators.filter((i) => i.direction !== "increases_risk") ?? [];

  const allInterventions = studentInterventions?.items ?? [];
  const activeInterventions = allInterventions.filter(
    (item) => item.status !== "COMPLETED" && item.status !== "CANCELLED"
  );
  const pastInterventions = allInterventions.filter(
    (item) => item.status === "COMPLETED" || item.status === "CANCELLED"
  );

  const renderInterventionCard = (item: InterventionRecordOut) => {
    const historyRows = expandedHistoryById[item.id];
    return (
      <div
        key={item.id}
        className="rounded-lg border border-slate-200 bg-white p-4 shadow-2xs"
      >
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-navy-900">
                #{item.id} · {humanizeInterventionType(item.intervention_type)}
              </span>
              <Badge variant={item.priority}>{item.priority.toUpperCase()} PRIORITY</Badge>
              <InterventionStatusBadge status={item.status} />
            </div>
            <p className="text-xs text-slate-700">{item.recommended_action}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void handleToggleHistory(item.id)}
              disabled={loadingHistoryId === item.id}
            >
              <History className="h-3.5 w-3.5" />
              {loadingHistoryId === item.id
                ? "Loading..."
                : historyRows
                  ? "Hide History"
                  : `History (${item.history_count})`}
            </Button>
            <Link href={`/interventions?student_id=${encodeURIComponent(detail.student_id)}`}>
              <Button type="button" variant="outline" size="sm">
                Manage
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
          </div>
        </div>

        <div className="mt-3 grid gap-2 text-xs text-slate-600 sm:grid-cols-3">
          <div className="flex items-center gap-1.5">
            <UserCheck className="h-3.5 w-3.5 text-slate-400" />
            <span>
              <strong>Counsellor:</strong> {item.assigned_to || "Unassigned"}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <CalendarClock className="h-3.5 w-3.5 text-slate-400" />
            <span>
              <strong>Follow-Up:</strong>{" "}
              {item.follow_up_date ? formatDateTime(item.follow_up_date) : "Not scheduled"}
            </span>
          </div>
          <div>
            <strong>Updated:</strong> {formatDateTime(item.updated_at)}
          </div>
        </div>

        {item.notes && (
          <div className="mt-2.5 rounded-md border border-slate-100 bg-slate-50 px-3 py-2 text-xs text-slate-700">
            <strong>Counsellor Notes:</strong> {item.notes}
          </div>
        )}

        {historyRows && (
          <div className="mt-3 border-t border-slate-100 pt-3">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Audit History ({historyRows.length})
            </p>
            {historyRows.length === 0 ? (
              <p className="text-xs text-slate-500">No history events recorded.</p>
            ) : (
              <div className="space-y-1.5">
                {historyRows.map((h) => (
                  <div
                    key={h.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded border border-slate-100 bg-slate-50 px-2.5 py-1.5 text-xs"
                  >
                    <div>
                      <span className="font-semibold text-navy-900">{h.action}</span>
                      <span className="mx-1.5 text-slate-400">·</span>
                      <span className="text-slate-700">{h.summary}</span>
                      {h.actor_id && (
                        <span className="ml-1.5 text-slate-500">(by {h.actor_id})</span>
                      )}
                    </div>
                    <span className="text-[11px] text-slate-500">
                      {formatDateTime(h.created_at)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div className="space-y-1">
          <Link
            href="/students"
            className="inline-flex items-center gap-1 text-xs font-medium text-blue-700 hover:underline"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Student Risk Analysis
          </Link>
          <div className="flex flex-wrap items-center gap-2.5">
            <h2 className="text-2xl font-bold tracking-tight text-navy-900">
              Student {detail.student_id}
            </h2>
            <DemoDataBadge isDemo={detail.is_synthetic} />
            {prediction && <RiskBadge level={prediction.risk_level} />}
          </div>
          <p className="text-xs text-slate-500">
            Data Source: <code>{detail.data_source}</code> · Updated{" "}
            {formatDateTime(detail.updated_at)}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => openCreateFromRecommendation("advisor_outreach", "medium", "")}
          >
            <Plus className="h-4 w-4" />
            Create Intervention
          </Button>
          {isAdmin && (
            <Button size="sm" onClick={() => void handleScoreStudent()} disabled={scoring}>
              <Play className="h-4 w-4" />
              {scoring
                ? "Scoring Student..."
                : prediction
                  ? "Re-Score Student"
                  : "Generate Risk Score"}
            </Button>
          )}
        </div>
      </div>

      {detail.is_synthetic && (
        <SyntheticBanner
          title="DEMO DATA – SYNTHETIC STUDENT PROFILE"
          notice="This student profile belongs to the synthetic demonstration dataset for testing and training workflows."
        />
      )}

      {notice && (
        <Alert variant={notice.variant}>
          <p className="text-sm font-medium">{notice.text}</p>
        </Alert>
      )}

      {latestFeatures && (
        <Card>
          <CardHeader>
            <CardTitle>Latest Activity Snapshot (#{latestFeatures.snapshot_id})</CardTitle>
            <CardDescription>
              Recorded {formatDateTime(latestFeatures.recorded_at)} · Source:{" "}
              <code>{latestFeatures.data_source}</code> · Previous Failures:{" "}
              {latestFeatures.previous_failure_count}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg border border-slate-200 p-3">
              <p className="text-xs text-slate-500">Attendance Rate</p>
              <p className="mt-1 text-xl font-bold text-navy-900">
                {formatPercent(latestFeatures.attendance_rate)}
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 p-3">
              <p className="text-xs text-slate-500">Average Grade</p>
              <p className="mt-1 text-xl font-bold text-navy-900">
                {formatPercent(latestFeatures.average_grade)}
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 p-3">
              <p className="text-xs text-slate-500">Late / Missing Assignments</p>
              <p className="mt-1 text-xl font-bold text-navy-900">
                {latestFeatures.late_assignments} late · {latestFeatures.missing_assignments} missing
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 p-3">
              <p className="text-xs text-slate-500">LMS Logins (30d) & Change</p>
              <p className="mt-1 text-xl font-bold text-navy-900">
                {latestFeatures.lms_logins_30d}{" "}
                <span className="text-sm font-medium text-slate-600">
                  ({latestFeatures.engagement_change_pct > 0 ? "+" : ""}
                  {latestFeatures.engagement_change_pct.toFixed(1)}%)
                </span>
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Phase 4: Persistent Counsellor Interventions & Audit History */}
      <Card>
        <CardHeader className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div>
            <CardTitle className="flex items-center gap-2">
              <ClipboardCheck className="h-5 w-5 text-blue-600" />
              Counsellor Interventions & History ({allInterventions.length})
            </CardTitle>
            <CardDescription>
              Persistent case plans, assigned counsellors, follow-ups, and traceable updates via{" "}
              <code>GET /api/ps3/students/{detail.student_id}/interventions</code>.
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              onClick={() => openCreateFromRecommendation("advisor_outreach", "medium", "")}
            >
              <Plus className="h-4 w-4" />
              New Intervention
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert variant="info">
            <p className="text-xs">
              <strong>Access Note:</strong> Role-based authentication is pending future deployment;
              notes displayed here should exclude sensitive personal details.
            </p>
          </Alert>

          {allInterventions.length === 0 ? (
            <p className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-xs text-slate-600">
              No interventions recorded for {detail.student_id} yet. Review AI indicators below and
              click <strong>New Intervention</strong> if outreach is warranted.
            </p>
          ) : (
            <div className="space-y-5">
              <div>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Active Interventions ({activeInterventions.length})
                </h4>
                {activeInterventions.length === 0 ? (
                  <p className="text-xs text-slate-500">No active interventions open.</p>
                ) : (
                  <div className="space-y-3">{activeInterventions.map(renderInterventionCard)}</div>
                )}
              </div>

              {pastInterventions.length > 0 && (
                <div>
                  <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Previous / Completed Interventions ({pastInterventions.length})
                  </h4>
                  <div className="space-y-3">{pastInterventions.map(renderInterventionCard)}</div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {noPredictionYet || !prediction ? (
        <Alert variant="warning">
          <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <div>
              <p className="font-semibold">No Prediction Generated for {detail.student_id} Yet</p>
              <p className="mt-0.5 text-xs">
                Click &ldquo;Generate Risk Score&rdquo; above after training a model on Model
                Analytics to inspect explainability indicators and support recommendations.
              </p>
            </div>
          </div>
        </Alert>
      ) : (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <BrainCircuit className="h-5 w-5 text-blue-600" />
                    Risk Explainability & Key Indicators
                  </CardTitle>
                  <CardDescription>
                    Predicted dropout risk:{" "}
                    <strong className="text-navy-900">
                      {formatProbability(prediction.risk_probability)}
                    </strong>{" "}
                    · Model <code>{prediction.model_version}</code> · Scored{" "}
                    {formatDateTime(prediction.prediction_timestamp)}
                  </CardDescription>
                </div>
                <Badge variant={prediction.explanation.is_shap ? "primary" : "outline"}>
                  {prediction.explanation.method_label}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <Alert variant="warning" className="flex items-start gap-2.5">
                <Info className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" />
                <p className="text-xs text-amber-950">
                  <strong>Non-Causal Explanation:</strong>{" "}
                  {prediction.explanation.causation_disclaimer}
                </p>
              </Alert>

              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-2.5 rounded-lg border border-red-200 bg-red-50/40 p-4">
                  <h4 className="flex items-center gap-1.5 text-sm font-semibold text-red-900">
                    <ShieldAlert className="h-4 w-4 text-red-700" />
                    Risk-Increasing Indicators ({riskIncreasing.length})
                  </h4>
                  {riskIncreasing.length === 0 ? (
                    <p className="text-xs text-slate-600">
                      No risk-increasing threshold triggers identified in the latest snapshot.
                    </p>
                  ) : (
                    riskIncreasing.map((ind, idx) => (
                      <div
                        key={`${ind.feature}-${idx}`}
                        className="rounded-md border border-red-200 bg-white p-3 text-xs"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-semibold text-navy-900">
                            {humanizeFeatureName(ind.feature)}
                          </span>
                          <Badge variant="high">
                            Weight {(ind.importance_weight * 100).toFixed(1)}%
                          </Badge>
                        </div>
                        <p className="mt-1 text-slate-700">{ind.summary}</p>
                        {ind.value != null && (
                          <p className="mt-1 text-[11px] text-slate-500">
                            Observed value: {ind.value}
                          </p>
                        )}
                      </div>
                    ))
                  )}
                </div>

                <div className="space-y-2.5 rounded-lg border border-emerald-200 bg-emerald-50/40 p-4">
                  <h4 className="flex items-center gap-1.5 text-sm font-semibold text-emerald-900">
                    <CheckCircle2 className="h-4 w-4 text-emerald-700" />
                    Protective & Baseline Indicators ({protectiveOrNeutral.length})
                  </h4>
                  {protectiveOrNeutral.length === 0 ? (
                    <p className="text-xs text-slate-600">
                      No protective/neutral indicators reported separately.
                    </p>
                  ) : (
                    protectiveOrNeutral.map((ind, idx) => (
                      <div
                        key={`${ind.feature}-${idx}`}
                        className="rounded-md border border-emerald-200 bg-white p-3 text-xs"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-semibold text-navy-900">
                            {humanizeFeatureName(ind.feature)}
                          </span>
                          <Badge variant="low">
                            Weight {(ind.importance_weight * 100).toFixed(1)}%
                          </Badge>
                        </div>
                        <p className="mt-1 text-slate-700">{ind.summary}</p>
                        {ind.value != null && (
                          <p className="mt-1 text-[11px] text-slate-500">
                            Observed value: {ind.value}
                          </p>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-start justify-between gap-4">
              <div>
                <CardTitle>AI Advisory Recommendations</CardTitle>
                <CardDescription>
                  Rule-based outreach suggestions generated alongside prediction #
                  {prediction.prediction_id}. Review before creating or assigning a formal
                  intervention.
                </CardDescription>
              </div>
              <Link href="/interventions">
                <Button variant="outline" size="sm">
                  Interventions Queue
                  <ArrowUpRight className="h-4 w-4" />
                </Button>
              </Link>
            </CardHeader>
            <CardContent className="space-y-3">
              <Alert variant="info">
                <p className="text-xs">{explanationData?.human_review_notice}</p>
              </Alert>

              {prediction.recommended_interventions.length === 0 ? (
                <p className="text-sm text-slate-600">
                  No targeted interventions flagged for this snapshot.
                </p>
              ) : (
                <div className="grid gap-3 md:grid-cols-2">
                  {prediction.recommended_interventions.map((rec, idx) => (
                    <div
                      key={`${rec.intervention_type}-${idx}`}
                      className="flex flex-col justify-between rounded-lg border border-slate-200 bg-slate-50/70 p-4"
                    >
                      <div>
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-sm font-semibold text-navy-900">
                            {humanizeInterventionType(rec.intervention_type)}
                          </span>
                          <div className="flex items-center gap-1.5">
                            <Badge variant={rec.priority}>
                              {rec.priority.toUpperCase()} PRIORITY
                            </Badge>
                            {rec.requires_human_review && (
                              <Badge variant="outline">Human Review Required</Badge>
                            )}
                          </div>
                        </div>
                        <p className="mt-2 text-xs leading-relaxed text-slate-700">
                          {rec.recommended_action}
                        </p>
                        <p className="mt-2 text-[11px] text-slate-500">
                          <strong>Trigger:</strong> {rec.trigger_reason} · Status:{" "}
                          <code>{rec.status}</code>
                        </p>
                      </div>
                      <div className="mt-3 pt-2">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            openCreateFromRecommendation(
                              rec.intervention_type,
                              rec.priority,
                              rec.recommended_action
                            )
                          }
                        >
                          <Plus className="h-3.5 w-3.5" />
                          Create Intervention Case
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <History className="h-4 w-4 text-slate-600" />
              Activity Snapshot History ({detail.activity_history.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            {detail.activity_history.length === 0 ? (
              <p className="text-xs text-slate-500">No historical snapshots recorded.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Recorded</TableHead>
                    <TableHead>Attend.</TableHead>
                    <TableHead>Grade</TableHead>
                    <TableHead>Late/Miss</TableHead>
                    <TableHead>LMS 30d</TableHead>
                    <TableHead>Prev. Fail</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {detail.activity_history.map((snap) => (
                    <TableRow key={snap.snapshot_id}>
                      <TableCell className="text-xs">{formatDateTime(snap.recorded_at)}</TableCell>
                      <TableCell>{formatPercent(snap.attendance_rate)}</TableCell>
                      <TableCell>{formatPercent(snap.average_grade)}</TableCell>
                      <TableCell>
                        {snap.late_assignments}/{snap.missing_assignments}
                      </TableCell>
                      <TableCell>{snap.lms_logins_30d}</TableCell>
                      <TableCell>{snap.previous_failure_count}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Prediction History ({detail.predictions.length})</CardTitle>
          </CardHeader>
          <CardContent>
            {detail.predictions.length === 0 ? (
              <p className="text-xs text-slate-500">No prediction runs recorded for this student.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Predicted At</TableHead>
                    <TableHead>Model</TableHead>
                    <TableHead>Risk Prob.</TableHead>
                    <TableHead>Tier</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {detail.predictions.map((pred) => (
                    <TableRow key={pred.id}>
                      <TableCell className="text-xs">{formatDateTime(pred.predicted_at)}</TableCell>
                      <TableCell className="text-xs">
                        <code>{pred.model_version}</code>
                      </TableCell>
                      <TableCell className="font-semibold">
                        {formatProbability(pred.risk_score)}
                      </TableCell>
                      <TableCell>
                        <RiskBadge level={pred.risk_level} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      <CreateInterventionDialog
        open={createDialogOpen}
        initialStudentId={detail.student_id}
        initialPredictionId={prediction?.prediction_id ?? null}
        initialType={createDefaults.type}
        initialPriority={createDefaults.priority}
        initialAction={createDefaults.action}
        onClose={() => setCreateDialogOpen(false)}
        onCreated={(created) => {
          setCreateDialogOpen(false);
          setNotice({
            variant: "success",
            text: `Created intervention #${created.id} (${created.status}) for ${created.student_id}.`,
          });
          void loadStudent();
        }}
      />

      <ResponsibleAiFooterNotice />
    </div>
  );
}
