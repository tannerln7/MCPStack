import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CollapsibleSection } from "@/components/collapsible-section";
import { ConfigurationViewer } from "@/components/configuration-viewer";
import { HealthDetails } from "@/components/health-details";
import { LifecycleControls } from "@/components/lifecycle-controls";
import { ObservationRefresh } from "@/components/observation-refresh";
import { PageContainer } from "@/components/page-container";
import { PageHeader } from "@/components/page-header";
import { RelationshipView } from "@/components/relationship-view";
import { RuntimeExecutionDetails } from "@/components/runtime-execution-details";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ApiNotFoundError,
  getComponentLifecycle,
  getComponentLogs,
  getStack,
  getStackConfigurationContract,
} from "@/lib/api";
import type { StackView } from "@/lib/contracts/types";
import {
  componentSubject,
  findObservation,
  linkedResources,
} from "@/lib/domain";
import { componentRelationships } from "@/lib/relationships";

export const dynamic = "force-dynamic";

type PageParams = Promise<{ stackId: string; componentId: string }>;

export async function generateMetadata({
  params,
}: {
  params: PageParams;
}): Promise<Metadata> {
  const { stackId, componentId } = await params;
  try {
    const stack = await getStack(stackId);
    return {
      title:
        stack.configuration.components.find((item) => item.id === componentId)
          ?.name ?? "Component",
    };
  } catch {
    return { title: "Component" };
  }
}

export default async function ComponentPage({
  params,
}: {
  params: PageParams;
}) {
  const { stackId, componentId } = await params;
  let stack: StackView;
  try {
    stack = await getStack(stackId);
  } catch (error) {
    if (error instanceof ApiNotFoundError) notFound();
    throw error;
  }
  const component = stack.configuration.components.find(
    (item) => item.id === componentId,
  );
  if (!component) notFound();

  const schema = await getStackConfigurationContract();
  const observation = findObservation(
    component.id,
    stack.observations.components,
  );
  const subject = componentSubject(component);
  const resources = linkedResources(stack.configuration, component);
  const componentExecutions = stack.observations.executionSessions.filter(
    (session) => session.componentId === component.id,
  );
  const activeExecutionCount = componentExecutions.filter(
    (session) => session.state === "active",
  ).length;
  const lifecycle = await getComponentLifecycle(stackId, componentId);
  const recentLogs = lifecycle.eligible
    ? await getComponentLogs(stackId, componentId)
    : null;
  const componentHealthRefs = new Set(component.healthCheckRefs);
  const healthObservations = stack.observations.healthObservations.filter(
    (item) => componentHealthRefs.has(item.healthCheckRef),
  );

  return (
    <PageContainer>
      <ObservationRefresh />
      <PageHeader
        eyebrow={
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink render={<Link href="/stacks" />}>
                  Stacks
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbLink render={<Link href={`/stacks/${stackId}`} />}>
                  {stack.configuration.name}
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>{component.name}</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        }
        title={component.name}
        description={component.description}
        aside={
          <div className="grid justify-items-start gap-2 sm:justify-items-end">
            <div className="grid justify-items-start gap-1 sm:justify-items-end">
              <span className="text-xs text-muted-foreground">
                Runtime status
              </span>
              <StatusBadge status={observation.status} />
            </div>
          </div>
        }
      />

      <div className="mt-8 grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(20rem,0.85fr)]">
        <Card className="min-w-0">
          <CardHeader className="border-b">
            <CardTitle className="flex flex-wrap items-center gap-2">
              Component configuration{" "}
              <Badge variant="secondary" className="rounded-md">
                {subject.kind}
              </Badge>
            </CardTitle>
            <CardDescription>
              Durable desired configuration loaded from the stack document.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ConfigurationViewer
              schema={schema}
              definition="component"
              value={component}
            />
          </CardContent>
        </Card>

        <div className="grid min-w-0 gap-5">
          <Card className="min-w-0">
            <CardHeader className="border-b">
              <CardTitle>Health</CardTitle>
              <CardDescription>
                Bounded configured probes, distinct from provider runtime.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <HealthDetails observations={healthObservations} />
            </CardContent>
          </Card>

          {lifecycle.eligible ? (
            <Card className="min-w-0">
              <CardHeader className="border-b">
                <CardTitle>Lifecycle and logs</CardTitle>
                <CardDescription>
                  Manual systemd user lifecycle. This unit is never boot-enabled
                  automatically.
                </CardDescription>
              </CardHeader>
              <CardContent className="min-w-0">
                <LifecycleControls
                  stackId={stackId}
                  componentId={componentId}
                  initialLifecycle={lifecycle}
                  initialLogs={recentLogs}
                />
              </CardContent>
            </Card>
          ) : null}

          <Card className="min-w-0">
            <CardHeader className="border-b">
              <CardTitle>Runtime status</CardTitle>
              <CardDescription>
                Runtime observations remain separate and are not written back
                into configuration.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="flex items-center justify-between gap-4 rounded-lg border bg-muted/20 p-4">
                <div>
                  <p className="text-sm font-medium">Observation</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {observation.detail}
                  </p>
                </div>
                <StatusBadge status={observation.status} />
              </div>
              <RuntimeExecutionDetails
                componentId={component.id}
                sessions={componentExecutions}
              />
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
                <dt className="text-muted-foreground">Active executions</dt>
                <dd className="text-right font-mono">{activeExecutionCount}</dd>
                <dt className="text-muted-foreground">MCP sessions observed</dt>
                <dd className="text-right font-mono">
                  {
                    stack.observations.mcpSessions.filter(
                      (session) => session.mcpServerRef === subject.reference,
                    ).length
                  }
                </dd>
                <dt className="text-muted-foreground">Health results</dt>
                <dd className="text-right font-mono">
                  {stack.observations.healthObservations.length}
                </dd>
                <dt className="text-muted-foreground">Log streams</dt>
                <dd className="text-right font-mono">
                  {stack.observations.logStreams.length}
                </dd>
              </dl>
            </CardContent>
          </Card>
        </div>
      </div>

      <CollapsibleSection
        className="mt-5"
        title="Linked resources"
        description="Distinct identities referenced by this component."
      >
        <div className="grid gap-4 xl:grid-cols-2">
          {resources.map(
            (resource) =>
              resource && (
                <Card
                  key={`${resource.definition}-${JSON.stringify(resource.value)}`}
                  size="sm"
                >
                  <CardHeader className="border-b">
                    <CardTitle>{resource.label}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ConfigurationViewer
                      schema={schema}
                      definition={resource.definition}
                      value={resource.value}
                    />
                  </CardContent>
                </Card>
              ),
          )}
        </div>
      </CollapsibleSection>

      <CollapsibleSection
        className="mt-5"
        title="Resource relationships"
        description="Generic dependency, provision, exposure, and runtime links for this component and its directly connected resources."
      >
        <RelationshipView
          relationships={componentRelationships(stack.configuration, component)}
          stackId={stackId}
        />
      </CollapsibleSection>
    </PageContainer>
  );
}
