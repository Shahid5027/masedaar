import { apiRequest, ApiResult } from "@/lib/api";
import { ModelMetricsData, TrainModelRequest } from "@/lib/types";

export const modelService = {
  trainModel(payload: TrainModelRequest = {}): Promise<ApiResult<ModelMetricsData>> {
    return apiRequest<ModelMetricsData>("/model/train", {
      method: "POST",
      body: payload,
    });
  },

  getMetrics(modelVersion?: string): Promise<ApiResult<ModelMetricsData>> {
    return apiRequest<ModelMetricsData>("/model/metrics", {
      query: modelVersion ? { model_version: modelVersion } : undefined,
    });
  },
};

