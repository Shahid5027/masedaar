import { FlaskConical, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/feedback";

export function DemoDataBadge({
  isDemo,
  realLabel = "REAL DATA",
}: {
  isDemo: boolean;
  realLabel?: string;
}) {
  if (isDemo) {
    return (
      <Badge variant="demo" title="Synthetic demonstration dataset record">
        <FlaskConical className="h-3 w-3" />
        DEMO DATA – SYNTHETIC
      </Badge>
    );
  }

  return (
    <Badge variant="real">
      <ShieldCheck className="h-3 w-3" />
      {realLabel}
    </Badge>
  );
}

export function SyntheticBanner({
  notice,
  title = "DEMO DATA – SYNTHETIC RECORDS PRESENT",
}: {
  notice?: string | null;
  title?: string;
}) {
  return (
    <Alert variant="demo" className="flex items-start gap-3">
      <FlaskConical className="mt-0.5 h-5 w-5 shrink-0 text-violet-700" />
      <div>
        <p className="font-semibold text-violet-950">{title}</p>
        <p className="mt-0.5 text-xs text-violet-900">
          {notice ||
            "Records labeled DEMO DATA – SYNTHETIC are generated demonstration records, not real institutional student records."}
        </p>
      </div>
    </Alert>
  );
}

export function ResponsibleAiFooterNotice({ text }: { text?: string }) {
  return (
    <Alert variant="info" className="flex items-start gap-3">
      <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-blue-700" />
      <p className="text-xs leading-relaxed text-blue-950">
        {text ||
          "Responsible AI Notice: Dropout risk scores and support suggestions assist academic advisors and counselors. They indicate statistical patterns, do not guarantee outcomes, and do not replace human judgement."}
      </p>
    </Alert>
  );
}

