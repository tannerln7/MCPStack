import { proxyMutation } from "@/lib/backend-proxy";

export async function PUT(request: Request) {
  return proxyMutation(request, "/api/v1/tunnel-client/credential");
}
