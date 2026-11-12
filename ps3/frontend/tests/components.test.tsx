import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RiskBadge } from "@/components/shared/RiskBadge";
import { DemoDataBadge, SyntheticBanner } from "@/components/shared/DemoDataBadge";
import ModelAnalyticsPage from "@/app/model/page";
import InterventionsWorkspacePage from "@/app/interventions/page";
import { modelService } from "@/services/modelService";
import { interventionService } from "@/services/interventionService";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useParams: () => ({}),
}));

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PieChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  Pie: () => null,
  Cell: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Legend: () => null,
  CartesianGrid: () => null,
}));

describe("Responsible AI, synthetic badges, and page rendering", () => {
  it("renders explicit risk tier badges and synthetic data notice", () => {
    render(
      <div>
        <RiskBadge level="high" />
        <RiskBadge level="medium" />
        <RiskBadge level="low" />
        <DemoDataBadge isDemo={true} />
        <DemoDataBadge isDemo={false} />
        <SyntheticBanner />
      </div>
    );

    expect(screen.getByText("HIGH RISK")).toBeInTheDocument();
    expect(screen.getByText("MEDIUM RISK")).toBeInTheDocument();
    expect(screen.getByText("LOW RISK")).toBeInTheDocument();
    expect(screen.getAllByText("DEMO DATA – SYNTHETIC").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("REAL DATA")).toBeInTheDocument();
    expect(screen.getByText("DEMO DATA – SYNTHETIC RECORDS PRESENT")).toBeInTheDocument();
  });

  it("displays demo model disclaimer and ROC-AUC fallback note on ModelAnalyticsPage", async () => {
    vi.spyOn(modelService, "getMetrics").mockResolvedValue({
      message: "OK",
      errors: [],
      meta: {
        module: "ps3",
        api_version: "1.0.0",
        timestamp: "2026-11-12T00:00:00Z",
        contains_synthetic_data: true,
      },
      data: {
        model_version: "rf_v20261112_demo",
        algorithm: "RandomForestClassifier",
        trained_at: "2026-11-12T00:00:00Z",
        feature_columns: ["attendance_rate", "average_grade"],
        training_source: "synthetic_demo",
        is_demo_model: true,
        evaluation_disclaimer:
          "DEMO MODEL – Metrics are based on synthetic data and do not represent validated real-world prediction performance.",
        sample_count: 250,
        train_count: 200,
        test_count: 50,
        threshold_profile: "default",
        thresholds: { medium: 0.35, high: 0.65 },
        hyperparameters: {},
        evaluation: {
          accuracy: 0.88,
          precision: 0.84,
          recall: 0.81,
          f1_score: 0.825,
          roc_auc: null,
          roc_auc_note: "ROC-AUC unavailable for single-class test fold",
          confusion_matrix: { matrix: [[30, 3], [3, 14]], tn: 30, fp: 3, fn: 3, tp: 14 },
          class_distribution: {
            total_samples: 250,
            retained_0: 175,
            dropout_1: 75,
            dropout_rate_pct: 30,
            train_distribution: { "0": 140, "1": 60 },
            test_distribution: { "0": 35, "1": 15 },
          },
          feature_importances: { attendance_rate: 0.55, average_grade: 0.45 },
        },
      },
    });

    render(<ModelAnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText("DEMO MODEL NOTICE")).toBeInTheDocument();
    });
    expect(
      screen.getByText(
        "DEMO MODEL – Metrics are based on synthetic data and do not represent validated real-world prediction performance."
      )
    ).toBeInTheDocument();
    expect(screen.getByText("ROC-AUC unavailable for single-class test fold")).toBeInTheDocument();
  });

  it("renders real backend intervention counts and case rows on InterventionsWorkspacePage", async () => {
    vi.spyOn(interventionService, "listInterventions").mockResolvedValue({
      message: "OK",
      errors: [],
      meta: {
        module: "ps3",
        api_version: "1.0.0",
        timestamp: "2026-11-12T00:00:00Z",
        contains_synthetic_data: true,
      },
      data: {
        total: 1,
        limit: 20,
        offset: 0,
        page: 1,
        page_size: 20,
        total_pages: 1,
        has_next: false,
        has_previous: false,
        status_counts: {
          total: 1,
          pending: 1,
          assigned: 0,
          in_progress: 0,
          follow_up_required: 0,
          follow_ups_due: 0,
          completed: 0,
          cancelled: 0,
        },
        items: [
          {
            id: 5,
            student_id: "STU-9001",
            prediction_id: 12,
            intervention_type: "academic_advising",
            recommended_action: "Schedule one-on-one academic advisor check-in.",
            priority: "high",
            status: "PENDING",
            raw_status: "PENDING",
            assigned_to: null,
            follow_up_date: null,
            completed_at: null,
            notes: "Low attendance trigger",
            version: 1,
            is_archived: false,
            archived_at: null,
            is_demo: true,
            created_at: "2026-11-12T00:00:00Z",
            updated_at: "2026-11-12T00:00:00Z",
            latest_risk_level: "high",
            latest_risk_probability: 0.82,
            history_count: 1,
            human_review_notice: "Human advisor approval required.",
          },
        ],
      },
    });

    render(<InterventionsWorkspacePage />);

    await waitFor(() => {
      expect(screen.getByText("STU-9001")).toBeInTheDocument();
    });
    expect(screen.getByText("Human-in-the-Loop & Verified Audit Notice:")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Manage" })).toBeInTheDocument();
  });
});
