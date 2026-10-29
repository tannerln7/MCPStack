import { Layers3 } from "lucide-react";

import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";

export function EmptyState({
  title,
  description,
}: Readonly<{ title: string; description: string }>) {
  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia>
          <Layers3 aria-hidden="true" />
        </EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{description}</EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}
