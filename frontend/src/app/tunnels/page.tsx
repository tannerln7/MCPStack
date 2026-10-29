import { Plus } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { PageContainer } from "@/components/page-container";
import { PageHeader } from "@/components/page-header";
import { StatusChip } from "@/components/status-chip";
import { TunnelCredentialForm } from "@/components/tunnel-credential-form";
import { TunnelProfileControls } from "@/components/tunnel-profile-controls";
import { Badge } from "@/components/ui/badge";
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
import { getTunnelClient, getTunnelProfiles } from "@/lib/api";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Tunnels" };

export default async function TunnelsPage() {
  const [client, profiles] = await Promise.all([
    getTunnelClient(),
    getTunnelProfiles(),
  ]);
  return (
    <PageContainer>
      <PageHeader
        eyebrow="Outbound MCP exposure"
        title="Tunnels"
        description="Connect an MCPStack service or HTTP endpoint through a remote tunnel. Start and stop each profile independently."
        aside={
          <Link href="/tunnels/new" className={buttonVariants()}>
            <Plus data-icon="inline-start" />
            New profile
          </Link>
        }
      />
      <div className="mt-8 grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Tunnel client{" "}
              <StatusChip
                label={client.installed ? "installed" : "missing"}
                tone={client.installed ? "positive" : "destructive"}
              />
            </CardTitle>
            <CardDescription>
              Versioned executable managed by MCPStack.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm">
            <p>
              <span className="font-medium">Version:</span>{" "}
              {client.version ?? "Unavailable"}
            </p>
            <p className="break-all">
              <span className="font-medium">Executable:</span>{" "}
              {client.executable}
            </p>
            <p className="break-all">
              <span className="font-medium">Profiles:</span>{" "}
              {client.profileDirectory}
            </p>
            <p>
              <span className="font-medium">API key:</span>{" "}
              <StatusChip
                label={client.credentialState}
                tone={
                  client.credentialState === "configured"
                    ? "positive"
                    : "destructive"
                }
              />
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>OpenAI tunnel credential</CardTitle>
            <CardDescription>
              Every profile references the same required environment variable,
              `CONTROL_PLANE_API_KEY`.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <TunnelCredentialForm />
          </CardContent>
        </Card>
      </div>
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Configured profiles</CardTitle>
          <CardDescription>
            Start, stop, and restart each profile independently. Profiles are
            never boot-enabled automatically.
          </CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          {profiles.length ? (
            <>
              <div className="hidden md:block">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Profile</TableHead>
                      <TableHead>Target</TableHead>
                      <TableHead>Stack</TableHead>
                      <TableHead>State and controls</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {profiles.map((profile) => (
                      <TableRow key={profile.path}>
                        <TableCell>
                          {profile.id ? (
                            <Link
                              className="font-medium hover:underline"
                              href={`/tunnels/${profile.id}`}
                            >
                              {profile.id}
                            </Link>
                          ) : (
                            <p className="font-medium">{profile.path}</p>
                          )}
                          <p className="font-mono text-xs text-muted-foreground">
                            {profile.path}
                          </p>
                          {!profile.valid ? (
                            <p className="mt-1 text-xs text-destructive">
                              {profile.diagnostic}
                            </p>
                          ) : null}
                        </TableCell>
                        <TableCell>
                          {profile.target ? (
                            <>
                              <Badge variant="outline">
                                {profile.target.kind}
                              </Badge>
                              <p className="mt-1 max-w-md truncate font-mono text-xs text-muted-foreground">
                                {profile.target.command ?? profile.target.url}
                              </p>
                            </>
                          ) : (
                            "Invalid"
                          )}
                        </TableCell>
                        <TableCell>
                          {profile.associatedStackId ? (
                            <Link
                              className="font-medium hover:underline"
                              href={`/stacks/${profile.associatedStackId}`}
                            >
                              {profile.associatedStackId}
                            </Link>
                          ) : (
                            "—"
                          )}
                        </TableCell>
                        <TableCell>
                          {profile.valid && profile.id ? (
                            <TunnelProfileControls
                              profileId={profile.id}
                              initialObservation={profile.lifecycle}
                              compact
                            />
                          ) : (
                            <StatusChip
                              label="unavailable"
                              tone="destructive"
                            />
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <div className="grid divide-y md:hidden">
                {profiles.map((profile) => (
                  <article
                    key={profile.path}
                    className="grid min-w-0 gap-4 px-5 py-4"
                  >
                    <div className="min-w-0">
                      {profile.id ? (
                        <Link
                          className="font-medium hover:underline"
                          href={`/tunnels/${profile.id}`}
                        >
                          {profile.id}
                        </Link>
                      ) : (
                        <p className="font-medium">{profile.path}</p>
                      )}
                      <p className="mt-0.5 break-all font-mono text-xs text-muted-foreground">
                        {profile.path}
                      </p>
                      {!profile.valid ? (
                        <p className="mt-1 break-words text-xs text-destructive">
                          {profile.diagnostic}
                        </p>
                      ) : null}
                    </div>
                    {profile.target ? (
                      <div className="min-w-0">
                        <p className="mb-1 text-xs text-muted-foreground">
                          Target
                        </p>
                        <Badge variant="outline">{profile.target.kind}</Badge>
                        <p className="mt-1 break-all font-mono text-xs text-muted-foreground">
                          {profile.target.command ?? profile.target.url}
                        </p>
                      </div>
                    ) : null}
                    {profile.associatedStackId ? (
                      <div>
                        <p className="mb-1 text-xs text-muted-foreground">
                          Stack
                        </p>
                        <Link
                          className="font-medium hover:underline"
                          href={`/stacks/${profile.associatedStackId}`}
                        >
                          {profile.associatedStackId}
                        </Link>
                      </div>
                    ) : null}
                    {profile.valid && profile.id ? (
                      <TunnelProfileControls
                        profileId={profile.id}
                        initialObservation={profile.lifecycle}
                        compact
                      />
                    ) : (
                      <StatusChip label="unavailable" tone="destructive" />
                    )}
                  </article>
                ))}
              </div>
            </>
          ) : (
            <div className="px-6 py-10 text-center text-sm text-muted-foreground">
              No tunnel profiles are configured.
            </div>
          )}
        </CardContent>
      </Card>
    </PageContainer>
  );
}
