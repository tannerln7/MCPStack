import { ArrowLeft } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { DeleteResourceDialog } from "@/components/delete-resource-dialog";
import { PageContainer } from "@/components/page-container";
import { PageHeader } from "@/components/page-header";
import { SourceMetadata } from "@/components/source-metadata";
import { StackCreationForm } from "@/components/stack-creation-form";
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
  ApiNotFoundError,
  getEditableStackSource,
  getStack,
  getTunnelProfiles,
} from "@/lib/api";
import type { EditableStackSource, StackView } from "@/lib/contracts/types";

export const dynamic = "force-dynamic";

export const metadata: Metadata = { title: "Edit configuration" };

export default async function EditStackPage({
  params,
}: {
  params: Promise<{ stackId: string }>;
}) {
  const { stackId } = await params;
  let source: EditableStackSource;
  let stack: StackView;
  try {
    [source, stack] = await Promise.all([
      getEditableStackSource(stackId),
      getStack(stackId),
    ]);
  } catch (error) {
    if (error instanceof ApiNotFoundError) notFound();
    throw error;
  }
  const associatedTunnels = (await getTunnelProfiles()).filter(
    (profile) => profile.associatedStackId === stackId && profile.id,
  );
  return (
    <PageContainer>
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
                  {source.stackName}
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>Edit configuration</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        }
        title="Edit configuration"
        description="Edit the Stack through generated fields, review the resulting YAML, and save with validation and revision protection."
        aside={<SourceMetadata source={source.source} />}
      />
      <div className="mt-6">
        <Link
          href={`/stacks/${stackId}`}
          className={buttonVariants({ variant: "ghost" })}
        >
          <ArrowLeft data-icon="inline-start" />
          Back to stack
        </Link>
      </div>
      <StackCreationForm source={source} />
      <div className="mt-8">
        <DeleteResourceDialog
          title={`Delete ${source.stackName}?`}
          description="All managed Components are stopped, associated tunnel profiles are removed, and then the Stack source is deleted. Session-owned stdio processes are not force-stopped."
          items={[
            ...stack.configuration.components.map((component) => ({
              id: component.id,
              label: `Component: ${component.name}`,
            })),
            ...associatedTunnels.map((profile) => ({
              id: profile.id ?? profile.path,
              label: "Associated tunnel profile",
            })),
          ]}
          endpoint={`/api/stacks/${encodeURIComponent(stackId)}`}
          originalRevision={source.source.revision}
          redirectTo="/stacks"
        />
      </div>
    </PageContainer>
  );
}
