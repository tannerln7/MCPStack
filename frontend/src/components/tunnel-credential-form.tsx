"use client";

import { KeyRound, LoaderCircle } from "lucide-react";
import { useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";

export function TunnelCredentialForm() {
  const [value, setValue] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    setMessage(null);
    try {
      const response = await fetch("/api/tunnel-client/credential", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ apiKey: value }),
      });
      const payload = (await response.json()) as {
        detail?: { message?: string };
      };
      if (!response.ok)
        throw new Error(
          payload.detail?.message ?? "Credential could not be stored",
        );
      setValue("");
      setMessage(
        "CONTROL_PLANE_API_KEY is configured for managed tunnel units.",
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Credential could not be stored",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="tunnel-api-key">
            Set or replace API key
          </FieldLabel>
          <Input
            id="tunnel-api-key"
            type="password"
            autoComplete="new-password"
            required
            value={value}
            onChange={(event) => setValue(event.target.value)}
          />
          <FieldDescription>
            The value is written once to a private 0600 file and is never
            returned to the browser.
          </FieldDescription>
        </Field>
        {error ? (
          <Alert variant="destructive">
            <AlertTitle>Credential update failed</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
        {message ? (
          <Alert>
            <AlertTitle>Credential updated</AlertTitle>
            <AlertDescription>{message}</AlertDescription>
          </Alert>
        ) : null}
        <Button type="submit" disabled={pending}>
          {pending ? (
            <LoaderCircle data-icon="inline-start" />
          ) : (
            <KeyRound data-icon="inline-start" />
          )}
          Store credential
        </Button>
      </FieldGroup>
    </form>
  );
}
