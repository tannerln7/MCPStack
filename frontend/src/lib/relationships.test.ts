import { describe, expect, it } from "vitest";

import type { StackConfiguration } from "@/lib/contracts/types";
import {
  componentRelationships,
  configurationRelationships,
} from "@/lib/relationships";

const configuration = {
  modelVersion: "0.1",
  id: "test-stack",
  name: "Test stack",
  runtimes: [{ id: "host", kind: "host" }],
  commands: [
    {
      id: "app-command",
      runtimeRef: "host",
      executable: { kind: "path-name", name: "app" },
      args: [],
      environment: [
        {
          name: "TOKEN",
          valueFrom: { secretSourceRef: "app-token" },
        },
      ],
    },
    {
      id: "tunnel-command",
      runtimeRef: "host",
      executable: { kind: "path-name", name: "tunnel" },
      args: [],
      environment: [],
    },
  ],
  environmentSources: [],
  secretSources: [
    {
      id: "app-token",
      kind: "secret-reference",
      provider: "control-plane-store",
    },
  ],
  endpoints: [
    {
      id: "app-http",
      origin: "application-provided",
      applicationRef: "app",
      listener: { scheme: "http", host: "127.0.0.1", port: 8001, path: "/mcp" },
    },
    { id: "public-http", origin: "tunnel-provided", tunnelRef: "tunnel" },
  ],
  transports: [
    { id: "app-transport", kind: "streamable-http", endpointRef: "app-http" },
  ],
  mcpServers: [
    {
      id: "app-mcp",
      name: "App MCP",
      transportRef: "app-transport",
      providedByApplicationRef: "app",
    },
  ],
  applications: [
    {
      id: "app",
      name: "App",
      processCommandRef: "app-command",
      providedEndpointRefs: ["app-http"],
    },
  ],
  tunnels: [
    {
      id: "tunnel",
      name: "Tunnel",
      targetEndpointRef: "app-http",
      clientCommandRef: "tunnel-command",
      lifecyclePolicyRef: "managed",
      publicEndpointRef: "public-http",
    },
  ],
  lifecyclePolicies: [
    {
      id: "managed",
      ownership: "control-plane-managed",
      activation: "persistent",
    },
  ],
  healthChecks: [],
  logSources: [],
  components: [
    {
      id: "app",
      name: "App",
      enabled: true,
      subject: { applicationRef: "app" },
      healthCheckRefs: [],
      logSourceRefs: [],
    },
    {
      id: "tunnel",
      name: "Tunnel",
      enabled: true,
      subject: { tunnelRef: "tunnel" },
      lifecyclePolicyRef: "managed",
      healthCheckRefs: [],
      logSourceRefs: [],
    },
  ],
  dependencies: [
    {
      componentRef: "tunnel",
      dependsOnRef: "app",
      requirement: "ready",
      strength: "hard",
    },
  ],
} satisfies StackConfiguration;

describe("configurationRelationships", () => {
  it("describes dependencies, provision, exposure, and consumed inputs", () => {
    const relationships = configurationRelationships(configuration);
    expect(relationships).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          category: "Dependency",
          relation: "depends on (ready, hard)",
        }),
        expect.objectContaining({
          category: "Provision",
          relation: "provides endpoint",
        }),
        expect.objectContaining({ category: "Exposure", relation: "exposes" }),
        expect.objectContaining({
          category: "Runtime",
          relation: "consumes TOKEN",
        }),
        expect.objectContaining({
          category: "Provision",
          relation: "provides",
        }),
      ]),
    );
  });

  it("keeps a component view generic while following its resource chain", () => {
    const component = configuration.components[0];
    const relationships = componentRelationships(configuration, component);
    expect(relationships.some(({ to }) => to.id === "app-token")).toBe(true);
    expect(
      relationships.some(({ relation }) => relation === "provides endpoint"),
    ).toBe(true);
    expect(
      relationships.some(
        ({ from, relation }) =>
          from.id === "tunnel" && relation === "publishes",
      ),
    ).toBe(false);
  });
});
