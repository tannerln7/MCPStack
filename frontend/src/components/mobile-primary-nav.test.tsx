import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MobilePrimaryNav } from "@/components/mobile-primary-nav";

vi.mock("next/navigation", () => ({ usePathname: () => "/stacks" }));
vi.mock("next-themes", () => ({
  useTheme: () => ({ theme: "system", setTheme: vi.fn() }),
}));

afterEach(cleanup);

describe("MCPStack mobile navigation", () => {
  it("shows the product name and a branded navigation drawer", async () => {
    render(<MobilePrimaryNav />);

    expect(screen.getByRole("link", { name: "MCPStack" })).toHaveAttribute(
      "href",
      "/stacks",
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Open primary navigation" }),
    );
    expect(
      await screen.findByRole("heading", { name: "MCPStack" }),
    ).toBeInTheDocument();
    expect(screen.getByText("MCPStack navigation")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Stacks" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Tunnels" })).toBeInTheDocument();
  });
});
