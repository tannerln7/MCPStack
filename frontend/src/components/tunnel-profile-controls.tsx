"use client";

import { LoaderCircle, Play, RefreshCw, Square } from "lucide-react";
import { useState } from "react";
import {
  lifecycleActionClasses,
  lifecycleTone,
  StatusChip,
} from "@/components/status-chip";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type {
  LifecycleAction,
  LifecycleObservation,
} from "@/lib/contracts/types";

export function TunnelProfileControls({
  profileId,
  initialObservation,
  compact = false,
}: Readonly<{
  profileId: string;
  initialObservation: LifecycleObservation | null;
  compact?: boolean;
}>) {
  const [observation, setObservation] = useState(initialObservation);
  const [pending, setPending] = useState<LifecycleAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isActive =
    observation?.state === "active" || observation?.state === "activating";
  const toggleAction: LifecycleAction = isActive ? "stop" : "start";

  async function act(action: LifecycleAction) {
    setPending(action);
    setError(null);
    try {
      const response = await fetch(
        `/api/tunnel-profiles/${encodeURIComponent(profileId)}/lifecycle-actions`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action }),
        },
      );
      const payload = (await response.json()) as
        | LifecycleObservation
        | { detail?: { message?: string } };
      if (!response.ok || !("provider" in payload)) {
        throw new Error(
          "provider" in payload
            ? `Tunnel action failed with ${response.status}`
            : (payload.detail?.message ??
                `Tunnel action failed with ${response.status}`),
        );
      }
      setObservation(payload);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Tunnel action failed",
      );
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="grid min-w-0 gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size={compact ? "sm" : "default"}
          variant="outline"
          className={lifecycleActionClasses[toggleAction]}
          disabled={pending !== null}
          onClick={() => act(toggleAction)}
        >
          {pending === toggleAction ? (
            <LoaderCircle data-icon="inline-start" />
          ) : toggleAction === "start" ? (
            <Play data-icon="inline-start" />
          ) : (
            <Square data-icon="inline-start" />
          )}
          {pending === toggleAction
            ? `${toggleAction === "start" ? "Starting" : "Stopping"}…`
            : toggleAction[0].toUpperCase() + toggleAction.slice(1)}
        </Button>
        <Button
          type="button"
          size={compact ? "sm" : "default"}
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
        <StatusChip
          label={observation?.state ?? "not observed"}
          tone={lifecycleTone(observation?.state)}
        />
      </div>
      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Tunnel action failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      {!compact && observation ? (
        <p className="break-words text-xs text-muted-foreground">
          {observation.detail} Boot enabled:{" "}
          {observation.bootEnabled ? "yes" : "no"}.
        </p>
      ) : null}
    </div>
  );
}
