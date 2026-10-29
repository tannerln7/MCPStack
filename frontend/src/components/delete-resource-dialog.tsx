"use client";

import { LoaderCircle, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";

export function DeleteResourceDialog({
  title,
  description,
  items,
  endpoint,
  originalRevision,
  redirectTo,
}: Readonly<{
  title: string;
  description: string;
  items: { id: string; label: string }[];
  endpoint: string;
  originalRevision: string;
  redirectTo: string;
}>) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    setPending(true);
    setError(null);
    try {
      const response = await fetch(endpoint, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ originalRevision }),
      });
      const payload = (await response.json()) as {
        detail?: { message?: string };
      };
      if (!response.ok) {
        throw new Error(
          payload.detail?.message ?? `Deletion failed with ${response.status}`,
        );
      }
      router.push(redirectTo);
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Deletion failed",
      );
      setPending(false);
    }
  }

  return (
    <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-4">
      <div>
        <h2 className="font-semibold">Danger zone</h2>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </div>
      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      <AlertDialog>
        <AlertDialogTrigger
          render={
            <Button type="button" variant="destructive" className="w-fit" />
          }
        >
          <Trash2 data-icon="inline-start" />
          Delete
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{title}</AlertDialogTitle>
            <AlertDialogDescription>
              This cannot be undone. Managed processes are stopped before their
              configuration is removed.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="max-h-52 overflow-auto rounded-lg border bg-muted/30 p-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Will be deleted
            </p>
            <ul className="mt-2 grid gap-1 text-sm">
              {items.map((item) => (
                <li key={item.id}>
                  {item.label}{" "}
                  <span className="font-mono text-xs text-muted-foreground">
                    ({item.id})
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={pending}
              onClick={remove}
            >
              {pending ? (
                <LoaderCircle
                  data-icon="inline-start"
                  className="animate-spin"
                />
              ) : (
                <Trash2 data-icon="inline-start" />
              )}
              {pending ? "Deleting…" : "Confirm delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
