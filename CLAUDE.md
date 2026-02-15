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
```

## Architecture

- **Backend:** FastAPI (async) + SQLAlchemy + asyncpg + Anthropic SDK
- **Frontend:** Next.js 15 + Tailwind + shadcn/ui
- **Database:** PostgreSQL with pgvector extension
- **Cache/Queue:** Redis
- **Deployment:** Docker Compose (4 services on gamma-network bridge)

## Key Patterns

- **Async everywhere:** asyncpg + SQLAlchemy async + AsyncAnthropic
- **Service layer:** business logic in `services/` and `document_extractor/`, route handlers only do HTTP
- **Dependency injection:** `get_db()`, `get_claude_service()` overridable in tests
- **SQLAlchemy enums:** Use `values_callable=lambda e: [member.value for member in e]` to send lowercase values to Postgres
- **Tests use SQLite:** No Postgres needed for unit tests (via aiosqlite)
- **Phase 1 integration tests** need asyncpg — run in Docker or install asyncpg locally

## Project Structure (Backend)

```
backend/
  app/
    main.py              # FastAPI app, CORS, middleware, lifespan
    config.py            # pydantic-settings (all env vars)
    database.py          # Async SQLAlchemy engine + sessions
    dependencies.py      # DI factories (get_db, get_claude_service)
    models/              # SQLAlchemy ORM models
      base.py            # DeclarativeBase + TimestampMixin
      document.py        # Document model + DocumentStatus enum
    schemas/             # Pydantic request/response models
      document.py        # Upload/detail/list responses
      extraction.py      # FreightInvoice, BOL, DocumentType, ExtractionResponse
      health.py          # Health check response
    api/v1/              # Route handlers
      health.py          # GET /api/v1/health
      documents.py       # CRUD for document uploads
      extractions.py     # POST extraction pipeline trigger
      eval.py            # POST eval/run, GET eval/results
    services/            # Business logic
      claude_service.py  # Claude API wrapper (extract, review, vision)
      document_service.py# File save + text reading
    document_extractor/  # Phase 2: extraction pipeline
      parser.py          # DocumentParser (PDF/image/CSV → ParsedDocument)
      classifier.py      # Haiku-based document type classification
      pipeline.py        # 2-pass extraction pipeline orchestrator
    eval/                # Extraction accuracy evaluation
      metrics.py         # Field-level accuracy (precision/recall/F1)
      extraction_eval.py # Eval harness (runs pipeline against ground truth)
      ground_truth/      # Sample documents + expected JSON outputs
    middleware/logging.py# Request logging
    # Placeholder modules for Phase 3+:
    cost_allocator/ rag_engine/ anomaly_flagger/ audit_generator/
    reconciliation_engine/ hitl_workflow/ mcp_server/
  tests/
  alembic/versions/      # 001_initial + 002_doc_intelligence
```

## Current Phase: 2 (Document Intelligence)

### Phase 1 (Complete): Foundation
- Project scaffold, Docker Compose, FastAPI skeleton
- PostgreSQL + pgvector, basic Claude extraction, document upload
- Next.js frontend skeleton, test suites

### Phase 2 (Current): Document Intelligence
- Multi-format parsing (PDF via pdfplumber, images via Pillow, CSV)
- Document classification via Haiku (fast/cheap pre-screening)
- 2-pass extraction pipeline (extract → self-review)
- Bill of Lading + Freight Invoice schemas
- Extraction accuracy eval suite with ground truth
- Claude vision for scanned documents

### Phase 3 (Next): Cost Allocation & RAG
### Phase 4 (Future): Guardrails & Production Hardening

## Environment Variables (.env)

See `.env.example` for all required variables. Key ones:
- `ANTHROPIC_API_KEY` — required for extraction
- `CLAUDE_MODEL` — default: claude-sonnet-4-20250514
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string

## Known Issues / Gotchas

- `python-magic` requires `libmagic` system library (included in Docker image, may need install locally on Windows)
- Frontend Docker volume mounts only `src/` and `public/` to avoid clobbering node_modules
- Frontend needs `CI=true` env var to prevent pnpm TTY errors in Docker
- SQLAlchemy SAEnum must use `values_callable` to send lowercase enum values to Postgres
