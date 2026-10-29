import { describe, expect, it } from "vitest";

import type { StackSummary, StackView } from "@/lib/contracts/types";
import { toStackCollectionItem } from "@/lib/stack-collection";

const source = {
  path: "brightdata.yaml",
  format: "yaml" as const,
  revision: "0123456789abcdef",
  sizeBytes: 1024,
  modifiedAt: "2026-08-22T08:00:00Z",
};

describe("toStackCollectionItem", () => {
  it("derives useful search metadata without including secret references", () => {
    const summary: StackSummary = {
      id: "brightdata",
      name: "Bright Data",
      description: "Web data service",
      componentCount: 1,
      configurationRevision: source.revision,
      source,
    };
    const stack = {
      source,
      configuration: {
        modelVersion: "0.1",
        id: "brightdata",
        name: "Bright Data",
        runtimes: [{ id: "host", kind: "host" }],
        commands: [
          {
            id: "brightdata-command",
            runtimeRef: "host",
            executable: { kind: "path-name", name: "npx" },
            args: ["-y", "@brightdata/mcp"],
            environment: [
              {
                name: "API_TOKEN",
                valueFrom: { secretSourceRef: "brightdata-api-token" },
              },
            ],
          },
        ],
        environmentSources: [],
        secretSources: [
          {
            id: "brightdata-api-token",
            kind: "secret-reference",
            provider: "control-plane-store",
          },
        ],
        endpoints: [],
        transports: [
          {
            id: "brightdata-stdio",
            kind: "stdio",
            commandRef: "brightdata-command",
          },
        ],
        mcpServers: [
          {
            id: "brightdata-mcp",
            name: "Bright Data MCP",
            transportRef: "brightdata-stdio",
          },
        ],
        applications: [],
        tunnels: [],
        lifecyclePolicies: [],
        healthChecks: [],
        logSources: [],
        components: [
          {
            id: "brightdata",
            name: "Bright Data",
            description: "Web data component",
            enabled: true,
            subject: { mcpServerRef: "brightdata-mcp" },
            healthCheckRefs: [],
            logSourceRefs: [],
          },
        ],
        dependencies: [],
      },
      observations: {
        stackId: "brightdata",
        configurationRevision: source.revision,
        observedAt: "2026-08-22T08:00:00Z",
        components: [
          {
            componentId: "brightdata",
            status: "available",
            observedAt: "2026-08-22T08:00:00Z",
          },
        ],
        executionSessions: [],
        processInstances: [],
        mcpSessions: [],
        endpointObservations: [],
        healthObservations: [],
        logStreams: [],
      },
    } as StackView;

    const item = toStackCollectionItem(summary, stack);

    expect(item.componentTypes).toEqual(["MCP server"]);
    expect(item.transports).toEqual(["stdio"]);
    expect(item.statuses).toEqual(["available"]);
    expect(item.searchText).toContain("@brightdata/mcp");
    expect(item.searchText).toContain("npx");
    expect(item.searchText).not.toContain("private-secret-store");
    expect(item.searchText).not.toContain("brightdata-api-token");
  });
});
