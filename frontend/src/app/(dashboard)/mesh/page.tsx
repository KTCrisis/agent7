"use client";

import { useTraces, useApprovals, useHealth } from "@/lib/hooks/use-mesh";
import { Activity, Shield, Clock, Cpu, AlertTriangle, ArrowRight } from "lucide-react";
import { timeAgo } from "@/lib/utils";
import Link from "next/link";

export default function MeshOverview() {
  const { data: rawTraces, error } = useTraces({ limit: 100 });
  const { data: rawApprovals } = useApprovals();
  const traces = rawTraces ?? [];
  const approvals = rawApprovals ?? [];
  const { data: health } = useHealth();

  if (error) {
    return (
      <div className="mt-20 flex flex-col items-center gap-3 text-center">
        <div className="h-12 w-12 rounded-full bg-destructive/10 flex items-center justify-center">
          <AlertTriangle className="h-6 w-6 text-destructive" />
        </div>
        <div>
          <p className="text-sm font-medium">agent-mesh unreachable</p>
          <p className="text-xs text-muted-foreground mt-1">
            Make sure agent-mesh is running on localhost:9090
          </p>
        </div>
      </div>
    );
  }

  const uniqueAgents = [...new Set(traces.map((t) => t.agent_id))];
  const denied = traces.filter((t) => t.policy === "deny").length;
  const pending = approvals.filter((a) => a.status === "pending").length;
  const avgLatency = traces.length
    ? Math.round(traces.reduce((s, t) => s + t.latency_ms, 0) / traces.length)
    : 0;

  const totalTokens = traces.reduce(
    (s, t) => s + t.estimated_input_tokens + t.estimated_output_tokens,
    0
  );

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-xl font-semibold">Overview</h2>
          {health && (
            <p className="text-xs text-muted-foreground mt-0.5">
              {health.tools} tools registered &middot; {health.traces.total} total calls
            </p>
          )}
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KPI icon={Cpu} label="Agents" value={uniqueAgents.length} />
        <KPI icon={Activity} label="Traces" value={traces.length} />
        <KPI
          icon={Shield}
          label="Pending"
          value={pending}
          accent={pending > 0 ? "primary" : undefined}
        />
        <KPI icon={Clock} label="Avg latency" value={`${avgLatency}ms`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        {/* Agents — 2 cols */}
        <div className="lg:col-span-2 rounded-lg border border-border">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Agents
            </span>
          </div>
          <div className="p-2 space-y-0.5">
            {uniqueAgents.length === 0 && (
              <p className="px-2 py-4 text-xs text-muted-foreground text-center">
                No activity yet
              </p>
            )}
            {uniqueAgents.map((agent) => {
              const at = traces.filter((t) => t.agent_id === agent);
              const d = at.filter((t) => t.policy === "deny").length;
              const last = at[0];
              return (
                <div
                  key={agent}
                  className="flex items-center justify-between rounded-md px-3 py-2 hover:bg-secondary/40 transition-colors"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="h-2 w-2 rounded-full bg-emerald-400" />
                    <span className="text-sm font-medium">{agent}</span>
                    <span className="text-xs text-muted-foreground">{at.length}</span>
                    {d > 0 && (
                      <span className="text-[10px] text-red-400 bg-red-400/10 rounded px-1.5 py-0.5">
                        {d} denied
                      </span>
                    )}
                  </div>
                  {last && (
                    <span className="text-[11px] text-muted-foreground">
                      {timeAgo(last.timestamp)}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Recent — 3 cols */}
        <div className="lg:col-span-3 rounded-lg border border-border">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Recent activity
            </span>
            <Link
              href="/mesh/traces"
              className="flex items-center gap-1 text-[11px] text-primary hover:underline"
            >
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="divide-y divide-border/50">
            {traces.slice(0, 10).map((t) => (
              <div
                key={t.trace_id}
                className="flex items-center justify-between px-4 py-2.5 text-xs"
              >
                <div className="flex items-center gap-3">
                  <PolicyBadge policy={t.policy} />
                  <span className="text-muted-foreground w-20 truncate">{t.agent_id}</span>
                  <span className="font-mono text-[11px]">{t.tool}</span>
                </div>
                <span className="text-muted-foreground">{timeAgo(t.timestamp)}</span>
              </div>
            ))}
            {traces.length === 0 && (
              <p className="px-4 py-6 text-xs text-muted-foreground text-center">
                No traces yet
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Denials */}
      {denied > 0 && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/5">
          <div className="px-4 py-3 border-b border-red-500/10">
            <span className="text-xs font-medium text-red-400 uppercase tracking-wider">
              Denials ({denied})
            </span>
          </div>
          <div className="divide-y divide-red-500/10">
            {traces
              .filter((t) => t.policy === "deny")
              .slice(0, 5)
              .map((t) => (
                <div
                  key={t.trace_id}
                  className="flex items-center justify-between px-4 py-2.5 text-xs"
                >
                  <div>
                    <span className="font-medium">{t.agent_id}</span>
                    <span className="text-muted-foreground"> tried </span>
                    <span className="font-mono text-[11px]">{t.tool}</span>
                  </div>
                  <span className="text-muted-foreground">{timeAgo(t.timestamp)}</span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

function KPI({
  icon: Icon,
  label,
  value,
  accent,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  accent?: "primary";
}) {
  return (
    <div className="rounded-lg border border-border px-4 py-3">
      <div className="flex items-center gap-1.5 text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        <span className="text-[11px] uppercase tracking-wider">{label}</span>
      </div>
      <p
        className={`mt-1 text-2xl font-semibold tabular-nums ${
          accent === "primary" ? "text-primary" : ""
        }`}
      >
        {value}
      </p>
    </div>
  );
}

function PolicyBadge({ policy }: { policy: string }) {
  const styles: Record<string, string> = {
    allow: "bg-emerald-500/15 text-emerald-400 border-emerald-500/20",
    deny: "bg-red-500/15 text-red-400 border-red-500/20",
    human_approval: "bg-amber-500/15 text-amber-400 border-amber-500/20",
  };
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-medium leading-none ${
        styles[policy] || "bg-secondary text-muted-foreground border-border"
      }`}
    >
      {policy === "human_approval" ? "approval" : policy}
    </span>
  );
}
