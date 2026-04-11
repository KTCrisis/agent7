"use client";

import { useState } from "react";
import {
  useApprovals,
  useApprovalDetail,
  useResolveApproval,
} from "@/lib/hooks/use-mesh";
import { timeAgo } from "@/lib/utils";
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  ShieldAlert,
} from "lucide-react";

export default function ApprovalsPage() {
  const { data: rawApprovals } = useApprovals();
  const approvals = rawApprovals ?? [];
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reasoning, setReasoning] = useState("");

  const { data: detail } = useApprovalDetail(selectedId);
  const resolve = useResolveApproval();

  const pending = approvals.filter((a) => a.status === "pending");
  const resolved = approvals.filter((a) => a.status !== "pending");

  function handleResolve(id: string, decision: "approve" | "deny") {
    resolve.mutate(
      { id, decision, reasoning: reasoning || undefined },
      {
        onSuccess: () => {
          setSelectedId(null);
          setReasoning("");
        },
      }
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Approvals</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          {pending.length} pending &middot; {resolved.length} resolved
        </p>
      </div>

      {/* Pending */}
      {pending.length > 0 ? (
        <div className="space-y-2">
          {pending.map((a) => {
            const isOpen = selectedId === a.id;
            return (
              <div
                key={a.id}
                className="rounded-lg border border-amber-500/20 bg-amber-500/[0.03] overflow-hidden"
              >
                <button
                  onClick={() => setSelectedId(isOpen ? null : a.id)}
                  className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-amber-500/[0.05] transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <ShieldAlert className="h-4 w-4 text-amber-400 shrink-0" />
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{a.agent_id}</span>
                      <span className="font-mono text-xs text-muted-foreground">
                        {a.tool}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-[11px] text-muted-foreground">
                      {timeAgo(a.created_at)}
                    </span>
                    {isOpen ? (
                      <ChevronUp className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    )}
                  </div>
                </button>

                {isOpen && detail && (
                  <div className="border-t border-amber-500/10 px-4 py-4 space-y-4">
                    {detail.injection_risk && (
                      <div className="flex items-center gap-2 rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2 text-xs text-red-400">
                        <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                        Potential prompt injection detected in parameters
                      </div>
                    )}

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
                          Parameters
                        </span>
                        <pre className="mt-1 rounded-md bg-background border border-border p-3 text-[11px] leading-relaxed overflow-x-auto max-h-48">
                          {JSON.stringify(detail.params, null, 2)}
                        </pre>
                      </div>

                      {detail.recent_traces.length > 0 && (
                        <div>
                          <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
                            Recent from {a.agent_id}
                          </span>
                          <div className="mt-1 rounded-md border border-border divide-y divide-border/50">
                            {detail.recent_traces.slice(0, 6).map((t) => (
                              <div
                                key={t.trace_id}
                                className="flex justify-between px-3 py-1.5 text-[11px]"
                              >
                                <span className="font-mono text-muted-foreground truncate">
                                  {t.tool}
                                </span>
                                <PolicyMini policy={t.policy} />
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2 pt-1">
                      <input
                        type="text"
                        placeholder="Reasoning (optional)"
                        value={reasoning}
                        onChange={(e) => setReasoning(e.target.value)}
                        className="flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                      />
                      <button
                        onClick={() => handleResolve(a.id, "approve")}
                        disabled={resolve.isPending}
                        className="flex items-center gap-1.5 rounded-md bg-emerald-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50 transition-colors"
                      >
                        <CheckCircle className="h-3.5 w-3.5" />
                        Approve
                      </button>
                      <button
                        onClick={() => handleResolve(a.id, "deny")}
                        disabled={resolve.isPending}
                        className="flex items-center gap-1.5 rounded-md bg-red-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-red-500 disabled:opacity-50 transition-colors"
                      >
                        <XCircle className="h-3.5 w-3.5" />
                        Deny
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="rounded-lg border border-border py-12 text-center">
          <CheckCircle className="mx-auto h-8 w-8 text-emerald-400/60 mb-2" />
          <p className="text-sm text-muted-foreground">All clear</p>
        </div>
      )}

      {/* History */}
      {resolved.length > 0 && (
        <div>
          <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
            History
          </span>
          <div className="mt-2 rounded-lg border border-border overflow-hidden">
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
                    Decision
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                    Time
                  </th>
                </tr>
              </thead>
              <tbody>
                {resolved.map((a) => (
                  <tr key={a.id} className="border-b border-border/30">
                    <td className="px-4 py-2.5 text-sm">{a.agent_id}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">
                      {a.tool}
                    </td>
                    <td className="px-4 py-2.5">
                      <DecisionBadge status={a.status} />
                    </td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground">
                      {timeAgo(a.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function PolicyMini({ policy }: { policy: string }) {
  const color =
    policy === "allow"
      ? "text-emerald-400"
      : policy === "deny"
        ? "text-red-400"
        : "text-amber-400";
  return <span className={`text-[10px] ${color}`}>{policy}</span>;
}

function DecisionBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    approved: "bg-emerald-500/15 text-emerald-400 border-emerald-500/20",
    denied: "bg-red-500/15 text-red-400 border-red-500/20",
    timeout: "bg-zinc-500/15 text-zinc-400 border-zinc-500/20",
  };
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-medium leading-none ${
        styles[status] || "bg-secondary text-muted-foreground border-border"
      }`}
    >
      {status}
    </span>
  );
}
