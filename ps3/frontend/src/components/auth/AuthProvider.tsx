"use client";

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { clearCsrfToken, setCsrfToken, setUnauthorizedHandler } from "@/lib/api";
import { UserOut, UserRole } from "@/lib/types";
import { authService } from "@/services/authService";

export interface AuthContextValue {
  hasAuthProvider: boolean;
  user: UserOut | null;
  isLoading: boolean;
  sessionMessage: string | null;
  clearSessionMessage: () => void;
  login: (usernameOrEmail: string, password: string) => Promise<UserOut>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
  hasRole: (...roles: UserRole[]) => boolean;
}

const DEFAULT_AUTH_CONTEXT: AuthContextValue = {
  hasAuthProvider: false,
  user: null,
  isLoading: false,
  sessionMessage: null,
  clearSessionMessage: () => undefined,
  login: async () => {
    throw new Error("AuthProvider is not mounted.");
  },
  logout: async () => undefined,
  refreshSession: async () => undefined,
  hasRole: () => true,
};

const AuthContext = createContext<AuthContextValue>(DEFAULT_AUTH_CONTEXT);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<UserOut | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [sessionMessage, setSessionMessage] = useState<string | null>(null);
  const pathnameRef = useRef(pathname);
  pathnameRef.current = pathname;

  const clearSessionMessage = useCallback(() => {
    setSessionMessage(null);
  }, []);

  const handleSessionExpired = useCallback(() => {
    clearCsrfToken();
    setUser(null);
    setSessionMessage("Your session expired or is no longer valid. Please sign in again.");
    if (pathnameRef.current !== "/login") {
      router.replace("/login?reason=expired");
    }
  }, [router]);

  useEffect(() => {
    setUnauthorizedHandler(handleSessionExpired);
    return () => setUnauthorizedHandler(null);
  }, [handleSessionExpired]);

  useEffect(() => {
    let active = true;
    async function verifyCurrentSession() {
      setIsLoading(true);
      try {
        const res = await authService.me();
        if (!active) return;
        setCsrfToken(res.data.csrf_token);
        setUser(res.data.user);
      } catch {
        if (!active) return;
        clearCsrfToken();
        setUser(null);
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    }
    void verifyCurrentSession();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (isLoading) return;
    if (!user && pathname !== "/login") {
      router.replace(sessionMessage ? "/login?reason=expired" : "/login");
    } else if (user && pathname === "/login") {
      router.replace("/");
    }
  }, [isLoading, pathname, router, sessionMessage, user]);

  const login = useCallback(
    async (usernameOrEmail: string, password: string): Promise<UserOut> => {
      const res = await authService.login(usernameOrEmail, password);
      setCsrfToken(res.data.csrf_token);
      setSessionMessage(null);
      setUser(res.data.user);
      return res.data.user;
    },
    []
  );

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } catch {
      // Clear local session state even if server session already expired.
    } finally {
      clearCsrfToken();
      setUser(null);
      setSessionMessage(null);
      router.replace("/login");
    }
  }, [router]);

  const refreshSession = useCallback(async () => {
    const res = await authService.refresh();
    setCsrfToken(res.data.csrf_token);
    setUser(res.data.user);
  }, []);

  const hasRole = useCallback(
    (...roles: UserRole[]): boolean => {
      if (!user) return false;
      return roles.includes(user.role);
    },
    [user]
  );

  return (
    <AuthContext.Provider
      value={{
        hasAuthProvider: true,
        user,
        isLoading,
        sessionMessage,
        clearSessionMessage,
        login,
        logout,
        refreshSession,
        hasRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}

