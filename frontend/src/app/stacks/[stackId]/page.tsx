import { ArrowRight, FilePenLine, RadioTower } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CollapsibleSection } from "@/components/collapsible-section";
import { ObservationRefresh } from "@/components/observation-refresh";
import { PageContainer } from "@/components/page-container";
import { PageHeader } from "@/components/page-header";
import { RelationshipView } from "@/components/relationship-view";
import { SourceMetadata } from "@/components/source-metadata";
import { StatusBadge } from "@/components/status-badge";
import { TunnelProfileControls } from "@/components/tunnel-profile-controls";
import { Badge } from "@/components/ui/badge";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiNotFoundError, getStack, getTunnelProfiles } from "@/lib/api";
import type { StackView } from "@/lib/contracts/types";
import { componentSubject, findObservation } from "@/lib/domain";
import { configurationRelationships } from "@/lib/relationships";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ stackId: string }>;
}): Promise<Metadata> {
  const { stackId } = await params;
  try {
    return { title: (await getStack(stackId)).configuration.name };
  } catch {
    return { title: "Stack" };
  }
}

export default async function StackPage({
  params,
}: {
  params: Promise<{ stackId: string }>;
}) {
  const { stackId } = await params;
  let stack: StackView;
  try {
    stack = await getStack(stackId);
  } catch (error) {
    if (error instanceof ApiNotFoundError) notFound();
    throw error;
  }
  const tunnelProfiles = (await getTunnelProfiles()).filter(
    (profile) => profile.associatedStackId === stackId,
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
                <BreadcrumbPage>{stack.configuration.name}</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        }
        title={stack.configuration.name}
        description={stack.configuration.description}
        aside={
          <div className="grid justify-items-start gap-2 sm:justify-items-end">
            <Badge variant="outline" className="rounded-md font-mono">
              rev {stack.observations.configurationRevision.slice(0, 8)}
            </Badge>
            <SourceMetadata source={stack.source} compact />
            <Link
              href={`/stacks/${stackId}/edit`}
              className={buttonVariants({ variant: "outline" })}
            >
              <FilePenLine data-icon="inline-start" />
              Edit configuration
            </Link>
          </div>
        }
      />
      <Card className="mt-8">
        <CardHeader className="border-b">
          <CardTitle>Components</CardTitle>
          <CardDescription>
            Configured roles in this stack. Select any row to inspect its
            schema-backed configuration.
          </CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          <div className="hidden md:block">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Runtime status</TableHead>
                  <TableHead>
                    <span className="sr-only">Open</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stack.configuration.components.map((component) => {
                  const subject = componentSubject(component);
                  const observation = findObservation(
                    component.id,
                    stack.observations.components,
                  );
                  return (
                    <TableRow key={component.id}>
                      <TableCell>
                        <Link
                          href={`/stacks/${stackId}/components/${component.id}`}
                          className="font-medium hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          {component.name}
                        </Link>
                        <p className="mt-0.5 font-mono text-xs text-muted-foreground">
                          {component.id}
                        </p>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary" className="rounded-md">
                          {subject.kind}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={observation.status} />
                      </TableCell>
                      <TableCell className="text-right">
                        <Link
                          href={`/stacks/${stackId}/components/${component.id}`}
                          aria-label={`Open ${component.name}`}
                          className="inline-flex rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <ArrowRight aria-hidden="true" className="size-4" />
                        </Link>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
          <div className="grid divide-y md:hidden">
            {stack.configuration.components.map((component) => {
              const subject = componentSubject(component);
              const observation = findObservation(
                component.id,
                stack.observations.components,
              );
              return (
                <Link
                  key={component.id}
                  href={`/stacks/${stackId}/components/${component.id}`}
                  className="grid min-w-0 gap-3 px-5 py-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                >
                  <div className="flex min-w-0 items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-medium">{component.name}</p>
                      <p className="mt-0.5 break-all font-mono text-xs text-muted-foreground">
                        {component.id}
                      </p>
                    </div>
                    <ArrowRight
                      aria-hidden="true"
                      className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                    />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="secondary" className="rounded-md">
                      {subject.kind}
                    </Badge>
                    <StatusBadge status={observation.status} />
                  </div>
                </Link>
              );
            })}
          </div>
        </CardContent>
      </Card>
      <Card className="mt-8">
        <CardHeader className="border-b">
          <CardTitle>OpenAI remote tunnels</CardTitle>
          <CardDescription>
            Independent outbound tunnel-client profiles associated with this
            Stack. Starting a tunnel does not start or persist the stdio MCP
            server outside the tunnel-owned session.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          {tunnelProfiles.length ? (
            tunnelProfiles.map((profile) =>
              profile.id ? (
                <div
                  key={profile.id}
                  className="grid gap-3 rounded-lg border p-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center"
                >
                  <div className="min-w-0">
                    <p className="font-medium">{profile.id}</p>
                    <p className="mt-1 break-all font-mono text-xs text-muted-foreground">
                      {profile.target?.channel ?? "main"} · {profile.tunnelId}
                    </p>
                  </div>
                  <TunnelProfileControls
                    profileId={profile.id}
                    initialObservation={profile.lifecycle}
                    compact
                  />
                </div>
              ) : null,
            )
          ) : (
            <div className="flex flex-col items-start justify-between gap-4 rounded-lg border border-dashed p-5 sm:flex-row sm:items-center">
              <div>
                <p className="font-medium">No remote tunnel configured</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Create a profile preselected for this Stack, then start it
                  explicitly.
                </p>
              </div>
              <Link
                href={`/tunnels/new?stack=${encodeURIComponent(stackId)}`}
                className={buttonVariants()}
              >
                <RadioTower data-icon="inline-start" />
                Add remote tunnel
              </Link>
            </div>
          )}
        </CardContent>
      </Card>
      <CollapsibleSection
        className="mt-8"
        title="Configuration relationships"
        description="Read-only links between dependencies, identities, endpoints, exposure, observation, and execution definitions."
      >
        <RelationshipView
          relationships={configurationRelationships(stack.configuration)}
          stackId={stackId}
        />
      </CollapsibleSection>
    </PageContainer>
  );
}
