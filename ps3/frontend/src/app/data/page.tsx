"use client";

import * as React from "react";
import Link from "next/link";
import {
  CheckCircle2,
  Database,
  FileSpreadsheet,
  FlaskConical,
  Upload,
  XCircle,
} from "lucide-react";
import { dataService } from "@/services/dataService";
import { ApiClientError } from "@/lib/api";
import { DataSummaryData, UploadData, ValidationSummaryData } from "@/lib/types";
import { formatBytes, formatDateTime, formatPercent } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Alert, Progress } from "@/components/ui/feedback";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { RoleGuard } from "@/components/auth/RoleGuard";
import {
  DemoDataBadge,
  ResponsibleAiFooterNotice,
  SyntheticBanner,
} from "@/components/shared/DemoDataBadge";
import { ErrorState, PageLoadingSkeleton } from "@/components/shared/StateFeedback";

export default function DataManagementPage() {
  return (
    <RoleGuard allowedRoles={["administrator"]} sectionTitle="Data Management">
      <DataManagementContent />
    </RoleGuard>
  );
}

function DataManagementContent() {
  const [summary, setSummary] = React.useState<DataSummaryData | null>(null);
  const [loadingSummary, setLoadingSummary] = React.useState(true);
  const [summaryError, setSummaryError] = React.useState<string | null>(null);

  const [selectedFile, setSelectedFile] = React.useState<File | null>(null);
  const [dragOver, setDragOver] = React.useState(false);
  const [markSynthetic, setMarkSynthetic] = React.useState(false);
  const [uploadProgress, setUploadProgress] = React.useState<number>(0);

  const [validating, setValidating] = React.useState(false);
  const [uploading, setUploading] = React.useState(false);
  const [seeding, setSeeding] = React.useState(false);

  const [validationResult, setValidationResult] = React.useState<ValidationSummaryData | null>(null);
  const [uploadResult, setUploadResult] = React.useState<UploadData | null>(null);
  const [actionAlert, setActionAlert] = React.useState<{
    variant: "success" | "error" | "info";
    text: string;
  } | null>(null);

  const [seedRecords, setSeedRecords] = React.useState<string>("250");
  const [seedValue, setSeedValue] = React.useState<string>("42");

  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const loadSummary = React.useCallback(async () => {
    setLoadingSummary(true);
    setSummaryError(null);
    try {
      const res = await dataService.getSummary();
      setSummary(res.data);
    } catch (err) {
      setSummaryError(err instanceof Error ? err.message : "Failed to load data summary.");
    } finally {
      setLoadingSummary(false);
    }
  }, []);

  React.useEffect(() => {
    void loadSummary();
  }, [loadSummary]);

  const handleFileChosen = (file: File | null) => {
    setSelectedFile(file);
    setValidationResult(null);
    setUploadResult(null);
    setActionAlert(null);
    setUploadProgress(0);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragOver(false);
    const file = event.dataTransfer.files?.[0] ?? null;
    if (file) {
      handleFileChosen(file);
    }
  };

  const handleValidate = async () => {
    if (!selectedFile) return;
    setValidating(true);
    setActionAlert(null);
    setUploadResult(null);
    setUploadProgress(0);
    try {
      const res = await dataService.validateCsv(selectedFile, {
        isSynthetic: markSynthetic,
        onProgress: setUploadProgress,
      });
      setValidationResult(res.data);
      setActionAlert({
        variant: res.data.is_valid ? "success" : "error",
        text: res.data.is_valid
          ? `Dry-run validation passed for all ${res.data.valid_rows} row(s). Ready to ingest.`
          : `Dry-run validation found ${res.data.error_count} error(s) across ${res.data.invalid_rows} row(s).`,
      });
    } catch (err) {
      if (err instanceof ApiClientError && err.errors.length > 0) {
        setActionAlert({ variant: "error", text: err.message });
      } else {
        setActionAlert({
          variant: "error",
          text: err instanceof Error ? err.message : "Validation failed.",
        });
      }
    } finally {
      setValidating(false);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setActionAlert(null);
    setUploadProgress(0);
    try {
      const res = await dataService.uploadCsv(selectedFile, {
        isSynthetic: markSynthetic,
        onProgress: setUploadProgress,
      });
      setUploadResult(res.data);
      setActionAlert({
        variant: "success",
        text: `Batch #${res.data.batch_id} ingested ${res.data.ingested_rows} row(s) (${res.data.new_students} new, ${res.data.updated_students} updated).`,
      });
      await loadSummary();
    } catch (err) {
      if (err instanceof ApiClientError && err.errors.length > 0) {
        const firstErr = err.errors[0];
        setActionAlert({
          variant: "error",
          text: `${err.message} (${firstErr.code}: ${firstErr.message})`,
        });
      } else {
        setActionAlert({
          variant: "error",
          text: err instanceof Error ? err.message : "Upload failed.",
        });
      }
    } finally {
      setUploading(false);
    }
  };

  const handleSeedSynthetic = async (e: React.FormEvent) => {
    e.preventDefault();
    const num = Number(seedRecords);
    const seed = Number(seedValue);
    if (!Number.isFinite(num) || num < 200 || num > 5000) {
      setActionAlert({
        variant: "error",
        text: "Synthetic cohort size must be between 200 and 5000 records.",
      });
      return;
    }

    setSeeding(true);
    setActionAlert(null);
    try {
      const res = await dataService.seedSynthetic(num, Number.isFinite(seed) ? seed : 42);
      setUploadResult(res.data);
      setActionAlert({
        variant: "info",
        text: `Seeded ${res.data.ingested_rows} synthetic demonstration student records (Batch #${res.data.batch_id}).`,
      });
      await loadSummary();
    } catch (err) {
      setActionAlert({
        variant: "error",
        text: err instanceof Error ? err.message : "Synthetic seeding failed.",
      });
    } finally {
      setSeeding(false);
    }
  };

  const missingErrorCount =
    validationResult?.errors.filter((e) => e.code.startsWith("MISSING_")).length ?? 0;
  const duplicateErrorCount =
    validationResult?.errors.filter((e) => e.code.startsWith("DUPLICATE_")).length ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-navy-900">
            Data Ingestion & Validation
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Run non-mutating CSV dry-run validation, ingest institutional student snapshots, or seed
            clearly labeled synthetic demo data.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/model">
            <Button variant="outline" size="sm">
              Next: Model Analytics
            </Button>
          </Link>
        </div>
      </div>

      {summary?.contains_synthetic_data && (
        <SyntheticBanner notice={summary.synthetic_data_notice} />
      )}

      {actionAlert && (
        <Alert variant={actionAlert.variant}>
          <p className="text-sm font-medium">{actionAlert.text}</p>
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileSpreadsheet className="h-5 w-5 text-blue-600" />
              CSV Upload & Dry-Run Validator
            </CardTitle>
            <CardDescription>
              Required columns: <code>student_id</code>, <code>attendance_rate</code>,{" "}
              <code>average_grade</code>, <code>late_assignments</code>,{" "}
              <code>missing_assignments</code>, <code>lms_logins_30d</code>,{" "}
              <code>engagement_change_pct</code>, <code>previous_failure_count</code>. Optional
              target: <code>dropout_label</code>.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
                dragOver
                  ? "border-blue-600 bg-blue-50/70"
                  : "border-slate-300 bg-slate-50/70 hover:border-slate-400"
              }`}
            >
              <Upload className="h-8 w-8 text-slate-500" />
              <p className="mt-3 text-sm font-medium text-navy-900">
                Drag and drop a CSV file here, or click below to browse
              </p>
              <p className="mt-1 text-xs text-slate-500">
                UTF-8 CSV files validated via POST /api/ps3/data/validate and /upload
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                aria-label="Choose CSV file"
                onChange={(e) => handleFileChosen(e.target.files?.[0] ?? null)}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-4"
                onClick={() => fileInputRef.current?.click()}
              >
                Select CSV File
              </Button>

              {selectedFile && (
                <div className="mt-4 flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs">
                  <span className="font-semibold text-navy-900">{selectedFile.name}</span>
                  <span className="text-slate-500">({formatBytes(selectedFile.size)})</span>
                </div>
              )}
            </div>

            <label className="flex items-center gap-2.5 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={markSynthetic}
                onChange={(e) => setMarkSynthetic(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-blue-600"
              />
              <span>
                Mark uploaded records as <strong>synthetic / demonstration data</strong>{" "}
                (is_synthetic=true)
              </span>
            </label>

            {(validating || uploading || uploadProgress > 0) && (
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs text-slate-600">
                  <span>{uploading ? "Uploading & ingesting..." : validating ? "Validating..." : "Transfer complete"}</span>
                  <span>{uploadProgress}%</span>
                </div>
                <Progress value={uploadProgress} />
              </div>
            )}

            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="button"
                variant="secondary"
                disabled={!selectedFile || validating || uploading}
                onClick={() => void handleValidate()}
              >
                {validating ? "Validating..." : "Validate CSV (Dry Run)"}
              </Button>
              <Button
                type="button"
                disabled={!selectedFile || validating || uploading}
                onClick={() => void handleUpload()}
              >
                {uploading ? "Uploading..." : "Upload & Ingest CSV"}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="border-violet-200 bg-violet-50/30">
          <CardHeader>
            <div className="flex items-center justify-between gap-2">
              <CardTitle className="flex items-center gap-2 text-violet-950">
                <FlaskConical className="h-5 w-5 text-violet-700" />
                Seed Synthetic Demo Cohort
              </CardTitle>
              <Badge variant="demo">DEMO ONLY</Badge>
            </div>
            <CardDescription className="text-violet-900/80">
              Generates clearly labeled <code>DEMO DATA – SYNTHETIC</code> student records via{" "}
              <code>POST /api/ps3/data/seed-synthetic</code> for end-to-end testing when real
              institutional data is not loaded.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={(e) => void handleSeedSynthetic(e)} className="space-y-4">
              <div>
                <label
                  htmlFor="seed-records"
                  className="mb-1.5 block text-xs font-semibold text-violet-950"
                >
                  Number of Synthetic Students (200–5000)
                </label>
                <Input
                  id="seed-records"
                  type="number"
                  min={200}
                  max={5000}
                  value={seedRecords}
                  onChange={(e) => setSeedRecords(e.target.value)}
                />
              </div>
              <div>
                <label
                  htmlFor="seed-random"
                  className="mb-1.5 block text-xs font-semibold text-violet-950"
                >
                  Deterministic Random Seed
                </label>
                <Input
                  id="seed-random"
                  type="number"
                  value={seedValue}
                  onChange={(e) => setSeedValue(e.target.value)}
                />
              </div>
              <Button
                type="submit"
                variant="outline"
                className="w-full border-violet-300 bg-white text-violet-900 hover:bg-violet-100"
                disabled={seeding}
              >
                <FlaskConical className="h-4 w-4" />
                {seeding ? "Seeding Demo Data..." : "Seed Synthetic Demo Dataset"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      {validationResult && (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <CardTitle className="flex items-center gap-2">
                  {validationResult.is_valid ? (
                    <CheckCircle2 className="h-5 w-5 text-emerald-700" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-700" />
                  )}
                  Dry-Run Validation Results: {validationResult.filename}
                </CardTitle>
                <CardDescription>
                  No records were saved during this validation check.
                </CardDescription>
              </div>
              <DemoDataBadge isDemo={validationResult.is_synthetic_detected} />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <div className="rounded-lg border border-slate-200 p-3">
                <p className="text-[11px] font-semibold uppercase text-slate-500">Total Rows</p>
                <p className="mt-1 text-lg font-bold text-navy-900">
                  {validationResult.total_rows}
                </p>
              </div>
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
                <p className="text-[11px] font-semibold uppercase text-emerald-700">Valid Rows</p>
                <p className="mt-1 text-lg font-bold text-emerald-900">
                  {validationResult.valid_rows}
                </p>
              </div>
              <div className="rounded-lg border border-red-200 bg-red-50 p-3">
                <p className="text-[11px] font-semibold uppercase text-red-700">Invalid Rows</p>
                <p className="mt-1 text-lg font-bold text-red-900">
                  {validationResult.invalid_rows}
                </p>
              </div>
              <div className="rounded-lg border border-slate-200 p-3">
                <p className="text-[11px] font-semibold uppercase text-slate-500">Total Errors</p>
                <p className="mt-1 text-lg font-bold text-navy-900">
                  {validationResult.error_count}
                </p>
              </div>
              <div className="rounded-lg border border-slate-200 p-3">
                <p className="text-[11px] font-semibold uppercase text-slate-500">
                  Missing Errors
                </p>
                <p className="mt-1 text-lg font-bold text-navy-900">{missingErrorCount}</p>
              </div>
              <div className="rounded-lg border border-slate-200 p-3">
                <p className="text-[11px] font-semibold uppercase text-slate-500">
                  Duplicate Errors
                </p>
                <p className="mt-1 text-lg font-bold text-navy-900">{duplicateErrorCount}</p>
              </div>
            </div>

            {validationResult.missing_columns.length > 0 && (
              <Alert variant="error">
                Missing required columns:{" "}
                <strong>{validationResult.missing_columns.join(", ")}</strong>
              </Alert>
            )}

            {validationResult.errors_truncated && (
              <Alert variant="warning">
                Showing the first {validationResult.errors.length} validation errors; additional
                errors exist in the uploaded CSV.
              </Alert>
            )}

            {validationResult.errors.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>CSV Line</TableHead>
                    <TableHead>Student ID</TableHead>
                    <TableHead>Column</TableHead>
                    <TableHead>Code</TableHead>
                    <TableHead>Value</TableHead>
                    <TableHead>Message</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {validationResult.errors.map((err, index) => (
                    <TableRow key={`${err.code}-${err.csv_line ?? index}-${index}`}>
                      <TableCell>{err.csv_line ?? err.row ?? "—"}</TableCell>
                      <TableCell>{err.student_id ?? "—"}</TableCell>
                      <TableCell>
                        <code>{err.column ?? "—"}</code>
                      </TableCell>
                      <TableCell>
                        <Badge variant="high">{err.code}</Badge>
                      </TableCell>
                      <TableCell className="max-w-[120px] truncate">{err.value ?? "—"}</TableCell>
                      <TableCell className="text-xs text-slate-700">{err.message}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {uploadResult && (
        <Card className="border-emerald-200 bg-emerald-50/40">
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="text-emerald-950">
                Ingestion Confirmed — Batch #{uploadResult.batch_id}
              </CardTitle>
              <DemoDataBadge isDemo={uploadResult.is_synthetic} />
            </div>
            <CardDescription>
              Source: <code>{uploadResult.data_source}</code> · File:{" "}
              <code>{uploadResult.filename}</code> · Uploaded{" "}
              {formatDateTime(uploadResult.uploaded_at)}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <div className="rounded-lg border border-emerald-200 bg-white p-3">
              <p className="text-[11px] font-semibold uppercase text-slate-500">Ingested Rows</p>
              <p className="mt-1 text-lg font-bold text-navy-900">{uploadResult.ingested_rows}</p>
            </div>
            <div className="rounded-lg border border-emerald-200 bg-white p-3">
              <p className="text-[11px] font-semibold uppercase text-slate-500">New Students</p>
              <p className="mt-1 text-lg font-bold text-navy-900">{uploadResult.new_students}</p>
            </div>
            <div className="rounded-lg border border-emerald-200 bg-white p-3">
              <p className="text-[11px] font-semibold uppercase text-slate-500">Updated Students</p>
              <p className="mt-1 text-lg font-bold text-navy-900">{uploadResult.updated_students}</p>
            </div>
            <div className="rounded-lg border border-emerald-200 bg-white p-3">
              <p className="text-[11px] font-semibold uppercase text-slate-500">
                Snapshots Created
              </p>
              <p className="mt-1 text-lg font-bold text-navy-900">
                {uploadResult.snapshots_created}
              </p>
            </div>
            <div className="rounded-lg border border-emerald-200 bg-white p-3">
              <p className="text-[11px] font-semibold uppercase text-slate-500">
                Labeled Targets
              </p>
              <p className="mt-1 text-lg font-bold text-navy-900">
                {uploadResult.training_targets_stored}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {loadingSummary ? (
        <PageLoadingSkeleton rows={1} />
      ) : summaryError || !summary ? (
        <ErrorState
          title="Unable to Load Repository Summary"
          message={summaryError || "Summary unavailable."}
          onRetry={() => void loadSummary()}
        />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5 text-navy-800" />
              Current Dataset Summary
            </CardTitle>
            <CardDescription>
              Live totals returned by <code>GET /api/ps3/data/summary</code>.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg border border-slate-200 p-4">
              <p className="text-xs font-semibold uppercase text-slate-500">Students Breakdown</p>
              <p className="mt-1 text-2xl font-bold text-navy-900">{summary.total_students}</p>
              <p className="mt-1 text-xs text-slate-600">
                {summary.real_students} real · {summary.synthetic_students} synthetic
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 p-4">
              <p className="text-xs font-semibold uppercase text-slate-500">Snapshots & Batches</p>
              <p className="mt-1 text-2xl font-bold text-navy-900">
                {summary.total_activity_snapshots}
              </p>
              <p className="mt-1 text-xs text-slate-600">
                Across {summary.total_ingestion_batches} ingestion batch(es)
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 p-4">
              <p className="text-xs font-semibold uppercase text-slate-500">Labeled Outcomes</p>
              <p className="mt-1 text-2xl font-bold text-navy-900">
                {summary.training_targets_summary.total_labeled_snapshots}
              </p>
              <p className="mt-1 text-xs text-slate-600">
                Dropout rate: {formatPercent(summary.training_targets_summary.dropout_rate_pct)} (
                {summary.training_targets_summary.dropout_count} dropout /{" "}
                {summary.training_targets_summary.retained_count} retained)
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 p-4">
              <p className="text-xs font-semibold uppercase text-slate-500">
                Stored Predictions & Plans
              </p>
              <p className="mt-1 text-2xl font-bold text-navy-900">{summary.total_predictions}</p>
              <p className="mt-1 text-xs text-slate-600">
                {summary.total_interventions} advisory intervention row(s)
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      <ResponsibleAiFooterNotice />
    </div>
  );
}

