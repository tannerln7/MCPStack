import { Boxes } from "lucide-react";
import type { Metadata } from "next";
import { Geist } from "next/font/google";
import Link from "next/link";
import { MobilePrimaryNav } from "@/components/mobile-primary-nav";
import { PrimaryNav } from "@/components/primary-nav";
import { ThemeProvider } from "@/components/theme-provider";
import { ThemeSelect } from "@/components/theme-select";
import { cn } from "@/lib/utils";
import "./globals.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: {
    default: "MCPStack",
    template: "%s · MCPStack",
  },
  description:
    "Any MCP server. Your setup. One control panel. Manage MCP servers, applications, credentials, and tunnels with MCPStack.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={cn("font-sans", geist.variable)}
      suppressHydrationWarning
    >
      <body>
        <ThemeProvider>
          <div className="min-h-screen bg-background md:grid md:grid-cols-[15rem_minmax(0,1fr)]">
            <MobilePrimaryNav />
            <aside className="hidden border-b bg-sidebar md:sticky md:top-0 md:block md:h-screen md:border-r md:border-b-0">
              <div className="flex h-full flex-col p-4">
                <Link
                  href="/stacks"
                  className="flex items-center gap-3 rounded-lg px-2 py-2 font-semibold tracking-tight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="flex size-8 items-center justify-center rounded-lg bg-foreground text-background">
                    <Boxes aria-hidden="true" className="size-4" />
                  </span>
                  <span>MCPStack</span>
                </Link>
                <PrimaryNav />
                <ThemeSelect />
                <p className="mt-3 hidden px-3 pb-1 text-xs text-muted-foreground md:block">
                  Your MCP environment, together.
                </p>
              </div>
            </aside>
            <main className="min-w-0">{children}</main>
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
