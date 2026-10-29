import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HealthDetails } from "@/components/health-details";

describe("HealthDetails", () => {
  it("keeps passing, failing, and unknown health explicit", () => {
    render(
      <HealthDetails
        observations={[
          {
            healthCheckRef: "pass",
            status: "passing",
            observedAt: "2026-08-22T00:00:00Z",
            reason: "ok",
            latencyMs: 1,
            expiresAt: null,
          },
          {
            healthCheckRef: "fail",
            status: "failing",
            observedAt: "2026-08-22T00:00:00Z",
            reason: "down",
            latencyMs: 2,
            expiresAt: null,
          },
          {
            healthCheckRef: "unknown",
            status: "unknown",
            observedAt: "2026-08-22T00:00:00Z",
            reason: "not probed",
            latencyMs: null,
            expiresAt: null,
          },
        ]}
      />,
    );
    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.getByText("Unhealthy")).toBeInTheDocument();
    expect(screen.getByText("Not observed")).toBeInTheDocument();
  });
});
