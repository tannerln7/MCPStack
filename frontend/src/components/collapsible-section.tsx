"use client";

import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

export function CollapsibleSection({
  title,
  description,
  children,
  defaultOpen = false,
  className,
}: Readonly<{
  title: string;
  description?: string;
  children: ReactNode;
  defaultOpen?: boolean;
  className?: string;
}>) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <Collapsible open={open} onOpenChange={setOpen} className={className}>
      <div className="rounded-xl border bg-card">
        <CollapsibleTrigger
          render={
            <Button
              type="button"
              variant="ghost"
              className="h-auto min-w-0 w-full items-start justify-between gap-3 whitespace-normal rounded-xl px-4 py-4 text-left"
            />
          }
        >
          <span className="min-w-0 flex-1 overflow-hidden">
            <span className="block font-semibold tracking-tight break-words [overflow-wrap:anywhere]">
              {title}
            </span>
            {description ? (
              <span className="mt-1 block text-sm font-normal break-words text-muted-foreground [overflow-wrap:anywhere]">
                {description}
              </span>
            ) : null}
          </span>
          <ChevronDown
            aria-hidden="true"
            className={cn(
              "size-4 shrink-0 transition-transform",
              open && "rotate-180",
            )}
          />
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="border-t p-4">{children}</div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
