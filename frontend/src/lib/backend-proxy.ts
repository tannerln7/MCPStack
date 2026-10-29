import "server-only";

import { mutationOriginAllowed } from "@/lib/mutation-origin";

const apiBaseUrl = process.env.MCP_STACK_API_URL ?? "http://127.0.0.1:8000";
const maximumMutationBytes = 1_100_000;

export async function proxyGet(path: string) {
  return fetch(`${apiBaseUrl}${path}`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
}

export async function proxyMutation(request: Request, path: string) {
  const requestOrigin = request.headers.get("origin");
  if (!mutationOriginAllowed(requestOrigin)) {
    return Response.json(
      {
        detail: {
          code: "origin-rejected",
          message: "Mutation origin was rejected",
        },
      },
      { status: 403 },
    );
  }
  const contentLength = Number(request.headers.get("content-length"));
  if (!Number.isFinite(contentLength) || contentLength > maximumMutationBytes) {
    return Response.json(
      {
        detail: {
          code: "request-too-large",
          message: "Mutation request is too large",
        },
      },
      { status: 413 },
    );
  }
  const body = await request.text();
  if (new TextEncoder().encode(body).byteLength > maximumMutationBytes) {
    return Response.json(
      {
        detail: {
          code: "request-too-large",
          message: "Mutation request is too large",
        },
      },
      { status: 413 },
    );
  }
  return fetch(`${apiBaseUrl}${path}`, {
    method: request.method,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      Origin: requestOrigin,
      "X-MCP-Stack-Mutation": "1",
    },
    body,
  });
}
