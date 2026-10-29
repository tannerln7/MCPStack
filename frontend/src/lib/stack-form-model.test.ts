import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { parse, stringify } from "yaml";

import {
  applicationDeletionItems,
  applicationFormValuesFromSource,
  buildStackDocument,
  emptyStackFormValues,
  newApplicationFormValues,
  stackFormValuesFromSource,
  updateApplicationConfigurations,
  updateStackDocument,
} from "@/lib/stack-form-model";

const managedHttpSource = readFileSync(
  "src/test/fixtures/managed-http-stack.yaml",
  "utf8",
);

const source = `modelVersion: "0.1"
id: docs
name: Documentation MCP
description: Existing description

runtimes:
  - id: host
    kind: host
commands:
  - id: docs-command
    runtimeRef: host
    executable:
      kind: path-name
      name: npx
    args: [-y, "@example/docs-mcp@1.2.3", --stdio]
    environment:
      - name: DOCS_API_KEY
        valueFrom:
          secretSourceRef: docs-api-key
secretSources:
  - id: docs-api-key
    kind: secret-reference
    provider: control-plane-store
transports:
  - id: docs-stdio
    kind: stdio
    commandRef: docs-command
mcpServers:
  - id: docs-mcp
    name: Documentation MCP
    transportRef: docs-stdio
lifecyclePolicies:
  - id: session
    ownership: session-owned
    activation: on-demand
healthChecks:
  - id: docs-health
    name: MCP connection
    target:
      mcpServerRef: docs-mcp
    probe: mcp-connect
    role: readiness
logSources:
  - id: docs-stderr
    name: stderr
    target:
      commandRef: docs-command
      stream: stderr
    encoding: utf-8
    framing: lines
components:
  - id: docs
    name: Documentation MCP
    enabled: true
    subject:
      mcpServerRef: docs-mcp
    lifecyclePolicyRef: session
`;

const compositeSource = `modelVersion: "0.1"
id: composite
name: Composite
runtimes:
  - id: host
    kind: host
commands:
  - id: app-command
    runtimeRef: host
    executable: { kind: local-path, path: /opt/example/server }
    args: [--listen]
    environment:
      - name: APP_TOKEN
        valueFrom: { secretSourceRef: app-token }
  - id: bridge-command
    runtimeRef: host
    executable: { kind: path-name, name: uv }
    args: [run, bridge]
secretSources:
  - id: app-token
    kind: secret-reference
    provider: control-plane-store
transports:
  - id: bridge-stdio
    kind: stdio
    commandRef: bridge-command
mcpServers:
  - id: bridge-mcp
    name: Bridge MCP
    transportRef: bridge-stdio
    controlsApplicationRef: app
applications:
  - id: app
    name: Example server
    processCommandRef: app-command
lifecyclePolicies:
  - id: app-managed
    ownership: control-plane-managed
    activation: persistent
    provider: system-service
    restart: on-failure
  - id: bridge-session
    ownership: session-owned
    activation: on-demand
    provider: direct-child
    restart: never
healthChecks:
  - id: app-process
    name: Process active
    target: { componentRef: app-component }
    probe: process-running
    role: liveness
logSources:
  - id: app-journal
    name: Journal
    target: { commandRef: app-command, stream: stderr }
    encoding: utf-8
    framing: lines
components:
  - id: app-component
    name: Example server
    enabled: true
    subject: { applicationRef: app }
    lifecyclePolicyRef: app-managed
    healthCheckRefs: [app-process]
    logSourceRefs: [app-journal]
  - id: bridge-component
    name: Bridge MCP
    enabled: true
    subject: { mcpServerRef: bridge-mcp }
    lifecyclePolicyRef: bridge-session
dependencies:
  - componentRef: bridge-component
    dependsOnRef: app-component
    requirement: healthy
    strength: hard
`;

describe("Stack form model", () => {
  it("derives a read-only managed HTTP URL without changing its endpoint representation", () => {
    const values = stackFormValuesFromSource(managedHttpSource);
    expect(values).toMatchObject({
      kind: "http",
      endpointUrl: "http://127.0.0.1:8081/mcp",
      endpointUrlReadOnly: true,
    });
    expect(parse(updateStackDocument(managedHttpSource, values))).toEqual(
      parse(managedHttpSource),
    );
  });

  it.each([
    "::1",
    "[::1]",
  ])("brackets the IPv6 listener host %s exactly once", (host) => {
    const configuration = parse(managedHttpSource);
    configuration.endpoints[1].listener.host = host;
    expect(
      stackFormValuesFromSource(stringify(configuration)).endpointUrl,
    ).toBe("http://[::1]:8081/mcp");
  });

  it("preserves the HTTP application graph and secrets when editing an application environment", () => {
    const values = stackFormValuesFromSource(managedHttpSource);
    const applications = applicationFormValuesFromSource(managedHttpSource);
    expect(applications).toHaveLength(2);
    applications[0].bindings[0].value = "/opt/example/new-java";
    const candidate = updateApplicationConfigurations(
      updateStackDocument(managedHttpSource, {
        ...values,
        name: "Updated Analysis MCP",
        // Source endpoint ownership, not editable form state, guards the save.
        endpointUrl: "https://unrelated.example/mcp",
        endpointUrlReadOnly: false,
      }),
      applications,
    );
    const expected = parse(managedHttpSource);
    expected.name = "Updated Analysis MCP";
    expected.commands[0].environment[0].valueFrom.literal =
      "/opt/example/new-java";
    expect(parse(candidate)).toEqual(expected);
  });

  it("still edits explicitly configured HTTP URLs", () => {
    const source = buildStackDocument({
      ...emptyStackFormValues,
      id: "remote",
      name: "Remote MCP",
      kind: "http",
      endpointUrl: "https://old.example/mcp",
    });
    const values = stackFormValuesFromSource(source);
    expect(values.endpointUrlReadOnly).toBe(false);
    const configuration = parse(source);
    configuration.endpoints[0].url = "https://new.example/mcp";
    expect(
      parse(
        updateStackDocument(source, {
          ...values,
          endpointUrl: "https://new.example/mcp",
        }),
      ),
    ).toEqual(configuration);
  });

  it.each([
    ["stdio", { executable: "@example/bridge-mcp" }],
    ["http", { endpointUrl: "http://127.0.0.1:8080/mcp" }],
    ["application", { launcher: "native", executable: "/opt/example/main" }],
  ] as const)("adds an attached managed Application while creating a %s Stack", (kind, overrides) => {
    const values = {
      ...emptyStackFormValues,
      id: `example-${kind}`,
      name: `Example ${kind}`,
      kind,
      ...overrides,
    };
    const application = {
      ...newApplicationFormValues(values.id, []),
      name: "Dependent service",
      executable: "/opt/example/dependent-service",
    };

    const document = updateApplicationConfigurations(
      buildStackDocument(values),
      [application],
    );

    expect(document).toContain("applications:");
    expect(document).toContain("name: Dependent service");
    expect(document).toContain("ownership: control-plane-managed");
    expect(document).toContain("provider: system-service");
    expect(document).toContain("dependencies:");
    expect(document).toContain(`componentRef: example-${kind}-component`);
    if (kind !== "application")
      expect(document).toContain(
        `controlsApplicationRef: ${application.applicationId}`,
      );
  });

  it("hydrates the generated fields from an existing Stack", () => {
    const values = stackFormValuesFromSource(source);

    expect(values).toMatchObject({
      id: "docs",
      name: "Documentation MCP",
      kind: "stdio",
      launcher: "npx",
      executable: "@example/docs-mcp",
      version: "1.2.3",
      arguments: "--stdio",
    });
    expect(values.bindings).toMatchObject([
      {
        name: "DOCS_API_KEY",
        kind: "secret",
        value: "",
        sourceRef: "docs-api-key",
        secretValue: "",
        required: true,
      },
    ]);
  });

  it("regenerates edited fields without dropping advanced sections", () => {
    const values = stackFormValuesFromSource(source);
    const candidate = updateStackDocument(source, {
      ...values,
      name: "Updated Documentation MCP",
      version: "2.0.0",
    });

    expect(candidate).toContain("name: Updated Documentation MCP");
    expect(candidate).toContain('"@example/docs-mcp@2.0.0"');
    expect(candidate).toContain("healthChecks:");
    expect(candidate).toContain("id: docs-health");
    expect(candidate).toContain("logSources:");
    expect(candidate).toContain("id: docs-stderr");
  });

  it("edits the MCP bridge as primary and exposes attached Applications separately", () => {
    const primary = stackFormValuesFromSource(compositeSource);
    const applications = applicationFormValuesFromSource(compositeSource);

    expect(primary).toMatchObject({
      kind: "stdio",
      launcher: "native",
      executable: "uv",
      arguments: "run\nbridge",
    });
    expect(applications).toHaveLength(1);
    expect(applications[0]).toMatchObject({
      componentId: "app-component",
      applicationId: "app",
      executable: "/opt/example/server",
      arguments: "--listen",
    });
  });

  it("adds and removes complete Application graphs without dropping the primary MCP", () => {
    const existing = applicationFormValuesFromSource(compositeSource);
    const added = {
      ...newApplicationFormValues("composite", existing),
      name: "Indexer",
      executable: "/opt/example/indexer",
    };
    const withApplication = updateApplicationConfigurations(compositeSource, [
      ...existing,
      added,
    ]);

    expect(withApplication).toContain("name: Indexer");
    expect(withApplication).toContain("probe: process-running");
    expect(withApplication).toContain("service journal");

    const withoutOriginal = updateApplicationConfigurations(withApplication, [
      { ...added, isNew: false },
    ]);
    expect(withoutOriginal).not.toContain("id: app-token");
    expect(withoutOriginal).not.toContain("id: app-component");
    expect(withoutOriginal).not.toContain("id: app-command");
    expect(withoutOriginal).toContain("id: bridge-mcp");
    expect(withoutOriginal).toContain("name: Indexer");
  });

  it("lists graph resources and conditional secret cleanup in deletion confirmation", () => {
    expect(applicationDeletionItems(compositeSource, "app-component")).toEqual(
      expect.arrayContaining([
        { id: "app-component", label: "Application Component" },
        { id: "app", label: "Application definition" },
        { id: "app-command", label: "Application command" },
        { id: "app-token", label: "Secret slot if no longer shared" },
      ]),
    );
  });

  it("retains a SecretSource that is still referenced by another command", () => {
    const sharedSource = compositeSource.replace(
      "    args: [run, bridge]\nsecretSources:",
      "    args: [run, bridge]\n    environment:\n      - name: SHARED_TOKEN\n        valueFrom: { secretSourceRef: app-token }\nsecretSources:",
    );

    const candidate = updateApplicationConfigurations(sharedSource, []);

    expect(candidate).toContain("id: app-token");
    expect(candidate).toContain("secretSourceRef: app-token");
  });
});
