import { CircleAlert } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import type { ConfigurationDiagnostic } from "@/lib/contracts/types";

export function ValidationIssues({
  diagnostics,
  description = "Invalid sources are excluded. Other valid stacks remain available.",
}: Readonly<{
  diagnostics: ConfigurationDiagnostic[];
  description?: string;
}>) {
  if (diagnostics.length === 0) return null;
  return (
    <section aria-labelledby="configuration-issues" className="grid gap-3">
      <div>
        <h2
          id="configuration-issues"
          className="text-lg font-semibold tracking-tight"
        >
          Configuration issues
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </div>
      {diagnostics.map((diagnostic) => (
        <Alert key={diagnostic.sourcePath} variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle className="flex flex-wrap items-center gap-2">
            {diagnostic.sourcePath}
            <Badge variant="outline" className="rounded-md font-mono">
              {diagnostic.issues.length} issue
              {diagnostic.issues.length === 1 ? "" : "s"}
            </Badge>
          </AlertTitle>
          <AlertDescription>
            <ul className="mt-2 grid gap-2">
              {diagnostic.issues.map((issue, index) => (
                <li
                  key={`${issue.stage}:${issue.path}:${issue.code ?? index}`}
                  className="grid gap-1"
                >
                  <span className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline" className="rounded-md uppercase">
                      {issue.stage}
                    </Badge>
                    <code className="font-mono text-xs">{issue.path}</code>
                    {issue.line ? (
                      <span className="text-xs">
                        line {issue.line}
                        {issue.column ? `, column ${issue.column}` : ""}
                      </span>
                    ) : null}
                  </span>
                  <span>{issue.message}</span>
                </li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      ))}
    </section>
  );
}
