import { proxyMutation } from "@/lib/backend-proxy";

export async function POST(
  request: Request,
  context: { params: Promise<{ stackId: string; componentId: string }> },
) {
  const { stackId, componentId } = await context.params;
  return proxyMutation(
    request,
    `/api/v1/stacks/${encodeURIComponent(stackId)}/components/${encodeURIComponent(componentId)}/lifecycle-actions`,
  );
}
