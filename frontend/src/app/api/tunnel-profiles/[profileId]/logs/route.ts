import { proxyGet } from "@/lib/backend-proxy";

export async function GET(
  _request: Request,
  context: { params: Promise<{ profileId: string }> },
) {
  const { profileId } = await context.params;
  return proxyGet(
    `/api/v1/tunnel-profiles/${encodeURIComponent(profileId)}/logs?limit=100`,
  );
}
