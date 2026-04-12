"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Activity, Shield, LayoutDashboard, Radio, GitBranch, Users } from "lucide-react";
import { useHealth } from "@/lib/hooks/use-mesh";

const nav = [
  { href: "/mesh", label: "Overview", icon: LayoutDashboard },
  { href: "/mesh/traces", label: "Traces", icon: Activity },
  { href: "/mesh/sessions", label: "Sessions", icon: Users },
  { href: "/mesh/otel", label: "OTEL", icon: GitBranch },
  { href: "/mesh/approvals", label: "Approvals", icon: Shield },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { data: health } = useHealth();

  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur-sm">
        <div className="flex items-center justify-between px-6 h-14">
          <div className="flex items-center gap-8">
            <Link href="/mesh" className="flex items-center gap-2">
              <div className="h-7 w-7 rounded-md bg-primary/15 flex items-center justify-center">
                <Radio className="h-4 w-4 text-primary" />
              </div>
              <span className="text-sm font-semibold tracking-tight">agent7</span>
            </Link>
            <nav className="flex items-center gap-1">
              {nav.map(({ href, label, icon: Icon }) => (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors",
                    pathname === href
                      ? "bg-secondary text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            {health ? (
              <>
                <span className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Connected
                </span>
                <span className="text-border">|</span>
                <span>{health.tools} tools</span>
                <span className="text-border">|</span>
                <span>{health.traces.total} traces</span>
              </>
            ) : (
              <span className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-red-400" />
                Disconnected
              </span>
            )}
          </div>
        </div>
      </header>
      <main className="flex-1 px-6 py-6 max-w-7xl mx-auto w-full">{children}</main>
    </div>
  );
}
