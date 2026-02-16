import os
import tempfile
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
# Import all models so they register with Base.metadata for create_all
import app.models  # noqa: F401

# Use SQLite for tests (no Postgres dependency needed for unit tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    # Clean up test db file
    if os.path.exists("./test.db"):
        os.remove("./test.db")


@pytest.fixture
async def db_session(test_engine):
    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session, tmp_path):
    from app.database import get_db
    from app.main import app
    from app.config import settings

    # Override upload dir to temp
    original_upload_dir = settings.upload_dir
    settings.upload_dir = str(tmp_path)

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    settings.upload_dir = original_upload_dir


@pytest.fixture
def sample_pdf(tmp_path) -> str:
    """Create a minimal test PDF-like file."""
    pdf_path = tmp_path / "test_invoice.pdf"
    pdf_path.write_text("%PDF-1.4 fake test content\nInvoice #12345\nTotal: $1,500.00")
    return str(pdf_path)


@pytest.fixture
def sample_csv(tmp_path) -> str:
    """Create a test CSV file."""
    csv_path = tmp_path / "test_data.csv"
    csv_path.write_text("invoice_number,vendor,total\nINV-001,Acme Freight,1500.00\n")
    return str(csv_path)
