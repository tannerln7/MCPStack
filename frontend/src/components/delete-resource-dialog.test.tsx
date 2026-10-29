import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DeleteResourceDialog } from "@/components/delete-resource-dialog";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

afterEach(cleanup);

describe("DeleteResourceDialog", () => {
  it("lists every affected component before confirmation", async () => {
    render(
      <DeleteResourceDialog
        title="Delete Ghidra?"
        description="Delete the operational unit."
        items={[
          { id: "headless", label: "Component: Headless server" },
          { id: "bridge", label: "Component: MCP bridge" },
          { id: "remote", label: "Associated tunnel profile" },
        ]}
        endpoint="/api/stacks/ghidra"
        originalRevision={"a".repeat(64)}
        redirectTo="/stacks"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(
      await screen.findByText("Component: Headless server"),
    ).toBeInTheDocument();
    expect(screen.getByText("Component: MCP bridge")).toBeInTheDocument();
    expect(screen.getByText("Associated tunnel profile")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Confirm delete" }),
    ).toBeInTheDocument();
  });
});
