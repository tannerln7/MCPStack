import { StatusChip } from "@/components/status-chip";
import type { ExecutionSessionObservation } from "@/lib/contracts/types";

function sessionLabel(executionId: string) {
  return `Execution ${executionId.slice(0, 8)}`;
}

export function RuntimeExecutionDetails({
  componentId,
  sessions,
}: Readonly<{
  componentId: string;
  sessions: ExecutionSessionObservation[];
}>) {
  const componentSessions = sessions.filter(
    (session) => session.componentId === componentId,
  );
  const activeCount = componentSessions.filter(
    (session) => session.state === "active",
  ).length;

  if (componentSessions.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No execution launched through <code className="font-mono">mcpctl</code>{" "}
        is currently observed. Processes started by legacy wrappers or other
        launchers are outside this observer.
      </p>
    );
  }

  return (
    <div className="grid gap-3">
      <p className="text-sm text-muted-foreground">
        {activeCount} active execution process{activeCount === 1 ? "" : "es"}.
        Process presence does not establish MCP connectivity or health.
      </p>
      <ul className="grid gap-3" aria-label="Observed executions">
        {componentSessions.map((session) => (
          <li
            key={session.executionId}
            className="grid gap-3 rounded-lg border bg-muted/20 p-4"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-mono text-sm font-medium">
                {sessionLabel(session.executionId)}
              </span>
              <StatusChip
                label={
                  session.state === "active"
                    ? "Active process"
                    : "Stale registration"
                }
                tone={session.state === "active" ? "positive" : "warning"}
              />
            </div>
            <dl className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2 text-sm">
              <dt className="text-muted-foreground">Launched</dt>
              <dd className="text-right">
                <time dateTime={session.launchedAt}>
                  {new Date(session.launchedAt).toLocaleString()}
                </time>
              </dd>
              <dt className="text-muted-foreground">Configuration</dt>
              <dd className="text-right">
                <code className="font-mono">
                  {session.configurationRevision.slice(0, 8)}
                </code>{" "}
                {session.configurationRevisionMatches ? (
                  <span className="text-status-positive">current</span>
                ) : (
                  <span className="text-status-warning">
                    changed since launch
                  </span>
                )}
              </dd>
              <dt className="text-muted-foreground">MCP identity</dt>
              <dd className="min-w-0 break-all text-right font-mono">
                {session.mcpServerRef}
              </dd>
            </dl>
            {!session.configurationIdentityMatches ? (
              <p className="text-sm text-status-warning">
                The recorded target identity no longer matches this Component.
              </p>
            ) : null}
            {session.pid ? (
              <details className="text-xs text-muted-foreground">
                <summary className="cursor-pointer select-none">
                  Technical process identity
                </summary>
                <p className="mt-2 font-mono">PID {session.pid}</p>
              </details>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
