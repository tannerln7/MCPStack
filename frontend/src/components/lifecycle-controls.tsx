"use client";

import { LoaderCircle, Play, RefreshCw, Square } from "lucide-react";
import { useEffect, useState } from "react";
import { RecentLogsPanel } from "@/components/recent-logs";
import {
  lifecycleActionClasses,
  lifecycleTone,
  StatusChip,
} from "@/components/status-chip";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type {
  ComponentLifecycle,
  LifecycleAction,
  LifecycleObservation,
  RecentLogs,
} from "@/lib/contracts/types";

export function LifecycleControls({
  stackId,
  componentId,
  initialLifecycle,
  initialLogs,
}: Readonly<{
  stackId: string;
  componentId: string;
  initialLifecycle: ComponentLifecycle;
  initialLogs: RecentLogs | null;
}>) {
  const [observation, setObservation] = useState(initialLifecycle.observation);
  const [logs, setLogs] = useState(initialLogs);
  const [pending, setPending] = useState<LifecycleAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isActive =
    observation?.state === "active" || observation?.state === "activating";
  const toggleAction: LifecycleAction = isActive ? "stop" : "start";
  const availableActions = initialLifecycle.actions;
  const canToggle = availableActions.includes(toggleAction);
  const canRestart = availableActions.includes("restart");
  const ToggleIcon = toggleAction === "start" ? Play : Square;

  useEffect(
    () => setObservation(initialLifecycle.observation),
    [initialLifecycle],
  );
  useEffect(() => setLogs(initialLogs), [initialLogs]);

  async function act(action: LifecycleAction) {
    setPending(action);
    setError(null);
    try {
      const response = await fetch(
        `/api/stacks/${encodeURIComponent(stackId)}/components/${encodeURIComponent(componentId)}/lifecycle-actions`,
        {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ action }),
        },
      );
      const payload = (await response.json()) as
        | LifecycleObservation
        | { detail?: { code?: string; message?: string } };
      if (!response.ok || !("provider" in payload)) {
        const errorDetail = "provider" in payload ? null : payload.detail;
        throw new Error(
          errorDetail?.message
            ? errorDetail.message
            : `Lifecycle action failed with ${response.status}`,
        );
      }
      setObservation(payload);
      const logResponse = await fetch(
        `/api/stacks/${encodeURIComponent(stackId)}/components/${encodeURIComponent(componentId)}/logs?limit=100`,
      );
      if (logResponse.ok) setLogs((await logResponse.json()) as RecentLogs);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Lifecycle action failed",
      );
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="grid min-w-0 gap-5">
      <div className="flex flex-wrap items-center gap-3">
        {canToggle ? (
          <Button
            type="button"
            variant="outline"
            className={lifecycleActionClasses[toggleAction]}
            disabled={pending !== null}
            onClick={() => act(toggleAction)}
          >
            {pending === toggleAction ? (
              <LoaderCircle data-icon="inline-start" />
            ) : (
              <ToggleIcon data-icon="inline-start" />
            )}
            {pending === toggleAction
              ? `${toggleAction === "start" ? "Starting" : "Stopping"}…`
              : toggleAction[0].toUpperCase() + toggleAction.slice(1)}
          </Button>
        ) : null}
        {canRestart ? (
          <Button
            type="button"
            variant="outline"
            disabled={pending !== null || observation?.state !== "active"}
            onClick={() => act("restart")}
          >
            {pending === "restart" ? (
              <LoaderCircle data-icon="inline-start" />
            ) : (
              <RefreshCw data-icon="inline-start" />
            )}
            {pending === "restart" ? "Restarting…" : "Restart"}
          </Button>
        ) : null}
      </div>
      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Lifecycle action failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      {observation ? (
        <div className="min-w-0 rounded-lg border bg-muted/20 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium">systemd user provider</p>
              <p className="mt-1 break-words text-xs text-muted-foreground">
                {observation.detail}
              </p>
            </div>
            <StatusChip
              label={observation.state}
              tone={lifecycleTone(observation.state)}
            />
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Boot enabled: {observation.bootEnabled ? "yes" : "no"}
          </p>
        </div>
      ) : null}
      <RecentLogsPanel
        initialLogs={logs}
        refreshPath={`/api/stacks/${encodeURIComponent(stackId)}/components/${encodeURIComponent(componentId)}/logs?limit=100`}
        downloadName={`${stackId}-${componentId}-logs.txt`}
      />
    </div>
  );
}
