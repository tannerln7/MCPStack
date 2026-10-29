import type { Metadata } from "next";
import Link from "next/link";

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
import { getStacks } from "@/lib/api";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "New tunnel profile" };

export default async function NewTunnelPage() {
  const discovery = await getStacks();
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
                <BreadcrumbPage>New</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        }
        title="Create a tunnel profile"
        description="Configure one independent OpenAI remote tunnel. Creation writes a private profile but does not start it."
      />
      <TunnelProfileForm stacks={discovery.stacks} />
    </PageContainer>
  );
}
