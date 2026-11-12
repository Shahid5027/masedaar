import { describe, expect, it, vi } from "vitest";
import { dataService } from "@/services/dataService";
import { studentService } from "@/services/studentService";
import { modelService } from "@/services/modelService";
import { predictionService } from "@/services/predictionService";
import { interventionService } from "@/services/interventionService";

function mockSuccessFetch(data: unknown) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({
      status: "success",
      message: "OK",
      data,
      errors: [],
      meta: {
        module: "ps3",
        api_version: "1.0.0",
        timestamp: "2026-11-12T00:00:00Z",
        contains_synthetic_data: false,
      },
    }),
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("PS3 API service layer", () => {
  it("calls dataService endpoints with expected routes and payloads", async () => {
    const fetchMock = mockSuccessFetch({ total_students: 10 });
    await dataService.getSummary();
    expect(fetchMock.mock.calls[0][0]).toContain("/api/ps3/data/summary");

    await dataService.seedSynthetic(120, 99);
    const seedUrl = fetchMock.mock.calls[1][0] as string;
    const seedInit = fetchMock.mock.calls[1][1] as RequestInit;
    expect(seedUrl).toContain("/api/ps3/data/seed-synthetic");
    expect(seedUrl).toContain("num_records=120");
    expect(seedUrl).toContain("seed=99");
    expect(seedInit.method).toBe("POST");
  });

  it("calls studentService list, detail, and explanation endpoints", async () => {
    const fetchMock = mockSuccessFetch({ items: [], total: 0, limit: 20, offset: 0 });
    await studentService.listStudents({ search: "STU-10", sort_by: "attendance_rate" });
    expect(fetchMock.mock.calls[0][0]).toContain("/api/ps3/students?");
    expect(fetchMock.mock.calls[0][0]).toContain("search=STU-10");

    await studentService.getStudentDetail("STU 01");
    expect(fetchMock.mock.calls[1][0]).toContain("/api/ps3/students/STU%2001");

    await studentService.getStudentExplanation("STU-01");
    expect(fetchMock.mock.calls[2][0]).toContain("/api/ps3/students/STU-01/explanation");
  });

  it("calls modelService train and metrics endpoints", async () => {
    const fetchMock = mockSuccessFetch({ model_version: "rf_v1" });
    await modelService.trainModel({ dataset_mode: "auto", allow_synthetic_fallback: true });
    expect(fetchMock.mock.calls[0][0]).toContain("/api/ps3/model/train");
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe("POST");

    await modelService.getMetrics("rf_v1");
    expect(fetchMock.mock.calls[1][0]).toContain("/api/ps3/model/metrics?model_version=rf_v1");
  });

  it("calls predictionService run and list endpoints", async () => {
    const fetchMock = mockSuccessFetch({ total_predicted: 5 });
    await predictionService.runPredictions({ include_synthetic: true, persist_interventions: true });
    expect(fetchMock.mock.calls[0][0]).toContain("/api/ps3/predictions/run");
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe("POST");

    await predictionService.listPredictions({
      latest_only: true,
      risk_level: "high",
      sort_by: "risk_score",
    });
    const listUrl = fetchMock.mock.calls[1][0] as string;
    expect(listUrl).toContain("/api/ps3/predictions?");
    expect(listUrl).toContain("latest_only=true");
    expect(listUrl).toContain("risk_level=high");
  });

  it("calls interventionService CRUD, history, and student interventions endpoints", async () => {
    const fetchMock = mockSuccessFetch({ items: [], total: 0 });
    await interventionService.listInterventions({ page: 2, page_size: 20, status: "ASSIGNED" });
    const listUrl = fetchMock.mock.calls[0][0] as string;
    expect(listUrl).toContain("/api/ps3/interventions?");
    expect(listUrl).toContain("page=2");
    expect(listUrl).toContain("status=ASSIGNED");

    await interventionService.createIntervention({
      student_id: "STU-1001",
      intervention_type: "advisor_outreach",
      recommended_action: "Schedule outreach session",
      priority: "high",
    });
    expect(fetchMock.mock.calls[1][0]).toContain("/api/ps3/interventions");
    expect((fetchMock.mock.calls[1][1] as RequestInit).method).toBe("POST");

    await interventionService.updateIntervention(7, {
      version: 1,
      assigned_to: "counsellor.a",
      status: "IN_PROGRESS",
    });
    expect(fetchMock.mock.calls[2][0]).toContain("/api/ps3/interventions/7");
    expect((fetchMock.mock.calls[2][1] as RequestInit).method).toBe("PATCH");

    await interventionService.getInterventionHistory(7);
    expect(fetchMock.mock.calls[3][0]).toContain("/api/ps3/interventions/7/history");

    await interventionService.listStudentInterventions("STU-1001");
    expect(fetchMock.mock.calls[4][0]).toContain("/api/ps3/students/STU-1001/interventions");
  });
});

