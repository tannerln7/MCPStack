import { Circle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type StatusTone =
  | "active"
  | "positive"
  | "warning"
  | "destructive"
  | "neutral";

export const lifecycleActionClasses = {
  start:
    "border-status-positive/40 bg-status-positive/15 text-status-positive hover:bg-status-positive/25 dark:bg-status-positive/20 dark:hover:bg-status-positive/30",
  stop: "border-destructive/40 bg-destructive/10 text-destructive hover:bg-destructive/20 dark:bg-destructive/20 dark:hover:bg-destructive/30",
  restart: "",
} as const;

const toneClasses: Record<StatusTone, string> = {
  active:
    "border-status-active/35 bg-status-active/15 text-status-active dark:bg-status-active/20",
  positive:
    "border-status-positive/35 bg-status-positive/15 text-status-positive dark:bg-status-positive/20",
  warning:
    "border-status-warning/35 bg-status-warning/15 text-status-warning dark:bg-status-warning/20",
  destructive:
    "border-destructive/35 bg-destructive/10 text-destructive dark:bg-destructive/20",
  neutral: "border-border bg-muted text-muted-foreground",
};

export const lifecycleTone = (
  state:
    | "active"
    | "activating"
    | "deactivating"
    | "failed"
    | "inactive"
    | "unknown"
    | null
    | undefined,
): StatusTone => {
  if (state === "active") return "positive";
  if (state === "activating") return "active";
  if (state === "deactivating") return "warning";
  if (state === "failed") return "destructive";
  return "neutral";
};

export function StatusChip({
  label,
  tone,
  className,
}: Readonly<{ label: string; tone: StatusTone; className?: string }>) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "gap-1.5 rounded-md font-normal",
        toneClasses[tone],
        className,
      )}
    >
      <Circle aria-hidden="true" className="size-2 fill-current" />
      {label}
    </Badge>
  );
}
