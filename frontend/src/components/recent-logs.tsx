"use client";

import { Download, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import type { RecentLogs } from "@/lib/contracts/types";

export function RecentLogsPanel({
  initialLogs,
  refreshPath,
  downloadName,
  emptyMessage = "No recent managed-component logs.",
}: Readonly<{
  initialLogs: RecentLogs | null;
  refreshPath?: string;
  downloadName: string;
  emptyMessage?: string;
}>) {
  const [logs, setLogs] = useState(initialLogs);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(
    async (showProgress = true) => {
      if (!refreshPath) return;
      if (showProgress) setRefreshing(true);
      try {
        const response = await fetch(refreshPath);
        const payload = (await response.json()) as
          | RecentLogs
          | { detail?: { message?: string } };
        if (!response.ok || !("lines" in payload)) {
          throw new Error(
            "lines" in payload
              ? `Log refresh failed with ${response.status}`
              : payload.detail?.message ||
                  `Log refresh failed with ${response.status}`,
          );
        }
        setLogs(payload);
        setError(null);
      } catch (requestError) {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Log refresh failed",
        );
      } finally {
        if (showProgress) setRefreshing(false);
      }
    },
    [refreshPath],
  );

  useEffect(() => {
    if (!refreshPath) return;
    const timer = window.setInterval(() => void refresh(false), 5_000);
    return () => window.clearInterval(timer);
  }, [refresh, refreshPath]);

  function download() {
    if (!logs?.lines.length) return;
    const blob = new Blob([`${logs.lines.join("\n")}\n`], {
      type: "text/plain;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = downloadName;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="min-w-0">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-medium">Recent logs</h3>
        <div className="flex gap-2">
          {refreshPath ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void refresh()}
              disabled={refreshing}
            >
              <RefreshCw
                data-icon="inline-start"
                className={refreshing ? "animate-spin" : undefined}
              />
              Refresh
            </Button>
          ) : null}
          {logs?.lines.length ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={download}
            >
              <Download data-icon="inline-start" />
              Download
            </Button>
          ) : null}
        </div>
      </div>
      {error ? (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {error}
        </p>
      ) : null}
      {logs?.lines.length ? (
        <pre className="mt-2 max-h-80 w-full min-w-0 max-w-full overflow-auto rounded-lg border bg-muted/30 p-3 font-mono text-xs leading-relaxed break-words whitespace-pre-wrap">
          {logs.lines.join("\n")}
        </pre>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">{emptyMessage}</p>
      )}
    </div>
  );
}
