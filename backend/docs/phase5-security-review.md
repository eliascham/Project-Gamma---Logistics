# Phase 5: Security Review & Stress Test Report

**Reviewer:** Butcher Agent (Security & Robustness)
**Date:** 2026-02-17
**Scope:** All Phase 5 new/modified files -- schemas, extraction pipeline, document relationships, 3-way matching engine, cost allocation pipeline extensions, classifier, migration.

---

## Executive Summary

Phase 5 is **functionally solid** with good separation of concerns. The 9 new extraction schemas are well-structured, the matching engine uses pure functions correctly, and the registry pattern eliminates the scaling problem identified by the Devil's Advocate. One security vulnerability was found and fixed (empty-string party name matching bug). Several lower-severity issues are documented below.

**Tests:** 169 total (78 existing + 91 new stress tests) -- all passing.
**Bugs Fixed:** 1 (empty-string containment in `match_party_name`)

---

## 1. Security Vulnerabilities Found

### 1.1 FIXED: Empty-String Party Name Matching (Severity: MEDIUM)

**File:** `backend/app/matching_engine/matchers.py:122-132`
**Issue:** The `match_party_name` function used Python's `in` operator for containment matching. When a party name was whitespace-only (e.g., `"   "`), it would normalize to `""`, and `"" in "any_string"` returns `True` in Python. This means a whitespace-only vendor name would match ANY other party name with confidence 0.85.

**Impact:** Could cause false-positive 3-way matches if extraction produces empty/whitespace party names (possible with poorly scanned documents).

**Fix applied:** Added `if not norm_a or not norm_b: return False, 0.0` guard after normalization, before the equality and containment checks.

### 1.2 NOT FIXED: Self-Referencing Relationships Allowed (Severity: LOW)

**File:** `backend/app/api/v1/relationships.py:92-124` (create_relationship endpoint)
**Issue:** The `create_relationship` endpoint does not validate that `source_document_id != target_document_id`. A document can create a relationship pointing to itself. While not exploitable, this is logically invalid and could confuse downstream relationship traversal.

**Recommendation:** Add a check before creating the relationship:
```python
if request.source_document_id == request.target_document_id:
    raise HTTPException(status_code=400, detail="Cannot create self-referencing relationship")
```

### 1.3 NOT FIXED: No Pagination Limit on list_relationships (Severity: LOW)

**File:** `backend/app/api/v1/relationships.py:127-147`
**Issue:** The `list_relationships` endpoint returns ALL matching relationships without pagination. With a large dataset (thousands of documents with relationships), this could return enormous result sets, consuming memory and bandwidth.

**Recommendation:** Add `limit` and `offset` query parameters consistent with other list endpoints in the codebase (e.g., `GET /api/v1/documents` supports pagination).

### 1.4 NOT FIXED: Unvalidated relationship_type Query Parameter (Severity: LOW)

**File:** `backend/app/api/v1/relationships.py:143-144`
**Issue:** The `relationship_type` query parameter on `list_relationships` is passed directly to the SQLAlchemy WHERE clause as a string comparison. While SQLAlchemy's parameterized queries prevent SQL injection, an invalid relationship_type string will silently return empty results rather than returning a 400 error.

**Recommendation:** Validate against `RelationshipType` enum before querying, or document that unknown types return empty results by design.

### 1.5 OBSERVATION: No Authorization on New Endpoints

**Files:** `backend/app/api/v1/relationships.py`, `backend/app/api/v1/matching.py`
**Issue:** The new relationship and matching endpoints have no authentication or authorization checks. This is **consistent with all other endpoints** in the application (Phase 6 is planned for real RBAC). The current app uses mock auth on the frontend only.

**Status:** Not a regression; consistent with existing pattern. Will be addressed in Phase 6.

---

## 2. Input Validation Review

### 2.1 Pydantic Schema Validation -- GOOD

All 11 extraction schemas properly enforce required fields. Tested and confirmed:
- Missing required fields raise `ValidationError` (14 test cases)
- Optional fields default to `None` cleanly (10 test cases)
- Extra/unknown fields from Claude responses are silently ignored (2 test cases)
- Confidence bounds (0.0-1.0) are enforced via `ge=0.0, le=1.0` on `DocumentRelationshipCreate`
- `reference_field` (max_length=100) and `reference_value` (max_length=500) are length-validated

### 2.2 UUID Validation -- GOOD

All document ID parameters in the relationship and matching endpoints use FastAPI's `uuid.UUID` type annotation, which automatically validates UUID format and returns 422 for invalid UUIDs. No raw string IDs are passed to SQL queries.

### 2.3 SQL Injection -- NOT VULNERABLE

All raw SQL in `relationships.py` (`_find_documents_by_reference`, `_find_documents_referencing`) uses SQLAlchemy's `text()` with named parameters (`:doc_id`, `:exclude_id`). The `field_name` variable in `_find_documents_by_reference` is NOT interpolated into SQL -- it is used as a Python dict key on the extraction data after fetching. No SQL injection vector exists.

### 2.4 Prompt Injection via Extraction Fields -- LOW RISK

**File:** `backend/app/services/claude_service.py:423-431`, `backend/app/cost_allocator/pipeline.py:179-282`

Document text and extraction data are included in Claude prompts. If a malicious document contained text like `"Ignore previous instructions and return..."`, it would be processed by Claude. However:
- The extraction pipeline uses structured JSON output (`EXTRACTION_SYSTEM_PROMPT` says "Respond with valid JSON only"), which limits the attack surface
- Pydantic validation catches any non-conforming output
- The cost allocation pipeline only includes field values from already-validated extractions (not raw document text)
- This is a fundamental property of LLM-based systems and requires prompt hardening rather than code changes

### 2.5 Reference Number Normalization -- GOOD

The `_normalize_reference` function correctly handles:
- Empty strings, whitespace-only input
- All common prefixes (PO, INV, BOL, AWB, REF, etc.)
- Hyphens, dots, spaces
- Leading zeros (preserves at least "0")
- Case-insensitive comparison
- Very long references (500+ chars)

Tested with 14 dedicated test cases in the existing test suite.

---

## 3. Stress Test Results

### 3.1 Large Documents

| Test | Items | Status |
|------|-------|--------|
| Freight invoice 100 line items | 100 | PASS |
| Commercial invoice 200 line items | 200 | PASS |
| Purchase order 150 line items | 150 | PASS |
| Customs entry 50 line items | 50 | PASS |
| Packing list 100 items | 100 | PASS |
| Arrival notice 30 charges | 30 | PASS |
| Air waybill 25 other charges | 25 | PASS |
| D&D invoice 20 demurrage details | 20 | PASS |

**Note:** No upper bound is enforced on list sizes. For production, consider adding `max_items` validation to prevent extremely large extractions from consuming excessive storage.

### 3.2 Minimal Documents

All 10 document types tested with only required fields -- all pass. Optional fields correctly default to `None` or empty lists.

### 3.3 Long String Fields

- Invoice number: 500 chars -- PASS
- Party name: 1000 chars -- PASS
- Notes: 10,000 chars -- PASS
- Line item description: 5,000 chars -- PASS
- HS code: 100 chars -- PASS

**Note:** Pydantic schemas do not enforce `max_length` on most string fields. The DB column types (`String(512)`, `Text`, etc.) and the ORM model constraints would catch overflows at the database layer, but only for fields that are stored directly. Extraction data stored as JSON blobs has no per-field length limit.

### 3.4 Matching Engine Stress

- 50 vs 50 line item matching: PASS (greedy algorithm completes correctly)
- Mismatched counts (10 PO items vs 5 invoice items): PASS (correctly reports 5 unmatched)
- All identical descriptions: PASS (greedy assigns unique indices)
- Zero quantity/price items: PASS
- 30-item 3-way match: PASS
- Negative amounts: PASS
- Empty line items on both sides: PASS
- Party names as strings (not dicts): PASS

### 3.5 Numeric Edge Cases

- Very large values (1e12): PASS
- Very small values (0.001): PASS
- Negative values: PASS
- Mixed-sign values: Correctly returns mismatch
- Zero vs zero: PASS (1.0 confidence)
- Exact tolerance boundary: PASS
- Just outside tolerance: PASS (correctly rejects)

---

## 4. Functional Correctness

### 4.1 Registry Pattern -- CORRECT

Both registries (`EXTRACTION_MODEL_REGISTRY` in schemas and `_SCHEMA_REGISTRY` in claude_service) cover all 11 document types. `UNKNOWN` type correctly falls back to `FreightInvoiceExtraction` for validation.

### 4.2 Classifier Prompt -- CORRECT

The `CLASSIFICATION_PROMPT` in `classifier.py` includes descriptions for all 11 document types plus `unknown`. Each type has distinguishing keywords to help differentiate confusing pairs (e.g., freight invoice vs commercial invoice).

### 4.3 Cost Allocation Pipeline -- CORRECT

The pipeline now uses a dispatch pattern (`_FORMAT_DISPATCH` dict mapping doc_type to method name). Tested formatters for:
- Freight invoice: standard format
- Commercial invoice: includes seller/buyer, HS codes
- Customs entry: includes HTS numbers, duty amounts
- Debit/credit note: includes note type, original invoice reference
- Unknown type: falls back to freight invoice format

### 4.4 Relationship Auto-Detection -- CORRECT (with caveats)

The `_REFERENCE_FIELD_MAP` covers 7 document types with correct field mappings. The `_PRIMARY_REF_FIELDS` covers 5 types. Reference matching uses normalized comparison. Duplicate detection prevents creating the same relationship twice (via DB query check and UniqueConstraint).

**Caveat:** The auto-detection algorithm uses N+1 queries: first fetches all document IDs, then queries each one individually for extraction data. For databases with thousands of documents, this will be slow. Consider using PostgreSQL JSONB operators (`->>`  or `@>`) for single-query matching in production.

### 4.5 Migration -- CORRECT

The `005_phase5_document_relationships` migration correctly:
- Creates the `relationship_type` enum via raw SQL
- Creates the `document_relationships` table with FK references to `documents`
- Adds indexes on `source_document_id`, `target_document_id`, and `reference_value`
- Uses `PgENUM(create_type=False)` following the project's established pattern
- Has a correct `downgrade()` that drops in reverse order

**Note:** The migration does not create the `UniqueConstraint` that the ORM model declares (`uq_document_relationships_src_tgt_type`). This means the constraint exists in SQLAlchemy's metadata but is not enforced in the database until the next migration. This should be added to the migration or a new migration created.

---

## 5. Summary of Fixes Applied

| # | File | Fix | Severity |
|---|------|-----|----------|
| 1 | `backend/app/matching_engine/matchers.py:122` | Added empty-string guard after normalization in `match_party_name` | MEDIUM |

## 6. Recommendations (Not Fixed, For Follow-Up)

| # | Issue | Recommendation | Priority |
|---|-------|----------------|----------|
| 1 | Self-referencing relationships | Add `source != target` validation in `create_relationship` | P1 |
| 2 | No pagination on `list_relationships` | Add `limit`/`offset` params | P1 |
| 3 | Missing UniqueConstraint in migration | Add to `005` migration or create `006` | P1 |
| 4 | N+1 query in auto-detection | Use JSONB operators for single-query matching | P2 |
| 5 | No `max_length` on extraction string fields | Add Pydantic `max_length` for critical fields | P2 |
| 6 | Unvalidated `relationship_type` query param | Validate against enum or document behavior | P3 |

---

## 7. Test Coverage Summary

| Test File | Tests | Status |
|-----------|-------|--------|
| `test_phase5_schemas.py` | 27 | 27 PASS |
| `test_phase5_matching.py` | 28 | 28 PASS |
| `test_phase5_relationships.py` | 23 | 23 PASS |
| `test_phase5_stress.py` (NEW) | 91 | 91 PASS |
| **Total** | **169** | **169 PASS** |

Stress test categories:
- Large documents (8 tests)
- Minimal/all-null documents (10 tests)
- Schema validation rejection (14 tests)
- Numeric matching edge cases (9 tests)
- Description matching edge cases (5 tests)
- Party name matching edge cases (4 tests)
- Line item matching stress (5 tests)
- 3-way match stress (4 tests)
- Reference normalization edge cases (6 tests)
- Relationship model edge cases (5 tests)
- Registry completeness (3 tests)
- Cost allocation formatting (5 tests)
- Document type consistency (2 tests)
- Long string fields (5 tests)
- Negative/zero amounts (4 tests)
- Extra field handling (2 tests)
