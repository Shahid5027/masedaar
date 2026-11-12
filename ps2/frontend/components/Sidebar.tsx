"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  PlusCircle,
  FileText,
  Sparkles,
  ShieldCheck,
  GraduationCap,
  Layers,
  ChevronRight,
  ExternalLink,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navigationItems = [
  {
    name: "Assessment Dashboard",
    href: "/",
    icon: LayoutDashboard,
    description: "Overview & active courses",
  },
  {
    name: "Create Assessment",
    href: "/create-assessment",
    icon: PlusCircle,
    description: "Design questions & rubrics",
  },
  {
    name: "Student Submissions",
    href: "/submissions",
    icon: FileText,
    description: "Uploaded student answers",
  },
  {
    name: "Evaluation Results",
    href: "/evaluations",
    icon: Sparkles,
    description: "AI grading & semantic match",
  },
  {
    name: "Faculty Moderation",
    href: "/moderation",
    icon: ShieldCheck,
    description: "Human-in-the-loop review",
  },
  {
    name: "Student Result",
    href: "/student-result",
    icon: GraduationCap,
    description: "Formative feedback view",
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-72 bg-slate-900 border-r border-slate-800 flex flex-col h-screen sticky top-0 shrink-0 text-slate-300">
      {/* Brand Header */}
      <div className="p-6 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-400 flex items-center justify-center text-white shadow-lg shadow-emerald-500/20 font-bold text-lg">
            E2
          </div>
          <div>
            <h1 className="font-semibold text-white tracking-tight text-base">EDUCORE AI</h1>
            <p className="text-xs text-emerald-400 font-medium">PS2 • Subjective Grading</p>
          </div>
        </div>
      </div>

      {/* Nav list */}
      <div className="flex-1 px-4 py-6 overflow-y-auto space-y-1.5">
        <div className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          Core Workflows
        </div>
        {navigationItems.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
                isActive
                  ? "bg-emerald-600/15 text-emerald-400 border border-emerald-500/30"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
              )}
            >
              <div className="flex items-center space-x-3">
                <Icon
                  className={cn(
                    "w-5 h-5 transition-colors",
                    isActive ? "text-emerald-400" : "text-slate-400 group-hover:text-slate-200"
                  )}
                />
                <span className="truncate">{item.name}</span>
              </div>
              <ChevronRight
                className={cn(
                  "w-4 h-4 opacity-0 -translate-x-1 transition-all group-hover:opacity-100 group-hover:translate-x-0",
                  isActive && "opacity-100 translate-x-0 text-emerald-400"
                )}
              />
            </Link>
          );
        })}
      </div>

      {/* Footer Info Box */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/40">
        <div className="rounded-lg bg-slate-800/70 p-3 text-xs border border-slate-700/50">
          <div className="flex items-center justify-between mb-1">
            <span className="font-semibold text-slate-200">Shared Student ID</span>
            <span className="text-[10px] bg-emerald-950 text-emerald-400 px-1.5 py-0.5 rounded border border-emerald-800/40">Active</span>
          </div>
          <p className="text-slate-400 leading-relaxed text-[11px]">
            Connected with EDUCORE project namespace. Ready for cross-system evaluation.
          </p>
        </div>
      </div>
    </aside>
  );
}

