"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowDownUp, FilterX, Search } from "lucide-react";
import { studentService } from "@/services/studentService";
import { RiskLevel, StudentListItem } from "@/lib/types";
import { formatDateTime, formatPercent, formatProbability } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Alert } from "@/components/ui/feedback";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { RiskBadge } from "@/components/shared/RiskBadge";
import { DemoDataBadge, ResponsibleAiFooterNotice } from "@/components/shared/DemoDataBadge";
import { EmptyState, ErrorState, PageLoadingSkeleton } from "@/components/shared/StateFeedback";

type SortField =
  | "risk_score"
  | "predicted_at"
  | "attendance_rate"
  | "average_grade"
  | "missing_assignments"
  | "student_id";

const PAGE_SIZE = 20;

export default function StudentRiskAnalysisPage() {
  return (
    <RoleGuard
      allowedRoles={["administrator", "counsellor"]}
      sectionTitle="Student Risk Analysis"
    >
      <StudentRiskAnalysisContent />
    </RoleGuard>
  );
}

function StudentRiskAnalysisContent() {
  const [searchInput, setSearchInput] = React.useState("");
  const [debouncedSearch, setDebouncedSearch] = React.useState("");
  const [riskFilter, setRiskFilter] = React.useState<"all" | RiskLevel | "unscored">("all");
  const [sourceFilter, setSourceFilter] = React.useState<"all" | "real" | "synthetic">("all");
  const [minAttendance, setMinAttendance] = React.useState("");
  const [maxAttendance, setMaxAttendance] = React.useState("");
  const [predictedFrom, setPredictedFrom] = React.useState("");
  const [predictedTo, setPredictedTo] = React.useState("");
  const [sortBy, setSortBy] = React.useState<SortField>("risk_score");
  const [sortOrder, setSortOrder] = React.useState<"asc" | "desc">("desc");
  const [page, setPage] = React.useState(1);

  const [rows, setRows] = React.useState<StudentListItem[]>([]);
  const [totalRows, setTotalRows] = React.useState(0);
  const [totalPages, setTotalPages] = React.useState(1);
  const [hasNext, setHasNext] = React.useState(false);
  const [hasPrevious, setHasPrevious] = React.useState(false);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchInput.trim());
      setPage(1);
    }, 250);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const loadData = React.useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const isSyntheticBool =
        sourceFilter === "all" ? undefined : sourceFilter === "synthetic";
      const parsedMinAtt = minAttendance !== "" ? Number(minAttendance) : undefined;
      const parsedMaxAtt = maxAttendance !== "" ? Number(maxAttendance) : undefined;

      const res = await studentService.listStudents({
        page,
        page_size: PAGE_SIZE,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
        search: debouncedSearch || undefined,
        risk_level: riskFilter === "all" ? undefined : riskFilter,
        is_synthetic: isSyntheticBool,
        min_attendance:
          parsedMinAtt !== undefined && Number.isFinite(parsedMinAtt) ? parsedMinAtt : undefined,
        max_attendance:
          parsedMaxAtt !== undefined && Number.isFinite(parsedMaxAtt) ? parsedMaxAtt : undefined,
        predicted_from: predictedFrom ? `${predictedFrom}T00:00:00Z` : undefined,
        predicted_to: predictedTo ? `${predictedTo}T23:59:59Z` : undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
      });

      setRows(res.data.items);
      setTotalRows(res.data.total);
      setTotalPages(
        res.data.total_pages ?? Math.max(1, Math.ceil(res.data.total / PAGE_SIZE))
      );
      setHasNext(res.data.has_next ?? page * PAGE_SIZE < res.data.total);
      setHasPrevious(res.data.has_previous ?? page > 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load student risk table.");
    } finally {
      setLoading(false);
    }
  }, [
    page,
    debouncedSearch,
    riskFilter,
    sourceFilter,
    minAttendance,
    maxAttendance,
    predictedFrom,
    predictedTo,
    sortBy,
    sortOrder,
  ]);

  React.useEffect(() => {
    void loadData();
  }, [loadData]);

  const clearFilters = () => {
    setSearchInput("");
    setDebouncedSearch("");
    setRiskFilter("all");
    setSourceFilter("all");
    setMinAttendance("");
    setMaxAttendance("");
    setPredictedFrom("");
    setPredictedTo("");
    setSortBy("risk_score");
    setSortOrder("desc");
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-navy-900">Student Risk Analysis</h2>
          <p className="mt-1 text-sm text-slate-600">
            Server-side paginated search, combined filtering, and sorting across complete student
            cohorts.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={clearFilters}>
          <FilterX className="h-4 w-4" />
          Clear Filters
        </Button>
      </div>

      <Alert variant="info">
        <p className="text-xs">
          <strong>Advisory Framing:</strong> Risk percentages represent statistical likelihood
          patterns across observed activity snapshots, not guaranteed student outcomes. Click any
          student ID to inspect feature history, explainability indicators, and manage
          counsellor-reviewed interventions.
        </p>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle>Cohort Filters</CardTitle>
          <CardDescription>
            Server-side filtered via <code>GET /api/ps3/students</code> with combined search, risk
            tier, attendance bounds, and prediction date filters.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <div className="relative lg:col-span-2">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <Input
                placeholder="Search by Student ID (e.g., STU-1001)..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="pl-9"
                aria-label="Search by Student ID"
              />
            </div>

            <Select
              value={riskFilter}
              onChange={(e) => {
                setRiskFilter(e.target.value as "all" | RiskLevel | "unscored");
                setPage(1);
              }}
              aria-label="Filter by risk level"
            >
              <option value="all">All Risk Tiers</option>
              <option value="high">High Risk</option>
              <option value="medium">Medium Risk</option>
              <option value="low">Low Risk</option>
              <option value="unscored">Not Scored Yet</option>
            </Select>

            <Select
              value={sourceFilter}
              onChange={(e) => {
                setSourceFilter(e.target.value as "all" | "real" | "synthetic");
                setPage(1);
              }}
              aria-label="Filter by data source"
            >
              <option value="all">Real & Synthetic Data</option>
              <option value="real">Real Data Only</option>
              <option value="synthetic">Synthetic Demo Only</option>
            </Select>

            <div className="flex gap-2">
              <Select
                value={sortBy}
                onChange={(e) => {
                  setSortBy(e.target.value as SortField);
                  setPage(1);
                }}
                aria-label="Sort field"
              >
                <option value="risk_score">Sort: Risk Score</option>
                <option value="predicted_at">Sort: Prediction Date</option>
                <option value="attendance_rate">Sort: Attendance</option>
                <option value="average_grade">Sort: Average Grade</option>
                <option value="missing_assignments">Sort: Missing Tasks</option>
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
                title={`Order: ${sortOrder.toUpperCase()}`}
                aria-label="Toggle sort direction"
              >
                <ArrowDownUp className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <label className="mb-1 block text-[11px] font-medium text-slate-600">
                Min Attendance (%)
              </label>
              <Input
                type="number"
                min={0}
                max={100}
                placeholder="0"
                value={minAttendance}
                onChange={(e) => {
                  setMinAttendance(e.target.value);
                  setPage(1);
                }}
                aria-label="Minimum attendance rate"
              />
            </div>
            <div>
              <label className="mb-1 block text-[11px] font-medium text-slate-600">
                Max Attendance (%)
              </label>
              <Input
                type="number"
                min={0}
                max={100}
                placeholder="100"
                value={maxAttendance}
                onChange={(e) => {
                  setMaxAttendance(e.target.value);
                  setPage(1);
                }}
                aria-label="Maximum attendance rate"
              />
            </div>
            <div>
              <label className="mb-1 block text-[11px] font-medium text-slate-600">
                Predicted From
              </label>
              <Input
                type="date"
                value={predictedFrom}
                onChange={(e) => {
                  setPredictedFrom(e.target.value);
                  setPage(1);
                }}
                aria-label="Predicted from date"
              />
            </div>
            <div>
              <label className="mb-1 block text-[11px] font-medium text-slate-600">
                Predicted To
              </label>
              <Input
                type="date"
                value={predictedTo}
                onChange={(e) => {
                  setPredictedTo(e.target.value);
                  setPage(1);
                }}
                aria-label="Predicted to date"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <PageLoadingSkeleton rows={2} />
      ) : error ? (
        <ErrorState title="Error Loading Students" message={error} onRetry={() => void loadData()} />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No Matching Students Found"
          description="Try clearing filters, ingesting student records in Data Management, or running batch predictions."
          action={
            <Button variant="outline" onClick={clearFilters}>
              Reset Filters
            </Button>
          }
        />
      ) : (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-4">
            <div>
              <CardTitle>Student Risk Directory ({totalRows})</CardTitle>
              <CardDescription>
                Showing page {page} of {totalPages} ({rows.length} student(s) on this page)
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Student ID</TableHead>
                  <TableHead>Attendance</TableHead>
                  <TableHead>Avg Grade</TableHead>
                  <TableHead>Late / Missing</TableHead>
                  <TableHead>LMS Logins (30d)</TableHead>
                  <TableHead>Risk Prob.</TableHead>
                  <TableHead>Risk Tier</TableHead>
                  <TableHead>Predicted At</TableHead>
                  <TableHead>Cases</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead className="text-right">Profile</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.student_id}>
                    <TableCell className="font-semibold">
                      <Link
                        href={`/students/${encodeURIComponent(row.student_id)}`}
                        className="text-blue-700 hover:underline"
                      >
                        {row.student_id}
                      </Link>
                    </TableCell>
                    <TableCell>
                      {row.latest_features?.attendance_rate != null
                        ? formatPercent(row.latest_features.attendance_rate)
                        : "—"}
                    </TableCell>
                    <TableCell>
                      {row.latest_features?.average_grade != null
                        ? formatPercent(row.latest_features.average_grade)
                        : "—"}
                    </TableCell>
                    <TableCell>
                      {row.latest_features
                        ? `${row.latest_features.late_assignments} / ${row.latest_features.missing_assignments}`
                        : "—"}
                    </TableCell>
                    <TableCell>
                      {row.latest_features ? row.latest_features.lms_logins_30d : "—"}
                    </TableCell>
                    <TableCell className="font-semibold text-navy-900">
                      {row.latest_risk_probability != null
                        ? formatProbability(row.latest_risk_probability)
                        : "Not Scored"}
                    </TableCell>
                    <TableCell>
                      <RiskBadge level={row.latest_risk_level} />
                    </TableCell>
                    <TableCell className="text-xs text-slate-600">
                      {row.latest_prediction_timestamp
                        ? formatDateTime(row.latest_prediction_timestamp)
                        : "—"}
                    </TableCell>
                    <TableCell className="text-xs text-slate-700">{row.intervention_count}</TableCell>
                    <TableCell>
                      <DemoDataBadge isDemo={row.is_synthetic} />
                    </TableCell>
                    <TableCell className="text-right">
                      <Link href={`/students/${encodeURIComponent(row.student_id)}`}>
                        <Button variant="outline" size="sm">
                          Inspect
                        </Button>
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            <div className="flex items-center justify-between pt-2">
              <p className="text-xs text-slate-500">
                Page {page} of {totalPages} · {totalRows} total matching student(s)
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

      <ResponsibleAiFooterNotice />
    </div>
  );
}
