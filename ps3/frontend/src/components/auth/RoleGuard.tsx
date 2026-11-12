"use client";

import React from "react";
import Link from "next/link";
import { ShieldAlert, LockKeyhole } from "lucide-react";
import { useAuth } from "@/components/auth/AuthProvider";
import { UserRole } from "@/lib/types";

interface RoleGuardProps {
  allowedRoles: UserRole[];
  sectionTitle?: string;
  children: React.ReactNode;
}

export function RoleGuard({ allowedRoles, sectionTitle, children }: RoleGuardProps) {
  const { hasAuthProvider, user, isLoading } = useAuth();

  if (!hasAuthProvider) {
    return <>{children}</>;
  }

  if (isLoading) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-600 shadow-sm">
        Verifying authenticated role permissions...
      </div>
    );
  }

  if (!user) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-8 text-center shadow-sm">
        <LockKeyhole className="mx-auto h-8 w-8 text-slate-400" />
        <p className="mt-2 text-sm font-medium text-slate-800">Authentication required</p>
        <p className="mt-1 text-xs text-slate-500">Redirecting to institutional sign-in...</p>
      </div>
    );
  }

  if (!allowedRoles.includes(user.role)) {
    return (
      <div
        role="alert"
        className="mx-auto max-w-xl rounded-lg border border-amber-200 bg-amber-50 p-6 shadow-sm"
      >
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-0.5 h-6 w-6 shrink-0 text-amber-700" />
          <div>
            <h2 className="text-base font-semibold text-amber-950">
              403 — Access Restricted{sectionTitle ? `: ${sectionTitle}` : ""}
            </h2>
            <p className="mt-1 text-sm text-amber-900">
              Your account (<strong>{user.username}</strong>) is signed in with role{" "}
              <span className="rounded bg-amber-100 px-1.5 py-0.5 font-mono text-xs font-semibold">
                {user.role}
              </span>
              . This workspace requires one of:{" "}
              <span className="font-mono text-xs font-semibold">{allowedRoles.join(", ")}</span>.
            </p>
            <div className="mt-4">
              <Link
                href="/"
                className="inline-flex items-center rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800"
              >
                Return to Overview
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

