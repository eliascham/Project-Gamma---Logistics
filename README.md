# Project Gamma — Logistics Operations Intelligence

An on-prem-ready AI platform that automates logistics accounting and document workflows. Powered by Claude AI for document extraction, cost allocation, and operational Q&A with RAG.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Next.js](https://img.shields.io/badge/Next.js-15-black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)
![Claude](https://img.shields.io/badge/Claude-Sonnet-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## What It Does

Project Gamma turns logistics documents (freight invoices, bills of lading) into structured, actionable data — then allocates costs to the right accounts and answers operational questions about your procedures.

### Document Intelligence
- **Multi-format parsing** — PDF (via pdfplumber), images/scans (via Claude Vision), CSV
- **Auto-classification** — Claude Haiku pre-screens documents by type (fast and cheap)
- **2-pass extraction** — Claude Sonnet extracts structured data, then self-reviews for accuracy
- **Supported document types:** Freight Invoices, Bills of Lading

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

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Next.js Frontend                      │
│          Dashboard · Documents · Allocations · Chat      │
│              (React 19, Tailwind, shadcn/ui)             │
└───────────────────────────┬─────────────────────────────┘
                            │ HTTP/REST
┌───────────────────────────▼─────────────────────────────┐
│                   FastAPI Backend                         │
│                                                          │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐  │
│  │  Document     │  │  Cost          │  │  RAG Q&A     │  │
│  │  Extractor    │  │  Allocator     │  │  Engine       │  │
│  │              │  │               │  │              │  │
│  │ Parse → Class │  │ Rules → Claude │  │ Embed → Find │  │
│  │ → Extract     │  │ → Allocate     │  │ → Answer     │  │
│  │ → Review      │  │ → Score        │  │ → Cite       │  │
│  └──────┬───────┘  └───────┬───────┘  └──────┬───────┘  │
│         │                  │                  │          │
│  ┌──────▼──────────────────▼──────────────────▼───────┐  │
│  │              Claude API (Anthropic SDK)             │  │
│  │         Sonnet (extraction/allocation/Q&A)          │  │
│  │         Haiku (classification)                      │  │
│  └────────────────────────────────────────────────────┘  │
└──────────┬──────────────────────────────┬───────────────┘
           │                              │
┌──────────▼──────────┐     ┌─────────────▼────────────┐
│  PostgreSQL + pgvec │     │   Redis                  │
│  Documents, Allocs, │     │   Cache & Queue           │
│  Embeddings (1024d) │     │                          │
└─────────────────────┘     └──────────────────────────┘
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

### Other

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Health check (DB + Redis) |
| `POST` | `/api/v1/eval/run` | Run extraction accuracy eval |
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
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   ├── services/               # Claude + document services
│   │   ├── document_extractor/     # Parse → classify → extract → review
│   │   ├── cost_allocator/         # Business rules + Claude allocation
│   │   ├── rag_engine/             # Embeddings, chunking, retrieval, Q&A
│   │   └── eval/                   # Extraction accuracy evaluation
│   ├── tests/                      # pytest test suites
│   └── alembic/                    # Database migrations
├── frontend/
│   └── src/
│       ├── app/                    # Next.js pages (dashboard, docs, chat)
│       ├── components/             # React components (26+)
│       ├── hooks/                  # Custom hooks
│       ├── lib/                    # API client + utilities
│       └── types/                  # TypeScript interfaces
├── docker-compose.yml              # 5-service orchestration
├── .env.example                    # Environment variable template
└── CLAUDE.md                       # Project context for AI assistants
```

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

### Run extraction eval suite

```bash
curl -X POST http://localhost:8000/api/v1/eval/run
```

Evaluates extraction accuracy against 4 ground truth documents, computing field-level precision, recall, and F1.

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
| `ENVIRONMENT` | No | `development` | Runtime environment |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |

---

## Roadmap

- [x] **Phase 1** — Foundation (Docker, FastAPI, PostgreSQL, basic extraction, Next.js skeleton)
- [x] **Phase 2** — Document Intelligence (multi-format parsing, classification, 2-pass extraction, eval suite)
- [x] **Phase 3** — Cost Allocation & RAG (business rules, confidence scoring, Voyage AI embeddings, Q&A with citations)
- [ ] **Phase 4** — Guardrails & Production Hardening (anomaly detection, audit trails, reconciliation, HITL workflow, MCP server)

---

## License

MIT
