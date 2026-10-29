import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import RootLayout, { metadata } from "./layout";

vi.mock("next/font/google", () => ({
  Geist: () => ({ variable: "font-test" }),
}));
vi.mock("next/navigation", () => ({ usePathname: () => "/stacks" }));
vi.mock("next-themes", () => ({
  ThemeProvider: ({ children }: { children: React.ReactNode }) => children,
  useTheme: () => ({ theme: "system", setTheme: vi.fn() }),
}));

describe("MCPStack application identity", () => {
  it("uses MCPStack in page metadata and the desktop shell", () => {
    expect(metadata.title).toEqual({
      default: "MCPStack",
      template: "%s · MCPStack",
    });
    expect(metadata.description).toContain("Any MCP server. Your setup.");
    const markup = renderToStaticMarkup(
      <RootLayout>
        <p>Example content</p>
      </RootLayout>,
    );
    expect(markup).toContain("<span>MCPStack</span>");
    expect(markup).toContain("Your MCP environment, together.");
  });
});
