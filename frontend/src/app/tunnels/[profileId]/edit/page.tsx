import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { DeleteResourceDialog } from "@/components/delete-resource-dialog";
import { PageContainer } from "@/components/page-container";
import { PageHeader } from "@/components/page-header";
import { TunnelProfileForm } from "@/components/tunnel-profile-form";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { ApiNotFoundError, getStacks, getTunnelProfile } from "@/lib/api";
import type { TunnelProfile } from "@/lib/contracts/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Edit tunnel profile" };

export default async function EditTunnelProfilePage({
  params,
}: {
  params: Promise<{ profileId: string }>;
}) {
  const { profileId } = await params;
  let profile: TunnelProfile;
  try {
    profile = await getTunnelProfile(profileId);
  } catch (error) {
    if (error instanceof ApiNotFoundError) notFound();
    throw error;
  }
  const stacks = await getStacks();
  if (!profile.revision) notFound();
  return (
    <PageContainer>
      <PageHeader
        eyebrow={
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink render={<Link href="/tunnels" />}>
                  Tunnels
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbLink
                  render={<Link href={`/tunnels/${profileId}`} />}
                >
                  {profileId}
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>Edit</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        }
        title="Edit tunnel profile"
        description="Update the profile with revision protection or remove it after reviewing the affected resource."
      />
      <TunnelProfileForm stacks={stacks.stacks} initialProfile={profile} />
      <div className="mt-8">
        <DeleteResourceDialog
          title={`Delete ${profileId}?`}
          description="The tunnel is stopped before its profile file is deleted."
          items={[{ id: profileId, label: "Tunnel profile" }]}
          endpoint={`/api/tunnel-profiles/${encodeURIComponent(profileId)}`}
          originalRevision={profile.revision}
          redirectTo="/tunnels"
        />
      </div>
    </PageContainer>
  );
}
