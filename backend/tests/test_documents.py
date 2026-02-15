import io

import pytest


def make_upload_file(filename: str, content: bytes = b"test content") -> dict:
    """Helper to create a file upload payload."""
    return {"file": (filename, io.BytesIO(content), "application/octet-stream")}


@pytest.mark.asyncio
async def test_upload_pdf_document(client):
    content = b"%PDF-1.4 fake test content"
    response = await client.post(
        "/api/v1/documents",
        files={"file": ("invoice.pdf", io.BytesIO(content), "application/pdf")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["original_filename"] == "invoice.pdf"
    assert data["file_type"] == "pdf"
    assert data["status"] == "pending"
    assert "id" in data
    assert data["file_size"] == len(content)


@pytest.mark.asyncio
async def test_upload_csv_document(client):
    content = b"col1,col2\nval1,val2\n"
    response = await client.post(
        "/api/v1/documents",
        files={"file": ("data.csv", io.BytesIO(content), "text/csv")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["file_type"] == "csv"


@pytest.mark.asyncio
async def test_upload_png_document(client):
    content = b"\x89PNG\r\n\x1a\n fake png"
    response = await client.post(
        "/api/v1/documents",
        files={"file": ("scan.png", io.BytesIO(content), "image/png")},
    )
    assert response.status_code == 201
    assert response.json()["file_type"] == "png"


@pytest.mark.asyncio
async def test_upload_rejects_invalid_file_type(client):
    response = await client.post(
        "/api/v1/documents",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400
    assert "not allowed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_rejects_no_filename(client):
    response = await client.post(
        "/api/v1/documents",
        files={"file": ("", io.BytesIO(b"content"), "application/octet-stream")},
    )
    # Should reject empty filename or unrecognized extension
    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_list_documents_empty(client):
    response = await client.get("/api/v1/documents")
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["per_page"] == 20


@pytest.mark.asyncio
async def test_list_documents_after_upload(client):
    # Upload two documents
    for name in ["a.pdf", "b.pdf"]:
        await client.post(
            "/api/v1/documents",
            files={"file": (name, io.BytesIO(b"%PDF content"), "application/pdf")},
        )

    response = await client.get("/api/v1/documents")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2


@pytest.mark.asyncio
async def test_get_document_by_id(client):
    # Upload
    upload_resp = await client.post(
        "/api/v1/documents",
        files={"file": ("invoice.pdf", io.BytesIO(b"%PDF test"), "application/pdf")},
    )
    doc_id = upload_resp.json()["id"]

    # Fetch
    response = await client.get(f"/api/v1/documents/{doc_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == doc_id
    assert data["original_filename"] == "invoice.pdf"
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_get_nonexistent_document_returns_404(client):
    import uuid

    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/documents/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_documents_pagination(client):
    response = await client.get("/api/v1/documents?page=1&per_page=5")
    assert response.status_code == 200
    data = response.json()
    assert data["per_page"] == 5
    assert len(data["documents"]) <= 5
