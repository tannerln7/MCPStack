import type { StackComponent, StackConfiguration } from "@/lib/contracts/types";

export type ResourceKind =
  | "application"
  | "command"
  | "component"
  | "endpoint"
  | "environment source"
  | "health check"
  | "lifecycle policy"
  | "log source"
  | "MCP server"
  | "runtime"
  | "secret source"
  | "transport"
  | "tunnel";

export type RelationshipCategory =
  | "Dependency"
  | "Exposure"
  | "Observation"
  | "Ownership"
  | "Provision"
  | "Runtime";

export interface ResourceNode {
  id: string;
  kind: ResourceKind;
  label: string;
  componentId?: string;
}

export interface ResourceRelationship {
  category: RelationshipCategory;
  from: ResourceNode;
  relation: string;
  to: ResourceNode;
}

const nodeKey = (node: ResourceNode) => `${node.kind}:${node.id}`;

function namedNode(
  kind: ResourceKind,
  value: { id: string; name?: string },
  componentId?: string,
): ResourceNode {
  return { id: value.id, kind, label: value.name ?? value.id, componentId };
}

function subjectNode(
  configuration: StackConfiguration,
  component: StackComponent,
): ResourceNode | undefined {
  if ("mcpServerRef" in component.subject) {
    const reference = component.subject.mcpServerRef;
    const item = configuration.mcpServers.find(({ id }) => id === reference);
    return item && namedNode("MCP server", item, component.id);
  }
  if ("applicationRef" in component.subject) {
    const reference = component.subject.applicationRef;
    const item = configuration.applications.find(({ id }) => id === reference);
    return item && namedNode("application", item, component.id);
  }
  const reference = component.subject.tunnelRef;
  const item = configuration.tunnels.find(({ id }) => id === reference);
  return item && namedNode("tunnel", item, component.id);
}

export function configurationRelationships(
  configuration: StackConfiguration,
): ResourceRelationship[] {
  const relationships: ResourceRelationship[] = [];
  const add = (
    category: RelationshipCategory,
    from: ResourceNode | undefined,
    relation: string,
    to: ResourceNode | undefined,
  ) => {
    if (from && to) relationships.push({ category, from, relation, to });
  };
  const componentNode = (id: string) => {
    const component = configuration.components.find((item) => item.id === id);
    return component && namedNode("component", component, component.id);
  };
  const commandNode = (id?: string) => {
    const item = configuration.commands.find((value) => value.id === id);
    return item && namedNode("command", item);
  };
  const endpointNode = (id?: string) => {
    const item = configuration.endpoints.find((value) => value.id === id);
    return item && namedNode("endpoint", item);
  };
  const applicationNode = (id?: string) => {
    const item = configuration.applications.find((value) => value.id === id);
    const owner = configuration.components.find(
      (component) =>
        "applicationRef" in component.subject &&
        component.subject.applicationRef === item?.id,
    );
    return item && namedNode("application", item, owner?.id);
  };

  for (const component of configuration.components) {
    add(
      "Ownership",
      namedNode("component", component, component.id),
      "represents",
      subjectNode(configuration, component),
    );
    const policy = configuration.lifecyclePolicies.find(
      ({ id }) => id === component.lifecyclePolicyRef,
    );
    add(
      "Ownership",
      namedNode("component", component, component.id),
      "declares policy",
      policy && namedNode("lifecycle policy", policy),
    );
    for (const id of component.healthCheckRefs) {
      const item = configuration.healthChecks.find((value) => value.id === id);
      add(
        "Observation",
        namedNode("component", component, component.id),
        "is observed by",
        item && namedNode("health check", item),
      );
    }
    for (const id of component.logSourceRefs) {
      const item = configuration.logSources.find((value) => value.id === id);
      add(
        "Observation",
        namedNode("component", component, component.id),
        "emits through",
        item && namedNode("log source", item),
      );
    }
  }

  for (const dependency of configuration.dependencies) {
    add(
      "Dependency",
      componentNode(dependency.componentRef),
      `depends on (${dependency.requirement}, ${dependency.strength})`,
      componentNode(dependency.dependsOnRef),
    );
  }

  for (const command of configuration.commands) {
    const commandResource = namedNode("command", command);
    const runtime = configuration.runtimes.find(
      ({ id }) => id === command.runtimeRef,
    );
    add(
      "Runtime",
      commandResource,
      "executes with",
      runtime && namedNode("runtime", runtime),
    );
    for (const binding of command.environment) {
      if ("environmentSourceRef" in binding.valueFrom) {
        const reference = binding.valueFrom.environmentSourceRef;
        const source = configuration.environmentSources.find(
          ({ id }) => id === reference,
        );
        add(
          "Runtime",
          commandResource,
          `consumes ${binding.name}`,
          source && namedNode("environment source", source),
        );
      }
      if ("secretSourceRef" in binding.valueFrom) {
        const reference = binding.valueFrom.secretSourceRef;
        const source = configuration.secretSources.find(
          ({ id }) => id === reference,
        );
        add(
          "Runtime",
          commandResource,
          `consumes ${binding.name}`,
          source && namedNode("secret source", source),
        );
      }
    }
  }

  for (const transport of configuration.transports) {
    const transportResource = namedNode("transport", transport);
    if ("commandRef" in transport) {
      add(
        "Runtime",
        transportResource,
        "launches through",
        commandNode(transport.commandRef),
      );
    } else {
      add(
        "Runtime",
        transportResource,
        "connects to",
        endpointNode(transport.endpointRef),
      );
    }
  }

  for (const server of configuration.mcpServers) {
    const owner = configuration.components.find(
      (component) =>
        "mcpServerRef" in component.subject &&
        component.subject.mcpServerRef === server.id,
    );
    const serverResource = namedNode("MCP server", server, owner?.id);
    const transport = configuration.transports.find(
      ({ id }) => id === server.transportRef,
    );
    add(
      "Provision",
      serverResource,
      "uses",
      transport && namedNode("transport", transport),
    );
    add(
      "Provision",
      applicationNode(server.providedByApplicationRef),
      "provides",
      serverResource,
    );
    add(
      "Provision",
      serverResource,
      "controls",
      applicationNode(server.controlsApplicationRef),
    );
  }

  for (const application of configuration.applications) {
    const resource = applicationNode(application.id);
    add(
      "Runtime",
      resource,
      "starts through",
      commandNode(application.processCommandRef),
    );
    for (const id of application.providedEndpointRefs) {
      add("Provision", resource, "provides endpoint", endpointNode(id));
    }
  }

  for (const tunnel of configuration.tunnels) {
    const owner = configuration.components.find(
      (component) =>
        "tunnelRef" in component.subject &&
        component.subject.tunnelRef === tunnel.id,
    );
    const resource = namedNode("tunnel", tunnel, owner?.id);
    add(
      "Exposure",
      resource,
      "exposes",
      endpointNode(tunnel.targetEndpointRef),
    );
    add(
      "Runtime",
      resource,
      "runs client through",
      commandNode(tunnel.clientCommandRef),
    );
    add(
      "Exposure",
      resource,
      "publishes",
      endpointNode(tunnel.publicEndpointRef),
    );
  }

  const unique = new Map<string, ResourceRelationship>();
  for (const relationship of relationships) {
    unique.set(
      `${relationship.category}:${nodeKey(relationship.from)}:${relationship.relation}:${nodeKey(relationship.to)}`,
      relationship,
    );
  }
  return [...unique.values()];
}

export function componentRelationships(
  configuration: StackConfiguration,
  component: StackComponent,
): ResourceRelationship[] {
  const all = configurationRelationships(configuration);
  const subject = subjectNode(configuration, component);
  const seeds = new Set([
    nodeKey(namedNode("component", component, component.id)),
    ...(subject ? [nodeKey(subject)] : []),
  ]);
  const connected = new Set(seeds);
  let frontier = new Set(seeds);
  for (let depth = 0; depth < 2; depth += 1) {
    const next = new Set<string>();
    for (const { from, to } of all) {
      const fromKey = nodeKey(from);
      const toKey = nodeKey(to);
      if (frontier.has(fromKey) && !connected.has(toKey)) {
        connected.add(toKey);
        if (to.kind !== "component") next.add(toKey);
      }
      if (frontier.has(toKey) && !connected.has(fromKey)) {
        connected.add(fromKey);
        if (from.kind !== "component") next.add(fromKey);
      }
    }
    frontier = next;
  }
  return all.filter(
    ({ from, to }) =>
      connected.has(nodeKey(from)) && connected.has(nodeKey(to)),
  );
}
