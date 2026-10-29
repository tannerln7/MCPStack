import { StatusChip } from "@/components/status-chip";
import type { HealthState } from "@/lib/stack-collection";

export function HealthBadge({ state }: Readonly<{ state: HealthState }>) {
  return (
    <StatusChip
      label={
        state === "healthy"
          ? "Healthy"
          : state === "unhealthy"
            ? "Unhealthy"
            : "Not observed"
      }
      tone={
        state === "healthy"
          ? "positive"
          : state === "unhealthy"
            ? "destructive"
            : "neutral"
      }
    />
  );
}
