import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { RuntimeExecutionDetails } from "@/components/runtime-execution-details";
import type { ExecutionSessionObservation } from "@/lib/contracts/types";

const active: ExecutionSessionObservation = {
  executionId: "11111111-1111-4111-8111-111111111111",
  componentId: "context7",
  mcpServerRef: "context7-mcp",
  transport: "stdio",
  state: "active",
  configurationRevision: "abcdef1234567890",
  configurationRevisionMatches: true,
  configurationIdentityMatches: true,
  launchedAt: "2026-08-22T12:00:00Z",
  observedAt: "2026-08-22T12:01:00Z",
  pid: 123,
};

afterEach(cleanup);

describe("RuntimeExecutionDetails", () => {
  it("explains not-observed without treating wrappers as stopped", () => {
    render(<RuntimeExecutionDetails componentId="context7" sessions={[]} />);

    expect(
      screen.getByText(/No execution launched through/),
    ).toBeInTheDocument();
    expect(screen.getByText(/legacy wrappers/)).toBeInTheDocument();
  });

  it("renders concurrent active sessions without claiming protocol health", () => {
    render(
      <RuntimeExecutionDetails
        componentId="context7"
        sessions={[
          active,
          {
            ...active,
            executionId: "22222222-2222-4222-8222-222222222222",
            configurationRevisionMatches: false,
          },
        ]}
      />,
    );

    expect(screen.getByText(/Process presence/)).toHaveTextContent(
      "2 active execution processes.",
    );
    expect(screen.getAllByText("Active process")).toHaveLength(2);
    expect(screen.getByText("changed since launch")).toBeInTheDocument();
    expect(
      screen.getByText(/does not establish MCP connectivity/),
    ).toBeInTheDocument();
  });

  it("renders stale registrations separately from active processes", () => {
    render(
      <RuntimeExecutionDetails
        componentId="context7"
        sessions={[{ ...active, state: "stale", pid: undefined }]}
      />,
    );

    expect(screen.getByText("Stale registration")).toBeInTheDocument();
    expect(screen.getByText(/Process presence/)).toHaveTextContent(
      "0 active execution processes.",
    );
  });
});
