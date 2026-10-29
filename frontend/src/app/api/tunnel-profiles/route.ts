import { proxyMutation } from "@/lib/backend-proxy";

export async function POST(request: Request) {
  return proxyMutation(request, "/api/v1/tunnel-profiles");
}
