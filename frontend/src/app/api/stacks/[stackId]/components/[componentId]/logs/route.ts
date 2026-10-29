import { proxyGet } from "@/lib/backend-proxy";

export async function GET(
  request: Request,
  context: { params: Promise<{ stackId: string; componentId: string }> },
) {
  const { stackId, componentId } = await context.params;
  const limit = new URL(request.url).searchParams.get("limit") ?? "100";
  return proxyGet(
    `/api/v1/stacks/${encodeURIComponent(stackId)}/components/${encodeURIComponent(componentId)}/logs?limit=${encodeURIComponent(limit)}`,
  );
}
