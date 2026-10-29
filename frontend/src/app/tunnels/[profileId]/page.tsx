import { FilePenLine } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PageContainer } from "@/components/page-container";
import { PageHeader } from "@/components/page-header";
import { RecentLogsPanel } from "@/components/recent-logs";
import { lifecycleTone, StatusChip } from "@/components/status-chip";
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
  ApiNotFoundError,
  getTunnelProfile,
  getTunnelProfileLogs,
} from "@/lib/api";
import type { TunnelProfile } from "@/lib/contracts/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Tunnel profile" };

export default async function TunnelProfilePage({
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
  const logs = await getTunnelProfileLogs(profileId);
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
                <BreadcrumbPage>{profile.id}</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        }
        title={profile.id ?? profile.path}
        description="OpenAI remote tunnel profile, lifecycle state, target, and recent managed logs."
        aside={
          <Link
            href={`/tunnels/${profileId}/edit`}
            className={buttonVariants({ variant: "outline" })}
          >
            <FilePenLine data-icon="inline-start" />
            Edit
          </Link>
        }
      />
      <div className="mt-8 grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(20rem,0.7fr)]">
        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>Profile</CardTitle>
            <CardDescription>
              Durable tunnel-client configuration.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid min-w-0 gap-3 text-sm">
            <p>
              <span className="font-medium">State:</span>{" "}
              <StatusChip
                label={profile.lifecycle?.state ?? "not observed"}
                tone={lifecycleTone(profile.lifecycle?.state)}
              />
            </p>
            <p>
              <span className="font-medium">Tunnel ID:</span>{" "}
              <span className="break-all font-mono text-xs">
                {profile.tunnelId}
              </span>
            </p>
            <p>
              <span className="font-medium">Target:</span>{" "}
              <Badge variant="outline">{profile.target?.kind}</Badge>
            </p>
            <p className="break-all font-mono text-xs text-muted-foreground">
              {profile.target?.command ?? profile.target?.url}
            </p>
            {profile.associatedStackId ? (
              <p>
                <span className="font-medium">Stack:</span>{" "}
                <Link
                  href={`/stacks/${profile.associatedStackId}`}
                  className="hover:underline"
                >
                  {profile.associatedStackId}
                </Link>
              </p>
            ) : null}
            <p>
              <span className="font-medium">Channel:</span>{" "}
              {profile.target?.channel}
            </p>
            <p className="break-all">
              <span className="font-medium">Tunnel API:</span> {profile.baseUrl}
            </p>
            <p>
              <span className="font-medium">Health listener:</span>{" "}
              {profile.healthListenAddr}
            </p>
          </CardContent>
        </Card>
        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>Lifecycle</CardTitle>
            <CardDescription>
              Managed independently from the target Stack.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <TunnelProfileControls
              profileId={profileId}
              initialObservation={profile.lifecycle}
            />
          </CardContent>
        </Card>
      </div>
      <Card className="mt-5 min-w-0">
        <CardHeader>
          <CardTitle>Logs</CardTitle>
          <CardDescription>
            Recent logs from this tunnel's MCPStack-managed service.
          </CardDescription>
        </CardHeader>
        <CardContent className="min-w-0">
          <RecentLogsPanel
            initialLogs={logs}
            refreshPath={`/api/tunnel-profiles/${encodeURIComponent(profileId)}/logs`}
            downloadName={`${profileId}-logs.txt`}
            emptyMessage="No recent tunnel logs."
          />
        </CardContent>
      </Card>
    </PageContainer>
  );
}
