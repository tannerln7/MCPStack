"use client";

import { CircleX, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";

export function ApiErrorState({ reset }: Readonly<{ reset: () => void }>) {
  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia>
          <CircleX aria-hidden="true" />
        </EmptyMedia>
        <EmptyTitle>MCPStack API unavailable</EmptyTitle>
        <EmptyDescription>
          The frontend could not load the configured filesystem sources. Check
          that the local backend is running, then retry.
        </EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button type="button" variant="outline" onClick={reset}>
          <RefreshCw data-icon="inline-start" />
          Retry
        </Button>
      </EmptyContent>
    </Empty>
  );
}
