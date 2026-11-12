import { APIResponse, ErrorDetail, ResponseMeta } from "./types";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export function getApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL;
  return raw.replace(/\/+$/, "");
}

export function buildApiUrl(
  path: string,
  query?: Record<string, string | number | boolean | null | undefined>
): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const base = `${getApiBaseUrl()}/api/ps3${normalizedPath}`;
  if (!query) return base;

  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `${base}?${qs}` : base;
}

export class ApiClientError extends Error {
  public readonly statusCode: number;
  public readonly errors: ErrorDetail[];
  public readonly meta?: ResponseMeta;

  constructor(
    statusCode: number,
    message: string,
    errors: ErrorDetail[] = [],
    meta?: ResponseMeta
  ) {
    super(message);
    this.name = "ApiClientError";
    this.statusCode = statusCode;
    this.errors = errors;
    this.meta = meta;
  }

  get primaryCode(): string | undefined {
    return this.errors[0]?.code;
  }
}

const CSRF_COOKIE_NAME = "ps3_csrf";
let _csrfToken: string | null = null;
let _onUnauthorized: ((status: number, code?: string) => void) | null = null;

export function setCsrfToken(token: string | null): void {
  _csrfToken = token;
}

export function clearCsrfToken(): void {
  _csrfToken = null;
}

export function setUnauthorizedHandler(
  handler: ((status: number, code?: string) => void) | null
): void {
  _onUnauthorized = handler;
}

function readCookieValue(name: string): string | null {
  if (typeof document === "undefined" || !document.cookie) {
    return null;
  }
  const cookies = document.cookie.split(";");
  for (const raw of cookies) {
    const idx = raw.indexOf("=");
    if (idx === -1) continue;
    const key = raw.slice(0, idx).trim();
    if (key === name) {
      return decodeURIComponent(raw.slice(idx + 1).trim());
    }
  }
  return null;
}

export function getActiveCsrfToken(): string | null {
  return _csrfToken || readCookieValue(CSRF_COOKIE_NAME);
}

export interface ApiResult<T> {
  data: T;
  message: string;
  meta: ResponseMeta;
  errors: ErrorDetail[];
}

export async function apiRequest<T>(
  path: string,
  options: {
    method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
    query?: Record<string, string | number | boolean | null | undefined>;
    body?: unknown;
    formData?: FormData;
    signal?: AbortSignal;
    skipUnauthorizedRedirect?: boolean;
  } = {}
): Promise<ApiResult<T>> {
  const url = buildApiUrl(path, options.query);
  const method = options.method ?? "GET";
  const headers: Record<string, string> = {
    Accept: "application/json",
  };

  let requestBody: BodyInit | undefined;
  if (options.formData) {
    requestBody = options.formData;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    requestBody = JSON.stringify(options.body);
  }

  if (method !== "GET" && path !== "/auth/login") {
    const csrf = getActiveCsrfToken();
    if (csrf) {
      headers["X-CSRF-Token"] = csrf;
    }
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body: requestBody,
      credentials: "include",
      signal: options.signal,
      cache: "no-store",
    });
  } catch (err) {
    const msg =
      err instanceof Error && err.name === "AbortError"
        ? "Request was cancelled."
        : "Unable to connect to the EDUCORE PS3 backend server. Verify FastAPI is running and CORS/API URL settings are correct.";
    throw new ApiClientError(0, msg, [{ code: "NETWORK_ERROR", message: msg }]);
  }

  let payload: APIResponse<T> | null = null;
  try {
    payload = (await response.json()) as APIResponse<T>;
  } catch {
    throw new ApiClientError(
      response.status,
      `Backend returned an unreadable response (HTTP ${response.status}).`,
      [{ code: "INVALID_JSON_RESPONSE", message: `HTTP ${response.status}` }]
    );
  }

  if (!response.ok || payload.status === "error" || payload.data === null) {
    const primaryCode = payload.errors?.[0]?.code;
    if (
      response.status === 401 &&
      path !== "/auth/login" &&
      !options.skipUnauthorizedRedirect &&
      _onUnauthorized
    ) {
      _onUnauthorized(response.status, primaryCode);
    }
    throw new ApiClientError(
      response.status,
      payload.message || `Request failed with HTTP ${response.status}.`,
      payload.errors ?? [],
      payload.meta
    );
  }

  return {
    data: payload.data,
    message: payload.message,
    meta: payload.meta,
    errors: payload.errors ?? [],
  };
}

export function uploadWithProgress<T>(
  path: string,
  formData: FormData,
  options: {
    query?: Record<string, string | number | boolean | null | undefined>;
    onProgress?: (percent: number) => void;
  } = {}
): Promise<ApiResult<T>> {
  const url = buildApiUrl(path, options.query);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.withCredentials = true;
    xhr.setRequestHeader("Accept", "application/json");
    const csrf = getActiveCsrfToken();
    if (csrf) {
      xhr.setRequestHeader("X-CSRF-Token", csrf);
    }

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && options.onProgress) {
        const pct = Math.round((event.loaded / event.total) * 100);
        options.onProgress(pct);
      }
    };

    xhr.onload = () => {
      let payload: APIResponse<T> | null = null;
      try {
        payload = JSON.parse(xhr.responseText) as APIResponse<T>;
      } catch {
        reject(
          new ApiClientError(
            xhr.status,
            `Backend returned an unreadable response (HTTP ${xhr.status}).`,
            [{ code: "INVALID_JSON_RESPONSE", message: `HTTP ${xhr.status}` }]
          )
        );
        return;
      }

      if (xhr.status < 200 || xhr.status >= 300 || payload.status === "error" || payload.data === null) {
        reject(
          new ApiClientError(
            xhr.status,
            payload.message || `Upload failed with HTTP ${xhr.status}.`,
            payload.errors ?? [],
            payload.meta
          )
        );
        return;
      }

      resolve({
        data: payload.data,
        message: payload.message,
        meta: payload.meta,
        errors: payload.errors ?? [],
      });
    };

    xhr.onerror = () => {
      const msg =
        "Network error while uploading CSV. Verify the EDUCORE PS3 FastAPI backend is reachable.";
      reject(new ApiClientError(0, msg, [{ code: "NETWORK_ERROR", message: msg }]));
    };

    xhr.send(formData);
  });
}

