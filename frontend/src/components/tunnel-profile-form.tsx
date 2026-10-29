"use client";

import { LoaderCircle, RadioTower } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";
import type { StackSummary, TunnelProfile } from "@/lib/contracts/types";

interface FormValues {
  id: string;
  tunnelId: string;
  targetKind: "stdio" | "http";
  stackTarget: string;
  url: string;
  channel: string;
  baseUrl: string;
  healthListenAddr: string;
}

const slug = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);

export function TunnelProfileForm({
  stacks,
  initialProfile,
}: Readonly<{ stacks: StackSummary[]; initialProfile?: TunnelProfile }>) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const commandTarget = initialProfile?.target?.command
    ?.trim()
    .split(/\s+/)
    .at(-1);
  const initialStack =
    commandTarget ?? searchParams.get("stack") ?? stacks[0]?.id ?? "";
  const editing = Boolean(initialProfile);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, watch, setValue } = useForm<FormValues>({
    defaultValues: {
      id: initialProfile?.id ?? (initialStack ? `${initialStack}-tunnel` : ""),
      tunnelId: initialProfile?.tunnelId ?? "",
      targetKind: initialProfile?.target?.kind ?? "stdio",
      stackTarget: initialStack,
      url: initialProfile?.target?.url ?? "",
      channel: initialProfile?.target?.channel ?? "main",
      baseUrl: initialProfile?.baseUrl ?? "https://api.openai.com",
      healthListenAddr: initialProfile?.healthListenAddr ?? "127.0.0.1:0",
    },
  });
  const values = watch();
  const submit = handleSubmit(async (candidate) => {
    setPending(true);
    setError(null);
    try {
      const endpoint = editing
        ? `/api/tunnel-profiles/${encodeURIComponent(initialProfile?.id ?? "")}`
        : "/api/tunnel-profiles";
      const response = await fetch(endpoint, {
        method: editing ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...candidate,
          stackTarget:
            candidate.targetKind === "stdio" ? candidate.stackTarget : null,
          url: candidate.targetKind === "http" ? candidate.url : null,
          restart: "on-failure",
          ...(editing ? { originalRevision: initialProfile?.revision } : {}),
        }),
      });
      const payload = (await response.json()) as {
        id?: string;
        detail?: { message?: string };
      };
      if (!response.ok)
        throw new Error(
          payload.detail?.message ??
            `Profile creation failed with ${response.status}`,
        );
      router.push(editing ? `/tunnels/${candidate.id}` : "/tunnels");
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : `Tunnel profile ${editing ? "update" : "creation"} failed`,
      );
    } finally {
      setPending(false);
    }
  });

  return (
    <form onSubmit={submit} className="mt-8 grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Profile identity</CardTitle>
          <CardDescription>
            The profile remains authoritative in the tunnel-client configuration
            directory.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="profile-id">Profile name</FieldLabel>
              <Input
                id="profile-id"
                required
                pattern="[a-z][a-z0-9-]{0,79}"
                disabled={editing}
                {...register("id")}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="tunnel-id">OpenAI tunnel ID</FieldLabel>
              <Input
                id="tunnel-id"
                required
                placeholder="tunnel_…"
                {...register("tunnelId", {
                  onChange: (event) => {
                    if (!values.id) setValue("id", slug(event.target.value));
                  },
                })}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="channel">Channel</FieldLabel>
              <Input id="channel" required {...register("channel")} />
            </Field>
          </FieldGroup>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Target</CardTitle>
          <CardDescription>
            Expose a configured stdio MCP through mcpctl or an existing HTTP MCP
            URL.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="target-kind">Target type</FieldLabel>
              <NativeSelect
                id="target-kind"
                className="w-full"
                {...register("targetKind")}
              >
                <NativeSelectOption value="stdio">
                  Configured Stack MCP
                </NativeSelectOption>
                <NativeSelectOption value="http">
                  HTTP MCP URL
                </NativeSelectOption>
              </NativeSelect>
            </Field>
            {values.targetKind === "stdio" ? (
              <Field>
                <FieldLabel htmlFor="stack-target">Stack</FieldLabel>
                <NativeSelect
                  id="stack-target"
                  className="w-full"
                  required
                  {...register("stackTarget")}
                >
                  <NativeSelectOption value="">
                    Select a Stack
                  </NativeSelectOption>
                  {stacks.map((stack) => (
                    <NativeSelectOption key={stack.id} value={stack.id}>
                      {stack.name}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
                <FieldDescription>
                  Profiles launch `mcpctl stdio &lt;stack&gt;`; Stack
                  configuration remains authoritative.
                </FieldDescription>
              </Field>
            ) : (
              <Field>
                <FieldLabel htmlFor="target-url">HTTP MCP URL</FieldLabel>
                <Input
                  id="target-url"
                  type="url"
                  required
                  {...register("url")}
                />
              </Field>
            )}
            <Field>
              <FieldLabel htmlFor="base-url">OpenAI tunnel API URL</FieldLabel>
              <Input
                id="base-url"
                type="url"
                required
                {...register("baseUrl")}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="health-listen">Health listener</FieldLabel>
              <Input
                id="health-listen"
                required
                {...register("healthListenAddr")}
              />
              <FieldDescription>
                Loopback port 0 avoids collisions between profiles.
              </FieldDescription>
            </Field>
          </FieldGroup>
        </CardContent>
      </Card>
      {error ? (
        <Alert variant="destructive" className="lg:col-span-2">
          <AlertTitle>
            Profile could not be {editing ? "updated" : "created"}
          </AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      <div className="lg:col-span-2">
        <Button type="submit" disabled={pending}>
          {pending ? (
            <LoaderCircle data-icon="inline-start" />
          ) : (
            <RadioTower data-icon="inline-start" />
          )}
          {editing ? "Save tunnel profile" : "Create tunnel profile"}
        </Button>
      </div>
    </form>
  );
}
