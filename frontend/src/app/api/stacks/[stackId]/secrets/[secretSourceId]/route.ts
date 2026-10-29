import { proxyMutation } from "@/lib/backend-proxy";

export async function PUT(
  request: Request,
  context: { params: Promise<{ stackId: string; secretSourceId: string }> },
) {
  const { stackId, secretSourceId } = await context.params;
  return proxyMutation(
    request,
    `/api/v1/stacks/${encodeURIComponent(stackId)}/secrets/${encodeURIComponent(secretSourceId)}`,
  );
}

export async function DELETE(
  request: Request,
  context: { params: Promise<{ stackId: string; secretSourceId: string }> },
) {
  const { stackId, secretSourceId } = await context.params;
  return proxyMutation(
    request,
    `/api/v1/stacks/${encodeURIComponent(stackId)}/secrets/${encodeURIComponent(secretSourceId)}`,
  );
}
