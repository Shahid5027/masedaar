"use client";

import * as React from "react";
import Link from "next/link";
import {
  Archive,
  ArrowDownUp,
  CalendarClock,
  CheckCircle2,
  ClipboardCheck,
  FilterX,
  History,
  Info,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
} from "lucide-react";
import { ApiClientError } from "@/lib/api";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { useAuth } from "@/components/auth/AuthProvider";
import { interventionService } from "@/services/interventionService";
import {
  InterventionDetailData,
  InterventionPriority,
  InterventionRecordOut,
  InterventionStatus,
  InterventionSummaryCounts,
} from "@/lib/types";
import { formatDateTime, formatProbability, humanizeInterventionType } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input, Select } from "@/components/ui/input";
import { Alert } from "@/components/ui/feedback";
import { ConfirmDialog } from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { MetricCard } from "@/components/shared/MetricCard";
import { RiskBadge } from "@/components/shared/RiskBadge";
import { DemoDataBadge, ResponsibleAiFooterNotice } from "@/components/shared/DemoDataBadge";
import { EmptyState, ErrorState, PageLoadingSkeleton } from "@/components/shared/StateFeedback";
import { InterventionStatusBadge } from "@/components/shared/InterventionStatusBadge";
import { CreateInterventionDialog } from "@/components/shared/CreateInterventionDialog";

const PAGE_SIZE = 20;

const EMPTY_COUNTS: InterventionSummaryCounts = {
  total: 0,
  pending: 0,
  assigned: 0,
  in_progress: 0,
  follow_up_required: 0,
  follow_ups_due: 0,
  completed: 0,
  cancelled: 0,
};

type SortField =
  | "created_at"
  | "follow_up_date"
  | "priority"
  | "student_id"
  | "status"
  | "updated_at";

export default function InterventionsWorkspacePage() {
  return (
    <RoleGuard
      allowedRoles={["administrator", "counsellor"]}
      sectionTitle="Interventions Workspace"
    >
      <InterventionsWorkspaceContent />
    </RoleGuard>
  );
}

function InterventionsWorkspaceContent() {
  const { user, hasRole } = useAuth();
  const isAdmin = hasRole("administrator");
  const [items, setItems] = React.useState<InterventionRecordOut[]>([]);
  const [counts, setCounts] = React.useState<InterventionSummaryCounts>(EMPTY_COUNTS);
  const [total, setTotal] = React.useState(0);
  const [totalPages, setTotalPages] = React.useState(1);
  const [hasNext, setHasNext] = React.useState(false);
  const [hasPrevious, setHasPrevious] = React.useState(false);

  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [banner, setBanner] = React.useState<{
    variant: "success" | "error";
    text: string;
  } | null>(null);

  // Filters & Pagination
  const [searchInput, setSearchInput] = React.useState("");
  const [debouncedSearch, setDebouncedSearch] = React.useState("");

  React.useEffect(() => {
    if (typeof window !== "undefined") {
      const qs = new URLSearchParams(window.location.search);
      const sid = qs.get("student_id");
      if (sid) {
        setSearchInput(sid);
        setDebouncedSearch(sid.trim());
      }
    }
  }, []);
  const [statusFilter, setStatusFilter] = React.useState<"all" | InterventionStatus>("all");
  const [priorityFilter, setPriorityFilter] = React.useState<"all" | InterventionPriority>("all");
  const [sourceFilter, setSourceFilter] = React.useState<"all" | "real" | "synthetic">("all");
  const [overdueOnly, setOverdueOnly] = React.useState(false);
  const [sortBy, setSortBy] = React.useState<SortField>("created_at");
  const [sortOrder, setSortOrder] = React.useState<"asc" | "desc">("desc");
  const [page, setPage] = React.useState(1);

  // Create Dialog
  const [createOpen, setCreateOpen] = React.useState(false);

  // Selected Intervention Detail & Editor
  const [selectedDetail, setSelectedDetail] = React.useState<InterventionDetailData | null>(null);
  const [loadingDetail, setLoadingDetail] = React.useState(false);
  const [editAssignee, setEditAssignee] = React.useState("");
  const [editStatus, setEditStatus] = React.useState<InterventionStatus>("PENDING");
  const [editPriority, setEditPriority] = React.useState<InterventionPriority>("medium");
  const [editFollowUp, setEditFollowUp] = React.useState("");
  const [editNotes, setEditNotes] = React.useState("");
  const [savingUpdate, setSavingUpdate] = React.useState(false);
  const [archiving, setArchiving] = React.useState(false);
  const [versionConflict, setVersionConflict] = React.useState(false);
  const [confirmTransition, setConfirmTransition] = React.useState<{
    targetStatus: InterventionStatus;
    title: string;
    description: string;
  } | null>(null);

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchInput.trim());
      setPage(1);
    }, 250);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const loadInterventions = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const isDemoBool = sourceFilter === "all" ? undefined : sourceFilter === "synthetic";
      const res = await interventionService.listInterventions({
        page,
        page_size: PAGE_SIZE,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
        search: debouncedSearch || undefined,
        status: statusFilter === "all" ? undefined : statusFilter,
        priority: priorityFilter === "all" ? undefined : priorityFilter,
        is_demo: isDemoBool,
        overdue_only: overdueOnly || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
      });

      setItems(res.data.items);
      setCounts(res.data.status_counts);
      setTotal(res.data.total);
      setTotalPages(res.data.total_pages);
      setHasNext(res.data.has_next);
      setHasPrevious(res.data.has_previous);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load interventions queue.");
    } finally {
      setLoading(false);
    }
  }, [page, debouncedSearch, statusFilter, priorityFilter, sourceFilter, overdueOnly, sortBy, sortOrder]);

  React.useEffect(() => {
    void loadInterventions();
  }, [loadInterventions]);

  const selectIntervention = async (interventionId: number, preserveBanner = false) => {
    setLoadingDetail(true);
    if (!preserveBanner) {
      setBanner(null);
    }
    try {
      const res = await interventionService.getInterventionDetail(interventionId);
      const d = res.data;
      setSelectedDetail(d);
      setVersionConflict(false);
      setEditAssignee(d.intervention.assigned_to ?? "");
      setEditStatus(d.intervention.status);
      setEditPriority(d.intervention.priority);
      setEditFollowUp(
        d.intervention.follow_up_date ? d.intervention.follow_up_date.slice(0, 10) : ""
      );
      setEditNotes(d.intervention.notes ?? "");
    } catch (err) {
      setBanner({
        variant: "error",
        text: err instanceof Error ? err.message : "Failed to fetch intervention details.",
      });
    } finally {
      setLoadingDetail(false);
    }
  };

  const applyInterventionUpdate = async (overrideStatus?: InterventionStatus) => {
    if (!selectedDetail) return;
    const statusToSave = overrideStatus ?? editStatus;
    setSavingUpdate(true);
    setBanner(null);
    setVersionConflict(false);
    try {
      const res = await interventionService.updateIntervention(selectedDetail.intervention.id, {
        version: selectedDetail.intervention.version,
        assigned_to: editAssignee.trim() || null,
        status: statusToSave,
        priority: editPriority,
        follow_up_date: editFollowUp ? new Date(`${editFollowUp}T12:00:00Z`).toISOString() : null,
        notes: editNotes.trim() || null,
      });
      setConfirmTransition(null);
      setBanner({
        variant: "success",
        text: `Saved intervention #${res.data.id} (status: ${res.data.status}, v${res.data.version}).`,
      });
      await Promise.all([loadInterventions(), selectIntervention(res.data.id, true)]);
    } catch (err) {
      setConfirmTransition(null);
      if (
        err instanceof ApiClientError &&
        err.statusCode === 409 &&
        err.errors.some((e) => e.code === "INTERVENTION_VERSION_CONFLICT")
      ) {
        setVersionConflict(true);
      }
      setBanner({
        variant: "error",
        text: err instanceof Error ? err.message : "Unable to save intervention update.",
      });
    } finally {
      setSavingUpdate(false);
    }
  };

  const handleArchiveIntervention = async () => {
    if (!selectedDetail || !isAdmin) return;
    setArchiving(true);
    setBanner(null);
    try {
      const res = await interventionService.archiveIntervention(selectedDetail.intervention.id, {
        version: selectedDetail.intervention.version,
        reason: "Archived from Interventions Workspace by administrator.",
      });
      setBanner({
        variant: "success",
        text: `Archived intervention #${res.data.id} while preserving immutable history.`,
      });
      setSelectedDetail(null);
      await loadInterventions();
    } catch (err) {
      setBanner({
        variant: "error",
        text: err instanceof Error ? err.message : "Unable to archive intervention.",
      });
    } finally {
      setArchiving(false);
    }
  };

  const handleSaveForm = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDetail) return;
    const prevStatus = selectedDetail.intervention.status;
    const isTerminalTransition = editStatus === "COMPLETED" || editStatus === "CANCELLED";
    const isReopening = prevStatus === "COMPLETED" || prevStatus === "CANCELLED";
    if (editStatus !== prevStatus && (isTerminalTransition || isReopening)) {
      setConfirmTransition({
        targetStatus: editStatus,
        title: `Confirm Status Change to ${editStatus}`,
        description: `Transition intervention #${selectedDetail.intervention.id} for student ${selectedDetail.intervention.student_id} from ${prevStatus} to ${editStatus}? This action is recorded in the audit timeline.`,
      });
      return;
    }
    void applyInterventionUpdate();
  };

  const clearFilters = () => {
    setSearchInput("");
    setDebouncedSearch("");
    setStatusFilter("all");
    setPriorityFilter("all");
    setSourceFilter("all");
    setOverdueOnly(false);
    setSortBy("created_at");
    setSortOrder("desc");
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-navy-900">
            Interventions Management Workspace
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Create, assign, schedule follow-ups, record counsellor notes, and audit intervention
            lifecycle history.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => void loadInterventions()}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" />
            Create Intervention
          </Button>
        </div>
      </div>

      <Alert variant="info" className="flex items-start gap-3">
        <Info className="mt-0.5 h-5 w-5 shrink-0 text-blue-700" />
        <p className="text-xs text-blue-950">
          <strong>Human-in-the-Loop & Verified Audit Notice:</strong> All risk predictions and AI
          suggestions remain advisory only and never automate punitive actions. Counsellor actions,
          version checks, and audit history entries are bound to your authenticated session identity
          and RBAC permissions.
        </p>
      </Alert>

      {banner && (
        <Alert variant={banner.variant}>
          <p className="text-sm font-medium">{banner.text}</p>
        </Alert>
      )}

      {/* Real Backend Status KPIs */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
        <MetricCard
          title="Total Cases"
          value={counts.total}
          icon={<ClipboardCheck className="h-5 w-5" />}
          accent="blue"
        />
        <MetricCard title="Pending" value={counts.pending} accent="default" />
        <MetricCard title="Assigned" value={counts.assigned} accent="blue" />
        <MetricCard title="In Progress" value={counts.in_progress} accent="violet" />
        <MetricCard
          title="Follow-Ups Due"
          value={counts.follow_ups_due}
          subtitle={`${counts.follow_up_required} flagged`}
          icon={<CalendarClock className="h-5 w-5 text-amber-700" />}
          accent="amber"
        />
        <MetricCard
          title="Completed"
          value={counts.completed}
          icon={<CheckCircle2 className="h-5 w-5 text-emerald-700" />}
          accent="green"
        />
      </div>

      {/* Filter & Search Toolbar */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4">
          <div>
            <CardTitle>Filter & Search Cases</CardTitle>
            <CardDescription>
              Server-side filtered via <code>GET /api/ps3/interventions</code>.
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={clearFilters}>
            <FilterX className="h-4 w-4" />
            Clear Filters
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <div className="relative lg:col-span-2">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <Input
                placeholder="Search student ID, type, action, or counsellor..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="pl-9"
                aria-label="Search interventions"
              />
            </div>

            <Select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value as "all" | InterventionStatus);
                setPage(1);
              }}
              aria-label="Filter by status"
            >
              <option value="all">All Statuses</option>
              <option value="PENDING">Pending Review</option>
              <option value="ASSIGNED">Assigned</option>
              <option value="IN_PROGRESS">In Progress</option>
              <option value="FOLLOW_UP_REQUIRED">Follow-Up Required</option>
              <option value="COMPLETED">Completed</option>
              <option value="CANCELLED">Cancelled</option>
            </Select>

            <Select
              value={priorityFilter}
              onChange={(e) => {
                setPriorityFilter(e.target.value as "all" | InterventionPriority);
                setPage(1);
              }}
              aria-label="Filter by priority"
            >
              <option value="all">All Priorities</option>
              <option value="high">High Priority</option>
              <option value="medium">Medium Priority</option>
              <option value="low">Low Priority</option>
            </Select>

            <div className="flex gap-2">
              <Select
                value={sortBy}
                onChange={(e) => {
                  setSortBy(e.target.value as SortField);
                  setPage(1);
                }}
                aria-label="Sort interventions by"
              >
                <option value="created_at">Sort: Created Date</option>
                <option value="follow_up_date">Sort: Follow-Up Date</option>
                <option value="priority">Sort: Priority</option>
                <option value="status">Sort: Status</option>
                <option value="student_id">Sort: Student ID</option>
              </Select>
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={() => {
                  setSortOrder((prev) => (prev === "desc" ? "asc" : "desc"));
                  setPage(1);
                }}
                aria-label="Toggle sort order"
              >
                <ArrowDownUp className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <Select
              value={sourceFilter}
              onChange={(e) => {
                setSourceFilter(e.target.value as "all" | "real" | "synthetic");
                setPage(1);
              }}
              className="w-52"
              aria-label="Filter by data source"
            >
              <option value="all">Real & Synthetic Data</option>
              <option value="real">Real Data Only</option>
              <option value="synthetic">Synthetic Demo Only</option>
            </Select>

            <label className="flex items-center gap-2 text-xs font-medium text-slate-700">
              <input
                type="checkbox"
                checked={overdueOnly}
                onChange={(e) => {
                  setOverdueOnly(e.target.checked);
                  setPage(1);
                }}
                className="h-4 w-4 rounded border-slate-300 text-blue-600"
              />
              Show Follow-Ups Due Only
            </label>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Interventions Table */}
        <div className={selectedDetail ? "lg:col-span-2" : "lg:col-span-3"}>
          {loading ? (
            <PageLoadingSkeleton rows={2} />
          ) : error ? (
            <ErrorState
              title="Unable to Load Interventions"
              message={error}
              onRetry={() => void loadInterventions()}
            />
          ) : items.length === 0 ? (
            <EmptyState
              title="No Interventions Match Current Filters"
              description="Create a new counsellor-reviewed intervention or run predictions to generate initial cases."
              action={
                <Button onClick={() => setCreateOpen(true)}>
                  <Plus className="h-4 w-4" />
                  Create Intervention
                </Button>
              }
            />
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Intervention Cases ({total})</CardTitle>
                <CardDescription>
                  Page {page} of {totalPages} · Select a case to assign a counsellor, schedule
                  follow-up, update status, or view history.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Student ID</TableHead>
                      <TableHead>Intervention</TableHead>
                      <TableHead>Priority</TableHead>
                      <TableHead>Counsellor</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead>Follow-Up</TableHead>
                      <TableHead className="text-right">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {items.map((item) => (
                      <TableRow
                        key={item.id}
                        className={
                          selectedDetail?.intervention.id === item.id ? "bg-blue-50/50" : undefined
                        }
                      >
                        <TableCell>
                          <div className="flex flex-col gap-1">
                            <Link
                              href={`/students/${encodeURIComponent(item.student_id)}`}
                              className="font-semibold text-blue-700 hover:underline"
                            >
                              {item.student_id}
                            </Link>
                            <DemoDataBadge isDemo={item.is_demo} />
                          </div>
                        </TableCell>
                        <TableCell>
                          <p className="text-xs font-semibold text-navy-900">
                            {humanizeInterventionType(item.intervention_type)}
                          </p>
                          <p className="mt-0.5 max-w-xs truncate text-xs text-slate-600">
                            {item.recommended_action}
                          </p>
                        </TableCell>
                        <TableCell>
                          <Badge variant={item.priority}>{item.priority.toUpperCase()}</Badge>
                        </TableCell>
                        <TableCell className="text-xs text-slate-700">
                          {item.assigned_to || <span className="text-slate-400">Unassigned</span>}
                        </TableCell>
                        <TableCell>
                          <InterventionStatusBadge status={item.status} />
                        </TableCell>
                        <TableCell className="text-xs text-slate-600">
                          {formatDateTime(item.created_at)}
                        </TableCell>
                        <TableCell className="text-xs text-slate-600">
                          {item.follow_up_date ? formatDateTime(item.follow_up_date) : "—"}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => void selectIntervention(item.id)}
                          >
                            Manage
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>

                <div className="flex items-center justify-between pt-2">
                  <p className="text-xs text-slate-500">
                    Page {page} of {totalPages} · {total} matching case(s)
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!hasPrevious}
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!hasNext}
                      onClick={() => setPage((p) => p + 1)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Selected Intervention Workflow Editor & Audit History Timeline */}
        {selectedDetail && (
          <Card className="h-fit border-blue-200">
            <CardHeader>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <CardTitle className="text-base">
                    Case #{selectedDetail.intervention.id} ·{" "}
                    <Link
                      href={`/students/${encodeURIComponent(selectedDetail.intervention.student_id)}`}
                      className="text-blue-700 hover:underline"
                    >
                      {selectedDetail.intervention.student_id}
                    </Link>
                  </CardTitle>
                  <CardDescription>
                    {humanizeInterventionType(selectedDetail.intervention.intervention_type)}
                  </CardDescription>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedDetail(null)}
                >
                  Close
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {loadingDetail ? (
                <p className="text-xs text-slate-500">Refreshing case details...</p>
              ) : (
                <>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs">
                    <p className="font-medium text-navy-900">
                      {selectedDetail.intervention.recommended_action}
                    </p>
                    {selectedDetail.related_prediction && (
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <span>Linked Prediction Risk:</span>
                        <RiskBadge level={selectedDetail.related_prediction.risk_level} />
                        <span className="font-semibold">
                          {formatProbability(selectedDetail.related_prediction.risk_score)}
                        </span>
                      </div>
                    )}
                  </div>

                  <form onSubmit={handleSaveForm} className="space-y-3">
                    <div>
                      <label
                        htmlFor="edit-assignee"
                        className="mb-1 block text-xs font-semibold text-slate-700"
                      >
                        Assigned Counsellor
                      </label>
                      <Input
                        id="edit-assignee"
                        value={editAssignee}
                        onChange={(e) => setEditAssignee(e.target.value)}
                        placeholder="e.g. counsellor.alex"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-2.5">
                      <div>
                        <label
                          htmlFor="edit-status"
                          className="mb-1 block text-xs font-semibold text-slate-700"
                        >
                          Workflow Status
                        </label>
                        <Select
                          id="edit-status"
                          value={editStatus}
                          onChange={(e) => setEditStatus(e.target.value as InterventionStatus)}
                        >
                          {selectedDetail.allowed_next_statuses.map((st) => (
                            <option key={st} value={st}>
                              {st}
                            </option>
                          ))}
                        </Select>
                      </div>

                      <div>
                        <label
                          htmlFor="edit-priority"
                          className="mb-1 block text-xs font-semibold text-slate-700"
                        >
                          Priority
                        </label>
                        <Select
                          id="edit-priority"
                          value={editPriority}
                          onChange={(e) => setEditPriority(e.target.value as InterventionPriority)}
                        >
                          <option value="high">High</option>
                          <option value="medium">Medium</option>
                          <option value="low">Low</option>
                        </Select>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2.5">
                      <div>
                        <label
                          htmlFor="edit-followup"
                          className="mb-1 block text-xs font-semibold text-slate-700"
                        >
                          Follow-Up Date
                        </label>
                        <Input
                          id="edit-followup"
                          type="date"
                          value={editFollowUp}
                          onChange={(e) => setEditFollowUp(e.target.value)}
                        />
                      </div>

                      <div>
                        <p className="mb-1 block text-xs font-semibold text-slate-700">
                          Verified Audit Actor & Version
                        </p>
                        <div className="flex h-9 items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 text-xs text-slate-700">
                          <span className="truncate font-medium">
                            {user ? `${user.username} (${user.role})` : "Verified session user"}
                          </span>
                          <span className="ml-2 shrink-0 rounded bg-slate-200 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-slate-800">
                            v{selectedDetail.intervention.version}
                          </span>
                        </div>
                      </div>
                    </div>

                    {versionConflict && (
                      <Alert variant="error">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-xs font-medium">
                            Version conflict (HTTP 409): another user modified this case since you
                            loaded it.
                          </p>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => void selectIntervention(selectedDetail.intervention.id)}
                          >
                            <RefreshCw className="h-3.5 w-3.5" />
                            Refresh Latest Version
                          </Button>
                        </div>
                      </Alert>
                    )}

                    <div>
                      <label
                        htmlFor="edit-notes"
                        className="mb-1 block text-xs font-semibold text-slate-700"
                      >
                        Counsellor Notes & Outcomes
                      </label>
                      <textarea
                        id="edit-notes"
                        rows={3}
                        value={editNotes}
                        onChange={(e) => setEditNotes(e.target.value)}
                        placeholder="Record student check-in summary or support outcomes..."
                        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600/20"
                      />
                    </div>

                    <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                      <div className="flex flex-wrap items-center gap-2">
                        {selectedDetail.intervention.status === "COMPLETED" && (
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() =>
                              setConfirmTransition({
                                targetStatus: "IN_PROGRESS",
                                title: "Reopen Completed Intervention",
                                description: `Reopen intervention #${selectedDetail.intervention.id} to IN_PROGRESS and resume active follow-up?`,
                              })
                            }
                          >
                            <RotateCcw className="h-3.5 w-3.5" />
                            Reopen
                          </Button>
                        )}
                        {isAdmin && !selectedDetail.intervention.is_archived && (
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            disabled={archiving}
                            onClick={() => void handleArchiveIntervention()}
                          >
                            <Archive className="h-3.5 w-3.5" />
                            {archiving ? "Archiving..." : "Archive Case"}
                          </Button>
                        )}
                      </div>
                      <Button type="submit" size="sm" disabled={savingUpdate} className="ml-auto">
                        {savingUpdate ? "Saving..." : "Save Changes"}
                      </Button>
                    </div>
                  </form>

                  <div className="border-t border-slate-200 pt-3">
                    <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-600">
                      <History className="h-3.5 w-3.5" />
                      Audit Timeline ({selectedDetail.history.length})
                    </h4>
                    <div className="max-h-64 space-y-2 overflow-y-auto pr-1">
                      {selectedDetail.history.map((entry) => (
                        <div
                          key={entry.id}
                          className="rounded-md border border-slate-200 bg-slate-50 p-2.5 text-xs"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-semibold text-navy-900">{entry.action}</span>
                            <span className="text-[10px] text-slate-500">
                              {formatDateTime(entry.created_at)}
                            </span>
                          </div>
                          <p className="mt-0.5 text-slate-700">{entry.summary}</p>
                          <p className="mt-0.5 text-[10px] text-slate-500">
                            Actor: {entry.actor_id || "Unauthenticated / System"}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      <CreateInterventionDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(created) => {
          setCreateOpen(false);
          setBanner({
            variant: "success",
            text: `Created intervention #${created.id} (${created.status}) for ${created.student_id}.`,
          });
          void loadInterventions();
          void selectIntervention(created.id, true);
        }}
      />

      <ConfirmDialog
        open={Boolean(confirmTransition)}
        title={confirmTransition?.title || "Confirm Action"}
        description={confirmTransition?.description || ""}
        confirmLabel="Confirm Update"
        loading={savingUpdate}
        onConfirm={() => {
          if (confirmTransition) {
            void applyInterventionUpdate(confirmTransition.targetStatus);
          }
        }}
        onClose={() => setConfirmTransition(null)}
      />

      <ResponsibleAiFooterNotice />
    </div>
  );
}
