const MEM7_BASE = "/api/mem7";

// ───────────────────────────────────────────────────────────
// JSON-RPC helper
// ───────────────────────────────────────────────────────────

let rpcId = 0;

interface RPCResponse<T = unknown> {
  jsonrpc: string;
  id: number;
  result?: T;
  error?: { code: number; message: string };
}

async function rpc<T = unknown>(
  method: string,
  params?: unknown
): Promise<T> {
  const res = await fetch(`${MEM7_BASE}/rpc`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: ++rpcId,
      method,
      params: params ?? {},
    }),
  });
  if (!res.ok) throw new Error(`mem7 RPC failed: ${res.status}`);
  const data: RPCResponse<T> = await res.json();
  if (data.error) throw new Error(data.error.message);
  return data.result as T;
}

// ───────────────────────────────────────────────────────────
// MCP tool call wrapper
// ───────────────────────────────────────────────────────────

interface MCPContent {
  content: { type: string; text: string }[];
  isError?: boolean;
}

async function toolCall(
  name: string,
  args: Record<string, unknown> = {}
): Promise<string> {
  const result = await rpc<MCPContent>("tools/call", { name, arguments: args });
  const text = result.content?.[0]?.text ?? "";
  if (result.isError) throw new Error(text);
  return text;
}

// ───────────────────────────────────────────────────────────
// Types
// ───────────────────────────────────────────────────────────

export interface MemoryEntry {
  key: string;
  tags: string[];
  agent: string;
  updated: string;
}

export interface MemoryDetail extends MemoryEntry {
  value: string;
}

export interface MemorySearchResult extends MemoryDetail {}

export interface Mem7Health {
  status: string;
}

export interface Mem7Info {
  protocolVersion: string;
  serverInfo: { name: string; version: string };
}

// ───────────────────────────────────────────────────────────
// Parsers — extract structured data from MCP text responses
// ───────────────────────────────────────────────────────────

/**
 * Parse memory_list output. Format:
 * "N memories:\n- key [tag1, tag2] (by agent) — 2026-04-14T..."
 */
function parseList(text: string): MemoryEntry[] {
  const lines = text.split("\n").filter((l) => l.startsWith("- "));
  return lines.map((line) => {
    const rest = line.slice(2); // strip "- "

    // Extract tags: [tag1, tag2]
    const tagMatch = rest.match(/\[([^\]]*)\]/);
    const tags = tagMatch
      ? tagMatch[1].split(",").map((t) => t.trim()).filter(Boolean)
      : [];

    // Extract agent: (by agent)
    const agentMatch = rest.match(/\(by ([^)]+)\)/);
    const agent = agentMatch ? agentMatch[1] : "";

    // Extract timestamp after " — "
    const tsMatch = rest.match(/— (\d{4}-\d{2}-\d{2}T\S+)/);
    const updated = tsMatch ? tsMatch[1] : "";

    // Key is everything before [tags] or (by agent) or " — "
    let key = rest;
    const firstMeta = Math.min(
      tagMatch ? rest.indexOf("[") : Infinity,
      agentMatch ? rest.indexOf("(by ") : Infinity,
      tsMatch ? rest.indexOf(" — ") : Infinity
    );
    if (firstMeta < Infinity) key = rest.slice(0, firstMeta).trim();

    return { key, tags, agent, updated };
  });
}

/**
 * Parse memory_recall / memory_search output. Format:
 * "## key\nvalue lines...\nTags: t1, t2\nAgent: foo\nUpdated: ...\n\n"
 */
function parseRecall(text: string): MemoryDetail[] {
  const blocks = text.split(/^## /m).filter(Boolean);
  return blocks.map((block) => {
    const lines = block.split("\n");
    const key = lines[0]?.trim() ?? "";
    let agent = "";
    let updated = "";
    const tags: string[] = [];
    const valueLines: string[] = [];

    for (let i = 1; i < lines.length; i++) {
      const l = lines[i];
      if (l.startsWith("Tags: ")) {
        l.slice(6).split(",").map((t) => t.trim()).filter(Boolean).forEach((t) => tags.push(t));
      } else if (l.startsWith("Agent: ")) {
        agent = l.slice(7).trim();
      } else if (l.startsWith("Updated: ")) {
        updated = l.slice(9).trim();
      } else {
        valueLines.push(l);
      }
    }

    // Trim trailing empty lines from value
    while (valueLines.length > 0 && valueLines[valueLines.length - 1].trim() === "") {
      valueLines.pop();
    }

    return { key, value: valueLines.join("\n"), tags, agent, updated };
  });
}

// ───────────────────────────────────────────────────────────
// API functions
// ───────────────────────────────────────────────────────────

export async function fetchMem7Health(): Promise<Mem7Health> {
  const res = await fetch(`${MEM7_BASE}/healthz`);
  if (!res.ok) throw new Error(`mem7 health check failed: ${res.status}`);
  return res.json();
}

export async function fetchMem7Info(): Promise<Mem7Info> {
  const result = await rpc<Mem7Info>("initialize");
  return result;
}

export async function fetchMemories(opts?: {
  tags?: string[];
  agent?: string;
}): Promise<MemoryEntry[]> {
  const args: Record<string, unknown> = {};
  if (opts?.tags?.length) args.tags = opts.tags;
  if (opts?.agent) args.agent = opts.agent;
  const text = await toolCall("memory_list", args);
  if (text.startsWith("No memories")) return [];
  return parseList(text);
}

export async function fetchMemoryDetail(key: string): Promise<MemoryDetail | null> {
  const text = await toolCall("memory_recall", { key });
  if (text.startsWith("No memories")) return null;
  const entries = parseRecall(text);
  return entries[0] ?? null;
}

export async function searchMemories(opts: {
  query: string;
  agent?: string;
  tags?: string[];
  limit?: number;
}): Promise<MemorySearchResult[]> {
  const args: Record<string, unknown> = { query: opts.query };
  if (opts.agent) args.agent = opts.agent;
  if (opts.tags?.length) args.tags = opts.tags;
  if (opts.limit) args.limit = opts.limit;
  const text = await toolCall("memory_search", args);
  if (text.startsWith("No memories")) return [];
  // Strip the "N results (ranked by relevance):\n\n" header
  const body = text.replace(/^\d+ results \(ranked by relevance\):\n\n/, "");
  return parseRecall(body);
}
