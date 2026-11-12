import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import InterventionsWorkspacePage from "@/app/interventions/page";
import StudentProfilePage from "@/app/students/[studentId]/page";
import { interventionService } from "@/services/interventionService";
import { studentService } from "@/services/studentService";
import { InterventionRecordOut } from "@/lib/types";

vi.mock("next/navigation", () => ({
  usePathname: () => "/interventions",
  useParams: () => ({ studentId: "STU-777" }),
}));

const META = {
  module: "ps3",
  api_version: "1.0.0",
  timestamp: "2026-11-12T00:00:00Z",
  contains_synthetic_data: false,
};

function makeRecord(overrides: Partial<InterventionRecordOut> = {}): InterventionRecordOut {
  return {
    id: 101,
    student_id: "STU-777",
    prediction_id: 12,
    intervention_type: "advisor_outreach",
    recommended_action: "Arrange check-in with student advisor.",
    priority: "high",
    status: "PENDING",
    raw_status: "PENDING",
    assigned_to: null,
    follow_up_date: null,
    completed_at: null,
    notes: null,
    version: 1,
    is_archived: false,
    archived_at: null,
    is_demo: false,
    created_at: "2026-11-12T00:00:00Z",
    updated_at: "2026-11-12T00:00:00Z",
    latest_risk_level: "high",
    latest_risk_probability: 0.84,
    history_count: 1,
    human_review_notice: "Human advisor review required.",
    ...overrides,
  };
}

describe("Phase 4 Interventions Workflow & Student Profile Integration", () => {
  it("supports creating, assigning, scheduling follow-up, notes, status updates, and error handling", async () => {
    const initialItem = makeRecord();
    const assignedItem = makeRecord({
      assigned_to: "counsellor.lee",
      status: "IN_PROGRESS",
      follow_up_date: "2026-11-20T12:00:00Z",
      notes: "Contacted via campus email",
      history_count: 3,
    });

    vi.spyOn(interventionService, "listInterventions").mockResolvedValue({
      message: "OK",
      errors: [],
      meta: META,
      data: {
        total: 540,
        limit: 20,
        offset: 0,
        page: 1,
        page_size: 20,
        total_pages: 27,
        has_next: true,
        has_previous: false,
        status_counts: {
          total: 540,
          pending: 300,
          assigned: 100,
          in_progress: 80,
          follow_up_required: 20,
          follow_ups_due: 5,
          completed: 40,
          cancelled: 0,
        },
        items: [initialItem],
      },
    });

    const getDetailSpy = vi.spyOn(interventionService, "getInterventionDetail").mockResolvedValue({
      message: "OK",
      errors: [],
      meta: META,
      data: {
        intervention: initialItem,
        student_is_synthetic: false,
        related_prediction: {
          id: 12,
          snapshot_id: 5,
          risk_score: 0.84,
          risk_level: "high",
          model_version: "rf-v1",
          is_synthetic_input: false,
          predicted_at: "2026-11-12T00:00:00Z",
        },
        history: [
          {
            id: 1,
            intervention_id: 101,
            student_id: "STU-777",
            action: "INTERVENTION_CREATED",
            actor_id: null,
            summary: "Intervention created.",
            created_at: "2026-11-12T00:00:00Z",
          },
        ],
        allowed_next_statuses: ["PENDING", "ASSIGNED", "IN_PROGRESS", "FOLLOW_UP_REQUIRED", "COMPLETED", "CANCELLED"],
        auth_notice: "Auth not yet enabled.",
      },
    });

    const createSpy = vi.spyOn(interventionService, "createIntervention").mockResolvedValue({
      message: "Created",
      errors: [],
      meta: META,
      data: makeRecord({ id: 202, student_id: "STU-888" }),
    });

    const updateSpy = vi.spyOn(interventionService, "updateIntervention").mockResolvedValue({
      message: "Updated",
      errors: [],
      meta: META,
      data: assignedItem,
    });

    render(<InterventionsWorkspacePage />);

    await waitFor(() => {
      expect(screen.getByText("STU-777")).toBeInTheDocument();
    });
    expect(screen.getAllByText(/Page 1 of 27/).length).toBeGreaterThanOrEqual(1);

    // Open Create Intervention dialog and submit
    fireEvent.click(screen.getByRole("button", { name: /Create Intervention/i }));
    fireEvent.change(screen.getByLabelText(/Student ID/i), { target: { value: "STU-888" } });
    fireEvent.change(screen.getByLabelText(/Action Description/i), {
      target: { value: "Hold weekly academic planning check-in" },
    });
    fireEvent.click(screen.getAllByRole("button", { name: /^Create Intervention$/i }).pop()!);

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          student_id: "STU-888",
          recommended_action: "Hold weekly academic planning check-in",
        })
      );
    });

    // Manage an existing case: assign counsellor, change status, follow-up date, notes
    fireEvent.click(screen.getByRole("button", { name: "Manage" }));
    await waitFor(() => {
      expect(getDetailSpy).toHaveBeenCalledWith(101);
    });

    fireEvent.change(screen.getByLabelText(/Assigned Counsellor/i), {
      target: { value: "counsellor.lee" },
    });
    fireEvent.change(screen.getByLabelText(/Workflow Status/i), {
      target: { value: "IN_PROGRESS" },
    });
    fireEvent.change(screen.getByLabelText(/Follow-Up Date/i), {
      target: { value: "2026-11-20" },
    });
    fireEvent.change(screen.getByLabelText(/Counsellor Notes & Outcomes/i), {
      target: { value: "Contacted via campus email" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Save Changes/i }));

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith(
        101,
        expect.objectContaining({
          assigned_to: "counsellor.lee",
          status: "IN_PROGRESS",
          notes: "Contacted via campus email",
        })
      );
    });
  });

  it("renders error state cleanly when loading interventions fails", async () => {
    vi.spyOn(interventionService, "listInterventions").mockRejectedValue(
      new Error("Backend unreachable")
    );

    render(<InterventionsWorkspacePage />);
    await waitFor(() => {
      expect(screen.getByText("Unable to Load Interventions")).toBeInTheDocument();
    });
    expect(screen.getByText("Backend unreachable")).toBeInTheDocument();
  });

  it("integrates student interventions and history timeline into StudentProfilePage", async () => {
    vi.spyOn(studentService, "getStudentDetail").mockResolvedValue({
      message: "OK",
      errors: [],
      meta: META,
      data: {
        student_id: "STU-777",
        is_synthetic: false,
        data_source: "csv_upload",
        created_at: "2026-11-12T00:00:00Z",
        updated_at: "2026-11-12T00:00:00Z",
        latest_features: {
          snapshot_id: 1,
          attendance_rate: 62,
          average_grade: 58,
          late_assignments: 3,
          missing_assignments: 4,
          lms_logins_30d: 8,
          engagement_change_pct: -30,
          previous_failure_count: 1,
          is_synthetic: false,
          data_source: "csv_upload",
          recorded_at: "2026-11-12T00:00:00Z",
        },
        activity_history: [],
        predictions: [],
        interventions: [],
        has_training_target_record: false,
      },
    });

    vi.spyOn(studentService, "getStudentExplanation").mockResolvedValue({
      message: "OK",
      errors: [],
      meta: META,
      data: {
        student_id: "STU-777",
        is_synthetic: false,
        data_source: "csv_upload",
        prediction: {
          prediction_id: 12,
          student_id: "STU-777",
          snapshot_id: 1,
          risk_probability: 0.84,
          risk_level: "high",
          model_version: "rf-v1",
          prediction_timestamp: "2026-11-12T00:00:00Z",
          is_demo: false,
          threshold_profile: "default",
          thresholds_used: { medium: 0.35, high: 0.7 },
          explanation: {
            method: "rule_based_feature_indicators",
            is_shap: false,
            method_label: "Rule-Based Weighted Feature Indicators",
            causation_disclaimer: "Statistical association only.",
            indicators: [],
          },
          recommended_interventions: [],
          human_review_notice: "Advisor review required.",
        },
        human_review_notice: "Advisor review required.",
      },
    });

    vi.spyOn(interventionService, "listStudentInterventions").mockResolvedValue({
      message: "OK",
      errors: [],
      meta: META,
      data: {
        student_id: "STU-777",
        is_synthetic: false,
        total: 1,
        human_review_notice: "Advisor review required.",
        status_counts: {
          total: 1,
          pending: 0,
          assigned: 1,
          in_progress: 0,
          follow_up_required: 0,
          follow_ups_due: 0,
          completed: 0,
          cancelled: 0,
        },
        items: [
          makeRecord({
            status: "ASSIGNED",
            assigned_to: "advisor.patel",
            notes: "Scheduled advisor check-in",
            history_count: 2,
          }),
        ],
      },
    });

    const historySpy = vi
      .spyOn(interventionService, "getInterventionHistory")
      .mockResolvedValue({
        message: "OK",
        errors: [],
        meta: META,
        data: {
          intervention_id: 101,
          student_id: "STU-777",
          total: 1,
          items: [
            {
              id: 50,
              intervention_id: 101,
              student_id: "STU-777",
              action: "COUNSELLOR_ASSIGNED",
              actor_id: "lead.advisor",
              summary: "Assigned to advisor.patel.",
              created_at: "2026-11-12T00:00:00Z",
            },
          ],
        },
      });

    render(<StudentProfilePage />);

    await waitFor(() => {
      expect(screen.getByText(/Counsellor Interventions & History \(1\)/i)).toBeInTheDocument();
    });
    expect(screen.getByText("advisor.patel")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /History \(2\)/i }));
    await waitFor(() => {
      expect(historySpy).toHaveBeenCalledWith(101);
    });
    expect(screen.getByText("COUNSELLOR_ASSIGNED")).toBeInTheDocument();
  });
});
