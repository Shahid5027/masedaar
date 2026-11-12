"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FeatureStat } from "@/lib/types";
import { humanizeFeatureName } from "@/lib/utils";

const SUMMARY_KEYS = [
  "attendance_rate",
  "average_grade",
  "lms_logins_30d",
  "engagement_change_pct",
];

export function FeatureStatsChart({
  featureStatistics,
}: {
  featureStatistics: Record<string, FeatureStat>;
}) {
  const rows = SUMMARY_KEYS.filter((k) => featureStatistics[k]).map((key) => ({
    name: humanizeFeatureName(key),
    mean: Number(featureStatistics[key].mean.toFixed(2)),
    median: Number(featureStatistics[key].median.toFixed(2)),
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cohort Engagement & Academic Indicators</CardTitle>
        <CardDescription>
          Mean and median across latest student snapshots from GET /api/ps3/data/summary.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <div className="flex h-64 items-center justify-center text-sm text-slate-500">
            No student snapshot statistics available yet. Upload CSV or seed demo data.
          </div>
        ) : (
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#475569" }} />
                <YAxis tick={{ fontSize: 12, fill: "#475569" }} />
                <Tooltip />
                <Bar dataKey="mean" name="Mean" fill="#2563eb" radius={[4, 4, 0, 0]} />
                <Bar dataKey="median" name="Median" fill="#0f1e3a" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

