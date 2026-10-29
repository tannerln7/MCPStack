import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RelationshipView } from "@/components/relationship-view";

describe("RelationshipView", () => {
  it("renders a generic linked relationship with component navigation", () => {
    render(
      <RelationshipView
        stackId="local"
        relationships={[
          {
            category: "Dependency",
            relation: "depends on (ready, hard)",
            from: {
              id: "adapter",
              kind: "component",
              label: "Adapter",
              componentId: "adapter",
            },
            to: {
              id: "application",
              kind: "component",
              label: "Application",
              componentId: "application",
            },
          },
        ]}
      />,
    );

    expect(
      screen.getByRole("list", { name: "Dependency relationships" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Adapter component/ }),
    ).toHaveAttribute("href", "/stacks/local/components/adapter");
    expect(screen.getByText("depends on (ready, hard)")).toBeInTheDocument();
  });
});
