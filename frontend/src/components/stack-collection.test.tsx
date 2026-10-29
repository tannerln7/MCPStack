import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { StackCollection } from "@/components/stack-collection";
import type { StackDiscovery } from "@/lib/contracts/types";
import type { StackCollectionItem } from "@/lib/stack-collection";

const source = {
  path: "native-tools.yaml",
  format: "yaml" as const,
  revision: "0123456789abcdef",
  sizeBytes: 1024,
  modifiedAt: "2026-08-22T08:00:00Z",
};

const discovery: StackDiscovery = {
  stacks: [],
  invalidSources: [],
  scannedSourceCount: 2,
};

function item(
  overrides: Partial<StackCollectionItem> &
    Pick<StackCollectionItem, "id" | "name">,
): StackCollectionItem {
  return {
    description: `${overrides.name} tools`,
    componentCount: 1,
    configurationRevision: source.revision,
    source: { ...source, path: `${overrides.id}.yaml` },
    componentTypes: ["MCP server"],
    transports: ["stdio"],
    healthState: "not-observed",
    statuses: ["not-observed"],
    searchText: `${overrides.id} ${overrides.name}`.toLocaleLowerCase(),
    ...overrides,
  };
}

const alpha = item({
  id: "alpha",
  name: "Alpha",
  searchText: "alpha reactbits-dev-mcp-server mcp server stdio",
});
const browser = item({
  id: "browser",
  name: "Browser",
  componentTypes: ["Application"],
  transports: ["streamable-http"],
  statuses: ["running"],
  searchText: "browser application streamable-http",
});

afterEach(cleanup);

describe("StackCollection", () => {
  it("renders one flat table in alphabetical order with source metadata", () => {
    render(<StackCollection discovery={discovery} items={[browser, alpha]} />);

    const rows = screen.getAllByRole("row").slice(1);
    expect(rows).toHaveLength(2);
    expect(
      within(rows[0]).getByRole("link", { name: "Alpha" }),
    ).toHaveAttribute("href", "/stacks/alpha");
    expect(
      within(rows[1]).getByRole("link", { name: "Browser" }),
    ).toHaveAttribute("href", "/stacks/browser");
    expect(screen.getByText("alpha.yaml")).toBeInTheDocument();
    expect(screen.getByText("2 of 2 stacks")).toBeInTheDocument();
  });

  it("searches metadata and filters by type, transport, health, and runtime status", () => {
    render(<StackCollection discovery={discovery} items={[alpha, browser]} />);

    fireEvent.change(screen.getByLabelText("Search"), {
      target: { value: "reactbits-dev-mcp-server" },
    });
    expect(screen.getByRole("link", { name: "Alpha" })).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Browser" }),
    ).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Search"), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByRole("button", { name: /show filters/i }));
    fireEvent.change(screen.getByLabelText("Type"), {
      target: { value: "Application" },
    });
    expect(screen.getByRole("link", { name: "Browser" })).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Alpha" }),
    ).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Transport"), {
      target: { value: "stdio" },
    });
    expect(screen.getByText("No matching stacks")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Type"), {
      target: { value: "all" },
    });
    fireEvent.change(screen.getByLabelText("Transport"), {
      target: { value: "all" },
    });
    fireEvent.change(screen.getByLabelText("Runtime status"), {
      target: { value: "running" },
    });
    expect(screen.getByRole("link", { name: "Browser" })).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Alpha" }),
    ).not.toBeInTheDocument();
  });

  it("sorts by type and runtime status", () => {
    const ready = item({ id: "ready", name: "Ready" });
    const unknown = item({ id: "unknown", name: "Unknown" });
    render(
      <StackCollection
        discovery={discovery}
        items={[unknown, alpha, browser, ready]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /show filters/i }));
    fireEvent.change(screen.getByLabelText("Sort"), {
      target: { value: "type" },
    });
    let rows = screen.getAllByRole("row").slice(1);
    expect(
      within(rows[0]).getByRole("link", { name: "Browser" }),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Sort"), {
      target: { value: "status" },
    });
    rows = screen.getAllByRole("row").slice(1);
    expect(
      within(rows[0]).getByRole("link", { name: "Browser" }),
    ).toBeInTheDocument();
  });

  it("shows invalid-source details when no valid stacks exist", () => {
    const invalidDiscovery: StackDiscovery = {
      stacks: [],
      scannedSourceCount: 1,
      invalidSources: [
        {
          sourcePath: "broken.yaml",
          source,
          issues: [
            {
              stage: "parsing",
              path: "/",
              code: "invalid-yaml",
              message: "expected the node content",
              line: 4,
              column: 8,
            },
          ],
        },
      ],
    };
    render(<StackCollection discovery={invalidDiscovery} items={[]} />);

    expect(
      screen.getByRole("heading", { name: "Configuration issues" }),
    ).toBeInTheDocument();
    expect(screen.getByText("broken.yaml")).toBeInTheDocument();
    expect(screen.getByText("line 4, column 8")).toBeInTheDocument();
    expect(screen.getByText("No valid stacks found")).toBeInTheDocument();
  });
});
