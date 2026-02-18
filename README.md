# Project Gamma — Logistics Operations Intelligence

An on-prem-ready AI platform that automates logistics accounting and document workflows. Powered by Claude AI for document extraction, cost allocation, operational Q&A, anomaly detection, and three-way reconciliation — with full audit trails and human-in-the-loop review.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Next.js](https://img.shields.io/badge/Next.js-15-black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)
![Claude](https://img.shields.io/badge/Claude-Sonnet-orange)
![MCP](https://img.shields.io/badge/MCP-Server-purple)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## What It Does

Project Gamma turns logistics documents (freight invoices, bills of lading) into structured, actionable data — then allocates costs to the right accounts and answers operational questions about your procedures.

### Document Intelligence
- **Multi-format parsing** — PDF (via pdfplumber), images/scans (via Claude Vision), CSV
- **Auto-classification** — Claude Haiku pre-screens documents by type (fast and cheap)
- **2-pass extraction** — Claude Sonnet extracts structured data, then self-reviews for accuracy
- **Supported document types:** Freight Invoices, Bills of Lading, Commercial Invoices, Purchase Orders, Packing Lists, Arrival Notices, Air Waybills, Debit/Credit Notes, CBP 7501 Customs Entries, Proof of Delivery, Certificates of Origin

### Cost Allocation
- **AI-powered mapping** — Claude maps each invoice line item to project codes, cost centers, and GL accounts
- **10 built-in business rules** — Ocean freight, air freight, customs, drayage, warehousing, and more
- **Confidence scoring** — Items with ≥85% confidence are auto-approved; lower confidence items are flagged for human review
- **Manual overrides** — Inline editing to correct any allocation before final approval

### RAG Q&A Engine
- **Voyage AI embeddings** — 1024-dimensional vectors via `voyage-3`
- **pgvector similarity search** — Cosine similarity retrieval over ingested documents and SOPs
- **Cited answers** — Claude answers with `[Source N]` citations linking back to source chunks
- **Knowledge base** — Ingest extractions and standard operating procedures for searchable Q&A

### Guardrails & Production Hardening (Phase 4)
- **Audit logging** — Immutable append-only audit trail for every action (uploads, extractions, allocations, reviews, anomalies)
- **HITL workflow** — Human-in-the-loop review queue with auto-approve rules ($1K low-risk threshold, $10K mandatory review), approve/reject/escalate state machine, enriched review detail with evidence panels, reviewer guidance, and one-click quick actions
- **Anomaly detection** — Duplicate invoice detection, budget overrun alerts, low-confidence flagging, missing approval checks
- **Reconciliation engine** — Cross-references TMS shipments vs ERP GL entries with deterministic + fuzzy matching
- **MCP server** — Model Context Protocol server for Claude Desktop integration with 4 logistics tools (freight lanes, inventory, budgets, purchase orders)
- **Mock data generator** — 500 shipments, 50 SKUs, 200 POs, 5 project budgets for demo and testing
- **Data Explorer** — Tabbed UI to browse all mock logistics data (shipments, inventory, POs, GL entries, budgets) with search, pagination, and utilization bars
- **RAG eval suite** — 10-question benchmark with hit rate, MRR, and answer accuracy metrics
- **Structured logging** — JSON request logs with request ID tracing
- **Sentry integration** — Optional error monitoring (conditional on `SENTRY_DSN`)
- **Metrics endpoint** — System-wide metrics (eval scores, HITL stats, anomaly counts)
- **SSO login page** — Premium split-screen login with Google and Microsoft SSO buttons, email/password form, localStorage-persisted mock auth session, auth-gated app shell with user info in sidebar

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       Next.js 15 Frontend                        │
│   Login (SSO) · Dashboard · Documents · Allocations · Chat       │
│   Reviews · Anomalies · Reconciliation · Data Explorer · Audit   │
│              (React 19, Tailwind, shadcn/ui)                     │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTP/REST
┌──────────────────────────▼───────────────────────────────────────┐
│                      FastAPI Backend                              │
│                                                                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────────┐ │
│  │  Document    │ │  Cost        │ │  RAG Q&A    │ │  Anomaly   │ │
│  │  Extractor   │ │  Allocator   │ │  Engine     │ │  Flagger   │ │
│  │             │ │             │ │             │ │            │ │
│  │ Parse→Class │ │ Rules→Claude│ │ Embed→Find  │ │ Dup/Budget │ │
│  │ →Extract    │ │ →Allocate   │ │ →Answer     │ │ →Low Conf  │ │
│  │ →Review     │ │ →Score      │ │ →Cite       │ │ →Flag      │ │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └─────┬──────┘ │
│         │               │               │              │         │
│  ┌──────┴───────────────┴───────────────┴──────────────┴──────┐  │
│  │                Claude API (Anthropic SDK)                   │  │
│  │         Sonnet (extraction / allocation / Q&A / audit)      │  │
│  │         Haiku (classification)                              │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────────┐ │
│  │  Reconcil.   │ │  HITL        │ │  Audit       │ │  Eval      │ │
│  │  Engine      │ │  Workflow    │ │  Generator   │ │  Suite     │ │
│  │             │ │             │ │             │ │            │ │
│  │ TMS↔WMS↔ERP│ │ Auto-approve│ │ Append-only │ │ Extraction │ │
│  │ Match+Fuzzy │ │ Review Queue│ │ Event Log   │ │ RAG Quality│ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └────────────┘ │
└──────────┬──────────────────────────────┬──────────┬─────────────┘
           │                              │          │
┌──────────▼──────────┐     ┌─────────────▼───┐  ┌──▼──────────────┐
│  PostgreSQL + pgvec │     │   Redis         │  │  MCP Server     │
│  Documents, Allocs, │     │   Cache & Queue  │  │  Claude Desktop │
│  Embeddings (1024d),│     │                 │  │  4 logistics    │
│  Audit, Reviews,    │     │                 │  │  tools (stdio)  │
│  Anomalies, Recon   │     │                 │  │                 │
└─────────────────────┘     └─────────────────┘  └─────────────────┘
```

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [Anthropic API key](https://console.anthropic.com/)
- [Voyage AI API key](https://dash.voyageai.com/) (for RAG embeddings)

### 1. Clone and configure

```bash
git clone https://github.com/eliascham/Project-Gamma---Logistics.git
cd Project-Gamma---Logistics
cp .env.example .env
```

Edit `.env` and add your API keys:

```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
VOYAGE_API_KEY=pa-your-key-here
```

### 2. Start services

```bash
docker compose up -d
```

This starts 5 services:

| Service    | Port  | Description                        |
|------------|-------|------------------------------------|
| **backend**  | 8000  | FastAPI API server                 |
| **frontend** | 3000  | Next.js web UI                     |
| **postgres** | 5432  | PostgreSQL 16 + pgvector           |
| **redis**    | 6379  | Redis 7 (cache/queue)              |
| **pgweb**    | 8081  | PostgreSQL web admin               |

### 3. Run migrations

```bash
docker exec gamma-backend alembic upgrade head
```

### 4. Seed demo data

```bash
# Seed cost allocation business rules
curl -X POST http://localhost:8000/api/v1/allocations/rules/seed

# Seed sample SOPs for RAG
curl -X POST http://localhost:8000/api/v1/rag/ingest/seed

# Seed mock logistics data (MCP server + reconciliation)
curl -X POST http://localhost:8000/api/v1/mcp/seed
```

### 5. Open the app

- **Frontend:** http://localhost:3000
- **API docs:** http://localhost:8000/docs
- **DB admin:** http://localhost:8081

---

## Usage

### Upload and extract a document

```bash
# Upload a freight invoice or bill of lading
curl -X POST http://localhost:8000/api/v1/documents \
  -F "file=@your-invoice.pdf"

# Trigger extraction (2-pass: extract → self-review)
curl -X POST http://localhost:8000/api/v1/extractions/{document_id}

# View extraction results
curl http://localhost:8000/api/v1/extractions/{document_id}
```

### Run cost allocation

```bash
# Allocate costs for an extracted invoice
curl -X POST http://localhost:8000/api/v1/allocations/{document_id}

# View allocation with line items and confidence scores
curl http://localhost:8000/api/v1/allocations/{document_id}
```

### Ask questions (RAG)

```bash
curl -X POST http://localhost:8000/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What GL account is used for ocean freight?"}'
```

### Scan for anomalies

```bash
# Run anomaly detection on a document (duplicate invoice, budget overrun, etc.)
curl -X POST http://localhost:8000/api/v1/anomalies/scan \
  -H "Content-Type: application/json" \
  -d '{"document_id": "your-document-uuid"}'

# View flagged anomalies
curl http://localhost:8000/api/v1/anomalies/list
```

### Run reconciliation

```bash
# Seed mock TMS/WMS/ERP data
curl -X POST http://localhost:8000/api/v1/reconciliation/seed

# Run three-way reconciliation (TMS shipments vs ERP GL entries)
curl -X POST http://localhost:8000/api/v1/reconciliation/run

# View match results
curl http://localhost:8000/api/v1/reconciliation/runs
```

### Review queue (HITL)

```bash
# View pending reviews (anomalies, low-confidence allocations, mismatches)
curl http://localhost:8000/api/v1/reviews/queue

# Approve a review item
curl -X POST http://localhost:8000/api/v1/reviews/{id}/action \
  -H "Content-Type: application/json" \
  -d '{"action": "approved", "notes": "Reviewed and confirmed"}'
```

### Audit trail

```bash
# Browse audit events
curl http://localhost:8000/api/v1/audit/events

# Generate a Claude-powered audit report
curl -X POST http://localhost:8000/api/v1/audit/reports \
  -H "Content-Type: application/json" \
  -d '{"days": 30}'
```

---

## API Reference

### Documents & Extraction

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/documents` | Upload document (multipart) |
| `GET` | `/api/v1/documents` | List documents (paginated) |
| `GET` | `/api/v1/documents/{id}` | Get document details |
| `POST` | `/api/v1/extractions/{document_id}` | Trigger extraction pipeline |
| `GET` | `/api/v1/extractions/{document_id}` | Get extraction results |

### Cost Allocation

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/allocations/{document_id}` | Run cost allocation |
| `GET` | `/api/v1/allocations/{document_id}` | Get allocation results |
| `PUT` | `/api/v1/allocations/line-items/{id}` | Override line item codes |
| `POST` | `/api/v1/allocations/{id}/approve` | Approve or reject allocation |
| `GET` | `/api/v1/allocations/rules/list` | List active business rules |
| `POST` | `/api/v1/allocations/rules/seed` | Seed 10 demo rules |

### RAG Q&A

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/rag/query` | Ask a question |
| `POST` | `/api/v1/rag/ingest/{document_id}` | Ingest document into knowledge base |
| `POST` | `/api/v1/rag/ingest/seed` | Seed sample SOPs |
| `GET` | `/api/v1/rag/stats` | Knowledge base statistics |

### Audit & Reviews

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/audit/events` | List audit events (paginated, filterable) |
| `POST` | `/api/v1/audit/reports` | Generate Claude-powered audit report |
| `GET` | `/api/v1/audit/stats` | Audit event statistics |
| `GET` | `/api/v1/reviews/queue` | Get review queue (paginated, filterable) |
| `GET` | `/api/v1/reviews/{id}` | Get review item details (enriched with evidence, guidance, quick actions) |
| `POST` | `/api/v1/reviews/{id}/action` | Approve/reject/escalate review item |
| `GET` | `/api/v1/reviews/stats` | Review queue statistics |

### Anomaly Detection

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/anomalies/scan` | Run anomaly detection scan |
| `GET` | `/api/v1/anomalies/list` | List anomaly flags (filterable) |
| `GET` | `/api/v1/anomalies/{id}` | Get anomaly details |
| `POST` | `/api/v1/anomalies/{id}/resolve` | Resolve an anomaly |
| `GET` | `/api/v1/anomalies/stats` | Anomaly statistics |
| `POST` | `/api/v1/anomalies/audit-summary` | Claude-powered anomaly audit summary |

### Reconciliation

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/reconciliation/run` | Run TMS/ERP reconciliation |
| `POST` | `/api/v1/reconciliation/seed` | Seed mock logistics data |
| `GET` | `/api/v1/reconciliation/runs` | List reconciliation runs |
| `GET` | `/api/v1/reconciliation/{id}` | Get run details with records |
| `GET` | `/api/v1/reconciliation/stats` | Reconciliation statistics |

### MCP Server & Data Explorer

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/mcp/status` | MCP server status and available tools |
| `POST` | `/api/v1/mcp/seed` | Seed mock data for MCP server |
| `GET` | `/api/v1/mcp/stats` | Mock data statistics |
| `GET` | `/api/v1/mcp/records` | Browse mock records (filterable by source, type, search) |
| `GET` | `/api/v1/mcp/budgets` | List all project budgets |

### Other

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Health check (DB + Redis) |
| `GET` | `/api/v1/metrics` | System metrics (eval, HITL, anomalies) |
| `POST` | `/api/v1/eval/run` | Run eval (extraction or RAG) |
| `GET` | `/api/v1/eval/results` | List eval runs |

---

## Project Structure

```
project-gamma/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app + middleware + lifespan
│   │   ├── config.py               # Environment config (pydantic-settings)
│   │   ├── database.py             # Async SQLAlchemy engine
│   │   ├── dependencies.py         # Dependency injection factories
│   │   ├── api/v1/                 # Route handlers
│   │   │   ├── health.py           #   Health + metrics endpoints
│   │   │   ├── documents.py        #   Document upload/list/detail
│   │   │   ├── extractions.py      #   Extraction pipeline triggers
│   │   │   ├── allocations.py      #   Cost allocation + overrides
│   │   │   ├── rag.py              #   RAG Q&A + ingestion
│   │   │   ├── audit.py            #   Audit event log + reports
│   │   │   ├── reviews.py          #   HITL review queue (enriched detail with context)
│   │   │   ├── anomalies.py        #   Anomaly detection + resolution
│   │   │   ├── reconciliation.py   #   Three-way reconciliation
│   │   │   ├── mcp_status.py       #   MCP server status + mock data
│   │   │   └── eval.py             #   Extraction + RAG eval suites
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   │   ├── document.py         #   Document + DocumentStatus
│   │   │   ├── cost_allocation.py  #   Allocation, LineItem, Rule
│   │   │   ├── embedding.py        #   pgvector embeddings
│   │   │   ├── rag.py              #   RAG query history
│   │   │   ├── audit.py            #   AuditEvent (immutable log)
│   │   │   ├── review.py           #   ReviewItem + state enums
│   │   │   ├── anomaly.py          #   AnomalyFlag + severity enums
│   │   │   ├── reconciliation.py   #   ReconciliationRun/Record
│   │   │   └── mock_data.py        #   MockLogisticsData, ProjectBudget
│   │   ├── schemas/                # Pydantic request/response schemas (incl. ReviewItemDetailResponse with EvidenceItem, SuggestedAction, ReviewContext)
│   │   ├── services/               # Claude API wrapper + document service
│   │   ├── document_extractor/     # Parse → classify → extract → review
│   │   ├── cost_allocator/         # Business rules + Claude allocation
│   │   ├── rag_engine/             # Voyage AI embeddings, chunking, retrieval, Q&A
│   │   ├── anomaly_flagger/        # Duplicate/budget/amount/confidence detectors
│   │   ├── audit_generator/        # Append-only audit log + Claude report generation
│   │   ├── hitl_workflow/          # Review queue state machine + trigger rules
│   │   ├── reconciliation_engine/  # TMS/ERP matching (deterministic + fuzzy)
│   │   ├── mcp_server/             # MCP server for Claude Desktop (stdio)
│   │   │   ├── server.py           #   LogisticsMCPServer (4 tools)
│   │   │   ├── data_layer.py       #   MCPDataLayer (DB queries)
│   │   │   ├── mock_data.py        #   Deterministic mock data generator
│   │   │   └── __main__.py         #   Entry point: python -m app.mcp_server
│   │   └── eval/                   # Extraction + RAG evaluation harness
│   ├── tests/                      # pytest test suites (74 Phase 4 tests)
│   └── alembic/                    # Database migrations (001-004)
├── frontend/
│   └── src/
│       ├── app/                    # Next.js pages
│       │   ├── login/              #   SSO login page (Google, Microsoft, email)
│       │   ├── page.tsx            #   Dashboard with Phase 4 widgets
│       │   ├── documents/          #   Document upload + list
│       │   ├── allocations/        #   Cost allocation detail
│       │   ├── chat/               #   RAG Q&A chat interface
│       │   ├── reviews/            #   HITL review queue + detail
│       │   ├── anomalies/          #   Anomaly list + resolution
│       │   ├── reconciliation/     #   Reconciliation runs + detail
│       │   ├── data-explorer/      #   MCP data browser (shipments, inventory, POs, GL, budgets)
│       │   └── audit/              #   Audit event timeline
│       ├── components/             # React components (30+)
│       ├── hooks/                  # Custom hooks
│       ├── lib/                    # API client, auth context, utilities
│       └── types/                  # TypeScript interfaces
├── docker-compose.yml              # 5-service orchestration
├── .env.example                    # Environment variable template
└── CLAUDE.md                       # Project context for AI assistants
```

---

## HITL Review Workflow

The human-in-the-loop system enforces review policies based on risk level:

```
                    ┌─────────────────┐
                    │  Event triggers  │
                    │  review item     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Apply autonomy  │
                    │  rules           │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
    ┌─────────▼───┐  ┌──────▼──────┐  ┌───▼──────────┐
    │ Low risk     │  │ Medium risk  │  │ High risk     │
    │ < $1,000     │  │ $1K - $10K   │  │ > $10,000     │
    │ High conf.   │  │              │  │               │
    │              │  │              │  │               │
    │ AUTO-APPROVE │  │ PENDING      │  │ MANDATORY     │
    │              │  │ REVIEW       │  │ REVIEW        │
    └──────────────┘  └──────┬──────┘  └───┬──────────┘
                             │              │
                    ┌────────▼──────────────▼┐
                    │    Human reviewer       │
                    │                        │
                    │  Approve / Reject /     │
                    │  Escalate              │
                    └────────┬───────────────┘
                             │
                    ┌────────▼────────┐
                    │  Audit event     │
                    │  logged          │
                    └─────────────────┘
```

**What triggers review items:**
- Cost allocations with confidence below 85%
- Anomaly flags (duplicate invoices, budget overruns)
- Reconciliation mismatches
- High-value transactions above $10K threshold

**Review detail experience:**
- **Reviewer guidance** — Type-specific instructions explaining what to check (e.g., "Compare dates and amounts to determine if this is a true duplicate")
- **Evidence panel** — Structured data from the anomaly (invoice numbers, budget amounts, confidence gaps, mismatch fields)
- **Quick actions** — One-click buttons with pre-filled notes per anomaly type (e.g., "Confirmed Duplicate" → reject, "Budget Exception Granted" → approve)
- **Related items** — Links to the source document and cost allocation
- **Custom action** — Manual approve/reject/escalate with free-form notes

---

## Database Schema (Phase 4)

Phase 4 adds 6 new tables to the existing schema:

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `audit_events` | Immutable append-only event log | entity_type, action, actor, previous/new state, rationale |
| `review_queue` | HITL review items with state machine | item_type, severity, status (pending→approved/rejected/escalated) |
| `anomaly_flags` | Detected anomalies per document | anomaly_type, severity, details, resolution status |
| `reconciliation_runs` | Reconciliation batch results | match_rate, matched/mismatch counts, summary |
| `reconciliation_records` | Individual record match results | source (TMS/WMS/ERP), match_status, confidence, reasoning |
| `mock_logistics_data` | Simulated TMS/WMS/ERP records | data_source, record_type, reference_number, JSON data |
| `project_budgets` | Project budget tracking | project_code, budget_amount, spent_amount, cost_center |

---

## Tech Stack

### Backend
- **Python 3.12** — async throughout
- **FastAPI** — REST API framework
- **SQLAlchemy** (async) + **asyncpg** — database ORM
- **Anthropic SDK** — Claude Sonnet (extraction, allocation, Q&A) + Haiku (classification)
- **Voyage AI** — `voyage-3` embeddings (1024-dim)
- **pdfplumber** — PDF text extraction
- **Pillow** — Image processing for Claude Vision
- **Alembic** — Database migrations

### Frontend
- **Next.js 15** — React 19 with App Router
- **Tailwind CSS** — Utility-first styling
- **shadcn/ui** — Component library
- **Framer Motion** — Animations and page transitions
- **lucide-react** — Icons

### Infrastructure
- **PostgreSQL 16** + **pgvector** — Relational DB with vector similarity search
- **Redis 7** — Caching and queue
- **Docker Compose** — Single-command deployment

---

## Extraction Schemas

### Freight Invoice
```json
{
  "invoice_number": "INV-2024-001",
  "invoice_date": "2024-01-15",
  "vendor_name": "Global Shipping Co.",
  "shipper_name": "ABC Manufacturing",
  "consignee_name": "XYZ Distribution",
  "origin": "Shanghai, CN",
  "destination": "Los Angeles, US",
  "currency": "USD",
  "line_items": [
    {
      "description": "Ocean freight - 40ft container",
      "quantity": 1,
      "unit": "container",
      "unit_price": 3500.00,
      "total": 3500.00
    }
  ],
  "subtotal": 3500.00,
  "tax_amount": 0.00,
  "total_amount": 3500.00
}
```

### Bill of Lading
```json
{
  "bol_number": "BOL-2024-12345",
  "carrier_name": "Maersk Line",
  "carrier_scac": "MAEU",
  "shipper": { "name": "...", "address": "..." },
  "consignee": { "name": "...", "address": "..." },
  "origin": { "city": "Shanghai", "country": "CN", "port_code": "CNSHA" },
  "destination": { "city": "Los Angeles", "country": "US", "port_code": "USLAX" },
  "vessel_name": "Emma Maersk",
  "container_numbers": ["MSKU1234567"],
  "cargo_description": "Electronic components",
  "gross_weight": "15000 KGS"
}
```

---

## Cost Allocation Rules

10 built-in rules map logistics charges to accounting codes:

| Rule | Match Pattern | GL Account | Cost Center |
|------|--------------|------------|-------------|
| Ocean Freight | ocean, sea, container, FCL, LCL | 5010 | LOGISTICS |
| Air Freight | air, express, cargo flight | 5020 | LOGISTICS |
| Ground Transport | truck, drayage, rail, intermodal | 5030 | LOGISTICS |
| Customs & Duties | customs, duty, tariff, import | 5040 | COMPLIANCE |
| Warehousing | storage, warehouse, handling | 5050 | WAREHOUSE |
| Documentation | documentation, B/L, certificate | 5060 | ADMIN |
| Labeling & Packaging | label, packaging, palletizing | 5070 | WAREHOUSE |
| Hazmat | hazardous, dangerous goods, DG | 5080 | COMPLIANCE |
| Insurance | insurance, cargo protection | 5090 | FINANCE |
| Miscellaneous | (fallback for unmatched items) | 5099 | GENERAL |

---

## Development

### Local backend (without Docker)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
python -m pytest tests/ -v
```

### Local frontend

```bash
cd frontend
pnpm install
pnpm dev
```

### Run tests

```bash
# Backend unit tests (uses SQLite, no Postgres needed)
cd backend && python -m pytest tests/ -v

# Frontend tests
cd frontend && pnpm test
```

### Test suites

```bash
# All backend tests (SQLite, no Postgres needed)
cd backend && python -m pytest tests/ -v

# Test breakdown:
#   test_cost_allocation.py   — Cost allocation pipeline + rules
#   test_rag.py               — Chunker, text conversion, QA pipeline
#   test_audit.py             — AuditService log/query, stats (8 tests)
#   test_hitl.py              — State machine, triggers, auto-approve (20 tests)
#   test_anomaly.py           — Duplicate, budget, amount detectors (16 tests)
#   test_reconciliation.py    — Ref/amount/date matchers, composite (19 tests)
#   test_mcp.py               — Mock data determinism, structure (11 tests)
```

### Run eval suites

```bash
# Extraction accuracy eval
curl -X POST http://localhost:8000/api/v1/eval/run

# RAG retrieval quality eval
curl -X POST "http://localhost:8000/api/v1/eval/run?eval_type=rag"
```

### MCP Server (Claude Desktop)

The MCP server exposes logistics data tools for Claude Desktop integration.

```bash
# From the backend directory:
python -m app.mcp_server
```

Add to Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "project-gamma": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/path/to/backend"
    }
  }
}
```

Available tools:
- `query_freight_lanes` — Search shipments by origin/destination/carrier
- `get_warehouse_inventory` — Query inventory across facilities
- `lookup_project_budget` — Check project budget utilization
- `search_purchase_orders` — Search POs by number/vendor/status

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key for Claude |
| `VOYAGE_API_KEY` | Yes | — | Voyage AI key for embeddings |
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `REDIS_URL` | Yes | — | Redis connection string |
| `CLAUDE_MODEL` | No | `claude-sonnet-4-20250514` | Main Claude model |
| `CLAUDE_MAX_TOKENS` | No | `4096` | Max response tokens |
| `VOYAGE_MODEL` | No | `voyage-3` | Embedding model |
| `EMBEDDING_DIMENSIONS` | No | `1024` | Vector dimensions |
| `ALLOCATION_CONFIDENCE_THRESHOLD` | No | `0.85` | Auto-approve threshold |
| `HITL_AUTO_APPROVE_DOLLAR_THRESHOLD` | No | `1000` | Auto-approve below this amount |
| `HITL_HIGH_RISK_DOLLAR_THRESHOLD` | No | `10000` | Mandatory review above this |
| `ANOMALY_BUDGET_OVERRUN_THRESHOLD` | No | `0.1` | Budget overrun alert threshold |
| `SENTRY_DSN` | No | — | Sentry error monitoring DSN |
| `ENVIRONMENT` | No | `development` | Runtime environment |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |

---

## Roadmap

- [x] **Phase 1** — Foundation (Docker, FastAPI, PostgreSQL, basic extraction, Next.js skeleton)
- [x] **Phase 2** — Document Intelligence (multi-format parsing, classification, 2-pass extraction, eval suite)
- [x] **Phase 3** — Cost Allocation & RAG (business rules, confidence scoring, Voyage AI embeddings, Q&A with citations)
- [x] **Phase 4** — Guardrails & Production Hardening (audit logging, HITL workflow, anomaly detection, reconciliation, MCP server, eval improvements, monitoring)
- [x] **Phase 5** — Document Intelligence Expansion (9 new document types, document relationships, 3-way matching, invoice variants, 169 tests)
- [ ] **Phase 6** — Enterprise Readiness (see below)
- [ ] **Phase 7** — AI Differentiators (see below)
- [ ] **Phase 8** — Platform & Integrations (see below)

---

## Phase 5-8 Roadmap (Planned)

### Phase 5: Document Intelligence Expansion

Gamma currently supports 2 document types; a single shipment generates 15-25+. The IDP market is growing at ~33% CAGR to $43.9B by 2034.

| Priority | Document Type | Impact | Why |
|----------|--------------|--------|-----|
| **P0** | Commercial Invoice | 10/10 | Required for every international shipment, customs matching |
| **P0** | Purchase Order | 9/10 | Enables 3-way matching (PO vs BOL vs Invoice) — core AP automation |
| **P0** | Packing List | 9/10 | Paired with commercial invoice for customs, weight/dimension validation |
| **P1** | Arrival Notice | 8/10 | Triggers import clearance, demurrage avoidance ($75-300/container/day) |
| **P1** | Air Waybill (AWB/HAWB) | 8/10 | Opens air freight vertical, complex chargeable weight auditing |
| **P1** | Debit/Credit Notes | 7/10 | #1 source of AP reconciliation errors, low implementation effort |
| **P2** | CBP 7501 (Customs Entry) | 7/10 | Duty audit and drawback claims |
| **P2** | Proof of Delivery | 7/10 | Closes the shipment loop, triggers payment release |
| **P2** | Certificate of Origin | 6/10 | Preferential duty rates under trade agreements |

**Document Relationship Model:** Track the PO -> BOL -> Invoice -> POD chain for cross-document validation, one-click audit packages, and 3-way matching.

**Invoice variant classification:** Detention/demurrage, accessorial charges, consolidated, pro-forma, debit/credit notes.

### Phase 6: Enterprise Readiness

| Priority | Feature | Impact | Effort |
|----------|---------|--------|--------|
| **P0** | Multi-tenancy (`tenant_id` + PostgreSQL RLS) | Critical | Large |
| **P0** | Real RBAC (roles/permissions, separation of duties) | Critical | Medium |
| **P1** | Multi-level configurable approval workflows | High | Medium |
| **P1** | Per-tenant business rules engine | High | Medium |
| **P1** | Accounting exports (QuickBooks, Xero, NetSuite) | High | Medium |
| **P1** | Email ingestion (auto-process invoices from email) | High | Medium |
| **P1** | SOX-compliant audit retention (WORM storage, 7-year retention) | High | Small |

### Phase 7: AI Differentiators

| Feature | Impact | Description |
|---------|--------|-------------|
| Smart GL coding with active learning | HIGH | Track user corrections, retrain allocation rules over time |
| Automated dispute detection | HIGH | Extend anomaly detection to auto-generate dispute claims with evidence |
| Natural language analytics | HIGH | Extend RAG to query operational data ("What's our avg cost per container?") |
| 3-way PO-BOL-Invoice matching | HIGH | Core freight audit — automated matching catches overcharges |
| Rate benchmarking | MEDIUM | Compare invoice rates against market/contracted rates |
| Carbon/emissions tracking | MEDIUM | Per-shipment emissions estimates, sustainability dashboards |
| Carrier performance scoring | MEDIUM | Score carriers on delivery, billing accuracy, dispute frequency |

### Phase 8: Platform & Integrations

| Feature | Priority | Notes |
|---------|----------|-------|
| EDI 210 inbound parsing | P2 | Automates invoice ingestion for automated clients |
| TMS connectors (MercuryGate, BluJay, OTM) | P2 | Replace mock data with live operational data |
| Notification system (email/Slack/SMS) | P2 | Configurable alerts, SLA breach notifications |
| Batch processing / bulk import | P2 | Handle thousands of documents at once |
| Spend analytics dashboard | P2 | Carrier spend, cost trending, budget vs actual |
| Multi-currency support | P2 | Required for international logistics |
| Agentic invoice processing | P3 | Autonomous end-to-end for routine invoices via MCP |
| Custom document type builder | P3 | Let clients define their own extraction schemas |
| White-label branding | P3 | Per-tenant logo, colors, custom domain |
| Multi-region / Kubernetes | P3 | GDPR data sovereignty, production scaling |

### Competitive Positioning

**Gamma's moat is three things competitors can't easily replicate:**

1. **On-prem / self-hosted** — CargoWise, Flexport, project44, Trax are all cloud-only. Defense, government, pharma, and EU clients under GDPR need data sovereignty.
2. **Transparent AI** — Claude explains its reasoning with evidence for every decision. Competitors are black boxes. The existing HITL enrichment (evidence, guidance, suggested actions) is genuinely differentiated.
3. **Unified pipeline** — Most competitors do document processing OR freight audit OR AP automation. Gamma does document-to-GL in one platform.

**Market timing:** CargoWise's 25-35% price increases are creating churn. The IDP market is growing at 33% CAGR. Freight audit & payment is a $2.5B+ market.

### Recommended Execution Order

```
Phase 5 (Complete): Commercial Invoice + PO + Packing List + 6 more doc types + Document Relationships + 3-Way Matching
Phase 6 (Next):    Multi-tenancy + RBAC + Configurable Approvals + Accounting Exports
Phase 7 (Then):    Smart GL Learning + Dispute Detection + NL Analytics + Email Ingestion
Phase 8 (Later):   EDI + TMS Connectors + Notifications + Batch Processing
```

---

## License

MIT
