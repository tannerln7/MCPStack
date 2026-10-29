import { Plus } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { ObservationRefresh } from "@/components/observation-refresh";
import { PageContainer } from "@/components/page-container";
import { PageHeader } from "@/components/page-header";
import { StackCollection } from "@/components/stack-collection";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { getStack, getStacks } from "@/lib/api";
import { toStackCollectionItem } from "@/lib/stack-collection";

export const dynamic = "force-dynamic";

export const metadata: Metadata = { title: "Stacks" };

export default async function StacksPage() {
  const discovery = await getStacks();
  const stackViews = await Promise.all(
    discovery.stacks.map((stack) => getStack(stack.id)),
  );
  const items = discovery.stacks.map((stack, index) =>
    toStackCollectionItem(stack, stackViews[index]),
  );
  return (
    <PageContainer>
      <ObservationRefresh />
      <PageHeader
        eyebrow="Configured world"
        title="Stacks"
        description="Durable, filesystem-backed operational units for MCP servers, applications, and tunnels. Invalid sources are reported without hiding valid stacks."
        aside={
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="rounded-md tabular-nums">
              {discovery.scannedSourceCount} source
              {discovery.scannedSourceCount === 1 ? "" : "s"} scanned
            </Badge>
            <Link href="/stacks/new" className={buttonVariants()}>
              <Plus data-icon="inline-start" />
              New Stack
            </Link>
          </div>
        }
      />
      <StackCollection discovery={discovery} items={items} />
    </PageContainer>
  );
}
