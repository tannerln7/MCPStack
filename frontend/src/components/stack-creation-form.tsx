"use client";

import {
  CircleCheck,
  LoaderCircle,
  Plus,
  RotateCcw,
  Save,
  Trash2,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { ApplicationConfigurationEditor } from "@/components/application-configuration-editor";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
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
import { Textarea } from "@/components/ui/textarea";
import type {
  ConfigurationWriteResult,
  EditableStackSource,
} from "@/lib/contracts/types";
import {
  type ApplicationFormValues,
  applicationDeletionItems,
  applicationFormValuesFromSource,
  buildStackDocument,
  emptyStackFormValues,
  newApplicationFormValues,
  type StackFormValues,
  slug,
  stackFormValuesFromSource,
  updateApplicationConfigurations,
  updateStackDocument,
} from "@/lib/stack-form-model";

interface PreviewResult {
  valid: boolean;
  issues: Array<{ message: string; path: string }>;
}
export function StackCreationForm({
  source,
}: Readonly<{ source?: EditableStackSource }>) {
  const router = useRouter();
  const editing = source !== undefined;
  const initialValues = useMemo(
    () =>
      source
        ? stackFormValuesFromSource(source.document)
        : emptyStackFormValues,
    [source],
  );
  const [idEdited, setIdEdited] = useState(false);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [pending, setPending] = useState<"validate" | "create" | "save" | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(source?.source.revision ?? "");
  const [conflict, setConflict] = useState(false);
  const [saved, setSaved] = useState<ConfigurationWriteResult | null>(null);
  const [baseValues, setBaseValues] = useState(initialValues);
  const initialApplications = useMemo(
    () => (source ? applicationFormValuesFromSource(source.document) : []),
    [source],
  );
  const [applications, setApplications] =
    useState<ApplicationFormValues[]>(initialApplications);
  const [baseApplications, setBaseApplications] =
    useState<ApplicationFormValues[]>(initialApplications);
  const { register, control, handleSubmit, setValue, watch, reset } =
    useForm<StackFormValues>({
      defaultValues: initialValues,
    });
  const { fields, append, remove } = useFieldArray({
    control,
    name: "bindings",
  });
  const values = watch();
  const document = useMemo(() => {
    const primaryDocument = source
      ? updateStackDocument(source.document, values)
      : buildStackDocument(values);
    if (!applications.length) return primaryDocument;
    return updateApplicationConfigurations(primaryDocument, applications);
  }, [applications, source, values]);
  const [baseDocument, setBaseDocument] = useState(document);
  const secretDirty = values.bindings.some(
    (binding) => binding.kind === "secret" && binding.secretValue?.length,
  );
  const applicationSecretDirty = applications.some((application) =>
    application.bindings.some(
      (binding) => binding.kind === "secret" && binding.secretValue?.length,
    ),
  );
  const dirty =
    document !== baseDocument || secretDirty || applicationSecretDirty;

  async function storeSecrets(
    stackId: string,
    candidate: StackFormValues,
    candidateApplications: ApplicationFormValues[],
  ) {
    const bindings = [
      ...candidate.bindings.map((binding) => ({
        binding,
        defaultSourceId: `${stackId}-${slug(binding.name)}-secret`,
      })),
      ...candidateApplications.flatMap((application) =>
        application.bindings.map((binding) => ({
          binding,
          defaultSourceId: `${application.applicationId}-${slug(binding.name)}-secret`,
        })),
      ),
    ];
    for (const { binding, defaultSourceId } of bindings) {
      if (binding.kind !== "secret" || !binding.secretValue) continue;
      const sourceId = binding.sourceRef || defaultSourceId;
      const response = await fetch(
        `/api/stacks/${encodeURIComponent(stackId)}/secrets/${encodeURIComponent(sourceId)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ value: binding.secretValue }),
        },
      );
      if (!response.ok)
        throw new Error(
          `Configuration was saved, but secret slot ${sourceId} could not be stored`,
        );
    }
  }

  function candidateDocument(candidate: StackFormValues) {
    const primaryDocument = source
      ? updateStackDocument(source.document, candidate)
      : buildStackDocument(candidate);
    return applications.length
      ? updateApplicationConfigurations(primaryDocument, applications)
      : primaryDocument;
  }

  async function validate(candidate: StackFormValues) {
    setPending("validate");
    setError(null);
    try {
      const documentCandidate = candidateDocument(candidate);
      const response = await fetch(
        source
          ? `/api/stacks/${encodeURIComponent(source.stackId)}/validation-previews`
          : "/api/stacks/validation-previews",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(
            source
              ? { document: documentCandidate }
              : { stackId: candidate.id, document: documentCandidate },
          ),
        },
      );
      const payload = (await response.json()) as PreviewResult & {
        detail?: { message?: string };
      };
      if (!response.ok)
        throw new Error(
          payload.detail?.message ??
            `Validation failed with ${response.status}`,
        );
      setPreview(payload);
      return payload.valid;
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Validation failed",
      );
      return false;
    } finally {
      setPending(null);
    }
  }

  const create = handleSubmit(async (candidate) => {
    if (!(await validate(candidate))) return;
    setPending("create");
    try {
      const documentCandidate = candidateDocument(candidate);
      const response = await fetch("/api/stacks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          stackId: candidate.id,
          document: documentCandidate,
        }),
      });
      const payload = (await response.json()) as {
        detail?: { message?: string };
      };
      if (!response.ok)
        throw new Error(
          payload.detail?.message ?? `Creation failed with ${response.status}`,
        );
      await storeSecrets(candidate.id, candidate, applications);
      router.push(
        candidate.configureTunnel
          ? `/tunnels/new?stack=${encodeURIComponent(candidate.id)}`
          : `/stacks/${encodeURIComponent(candidate.id)}`,
      );
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Stack creation failed",
      );
    } finally {
      setPending(null);
    }
  });

  const save = handleSubmit(async (candidate) => {
    if (!(await validate(candidate))) return;
    setPending("save");
    setError(null);
    setConflict(false);
    setSaved(null);
    try {
      const documentCandidate = candidateDocument(candidate);
      const response = await fetch(
        `/api/stacks/${encodeURIComponent(source?.stackId ?? "")}/source`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            originalRevision: revision,
            document: documentCandidate,
          }),
        },
      );
      const payload = (await response.json()) as
        | ConfigurationWriteResult
        | { detail?: { message?: string } };
      if (response.status === 409) {
        setConflict(true);
        return;
      }
      if (!("status" in payload))
        throw new Error(
          payload.detail?.message ?? `Save failed with ${response.status}`,
        );
      if (!response.ok) throw new Error(`Save failed with ${response.status}`);
      await storeSecrets(
        source?.stackId ?? candidate.id,
        candidate,
        applications,
      );
      const cleanCandidate = {
        ...candidate,
        bindings: candidate.bindings.map((binding) => ({
          ...binding,
          secretValue: "",
        })),
      };
      const cleanApplications = applications.map((application) => ({
        ...application,
        isNew: false,
        bindings: application.bindings.map((binding) => ({
          ...binding,
          secretValue: "",
        })),
      }));
      setSaved(payload);
      setRevision(payload.source.revision);
      setBaseDocument(documentCandidate);
      setBaseValues(cleanCandidate);
      setApplications(cleanApplications);
      setBaseApplications(cleanApplications);
      reset(cleanCandidate);
      setPreview(null);
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Save failed",
      );
    } finally {
      setPending(null);
    }
  });

  return (
    <form
      onSubmit={editing ? save : create}
      className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(22rem,0.8fr)]"
    >
      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Stack identity</CardTitle>
            <CardDescription>
              One operational unit and its durable identity.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="name">Name</FieldLabel>
                <Input
                  id="name"
                  required
                  {...register("name", {
                    onChange: (event) => {
                      if (!editing && !idEdited)
                        setValue("id", slug(event.target.value));
                    },
                  })}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="id">ID</FieldLabel>
                <Input
                  id="id"
                  required
                  disabled={editing}
                  pattern="[a-z][a-z0-9-]{0,79}"
                  {...register("id", { onChange: () => setIdEdited(true) })}
                />
                <FieldDescription>
                  Used in filenames, URLs, and `mcpctl stdio` targets.
                </FieldDescription>
              </Field>
              <Field>
                <FieldLabel htmlFor="description">Description</FieldLabel>
                <Textarea id="description" {...register("description")} />
              </Field>
              <Field>
                <FieldLabel htmlFor="kind">Stack type</FieldLabel>
                <NativeSelect
                  id="kind"
                  className="w-full"
                  disabled={editing}
                  {...register("kind")}
                >
                  <NativeSelectOption value="stdio">
                    Local stdio MCP
                  </NativeSelectOption>
                  <NativeSelectOption value="http">
                    HTTP MCP endpoint
                  </NativeSelectOption>
                  <NativeSelectOption value="application">
                    Managed persistent Application
                  </NativeSelectOption>
                </NativeSelect>
              </Field>
            </FieldGroup>
          </CardContent>
        </Card>

        {values.kind === "http" ? (
          <Card>
            <CardHeader>
              <CardTitle>HTTP MCP</CardTitle>
              <CardDescription>
                An existing Streamable HTTP MCP endpoint.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="endpointUrl">Endpoint URL</FieldLabel>
                  <Input
                    id="endpointUrl"
                    type="url"
                    required={!values.endpointUrlReadOnly}
                    readOnly={values.endpointUrlReadOnly}
                    aria-describedby={
                      values.endpointUrlReadOnly
                        ? "endpointUrl-description"
                        : undefined
                    }
                    placeholder="https://example.com/mcp"
                    {...register("endpointUrl")}
                  />
                  {values.endpointUrlReadOnly ? (
                    <FieldDescription id="endpointUrl-description">
                      This address is provided by an Application or Tunnel. Edit
                      the provider configuration to change it.
                    </FieldDescription>
                  ) : null}
                </Field>
              </FieldGroup>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>
                {values.kind === "application"
                  ? "Application command"
                  : "MCP command"}
              </CardTitle>
              <CardDescription>
                The generic executable plan used by the backend.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="launcher">Launcher</FieldLabel>
                  <NativeSelect
                    id="launcher"
                    className="w-full"
                    {...register("launcher")}
                  >
                    <NativeSelectOption value="npx">
                      npx package
                    </NativeSelectOption>
                    <NativeSelectOption value="uvx">
                      uvx package
                    </NativeSelectOption>
                    <NativeSelectOption value="native">
                      Native executable
                    </NativeSelectOption>
                    <NativeSelectOption value="docker">
                      Docker image
                    </NativeSelectOption>
                  </NativeSelect>
                </Field>
                <Field>
                  <FieldLabel htmlFor="executable">
                    {values.launcher === "docker"
                      ? "Image"
                      : values.launcher === "native"
                        ? "Executable"
                        : "Package"}
                  </FieldLabel>
                  <Input
                    id="executable"
                    required
                    placeholder={
                      values.launcher === "npx"
                        ? "@scope/package"
                        : values.launcher === "docker"
                          ? "ghcr.io/org/image"
                          : "command"
                    }
                    {...register("executable")}
                  />
                </Field>
                {values.launcher !== "native" ? (
                  <Field>
                    <FieldLabel htmlFor="version">Version or tag</FieldLabel>
                    <Input
                      id="version"
                      placeholder="Optional but recommended"
                      {...register("version")}
                    />
                  </Field>
                ) : null}
                <Field>
                  <FieldLabel htmlFor="arguments">Arguments</FieldLabel>
                  <Textarea
                    id="arguments"
                    placeholder="One argument per line"
                    {...register("arguments")}
                  />
                  <FieldDescription>
                    Each line is preserved as one argv item.
                  </FieldDescription>
                </Field>
                <Field>
                  <FieldLabel htmlFor="workingDirectory">
                    Working directory
                  </FieldLabel>
                  <Input
                    id="workingDirectory"
                    placeholder="Optional"
                    {...register("workingDirectory")}
                  />
                </Field>
                {values.kind === "application" ? (
                  <Field>
                    <label
                      htmlFor="restart-on-failure"
                      className="flex items-center gap-3 text-sm font-medium"
                    >
                      <Checkbox
                        id="restart-on-failure"
                        checked={values.restartOnFailure}
                        onCheckedChange={(checked) =>
                          setValue("restartOnFailure", checked === true)
                        }
                      />
                      Restart on failure
                    </label>
                    <FieldDescription>
                      Manual activation remains the default; boot enablement is
                      not created.
                    </FieldDescription>
                  </Field>
                ) : null}
              </FieldGroup>
            </CardContent>
          </Card>
        )}

        {values.kind !== "http" ? (
          <Card>
            <CardHeader>
              <CardTitle>Environment bindings</CardTitle>
              <CardDescription>
                Bind literals, inherited variables, or service-owned write-only
                secret slots. Stored secret values are never returned to this
                form.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              {fields.map((field, index) => (
                <div
                  key={field.id}
                  className="grid gap-3 rounded-lg border p-4 sm:grid-cols-2"
                >
                  <Field>
                    <FieldLabel htmlFor={`binding-name-${index}`}>
                      Target variable
                    </FieldLabel>
                    <Input
                      id={`binding-name-${index}`}
                      {...register(`bindings.${index}.name`)}
                    />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor={`binding-kind-${index}`}>
                      Source
                    </FieldLabel>
                    <NativeSelect
                      id={`binding-kind-${index}`}
                      className="w-full"
                      {...register(`bindings.${index}.kind`)}
                    >
                      <NativeSelectOption value="literal">
                        Literal
                      </NativeSelectOption>
                      <NativeSelectOption value="host">
                        Host variable
                      </NativeSelectOption>
                      <NativeSelectOption value="secret">
                        Stored secret
                      </NativeSelectOption>
                    </NativeSelect>
                  </Field>
                  {values.bindings[index]?.kind === "secret" ? (
                    <>
                      <Field>
                        <FieldLabel htmlFor={`binding-source-${index}`}>
                          Secret slot ID
                        </FieldLabel>
                        <Input
                          id={`binding-source-${index}`}
                          placeholder={`${values.id || "stack"}-token-secret`}
                          {...register(`bindings.${index}.sourceRef`)}
                        />
                      </Field>
                      <Field>
                        <FieldLabel htmlFor={`binding-secret-${index}`}>
                          {editing ? "Replace secret value" : "Secret value"}
                        </FieldLabel>
                        <Input
                          id={`binding-secret-${index}`}
                          type="password"
                          autoComplete="new-password"
                          placeholder={
                            editing
                              ? "Leave empty to keep current value"
                              : "Enter later if preferred"
                          }
                          {...register(`bindings.${index}.secretValue`)}
                        />
                      </Field>
                    </>
                  ) : (
                    <Field className="sm:col-span-2">
                      <FieldLabel htmlFor={`binding-value-${index}`}>
                        {values.bindings[index]?.kind === "host"
                          ? "Source variable"
                          : "Value"}
                      </FieldLabel>
                      <Input
                        id={`binding-value-${index}`}
                        {...register(`bindings.${index}.value`)}
                      />
                    </Field>
                  )}
                  <div className="flex items-center justify-between gap-3 sm:col-span-2">
                    <label
                      htmlFor={`binding-required-${index}`}
                      className="flex items-center gap-3 text-sm"
                    >
                      <Checkbox
                        id={`binding-required-${index}`}
                        checked={values.bindings[index]?.required}
                        onCheckedChange={(checked) =>
                          setValue(
                            `bindings.${index}.required`,
                            checked === true,
                          )
                        }
                      />
                      Required
                    </label>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => remove(index)}
                    >
                      <Trash2 data-icon="inline-start" />
                      Remove
                    </Button>
                  </div>
                </div>
              ))}
              <Button
                type="button"
                variant="outline"
                onClick={() =>
                  append({ name: "", kind: "host", value: "", required: true })
                }
              >
                <Plus data-icon="inline-start" />
                Add binding
              </Button>
            </CardContent>
          </Card>
        ) : null}

        <section className="grid gap-4" aria-labelledby="applications-heading">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 id="applications-heading" className="text-lg font-semibold">
                Attached applications
              </h2>
              <p className="text-sm text-muted-foreground">
                Long-lived services used by this Stack. Each Application is
                managed independently from the primary Component.
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              disabled={!values.id}
              onClick={() =>
                setApplications((current) => [
                  ...current,
                  newApplicationFormValues(values.id, current),
                ])
              }
            >
              <Plus data-icon="inline-start" />
              Add application
            </Button>
          </div>
          {applications.length ? (
            applications.map((application, index) => (
              <ApplicationConfigurationEditor
                key={application.componentId}
                application={application}
                index={index}
                deletionItems={
                  application.isNew || !source
                    ? []
                    : applicationDeletionItems(
                        source.document,
                        application.componentId,
                      )
                }
                onChange={(nextApplication) =>
                  setApplications((current) =>
                    current.map((item, currentIndex) =>
                      currentIndex === index ? nextApplication : item,
                    ),
                  )
                }
                onDelete={() =>
                  setApplications((current) =>
                    current.filter((_, currentIndex) => currentIndex !== index),
                  )
                }
              />
            ))
          ) : (
            <Card>
              <CardContent className="py-6 text-sm text-muted-foreground">
                {values.id
                  ? "No attached Applications. Add one when this Stack depends on a persistent local service."
                  : "Enter the Stack name and ID before adding an attached Application."}
              </CardContent>
            </Card>
          )}
        </section>

        {!editing && values.kind !== "application" ? (
          <Card>
            <CardContent>
              <label
                htmlFor="configure-tunnel"
                className="flex items-start gap-3"
              >
                <Checkbox
                  id="configure-tunnel"
                  checked={values.configureTunnel}
                  onCheckedChange={(checked) =>
                    setValue("configureTunnel", checked === true)
                  }
                />
                <span>
                  <span className="block text-sm font-medium">
                    Configure an OpenAI remote tunnel next
                  </span>
                  <span className="mt-1 block text-sm text-muted-foreground">
                    The Stack is created first and remains inactive. The tunnel
                    profile wizard opens afterward.
                  </span>
                </span>
              </label>
            </CardContent>
          </Card>
        ) : null}
      </div>

      <div className="grid content-start gap-4 xl:sticky xl:top-6">
        <Card>
          <CardHeader>
            <CardTitle>Generated configuration</CardTitle>
            <CardDescription>
              {editing
                ? "Field changes update the primary Component while preserving advanced and unrelated Stack sections."
                : "The complete YAML source that will become filesystem authority."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="max-h-[32rem] overflow-auto rounded-lg border bg-muted/30 p-3 font-mono text-xs whitespace-pre-wrap">
              {document}
            </pre>
          </CardContent>
        </Card>
        {preview ? (
          <Alert variant={preview.valid ? "default" : "destructive"}>
            <AlertTitle>
              {preview.valid
                ? "Configuration is valid"
                : "Configuration needs attention"}
            </AlertTitle>
            <AlertDescription>
              {preview.valid
                ? "Schema and domain validation passed."
                : preview.issues
                    .map((issue) => `${issue.path}: ${issue.message}`)
                    .join("; ")}
            </AlertDescription>
          </Alert>
        ) : null}
        {error ? (
          <Alert variant="destructive">
            <AlertTitle>
              {editing
                ? "Configuration operation failed"
                : "Stack could not be created"}
            </AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
        {conflict ? (
          <Alert variant="destructive">
            <AlertTitle>Configuration changed on disk</AlertTitle>
            <AlertDescription className="flex flex-wrap items-center gap-3">
              Reload before saving so a newer source is never overwritten.
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => window.location.reload()}
              >
                Reload source
              </Button>
            </AlertDescription>
          </Alert>
        ) : null}
        {saved ? (
          <Alert>
            <CircleCheck aria-hidden="true" />
            <AlertTitle>Configuration saved</AlertTitle>
            <AlertDescription>
              Revision <code>{saved.source.revision.slice(0, 12)}</code> is now
              filesystem authority.
            </AlertDescription>
          </Alert>
        ) : null}
        <div className="flex flex-wrap gap-3">
          <Button
            type="button"
            variant="outline"
            disabled={pending !== null}
            onClick={handleSubmit(validate)}
          >
            {pending === "validate" ? (
              <LoaderCircle data-icon="inline-start" />
            ) : null}
            Validate
          </Button>
          <Button
            type="submit"
            disabled={pending !== null || (editing && !dirty)}
          >
            {pending === "create" || pending === "save" ? (
              <LoaderCircle data-icon="inline-start" />
            ) : editing ? (
              <Save data-icon="inline-start" />
            ) : (
              <Plus data-icon="inline-start" />
            )}
            {editing ? "Save configuration" : "Create Stack"}
          </Button>
          {editing ? (
            <Button
              type="button"
              variant="outline"
              disabled={pending !== null || !dirty}
              onClick={() => {
                reset(baseValues);
                setApplications(baseApplications);
                setPreview(null);
                setError(null);
                setSaved(null);
              }}
            >
              <RotateCcw data-icon="inline-start" />
              Discard
            </Button>
          ) : null}
          {editing ? (
            <span
              className="self-center text-sm text-muted-foreground"
              aria-live="polite"
            >
              {dirty ? "Unsaved changes" : `Revision ${revision.slice(0, 12)}`}
            </span>
          ) : null}
        </div>
      </div>
    </form>
  );
}
