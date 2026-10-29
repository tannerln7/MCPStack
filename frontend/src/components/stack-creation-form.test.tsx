import { readFileSync } from "node:fs";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { parse } from "yaml";

import { StackCreationForm } from "@/components/stack-creation-form";
import type { EditableStackSource } from "@/lib/contracts/types";

const refresh = vi.fn();
const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

const source: EditableStackSource = {
  stackId: "docs",
  stackName: "Documentation MCP",
  source: {
    path: "docs.yaml",
    format: "yaml",
    revision: "a".repeat(64),
    sizeBytes: 500,
    modifiedAt: "2026-08-23T00:00:00Z",
  },
  mediaType: "application/yaml",
  encoding: "utf-8",
  document: `modelVersion: "0.1"
id: docs
name: Documentation MCP
runtimes:
  - id: host
    kind: host
commands:
  - id: docs-command
    runtimeRef: host
    executable:
      kind: path-name
      name: npx
    args: [-y, "@example/docs-mcp@1.0.0"]
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
components:
  - id: docs
    name: Documentation MCP
    enabled: true
    subject:
      mcpServerRef: docs-mcp
    lifecyclePolicyRef: session
`,
};

afterEach(() => {
  cleanup();
  refresh.mockClear();
  push.mockClear();
  vi.unstubAllGlobals();
});

describe("StackCreationForm create mode", () => {
  it("creates a stdio MCP Stack with an attached managed Application", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ valid: true, issues: [] }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => ({ status: "created" }),
      });
    vi.stubGlobal("fetch", fetchMock);
    render(<StackCreationForm />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Example Bridge" },
    });
    fireEvent.change(screen.getByLabelText("Package"), {
      target: { value: "@example/bridge-mcp" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add application" }));
    fireEvent.change(screen.getByLabelText("Application name"), {
      target: { value: "Example service" },
    });
    fireEvent.change(screen.getByLabelText("Executable"), {
      target: { value: "/opt/example/bin/server" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Stack" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const previewBody = JSON.parse(
      fetchMock.mock.calls[0]?.[1]?.body as string,
    );
    const createBody = JSON.parse(fetchMock.mock.calls[1]?.[1]?.body as string);
    for (const body of [previewBody, createBody]) {
      expect(body.stackId).toBe("example-bridge");
      expect(body.document).toContain("applications:");
      expect(body.document).toContain("name: Example service");
      expect(body.document).toContain("controlsApplicationRef:");
      expect(body.document).toContain("dependencies:");
    }
    expect(push).toHaveBeenCalledWith("/stacks/example-bridge");
  });
});

describe("StackCreationForm edit mode", () => {
  it("displays the managed HTTP listener read-only and saves unrelated edits without adding a URL", async () => {
    const managedSource: EditableStackSource = {
      ...source,
      stackId: "analysis",
      stackName: "Analysis MCP",
      document: readFileSync(
        "src/test/fixtures/managed-http-stack.yaml",
        "utf8",
      ),
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ valid: true, issues: [] }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          status: "saved",
          source: { ...source.source, revision: "b".repeat(64) },
        }),
      });
    vi.stubGlobal("fetch", fetchMock);
    render(<StackCreationForm source={managedSource} />);

    const endpoint = screen.getByLabelText("Endpoint URL");
    expect(endpoint).toHaveValue("http://127.0.0.1:8081/mcp");
    expect(endpoint).toHaveAttribute("readonly");
    expect(endpoint).not.toBeRequired();
    expect(screen.getByLabelText("Stack type")).toHaveValue("http");
    expect(screen.getByDisplayValue("Headless server")).toBeInTheDocument();
    expect(screen.getByDisplayValue("HTTP bridge")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Save configuration" }),
    ).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Updated Analysis MCP" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save configuration" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/stacks/analysis/validation-previews",
    );
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/stacks/analysis/source");
    const body = JSON.parse(fetchMock.mock.calls[1]?.[1]?.body as string);
    expect(body.originalRevision).toBe(source.source.revision);
    const expected = parse(managedSource.document);
    expected.name = "Updated Analysis MCP";
    expect(parse(body.document)).toEqual(expected);
    expect(await screen.findByText("Configuration saved")).toBeInTheDocument();
  });

  it("hydrates fields and saves the generated YAML with the source revision", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ valid: true, issues: [] }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          status: "saved",
          previousRevision: source.source.revision,
          source: { ...source.source, revision: "b".repeat(64) },
          bytesWritten: 600,
          replaced: true,
        }),
      });
    vi.stubGlobal("fetch", fetchMock);
    render(<StackCreationForm source={source} />);

    expect(screen.getByLabelText("ID")).toBeDisabled();
    expect(screen.getByLabelText("Stack type")).toBeDisabled();
    expect(screen.getByLabelText("Package")).toHaveValue("@example/docs-mcp");
    expect(screen.getByLabelText("Version or tag")).toHaveValue("1.0.0");
    expect(
      screen.getByRole("button", { name: "Save configuration" }),
    ).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Updated Documentation MCP" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save configuration" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/stacks/docs/validation-previews",
    );
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/stacks/docs/source");
    const saveBody = JSON.parse(fetchMock.mock.calls[1]?.[1]?.body as string);
    expect(saveBody.originalRevision).toBe(source.source.revision);
    expect(saveBody.document).toContain("name: Updated Documentation MCP");
    expect(await screen.findByText("Configuration saved")).toBeInTheDocument();
  });

  it("adds and confirms removal of an attached Application candidate", async () => {
    render(<StackCreationForm source={source} />);

    expect(
      screen.getByText(
        "No attached Applications. Add one when this Stack depends on a persistent local service.",
      ),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add application" }));

    expect(screen.getByDisplayValue("New application")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete application" }));
    expect(
      await screen.findByText("New Application Component"),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Remove from candidate" }),
    );

    await waitFor(() =>
      expect(
        screen.queryByDisplayValue("New application"),
      ).not.toBeInTheDocument(),
    );
  });
});
