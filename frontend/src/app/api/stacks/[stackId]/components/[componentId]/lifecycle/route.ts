import { proxyGet } from "@/lib/backend-proxy";

export async function GET(
  _request: Request,
  context: { params: Promise<{ stackId: string; componentId: string }> },
) {
  const { stackId, componentId } = await context.params;
  return proxyGet(
    `/api/v1/stacks/${encodeURIComponent(stackId)}/components/${encodeURIComponent(componentId)}/lifecycle`,
  );
}
