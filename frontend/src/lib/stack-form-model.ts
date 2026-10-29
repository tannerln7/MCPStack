import { parseDocument } from "yaml";

export type StackKind = "stdio" | "http" | "application";
export type Launcher = "npx" | "uvx" | "native" | "docker";
export type BindingKind = "literal" | "host" | "secret";

export interface StackFormValues {
  name: string;
  id: string;
  description: string;
  kind: StackKind;
  launcher: Launcher;
  executable: string;
  version: string;
  arguments: string;
  workingDirectory: string;
  endpointUrl: string;
  endpointUrlReadOnly: boolean;
  listenerPort: number;
  listenerPath: string;
  restartOnFailure: boolean;
  configureTunnel: boolean;
  bindings: Array<{
    name: string;
    kind: BindingKind;
    value: string;
    required: boolean;
    sourceRef?: string;
    secretValue?: string;
  }>;
}

export interface ApplicationFormValues {
  componentId: string;
  applicationId: string;
  commandId: string;
  lifecyclePolicyId: string;
  runtimeRef: string;
  name: string;
  description: string;
  launcher: Launcher;
  executable: string;
  version: string;
  arguments: string;
  workingDirectory: string;
  restartOnFailure: boolean;
  bindings: StackFormValues["bindings"];
  isNew: boolean;
}

type RecordValue = Record<string, unknown>;

export const emptyStackFormValues: StackFormValues = {
  name: "",
  id: "",
  description: "",
  kind: "stdio",
  launcher: "npx",
  executable: "",
  version: "",
  arguments: "",
  workingDirectory: "",
  endpointUrl: "",
  endpointUrlReadOnly: false,
  listenerPort: 8080,
  listenerPath: "/",
  restartOnFailure: true,
  configureTunnel: false,
  bindings: [],
};

export const slug = (value: string) =>
  value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);

const quote = (value: string) => JSON.stringify(value);

function yamlList(values: string[], indent: string) {
  return values.map((value) => `${indent}- ${quote(value)}`).join("\n");
}

function isRecord(value: unknown): value is RecordValue {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function records(value: unknown): RecordValue[] {
  return Array.isArray(value) ? value.filter(isRecord) : [];
}

function stringValue(value: unknown) {
  return typeof value === "string" ? value : "";
}

function findById(values: unknown, id: string) {
  return records(values).find((value) => value.id === id);
}

function splitVersion(value: string, delimiter: "@" | "==") {
  if (delimiter === "==") {
    const index = value.lastIndexOf(delimiter);
    return index > 0
      ? [value.slice(0, index), value.slice(index + delimiter.length)]
      : [value, ""];
  }
  const index = value.lastIndexOf(delimiter);
  return index > 0
    ? [value.slice(0, index), value.slice(index + 1)]
    : [value, ""];
}

export function resolveCommand(values: StackFormValues) {
  let executable = values.executable.trim();
  let args = values.arguments
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
  if (values.launcher === "npx") {
    executable = "npx";
    args = [
      "-y",
      values.version
        ? `${values.executable}@${values.version}`
        : values.executable,
      ...args,
    ];
  } else if (values.launcher === "uvx") {
    executable = "uvx";
    args = [
      values.version
        ? `${values.executable}==${values.version}`
        : values.executable,
      ...args,
    ];
  } else if (values.launcher === "docker") {
    executable = "docker";
    args = [
      "run",
      "--rm",
      "-i",
      values.version
        ? `${values.executable}:${values.version}`
        : values.executable,
      ...args,
    ];
  }
  return {
    executable,
    executableDefinition:
      executable.includes("/") || executable.startsWith("~")
        ? { kind: "local-path", path: executable }
        : { kind: "path-name", name: executable },
    args,
  };
}

export function buildStackDocument(values: StackFormValues) {
  const id = values.id;
  const componentId = `${id}-component`;
  const lines = [
    'modelVersion: "0.1"',
    `id: ${id}`,
    `name: ${quote(values.name)}`,
  ];
  if (values.description.trim())
    lines.push(`description: ${quote(values.description.trim())}`);

  if (values.kind === "http") {
    lines.push(
      "",
      "endpoints:",
      `  - id: ${id}-endpoint`,
      "    origin: configured",
      `    url: ${quote(values.endpointUrl)}`,
      "",
      "transports:",
      `  - id: ${id}-http`,
      "    kind: streamable-http",
      `    endpointRef: ${id}-endpoint`,
      "",
      "mcpServers:",
      `  - id: ${id}-mcp`,
      `    name: ${quote(values.name)}`,
      `    transportRef: ${id}-http`,
      "",
      "components:",
      `  - id: ${componentId}`,
      `    name: ${quote(values.name)}`,
      "    enabled: true",
      "    subject:",
      `      mcpServerRef: ${id}-mcp`,
    );
    return `${lines.join("\n")}\n`;
  }

  const command = resolveCommand(values);
  const executableKind = command.executableDefinition.kind;
  lines.push(
    "",
    "runtimes:",
    `  - id: ${id}-runtime`,
    "    kind: host",
    "",
    "commands:",
    `  - id: ${id}-command`,
    `    runtimeRef: ${id}-runtime`,
    "    executable:",
    `      kind: ${executableKind}`,
    `      ${executableKind === "local-path" ? "path" : "name"}: ${quote(command.executable)}`,
    "    args:",
    command.args.length ? yamlList(command.args, "      ") : "      []",
  );
  if (values.workingDirectory.trim())
    lines.push(
      `    workingDirectory: ${quote(values.workingDirectory.trim())}`,
    );

  const environmentSources = values.bindings.filter(
    (item) => item.kind === "host" && item.name && item.value,
  );
  const secretSources = values.bindings.filter(
    (item) => item.kind === "secret" && item.name,
  );
  if (environmentSources.length) {
    lines.push("", "environmentSources:");
    for (const item of environmentSources) {
      lines.push(
        `  - id: ${id}-${slug(item.name)}-environment`,
        "    kind: host-environment",
        `    variable: ${quote(item.value)}`,
      );
    }
  }
  if (secretSources.length) {
    lines.push("", "secretSources:");
    for (const item of secretSources) {
      lines.push(
        `  - id: ${item.sourceRef || `${id}-${slug(item.name)}-secret`}`,
        "    kind: secret-reference",
        "    provider: control-plane-store",
      );
    }
  }
  const bindings = values.bindings.filter(
    (item) => item.name && (item.kind === "secret" || item.value),
  );
  if (bindings.length) {
    const commandIndex = lines.indexOf("    args:");
    let insertAt = commandIndex + 2;
    while (insertAt < lines.length && lines[insertAt].startsWith("      - "))
      insertAt += 1;
    if (values.workingDirectory.trim()) insertAt += 1;
    const environmentLines = ["    environment:"];
    for (const item of bindings) {
      environmentLines.push(
        `      - name: ${quote(item.name)}`,
        "        valueFrom:",
      );
      if (item.kind === "literal")
        environmentLines.push(`          literal: ${quote(item.value)}`);
      if (item.kind === "host")
        environmentLines.push(
          `          environmentSourceRef: ${id}-${slug(item.name)}-environment`,
        );
      if (item.kind === "secret")
        environmentLines.push(
          `          secretSourceRef: ${item.sourceRef || `${id}-${slug(item.name)}-secret`}`,
        );
      environmentLines.push(
        `        required: ${item.required ? "true" : "false"}`,
      );
    }
    lines.splice(insertAt, 0, ...environmentLines);
  }

  if (values.kind === "application") {
    lines.push(
      "",
      "applications:",
      `  - id: ${id}-application`,
      `    name: ${quote(values.name)}`,
      `    processCommandRef: ${id}-command`,
      "",
      "lifecyclePolicies:",
      `  - id: ${id}-managed`,
      "    ownership: control-plane-managed",
      "    activation: persistent",
      "    provider: system-service",
      `    restart: ${values.restartOnFailure ? "on-failure" : "never"}`,
      "    stopTimeoutSeconds: 20",
      "",
      "components:",
      `  - id: ${componentId}`,
      `    name: ${quote(values.name)}`,
      "    enabled: true",
      "    subject:",
      `      applicationRef: ${id}-application`,
      `    lifecyclePolicyRef: ${id}-managed`,
    );
  } else {
    lines.push(
      "",
      "transports:",
      `  - id: ${id}-stdio`,
      "    kind: stdio",
      `    commandRef: ${id}-command`,
      "",
      "mcpServers:",
      `  - id: ${id}-mcp`,
      `    name: ${quote(values.name)}`,
      `    transportRef: ${id}-stdio`,
      "",
      "lifecyclePolicies:",
      `  - id: ${id}-session`,
      "    ownership: session-owned",
      "    activation: on-demand",
      "    provider: direct-child",
      "    restart: never",
      "",
      "components:",
      `  - id: ${componentId}`,
      `    name: ${quote(values.name)}`,
      "    enabled: true",
      "    subject:",
      `      mcpServerRef: ${id}-mcp`,
      `    lifecyclePolicyRef: ${id}-session`,
    );
  }
  return `${lines.join("\n")}\n`;
}

interface EditContext {
  configuration: RecordValue;
  primaryComponentId: string;
  primaryMcpServerId: string | null;
  commandIndex: number | null;
  endpointIndex: number | null;
  lifecycleIndex: number | null;
}

function editContext(source: string): EditContext {
  const document = parseDocument(source);
  if (document.errors.length)
    throw new Error("The existing Stack YAML could not be parsed");
  const configuration = document.toJS() as unknown;
  if (!isRecord(configuration))
    throw new Error("The existing Stack document is not an object");
  const components = records(configuration.components);
  const primary =
    components.find((component) => {
      const subject = isRecord(component.subject) ? component.subject : {};
      return typeof subject.mcpServerRef === "string";
    }) ?? components[0];
  if (!primary)
    throw new Error("The existing Stack does not contain a Component");
  const subject = isRecord(primary.subject) ? primary.subject : {};
  let commandId = "";
  let endpointId = "";
  if (typeof subject.applicationRef === "string") {
    const application = findById(
      configuration.applications,
      subject.applicationRef,
    );
    commandId = stringValue(application?.processCommandRef);
  } else if (typeof subject.mcpServerRef === "string") {
    const mcpServer = findById(configuration.mcpServers, subject.mcpServerRef);
    const transport = findById(
      configuration.transports,
      stringValue(mcpServer?.transportRef),
    );
    commandId = stringValue(transport?.commandRef);
    endpointId = stringValue(transport?.endpointRef);
  }
  const commandIndex = records(configuration.commands).findIndex(
    (item) => item.id === commandId,
  );
  const endpointIndex = records(configuration.endpoints).findIndex(
    (item) => item.id === endpointId,
  );
  const lifecycleIndex = records(configuration.lifecyclePolicies).findIndex(
    (item) => item.id === primary.lifecyclePolicyRef,
  );
  return {
    configuration,
    primaryComponentId: stringValue(primary.id),
    primaryMcpServerId:
      typeof subject.mcpServerRef === "string" ? subject.mcpServerRef : null,
    commandIndex: commandIndex < 0 ? null : commandIndex,
    endpointIndex: endpointIndex < 0 ? null : endpointIndex,
    lifecycleIndex: lifecycleIndex < 0 ? null : lifecycleIndex,
  };
}

function commandFields(command: RecordValue | undefined) {
  const executableDefinition = isRecord(command?.executable)
    ? command.executable
    : {};
  const executable = stringValue(
    executableDefinition.name || executableDefinition.path,
  );
  let launcher: Launcher = "native";
  let packageOrExecutable = executable;
  let version = "";
  let args = Array.isArray(command?.args)
    ? command.args.filter((value): value is string => typeof value === "string")
    : [];
  if (executable === "npx" && args[0] === "-y" && args[1]) {
    launcher = "npx";
    [packageOrExecutable, version] = splitVersion(args[1], "@");
    args = args.slice(2);
  } else if (executable === "uvx" && args[0]) {
    launcher = "uvx";
    [packageOrExecutable, version] = splitVersion(args[0], "==");
    args = args.slice(1);
  } else if (
    executable === "docker" &&
    args[0] === "run" &&
    args[1] === "--rm" &&
    args[2] === "-i" &&
    args[3]
  ) {
    launcher = "docker";
    const image = args[3];
    const separator = image.lastIndexOf(":");
    const slash = image.lastIndexOf("/");
    if (separator > slash) {
      packageOrExecutable = image.slice(0, separator);
      version = image.slice(separator + 1);
    } else packageOrExecutable = image;
    args = args.slice(4);
  }
  return { launcher, packageOrExecutable, version, args };
}

function bindingsFromCommand(
  configuration: RecordValue,
  command: RecordValue | undefined,
) {
  const environmentSources = new Map(
    records(configuration.environmentSources).map((item) => [item.id, item]),
  );
  return records(command?.environment).map((binding) => {
    const valueFrom = isRecord(binding.valueFrom) ? binding.valueFrom : {};
    if (typeof valueFrom.environmentSourceRef === "string") {
      const sourceDefinition = environmentSources.get(
        valueFrom.environmentSourceRef,
      );
      return {
        name: stringValue(binding.name),
        kind: "host" as const,
        value: stringValue(sourceDefinition?.variable),
        required: binding.required !== false,
        sourceRef: valueFrom.environmentSourceRef,
      };
    }
    if (typeof valueFrom.secretSourceRef === "string") {
      return {
        name: stringValue(binding.name),
        kind: "secret" as const,
        value: "",
        required: binding.required !== false,
        sourceRef: valueFrom.secretSourceRef,
        secretValue: "",
      };
    }
    return {
      name: stringValue(binding.name),
      kind: "literal" as const,
      value: stringValue(valueFrom.literal),
      required: binding.required !== false,
    };
  });
}

function endpointDisplayUrl(endpoint: RecordValue | undefined): string {
  if (endpoint?.origin !== "application-provided")
    return stringValue(endpoint?.url);
  const listener = isRecord(endpoint.listener) ? endpoint.listener : {};
  const host = stringValue(listener.host);
  const authorityHost =
    host.includes(":") && !host.startsWith("[") ? `[${host}]` : host;
  return `${stringValue(listener.scheme)}://${authorityHost}:${listener.port}${stringValue(listener.path)}`;
}

export function stackFormValuesFromSource(source: string): StackFormValues {
  const context = editContext(source);
  const configuration = context.configuration;
  const command =
    context.commandIndex === null
      ? undefined
      : records(configuration.commands)[context.commandIndex];
  const endpoint =
    context.endpointIndex === null
      ? undefined
      : records(configuration.endpoints)[context.endpointIndex];
  const components = records(configuration.components);
  const primary = components.find(
    (component) => component.id === context.primaryComponentId,
  );
  const subject = isRecord(primary?.subject) ? primary.subject : {};
  const kind: StackKind =
    typeof subject.applicationRef === "string"
      ? "application"
      : endpoint
        ? "http"
        : "stdio";
  const { launcher, packageOrExecutable, version, args } =
    commandFields(command);
  const bindings = bindingsFromCommand(configuration, command);
  const lifecycle =
    context.lifecycleIndex === null
      ? undefined
      : records(configuration.lifecyclePolicies)[context.lifecycleIndex];
  return {
    ...emptyStackFormValues,
    id: stringValue(configuration.id),
    name: stringValue(configuration.name),
    description: stringValue(configuration.description),
    kind,
    launcher,
    executable: packageOrExecutable,
    version,
    arguments: args.join("\n"),
    workingDirectory: stringValue(command?.workingDirectory),
    endpointUrl: endpointDisplayUrl(endpoint),
    endpointUrlReadOnly:
      endpoint !== undefined && endpoint.origin !== "configured",
    restartOnFailure: lifecycle?.restart === "on-failure",
    bindings,
  };
}

export function applicationFormValuesFromSource(
  source: string,
): ApplicationFormValues[] {
  const context = editContext(source);
  const configuration = context.configuration;
  const commands = records(configuration.commands);
  const lifecyclePolicies = records(configuration.lifecyclePolicies);
  return records(configuration.components).flatMap((component) => {
    if (component.id === context.primaryComponentId) return [];
    const subject = isRecord(component.subject) ? component.subject : {};
    if (typeof subject.applicationRef !== "string") return [];
    const application = findById(
      configuration.applications,
      subject.applicationRef,
    );
    if (!application) return [];
    const commandId = stringValue(application.processCommandRef);
    const command = commands.find((item) => item.id === commandId);
    if (!command) return [];
    const lifecyclePolicyId = stringValue(component.lifecyclePolicyRef);
    const lifecycle = lifecyclePolicies.find(
      (item) => item.id === lifecyclePolicyId,
    );
    const fields = commandFields(command);
    return [
      {
        componentId: stringValue(component.id),
        applicationId: stringValue(application.id),
        commandId,
        lifecyclePolicyId,
        runtimeRef: stringValue(command.runtimeRef),
        name: stringValue(application.name || component.name),
        description: stringValue(component.description),
        launcher: fields.launcher,
        executable: fields.packageOrExecutable,
        version: fields.version,
        arguments: fields.args.join("\n"),
        workingDirectory: stringValue(command.workingDirectory),
        restartOnFailure: lifecycle?.restart === "on-failure",
        bindings: bindingsFromCommand(configuration, command),
        isNew: false,
      },
    ];
  });
}

export function newApplicationFormValues(
  stackId: string,
  existing: ApplicationFormValues[],
): ApplicationFormValues {
  let suffix = existing.length + 1;
  let id = `${stackId}-application-${suffix}`;
  const used = new Set(existing.map((item) => item.applicationId));
  while (used.has(id)) {
    suffix += 1;
    id = `${stackId}-application-${suffix}`;
  }
  return {
    componentId: `${id}-component`,
    applicationId: id,
    commandId: `${id}-command`,
    lifecyclePolicyId: `${id}-managed`,
    runtimeRef: `${stackId}-runtime`,
    name: "New application",
    description: "",
    launcher: "native",
    executable: "",
    version: "",
    arguments: "",
    workingDirectory: "",
    restartOnFailure: true,
    bindings: [],
    isNew: true,
  };
}

export function updateStackDocument(source: string, values: StackFormValues) {
  const context = editContext(source);
  const document = parseDocument(source);
  document.set("name", values.name);
  if (values.description.trim())
    document.set("description", values.description.trim());
  else document.delete("description");

  // Only configured endpoints own a URL. Provider-owned endpoints retain their
  // discriminated representation, regardless of any submitted display value.
  if (
    context.endpointIndex !== null &&
    records(context.configuration.endpoints)[context.endpointIndex]?.origin ===
      "configured"
  ) {
    document.setIn(
      ["endpoints", context.endpointIndex, "url"],
      values.endpointUrl,
    );
  }
  if (context.commandIndex !== null) {
    const command = resolveCommand(values);
    document.setIn(
      ["commands", context.commandIndex, "executable"],
      command.executableDefinition,
    );
    document.setIn(["commands", context.commandIndex, "args"], command.args);
    if (values.workingDirectory.trim())
      document.setIn(
        ["commands", context.commandIndex, "workingDirectory"],
        values.workingDirectory.trim(),
      );
    else
      document.deleteIn(["commands", context.commandIndex, "workingDirectory"]);

    const configuration = context.configuration;
    const environmentSources = records(configuration.environmentSources);
    const secretSources = records(configuration.secretSources);
    const bindings = values.bindings
      .filter(
        (binding) =>
          binding.name && (binding.kind === "secret" || binding.value),
      )
      .map((binding) => {
        const valueFrom: RecordValue = {};
        if (binding.kind === "literal") valueFrom.literal = binding.value;
        if (binding.kind === "host") {
          const id =
            binding.sourceRef ||
            `${values.id}-${slug(binding.name)}-environment`;
          valueFrom.environmentSourceRef = id;
          const existing = environmentSources.find((item) => item.id === id);
          if (existing) existing.variable = binding.value;
          else
            environmentSources.push({
              id,
              kind: "host-environment",
              variable: binding.value,
            });
        }
        if (binding.kind === "secret") {
          const id =
            binding.sourceRef || `${values.id}-${slug(binding.name)}-secret`;
          valueFrom.secretSourceRef = id;
          const existing = secretSources.find((item) => item.id === id);
          if (existing) {
            existing.kind = "secret-reference";
            existing.provider = "control-plane-store";
            delete existing.key;
          } else
            secretSources.push({
              id,
              kind: "secret-reference",
              provider: "control-plane-store",
            });
        }
        return { name: binding.name, valueFrom, required: binding.required };
      });
    document.setIn(["commands", context.commandIndex, "environment"], bindings);
    const commands = records(configuration.commands);
    if (commands[context.commandIndex])
      commands[context.commandIndex].environment = bindings;
    const remainingBindings = commands.flatMap((item) =>
      records(item.environment),
    );
    const remainingEnvironmentRefs = new Set(
      remainingBindings.flatMap((binding) => {
        const valueFrom = isRecord(binding.valueFrom) ? binding.valueFrom : {};
        return typeof valueFrom.environmentSourceRef === "string"
          ? [valueFrom.environmentSourceRef]
          : [];
      }),
    );
    const remainingSecretRefs = new Set(
      remainingBindings.flatMap((binding) => {
        const valueFrom = isRecord(binding.valueFrom) ? binding.valueFrom : {};
        return typeof valueFrom.secretSourceRef === "string"
          ? [valueFrom.secretSourceRef]
          : [];
      }),
    );
    const retainedEnvironmentSources = environmentSources.filter((item) =>
      remainingEnvironmentRefs.has(stringValue(item.id)),
    );
    const retainedSecretSources = secretSources.filter((item) =>
      remainingSecretRefs.has(stringValue(item.id)),
    );
    if (retainedEnvironmentSources.length)
      document.set("environmentSources", retainedEnvironmentSources);
    else document.delete("environmentSources");
    if (retainedSecretSources.length)
      document.set("secretSources", retainedSecretSources);
    else document.delete("secretSources");
  }
  if (context.lifecycleIndex !== null && values.kind === "application") {
    document.setIn(
      ["lifecyclePolicies", context.lifecycleIndex, "restart"],
      values.restartOnFailure ? "on-failure" : "never",
    );
  }
  return document.toString({ lineWidth: 0 });
}

function applicationEnvironment(
  configuration: RecordValue,
  application: ApplicationFormValues,
) {
  const environmentSources = records(configuration.environmentSources);
  const secretSources = records(configuration.secretSources);
  const environment = application.bindings
    .filter(
      (binding) => binding.name && (binding.kind === "secret" || binding.value),
    )
    .map((binding) => {
      const valueFrom: RecordValue = {};
      if (binding.kind === "literal") valueFrom.literal = binding.value;
      if (binding.kind === "host") {
        const id =
          binding.sourceRef ||
          `${application.applicationId}-${slug(binding.name)}-environment`;
        valueFrom.environmentSourceRef = id;
        const existing = environmentSources.find((item) => item.id === id);
        if (existing) existing.variable = binding.value;
        else
          environmentSources.push({
            id,
            kind: "host-environment",
            variable: binding.value,
          });
      }
      if (binding.kind === "secret") {
        const id =
          binding.sourceRef ||
          `${application.applicationId}-${slug(binding.name)}-secret`;
        valueFrom.secretSourceRef = id;
        if (!secretSources.some((item) => item.id === id))
          secretSources.push({
            id,
            kind: "secret-reference",
            provider: "control-plane-store",
          });
      }
      return { name: binding.name, valueFrom, required: binding.required };
    });
  configuration.environmentSources = environmentSources;
  configuration.secretSources = secretSources;
  return environment;
}

function referencedCommandIds(configuration: RecordValue) {
  return new Set([
    ...records(configuration.applications).map(
      (item) => item.processCommandRef,
    ),
    ...records(configuration.transports).map((item) => item.commandRef),
    ...records(configuration.tunnels).map((item) => item.clientCommandRef),
  ]);
}

function removeApplicationGraph(
  configuration: RecordValue,
  application: ApplicationFormValues,
) {
  const command = findById(configuration.commands, application.commandId);
  const lifecyclePolicyId = application.lifecyclePolicyId;
  const runtimeRef = stringValue(command?.runtimeRef || application.runtimeRef);
  const environmentSourceRefs = new Set<string>();
  const secretSourceRefs = new Set<string>();
  for (const binding of records(command?.environment)) {
    const valueFrom = isRecord(binding.valueFrom) ? binding.valueFrom : {};
    if (typeof valueFrom.environmentSourceRef === "string")
      environmentSourceRefs.add(valueFrom.environmentSourceRef);
    if (typeof valueFrom.secretSourceRef === "string")
      secretSourceRefs.add(valueFrom.secretSourceRef);
  }
  const endpointIds = new Set(
    records(configuration.endpoints)
      .filter((item) => item.applicationRef === application.applicationId)
      .map((item) => stringValue(item.id)),
  );

  configuration.components = records(configuration.components).filter(
    (item) => item.id !== application.componentId,
  );
  configuration.applications = records(configuration.applications).filter(
    (item) => item.id !== application.applicationId,
  );
  configuration.dependencies = records(configuration.dependencies).filter(
    (item) =>
      item.componentRef !== application.componentId &&
      item.dependsOnRef !== application.componentId,
  );
  configuration.mcpServers = records(configuration.mcpServers).map((item) => {
    if (item.controlsApplicationRef === application.applicationId)
      delete item.controlsApplicationRef;
    if (item.providedByApplicationRef === application.applicationId)
      delete item.providedByApplicationRef;
    return item;
  });
  configuration.endpoints = records(configuration.endpoints).filter(
    (item) => !endpointIds.has(stringValue(item.id)),
  );
  configuration.healthChecks = records(configuration.healthChecks).filter(
    (item) => {
      const target = isRecord(item.target) ? item.target : {};
      return (
        target.componentRef !== application.componentId &&
        !endpointIds.has(stringValue(target.endpointRef))
      );
    },
  );
  configuration.logSources = records(configuration.logSources).filter(
    (item) => {
      const target = isRecord(item.target) ? item.target : {};
      return target.commandRef !== application.commandId;
    },
  );

  if (!referencedCommandIds(configuration).has(application.commandId))
    configuration.commands = records(configuration.commands).filter(
      (item) => item.id !== application.commandId,
    );
  if (
    !records(configuration.components).some(
      (item) => item.lifecyclePolicyRef === lifecyclePolicyId,
    ) &&
    !records(configuration.tunnels).some(
      (item) => item.lifecyclePolicyRef === lifecyclePolicyId,
    )
  )
    configuration.lifecyclePolicies = records(
      configuration.lifecyclePolicies,
    ).filter((item) => item.id !== lifecyclePolicyId);
  if (
    runtimeRef &&
    !records(configuration.commands).some(
      (item) => item.runtimeRef === runtimeRef,
    )
  )
    configuration.runtimes = records(configuration.runtimes).filter(
      (item) => item.id !== runtimeRef,
    );

  const remainingBindings = records(configuration.commands).flatMap((item) =>
    records(item.environment),
  );
  const remainingEnvironmentRefs = new Set(
    remainingBindings.flatMap((binding) => {
      const valueFrom = isRecord(binding.valueFrom) ? binding.valueFrom : {};
      return typeof valueFrom.environmentSourceRef === "string"
        ? [valueFrom.environmentSourceRef]
        : [];
    }),
  );
  const remainingSecretRefs = new Set(
    remainingBindings.flatMap((binding) => {
      const valueFrom = isRecord(binding.valueFrom) ? binding.valueFrom : {};
      return typeof valueFrom.secretSourceRef === "string"
        ? [valueFrom.secretSourceRef]
        : [];
    }),
  );
  configuration.environmentSources = records(
    configuration.environmentSources,
  ).filter(
    (item) =>
      !environmentSourceRefs.has(stringValue(item.id)) ||
      remainingEnvironmentRefs.has(stringValue(item.id)),
  );
  configuration.secretSources = records(configuration.secretSources).filter(
    (item) =>
      !secretSourceRefs.has(stringValue(item.id)) ||
      remainingSecretRefs.has(stringValue(item.id)),
  );
}

export function updateApplicationConfigurations(
  source: string,
  applications: ApplicationFormValues[],
) {
  const context = editContext(source);
  const document = parseDocument(source);
  const configuration = document.toJS() as RecordValue;
  const existing = applicationFormValuesFromSource(source);
  const retainedIds = new Set(applications.map((item) => item.componentId));
  for (const application of existing) {
    if (!retainedIds.has(application.componentId))
      removeApplicationGraph(configuration, application);
  }

  const commands = records(configuration.commands);
  const applicationDefinitions = records(configuration.applications);
  const components = records(configuration.components);
  const lifecyclePolicies = records(configuration.lifecyclePolicies);
  const runtimes = records(configuration.runtimes);
  const dependencies = records(configuration.dependencies);
  const mcpServers = records(configuration.mcpServers);
  const healthChecks = records(configuration.healthChecks);
  const logSources = records(configuration.logSources);
  for (const application of applications) {
    const creating = !applicationDefinitions.some(
      (item) => item.id === application.applicationId,
    );
    const resolved = resolveCommand({
      ...emptyStackFormValues,
      launcher: application.launcher,
      executable: application.executable,
      version: application.version,
      arguments: application.arguments,
    });
    let command = commands.find((item) => item.id === application.commandId);
    if (!command) {
      command = { id: application.commandId };
      commands.push(command);
    }
    command.runtimeRef = application.runtimeRef;
    command.executable = resolved.executableDefinition;
    command.args = resolved.args;
    if (application.workingDirectory.trim())
      command.workingDirectory = application.workingDirectory.trim();
    else delete command.workingDirectory;
    command.environment = applicationEnvironment(configuration, application);

    if (!runtimes.some((item) => item.id === application.runtimeRef))
      runtimes.push({ id: application.runtimeRef, kind: "host" });
    let definition = applicationDefinitions.find(
      (item) => item.id === application.applicationId,
    );
    if (!definition) {
      definition = { id: application.applicationId };
      applicationDefinitions.push(definition);
    }
    definition.name = application.name;
    definition.processCommandRef = application.commandId;
    if (!Array.isArray(definition.providedEndpointRefs))
      definition.providedEndpointRefs = [];

    let component = components.find(
      (item) => item.id === application.componentId,
    );
    if (!component) {
      component = { id: application.componentId };
      components.push(component);
    }
    component.name = application.name;
    if (application.description.trim())
      component.description = application.description.trim();
    else delete component.description;
    component.enabled = true;
    component.subject = { applicationRef: application.applicationId };
    component.lifecyclePolicyRef = application.lifecyclePolicyId;
    if (!Array.isArray(component.healthCheckRefs)) {
      const healthId = `${application.applicationId}-process`;
      component.healthCheckRefs = [healthId];
      healthChecks.push({
        id: healthId,
        name: `${application.name} process active`,
        target: { componentRef: application.componentId },
        probe: "process-running",
        role: "liveness",
        timeoutSeconds: 2,
      });
    }
    if (!Array.isArray(component.logSourceRefs)) {
      const logId = `${application.applicationId}-journal`;
      component.logSourceRefs = [logId];
      logSources.push({
        id: logId,
        name: `${application.name} service journal`,
        target: { commandRef: application.commandId, stream: "stderr" },
        encoding: "utf-8",
        framing: "lines",
      });
    }

    let lifecycle = lifecyclePolicies.find(
      (item) => item.id === application.lifecyclePolicyId,
    );
    if (!lifecycle) {
      lifecycle = { id: application.lifecyclePolicyId };
      lifecyclePolicies.push(lifecycle);
    }
    lifecycle.ownership = "control-plane-managed";
    lifecycle.activation = "persistent";
    lifecycle.provider = "system-service";
    lifecycle.restart = application.restartOnFailure ? "on-failure" : "never";
    if (creating) lifecycle.stopTimeoutSeconds = 20;

    if (
      creating &&
      !dependencies.some(
        (item) =>
          item.componentRef === context.primaryComponentId &&
          item.dependsOnRef === application.componentId,
      )
    )
      dependencies.push({
        componentRef: context.primaryComponentId,
        dependsOnRef: application.componentId,
        requirement: "healthy",
        strength: "hard",
      });
    if (creating && context.primaryMcpServerId) {
      const server = mcpServers.find(
        (item) => item.id === context.primaryMcpServerId,
      );
      if (server && !server.controlsApplicationRef)
        server.controlsApplicationRef = application.applicationId;
    }
  }

  configuration.commands = commands;
  configuration.applications = applicationDefinitions;
  configuration.components = components;
  configuration.lifecyclePolicies = lifecyclePolicies;
  configuration.runtimes = runtimes;
  configuration.dependencies = dependencies;
  configuration.mcpServers = mcpServers;
  configuration.healthChecks = healthChecks;
  configuration.logSources = logSources;
  for (const key of [
    "runtimes",
    "commands",
    "environmentSources",
    "secretSources",
    "endpoints",
    "mcpServers",
    "applications",
    "lifecyclePolicies",
    "healthChecks",
    "logSources",
    "components",
    "dependencies",
  ]) {
    const value = configuration[key];
    if (Array.isArray(value) && value.length === 0) document.delete(key);
    else if (value !== undefined) document.set(key, value);
  }
  return document.toString({ lineWidth: 0 });
}

export function applicationDeletionItems(source: string, componentId: string) {
  const application = applicationFormValuesFromSource(source).find(
    (item) => item.componentId === componentId,
  );
  if (!application) return [];
  const configuration = editContext(source).configuration;
  const endpointIds = records(configuration.endpoints)
    .filter((item) => item.applicationRef === application.applicationId)
    .map((item) => stringValue(item.id));
  const items = [
    { id: application.componentId, label: "Application Component" },
    { id: application.applicationId, label: "Application definition" },
    { id: application.commandId, label: "Application command" },
    { id: application.lifecyclePolicyId, label: "Lifecycle policy" },
    ...endpointIds.map((id) => ({ id, label: "Provided endpoint" })),
  ];
  for (const healthCheck of records(configuration.healthChecks)) {
    const target = isRecord(healthCheck.target) ? healthCheck.target : {};
    if (
      target.componentRef === application.componentId ||
      endpointIds.includes(stringValue(target.endpointRef))
    )
      items.push({ id: stringValue(healthCheck.id), label: "Health check" });
  }
  for (const logSource of records(configuration.logSources)) {
    const target = isRecord(logSource.target) ? logSource.target : {};
    if (target.commandRef === application.commandId)
      items.push({ id: stringValue(logSource.id), label: "Log source" });
  }
  for (const [index, dependency] of records(
    configuration.dependencies,
  ).entries()) {
    if (
      dependency.componentRef === application.componentId ||
      dependency.dependsOnRef === application.componentId
    )
      items.push({
        id: `${stringValue(dependency.componentRef)} -> ${stringValue(dependency.dependsOnRef)} (${index + 1})`,
        label: "Dependency relationship",
      });
  }
  const command = findById(configuration.commands, application.commandId);
  for (const binding of records(command?.environment)) {
    const valueFrom = isRecord(binding.valueFrom) ? binding.valueFrom : {};
    if (typeof valueFrom.secretSourceRef === "string")
      items.push({
        id: valueFrom.secretSourceRef,
        label: "Secret slot if no longer shared",
      });
  }
  return items;
}
