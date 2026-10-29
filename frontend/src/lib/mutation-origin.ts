const loopbackOrigins = [
  "http://127.0.0.1:3000",
  "http://localhost:3000",
  "http://[::1]:3000",
  "http://127.0.0.1:3100",
  "http://localhost:3100",
  "http://[::1]:3100",
];

export function allowedMutationOrigins(configuredOrigins = "") {
  const origins = new Set(loopbackOrigins);
  for (const value of configuredOrigins.split(",")) {
    const candidate = value.trim();
    if (!candidate) continue;
    const parsed = new URL(candidate);
    if (
      !["http:", "https:"].includes(parsed.protocol) ||
      parsed.origin !== candidate ||
      parsed.username ||
      parsed.password
    ) {
      throw new Error(
        "MCP_STACK_PUBLIC_ORIGINS must contain comma-separated exact HTTP(S) origins",
      );
    }
    origins.add(candidate);
  }
  return origins;
}

export function mutationOriginAllowed(
  origin: string | null,
  configuredOrigins = process.env.MCP_STACK_PUBLIC_ORIGINS ?? "",
): origin is string {
  return (
    origin !== null && allowedMutationOrigins(configuredOrigins).has(origin)
  );
}
