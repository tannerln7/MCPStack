import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[70vh] max-w-lg flex-col items-start justify-center gap-4 px-6">
      <p className="text-sm font-medium text-primary">Not found</p>
      <h1 className="text-3xl font-semibold tracking-tight">
        That configured resource is missing.
      </h1>
      <p className="text-muted-foreground">
        It may have been removed from the filesystem configuration since this
        page was loaded.
      </p>
      <Button render={<Link href="/stacks" />}>Back to stacks</Button>
    </div>
  );
}
