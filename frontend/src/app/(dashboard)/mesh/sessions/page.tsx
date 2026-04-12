"use client";

import { useSessions } from "@/lib/hooks/use-mesh";
import { timeAgo } from "@/lib/utils";
import Link from "next/link";

export default function SessionsPage() {
  const { data: rawSessions } = useSessions({ limit: 100 });
  const sessions = rawSessions ?? [];

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Sessions</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          {sessions.length} session{sessions.length !== 1 ? "s" : ""}
        </p>
      </div>

      {sessions.length === 0 ? (
        <div className="rounded-lg border border-border px-4 py-12 text-center">
          <p className="text-sm text-muted-foreground">No sessions yet</p>
          <p className="text-xs text-muted-foreground mt-1">
            Sessions appear when agents send an X-Session-Id header or connect
            via MCP
          </p>
        </div>
      ) : (
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-secondary/30">
                <th className="px-4 py-2.5 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                  Session
                </th>
                <th className="px-4 py-2.5 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                  Agent
                </th>
                <th className="px-4 py-2.5 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                  Events
                </th>
                <th className="px-4 py-2.5 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                  Tools
                </th>
                <th className="px-4 py-2.5 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                  Duration
                </th>
                <th className="px-4 py-2.5 text-left text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                  Last seen
                </th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => {
                const durationMs =
                  new Date(s.last_seen).getTime() -
                  new Date(s.first_seen).getTime();
                const durationLabel =
                  durationMs < 1000
                    ? "<1s"
                    : durationMs < 60_000
                      ? `${Math.round(durationMs / 1000)}s`
                      : `${Math.round(durationMs / 60_000)}m`;

                return (
                  <tr
                    key={s.session_id}
                    className="border-b border-border/30 hover:bg-secondary/20 transition-colors"
                  >
                    <td className="px-4 py-2.5">
                      <Link
                        href={`/mesh/sessions/${s.session_id}`}
                        className="font-mono text-xs text-primary hover:underline"
                      >
                        {s.session_id.slice(0, 12)}
                      </Link>
                    </td>
                    <td className="px-4 py-2.5 text-sm font-medium">
                      {s.agent_id}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground tabular-nums">
                      {s.event_count}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex flex-wrap gap-1">
                        {s.tools.map((t) => (
                          <span
                            key={t}
                            className="inline-flex rounded border border-border bg-secondary/40 px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground tabular-nums">
                      {durationLabel}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground">
                      {timeAgo(s.last_seen)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
