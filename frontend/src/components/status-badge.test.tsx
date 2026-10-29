import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "@/components/status-badge";

describe("StatusBadge", () => {
  it("labels absence of runtime evidence without calling it stopped", () => {
    render(<StatusBadge status="not-observed" />);

    expect(screen.getByText("Not observed")).toBeInTheDocument();
    expect(screen.queryByText("Stopped")).not.toBeInTheDocument();
  });

  it("labels a verified execution process without claiming MCP connectivity", () => {
    render(<StatusBadge status="running" />);

    const badge = screen.getByText("Running process");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass("bg-status-positive/15");
    expect(screen.queryByText(/connected/i)).not.toBeInTheDocument();
  });
});
