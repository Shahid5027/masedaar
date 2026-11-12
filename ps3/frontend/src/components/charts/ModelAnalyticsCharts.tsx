"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfusionMatrixOut } from "@/lib/types";
import { humanizeFeatureName } from "@/lib/utils";

export function FeatureImportanceChart({
  featureImportances,
}: {
  featureImportances: Record<string, number>;
}) {
  const data = Object.entries(featureImportances)
    .map(([feature, importance]) => ({
      feature: humanizeFeatureName(feature),
      importancePct: Number((importance * 100).toFixed(2)),
    }))
    .sort((a, b) => b.importancePct - a.importancePct);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Random Forest Feature Importance</CardTitle>
        <CardDescription>
          Relative Gini importance across the 7 academic and LMS input features (statistical
          importance, not causal weight).
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              layout="vertical"
              margin={{ top: 5, right: 24, left: 28, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis type="number" unit="%" tick={{ fontSize: 12, fill: "#475569" }} />
              <YAxis
                type="category"
                dataKey="feature"
                width={135}
                tick={{ fontSize: 12, fill: "#0f1e3a" }}
              />
              <Tooltip formatter={(val: number) => [`${val}%`, "Importance"]} />
              <Bar dataKey="importancePct" radius={[0, 6, 6, 0]}>
                {data.map((_, idx) => (
                  <Cell key={idx} fill={idx < 3 ? "#2563eb" : "#64748b"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

export function ConfusionMatrixCard({ matrix }: { matrix: ConfusionMatrixOut }) {
  const total = matrix.tn + matrix.fp + matrix.fn + matrix.tp;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Holdout Confusion Matrix</CardTitle>
        <CardDescription>
          Stratified test set evaluation across {total} held-out labeled record(s).
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-2 text-center text-xs">
          <div />
          <div className="rounded-md bg-slate-100 py-2 font-semibold text-slate-600">
            Predicted: Retained (0)
          </div>
          <div className="rounded-md bg-slate-100 py-2 font-semibold text-slate-600">
            Predicted: Dropout (1)
          </div>

          <div className="flex items-center justify-center rounded-md bg-slate-100 px-2 font-semibold text-slate-600">
            Actual: Retained (0)
          </div>
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
            <p className="text-xl font-bold text-emerald-800">{matrix.tn}</p>
            <p className="mt-1 text-[11px] font-medium text-emerald-700">True Negative (TN)</p>
          </div>
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
            <p className="text-xl font-bold text-amber-800">{matrix.fp}</p>
            <p className="mt-1 text-[11px] font-medium text-amber-700">False Positive (FP)</p>
          </div>

          <div className="flex items-center justify-center rounded-md bg-slate-100 px-2 font-semibold text-slate-600">
            Actual: Dropout (1)
          </div>
          <div className="rounded-lg border border-red-200 bg-red-50 p-4">
            <p className="text-xl font-bold text-red-800">{matrix.fn}</p>
            <p className="mt-1 text-[11px] font-medium text-red-700">False Negative (FN)</p>
          </div>
          <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
            <p className="text-xl font-bold text-blue-800">{matrix.tp}</p>
            <p className="mt-1 text-[11px] font-medium text-blue-700">True Positive (TP)</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

