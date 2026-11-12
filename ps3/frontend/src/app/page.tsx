"use client";

import * as React from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  BrainCircuit,
  Database,
  Play,
  RefreshCw,
  Users,
} from "lucide-react";
import { dataService } from "@/services/dataService";
import { predictionService } from "@/services/predictionService";
import { modelService } from "@/services/modelService";
import { ApiClientError } from "@/lib/api";
import { DataSummaryData, ModelMetricsData, PredictionRecordOut } from "@/lib/types";
import { formatDateTime, formatPercent, formatProbability } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/feedback";
import { Badge } from "@/components/ui/badge";
import { MetricCard } from "@/components/shared/MetricCard";
import { RiskBadge } from "@/components/shared/RiskBadge";
import {
  DemoDataBadge,
  ResponsibleAiFooterNotice,
  SyntheticBanner,
} from "@/components/shared/DemoDataBadge";
import { useAuth } from "@/components/auth/AuthProvider";
import { EmptyState, ErrorState, PageLoadingSkeleton } from "@/components/shared/StateFeedback";
import { RiskDistributionCharts } from "@/components/charts/RiskDistributionCharts";
import { FeatureStatsChart } from "@/components/charts/FeatureStatsChart";

export default function OverviewDashboardPage() {
  const { hasRole } = useAuth();
  const isAdmin = hasRole("administrator");
  const canViewStudents = hasRole("administrator", "counsellor");
  const [summary, setSummary] = React.useState<DataSummaryData | null>(null);
  const [attentionPredictions, setAttentionPredictions] = React.useState<PredictionRecordOut[]>(
    []
  );
  const [recentPredictions, setRecentPredictions] = React.useState<PredictionRecordOut[]>([]);
  const [metrics, setMetrics] = React.useState<ModelMetricsData | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [runningPredictions, setRunningPredictions] = React.useState(false);
  const [actionBanner, setActionBanner] = React.useState<{
    variant: "success" | "error";
    text: string;
  } | null>(null);

  const loadDashboard = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summaryRes, highPredRes, medPredRes, recentPredRes, metricsRes] = await Promise.all([
        dataService.getSummary(),
        predictionService.listPredictions({
          latest_only: true,
          risk_level: "high",
          limit: 8,
          sort_by: "risk_score",
          sort_order: "desc",
        }),
        predictionService.listPredictions({
          latest_only: true,
          risk_level: "medium",
          limit: 8,
          sort_by: "risk_score",
          sort_order: "desc",
        }),
        predictionService.listPredictions({
          latest_only: true,
          limit: 6,
          sort_by: "predicted_at",
          sort_order: "desc",
        }),
        modelService.getMetrics().catch((err: unknown) => {
          if (err instanceof ApiClientError && err.statusCode === 404) {
            return null;
          }
          throw err;
        }),
      ]);

      setSummary(summaryRes.data);
      const combinedAttention = [...highPredRes.data.items, ...medPredRes.data.items]
        .sort((a, b) => b.risk_probability - a.risk_probability)
        .slice(0, 8);
      setAttentionPredictions(combinedAttention);
      setRecentPredictions(recentPredRes.data.items);
      setMetrics(metricsRes ? metricsRes.data : null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load overview metrics.");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const handleRunPredictions = async () => {
    setRunningPredictions(true);
    setActionBanner(null);
    try {
      const res = await predictionService.runPredictions({
        include_synthetic: true,
        persist_interventions: true,
      });
      setActionBanner({
        variant: "success",
        text: `Generated ${res.data.total_predicted} prediction(s) with model ${res.data.model_version} (${res.data.interventions_persisted} intervention suggestion(s) saved for human review).`,
      });
      await loadDashboard();
    } catch (err) {
      setActionBanner({
        variant: "error",
        text:
          err instanceof Error
            ? err.message
            : "Unable to run predictions. Verify data and trained model exist.",
      });
    } finally {
      setRunningPredictions(false);
    }
  };

  if (loading) {
    return <PageLoadingSkeleton rows={4} />;
  }

  if (error || !summary) {
    return (
      <ErrorState
        title="Dashboard Connection Error"
        message={error || "Could not retrieve summary data from the backend API."}
        onRetry={() => void loadDashboard()}
      />
    );
  }

  const riskCounts = {
    low: summary.latest_risk_distribution?.low ?? 0,
    medium: summary.latest_risk_distribution?.medium ?? 0,
    high: summary.latest_risk_distribution?.high ?? 0,
  };

  const attentionStudents = attentionPredictions;
  const recentlyScored = recentPredictions;

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-navy-900">
            Institutional Early-Warning Overview
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Live cohort telemetry, risk distribution, and explainable dropout indicators from the
            PS3 analytics engine.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => void loadDashboard()}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
          {isAdmin && (
            <Button
              size="sm"
              onClick={() => void handleRunPredictions()}
              disabled={runningPredictions || !metrics || summary.total_students === 0}
              title={
                !metrics
                  ? "Train a model first before running predictions"
                  : summary.total_students === 0
                    ? "Ingest student data first"
                    : "Score all students with the active model"
              }
            >
              <Play className="h-4 w-4" />
              {runningPredictions ? "Scoring Students..." : "Run Predictions"}
            </Button>
          )}
        </div>
      </div>

      {summary.contains_synthetic_data && (
        <SyntheticBanner notice={summary.synthetic_data_notice} />
      )}

      {actionBanner && (
        <Alert variant={actionBanner.variant}>
          <p className="font-medium">{actionBanner.text}</p>
        </Alert>
      )}

      {summary.total_students === 0 && (
        <EmptyState
          title="No Student Activity Records Loaded Yet"
          description={
            isAdmin
              ? "Upload a validated student CSV file or seed the synthetic demonstration cohort on Data Management to explore analytics, train the model, and generate risk indicators."
              : "No cohort activity records have been ingested by an administrator yet."
          }
          action={
            isAdmin ? (
              <Link href="/data">
                <Button>
                  Go to Data Management
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
            ) : undefined
          }
        />
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard
          title="Total Students"
          value={summary.total_students}
          subtitle={`${summary.real_students} real · ${summary.synthetic_students} synthetic`}
          icon={<Users className="h-5 w-5" />}
          accent="blue"
        />
        <MetricCard
          title="High Risk"
          value={riskCounts.high}
          subtitle="Latest scored cohort"
          icon={<AlertTriangle className="h-5 w-5 text-red-700" />}
          accent="red"
        />
        <MetricCard
          title="Medium Risk"
          value={riskCounts.medium}
          subtitle="Advisor monitoring"
          accent="amber"
        />
        <MetricCard
          title="Low Risk"
          value={riskCounts.low}
          subtitle="Within normal range"
          accent="green"
        />
        <MetricCard
          title="Active Model"
          value={metrics ? metrics.model_version : "Not Trained"}
          subtitle={
            metrics ? `Trained ${formatDateTime(metrics.trained_at)}` : "Train on Model Analytics"
          }
          icon={<BrainCircuit className="h-5 w-5" />}
          accent={metrics?.is_demo_model ? "violet" : "default"}
          badge={
            metrics ? (
              metrics.is_demo_model ? (
                <Badge variant="demo">DEMO MODEL</Badge>
              ) : (
                <Badge variant="real">REAL MODEL</Badge>
              )
            ) : undefined
          }
        />
      </div>

      <RiskDistributionCharts counts={riskCounts} />

      <div className="grid gap-6 lg:grid-cols-2">
        <FeatureStatsChart featureStatistics={summary.feature_statistics} />

        <Card>
          <CardHeader className="flex flex-row items-start justify-between gap-4">
            <div>
              <CardTitle>Model Performance Snapshot</CardTitle>
              <CardDescription>
                Active Random Forest holdout evaluation from GET /api/ps3/model/metrics.
              </CardDescription>
            </div>
            <Link href="/model">
              <Button variant="outline" size="sm">
                Full Analytics
              </Button>
            </Link>
          </CardHeader>
          <CardContent className="space-y-4">
            {!metrics ? (
              <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
                <p className="text-sm font-medium text-navy-900">No trained model found yet.</p>
                <p className="mt-1 text-xs text-slate-600">
                  Train a model on labeled snapshots in Model Analytics before running batch
                  predictions.
                </p>
                <Link href="/model" className="mt-4 inline-block">
                  <Button size="sm">Open Model Analytics</Button>
                </Link>
              </div>
            ) : (
              <>
                {metrics.is_demo_model && (
                  <Alert variant="demo">
                    <p className="text-xs font-medium">{metrics.evaluation_disclaimer}</p>
                  </Alert>
                )}
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <p className="text-[11px] font-semibold uppercase text-slate-500">Accuracy</p>
                    <p className="mt-1 text-lg font-bold text-navy-900">
                      {formatPercent(metrics.evaluation.accuracy * 100)}
                    </p>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <p className="text-[11px] font-semibold uppercase text-slate-500">Precision</p>
                    <p className="mt-1 text-lg font-bold text-navy-900">
                      {formatPercent(metrics.evaluation.precision * 100)}
                    </p>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <p className="text-[11px] font-semibold uppercase text-slate-500">Recall</p>
                    <p className="mt-1 text-lg font-bold text-navy-900">
                      {formatPercent(metrics.evaluation.recall * 100)}
                    </p>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <p className="text-[11px] font-semibold uppercase text-slate-500">ROC-AUC</p>
                    <p className="mt-1 text-lg font-bold text-navy-900">
                      {metrics.evaluation.roc_auc != null
                        ? metrics.evaluation.roc_auc.toFixed(3)
                        : "N/A"}
                    </p>
                  </div>
                </div>
                <p className="text-xs text-slate-500">
                  Source: <span className="font-medium text-slate-700">{metrics.training_source}</span>{" "}
                  · Split: {metrics.train_count} train / {metrics.test_count} test · Total{" "}
                  {metrics.sample_count} labeled snapshot(s).
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-start justify-between gap-4">
            <div>
              <CardTitle>Students Requiring Attention</CardTitle>
              <CardDescription>
                Highest predicted dropout risk indicators requiring advisor review.
              </CardDescription>
            </div>
            {canViewStudents && (
              <Link href="/students">
                <Button variant="outline" size="sm">
                  View All
                </Button>
              </Link>
            )}
          </CardHeader>
          <CardContent>
            {attentionStudents.length === 0 ? (
              <p className="py-6 text-center text-sm text-slate-500">
                No medium- or high-risk predictions found in the latest batch.
              </p>
            ) : (
              <div className="divide-y divide-slate-100">
                {attentionStudents.map((item) => (
                  <div
                    key={item.prediction_id}
                    className="flex flex-wrap items-center justify-between gap-3 py-3"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        {canViewStudents ? (
                          <Link
                            href={`/students/${encodeURIComponent(item.student_id)}`}
                            className="font-semibold text-blue-700 hover:underline"
                          >
                            {item.student_id}
                          </Link>
                        ) : (
                          <span className="font-semibold text-navy-900">{item.student_id}</span>
                        )}
                        <DemoDataBadge isDemo={item.is_demo} />
                      </div>
                      <p className="mt-0.5 text-xs text-slate-500">
                        Top indicator:{" "}
                        {item.explanation.indicators[0]?.summary || "See explainability profile"}
                      </p>
                    </div>
                    <div className="flex items-center gap-2.5">
                      <span className="text-sm font-semibold text-navy-900">
                        {formatProbability(item.risk_probability)}
                      </span>
                      <RiskBadge level={item.risk_level} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recently Scored & Ingestion Status</CardTitle>
            <CardDescription>
              Latest prediction timestamps alongside repository totals from /data/summary.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <div className="rounded-lg border border-slate-200 p-3">
                <p className="text-[11px] font-semibold uppercase text-slate-500">
                  Ingestion Batches
                </p>
                <p className="mt-1 text-lg font-bold text-navy-900">
                  {summary.total_ingestion_batches}
                </p>
              </div>
              <div className="rounded-lg border border-slate-200 p-3">
                <p className="text-[11px] font-semibold uppercase text-slate-500">
                  Activity Snapshots
                </p>
                <p className="mt-1 text-lg font-bold text-navy-900">
                  {summary.total_activity_snapshots}
                </p>
              </div>
              <div className="rounded-lg border border-slate-200 p-3">
                <p className="text-[11px] font-semibold uppercase text-slate-500">
                  Labeled Targets
                </p>
                <p className="mt-1 text-lg font-bold text-navy-900">
                  {summary.training_targets_summary.total_labeled_snapshots}
                </p>
              </div>
            </div>

            <div>
              <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
                <Database className="h-3.5 w-3.5" />
                Latest Prediction Runs
              </h4>
              {recentlyScored.length === 0 ? (
                <p className="text-xs text-slate-500">No prediction runs recorded yet.</p>
              ) : (
                <div className="divide-y divide-slate-100 text-xs">
                  {recentlyScored.map((pred) => (
                    <div
                      key={pred.prediction_id}
                      className="flex items-center justify-between gap-2 py-2"
                    >
                      {canViewStudents ? (
                        <Link
                          href={`/students/${encodeURIComponent(pred.student_id)}`}
                          className="font-medium text-blue-700 hover:underline"
                        >
                          {pred.student_id}
                        </Link>
                      ) : (
                        <span className="font-medium text-navy-900">{pred.student_id}</span>
                      )}
                      <div className="flex items-center gap-2">
                        <span className="text-slate-500">
                          {formatDateTime(pred.prediction_timestamp)}
                        </span>
                        <RiskBadge level={pred.risk_level} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <p className="mt-3 text-[11px] text-slate-500">
                Note: Individual CSV batch history logs (filenames/uploaders per batch) are
                aggregated into batch counts because the Phase 1/2 API exposes summary counts via{" "}
                <code>GET /api/ps3/data/summary</code> without a per-batch log endpoint.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      <ResponsibleAiFooterNotice />
    </div>
  );
}

