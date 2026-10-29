import { proxyMutation } from "@/lib/backend-proxy";

export async function PUT(
  request: Request,
  context: { params: Promise<{ profileId: string }> },
) {
  const { profileId } = await context.params;
  return proxyMutation(
    request,
    `/api/v1/tunnel-profiles/${encodeURIComponent(profileId)}`,
  );
}

export async function DELETE(
  request: Request,
  context: { params: Promise<{ profileId: string }> },
) {
  const { profileId } = await context.params;
  return proxyMutation(
    request,
    `/api/v1/tunnel-profiles/${encodeURIComponent(profileId)}`,
  );
}
