import { describe, expect, it } from "vitest";

import {
  allowedMutationOrigins,
  mutationOriginAllowed,
} from "@/lib/mutation-origin";

describe("mutation origins", () => {
  it("retains loopback and accepts configured exact HTTPS origins", () => {
    const origins = allowedMutationOrigins("https://mcp.example.com");

    expect(origins.has("http://127.0.0.1:3100")).toBe(true);
    expect(origins.has("https://mcp.example.com")).toBe(true);
    expect(
      mutationOriginAllowed(
        "https://mcp.example.com",
        "https://mcp.example.com",
      ),
    ).toBe(true);
    expect(
      mutationOriginAllowed(
        "https://attacker.example",
        "https://mcp.example.com",
      ),
    ).toBe(false);
  });

  it.each([
    "https://mcp.example.com/",
    "https://user@example.com",
    "https://example.com/path",
    "javascript:alert(1)",
  ])("rejects a value that is not an exact HTTP origin: %s", (origin) => {
    expect(() => allowedMutationOrigins(origin)).toThrow(
      /exact HTTP\(S\) origins/,
    );
  });
});
