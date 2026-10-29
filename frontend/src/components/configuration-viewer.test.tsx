import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConfigurationViewer } from "@/components/configuration-viewer";

describe("ConfigurationViewer", () => {
  it("renders nested configuration from schema property order", () => {
    render(
      <ConfigurationViewer
        schema={{
          $defs: {
            component: {
              type: "object",
              properties: {
                name: { type: "string" },
                enabled: { type: "boolean" },
                subject: {
                  type: "object",
                  properties: { mcpServerRef: { type: "string" } },
                },
              },
            },
          },
        }}
        definition="component"
        value={{
          name: "Filesystem MCP",
          enabled: true,
          subject: { mcpServerRef: "filesystem-mcp" },
        }}
      />,
    );

    expect(screen.getByText("Filesystem MCP")).toBeInTheDocument();
    expect(screen.getAllByText("Enabled")).toHaveLength(2);
    expect(screen.getByText("filesystem-mcp")).toBeInTheDocument();
  });
});
