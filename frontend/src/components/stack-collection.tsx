"use client";

import { ArrowRight, ChevronDown, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { HealthBadge } from "@/components/health-badge";
import { SourceMetadata } from "@/components/source-metadata";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ValidationIssues } from "@/components/validation-issues";
import type { StackDiscovery } from "@/lib/contracts/types";
import {
  compareStackCollectionItems,
  componentStatusLabels,
  type HealthState,
  type StackCollectionItem,
  type StackSort,
} from "@/lib/stack-collection";
import { cn } from "@/lib/utils";

const allFilters = "all";

function uniqueOptions<T extends string>(
  items: StackCollectionItem[],
  select: (item: StackCollectionItem) => T[],
): T[] {
  return [...new Set(items.flatMap(select))].sort((left, right) =>
    left.localeCompare(right),
  );
}

export function StackCollection({
  discovery,
  items,
}: Readonly<{ discovery: StackDiscovery; items: StackCollectionItem[] }>) {
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState(allFilters);
  const [transportFilter, setTransportFilter] = useState(allFilters);
  const [statusFilter, setStatusFilter] = useState(allFilters);
  const [healthFilter, setHealthFilter] = useState(allFilters);
  const [sort, setSort] = useState<StackSort>("name");
  const [filtersOpen, setFiltersOpen] = useState(false);

  const typeOptions = useMemo(
    () => uniqueOptions(items, (item) => item.componentTypes),
    [items],
  );
  const transportOptions = useMemo(
    () => uniqueOptions(items, (item) => item.transports),
    [items],
  );
  const statusOptions = useMemo(
    () => uniqueOptions(items, (item) => item.statuses),
    [items],
  );
  const healthOptions: HealthState[] = ["healthy", "unhealthy", "not-observed"];
  const visibleItems = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    return items
      .filter(
        (item) =>
          (!normalizedQuery || item.searchText.includes(normalizedQuery)) &&
          (typeFilter === allFilters ||
            item.componentTypes.includes(
              typeFilter as StackCollectionItem["componentTypes"][number],
            )) &&
          (transportFilter === allFilters ||
            item.transports.includes(
              transportFilter as StackCollectionItem["transports"][number],
            )) &&
          (healthFilter === allFilters || item.healthState === healthFilter) &&
          (statusFilter === allFilters ||
            item.statuses.includes(
              statusFilter as StackCollectionItem["statuses"][number],
            )),
      )
      .toSorted((left, right) =>
        compareStackCollectionItems(left, right, sort),
      );
  }, [
    items,
    healthFilter,
    query,
    sort,
    statusFilter,
    transportFilter,
    typeFilter,
  ]);

  return (
    <div className="mt-8 grid gap-8">
      <ValidationIssues diagnostics={discovery.invalidSources} />
      {items.length === 0 ? (
        <EmptyState
          title="No valid stacks found"
          description={
            discovery.invalidSources.length > 0
              ? "Fix the configuration issues above. Valid YAML stack files will appear automatically on the next request."
              : "Add a YAML stack document to the configured local directory, then reload this page."
          }
        />
      ) : (
        <section
          aria-labelledby="stack-collection-heading"
          className="grid min-w-0 gap-4"
        >
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 id="stack-collection-heading" className="font-medium">
                All stacks
              </h2>
              <p
                className="mt-1 text-sm text-muted-foreground"
                aria-live="polite"
              >
                {visibleItems.length} of {items.length} stack
                {items.length === 1 ? "" : "s"}
              </p>
            </div>
          </div>

          <Collapsible
            open={filtersOpen}
            onOpenChange={setFiltersOpen}
            className="rounded-xl border bg-card p-3"
          >
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <Field className="min-w-0 flex-1">
                <FieldLabel htmlFor="stack-search">Search</FieldLabel>
                <Input
                  id="stack-search"
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Name, component, package…"
                />
              </Field>
              <CollapsibleTrigger
                render={
                  <Button
                    type="button"
                    variant="outline"
                    className="shrink-0"
                  />
                }
              >
                <SlidersHorizontal data-icon="inline-start" />
                {filtersOpen ? "Hide filters" : "Show filters"}
                <ChevronDown
                  aria-hidden="true"
                  className={cn(
                    "size-4 transition-transform",
                    filtersOpen && "rotate-180",
                  )}
                />
              </CollapsibleTrigger>
            </div>
            <CollapsibleContent>
              <div className="mt-3 grid min-w-0 gap-3 border-t pt-3 sm:grid-cols-2 xl:grid-cols-5">
                <Field>
                  <FieldLabel htmlFor="stack-health-filter">Health</FieldLabel>
                  <NativeSelect
                    id="stack-health-filter"
                    className="w-full"
                    value={healthFilter}
                    onChange={(event) => setHealthFilter(event.target.value)}
                  >
                    <NativeSelectOption value={allFilters}>
                      All health states
                    </NativeSelectOption>
                    {healthOptions.map((option) => (
                      <NativeSelectOption key={option} value={option}>
                        {option === "healthy"
                          ? "Healthy"
                          : option === "unhealthy"
                            ? "Unhealthy"
                            : "Not observed"}
                      </NativeSelectOption>
                    ))}
                  </NativeSelect>
                </Field>
                <Field>
                  <FieldLabel htmlFor="stack-type-filter">Type</FieldLabel>
                  <NativeSelect
                    id="stack-type-filter"
                    className="w-full"
                    value={typeFilter}
                    onChange={(event) => setTypeFilter(event.target.value)}
                  >
                    <NativeSelectOption value={allFilters}>
                      All types
                    </NativeSelectOption>
                    {typeOptions.map((option) => (
                      <NativeSelectOption key={option} value={option}>
                        {option}
                      </NativeSelectOption>
                    ))}
                  </NativeSelect>
                </Field>
                <Field>
                  <FieldLabel htmlFor="stack-transport-filter">
                    Transport
                  </FieldLabel>
                  <NativeSelect
                    id="stack-transport-filter"
                    className="w-full"
                    value={transportFilter}
                    onChange={(event) => setTransportFilter(event.target.value)}
                  >
                    <NativeSelectOption value={allFilters}>
                      All transports
                    </NativeSelectOption>
                    {transportOptions.map((option) => (
                      <NativeSelectOption key={option} value={option}>
                        {option}
                      </NativeSelectOption>
                    ))}
                  </NativeSelect>
                </Field>
                <Field>
                  <FieldLabel htmlFor="stack-status-filter">
                    Runtime status
                  </FieldLabel>
                  <NativeSelect
                    id="stack-status-filter"
                    className="w-full"
                    value={statusFilter}
                    onChange={(event) => setStatusFilter(event.target.value)}
                  >
                    <NativeSelectOption value={allFilters}>
                      All runtime statuses
                    </NativeSelectOption>
                    {statusOptions.map((option) => (
                      <NativeSelectOption key={option} value={option}>
                        {componentStatusLabels[option]}
                      </NativeSelectOption>
                    ))}
                  </NativeSelect>
                </Field>
                <Field>
                  <FieldLabel htmlFor="stack-sort">Sort</FieldLabel>
                  <NativeSelect
                    id="stack-sort"
                    className="w-full"
                    value={sort}
                    onChange={(event) =>
                      setSort(event.target.value as StackSort)
                    }
                  >
                    <NativeSelectOption value="name">Name</NativeSelectOption>
                    <NativeSelectOption value="type">Type</NativeSelectOption>
                    <NativeSelectOption value="status">
                      Runtime status
                    </NativeSelectOption>
                  </NativeSelect>
                </Field>
              </div>
            </CollapsibleContent>
          </Collapsible>

          {visibleItems.length === 0 ? (
            <EmptyState
              title="No matching stacks"
              description="Adjust the search text or filters to show configured stacks."
            />
          ) : (
            <div className="min-w-0 rounded-xl border bg-card">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Stack</TableHead>
                    <TableHead className="hidden sm:table-cell">Type</TableHead>
                    <TableHead className="hidden md:table-cell">
                      Transport
                    </TableHead>
                    <TableHead className="hidden md:table-cell">
                      Runtime status
                    </TableHead>
                    <TableHead className="hidden lg:table-cell">
                      Health
                    </TableHead>
                    <TableHead className="hidden lg:table-cell">
                      Source
                    </TableHead>
                    <TableHead>
                      <span className="sr-only">Open</span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleItems.map((stack) => (
                    <TableRow key={stack.id}>
                      <TableCell className="min-w-48 whitespace-normal py-3">
                        <Link
                          href={`/stacks/${stack.id}`}
                          className="font-medium hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          {stack.name}
                        </Link>
                        <p className="mt-0.5 font-mono text-xs text-muted-foreground">
                          {stack.id}
                        </p>
                        {stack.description ? (
                          <p className="mt-1 hidden max-w-xl text-xs text-muted-foreground xl:block">
                            {stack.description}
                          </p>
                        ) : null}
                        <div className="mt-2 grid justify-items-start gap-1 md:hidden">
                          <span className="text-xs text-muted-foreground">
                            Runtime status
                          </span>
                          {stack.statuses.map((status) => (
                            <StatusBadge key={status} status={status} />
                          ))}
                          <span className="mt-1 text-xs text-muted-foreground">
                            Health
                          </span>
                          <HealthBadge state={stack.healthState} />
                        </div>
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        <div className="flex flex-wrap gap-1.5">
                          {stack.componentTypes.map((type) => (
                            <Badge
                              key={type}
                              variant="secondary"
                              className="rounded-md"
                            >
                              {type}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        <div className="flex flex-wrap gap-1.5">
                          {stack.transports.map((transport) => (
                            <Badge
                              key={transport}
                              variant="outline"
                              className="rounded-md font-mono font-normal"
                            >
                              {transport}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        <div className="flex flex-wrap gap-1.5">
                          {stack.statuses.map((status) => (
                            <StatusBadge key={status} status={status} />
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="hidden lg:table-cell">
                        <HealthBadge state={stack.healthState} />
                      </TableCell>
                      <TableCell className="hidden lg:table-cell">
                        <SourceMetadata source={stack.source} compact />
                        <p className="mt-1 text-xs text-muted-foreground">
                          {stack.componentCount} component
                          {stack.componentCount === 1 ? "" : "s"} · rev{" "}
                          <code className="font-mono">
                            {stack.configurationRevision.slice(0, 8)}
                          </code>
                        </p>
                      </TableCell>
                      <TableCell className="text-right">
                        <Link
                          href={`/stacks/${stack.id}`}
                          aria-label={`Open ${stack.name}`}
                          className="inline-flex rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <ArrowRight aria-hidden="true" className="size-4" />
                        </Link>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
