# Project Gamma: Claude for Logistics Operations Intelligence

On-prem-ready Claude deployment that automates logistics accounting and document workflows.

## Quick Reference

```bash
# Run everything
docker compose up -d

# Run backend tests (inside container or locally)
cd backend && python -m pytest tests/ -v

# Run alembic migrations
docker exec gamma-backend alembic upgrade head

# Test extraction endpoint
curl -X POST http://localhost:8000/api/v1/documents -F "file=@test.csv"
curl -X POST http://localhost:8000/api/v1/extractions/{document_id}

# Run eval suite
curl -X POST http://localhost:8000/api/v1/eval/run

# Seed cost allocation rules
curl -X POST http://localhost:8000/api/v1/allocations/rules/seed

# Seed RAG demo data (sample SOPs)
curl -X POST http://localhost:8000/api/v1/rag/ingest/seed

# Run cost allocation on a document
curl -X POST http://localhost:8000/api/v1/allocations/{document_id}

# Ask a question via RAG
curl -X POST http://localhost:8000/api/v1/rag/query -H "Content-Type: application/json" -d '{"question": "What GL account is used for ocean freight?"}'
```

## Architecture

- **Backend:** FastAPI (async) + SQLAlchemy + asyncpg + Anthropic SDK + Voyage AI
- **Frontend:** Next.js 15 + Tailwind + shadcn/ui + Framer Motion
- **Database:** PostgreSQL with pgvector extension (1024-dim vectors)
- **Cache/Queue:** Redis
- **Deployment:** Docker Compose (4 services on gamma-network bridge)

## Key Patterns

- **Async everywhere:** asyncpg + SQLAlchemy async + AsyncAnthropic
- **Service layer:** business logic in `services/`, `document_extractor/`, `cost_allocator/`, `rag_engine/` — route handlers only do HTTP
- **Dependency injection:** `get_db()`, `get_claude_service()`, `get_cost_allocation_pipeline()`, `get_qa_pipeline()`, `get_rag_ingestor()` — all overridable in tests
- **SQLAlchemy enums:** Use `values_callable=lambda e: [member.value for member in e]` to send lowercase values to Postgres
- **Tests use SQLite:** No Postgres needed for unit tests (via aiosqlite). Mock pgvector queries + Voyage AI.
- **Phase 1 integration tests** need asyncpg — run in Docker or install asyncpg locally

## Project Structure (Backend)

```
backend/
  app/
    main.py              # FastAPI app, CORS, middleware, lifespan
    config.py            # pydantic-settings (all env vars)
    database.py          # Async SQLAlchemy engine + sessions
    dependencies.py      # DI factories (get_db, get_claude_service, get_*_pipeline)
    models/              # SQLAlchemy ORM models
      base.py            # DeclarativeBase + TimestampMixin
      document.py        # Document model + DocumentStatus enum
      cost_allocation.py # CostAllocation, AllocationLineItem, AllocationRule
      embedding.py       # Embedding model (pgvector)
      rag.py             # RagQuery model
    schemas/             # Pydantic request/response models
      document.py        # Upload/detail/list responses
      extraction.py      # FreightInvoice, BOL, DocumentType, ExtractionResponse
      cost_allocation.py # Allocation responses, override/approval requests
      rag.py             # RagQueryRequest/Response, SourceChunk, RagStats
      health.py          # Health check response
    api/v1/              # Route handlers
      health.py          # GET /api/v1/health
      documents.py       # CRUD for document uploads
      extractions.py     # POST/GET extraction pipeline
      eval.py            # POST eval/run, GET eval/results
      allocations.py     # POST/GET allocations, PUT overrides, POST approve
      rag.py             # POST query, POST ingest, GET stats
    services/            # Business logic
      claude_service.py  # Claude API wrapper (extract, review, vision)
      document_service.py# File save + text reading
    document_extractor/  # Phase 2: extraction pipeline
      parser.py          # DocumentParser (PDF/image/CSV → ParsedDocument)
      classifier.py      # Haiku-based document type classification
      pipeline.py        # 2-pass extraction pipeline orchestrator
    cost_allocator/      # Phase 3: cost allocation pipeline
      rules.py           # Business rules manager + 10 demo rules
      pipeline.py        # CostAllocationPipeline (Claude-powered allocation)
    rag_engine/          # Phase 3: RAG Q&A engine
      embeddings.py      # Voyage AI embedding service
      chunker.py         # Text chunking + extraction_to_text conversion
      retriever.py       # pgvector cosine similarity search
      qa.py              # QAPipeline (retrieve → Claude answers with citations)
      ingest.py          # RAGIngestor (extractions + sample SOPs)
    eval/                # Extraction accuracy evaluation
      metrics.py         # Field-level accuracy (precision/recall/F1)
      extraction_eval.py # Eval harness (runs pipeline against ground truth)
      ground_truth/      # Sample documents + expected JSON outputs
    middleware/logging.py# Request logging
    # Placeholder modules for Phase 4+:
    anomaly_flagger/ audit_generator/ reconciliation_engine/
    hitl_workflow/ mcp_server/
  tests/
    test_cost_allocation.py  # Cost allocation pipeline + rules tests
    test_rag.py              # Chunker, extraction_to_text, QA pipeline tests
  alembic/versions/      # 001_initial + 002_doc_intelligence + 003_cost_allocation_rag
```

## Current Phase: 3 Complete — Next: Phase 4 (Guardrails & Production Hardening)

### Phase 1 (Complete): Foundation
- Project scaffold, Docker Compose, FastAPI skeleton
- PostgreSQL + pgvector, basic Claude extraction, document upload
- Next.js frontend skeleton, test suites

### Phase 2 (Complete): Document Intelligence
- Multi-format parsing (PDF via pdfplumber, images via Pillow, CSV)
- Document classification via Haiku (fast/cheap pre-screening)
- 2-pass extraction pipeline (extract → self-review)
- Bill of Lading + Freight Invoice schemas
- Extraction accuracy eval suite with ground truth
- Claude vision for scanned documents

### Phase 3 (Complete): Cost Allocation & RAG
- Cost allocation pipeline: Claude maps invoice line items → project codes, cost centers, GL accounts
- 10 demo business rules (ocean freight, customs, drayage, warehousing, etc.)
- Confidence thresholds: ≥85% auto-approved, <85% flagged for human review
- Inline override + approve/reject workflow
- RAG engine: Voyage AI embeddings (voyage-3, 1024-dim) → pgvector cosine similarity
- Q&A pipeline: retrieve relevant chunks → Claude answers with [Source N] citations
- Sample SOP ingestion (invoice processing, cost center guidelines, GL account mapping)
- Chat-style Q&A frontend with source citations and example question chips
- Allocations list/detail pages with confidence bars and inline editing

### Phase 4 (Future): Guardrails & Production Hardening

## API Endpoints

### Documents & Extraction
- `POST /api/v1/documents` — Upload document (multipart)
- `GET /api/v1/documents` — List documents (paginated)
- `GET /api/v1/documents/{id}` — Get document details
- `POST /api/v1/extractions/{document_id}` — Trigger extraction
- `GET /api/v1/extractions/{document_id}` — Get extraction results

### Cost Allocation
- `POST /api/v1/allocations/{document_id}` — Run allocation
- `GET /api/v1/allocations/{document_id}` — Get allocation results
- `PUT /api/v1/allocations/line-items/{id}` — Override line item
- `POST /api/v1/allocations/{id}/approve` — Approve/reject allocation
- `GET /api/v1/allocations/rules/list` — List active rules
- `POST /api/v1/allocations/rules/seed` — Seed demo rules

### RAG Q&A
- `POST /api/v1/rag/query` — Ask a question
- `POST /api/v1/rag/ingest/{document_id}` — Ingest extraction
- `POST /api/v1/rag/ingest/seed` — Seed sample SOPs
- `GET /api/v1/rag/stats` — Knowledge base statistics

### Other
- `GET /api/v1/health` — Health check
- `POST /api/v1/eval/run` — Run eval suite

## Environment Variables (.env)

See `.env.example` for all required variables. Key ones:
- `ANTHROPIC_API_KEY` — required for extraction + allocation + Q&A
- `CLAUDE_MODEL` — default: claude-sonnet-4-20250514
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `VOYAGE_API_KEY` — required for RAG embeddings (Voyage AI)
- `ALLOCATION_CONFIDENCE_THRESHOLD` — default: 0.85

## Known Issues / Gotchas

- `python-magic` requires `libmagic` system library (included in Docker image, may need install locally on Windows)
- Frontend Docker volume mounts only `src/` and `public/` to avoid clobbering node_modules
- Frontend needs `CI=true` env var to prevent pnpm TTY errors in Docker
- SQLAlchemy SAEnum must use `values_callable` to send lowercase enum values to Postgres
- pgvector queries can't run in SQLite tests — mock the retriever instead
- Docker `.env` reloads require `docker compose up -d --force-recreate`, not just `restart`
- Alembic + PG enums: use raw SQL `CREATE TYPE` + `PgENUM(create_type=False)` for column refs in migrations
- SAEnum needs explicit `name=` matching the DB type name (e.g. `name="allocation_status"`)
- Raw SQL with asyncpg: use `CAST(:param AS vector)` not `:param::vector` (conflicts with named params)
- FastAPI route ordering: static routes (`/rules/seed`) must come before parameterized routes (`/{document_id}`)
- Voyage AI free tier: 3 RPM without payment method — can hit rate limits during bulk ingestion
