import { describe, expect, it, vi } from "vitest";
import { ApiClientError, apiRequest, buildApiUrl } from "@/lib/api";

describe("api client & envelope parsing", () => {
  it("constructs versioned /api/ps3 URLs and omits empty query params", () => {
    const url = buildApiUrl("/students", {
      limit: 20,
      offset: 0,
      search: "",
      is_synthetic: false,
      unused: undefined,
    });
    expect(url).toContain("/api/ps3/students?");
    expect(url).toContain("limit=20");
    expect(url).toContain("offset=0");
    expect(url).toContain("is_synthetic=false");
    expect(url).not.toContain("search=");
    expect(url).not.toContain("unused");
  });

  it("unwraps valid APIResponse success envelope", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        status: "success",
        message: "Health check succeeded",
        data: {
          service: "educore-ps3",
          environment: "development",
          database_connected: true,
          database_dialect: "sqlite",
        },
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

    const res = await apiRequest<{ service: string }>("/health");
    expect(res.data.service).toBe("educore-ps3");
    expect(res.message).toBe("Health check succeeded");
    expect(res.meta.module).toBe("ps3");
  });

  it("throws ApiClientError with primaryCode on backend error envelope", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({
        status: "error",
        message: "No trained model found.",
        data: null,
        errors: [{ code: "MODEL_NOT_TRAINED", message: "Train a model first." }],
        meta: {
          module: "ps3",
          api_version: "1.0.0",
          timestamp: "2026-11-12T00:00:00Z",
          contains_synthetic_data: false,
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiRequest("/model/metrics")).rejects.toMatchObject({
      name: "ApiClientError",
      statusCode: 404,
      primaryCode: "MODEL_NOT_TRAINED",
      message: "No trained model found.",
    });
  });

  it("throws NETWORK_ERROR ApiClientError when fetch rejects", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);

    try {
      await apiRequest("/health");
      expect.fail("Should have thrown ApiClientError");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiClientError);
      expect((err as ApiClientError).primaryCode).toBe("NETWORK_ERROR");
      expect((err as ApiClientError).statusCode).toBe(0);
    }
  });
});

