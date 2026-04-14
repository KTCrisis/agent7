# agent7

Management plane for [agent-mesh](https://github.com/KTCrisis/agent-mesh) — a local dashboard and
supervisor service to observe, approve and govern agents running behind the mesh sidecar.

agent7 is the control side. agent-mesh is the runtime enforcement side. This repo contains
what currently runs locally; the broader governance platform (registry, scoring, dependency
graph, lifecycle) is built incrementally.

## Status

Early stage. Two pieces are operational:

- **supervisor** — Python service that watches `agent-mesh` approval queue, evaluates pending
  tool calls against declarative rules, and either auto-resolves or escalates. Falls back to
  a local Ollama model for ambiguous cases. Ships with a process manager and memory integration.
- **dashboard** — Next.js 16 + TanStack Query frontend with mesh-oriented routes:
  - `/mesh` — health, connected MCP servers, tool inventory
  - `/mesh/traces` — trace browser fed by agent-mesh `/traces`
  - `/mesh/sessions` — session list and drill-down
  - `/mesh/approvals` — pending approvals, approve/deny
  - `/mesh/otel` — OTEL waterfall view fed by agent-mesh `/otel-traces` (v0.6.1+)
  - `/mesh/memory` — mem7 memory browser (search, filter by agent, detail view)

Everything else in the tree (`backend/app/api`, `governance-engine/`, `schemas/`, `examples/`)
is scaffolding for future phases.

## Architecture

```
┌──────────────────────┐        ┌──────────────────────┐
│  agent7 frontend     │        │  agent7 supervisor   │
│  Next.js dashboard   │        │  rule-based approver │
│  localhost:3000      │        │  + Ollama fallback   │
└──────────┬───────────┘        └──────────┬───────────┘
           │                               │
           │  HTTP (/mesh, /traces,        │  HTTP (/approval/pending,
           │   /otel-traces, /approval)    │   /approval/resolve)
           ▼                               ▼
┌──────────────────────────────────────────────────────┐
│                  agent-mesh (Go)                     │
│  policy engine · rate limits · approvals · traces    │
│              localhost:9090                          │
└──────────────────────────────────────────────────────┘
           ▲
           │  JSON-RPC (/rpc)
┌──────────┴───────────┐
│       mem7 (Go)      │
│  memory substrate    │
│  localhost:9070      │
└──────────────────────┘
```

Both sides talk to agent-mesh over plain HTTP. No direct coupling between frontend and supervisor.
The frontend also connects directly to mem7 (JSON-RPC on port 9070) for the memory debug view.

## Local setup

Prerequisites:

- [agent-mesh](https://github.com/KTCrisis/agent-mesh) running on `localhost:9090`
- Node.js 20+
- Python 3.12+
- Optional: [Ollama](https://ollama.com) running locally for the supervisor LLM fallback
- Optional: [mem7](https://github.com/KTCrisis/mem7) in serve mode on `localhost:9070` for the memory view

### Dashboard

```bash
cd frontend
npm install
npm run dev
# http://localhost:3000
```

The dashboard proxies to `http://localhost:9090` (agent-mesh) and `http://localhost:9070` (mem7)
by default. Adjust in `frontend/next.config.ts` if they listen elsewhere.

### Supervisor

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m app.services.supervisor --config ../demo-supervisor.yaml
```

Example configs at the repo root (git-ignored):

- `demo-mesh-config.yaml` — mesh-side config exposing approval tools
- `demo-supervisor.yaml` — supervisor rules + Ollama fallback

Decisions and traces are logged to `*.jsonl` files (git-ignored).

### Tests

```bash
cd backend
pytest tests/supervisor
```

## Repo layout

| Path                              | Purpose                                  | State     |
|-----------------------------------|------------------------------------------|-----------|
| `backend/app/services/supervisor` | Rule-based approval agent                | Running   |
| `frontend/`                       | Next.js dashboard                        | Running   |
| `backend/app/{api,db,models}`     | FastAPI scaffolding                      | Skeleton  |
| `governance-engine/`              | Rules / scoring / severity / diff engine | Skeleton  |
| `schemas/`                        | JSON Schemas (agent, flow, template)     | Drafted   |
| `examples/`                       | YAML declarations (agents, flows, pol.)  | Drafted   |

## Related

- [agent-mesh](https://github.com/KTCrisis/agent-mesh) — runtime enforcement sidecar
- [mem7](https://github.com/KTCrisis/mem7) — governed memory substrate for multi-agent systems
- [event7](https://github.com/KTCrisis/event7) — sibling project for data contract governance
