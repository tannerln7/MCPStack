"use client";

import { useEffect } from "react";

import { ApiErrorState } from "@/components/api-error-state";
import { PageContainer } from "@/components/page-container";
import { PageHeader } from "@/components/page-header";

export default function StacksError({
  error,
  reset,
}: Readonly<{ error: Error & { digest?: string }; reset: () => void }>) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <PageContainer>
      <PageHeader eyebrow="Configured world" title="Stacks" />
      <div className="mt-8">
        <ApiErrorState reset={reset} />
      </div>
    </PageContainer>
  );
}
