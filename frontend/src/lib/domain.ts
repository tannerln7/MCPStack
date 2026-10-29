import type {
  ComponentObservation,
  StackComponent,
  StackConfiguration,
} from "@/lib/contracts/types";

export type SubjectKind = "MCP server" | "Application" | "Tunnel";

export function componentSubject(component: StackComponent): {
  kind: SubjectKind;
  reference: string;
} {
  if ("mcpServerRef" in component.subject) {
    return { kind: "MCP server", reference: component.subject.mcpServerRef };
  }
  if ("applicationRef" in component.subject) {
    return { kind: "Application", reference: component.subject.applicationRef };
  }
  return { kind: "Tunnel", reference: component.subject.tunnelRef };
}

export function findObservation(
  componentId: string,
  observations: ComponentObservation[],
): ComponentObservation {
  return (
    observations.find(
      (observation) => observation.componentId === componentId,
    ) ?? {
      componentId,
      status: "not-observed",
      observedAt: new Date(0).toISOString(),
      detail: "No runtime observer has reported this component.",
    }
  );
}

export function linkedResources(
  configuration: StackConfiguration,
  component: StackComponent,
) {
  const subject = componentSubject(component);
  if (subject.kind === "MCP server") {
    const server = configuration.mcpServers.find(
      (item) => item.id === subject.reference,
    );
    const transport = configuration.transports.find(
      (item) => item.id === server?.transportRef,
    );
    const command =
      transport && "commandRef" in transport
        ? configuration.commands.find(
            (item) => item.id === transport.commandRef,
          )
        : undefined;
    const runtime = command
      ? configuration.runtimes.find((item) => item.id === command.runtimeRef)
      : undefined;
    return [
      server && { label: "MCP server", definition: "mcpServer", value: server },
      transport && {
        label: "Transport",
        definition: "transport",
        value: transport,
      },
      command && { label: "Command", definition: "command", value: command },
      runtime && { label: "Runtime", definition: "runtime", value: runtime },
    ].filter(Boolean);
  }
  if (subject.kind === "Application") {
    const application = configuration.applications.find(
      (item) => item.id === subject.reference,
    );
    const command = configuration.commands.find(
      (item) => item.id === application?.processCommandRef,
    );
    const endpoints = configuration.endpoints.filter((item) =>
      application?.providedEndpointRefs.includes(item.id),
    );
    return [
      application && {
        label: "Application",
        definition: "application",
        value: application,
      },
      command && { label: "Command", definition: "command", value: command },
      ...endpoints.map((endpoint) => ({
        label: "Endpoint",
        definition: "endpoint",
        value: endpoint,
      })),
    ].filter(Boolean);
  }
  const tunnel = configuration.tunnels.find(
    (item) => item.id === subject.reference,
  );
  const command = configuration.commands.find(
    (item) => item.id === tunnel?.clientCommandRef,
  );
  const endpoint = configuration.endpoints.find(
    (item) => item.id === tunnel?.targetEndpointRef,
  );
  return [
    tunnel && { label: "Tunnel", definition: "tunnel", value: tunnel },
    endpoint && {
      label: "Target endpoint",
      definition: "endpoint",
      value: endpoint,
    },
    command && { label: "Command", definition: "command", value: command },
  ].filter(Boolean);
}
