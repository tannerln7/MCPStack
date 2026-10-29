"use client";

import { Plus, Trash2 } from "lucide-react";
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
  ApplicationFormValues,
  BindingKind,
  Launcher,
} from "@/lib/stack-form-model";

interface DeletionItem {
  id: string;
  label: string;
}

export function ApplicationConfigurationEditor({
  application,
  index,
  deletionItems,
  onChange,
  onDelete,
}: Readonly<{
  application: ApplicationFormValues;
  index: number;
  deletionItems: DeletionItem[];
  onChange: (application: ApplicationFormValues) => void;
  onDelete: () => void;
}>) {
  const prefix = `application-${index}`;
  const update = (patch: Partial<ApplicationFormValues>) =>
    onChange({ ...application, ...patch });
  const updateBinding = (
    bindingIndex: number,
    patch: Partial<ApplicationFormValues["bindings"][number]>,
  ) =>
    update({
      bindings: application.bindings.map((binding, current) =>
        current === bindingIndex ? { ...binding, ...patch } : binding,
      ),
    });

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-4">
        <div className="min-w-0">
          <CardTitle className="break-words">{application.name}</CardTitle>
          <CardDescription className="break-words">
            Persistent Application Component managed independently from its MCP
            bridge.
          </CardDescription>
        </div>
        <AlertDialog>
          <AlertDialogTrigger
            render={<Button type="button" variant="destructive" size="sm" />}
          >
            <Trash2 data-icon="inline-start" />
            Delete application
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                Delete {application.name || application.applicationId}?
              </AlertDialogTitle>
              <AlertDialogDescription>
                The generated candidate removes this Application and its
                unshared supporting resources. The deletion takes effect when
                the Stack configuration is saved.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="max-h-52 overflow-auto rounded-lg border bg-muted/30 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Will be removed
              </p>
              <ul className="mt-2 grid gap-1 text-sm">
                {(deletionItems.length
                  ? deletionItems
                  : [
                      {
                        id: application.componentId,
                        label: "New Application Component",
                      },
                    ]
                ).map((item) => (
                  <li key={`${item.label}-${item.id}`} className="break-words">
                    {item.label}{" "}
                    <span className="font-mono text-xs text-muted-foreground">
                      ({item.id})
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction variant="destructive" onClick={onDelete}>
                <Trash2 data-icon="inline-start" />
                Remove from candidate
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </CardHeader>
      <CardContent>
        <FieldGroup>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor={`${prefix}-name`}>
                Application name
              </FieldLabel>
              <Input
                id={`${prefix}-name`}
                required
                value={application.name}
                onChange={(event) => update({ name: event.target.value })}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor={`${prefix}-id`}>Application ID</FieldLabel>
              <Input
                id={`${prefix}-id`}
                value={application.applicationId}
                disabled
              />
            </Field>
          </div>
          <Field>
            <FieldLabel htmlFor={`${prefix}-description`}>
              Description
            </FieldLabel>
            <Input
              id={`${prefix}-description`}
              value={application.description}
              onChange={(event) => update({ description: event.target.value })}
            />
          </Field>
          <Field>
            <FieldLabel htmlFor={`${prefix}-launcher`}>Launcher</FieldLabel>
            <NativeSelect
              id={`${prefix}-launcher`}
              value={application.launcher}
              onChange={(event) =>
                update({ launcher: event.target.value as Launcher })
              }
            >
              <NativeSelectOption value="native">
                Native executable
              </NativeSelectOption>
              <NativeSelectOption value="npx">npx package</NativeSelectOption>
              <NativeSelectOption value="uvx">uvx package</NativeSelectOption>
              <NativeSelectOption value="docker">
                Docker image
              </NativeSelectOption>
            </NativeSelect>
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor={`${prefix}-executable`}>
                {application.launcher === "native"
                  ? "Executable"
                  : application.launcher === "docker"
                    ? "Image"
                    : "Package"}
              </FieldLabel>
              <Input
                id={`${prefix}-executable`}
                required
                value={application.executable}
                onChange={(event) => update({ executable: event.target.value })}
              />
            </Field>
            {application.launcher === "native" ? null : (
              <Field>
                <FieldLabel htmlFor={`${prefix}-version`}>
                  Version or tag
                </FieldLabel>
                <Input
                  id={`${prefix}-version`}
                  value={application.version}
                  onChange={(event) => update({ version: event.target.value })}
                />
              </Field>
            )}
          </div>
          <Field>
            <FieldLabel htmlFor={`${prefix}-arguments`}>Arguments</FieldLabel>
            <Textarea
              id={`${prefix}-arguments`}
              rows={5}
              value={application.arguments}
              onChange={(event) => update({ arguments: event.target.value })}
            />
            <FieldDescription>
              Each line is preserved as one argv item.
            </FieldDescription>
          </Field>
          <Field>
            <FieldLabel htmlFor={`${prefix}-working-directory`}>
              Working directory
            </FieldLabel>
            <Input
              id={`${prefix}-working-directory`}
              value={application.workingDirectory}
              onChange={(event) =>
                update({ workingDirectory: event.target.value })
              }
            />
          </Field>
          <Field className="flex-row items-start">
            <Checkbox
              id={`${prefix}-restart`}
              checked={application.restartOnFailure}
              onCheckedChange={(checked) =>
                update({ restartOnFailure: checked === true })
              }
            />
            <div>
              <FieldLabel htmlFor={`${prefix}-restart`}>
                Restart on failure
              </FieldLabel>
              <FieldDescription>
                Manual activation remains the default; boot enablement is not
                created.
              </FieldDescription>
            </div>
          </Field>

          <div className="flex flex-col gap-3 rounded-lg border p-4">
            <div>
              <p className="text-sm font-medium">Environment bindings</p>
              <p className="text-sm text-muted-foreground">
                Secret values are write-only and never load into this form.
              </p>
            </div>
            {application.bindings.map((binding, bindingIndex) => (
              <div
                key={`${binding.sourceRef || binding.name}-${bindingIndex}`}
                className="grid gap-3 rounded-lg border bg-muted/20 p-3 sm:grid-cols-2"
              >
                <Field>
                  <FieldLabel
                    htmlFor={`${prefix}-binding-${bindingIndex}-name`}
                  >
                    Variable
                  </FieldLabel>
                  <Input
                    id={`${prefix}-binding-${bindingIndex}-name`}
                    value={binding.name}
                    onChange={(event) =>
                      updateBinding(bindingIndex, { name: event.target.value })
                    }
                  />
                </Field>
                <Field>
                  <FieldLabel
                    htmlFor={`${prefix}-binding-${bindingIndex}-kind`}
                  >
                    Source
                  </FieldLabel>
                  <NativeSelect
                    id={`${prefix}-binding-${bindingIndex}-kind`}
                    value={binding.kind}
                    onChange={(event) =>
                      updateBinding(bindingIndex, {
                        kind: event.target.value as BindingKind,
                        value: "",
                        secretValue: "",
                      })
                    }
                  >
                    <NativeSelectOption value="literal">
                      Literal value
                    </NativeSelectOption>
                    <NativeSelectOption value="host">
                      Service environment
                    </NativeSelectOption>
                    <NativeSelectOption value="secret">
                      Secret slot
                    </NativeSelectOption>
                  </NativeSelect>
                </Field>
                {binding.kind === "secret" ? (
                  <>
                    <Field>
                      <FieldLabel
                        htmlFor={`${prefix}-binding-${bindingIndex}-source`}
                      >
                        Secret slot ID
                      </FieldLabel>
                      <Input
                        id={`${prefix}-binding-${bindingIndex}-source`}
                        placeholder={`${application.applicationId}-token-secret`}
                        value={binding.sourceRef || ""}
                        onChange={(event) =>
                          updateBinding(bindingIndex, {
                            sourceRef: event.target.value,
                          })
                        }
                      />
                    </Field>
                    <Field>
                      <FieldLabel
                        htmlFor={`${prefix}-binding-${bindingIndex}-value`}
                      >
                        New secret value
                      </FieldLabel>
                      <Input
                        id={`${prefix}-binding-${bindingIndex}-value`}
                        type="password"
                        autoComplete="new-password"
                        placeholder="Leave empty to keep the current value"
                        value={binding.secretValue || ""}
                        onChange={(event) =>
                          updateBinding(bindingIndex, {
                            secretValue: event.target.value,
                          })
                        }
                      />
                    </Field>
                  </>
                ) : (
                  <Field className="sm:col-span-2">
                    <FieldLabel
                      htmlFor={`${prefix}-binding-${bindingIndex}-value`}
                    >
                      {binding.kind === "host" ? "Source variable" : "Value"}
                    </FieldLabel>
                    <Input
                      id={`${prefix}-binding-${bindingIndex}-value`}
                      value={binding.value}
                      onChange={(event) =>
                        updateBinding(bindingIndex, {
                          value: event.target.value,
                        })
                      }
                    />
                  </Field>
                )}
                <div className="flex flex-wrap items-center justify-between gap-3 sm:col-span-2">
                  <label
                    htmlFor={`${prefix}-binding-${bindingIndex}-required`}
                    className="flex items-center gap-3 text-sm"
                  >
                    <Checkbox
                      id={`${prefix}-binding-${bindingIndex}-required`}
                      checked={binding.required}
                      onCheckedChange={(checked) =>
                        updateBinding(bindingIndex, {
                          required: checked === true,
                        })
                      }
                    />
                    Required
                  </label>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      update({
                        bindings: application.bindings.filter(
                          (_, current) => current !== bindingIndex,
                        ),
                      })
                    }
                  >
                    <Trash2 data-icon="inline-start" />
                    Remove binding
                  </Button>
                </div>
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              className="w-fit"
              onClick={() =>
                update({
                  bindings: [
                    ...application.bindings,
                    { name: "", kind: "host", value: "", required: true },
                  ],
                })
              }
            >
              <Plus data-icon="inline-start" />
              Add binding
            </Button>
          </div>
        </FieldGroup>
      </CardContent>
    </Card>
  );
}
