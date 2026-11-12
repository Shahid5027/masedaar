import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "@/components/auth/AuthProvider";
import { RoleGuard } from "@/components/auth/RoleGuard";
import { AppShell } from "@/components/layout/AppShell";
import LoginPage from "@/app/login/page";
import InterventionsWorkspacePage from "@/app/interventions/page";
import { NotificationsPanel } from "@/components/shared/NotificationsPanel";
import { ApiClientError, apiRequest, clearCsrfToken, getActiveCsrfToken } from "@/lib/api";
import { authService } from "@/services/authService";
import { dataService } from "@/services/dataService";
import { notificationService } from "@/services/notificationService";
import { interventionService } from "@/services/interventionService";
import { InterventionRecordOut, UserOut } from "@/lib/types";

const replaceMock = vi.fn();
let currentPathname = "/";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock, push: vi.fn() }),
  usePathname: () => currentPathname,
}));

const META = {
  module: "ps3",
  api_version: "1.0.0",
  timestamp: "2026-11-12T00:00:00Z",
  contains_synthetic_data: false,
};

function makeUser(overrides: Partial<UserOut> = {}): UserOut {
  return {
    id: 1,
    username: "admin.one",
    email: "admin@university.edu",
    full_name: "Admin One",
    role: "administrator",
    is_active: true,
    last_login_at: "2026-11-12T00:00:00Z",
    created_at: "2026-11-12T00:00:00Z",
    updated_at: "2026-11-12T00:00:00Z",
    ...overrides,
  };
}

function makeIntervention(overrides: Partial<InterventionRecordOut> = {}): InterventionRecordOut {
  return {
    id: 101,
    student_id: "STU-777",
    prediction_id: 12,
    intervention_type: "advisor_outreach",
    recommended_action: "Schedule check-in",
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
    latest_risk_probability: 0.88,
    history_count: 1,
    human_review_notice: "Human advisor review required.",
    ...overrides,
  };
}

describe("Phase 5 Auth, RBAC, Notifications, and Concurrency UI", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    replaceMock.mockReset();
    clearCsrfToken();
    currentPathname = "/";
  });

  it("handles login, CSRF storage, and logout cleanly", async () => {
    currentPathname = "/login";
    vi.spyOn(authService, "me").mockRejectedValue(
      new ApiClientError(401, "Not authenticated", [{ code: "UNAUTHORIZED", message: "No session" }])
    );
    const loginSpy = vi.spyOn(authService, "login").mockResolvedValue({
      message: "Signed in",
      errors: [],
      meta: META,
      data: {
        user: makeUser({ username: "counsellor.maya", role: "counsellor", full_name: "Maya Patel" }),
        csrf_token: "csrf-test-token-123",
        expires_at: "2026-11-12T08:00:00Z",
        session_ttl_minutes: 480,
      },
    });
    const logoutSpy = vi.spyOn(authService, "logout").mockResolvedValue({
      message: "Signed out",
      errors: [],
      meta: META,
      data: { logged_out: true },
    });

    vi.spyOn(dataService, "getHealth").mockResolvedValue({
      message: "OK",
      errors: [],
      meta: META,
      data: {
        service: "EDUCORE AI PS3",
        environment: "test",
        database_connected: true,
        database_dialect: "sqlite",
      },
    });
    vi.spyOn(dataService, "getSummary").mockResolvedValue({
      message: "OK",
      errors: [],
      meta: META,
      data: {
        total_students: 10,
        real_students: 10,
        synthetic_students: 0,
        total_ingestion_batches: 1,
        total_activity_snapshots: 10,
        total_predictions: 10,
        total_interventions: 2,
        contains_synthetic_data: false,
        latest_risk_distribution: { low: 5, medium: 3, high: 2 },
        feature_statistics: {},
        training_targets_summary: {
          total_labeled_snapshots: 10,
          dropout_count: 2,
          retained_count: 8,
          dropout_rate_pct: 20,
          note: "Sample training targets.",
        },
      },
    });
    vi.spyOn(notificationService, "listNotifications").mockResolvedValue({
      message: "OK",
      errors: [],
      meta: META,
      data: {
        items: [],
        total: 0,
        unread_count: 0,
        email_transport: "disabled",
        email_verification_notice: "Email disabled.",
      },
    });

    const { rerender } = render(
      <AuthProvider>
        <AppShell>
          <LoginPage />
        </AppShell>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Username or Email/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/Username or Email/i), {
      target: { value: "counsellor.maya" },
    });
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: "SecurePass1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Sign In/i }));

    await waitFor(() => {
      expect(loginSpy).toHaveBeenCalledWith("counsellor.maya", "SecurePass1!");
      expect(getActiveCsrfToken()).toBe("csrf-test-token-123");
      expect(replaceMock).toHaveBeenCalledWith("/");
    });

    currentPathname = "/";
    rerender(
      <AuthProvider>
        <AppShell>
          <div>Dashboard Child</div>
        </AppShell>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Maya Patel")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Sign Out/i }));
    await waitFor(() => {
      expect(logoutSpy).toHaveBeenCalled();
      expect(getActiveCsrfToken()).toBeNull();
      expect(replaceMock).toHaveBeenCalledWith("/login");
    });
  });

  it("redirects to /login when an authenticated API request returns 401 expired session", async () => {
    currentPathname = "/";
    vi.spyOn(authService, "me").mockResolvedValue({
      message: "OK",
      errors: [],
      meta: META,
      data: {
        user: makeUser(),
        csrf_token: "csrf-valid",
        expires_at: "2026-11-12T08:00:00Z",
      },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({
          status: "error",
          message: "Session expired.",
          data: null,
          errors: [{ code: "SESSION_EXPIRED", message: "Session expired." }],
          meta: META,
        }),
      })
    );

    render(
      <AuthProvider>
        <div>Authenticated Content</div>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(getActiveCsrfToken()).toBe("csrf-valid");
    });

    await expect(apiRequest("/predictions")).rejects.toThrow(/Session expired/i);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/login?reason=expired");
      expect(getActiveCsrfToken()).toBeNull();
    });
  });

  it("enforces viewer role navigation restrictions and 403 RoleGuard screen", async () => {
    currentPathname = "/";
    vi.spyOn(authService, "me").mockResolvedValue({
      message: "OK",
      errors: [],
      meta: META,
      data: {
        user: makeUser({ username: "viewer.sam", role: "viewer", full_name: "Sam Viewer" }),
        csrf_token: "csrf-viewer",
        expires_at: "2026-11-12T08:00:00Z",
      },
    });
    vi.spyOn(dataService, "getHealth").mockResolvedValue({
      message: "OK",
      errors: [],
      meta: META,
      data: {
        service: "EDUCORE AI PS3",
        environment: "test",
        database_connected: true,
        database_dialect: "sqlite",
      },
    });
    vi.spyOn(dataService, "getSummary").mockResolvedValue({
      message: "OK",
      errors: [],
      meta: META,
      data: {
        total_students: 5,
        real_students: 5,
        synthetic_students: 0,
        total_ingestion_batches: 1,
        total_activity_snapshots: 5,
        total_predictions: 5,
        total_interventions: 0,
        contains_synthetic_data: false,
        latest_risk_distribution: { low: 5, medium: 0, high: 0 },
        feature_statistics: {},
        training_targets_summary: {
          total_labeled_snapshots: 5,
          dropout_count: 0,
          retained_count: 5,
          dropout_rate_pct: 0,
          note: "Sample training targets.",
        },
      },
    });

    render(
      <AuthProvider>
        <AppShell>
          <RoleGuard allowedRoles={["administrator"]} sectionTitle="Data Management">
            <div>Restricted Admin Content</div>
          </RoleGuard>
        </AppShell>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/403 — Access Restricted: Data Management/i)).toBeInTheDocument();
    });

    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Model Analytics")).toBeInTheDocument();
    expect(screen.queryByText("Data Management")).not.toBeInTheDocument();
    expect(screen.queryByText("Interventions")).not.toBeInTheDocument();
    expect(screen.queryByText("Administration")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Notifications")).not.toBeInTheDocument();
  });

  it("renders NotificationsPanel unread count, scan-followups, and mark-read actions", async () => {
    vi.spyOn(authService, "me").mockResolvedValue({
      message: "OK",
      errors: [],
      meta: META,
      data: {
        user: makeUser({ username: "counsellor.maya", role: "counsellor", full_name: "Maya" }),
        csrf_token: "csrf-c",
        expires_at: "2026-11-12T08:00:00Z",
      },
    });
    vi.spyOn(notificationService, "listNotifications").mockResolvedValue({
      message: "OK",
      errors: [],
      meta: META,
      data: {
        items: [
          {
            id: 50,
            recipient_user_id: 2,
            recipient_username: "counsellor.maya",
            intervention_id: 101,
            student_id: "STU-777",
            event_type: "INTERVENTION_ASSIGNED",
            channel: "in_app+email",
            title: "Intervention #101 assigned",
            message: "Case #101 for STU-777 assigned.",
            email_status: "memory_test",
            email_attempts: 1,
            last_error: null,
            is_read: false,
            read_at: null,
            created_at: "2026-11-12T00:00:00Z",
            sent_at: "2026-11-12T00:00:00Z",
          },
        ],
        total: 1,
        unread_count: 1,
        email_transport: "memory_test",
        email_verification_notice: "Tested via controlled memory_test transport.",
      },
    });
    const scanSpy = vi.spyOn(notificationService, "scanFollowups").mockResolvedValue({
      message: "Scanned",
      errors: [],
      meta: META,
      data: {
        created_count: 0,
        approaching_count: 0,
        overdue_count: 0,
        email_transport: "memory_test",
      },
    });
    const readSpy = vi.spyOn(notificationService, "markRead").mockResolvedValue({
      message: "Read",
      errors: [],
      meta: META,
      data: {
        id: 50,
        recipient_user_id: 2,
        recipient_username: "counsellor.maya",
        intervention_id: 101,
        student_id: "STU-777",
        event_type: "INTERVENTION_ASSIGNED",
        channel: "in_app+email",
        title: "Intervention #101 assigned",
        message: "Case #101 for STU-777 assigned.",
        email_status: "memory_test",
        email_attempts: 1,
        last_error: null,
        is_read: true,
        read_at: "2026-11-12T01:00:00Z",
        created_at: "2026-11-12T00:00:00Z",
        sent_at: "2026-11-12T00:00:00Z",
      },
    });

    render(
      <AuthProvider>
        <NotificationsPanel />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("unread-notifications-badge")).toHaveTextContent("1");
    });

    fireEvent.click(screen.getByRole("button", { name: /Notifications/i }));
    expect(screen.getByText("Intervention #101 assigned")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Scan Due/i }));
    await waitFor(() => {
      expect(scanSpy).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByRole("button", { name: /^Read$/i }));
    await waitFor(() => {
      expect(readSpy).toHaveBeenCalledWith(50);
    });
  });

  it("handles 409 optimistic concurrency conflict and refreshes latest intervention version", async () => {
    const recordV1 = makeIntervention({ version: 1 });
    const recordV2 = makeIntervention({ version: 2, notes: "Updated externally" });

    vi.spyOn(interventionService, "listInterventions").mockResolvedValue({
      message: "OK",
      errors: [],
      meta: META,
      data: {
        items: [recordV1],
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
      },
    });

    const getDetailSpy = vi
      .spyOn(interventionService, "getInterventionDetail")
      .mockResolvedValueOnce({
        message: "OK",
        errors: [],
        meta: META,
        data: {
          intervention: recordV1,
          student_is_synthetic: false,
          related_prediction: null,
          history: [],
          allowed_next_statuses: ["PENDING", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "CANCELLED"],
          auth_notice: "Verified",
        },
      })
      .mockResolvedValueOnce({
        message: "OK",
        errors: [],
        meta: META,
        data: {
          intervention: recordV2,
          student_is_synthetic: false,
          related_prediction: null,
          history: [],
          allowed_next_statuses: ["PENDING", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "CANCELLED"],
          auth_notice: "Verified",
        },
      });

    vi.spyOn(interventionService, "updateIntervention").mockRejectedValue(
      new ApiClientError(409, "Version conflict", [
        { code: "INTERVENTION_VERSION_CONFLICT", message: "Stale version 1" },
      ])
    );

    render(<InterventionsWorkspacePage />);

    await waitFor(() => {
      expect(screen.getByText("STU-777")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Manage" }));
    await waitFor(() => {
      expect(screen.getByText("v1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Save Changes/i }));
    await waitFor(() => {
      expect(screen.getByText(/Version conflict \(HTTP 409\)/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Refresh Latest Version/i }));
    await waitFor(() => {
      expect(getDetailSpy).toHaveBeenCalledTimes(2);
      expect(screen.getByText("v2")).toBeInTheDocument();
    });
  });
});
