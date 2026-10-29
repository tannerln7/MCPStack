import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ResourceNode, ResourceRelationship } from "@/lib/relationships";

function NodeLabel({
  node,
  stackId,
}: Readonly<{ node: ResourceNode; stackId: string }>) {
  const content = (
    <>
      <span className="font-medium text-foreground">{node.label}</span>
      <span className="font-mono text-[0.6875rem] uppercase tracking-wide text-muted-foreground">
        {node.kind}
      </span>
    </>
  );
  return node.componentId ? (
    <Link
      href={`/stacks/${stackId}/components/${node.componentId}`}
      aria-label={`${node.label} ${node.kind}`}
      className="flex min-w-0 flex-col rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {content}
    </Link>
  ) : (
    <span className="flex min-w-0 flex-col">{content}</span>
  );
}

export function RelationshipView({
  relationships,
  stackId,
}: Readonly<{
  relationships: ResourceRelationship[];
  stackId: string;
}>) {
  const categories = [
    ...new Set(relationships.map(({ category }) => category)),
  ];
  if (relationships.length === 0) {
    return (
      <p className="rounded-lg border bg-muted/20 p-4 text-sm text-muted-foreground">
        No configured relationships.
      </p>
    );
  }

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {categories.map((category) => (
        <Card key={category} size="sm">
          <CardHeader className="border-b">
            <CardTitle className="flex items-center justify-between gap-3">
              {category}
              <Badge variant="secondary" className="rounded-md tabular-nums">
                {
                  relationships.filter((item) => item.category === category)
                    .length
                }
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="grid gap-3" aria-label={`${category} relationships`}>
              {relationships
                .filter((item) => item.category === category)
                .map((relationship) => (
                  <li
                    key={`${relationship.from.kind}:${relationship.from.id}:${relationship.relation}:${relationship.to.kind}:${relationship.to.id}`}
                    className="grid gap-2 rounded-lg border bg-muted/20 p-3 sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] sm:items-center"
                  >
                    <NodeLabel node={relationship.from} stackId={stackId} />
                    <span className="flex items-center gap-1.5 text-xs text-muted-foreground sm:flex-col sm:text-center">
                      <ArrowRight aria-hidden="true" className="size-3.5" />
                      {relationship.relation}
                    </span>
                    <NodeLabel node={relationship.to} stackId={stackId} />
                  </li>
                ))}
            </ul>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
