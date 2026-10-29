"use client";

import { Boxes, Menu } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PrimaryNav } from "@/components/primary-nav";
import { ThemeSelect } from "@/components/theme-select";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

export function MobilePrimaryNav() {
  const [open, setOpen] = useState(false);
  return (
    <header className="flex items-center justify-between border-b bg-sidebar p-3 md:hidden">
      <Link
        href="/stacks"
        className="flex items-center gap-2 rounded-lg font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="flex size-8 items-center justify-center rounded-lg bg-foreground text-background">
          <Boxes aria-hidden="true" className="size-4" />
        </span>
        MCPStack
      </Link>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger
          render={
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label="Open primary navigation"
            />
          }
        >
          <Menu />
        </SheetTrigger>
        <SheetContent side="left" className="w-[18rem] p-4">
          <SheetHeader className="px-0">
            <SheetTitle>MCPStack</SheetTitle>
            <SheetDescription>MCPStack navigation</SheetDescription>
          </SheetHeader>
          <PrimaryNav onNavigate={() => setOpen(false)} />
          <div className="mt-auto">
            <ThemeSelect />
          </div>
        </SheetContent>
      </Sheet>
    </header>
  );
}
