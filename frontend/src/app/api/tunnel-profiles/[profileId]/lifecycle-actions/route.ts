import { proxyMutation } from "@/lib/backend-proxy";

export async function POST(
  request: Request,
  context: { params: Promise<{ profileId: string }> },
) {
  const { profileId } = await context.params;
  return proxyMutation(
    request,
    `/api/v1/tunnel-profiles/${encodeURIComponent(profileId)}/lifecycle-actions`,
  );
}
