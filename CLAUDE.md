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

# Seed mock data (MCP server + reconciliation)
curl -X POST http://localhost:8000/api/v1/mcp/seed

# Run anomaly scan
curl -X POST http://localhost:8000/api/v1/anomalies/scan -H "Content-Type: application/json" -d '{}'

# Run reconciliation
curl -X POST http://localhost:8000/api/v1/reconciliation/run -H "Content-Type: application/json" -d '{"run_by": "user"}'

# Run MCP server (for Claude Desktop)
cd backend && python -m app.mcp_server

# Run RAG eval
curl -X POST "http://localhost:8000/api/v1/eval/run?eval_type=rag"

# Run 3-way PO-BOL-Invoice matching
curl -X POST http://localhost:8000/api/v1/matching/run -H "Content-Type: application/json" -d '{"po_document_id": "...", "invoice_document_id": "..."}'

# Auto-detect document relationships
curl -X POST http://localhost:8000/api/v1/relationships/detect/{document_id}

# List document relationships
curl http://localhost:8000/api/v1/relationships/?document_id={document_id}
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
- **Dependency injection:** `get_db()`, `get_claude_service()`, `get_cost_allocation_pipeline()`, `get_qa_pipeline()`, `get_rag_ingestor()`, `get_hitl_service()`, `get_anomaly_flagger()`, `get_reconciliation_engine()`, `get_audit_report_generator()` — all overridable in tests
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
      review.py          # ReviewItemResponse, ReviewItemDetailResponse (enriched), EvidenceItem, SuggestedAction, ReviewContext
      mcp.py             # MCP status, MockRecordResponse/ListResponse, ProjectBudgetResponse
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
      document_service.py # File save + text reading
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
    eval/                # Extraction + RAG accuracy evaluation
      metrics.py         # Field-level accuracy (precision/recall/F1)
      extraction_eval.py # Eval harness (runs pipeline against ground truth)
      rag_eval.py        # RAG retrieval quality eval (hit rate, MRR)
      ground_truth/      # Sample documents + expected JSON outputs
    middleware/logging.py # Structured JSON request logging with request ID
    audit_generator/     # Audit logging + report generation
      service.py         # AuditService (static, append-only log)
      report_generator.py # Claude-powered audit report summaries
    hitl_workflow/       # Human-in-the-loop review queue
      service.py         # HITLService (state machine)
      triggers.py        # ReviewTriggers (pure functions)
    # Review detail enrichment: reviews.py builds ReviewContext with evidence, guidance,
    # suggested actions, and related entity links per anomaly type (duplicate_invoice,
    # budget_overrun, misallocated_cost, missing_approval, reconciliation_mismatch)
    anomaly_flagger/     # Anomaly detection
      detectors.py       # Pure detection functions (no DB/Claude)
      service.py         # AnomalyFlagger orchestrator
    reconciliation_engine/ # Cross-system reconciliation
      matchers.py        # Pure matching functions
      service.py         # ReconciliationEngine
    matching_engine/       # Phase 5: 3-way PO-BOL-Invoice matching
      matchers.py        # Pure matching functions (numeric, party name, description, line items)
      service.py         # ThreeWayMatchingService orchestrator
    models/
      document_relationship.py # DocumentRelationship ORM model + RelationshipType enum
    schemas/
      document_relationship.py # Pydantic request/response models for relationships
    api/v1/
      relationships.py   # CRUD + auto-detect endpoints for document relationships
      matching.py        # 3-way matching run + auto-match endpoints
    mcp_server/          # MCP server for Claude Desktop
      server.py          # LogisticsMCPServer (4 tools)
      data_layer.py      # MCPDataLayer (DB queries)
      mock_data.py       # MockDataGenerator (deterministic)
      __main__.py        # Entry point: python -m app.mcp_server
  tests/
    test_cost_allocation.py  # Cost allocation pipeline + rules tests
    test_rag.py              # Chunker, extraction_to_text, QA pipeline tests
    test_audit.py            # AuditService log/query, stats tests
    test_hitl.py             # HITL state machine, triggers, auto-approve tests
    test_anomaly.py          # Pure detector functions, anomaly flagging tests
    test_reconciliation.py   # Matcher functions, reconciliation engine tests
    test_mcp.py              # MockDataGenerator determinism, data layer tests
    test_phase5_schemas.py   # All 9 new extraction schemas + shared models
    test_phase5_matching.py  # 3-way matching: numeric, party, description, line items, full match
    test_phase5_relationships.py # Document relationship model, schemas, reference maps
  alembic/versions/      # 001_initial + 002_doc_intelligence + 003_cost_allocation_rag + 004_guardrails + 005_phase5_doc_relationships
```

## Current Phase: 5 Complete

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

### Phase 4 (Complete): Guardrails & Production Hardening
- Immutable audit logging (AuditService) — every action logged with actor, entity, state diffs
- HITL review queue — state machine (pending→approved/rejected/escalated), auto-approve rules, enriched detail view with evidence/guidance/quick actions
- Anomaly detection — duplicate invoices, budget overruns, low-confidence, missing approvals
- Reconciliation engine — TMS vs ERP matching (deterministic + fuzzy), mismatch reports
- MCP server — 4 logistics tools via MCP Python SDK for Claude Desktop integration
- Mock data generator — 500 shipments, 50 SKUs, 200 POs, 5 project budgets
- RAG eval suite — 10-question benchmark with hit rate, MRR, answer accuracy
- Structured JSON logging with request ID tracing
- Sentry integration (optional, conditional on SENTRY_DSN)
- Metrics endpoint — system-wide observability
- Frontend pages: Review Queue, Anomalies, Reconciliation, Audit Log, Data Explorer, Dashboard widgets
- Premium login page — Google + Microsoft SSO buttons (UI-only mock auth), email/password form
- Auth-gated app shell — localStorage session, auto-redirect to /login, user info + logout in sidebar

### Phase 5 (Complete): Document Intelligence Expansion
- **9 new document type schemas:** Commercial Invoice, Purchase Order, Packing List, Arrival Notice, Air Waybill, Debit/Credit Note, CBP 7501, Proof of Delivery, Certificate of Origin
- **Shared `PartyInfo` sub-model** for party blocks across all new types
- **`EXTRACTION_MODEL_REGISTRY`** maps DocumentType to Pydantic model for validation
- **ClaudeService refactored** to registry pattern — `_SCHEMA_REGISTRY` dict, `_validate_extraction()` helper
- **Classifier updated** with 11 document types and discriminating signals for each
- **Document Relationship Model:** `DocumentRelationship` table + `RelationshipType` enum (fulfills, invoices, supports, adjusts, certifies, clears, confirms, notifies)
- **Auto-detection:** Extracts reference numbers (PO, BOL, AWB, invoice) and creates relationships automatically
- **Invoice variant classification:** `invoice_variant` field on FreightInvoice and CommercialInvoice; `DemurrageDetail` sub-model for D&D invoices
- **3-way PO-BOL-Invoice matching engine:** Pure matching functions (numeric with tolerance, party name fuzzy, description word-overlap, line item pairing) + `ThreeWayMatchingService` orchestrator
- **Cost allocation expanded:** Commercial invoices, CBP 7501, debit/credit notes now allocable; 4 new rules (Import Duties, MPF, HMF, Accessorial)
- **Reference number normalization:** Auto-detect strips prefixes (PO-, INV-, BOL-, AWB-), hyphens, dots, spaces, leading zeros for fuzzy matching
- **Alembic migration 005:** `document_relationships` table with indexes + unique constraint (source, target, type)
- **Cost allocation dispatch:** Explicit `doc_type` parameter (no field-sniffing)
- **Eval harness expanded:** Field lists for all 11 document types with registry pattern
- **Self-referencing relationship prevention** in create endpoint
- **Paginated relationship listing** (limit/offset with max 500)
- **169 tests total:** 78 existing (0 regressions) + 27 schema + 28 matching + 23 relationship + 91 stress tests (security, edge cases, large documents)

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

### Audit & Reviews
- `GET /api/v1/audit/events` — List audit events (paginated, filterable)
- `POST /api/v1/audit/reports` — Generate Claude-powered audit report
- `GET /api/v1/audit/stats` — Audit event statistics
- `GET /api/v1/reviews/queue` — Get review queue (paginated, filterable)
- `GET /api/v1/reviews/{id}` — Get review item details (enriched: evidence, guidance, suggested actions, related entities)
- `POST /api/v1/reviews/{id}/action` — Approve/reject/escalate
- `GET /api/v1/reviews/stats` — Review queue statistics

### Anomaly Detection
- `POST /api/v1/anomalies/scan` — Run anomaly detection
- `GET /api/v1/anomalies/list` — List anomaly flags
- `GET /api/v1/anomalies/{id}` — Get anomaly details
- `POST /api/v1/anomalies/{id}/resolve` — Resolve anomaly
- `GET /api/v1/anomalies/stats` — Anomaly statistics
- `POST /api/v1/anomalies/audit-summary` — Claude-powered anomaly audit summary

### Reconciliation
- `POST /api/v1/reconciliation/run` — Run TMS/ERP reconciliation
- `POST /api/v1/reconciliation/seed` — Seed mock logistics data
- `GET /api/v1/reconciliation/runs` — List reconciliation runs
- `GET /api/v1/reconciliation/{id}` — Get run with records
- `GET /api/v1/reconciliation/stats` — Reconciliation statistics

### Document Relationships
- `POST /api/v1/relationships/` — Create a document relationship manually
- `GET /api/v1/relationships/` — List relationships (filterable by document_id, relationship_type)
- `GET /api/v1/relationships/{id}` — Get a single relationship
- `DELETE /api/v1/relationships/{id}` — Delete a relationship
- `POST /api/v1/relationships/detect/{document_id}` — Auto-detect relationships from extraction references

### 3-Way Matching
- `POST /api/v1/matching/run` — Run 3-way PO-BOL-Invoice matching (provide at least 2 of 3 document IDs)
- `POST /api/v1/matching/auto/{document_id}` — Auto-detect related documents and run matching

### MCP Server & Data Explorer
- `GET /api/v1/mcp/status` — MCP server status + available tools
- `POST /api/v1/mcp/seed` — Seed mock data
- `GET /api/v1/mcp/stats` — Mock data statistics
- `GET /api/v1/mcp/records` — Browse mock records (filterable by source, record_type, search; paginated)
- `GET /api/v1/mcp/budgets` — List project budgets

### Other
- `GET /api/v1/health` — Health check
- `GET /api/v1/metrics` — System metrics (eval, HITL, anomalies)
- `POST /api/v1/eval/run` — Run eval suite (extraction or RAG via eval_type param)

## Environment Variables (.env)

See `.env.example` for all required variables. Key ones:
- `ANTHROPIC_API_KEY` — required for extraction + allocation + Q&A
- `CLAUDE_MODEL` — default: claude-sonnet-4-20250514
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `VOYAGE_API_KEY` — required for RAG embeddings (Voyage AI)
- `ALLOCATION_CONFIDENCE_THRESHOLD` — default: 0.85
- `HITL_AUTO_APPROVE_DOLLAR_THRESHOLD` — default: 1000 (auto-approve below this)
- `HITL_HIGH_RISK_DOLLAR_THRESHOLD` — default: 10000 (mandatory review above this)
- `ANOMALY_BUDGET_OVERRUN_THRESHOLD` — default: 0.1 (10% over budget triggers alert)
- `ANOMALY_DUPLICATE_WINDOW_DAYS` — default: 90
- `MCP_SERVER_PORT` — default: 3001
- `SENTRY_DSN` — optional, leave empty to disable Sentry

## Roadmap: Phases 5-8 (Planned)

### Phase 5: Document Intelligence Expansion (Complete)
- ~~**P0:** Commercial Invoice, Purchase Order, Packing List extraction schemas~~
- ~~**P1:** Arrival Notice, Air Waybill (AWB/HAWB), Debit/Credit Notes~~
- ~~**P2:** CBP 7501 (Customs Entry), Proof of Delivery, Certificate of Origin~~
- ~~**Document Relationship Model:** `DocumentRelationship` table linking source -> target with relationship_type, reference_field, confidence~~
- ~~**Invoice variant classification:** detention/demurrage, accessorial, consolidated, pro-forma, debit/credit~~
- ~~**3-way PO-BOL-Invoice matching engine**~~

### Phase 6: Enterprise Readiness
- **P0:** Multi-tenancy (`tenant_id` on every table + PostgreSQL Row-Level Security)
- **P0:** Real RBAC (roles/permissions, separation of duties — replace mock auth)
- **P1:** Multi-level configurable approval workflows (extend HITL state machine)
- **P1:** Per-tenant business rules engine (JSON/YAML definitions, versioned)
- **P1:** Accounting exports (QuickBooks, Xero, NetSuite — journal entries from approved allocations)
- **P1:** Email ingestion (auto-process invoices received via email)
- **P1:** SOX-compliant audit retention (WORM storage, 7-year policy)

### Phase 7: AI Differentiators
- Smart GL coding with active learning (track corrections, retrain rules)
- Automated dispute detection + Claude-drafted dispute letters
- Natural language analytics (extend RAG to query operational data)
- Rate benchmarking against market/contracted rates
- Carbon/emissions tracking per shipment
- Carrier performance scoring from reconciliation data

### Phase 8: Platform & Integrations
- EDI 210 inbound parsing, TMS connectors (MercuryGate, BluJay, OTM)
- Notification system (email/Slack/SMS), batch processing / bulk import
- Spend analytics dashboard, multi-currency support
- Agentic invoice processing, custom document type builder
- White-label branding, multi-region / Kubernetes deployment

### Competitive Positioning
- **On-prem moat:** Only serious logistics automation platform offering self-hosted deployment
- **Transparent AI:** Claude explains reasoning with evidence (not a black box)
- **Unified pipeline:** Document-to-GL in one platform (vs competitors doing only one piece)
- **Market opportunity:** CargoWise 25-35% price increases creating churn; IDP market at 33% CAGR

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
- ReviewItem.review_metadata maps to DB column "metadata" (SQLAlchemy reserved name)
- MCP server runs as separate process (own engine), not inside FastAPI
- Anomaly scan on empty DB is safe — returns empty list
- HITL auto-approve: both dollar_amount AND confidence must be provided for auto-approve logic
- Reconciliation matching is reference-number-first (deterministic), then amount/date (fuzzy)
- GET /reviews/{id} returns `ReviewItemDetailResponse` (enriched with context); POST /reviews/{id}/action returns base `ReviewItemResponse` (no context) — frontend preserves context locally after action
- Review detail suggested actions + guidance are defined in `api/v1/reviews.py` (`_SUGGESTED_ACTIONS`, `_GUIDANCE` dicts) keyed by anomaly type
- Structured JSON logs include request_id header (X-Request-ID) for traceability
- Login page is at `/login` with its own layout (no sidebar/header) — `AppShell` component conditionally renders the app shell
- Auth state managed by `AuthProvider` in `lib/auth-context.tsx` — persists to `localStorage` key `gamma-auth`
- Mock SSO: login sets user in context (no real OAuth); swap `AuthProvider` for real OAuth provider in production
- PackingListExtraction uses `packing_date` (not `date`) to avoid shadowing Python's `date` type import
- `EXTRACTION_MODEL_REGISTRY` in `schemas/extraction.py` maps DocumentType to Pydantic model class — used by `_validate_extraction()` in claude_service.py
- `_SCHEMA_REGISTRY` in `claude_service.py` maps DocumentType to JSON template string — used by `_get_schema_for_type()`
- Cost allocation now accepts 4 document types: freight_invoice, commercial_invoice, customs_entry, debit_credit_note
- 3-way matching tolerances are configurable via `MATCH_TOLERANCES` dict in `matching_engine/matchers.py`
- Document relationship auto-detection searches extraction JSON for reference numbers — uses raw SQL queries against extractions table
- Phase 5 adds 14 allocation rules total (10 original + 4 new: Import Duties, MPF, HMF, Accessorial)
