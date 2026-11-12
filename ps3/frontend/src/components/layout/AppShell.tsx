"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BarChart3,
  ClipboardCheck,
  Database,
  FlaskConical,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Menu,
  Shield,
  Users,
  X,
} from "lucide-react";
import { useAuth } from "@/components/auth/AuthProvider";
import { NotificationsPanel } from "@/components/shared/NotificationsPanel";
import { dataService } from "@/services/dataService";
import { UserRole } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

const NAV_ITEMS: Array<{
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  roles: UserRole[];
}> = [
  { href: "/", label: "Overview", icon: LayoutDashboard, roles: ["administrator", "counsellor", "viewer"] },
  { href: "/data", label: "Data Management", icon: Database, roles: ["administrator"] },
  { href: "/students", label: "Student Risk Analysis", icon: Users, roles: ["administrator", "counsellor"] },
  { href: "/model", label: "Model Analytics", icon: BarChart3, roles: ["administrator", "counsellor", "viewer"] },
  { href: "/interventions", label: "Interventions", icon: ClipboardCheck, roles: ["administrator", "counsellor"] },
  { href: "/admin", label: "Administration", icon: Shield, roles: ["administrator"] },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { hasAuthProvider, user, isLoading: authLoading, logout, hasRole } = useAuth();
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const [backendConnected, setBackendConnected] = React.useState<boolean | null>(null);
  const [dbDialect, setDbDialect] = React.useState<string>("");
  const [hasSyntheticData, setHasSyntheticData] = React.useState<boolean>(false);

  const checkStatus = React.useCallback(async () => {
    try {
      const healthRes = await dataService.getHealth();
      setBackendConnected(healthRes.data.database_connected);
      setDbDialect(healthRes.data.database_dialect);
      if (!hasAuthProvider || user) {
        const summaryRes = await dataService.getSummary();
        setHasSyntheticData(summaryRes.data.contains_synthetic_data);
      }
    } catch {
      setBackendConnected(false);
    }
  }, [hasAuthProvider, user]);

  React.useEffect(() => {
    if (pathname === "/login") return;
    void checkStatus();
    const interval = setInterval(() => {
      void checkStatus();
    }, 30000);
    return () => clearInterval(interval);
  }, [checkStatus, pathname]);

  React.useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  if (pathname === "/login") {
    return <>{children}</>;
  }

  if (hasAuthProvider && (authLoading || !user)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
        <div className="rounded-lg border border-slate-200 bg-white px-6 py-4 text-sm text-slate-600 shadow-xs">
          Verifying institutional session...
        </div>
      </div>
    );
  }

  const visibleNavItems = NAV_ITEMS.filter((item) => hasRole(...item.roles));

  const isNavActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(`${href}/`);
  };

  return (
    <div className="min-h-screen bg-slate-50 lg:flex">
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-xs lg:hidden"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 shrink-0 flex-col bg-navy-900 text-slate-100 transition-transform duration-200 lg:static lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-16 items-center justify-between border-b border-navy-800 px-5">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 text-white shadow-xs">
              <GraduationCap className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-bold tracking-tight text-white">EDUCORE AI</p>
              <p className="text-[11px] text-slate-400">PS3 Dropout Risk Suite</p>
            </div>
          </Link>
          <button
            type="button"
            className="rounded-md p-1 text-slate-300 hover:bg-navy-800 lg:hidden"
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation menu"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4" aria-label="Primary Navigation">
          {visibleNavItems.map((item) => {
            const Icon = item.icon;
            const active = isNavActive(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-blue-600 text-white shadow-xs"
                    : "text-slate-300 hover:bg-navy-800 hover:text-white"
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-navy-800 p-4 text-xs text-slate-400">
          <p className="font-semibold text-slate-200">Advisory Decision Support</p>
          <p className="mt-1 leading-relaxed">
            Risk indicators guide advisor outreach and never automate disciplinary or enrollment
            decisions.
          </p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-slate-200 bg-white/95 px-4 backdrop-blur-xs sm:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="rounded-md border border-slate-200 p-2 text-slate-700 hover:bg-slate-100 lg:hidden"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation menu"
            >
              <Menu className="h-4 w-4" />
            </button>
            <div>
              <h1 className="text-sm font-semibold text-navy-900 sm:text-base">
                Student Dropout Risk Prediction Dashboard
              </h1>
              <p className="hidden text-xs text-slate-500 sm:block">
                EDUCORE AI Phase 3 · Institutional Early-Warning & Explainability Workspace
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {hasSyntheticData && (
              <Badge variant="demo" title="Workspace currently contains synthetic demonstration records">
                <FlaskConical className="h-3 w-3" />
                DEMO DATA – SYNTHETIC
              </Badge>
            )}
            <NotificationsPanel />
            <div className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700">
              <Activity
                className={cn(
                  "h-3.5 w-3.5",
                  backendConnected === true
                    ? "text-emerald-600"
                    : backendConnected === false
                      ? "text-red-600"
                      : "text-slate-400"
                )}
              />
              <span>
                {backendConnected === true
                  ? `API Connected${dbDialect ? ` (${dbDialect})` : ""}`
                  : backendConnected === false
                    ? "API Offline"
                    : "Checking API..."}
              </span>
            </div>
            {user && (
              <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs">
                <span className="font-semibold text-slate-800">{user.full_name}</span>
                <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] uppercase text-slate-700">
                  {user.role}
                </span>
                <button
                  type="button"
                  onClick={() => void logout()}
                  className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  title="Sign out and revoke session"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">Sign Out</span>
                </button>
              </div>
            )}
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}

