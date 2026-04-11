"use client";

import { useMemo, useState } from "react";
import { useOtelTraces } from "@/lib/hooks/use-mesh";
import { flattenOtlp, type FlatSpan } from "@/lib/api/mesh";

export default function OtelTracesPage() {
  const [filterAgent, setFilterAgent] = useState("");
  const [filterTool, setFilterTool] = useState("");

  const { data, isLoading, error } = useOtelTraces({ limit: 200 });

  const spans = useMemo<FlatSpan[]>(
    () => (data ? flattenOtlp(data) : []),
    [data]
  );

  const uniqueAgents = useMemo(
    () => [...new Set(spans.map((s) => s.attrs["agent.id"]).filter(Boolean))],
    [spans]
  );

  const filtered = useMemo(
    () =>
      spans.filter((s) => {
        if (filterAgent && s.attrs["agent.id"] !== filterAgent) return false;
        if (
          filterTool &&
          !s.name.toLowerCase().includes(filterTool.toLowerCase())
        )
          return false;
        return true;
      }),
    [spans, filterAgent, filterTool]
  );

  // Compute latency bucket for waterfall bar width (relative to max duration)
  const maxDuration = useMemo(
    () => Math.max(1, ...filtered.map((s) => s.durationMs)),
    [filtered]
  );

  const totalInputTokens = filtered.reduce(
    (sum, s) => sum + Number(s.attrs["llm.token.input"] || 0),
    0
  );
  const totalOutputTokens = filtered.reduce(
    (sum, s) => sum + Number(s.attrs["llm.token.output"] || 0),
    0
  );

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-xl font-semibold">OTEL Traces</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            OTLP JSON spans from agent-mesh v0.6.0 · {filtered.length} spans
            {totalInputTokens + totalOutputTokens > 0 && (
              <>
                {" · "}
                <span className="tabular-nums">
                  {totalInputTokens} / {totalOutputTokens} tokens
                </span>
              </>
            )}
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
        {(filterAgent || filterTool) && (
          <button
            onClick={() => {
              setFilterAgent("");
              setFilterTool("");
            }}
            className="text-[11px] text-muted-foreground hover:text-foreground transition-colors px-2"
          >
            Clear filters
          </button>
        )}
      </div>

      {isLoading && (
        <div className="rounded-lg border border-border p-8 text-center text-sm text-muted-foreground">
          Loading spans...
        </div>
      )}

      {error instanceof Error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error.message}
          <p className="mt-2 text-xs text-muted-foreground">
            agent-mesh v0.6.0+ required. Run{" "}
            <code className="font-mono">make install</code> and restart.
          </p>
        </div>
      )}

      {!isLoading && !error && (
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-secondary/30">
                <th className="px-4 py-2.5 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                  Agent
                </th>
                <th className="px-4 py-2.5 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                  Span
                </th>
                <th className="px-4 py-2.5 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider w-96">
                  Duration
                </th>
                <th className="px-4 py-2.5 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                  Policy
                </th>
                <th className="px-4 py-2.5 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                  Status
                </th>
                <th className="px-4 py-2.5 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                  Tokens
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s, i) => (
                <SpanRow
                  key={`${s.traceId}-${s.spanId}-${i}`}
                  span={s}
                  maxDuration={maxDuration}
                />
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-12 text-center text-sm text-muted-foreground"
                  >
                    No OTEL spans found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function SpanRow({
  span,
  maxDuration,
}: {
  span: FlatSpan;
  maxDuration: number;
}) {
  const [open, setOpen] = useState(false);
  const widthPct = Math.max(1, (span.durationMs / maxDuration) * 100);
  const barColor =
    span.statusCode === 2
      ? "bg-red-500/40"
      : span.attrs["policy.action"] === "human_approval"
        ? "bg-amber-500/40"
        : "bg-emerald-500/40";

  const inputTokens = Number(span.attrs["llm.token.input"] || 0);
  const outputTokens = Number(span.attrs["llm.token.output"] || 0);

  return (
    <>
      <tr
        className="border-b border-border/30 hover:bg-secondary/20 cursor-pointer transition-colors"
        onClick={() => setOpen(!open)}
      >
        <td className="px-4 py-2.5 text-sm font-medium">
          {span.attrs["agent.id"] || "-"}
        </td>
        <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">
          {span.name}
        </td>
        <td className="px-4 py-2.5">
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-secondary/50 rounded-sm overflow-hidden">
              <div
                className={`h-full ${barColor}`}
                style={{ width: `${widthPct}%` }}
              />
            </div>
            <span className="text-[10px] text-muted-foreground tabular-nums w-14 text-right">
              {span.durationMs}ms
            </span>
          </div>
        </td>
        <td className="px-4 py-2.5">
          <PolicyBadge policy={span.attrs["policy.action"] || "-"} />
        </td>
        <td className="px-4 py-2.5">
          <StatusBadge code={span.statusCode} message={span.statusMessage} />
        </td>
        <td className="px-4 py-2.5 text-xs text-muted-foreground tabular-nums">
          {inputTokens + outputTokens > 0
            ? `${inputTokens} / ${outputTokens}`
            : "-"}
        </td>
      </tr>
      {open && (
        <tr className="border-b border-border/30">
          <td colSpan={6} className="px-4 py-4 bg-secondary/10">
            <div className="grid grid-cols-2 gap-4 text-xs max-w-3xl">
              <div className="space-y-1.5">
                <Field label="Trace ID" value={span.traceId} mono />
                <Field label="Span ID" value={span.spanId} mono />
                <Field
                  label="Start"
                  value={new Date(
                    Number(span.startNs / BigInt(1000000))
                  ).toISOString()}
                />
                {span.statusMessage && (
                  <Field label="Error" value={span.statusMessage} error />
                )}
              </div>
              <div>
                <span className="text-muted-foreground text-[10px] uppercase tracking-wider">
                  Attributes
                </span>
                <pre className="mt-1 rounded-md bg-background border border-border p-3 overflow-x-auto text-[11px] leading-relaxed max-h-48">
                  {JSON.stringify(span.attrs, null, 2)}
                </pre>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
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
        className={`mt-0.5 ${mono ? "font-mono text-[11px] break-all" : "text-xs"} ${error ? "text-destructive" : ""}`}
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

function StatusBadge({ code, message }: { code: number; message: string }) {
  const label = code === 2 ? "error" : code === 1 ? "ok" : "unset";
  const color =
    code === 2
      ? "text-red-400"
      : code === 1
        ? "text-emerald-400"
        : "text-muted-foreground";
  return (
    <span
      className={`text-xs font-medium ${color}`}
      title={message || undefined}
    >
      {label}
    </span>
  );
}
