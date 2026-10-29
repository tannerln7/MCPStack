import type * as React from "react";

import { cn } from "@/lib/utils";

function FieldGroup({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="field-group"
      className={cn("flex flex-col gap-6", className)}
      {...props}
    />
  );
}

function Field({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="field"
      className={cn("flex flex-col gap-2", className)}
      {...props}
    />
  );
}

function FieldLabel({
  className,
  children,
  htmlFor,
  ...props
}: React.ComponentProps<"label"> & { htmlFor: string }) {
  return (
    <label
      data-slot="field-label"
      htmlFor={htmlFor}
      className={cn("text-sm font-medium leading-none", className)}
      {...props}
    >
      {children}
    </label>
  );
}

function FieldDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      data-slot="field-description"
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  );
}

export { Field, FieldDescription, FieldGroup, FieldLabel };
