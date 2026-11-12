import { apiRequest, ApiResult } from "@/lib/api";
import { LoginData, SessionMeData } from "@/lib/types";

export const authService = {
  login(username_or_email: string, password: string): Promise<ApiResult<LoginData>> {
    return apiRequest<LoginData>("/auth/login", {
      method: "POST",
      body: { username_or_email, password },
      skipUnauthorizedRedirect: true,
    });
  },

  logout(): Promise<ApiResult<{ logged_out: boolean }>> {
    return apiRequest<{ logged_out: boolean }>("/auth/logout", {
      method: "POST",
      skipUnauthorizedRedirect: true,
    });
  },

  me(): Promise<ApiResult<SessionMeData>> {
    return apiRequest<SessionMeData>("/auth/me", {
      skipUnauthorizedRedirect: true,
    });
  },

  refresh(): Promise<ApiResult<SessionMeData>> {
    return apiRequest<SessionMeData>("/auth/refresh", {
      method: "POST",
    });
  },
};

