"use client";

import * as React from "react";
import { BrainCircuit, FlaskConical, Play, RefreshCw } from "lucide-react";
import { modelService } from "@/services/modelService";
import { ApiClientError } from "@/lib/api";
import { ModelMetricsData } from "@/lib/types";
import { formatDateTime, formatPercent } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/input";
import { Alert } from "@/components/ui/feedback";
import { ConfirmDialog } from "@/components/ui/dialog";
import { useAuth } from "@/components/auth/AuthProvider";
import { MetricCard } from "@/components/shared/MetricCard";
import { ResponsibleAiFooterNotice } from "@/components/shared/DemoDataBadge";
import { EmptyState, ErrorState, PageLoadingSkeleton } from "@/components/shared/StateFeedback";
import {
  ConfusionMatrixCard,
  FeatureImportanceChart,
} from "@/components/charts/ModelAnalyticsCharts";

export default function ModelAnalyticsPage() {
  const { hasRole } = useAuth();
  const isAdmin = hasRole("administrator");
  const [metrics, setMetrics] = React.useState<ModelMetricsData | null>(null);
  const [notTrained, setNotTrained] = React.useState(false);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const [datasetMode, setDatasetMode] = React.useState<"auto" | "real_only" | "synthetic_only">(
    "auto"
  );
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const [training, setTraining] = React.useState(false);
  const [trainBanner, setTrainBanner] = React.useState<{
    variant: "success" | "error";
    text: string;
  } | null>(null);

  const loadMetrics = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    setNotTrained(false);
    try {
      const res = await modelService.getMetrics();
      setMetrics(res.data);
    } catch (err) {
      if (err instanceof ApiClientError && err.statusCode === 404) {
        setMetrics(null);
        setNotTrained(true);
      } else {
        setError(err instanceof Error ? err.message : "Failed to load model metrics.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void loadMetrics();
  }, [loadMetrics]);

  const handleTrainModel = async () => {
    setTraining(true);
    setTrainBanner(null);
    try {
      const res = await modelService.trainModel({
        dataset_mode: datasetMode,
        allow_synthetic_fallback: datasetMode !== "real_only",
      });
      setMetrics(res.data);
      setNotTrained(false);
      setConfirmOpen(false);
      setTrainBanner({
        variant: "success",
        text: `Trained model ${res.data.model_version} (${res.data.training_source}) on ${res.data.sample_count} labeled snapshot(s).`,
      });
    } catch (err) {
      setConfirmOpen(false);
      setTrainBanner({
        variant: "error",
        text:
          err instanceof Error
            ? err.message
            : "Model training failed. Ensure enough labeled records exist.",
      });
    } finally {
      setTraining(false);
    }
  };

  if (loading) {
    return <PageLoadingSkeleton rows={3} />;
  }

  if (error) {
    return (
      <ErrorState
        title="Model Analytics Unavailable"
        message={error}
        onRetry={() => void loadMetrics()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-navy-900">
            Model Evaluation & Training Analytics
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Inspect Random Forest holdout metrics, feature importances, confusion matrix, and
            train a new version via <code>POST /api/ps3/model/train</code>.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {isAdmin && (
            <Select
              value={datasetMode}
              onChange={(e) =>
                setDatasetMode(e.target.value as "auto" | "real_only" | "synthetic_only")
              }
              className="w-48"
              aria-label="Training dataset mode"
            >
              <option value="auto">Dataset: Auto (Real / Demo)</option>
              <option value="real_only">Dataset: Real Only</option>
              <option value="synthetic_only">Dataset: Synthetic Demo Only</option>
            </Select>
          )}
          <Button variant="outline" size="sm" onClick={() => void loadMetrics()}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
          {isAdmin && (
            <Button size="sm" onClick={() => setConfirmOpen(true)} disabled={training}>
              <Play className="h-4 w-4" />
              Train Model
            </Button>
          )}
        </div>
      </div>

      {trainBanner && (
        <Alert variant={trainBanner.variant}>
          <p className="text-sm font-medium">{trainBanner.text}</p>
        </Alert>
      )}

      {notTrained || !metrics ? (
        <EmptyState
          title="No Trained Model Artifact Found"
          description={
            isAdmin
              ? "Upload labeled student CSV data or seed the synthetic demonstration cohort in Data Management, then click Train Model above."
              : "No trained model artifact has been published by an administrator yet."
          }
          action={
            isAdmin ? (
              <Button onClick={() => setConfirmOpen(true)}>Train Model Now</Button>
            ) : undefined
          }
        />
      ) : (
        <>
          {metrics.is_demo_model && (
            <Alert variant="demo" className="flex items-start gap-3">
              <FlaskConical className="mt-0.5 h-5 w-5 shrink-0 text-violet-700" />
              <div>
                <p className="font-semibold text-violet-950">DEMO MODEL NOTICE</p>
                <p className="mt-0.5 text-xs text-violet-900">{metrics.evaluation_disclaimer}</p>
              </div>
            </Alert>
          )}

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <MetricCard
              title="Accuracy"
              value={formatPercent(metrics.evaluation.accuracy * 100)}
              subtitle={`${metrics.test_count} holdout test rows`}
              accent="blue"
            />
            <MetricCard
              title="Precision"
              value={formatPercent(metrics.evaluation.precision * 100)}
              subtitle="Positive predictive value"
              accent="green"
            />
            <MetricCard
              title="Recall"
              value={formatPercent(metrics.evaluation.recall * 100)}
              subtitle="Dropout sensitivity"
              accent="amber"
            />
            <MetricCard
              title="F1 Score"
              value={formatPercent(metrics.evaluation.f1_score * 100)}
              subtitle="Harmonic mean"
              accent="default"
            />
            <MetricCard
              title="ROC-AUC"
              value={
                metrics.evaluation.roc_auc != null
                  ? metrics.evaluation.roc_auc.toFixed(3)
                  : "N/A"
              }
              subtitle={metrics.evaluation.roc_auc_note || "Holdout area under ROC"}
              icon={<BrainCircuit className="h-5 w-5" />}
              accent={metrics.is_demo_model ? "violet" : "blue"}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <FeatureImportanceChart featureImportances={metrics.evaluation.feature_importances} />
            <ConfusionMatrixCard matrix={metrics.evaluation.confusion_matrix} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Class Distribution Breakdown</CardTitle>
                <CardDescription>
                  Observed target balance across {metrics.evaluation.class_distribution.total_samples}{" "}
                  labeled training sample(s).
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-lg border border-slate-200 p-3">
                  <p className="text-xs text-slate-500">Retained (0)</p>
                  <p className="mt-1 text-xl font-bold text-emerald-700">
                    {metrics.evaluation.class_distribution.retained_0}
                  </p>
                </div>
                <div className="rounded-lg border border-slate-200 p-3">
                  <p className="text-xs text-slate-500">Dropout (1)</p>
                  <p className="mt-1 text-xl font-bold text-red-700">
                    {metrics.evaluation.class_distribution.dropout_1}
                  </p>
                </div>
                <div className="rounded-lg border border-slate-200 p-3">
                  <p className="text-xs text-slate-500">Dropout Rate</p>
                  <p className="mt-1 text-xl font-bold text-navy-900">
                    {formatPercent(metrics.evaluation.class_distribution.dropout_rate_pct)}
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <CardTitle>Active Artifact Metadata</CardTitle>
                  <Badge variant={metrics.is_demo_model ? "demo" : "real"}>
                    {metrics.is_demo_model ? "DEMO MODEL" : "REAL MODEL"}
                  </Badge>
                </div>
                <CardDescription>
                  Model <code>{metrics.model_version}</code> · {metrics.algorithm}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-xs text-slate-700">
                <p>
                  <strong>Trained At:</strong> {formatDateTime(metrics.trained_at)}
                </p>
                <p>
                  <strong>Training Source:</strong> <code>{metrics.training_source}</code> (
                  {metrics.train_count} train / {metrics.test_count} test)
                </p>
                <p>
                  <strong>Threshold Profile:</strong> <code>{metrics.threshold_profile}</code> (
                  {Object.entries(metrics.thresholds)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join(", ")}
                  )
                </p>
                <p>
                  <strong>Features ({metrics.feature_columns.length}):</strong>{" "}
                  {metrics.feature_columns.join(", ")}
                </p>
              </CardContent>
            </Card>
          </div>
        </>
      )}

      <ConfirmDialog
        open={confirmOpen}
        title="Confirm Model Retraining"
        description={`Train a new Random Forest artifact using dataset_mode="${datasetMode}"? Existing stored predictions remain preserved alongside the new model version.`}
        confirmLabel="Start Training"
        loading={training}
        onConfirm={() => void handleTrainModel()}
        onClose={() => setConfirmOpen(false)}
      />

      <ResponsibleAiFooterNotice />
    </div>
  );
}

