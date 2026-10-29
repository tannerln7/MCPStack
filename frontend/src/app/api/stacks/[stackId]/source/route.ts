import { proxyMutation } from "@/lib/backend-proxy";

export async function PUT(
  request: Request,
  context: { params: Promise<{ stackId: string }> },
) {
  const { stackId } = await context.params;
  return proxyMutation(
    request,
    `/api/v1/stacks/${encodeURIComponent(stackId)}/source`,
  );
}
