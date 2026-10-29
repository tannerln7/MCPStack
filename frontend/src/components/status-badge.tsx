import { StatusChip, type StatusTone } from "@/components/status-chip";
import type { ComponentStatus } from "@/lib/contracts/types";

const statusLabels: Record<ComponentStatus, string> = {
  "not-observed": "Not observed",
  starting: "Starting",
  running: "Running process",
  available: "Available",
  degraded: "Degraded",
  unavailable: "Unavailable",
  stopped: "Stopped",
};

const statusTones: Record<ComponentStatus, StatusTone> = {
  "not-observed": "neutral",
  starting: "active",
  running: "positive",
  available: "positive",
  degraded: "warning",
  unavailable: "destructive",
  stopped: "neutral",
};

export function StatusBadge({ status }: Readonly<{ status: ComponentStatus }>) {
  return <StatusChip label={statusLabels[status]} tone={statusTones[status]} />;
}
