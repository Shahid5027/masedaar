"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface RiskCounts {
  low: number;
  medium: number;
  high: number;
}

const RISK_COLORS = {
  low: "#15803d",
  medium: "#d97706",
  high: "#b91c1c",
};

export function RiskDistributionCharts({ counts }: { counts: RiskCounts }) {
  const total = counts.low + counts.medium + counts.high;
  const chartData = [
    { name: "Low Risk", key: "low", value: counts.low, color: RISK_COLORS.low },
    { name: "Medium Risk", key: "medium", value: counts.medium, color: RISK_COLORS.medium },
    { name: "High Risk", key: "high", value: counts.high, color: RISK_COLORS.high },
  ];

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Student Risk Distribution (Donut)</CardTitle>
          <CardDescription>
            Latest predicted risk tier share across {total} scored student(s).
          </CardDescription>
        </CardHeader>
        <CardContent>
          {total === 0 ? (
            <div className="flex h-64 items-center justify-center text-sm text-slate-500">
              No predictions generated yet. Run predictions to view risk distribution.
            </div>
          ) : (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={chartData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={58}
                    outerRadius={90}
                    paddingAngle={3}
                  >
                    {chartData.map((entry) => (
                      <Cell key={entry.key} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(val: number) => [
                      `${val} student(s) (${total > 0 ? ((val / total) * 100).toFixed(1) : "0.0"}%)`,
                      "Count",
                    ]}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Risk Tier Breakdown (Bar)</CardTitle>
          <CardDescription>
            Headcount per risk category using active backend thresholds.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {total === 0 ? (
            <div className="flex h-64 items-center justify-center text-sm text-slate-500">
              No predictions generated yet. Run predictions to view tier counts.
            </div>
          ) : (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#475569" }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "#475569" }} />
                  <Tooltip formatter={(val: number) => [`${val} student(s)`, "Students"]} />
                  <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                    {chartData.map((entry) => (
                      <Cell key={entry.key} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

