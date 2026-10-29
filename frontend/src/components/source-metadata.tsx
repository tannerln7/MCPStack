import { FileCode2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { ConfigurationSource } from "@/lib/contracts/types";

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  return `${(value / 1024).toFixed(1)} KiB`;
}

export function SourceMetadata({
  source,
  compact = false,
}: Readonly<{ source: ConfigurationSource; compact?: boolean }>) {
  const modified = new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(source.modifiedAt));
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
      <span className="inline-flex min-w-0 items-center gap-1.5">
        <FileCode2 aria-hidden="true" className="size-3.5 shrink-0" />
        <code className="truncate font-mono">{source.path}</code>
      </span>
      <Badge variant="outline" className="rounded-md uppercase">
        {source.format}
      </Badge>
      {compact ? null : (
        <>
          <span>{formatBytes(source.sizeBytes)}</span>
          <span>Modified {modified} UTC</span>
        </>
      )}
    </div>
  );
}
