import { Activity } from "lucide-react";
import { StatusChip } from "@/components/status-chip";
import type { HealthObservation } from "@/lib/contracts/types";

export function HealthDetails({
  observations,
}: Readonly<{ observations: HealthObservation[] }>) {
  if (observations.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No health check is configured.
      </p>
    );
  }
  return (
    <ul className="grid gap-3">
      {observations.map((observation) => (
        <li
          key={observation.healthCheckRef}
          className="rounded-lg border bg-muted/20 p-3"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="flex min-w-0 items-center gap-2 break-all text-sm font-medium">
              <Activity aria-hidden="true" />
              {observation.healthCheckRef}
            </span>
            <StatusChip
              label={
                observation.status === "passing"
                  ? "Healthy"
                  : observation.status === "failing"
                    ? "Unhealthy"
                    : "Not observed"
              }
              tone={
                observation.status === "passing"
                  ? "positive"
                  : observation.status === "failing"
                    ? "destructive"
                    : "neutral"
              }
            />
          </div>
          {observation.reason ? (
            <p className="mt-2 text-xs text-muted-foreground">
              {observation.reason}
            </p>
          ) : null}
          {observation.latencyMs != null ? (
            <p className="mt-1 font-mono text-xs text-muted-foreground">
              {observation.latencyMs.toFixed(1)} ms
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
