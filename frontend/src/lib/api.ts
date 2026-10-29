import "server-only";

import type {
  ComponentLifecycle,
  ConfigurationValidationPreview,
  ConfigurationValidationPreviewRequest,
  EditableStackSource,
  JsonSchema,
  RecentLogs,
  StackDiscovery,
  StackView,
  TunnelClientInfo,
  TunnelProfile,
} from "@/lib/contracts/types";

const apiBaseUrl = process.env.MCP_STACK_API_URL ?? "http://127.0.0.1:8000";

export class ApiNotFoundError extends Error {}

export class ApiRequestError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  if (response.status === 404) {
    throw new ApiNotFoundError(path);
  }
  if (!response.ok) {
    throw new ApiRequestError(
      response.status,
      `MCPStack API request failed with ${response.status}`,
    );
  }
  return response.json() as Promise<T>;
}

async function postJson<TRequest, TResponse>(
  path: string,
  body: TRequest,
): Promise<TResponse> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: "POST",
    cache: "no-store",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (response.status === 404) {
    throw new ApiNotFoundError(path);
  }
  if (!response.ok) {
    throw new ApiRequestError(
      response.status,
      `MCPStack API request failed with ${response.status}`,
    );
  }
  return response.json() as Promise<TResponse>;
}

export function getStacks() {
  return getJson<StackDiscovery>("/api/v1/stacks");
}

export function getStack(stackId: string) {
  return getJson<StackView>(`/api/v1/stacks/${encodeURIComponent(stackId)}`);
}

export function getEditableStackSource(stackId: string) {
  return getJson<EditableStackSource>(
    `/api/v1/stacks/${encodeURIComponent(stackId)}/source`,
  );
}

export function previewStackConfiguration(
  stackId: string,
  candidate: ConfigurationValidationPreviewRequest,
) {
  return postJson<
    ConfigurationValidationPreviewRequest,
    ConfigurationValidationPreview
  >(
    `/api/v1/stacks/${encodeURIComponent(stackId)}/validation-previews`,
    candidate,
  );
}

export function getStackConfigurationContract() {
  return getJson<JsonSchema>("/api/v1/contracts/stack-configuration");
}

export function getTunnelClient() {
  return getJson<TunnelClientInfo>("/api/v1/tunnel-client");
}

export function getTunnelProfiles() {
  return getJson<TunnelProfile[]>("/api/v1/tunnel-profiles");
}

export function getTunnelProfile(profileId: string) {
  return getJson<TunnelProfile>(
    `/api/v1/tunnel-profiles/${encodeURIComponent(profileId)}`,
  );
}

export async function getTunnelProfileLogs(profileId: string) {
  try {
    return await getJson<RecentLogs>(
      `/api/v1/tunnel-profiles/${encodeURIComponent(profileId)}/logs?limit=100`,
    );
  } catch (error) {
    if (error instanceof ApiRequestError) return null;
    throw error;
  }
}

export function getComponentLifecycle(stackId: string, componentId: string) {
  return getJson<ComponentLifecycle>(
    `/api/v1/stacks/${encodeURIComponent(stackId)}/components/${encodeURIComponent(componentId)}/lifecycle`,
  );
}

export async function getComponentLogs(stackId: string, componentId: string) {
  try {
    return await getJson<RecentLogs>(
      `/api/v1/stacks/${encodeURIComponent(stackId)}/components/${encodeURIComponent(componentId)}/logs?limit=100`,
    );
  } catch (error) {
    if (error instanceof ApiRequestError) return null;
    throw error;
  }
}
