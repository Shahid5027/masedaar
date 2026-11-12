import { Badge } from "@/components/ui/badge";
import { RiskLevel } from "@/lib/types";

interface RiskBadgeProps {
  level: RiskLevel | string | null | undefined;
}

export function RiskBadge({ level }: RiskBadgeProps) {
  if (!level) {
    return <Badge variant="outline">Not Scored</Badge>;
  }

  const normalized = level.toLowerCase();
  if (normalized === "high") {
    return <Badge variant="high">HIGH RISK</Badge>;
  }
  if (normalized === "medium") {
    return <Badge variant="medium">MEDIUM RISK</Badge>;
  }
  if (normalized === "low") {
    return <Badge variant="low">LOW RISK</Badge>;
  }
  return <Badge variant="default">{level.toUpperCase()}</Badge>;
}

