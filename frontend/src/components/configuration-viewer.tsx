import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { JsonSchema } from "@/lib/contracts/types";

function humanize(value: string) {
  return value
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[-_]/g, " ")
    .replace(/^./, (letter) => letter.toUpperCase());
}

function resolveSchema(
  root: JsonSchema,
  schema?: JsonSchema,
): JsonSchema | undefined {
  if (!schema?.$ref?.startsWith("#/$defs/")) {
    return schema;
  }
  return root.$defs?.[schema.$ref.slice("#/$defs/".length)] ?? schema;
}

function selectVariant(
  root: JsonSchema,
  schema: JsonSchema | undefined,
  value: unknown,
) {
  const resolved = resolveSchema(root, schema);
  if (!resolved?.oneOf || typeof value !== "object" || value === null) {
    return resolved;
  }
  return (
    resolved.oneOf
      .map((variant) => resolveSchema(root, variant))
      .find((variant) =>
        Object.entries(variant?.properties ?? {}).some(
          ([key, property]) =>
            property.const !== undefined &&
            value &&
            key in value &&
            value[key as keyof typeof value] === property.const,
        ),
      ) ?? resolved
  );
}

function ScalarValue({
  value,
}: Readonly<{ value: string | number | boolean | null }>) {
  if (value === null) {
    return <span className="text-muted-foreground">Not set</span>;
  }
  if (typeof value === "boolean") {
    return <Badge variant="secondary">{value ? "Enabled" : "Disabled"}</Badge>;
  }
  return (
    <code className="break-all font-mono text-[0.8125rem] text-foreground">
      {String(value)}
    </code>
  );
}

function SchemaValue({
  root,
  schema,
  value,
}: Readonly<{ root: JsonSchema; schema?: JsonSchema; value: unknown }>) {
  const selectedSchema = selectVariant(root, schema, value);
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="text-muted-foreground">None configured</span>;
    }
    return (
      <div className="grid gap-2">
        {value.map((item, index) => (
          <div
            key={`${index}-${JSON.stringify(item)}`}
            className="rounded-md border bg-muted/30 p-3"
          >
            <SchemaValue
              root={root}
              schema={selectedSchema?.items}
              value={item}
            />
          </div>
        ))}
      </div>
    );
  }
  if (typeof value === "object" && value !== null) {
    const properties = selectedSchema?.properties ?? {};
    const entries = Object.entries(value).sort(([left], [right]) => {
      const order = Object.keys(properties);
      const leftIndex = order.indexOf(left);
      const rightIndex = order.indexOf(right);
      return (
        (leftIndex < 0 ? Number.MAX_SAFE_INTEGER : leftIndex) -
        (rightIndex < 0 ? Number.MAX_SAFE_INTEGER : rightIndex)
      );
    });
    return (
      <dl className="grid gap-0">
        {entries.map(([key, child], index) => (
          <div key={key}>
            {index > 0 ? <Separator /> : null}
            <div className="grid gap-2 py-3 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-5">
              <dt className="text-sm font-medium text-muted-foreground">
                {humanize(key)}
              </dt>
              <dd className="min-w-0 text-sm">
                <SchemaValue
                  root={root}
                  schema={properties[key]}
                  value={child}
                />
              </dd>
            </div>
          </div>
        ))}
      </dl>
    );
  }
  return <ScalarValue value={value as string | number | boolean | null} />;
}

export function ConfigurationViewer({
  schema,
  definition,
  value,
}: Readonly<{ schema: JsonSchema; definition?: string; value: unknown }>) {
  const selected = definition ? schema.$defs?.[definition] : schema;
  return <SchemaValue root={schema} schema={selected} value={value} />;
}
