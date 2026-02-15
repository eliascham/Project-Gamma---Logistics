import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.models.document import Document, DocumentStatus
from app.schemas.document import DocumentDetail, DocumentListResponse, DocumentUploadResponse
from app.services.document_service import get_file_extension, get_mime_type, save_upload

router = APIRouter()


@router.post("", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_ext = get_file_extension(file.filename)
    if file_ext not in settings.allowed_file_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file_ext}' not allowed. Allowed: {', '.join(sorted(settings.allowed_file_types))}",
        )

    # Check file size
    content = await file.read()
    file_size = len(content)
    if file_size > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.max_upload_size_mb}MB",
        )
    # Reset file position for save
    await file.seek(0)

    stored_filename, file_path = await save_upload(file, settings)

    document = Document(
        id=uuid.uuid4(),
        filename=stored_filename,
        original_filename=file.filename,
        file_path=file_path,
        file_type=file_ext,
        mime_type=get_mime_type(file.filename),
        file_size=file_size,
        status=DocumentStatus.PENDING,
    )

    db.add(document)
    await db.flush()

    return DocumentUploadResponse(
        id=document.id,
        filename=stored_filename,
        original_filename=document.original_filename,
        file_type=document.file_type,
        file_size=document.file_size,
        status=document.status,
        uploaded_at=document.created_at,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    offset = (page - 1) * per_page

    count_result = await db.execute(select(func.count(Document.id)))
    total = count_result.scalar_one()

    result = await db.execute(
        select(Document)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    documents = result.scalars().all()

    return DocumentListResponse(
        documents=[DocumentDetail.model_validate(doc) for doc in documents],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DocumentDetail:
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentDetail.model_validate(document)
