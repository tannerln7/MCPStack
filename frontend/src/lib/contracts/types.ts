import type { components, paths } from "./api.generated";

type GeneratedStackConfiguration = components["schemas"]["stack-config.schema"];
type GeneratedRuntimeSnapshot =
  components["schemas"]["runtime-snapshot.schema"];

export type StackConfiguration = Omit<GeneratedStackConfiguration, "$defs">;
export type RuntimeSnapshot = Omit<GeneratedRuntimeSnapshot, "$defs">;
export type StackSummary = components["schemas"]["StackSummary"];
export type StackDiscovery = components["schemas"]["StackDiscovery"];
export type ConfigurationSource = components["schemas"]["ConfigurationSource"];
export type ConfigurationIssue = components["schemas"]["ConfigurationIssue"];
export type ConfigurationDiagnostic =
  components["schemas"]["ConfigurationDiagnostic"];
export type EditableStackSource = components["schemas"]["EditableStackSource"];
export type ConfigurationValidationPreviewRequest =
  components["schemas"]["ConfigurationValidationPreviewRequest"];
export type StackComponent = components["schemas"]["component"];
export type ComponentObservation =
  components["schemas"]["componentObservation"];
export type ComponentStatus = ComponentObservation["status"];
export type ExecutionSessionObservation =
  components["schemas"]["executionSessionObservation"];
export type ConfigurationWriteResult =
  components["schemas"]["ConfigurationWriteResult"];
export type ComponentLifecycle = components["schemas"]["ComponentLifecycle"];
export type LifecycleObservation =
  components["schemas"]["LifecycleObservation"];
export type LifecycleAction =
  components["schemas"]["LifecycleActionRequest"]["action"];
export type RecentLogs = components["schemas"]["RecentLogs"];
export type HealthObservation = components["schemas"]["healthObservation"];

export interface TunnelClientInfo {
  installed: boolean;
  executable: string;
  version: string | null;
  profileDirectory: string;
  credentialState: "configured" | "missing" | "inaccessible";
}

export interface TunnelProfile {
  id: string | null;
  path: string;
  valid: boolean;
  diagnostic: string | null;
  revision: string | null;
  tunnelId: string | null;
  baseUrl: string | null;
  target: {
    kind: "stdio" | "http";
    channel: string;
    command: string | null;
    url: string | null;
  } | null;
  healthListenAddr: string | null;
  logLevel: string | null;
  logFormat: string | null;
  associatedStackId: string | null;
  lifecycle: LifecycleObservation | null;
}

type GeneratedStackView =
  paths["/api/v1/stacks/{stackId}"]["get"]["responses"][200]["content"]["application/json"];
export type StackView = Omit<
  GeneratedStackView,
  "configuration" | "observations"
> & {
  configuration: StackConfiguration;
  observations: RuntimeSnapshot;
};

type GeneratedConfigurationValidationPreview =
  components["schemas"]["ConfigurationValidationPreview"];
export type ConfigurationValidationPreview = Omit<
  GeneratedConfigurationValidationPreview,
  "configuration"
> & {
  configuration: StackConfiguration | null;
};

export interface JsonSchema {
  $ref?: string;
  $defs?: Record<string, JsonSchema>;
  title?: string;
  description?: string;
  type?: string | string[];
  const?: unknown;
  properties?: Record<string, JsonSchema>;
  items?: JsonSchema;
  oneOf?: JsonSchema[];
  [key: string]: unknown;
}
