# Project Gamma — Logistics Operations Intelligence

A logistics intelligence platform powered by Claude AI. Automates document extraction, cost allocation, anomaly detection, reconciliation, and operational Q&A across 11 document types — with eval harnesses, human-in-the-loop review, and full audit trails.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Next.js](https://img.shields.io/badge/Next.js-15-black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)
![Claude](https://img.shields.io/badge/Claude-Sonnet-orange)
![MCP](https://img.shields.io/badge/MCP-Server-purple)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## What It Does

Project Gamma turns logistics documents into structured, actionable data — then allocates costs to the right accounts, detects anomalies, reconciles across systems, and answers operational questions about your procedures.

### Document Intelligence
- **Multi-format parsing** — PDF (via pdfplumber), images/scans (via Claude Vision), CSV
- **Auto-classification** — Claude Haiku pre-screens documents by type (fast and cheap)
- **2-pass extraction** — Claude Sonnet extracts structured data, then self-reviews for accuracy
- **11 document types:** Freight Invoice, Bill of Lading, Commercial Invoice, Purchase Order, Packing List, Arrival Notice, Air Waybill, Debit/Credit Note, CBP 7501 Customs Entry, Proof of Delivery, Certificate of Origin
- **Document relationships** — Auto-detects PO → BOL → Invoice → POD chains from reference numbers
- **Invoice variant classification** — Detention/demurrage, accessorial, consolidated, pro-forma, debit/credit

### Cost Allocation
- **AI-powered mapping** — Claude maps each invoice line item to project codes, cost centers, and GL accounts
- **14 built-in business rules** — Ocean freight, air freight, customs, drayage, warehousing, import duties, MPF, HMF, and more
- **Confidence scoring** — Items with ≥85% confidence are auto-approved; lower confidence items are flagged for human review
- **Manual overrides** — Inline editing to correct any allocation before final approval
- **Multi-type support** — Freight invoices, commercial invoices, CBP 7501, debit/credit notes

### RAG Q&A Engine
- **Voyage AI embeddings** — 1024-dimensional vectors via `voyage-3`
- **pgvector similarity search** — Cosine similarity retrieval over ingested documents and SOPs
- **Cited answers** — Claude answers with `[Source N]` citations linking back to source chunks
- **Knowledge base** — Ingest extractions and standard operating procedures for searchable Q&A

### 3-Way Document Matching
- **PO-BOL-Invoice matching** — Pairs documents and compares quantities, amounts, parties, and line items
- **Configurable tolerances** — Numeric matching with percentage and absolute thresholds
- **Fuzzy matching** — Party name similarity, description word-overlap, reference number normalization
- **Auto-detection** — Finds related documents from extraction references and runs matching automatically

### Anomaly Detection
- **Duplicate invoice detection** — Flags invoices with matching vendor + amount within a configurable window
- **Budget overrun alerts** — Triggers when project spend exceeds budget by a configurable threshold
- **Low-confidence flagging** — Surfaces extractions and allocations below confidence thresholds
- **Missing approval checks** — Identifies high-value items that bypassed required review

### Reconciliation
- **Cross-system matching** — TMS shipments vs ERP GL entries with deterministic + fuzzy matching
- **Reference-first strategy** — Exact reference match, then fallback to amount/date similarity
- **Mismatch reports** — Detailed diffs with confidence scores and match reasoning

### Human-in-the-Loop Review
- **Risk-based routing** — Auto-approve low-risk (<$1K, high confidence), mandatory review for high-risk (>$10K)
- **State machine** — Pending → Approved / Rejected / Escalated
- **Enriched detail view** — Evidence panels, reviewer guidance, suggested quick actions per anomaly type
- **Audit logging** — Immutable append-only trail for every action

### MCP Server
- **Claude Desktop integration** — 4 logistics tools via Model Context Protocol (stdio)
- **Tools:** Query freight lanes, get warehouse inventory, lookup project budgets, search purchase orders
- **Mock data** — 500 shipments, 50 SKUs, 200 POs, 5 project budgets

### Eval Suites
- **Extraction eval** — Field-level precision/recall/F1 against ground truth for all 11 document types (22 ground truth documents)
- **Classification eval** — Classifier accuracy, per-type accuracy, and confusion matrix across all ground truth docs
- **Validation eval** — Precision/recall/F1 for 7 deterministic validators against annotated test cases (5 scenarios: bad math, bad totals, bad dates, bad refs, clean)
- **Confidence calibration eval** — ECE (Expected Calibration Error), Brier score, calibration bins measuring whether confidence scores match actual accuracy
- **RAG eval** — 20-question benchmark (15 positive + 5 negative) with hit rate, MRR, answer accuracy, negative rejection rate, and per-category accuracy
- **Regression baseline** — Save/load/compare eval scores against a baseline with configurable tolerance (default 2%) to detect regressions

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
│  │  Reconcil.   │ │  HITL        │ │  Audit       │ │  Matching  │ │
│  │  Engine      │ │  Workflow    │ │  Generator   │ │  Engine    │ │
│  │             │ │             │ │             │ │            │ │
│  │ TMS↔WMS↔ERP│ │ Auto-approve│ │ Append-only │ │ PO↔BOL↔INV │ │
│  │ Match+Fuzzy │ │ Review Queue│ │ Event Log   │ │ 3-Way Match│ │
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
# Upload a document (freight invoice, BOL, commercial invoice, PO, etc.)
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

### 3-way document matching

```bash
# Run PO-BOL-Invoice matching (provide at least 2 of 3 document IDs)
curl -X POST http://localhost:8000/api/v1/matching/run \
  -H "Content-Type: application/json" \
  -d '{"po_document_id": "...", "invoice_document_id": "..."}'

# Auto-detect related documents and match
curl -X POST http://localhost:8000/api/v1/matching/auto/{document_id}
```

### Document relationships

```bash
# Auto-detect relationships from extraction references
curl -X POST http://localhost:8000/api/v1/relationships/detect/{document_id}

# List relationships for a document
curl http://localhost:8000/api/v1/relationships/?document_id={document_id}
```

### Scan for anomalies

```bash
curl -X POST http://localhost:8000/api/v1/anomalies/scan \
  -H "Content-Type: application/json" \
  -d '{"document_id": "your-document-uuid"}'

curl http://localhost:8000/api/v1/anomalies/list
```

### Run reconciliation

```bash
curl -X POST http://localhost:8000/api/v1/reconciliation/run \
  -H "Content-Type: application/json" \
  -d '{"run_by": "user"}'

curl http://localhost:8000/api/v1/reconciliation/runs
```

### Review queue (HITL)

```bash
curl http://localhost:8000/api/v1/reviews/queue

curl -X POST http://localhost:8000/api/v1/reviews/{id}/action \
  -H "Content-Type: application/json" \
  -d '{"action": "approved", "notes": "Reviewed and confirmed"}'
```

### Audit trail

```bash
curl http://localhost:8000/api/v1/audit/events

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
| `POST` | `/api/v1/allocations/rules/seed` | Seed demo rules |

### RAG Q&A

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/rag/query` | Ask a question |
| `POST` | `/api/v1/rag/ingest/{document_id}` | Ingest document into knowledge base |
| `POST` | `/api/v1/rag/ingest/seed` | Seed sample SOPs |
| `GET` | `/api/v1/rag/stats` | Knowledge base statistics |

### Document Relationships

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/relationships/` | Create a relationship manually |
| `GET` | `/api/v1/relationships/` | List relationships (filterable) |
| `GET` | `/api/v1/relationships/{id}` | Get a single relationship |
| `DELETE` | `/api/v1/relationships/{id}` | Delete a relationship |
| `POST` | `/api/v1/relationships/detect/{document_id}` | Auto-detect from extraction references |

### 3-Way Matching

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/matching/run` | Run PO-BOL-Invoice matching |
| `POST` | `/api/v1/matching/auto/{document_id}` | Auto-detect and match related documents |

### Audit & Reviews

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/audit/events` | List audit events (paginated, filterable) |
| `POST` | `/api/v1/audit/reports` | Generate Claude-powered audit report |
| `GET` | `/api/v1/audit/stats` | Audit event statistics |
| `GET` | `/api/v1/reviews/queue` | Get review queue (paginated, filterable) |
| `GET` | `/api/v1/reviews/{id}` | Get review detail (evidence, guidance, actions) |
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
| `GET` | `/api/v1/mcp/records` | Browse mock records (filterable) |
| `GET` | `/api/v1/mcp/budgets` | List all project budgets |

### Other

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Health check (DB + Redis) |
| `GET` | `/api/v1/metrics` | System metrics (eval, HITL, anomalies) |
| `POST` | `/api/v1/eval/run` | Run eval suite (extraction, rag, classification, validation, confidence) |
| `GET` | `/api/v1/eval/results` | List eval runs |
| `GET` | `/api/v1/eval/results/{id}` | Get detailed eval result |
| `GET` | `/api/v1/eval/baseline` | Get saved baseline scores |
| `POST` | `/api/v1/eval/baseline/save` | Save current scores as baseline |
| `POST` | `/api/v1/eval/baseline/compare` | Compare current scores against baseline |

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
│   │   │   ├── health.py           #   Health + metrics
│   │   │   ├── documents.py        #   Document upload/list/detail
│   │   │   ├── extractions.py      #   Extraction pipeline
│   │   │   ├── allocations.py      #   Cost allocation + overrides
│   │   │   ├── rag.py              #   RAG Q&A + ingestion
│   │   │   ├── audit.py            #   Audit event log + reports
│   │   │   ├── reviews.py          #   HITL review queue
│   │   │   ├── anomalies.py        #   Anomaly detection + resolution
│   │   │   ├── reconciliation.py   #   Cross-system reconciliation
│   │   │   ├── relationships.py    #   Document relationship CRUD + auto-detect
│   │   │   ├── matching.py         #   3-way PO-BOL-Invoice matching
│   │   │   ├── mcp_status.py       #   MCP server status + mock data
│   │   │   └── eval.py             #   Eval suites (5 types) + baseline endpoints
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   ├── services/               # Claude API wrapper + document service
│   │   ├── document_extractor/     # Parse → classify → extract → review
│   │   ├── cost_allocator/         # Business rules + Claude allocation
│   │   ├── rag_engine/             # Voyage AI embeddings, chunking, retrieval, Q&A
│   │   ├── matching_engine/        # 3-way matching (numeric, party, description, line items)
│   │   ├── anomaly_flagger/        # Duplicate/budget/amount/confidence detectors
│   │   ├── audit_generator/        # Append-only audit log + Claude report generation
│   │   ├── hitl_workflow/          # Review queue state machine + trigger rules
│   │   ├── reconciliation_engine/  # TMS/ERP matching (deterministic + fuzzy)
│   │   ├── mcp_server/             # MCP server for Claude Desktop (stdio)
│   │   ├── eval/                   # Comprehensive eval suite (5 evaluators + baseline)
│   │   └── middleware/             # Structured JSON logging with request ID
│   ├── tests/                      # 510 tests (unit, integration, schema, stress, eval suite)
│   └── alembic/                    # Database migrations (001-005)
├── frontend/
│   └── src/
│       ├── app/                    # Next.js pages
│       │   ├── login/              #   Login page (Google, Microsoft SSO, email)
│       │   ├── page.tsx            #   Dashboard
│       │   ├── documents/          #   Document upload + list
│       │   ├── allocations/        #   Cost allocation detail
│       │   ├── chat/               #   RAG Q&A chat interface
│       │   ├── reviews/            #   HITL review queue + detail
│       │   ├── anomalies/          #   Anomaly list + resolution
│       │   ├── reconciliation/     #   Reconciliation runs + detail
│       │   ├── data-explorer/      #   MCP data browser
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

**Review triggers:** Low-confidence allocations, anomaly flags, reconciliation mismatches, high-value transactions.

**Review detail:** Evidence panels, type-specific reviewer guidance, one-click quick actions, related document links.

---

## Database Schema

| Table | Purpose |
|-------|---------|
| `documents` | Uploaded documents with status tracking |
| `extractions` | Extracted structured data with confidence scores |
| `cost_allocations` | Allocation results with line items |
| `allocation_rules` | Business rules for cost mapping |
| `embeddings` | pgvector embeddings (1024-dim) |
| `rag_queries` | RAG query history |
| `audit_events` | Immutable append-only event log |
| `review_queue` | HITL review items with state machine |
| `anomaly_flags` | Detected anomalies per document |
| `reconciliation_runs` | Reconciliation batch results |
| `reconciliation_records` | Individual record match results |
| `mock_logistics_data` | Simulated TMS/WMS/ERP records |
| `project_budgets` | Project budget tracking |
| `document_relationships` | Source → target document links with relationship type |

---

## Cost Allocation Rules

14 built-in rules map logistics charges to accounting codes:

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
| Import Duties | HTS, tariff, duty rate | 5041 | COMPLIANCE |
| MPF | merchandise processing fee | 5042 | COMPLIANCE |
| HMF | harbor maintenance fee | 5043 | COMPLIANCE |
| Accessorial | detention, demurrage, accessorial | 5035 | LOGISTICS |
| Miscellaneous | (fallback for unmatched items) | 5099 | GENERAL |

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

# 510 tests across:
#   test_cost_allocation.py        — Cost allocation pipeline + rules
#   test_rag.py                    — Chunker, text conversion, QA pipeline
#   test_audit.py                  — AuditService log/query, stats
#   test_hitl.py                   — State machine, triggers, auto-approve
#   test_anomaly.py                — Duplicate, budget, amount detectors
#   test_reconciliation.py         — Ref/amount/date matchers, composite
#   test_mcp.py                    — Mock data determinism, structure
#   test_phase5_schemas.py         — All 11 extraction schemas + shared models
#   test_phase5_matching.py        — 3-way matching functions + full orchestration
#   test_phase5_relationships.py   — Document relationships, reference maps
#   test_validation.py             — Extraction validation + edge cases
#   test_eval_suite.py             — Classification, validation, confidence, baseline, RAG evals
```

### Run eval suites

```bash
# Extraction accuracy eval (field-level F1 against 22 ground truth docs)
curl -X POST http://localhost:8000/api/v1/eval/run

# Classification accuracy eval (Haiku classifier vs ground truth types)
curl -X POST "http://localhost:8000/api/v1/eval/run?eval_type=classification"

# Validation eval (7 deterministic validators — precision/recall/F1)
curl -X POST "http://localhost:8000/api/v1/eval/run?eval_type=validation"

# Confidence calibration eval (ECE + Brier score)
curl -X POST "http://localhost:8000/api/v1/eval/run?eval_type=confidence"

# RAG retrieval quality eval (20 questions: hit rate, MRR, negative rejection)
curl -X POST "http://localhost:8000/api/v1/eval/run?eval_type=rag"

# Save current scores as regression baseline
curl -X POST http://localhost:8000/api/v1/eval/baseline/save

# Compare current scores against saved baseline (flags regressions >2%)
curl -X POST http://localhost:8000/api/v1/eval/baseline/compare
```

### MCP Server (Claude Desktop)

```bash
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
| `ANOMALY_BUDGET_OVERRUN_THRESHOLD` | No | `0.1` | Budget overrun alert (10%) |
| `ANOMALY_DUPLICATE_WINDOW_DAYS` | No | `90` | Duplicate detection window |
| `MCP_SERVER_PORT` | No | `3001` | MCP server port |
| `SENTRY_DSN` | No | — | Sentry error monitoring DSN |
| `ENVIRONMENT` | No | `development` | Runtime environment |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |

---

## License

MIT
