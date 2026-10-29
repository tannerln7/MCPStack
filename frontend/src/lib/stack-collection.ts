import type {
  ComponentStatus,
  StackSummary,
  StackView,
} from "@/lib/contracts/types";
import { componentSubject, type SubjectKind } from "@/lib/domain";

export type StackTransport = "stdio" | "streamable-http";
export type StackSort = "name" | "status" | "type";
export type HealthState = "healthy" | "unhealthy" | "not-observed";

export type StackCollectionItem = StackSummary & {
  componentTypes: SubjectKind[];
  transports: StackTransport[];
  healthState: HealthState;
  statuses: ComponentStatus[];
  searchText: string;
};

export const componentStatusLabels: Record<ComponentStatus, string> = {
  "not-observed": "Not observed",
  starting: "Starting",
  running: "Running process",
  available: "Available",
  degraded: "Degraded",
  unavailable: "Unavailable",
  stopped: "Stopped",
};

const statusSortOrder: Record<ComponentStatus, number> = {
  running: 0,
  available: 1,
  starting: 2,
  degraded: 3,
  unavailable: 4,
  stopped: 5,
  "not-observed": 6,
};

function uniqueSorted<T extends string>(values: T[]): T[] {
  return [...new Set(values)].sort((left, right) => left.localeCompare(right));
}

function executableIdentifier(
  executable: StackView["configuration"]["commands"][number]["executable"],
) {
  if ("name" in executable) return executable.name;
  if ("path" in executable) return executable.path.split(/[\\/]/).at(-1);
  return "image-entrypoint";
}

function isPackageOrImageIdentifier(value: string) {
  return (
    value.includes("mcp") ||
    value.startsWith("@") ||
    value.includes("@") ||
    (value.includes("/") && !value.startsWith("/"))
  );
}

export function toStackCollectionItem(
  summary: StackSummary,
  stack: StackView,
): StackCollectionItem {
  const { configuration, observations } = stack;
  const componentTypes = uniqueSorted(
    configuration.components.map(
      (component) => componentSubject(component).kind,
    ),
  );
  const transports = uniqueSorted(
    configuration.transports.map((transport) => transport.kind),
  );
  const observedStatuses = new Map(
    observations.components.map((item) => [item.componentId, item.status]),
  );
  const statuses = uniqueSorted(
    configuration.components.map(
      (component) => observedStatuses.get(component.id) ?? "not-observed",
    ),
  ).sort((left, right) => statusSortOrder[left] - statusSortOrder[right]);
  const healthStates = observations.healthObservations.map(
    (item) => item.status,
  );
  const healthState: HealthState = healthStates.includes("failing")
    ? "unhealthy"
    : healthStates.includes("passing")
      ? "healthy"
      : "not-observed";
  const commandIdentifiers = configuration.commands.flatMap((command) => [
    executableIdentifier(command.executable),
    ...command.args.filter(isPackageOrImageIdentifier),
  ]);
  const containerIdentifiers = configuration.runtimes.flatMap((runtime) =>
    runtime.kind === "container"
      ? [runtime.engine, runtime.image, runtime.version]
      : [],
  );
  const searchText = [
    summary.id,
    summary.name,
    summary.description,
    ...componentTypes,
    ...transports,
    ...configuration.components.flatMap((component) => [
      component.id,
      component.name,
      component.description,
    ]),
    ...commandIdentifiers,
    ...containerIdentifiers,
  ]
    .filter((value): value is string => Boolean(value))
    .join(" ")
    .toLocaleLowerCase();

  return {
    ...summary,
    componentTypes,
    transports,
    healthState,
    statuses,
    searchText,
  };
}

export function compareStackCollectionItems(
  left: StackCollectionItem,
  right: StackCollectionItem,
  sort: StackSort,
) {
  if (sort === "type") {
    const typeComparison = left.componentTypes
      .join(",")
      .localeCompare(right.componentTypes.join(","));
    if (typeComparison !== 0) return typeComparison;
  }
  if (sort === "status") {
    const statusComparison =
      statusSortOrder[left.statuses[0] ?? "not-observed"] -
      statusSortOrder[right.statuses[0] ?? "not-observed"];
    if (statusComparison !== 0) return statusComparison;
  }
  return left.name.localeCompare(right.name);
}
