"use client";

import { Fragment, useState } from "react";
import { useTraces } from "@/lib/hooks/use-mesh";
import { formatDuration, timeAgo } from "@/lib/utils";

export default function TracesPage() {
  const [filterAgent, setFilterAgent] = useState("");
  const [filterTool, setFilterTool] = useState("");
  const [filterPolicy, setFilterPolicy] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const { data: traces = [] } = useTraces({ limit: 200 });

  const uniqueAgents = [...new Set(traces.map((t) => t.agent_id))];
  const uniquePolicies = [...new Set(traces.map((t) => t.policy))];

  const filtered = traces.filter((t) => {
    if (filterAgent && t.agent_id !== filterAgent) return false;
    if (filterTool && !t.tool.toLowerCase().includes(filterTool.toLowerCase()))
      return false;
    if (filterPolicy && t.policy !== filterPolicy) return false;
    return true;
  });

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-xl font-semibold">Traces</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {filtered.length} of {traces.length} entries
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <select
          value={filterAgent}
          onChange={(e) => setFilterAgent(e.target.value)}
          className="rounded-md border border-border bg-background px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
        >
          <option value="">All agents</option>
          {uniqueAgents.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Filter tool..."
          value={filterTool}
          onChange={(e) => setFilterTool(e.target.value)}
          className="rounded-md border border-border bg-background px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary w-44"
        />
        <select
          value={filterPolicy}
          onChange={(e) => setFilterPolicy(e.target.value)}
          className="rounded-md border border-border bg-background px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
        >
          <option value="">All policies</option>
          {uniquePolicies.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        {(filterAgent || filterTool || filterPolicy) && (
          <button
            onClick={() => {
              setFilterAgent("");
              setFilterTool("");
              setFilterPolicy("");
            }}
            className="text-[11px] text-muted-foreground hover:text-foreground transition-colors px-2"
          >
            Clear filters
          </button>
        )}
      </div>

      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-secondary/30">
              <th className="px-4 py-2.5 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                Agent
              </th>
              <th className="px-4 py-2.5 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                Tool
              </th>
              <th className="px-4 py-2.5 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                Policy
              </th>
              <th className="px-4 py-2.5 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                Status
              </th>
              <th className="px-4 py-2.5 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                Latency
              </th>
              <th className="px-4 py-2.5 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                Tokens
              </th>
              <th className="px-4 py-2.5 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                Time
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((t) => (
              <Fragment key={t.trace_id}>
                <tr
                  className="border-b border-border/30 hover:bg-secondary/20 cursor-pointer transition-colors"
                  onClick={() =>
                    setExpanded(expanded === t.trace_id ? null : t.trace_id)
                  }
                >
                  <td className="px-4 py-2.5 text-sm font-medium">{t.agent_id}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">
                    {t.tool}
                  </td>
                  <td className="px-4 py-2.5">
                    <PolicyBadge policy={t.policy} />
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusCode code={t.status_code} error={t.error} />
                  </td>
                  <td className="px-4 py-2.5 text-xs text-muted-foreground tabular-nums">
                    {formatDuration(t.latency_ms)}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-muted-foreground tabular-nums">
                    {t.estimated_input_tokens + t.estimated_output_tokens > 0
                      ? `${t.estimated_input_tokens} / ${t.estimated_output_tokens}`
                      : "-"}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-muted-foreground">
                    {timeAgo(t.timestamp)}
                  </td>
                </tr>
                {expanded === t.trace_id && (
                  <tr className="border-b border-border/30">
                    <td colSpan={7} className="px-4 py-4 bg-secondary/10">
                      <div className="grid grid-cols-2 gap-4 text-xs max-w-3xl">
                        <div className="space-y-2">
                          <Field label="Trace ID" value={t.trace_id} mono />
                          <Field label="Policy rule" value={t.policy_rule} />
                          {t.approval_id && (
                            <>
                              <Field
                                label="Approval"
                                value={`${t.approval_status}${t.approved_by ? ` by ${t.approved_by}` : ""}${t.approval_ms > 0 ? ` (${formatDuration(t.approval_ms)})` : ""}`}
                              />
                            </>
                          )}
                          {t.error && <Field label="Error" value={t.error} error />}
                        </div>
                        <div>
                          <span className="text-muted-foreground text-[10px] uppercase tracking-wider">
                            Parameters
                          </span>
                          <pre className="mt-1 rounded-md bg-background border border-border p-3 overflow-x-auto text-[11px] leading-relaxed max-h-48">
                            {JSON.stringify(t.params, null, 2)}
                          </pre>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-12 text-center text-sm text-muted-foreground"
                >
                  No traces found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  mono,
  error,
}: {
  label: string;
  value: string;
  mono?: boolean;
  error?: boolean;
}) {
  return (
    <div>
      <span className="text-muted-foreground text-[10px] uppercase tracking-wider">
        {label}
      </span>
      <p
        className={`mt-0.5 ${mono ? "font-mono text-[11px]" : "text-xs"} ${error ? "text-destructive" : ""}`}
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

function StatusCode({ code, error }: { code: number; error: string }) {
  const color = error
    ? "text-red-400"
    : code >= 200 && code < 300
      ? "text-emerald-400"
      : code >= 400
        ? "text-red-400"
        : "text-muted-foreground";
  return <span className={`text-xs tabular-nums font-medium ${color}`}>{code}</span>;
}
