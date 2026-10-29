"use client";

import { Layers3, RadioTower } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const items = [
  { href: "/stacks", label: "Stacks", icon: Layers3 },
  { href: "/tunnels", label: "Tunnels", icon: RadioTower },
];

export function PrimaryNav({
  onNavigate,
}: Readonly<{ onNavigate?: () => void }>) {
  const pathname = usePathname();
  return (
    <nav aria-label="Primary" className="mt-4 grid gap-1">
      {items.map((item) => {
        const Icon = item.icon;
        const active = pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            onClick={onNavigate}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-sidebar-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring",
              active && "bg-sidebar-accent text-sidebar-accent-foreground",
            )}
          >
            <Icon
              aria-hidden="true"
              className={cn("size-4", active && "text-primary")}
            />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
