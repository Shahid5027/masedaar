import { apiRequest, ApiResult, uploadWithProgress } from "@/lib/api";
import {
  DataSummaryData,
  HealthData,
  UploadData,
  ValidationSummaryData,
} from "@/lib/types";

export const dataService = {
  getHealth(): Promise<ApiResult<HealthData>> {
    return apiRequest<HealthData>("/health");
  },

  getSummary(): Promise<ApiResult<DataSummaryData>> {
    return apiRequest<DataSummaryData>("/data/summary");
  },

  validateCsv(
    file: File,
    options: { isSynthetic?: boolean; onProgress?: (percent: number) => void } = {}
  ): Promise<ApiResult<ValidationSummaryData>> {
    const formData = new FormData();
    formData.append("file", file);

    if (options.onProgress) {
      return uploadWithProgress<ValidationSummaryData>("/data/validate", formData, {
        query: { is_synthetic: Boolean(options.isSynthetic) },
        onProgress: options.onProgress,
      });
    }

    return apiRequest<ValidationSummaryData>("/data/validate", {
      method: "POST",
      query: { is_synthetic: Boolean(options.isSynthetic) },
      formData,
    });
  },

  uploadCsv(
    file: File,
    options: { isSynthetic?: boolean; onProgress?: (percent: number) => void } = {}
  ): Promise<ApiResult<UploadData>> {
    const formData = new FormData();
    formData.append("file", file);

    if (options.onProgress) {
      return uploadWithProgress<UploadData>("/data/upload", formData, {
        query: { is_synthetic: Boolean(options.isSynthetic) },
        onProgress: options.onProgress,
      });
    }

    return apiRequest<UploadData>("/data/upload", {
      method: "POST",
      query: { is_synthetic: Boolean(options.isSynthetic) },
      formData,
    });
  },

  seedSynthetic(numRecords = 250, seed = 42): Promise<ApiResult<UploadData>> {
    return apiRequest<UploadData>("/data/seed-synthetic", {
      method: "POST",
      query: { num_records: numRecords, seed },
    });
  },
};

