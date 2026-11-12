"use client";

import React, { useEffect, useState } from "react";
import { CheckCircle2, AlertCircle, RefreshCw, Sparkles, User, Bell } from "lucide-react";
import { fetchHealth } from "@/lib/api";

export function Navbar() {
  const [healthStatus, setHealthStatus] = useState<string>("checking");
  const [lastCheck, setLastCheck] = useState<string>("");

  const checkStatus = async () => {
    setHealthStatus("checking");
    const res = await fetchHealth();
    if (res?.status === "healthy") {
      setHealthStatus("online");
    } else {
      setHealthStatus("offline");
    }
    setLastCheck(new Date().toLocaleTimeString());
  };

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-16 border-b border-slate-200 bg-white/95 backdrop-blur px-8 flex items-center justify-between sticky top-0 z-30 shadow-sm">
      <div className="flex items-center space-x-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-800">
            Automated Formative Assessment & Subjective Grading
          </h2>
          <p className="text-xs text-slate-500">
            Higher Education Intelligent Evaluation Engine (PS2)
          </p>
        </div>
      </div>

      <div className="flex items-center space-x-5">
        {/* API Health Indicator */}
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full border border-slate-200 bg-slate-50 text-xs">
          {healthStatus === "online" ? (
            <span className="flex items-center text-emerald-700 font-medium space-x-1.5">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span>FastAPI Online</span>
            </span>
          ) : healthStatus === "checking" ? (
            <span className="flex items-center text-slate-500 space-x-1.5">
              <RefreshCw className="w-3 h-3 animate-spin" />
              <span>Verifying API...</span>
            </span>
          ) : (
            <span className="flex items-center text-rose-600 font-medium space-x-1.5">
              <AlertCircle className="w-3.5 h-3.5" />
              <span>FastAPI Disconnected</span>
            </span>
          )}
          <button
            onClick={checkStatus}
            title="Refresh backend status"
            className="text-slate-400 hover:text-slate-600 transition-colors pl-1 border-l border-slate-200"
          >
            <RefreshCw className="w-3 h-3" />
          </button>
        </div>

        {/* User Info */}
        <div className="flex items-center space-x-3 pl-4 border-l border-slate-200">
          <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-600 text-xs font-semibold">
            FP
          </div>
          <div className="hidden sm:block text-left">
            <p className="text-xs font-medium text-slate-800">Prof. Evaluator</p>
            <p className="text-[11px] text-slate-500">Faculty Role</p>
          </div>
        </div>
      </div>
    </header>
  );
}

