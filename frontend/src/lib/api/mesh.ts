const MESH_BASE = "/api/mesh";

export interface TraceEntry {
  trace_id: string;
  session_id: string;
  agent_id: string;
  tool: string;
  params: Record<string, unknown>;
  policy: string;
  policy_rule: string;
  status_code: number;
  latency_ms: number;
  error: string;
  approval_id: string;
  approval_status: string;
  approved_by: string;
  approval_ms: number;
  estimated_input_tokens: number;
  estimated_output_tokens: number;
  timestamp: string;
}

export interface ApprovalSummary {
  id: string;
  agent_id: string;
  tool: string;
  params: Record<string, unknown>;
  status: string;
  created_at: string;
}

export interface ApprovalDetail extends ApprovalSummary {
  recent_traces: TraceEntry[];
  active_grants: unknown[];
  injection_risk: boolean;
}

export async function fetchTraces(opts?: {
  agent?: string;
  tool?: string;
  limit?: number;
}): Promise<TraceEntry[]> {
  const params = new URLSearchParams();
  if (opts?.agent) params.set("agent", opts.agent);
  if (opts?.tool) params.set("tool", opts.tool);
  if (opts?.limit) params.set("limit", String(opts.limit));
  const qs = params.toString();
  const res = await fetch(`${MESH_BASE}/traces${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(`Failed to fetch traces: ${res.status}`);
  return res.json();
}

export async function fetchApprovals(opts?: {
  status?: string;
  tool?: string;
}): Promise<ApprovalSummary[]> {
  const params = new URLSearchParams();
  if (opts?.status) params.set("status", opts.status);
  if (opts?.tool) params.set("tool", opts.tool);
  const qs = params.toString();
  const res = await fetch(`${MESH_BASE}/approvals${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(`Failed to fetch approvals: ${res.status}`);
  return res.json();
}

export async function fetchApprovalDetail(
  id: string
): Promise<ApprovalDetail> {
  const res = await fetch(`${MESH_BASE}/approvals/${id}`);
  if (!res.ok) throw new Error(`Failed to fetch approval: ${res.status}`);
  return res.json();
}

export async function resolveApproval(
  id: string,
  decision: "approve" | "deny",
  reasoning?: string
): Promise<void> {
  const res = await fetch(`${MESH_BASE}/approvals/${id}/${decision}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reasoning }),
  });
  if (!res.ok) throw new Error(`Failed to ${decision} approval: ${res.status}`);
}

export interface HealthData {
  status: string;
  tools: number;
  traces: {
    total: number;
    allowed: number;
    denied: number;
    errors: number;
    human_approval: number;
  };
  version?: string;
}

export async function fetchHealth(): Promise<HealthData> {
  const res = await fetch(`${MESH_BASE}/health`);
  if (!res.ok) throw new Error(`Failed to fetch health: ${res.status}`);
  return res.json();
}

// ───────────────────────────────────────────────────────────
// Sessions
// ───────────────────────────────────────────────────────────

export interface SessionSummary {
  session_id: string;
  agent_id: string;
  event_count: number;
  first_seen: string;
  last_seen: string;
  tools: string[];
}

export async function fetchSessions(opts?: {
  limit?: number;
}): Promise<SessionSummary[]> {
  const params = new URLSearchParams();
  if (opts?.limit) params.set("limit", String(opts.limit));
  const qs = params.toString();
  const res = await fetch(`${MESH_BASE}/sessions${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(`Failed to fetch sessions: ${res.status}`);
  return res.json();
}

export async function fetchSessionEvents(
  id: string,
  opts?: { limit?: number }
): Promise<TraceEntry[]> {
  const params = new URLSearchParams();
  if (opts?.limit) params.set("limit", String(opts.limit));
  const qs = params.toString();
  const res = await fetch(
    `${MESH_BASE}/sessions/${encodeURIComponent(id)}${qs ? `?${qs}` : ""}`
  );
  if (!res.ok) throw new Error(`Failed to fetch session events: ${res.status}`);
  return res.json();
}

// ───────────────────────────────────────────────────────────
// OTLP / OpenTelemetry types
// ───────────────────────────────────────────────────────────

export interface OtlpKV {
  key: string;
  value: { stringValue?: string; intValue?: string };
}

export interface OtlpSpan {
  traceId: string;
  spanId: string;
  name: string;
  kind: number;
  startTimeUnixNano: string;
  endTimeUnixNano: string;
  attributes: OtlpKV[];
  status: { code: number; message?: string };
}

export interface OtlpScopeSpan {
  scope: { name: string; version?: string };
  spans: OtlpSpan[];
}

export interface OtlpResourceSpan {
  resource: { attributes: OtlpKV[] };
  scopeSpans: OtlpScopeSpan[];
}

export interface OtlpExport {
  resourceSpans: OtlpResourceSpan[];
}

export async function fetchOtelTraces(opts?: {
  agent?: string;
  tool?: string;
  limit?: number;
}): Promise<OtlpExport> {
  const params = new URLSearchParams();
  if (opts?.agent) params.set("agent", opts.agent);
  if (opts?.tool) params.set("tool", opts.tool);
  if (opts?.limit) params.set("limit", String(opts.limit));
  const qs = params.toString();
  const res = await fetch(`${MESH_BASE}/otel-traces${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(`Failed to fetch OTEL traces: ${res.status}`);
  return res.json();
}

// Helper: flatten an OTLP export into a list of spans with attributes as a map.
export interface FlatSpan {
  traceId: string;
  spanId: string;
  name: string;
  startNs: bigint;
  endNs: bigint;
  durationMs: number;
  statusCode: number;
  statusMessage: string;
  attrs: Record<string, string>;
}

export function flattenOtlp(exp: OtlpExport): FlatSpan[] {
  const out: FlatSpan[] = [];
  for (const rs of exp.resourceSpans ?? []) {
    for (const ss of rs.scopeSpans ?? []) {
      for (const s of ss.spans ?? []) {
        const attrs: Record<string, string> = {};
        for (const kv of s.attributes ?? []) {
          attrs[kv.key] = kv.value.stringValue ?? kv.value.intValue ?? "";
        }
        const startNs = BigInt(s.startTimeUnixNano || "0");
        const endNs = BigInt(s.endTimeUnixNano || "0");
        const durationMs = Number((endNs - startNs) / BigInt(1000000));
        out.push({
          traceId: s.traceId,
          spanId: s.spanId,
          name: s.name,
          startNs,
          endNs,
          durationMs,
          statusCode: s.status?.code ?? 0,
          statusMessage: s.status?.message ?? "",
          attrs,
        });
      }
    }
  }
  return out;
}
