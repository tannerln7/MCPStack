import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LifecycleControls } from "@/components/lifecycle-controls";
import type { ComponentLifecycle } from "@/lib/contracts/types";

const lifecycle: ComponentLifecycle = {
  eligible: true,
  actions: ["start", "stop", "restart"],
  observation: {
    componentId: "app",
    provider: "systemd-user",
    unitId: "mcp-stack-app.service",
    state: "inactive",
    observedAt: "2026-08-22T00:00:00Z",
    detail: "No active unit is loaded.",
    intentionallyActive: false,
    bootEnabled: false,
    result: null,
  },
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("LifecycleControls", () => {
  it("shows the available start action, boot state, and ANSI-safe logs", () => {
    render(
      <LifecycleControls
        stackId="demo"
        componentId="app"
        initialLifecycle={lifecycle}
        initialLogs={{
          componentId: "app",
          lines: ["started"],
          truncated: false,
        }}
      />,
    );
    expect(screen.getByRole("button", { name: "Start" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Stop" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Restart" })).toBeDisabled();
    expect(screen.getByText("Boot enabled: no")).toBeInTheDocument();
    expect(screen.getByText("started")).toBeInTheDocument();
  });

  it("submits a bounded lifecycle action", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...lifecycle.observation,
          state: "active",
          detail: "active/running",
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ componentId: "app", lines: [], truncated: false }),
      });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <LifecycleControls
        stackId="demo"
        componentId="app"
        initialLifecycle={lifecycle}
        initialLogs={null}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Start" }));
    expect(await screen.findByText("active/running")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Start" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Restart" })).toBeEnabled();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/stacks/demo/components/app/lifecycle-actions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ action: "start" }),
      }),
    );
  });

  it("submits stop as the primary action for an active component", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...lifecycle.observation,
          state: "inactive",
          detail: "inactive/dead",
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ componentId: "app", lines: [], truncated: false }),
      });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <LifecycleControls
        stackId="demo"
        componentId="app"
        initialLifecycle={{
          ...lifecycle,
          observation: {
            componentId: "app",
            provider: "systemd-user",
            unitId: "mcp-stack-app.service",
            state: "active",
            observedAt: "2026-08-22T00:00:00Z",
            detail: "active/running",
            intentionallyActive: true,
            bootEnabled: false,
            result: null,
          },
        }}
        initialLogs={null}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Stop" }));

    expect(await screen.findByText("inactive/dead")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/stacks/demo/components/app/lifecycle-actions",
      expect.objectContaining({ body: JSON.stringify({ action: "stop" }) }),
    );
  });

  it("shows a structured mutation-boundary error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({
          detail: {
            code: "origin-rejected",
            message: "Mutation origin was rejected",
          },
        }),
      }),
    );
    render(
      <LifecycleControls
        stackId="demo"
        componentId="app"
        initialLifecycle={lifecycle}
        initialLogs={null}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Start" }));

    expect(
      await screen.findByText("Mutation origin was rejected"),
    ).toBeInTheDocument();
  });
});
