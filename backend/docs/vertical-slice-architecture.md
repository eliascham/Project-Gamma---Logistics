# Invoice Extraction + Reconciliation: Vertical Slice Architecture

## System Overview

This document describes the end-to-end invoice processing pipeline implemented
as a "single deep vertical slice" — demonstrating every layer from document
ingestion through agentic orchestration.

## Architecture Diagram

```
                         ┌─────────────────────────────────┐
                         │        Claude Desktop           │
                         │   (MCP Client / stdio+SSE)      │
                         └──────────┬──────────────────────┘
                                    │ MCP Protocol
                                    ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                          MCP Server (9 tools)                            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │query_freight │ │get_warehouse │ │lookup_budget │ │search_orders │   │
│  │   _lanes     │ │  _inventory  │ │              │ │              │   │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │get_document  │ │get_extraction│ │search_       │ │reconcile_    │   │
│  │  _details    │ │  _result     │ │ shipments    │ │  invoice     │   │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   │
│  ┌──────────────┐                                                       │
│  │list_review   │      Transport: stdio (Claude Desktop)                │
│  │  _queue      │                  SSE   (HTTP clients)                 │
│  └──────────────┘                                                       │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │ MCPDataLayer
                                ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                       FastAPI Backend (async)                            │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                    Agent Orchestrator                               │ │
│  │  ┌─────────┐  ┌──────────────┐  ┌────────────────────────────────┐│ │
│  │  │  Main   │  │  Sub-Agents  │  │      User Skills               ││ │
│  │  │ Agent   │  │  ┌──────────┐│  │  /process-invoice              ││ │
│  │  │ (8 tools│  │  │extraction││  │  /review-queue                 ││ │
│  │  │  full   │  │  │reconcile ││  │  /reconcile                    ││ │
│  │  │ access) │  │  │audit     ││  │  /extract                      ││ │
│  │  └─────────┘  │  └──────────┘│  └────────────────────────────────┘│ │
│  │               └──────────────┘                                     │ │
│  │  Claude tool_use loop:                                             │ │
│  │  goal → Claude → tool_use → ToolExecutor → result → Claude → done │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐│
│  │                     Processing Pipeline                              ││
│  │                                                                      ││
│  │  Document      Extraction       Validation      Reconciliation       ││
│  │  Upload    →   Pipeline     →   Layer       →   Engine              ││
│  │  (PDF/CSV/     (2-pass +        (7 pure         (multi-factor       ││
│  │   image)        confidence)      validators)     scoring)            ││
│  │                                                                      ││
│  │                    ┌────────────────────────────────┐                 ││
│  │                    │       HITL Review Queue        │                 ││
│  │                    │  ┌──────────────────────────┐  │                 ││
│  │                    │  │ Candidates │ Inline Edit │  │                 ││
│  │                    │  │ Exception Tasks          │  │                 ││
│  │                    │  │ Auto-approve rules       │  │                 ││
│  │                    │  └──────────────────────────┘  │                 ││
│  │                    └────────────────────────────────┘                 ││
│  │                                                                      ││
│  │                    ┌────────────────────────────────┐                 ││
│  │                    │       Audit Trail              │                 ││
│  │                    │  Every action logged with      │                 ││
│  │                    │  actor, entity, state diffs    │                 ││
│  │                    └────────────────────────────────┘                 ││
│  └──────────────────────────────────────────────────────────────────────┘│
│                                                                          │
└──────────────────────────────┬────────────────────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    PostgreSQL + pgvec│
                    │                      │
                    │  documents           │
                    │  extractions         │
                    │  review_queue        │
                    │  mock_logistics_data │
                    │  audit_events        │
                    │  project_budgets     │
                    └──────────────────────┘
```

## Data Flow: Invoice Processing Vertical Slice

```
1. INGEST                    2. EXTRACT                   3. VALIDATE
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│ Upload invoice  │         │ Pass 1: Extract │         │ 7 pure          │
│ (PDF/CSV/image) │────────▶│ Pass 2: Review  │────────▶│ validators:     │
│                 │         │ Confidence:     │         │ • required      │
│ Classify type   │         │  per-field      │         │ • math check    │
│ (Haiku)         │         │  agreement-     │         │ • totals        │
│                 │         │  based scoring  │         │ • dates         │
└─────────────────┘         └─────────────────┘         │ • currency      │
                                                         │ • amounts       │
                                                         │ • references    │
                                                         └────────┬────────┘
                                                                  │
                                                                  ▼
4. RECONCILE                 5. REVIEW                   6. AUDIT
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│ Match invoice   │         │ Auto-approve    │         │ Immutable log   │
│ to shipments:   │────────▶│ (< $1K + ≥85%) │────────▶│ of every action │
│                 │         │                 │         │                 │
│ Score factors:  │         │ Review queue:   │         │ Entity diffs    │
│  PO     (30%)   │         │ • candidates    │         │ Actor tracking  │
│  Vendor (25%)   │         │ • inline edit   │         │ Timestamp       │
│  Amount (25%)   │         │ • exception     │         │                 │
│  Date   (15%)   │         │   tasks         │         │ Claude-powered  │
│  Ref    (5%)    │         │                 │         │ audit reports   │
│                 │         │ Suggested       │         │                 │
│ Ranked          │         │ actions per     │         │                 │
│ candidates      │         │ anomaly type    │         │                 │
└─────────────────┘         └─────────────────┘         └─────────────────┘
```

## Component Details

### A. Pipeline Enhancements

#### A1: Per-Field Confidence Scoring
- **Module:** `app/validator/confidence.py`
- **Approach:** Agreement-based scoring — compares Pass 1 and Pass 2 extraction
  results, blends with Claude-reported confidence
- **Output:** Per-field float (0.0-1.0) + overall document confidence
- **Usage:** Low-confidence fields trigger HITL review

#### A2: Deterministic Validation Layer
- **Module:** `app/validator/validators.py`, `app/validator/service.py`
- **7 pure validators** (no DB, no Claude — fast, testable):
  1. Required fields check
  2. Line item math verification (qty × unit_price = total)
  3. Invoice total vs line item sum
  4. Date format and range validation
  5. Currency code validation (ISO 4217)
  6. Positive amount check
  7. Reference number format validation
- **Output:** `ValidationResult` with issues list, pass/fail, severity

#### A3: Invoice-to-Shipment Reconciliation
- **Module:** `app/reconciliation_engine/invoice_reconciler.py`
- **Multi-factor scoring:** PO (30%), vendor (25%), amount (25%), date (15%), ref (5%)
- **Fuzzy matching:** Vendor name substring matching, amount tolerance (configurable),
  date window (configurable)
- **Output:** Ranked candidates with `ReconciliationResult`, auto-match if clear winner
- **Statuses:** `STRONG_MATCH`, `LIKELY_MATCH`, `WEAK_MATCH`, `NO_MATCH`

#### A4: HITL Enhancements
- **Reconciliation candidates in review context** — when review items include
  reconciliation data in metadata, the detail view displays ranked candidates
- **Inline field editing** — `PATCH /reviews/{id}` updates title, description,
  assigned_to, severity, dollar_amount, review_metadata
- **Exception tasks** — `POST /reviews/{id}/exception` creates follow-up tasks
  linked to parent review items (type `EXCEPTION_TASK`)
- **New anomaly type** — `invoice_reconciliation` with dedicated guidance +
  suggested actions

### B. Agentic Architecture

#### B1: MCP Server Expansion
- **Module:** `app/mcp_server/server.py`
- **9 tools total:** 4 data query + 5 invoice processing
- **Dual transport:** stdio (Claude Desktop) + SSE (HTTP clients via `--sse`)
- **New tools:** `get_document_details`, `get_extraction_result`,
  `search_shipments`, `reconcile_invoice`, `list_review_queue`

#### B2: Invoice Processing Agent
- **Module:** `app/agent/orchestrator.py`
- **Pattern:** Claude `tool_use` conversation loop
  1. Send goal + system prompt + tools to Claude
  2. Claude returns `tool_use` content blocks
  3. `ToolExecutor` dispatches to backend services
  4. Results fed back as `tool_result`
  5. Repeat until Claude returns text-only (done) or max turns
- **8 tools:** extract, validate, search_shipments, reconcile, create_review_item,
  log_audit_event, get_document_info, get_extraction

#### B3: Sub-Agents
- **Module:** `app/agent/sub_agents.py`
- **3 specialized agents** with focused tool subsets and system prompts:
  - **Extraction agent:** Extract + validate + log (5 tools)
  - **Reconciliation agent:** Get extraction + search + reconcile + review (5 tools)
  - **Audit agent:** Get info + create review + log (4 tools)
- Reuses `run_agent()` with different `system_prompt` and `tools` params

#### B4: User-Invocable Skills
- **Module:** `app/agent/skills.py`
- **4 skills** mapped to agent types:
  - `/process-invoice` → main agent (full pipeline)
  - `/review-queue` → audit sub-agent
  - `/reconcile` → reconciliation sub-agent
  - `/extract` → extraction sub-agent
- Skills use goal templates with `{document_id}` placeholders

### C. Demo Data

#### C1: Demo Data Seeder
- **Module:** `app/demo/seeder.py`
- **5 invoice scenarios:**
  | # | Scenario | Vendor | Amount | What Happens |
  |---|----------|--------|--------|--------------|
  | 1 | Perfect match | Maersk | $12,500 | All fields align → auto-approve |
  | 2 | Amount mismatch | MSC | $18,750 | $850 difference → triggers review |
  | 3 | No match | COSCO | $7,200 | Wrong PO → exception task |
  | 4 | High-value | Hapag-Lloyd | $32,000 | Above $10K threshold → mandatory review |
  | 5 | Close candidates | Evergreen | $9,800 | Two matching shipments → ambiguous |
- **6 matching shipments** (one per invoice + extra for scenario 5)
- **Idempotent:** Second call is a no-op
- **Endpoint:** `POST /api/v1/demo/seed`

## API Endpoints (New in This Slice)

### Agent & Skills
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/agent/run` | Run main agent |
| POST | `/api/v1/agent/sub-agent` | Run sub-agent |
| POST | `/api/v1/agent/skills/{name}` | Run skill |
| GET | `/api/v1/agent/agents` | List agent types |
| GET | `/api/v1/agent/skills` | List skills |

### HITL Enhancements
| Method | Path | Description |
|--------|------|-------------|
| PATCH | `/api/v1/reviews/{id}` | Inline field editing |
| POST | `/api/v1/reviews/{id}/exception` | Create exception task |

### Demo
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/demo/seed` | Seed demo data |
| GET | `/api/v1/demo/scenarios` | List scenarios |

## Test Coverage

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_validation.py` | 41 | 7 validators, service, confidence scoring |
| `test_invoice_reconciler.py` | 19 | Scoring, reconciliation, ranked candidates |
| `test_agent.py` | 35 | Tool defs, executor, orchestrator, sub-agents, skills |
| `test_hitl.py` | 41 | State machine, triggers, field editing, exception tasks, candidates |
| `test_mcp.py` | 21 | Tool definitions, reconciliation serialization |
| `test_demo.py` | 17 | Data integrity, seeder, scenarios |
| **Total new** | **174** | All passing, zero regressions |

## Demo Walkthrough

```bash
# 1. Start the stack
docker compose up -d

# 2. Seed mock logistics data (500 shipments, 200 POs, 5 budgets)
curl -X POST http://localhost:8000/api/v1/mcp/seed

# 3. Seed demo invoices (5 scenarios + matching shipments)
curl -X POST http://localhost:8000/api/v1/demo/seed

# 4. List demo scenarios
curl http://localhost:8000/api/v1/demo/scenarios

# 5. Run the agent on the "perfect match" invoice
curl -X POST http://localhost:8000/api/v1/agent/skills/process-invoice \
  -H "Content-Type: application/json" \
  -d '{"document_id": "d0000001-0001-4000-a000-000000000001"}'

# 6. Run reconciliation sub-agent on "amount mismatch"
curl -X POST http://localhost:8000/api/v1/agent/sub-agent \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "reconciliation",
    "goal": "Reconcile invoice d0000001-0002-4000-a000-000000000002",
    "document_id": "d0000001-0002-4000-a000-000000000002"
  }'

# 7. Check the review queue
curl http://localhost:8000/api/v1/reviews/queue

# 8. View audit trail
curl http://localhost:8000/api/v1/audit/events
```
