import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TunnelProfileControls } from "@/components/tunnel-profile-controls";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("TunnelProfileControls", () => {
  it("keeps profile lifecycle distinct and displays a safe refusal", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({
          detail: {
            code: "credential-missing",
            message: "Tunnel client API key is not configured",
          },
        }),
      }),
    );
    render(
      <TunnelProfileControls
        profileId="docs-tunnel"
        initialObservation={null}
      />,
    );

    expect(screen.getByText("not observed")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Stop" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Restart" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Start" }));

    expect(
      await screen.findByText("Tunnel client API key is not configured"),
    ).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(
      "/api/tunnel-profiles/docs-tunnel/lifecycle-actions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ action: "start" }),
      }),
    );
  });

  it("switches the primary action from stop to start after stopping", async () => {
    const observation = {
      componentId: "docs-tunnel",
      provider: "systemd-user" as const,
      unitId: "mcp-stack-tunnel-docs.service",
      state: "active" as const,
      observedAt: "2026-08-23T00:00:00Z",
      detail: "active/running",
      intentionallyActive: true,
      bootEnabled: false,
      result: null,
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ...observation,
        state: "inactive",
        detail: "inactive/dead",
        intentionallyActive: false,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <TunnelProfileControls
        profileId="docs-tunnel"
        initialObservation={observation}
      />,
    );

    expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Restart" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Stop" }));

    expect(
      await screen.findByText("inactive/dead Boot enabled: no."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/tunnel-profiles/docs-tunnel/lifecycle-actions",
      expect.objectContaining({ body: JSON.stringify({ action: "stop" }) }),
    );
  });
});
