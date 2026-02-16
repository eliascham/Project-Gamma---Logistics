import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings
from app.middleware.logging import RequestLoggingMiddleware

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Sentry if DSN is configured
    if settings.sentry_dsn:
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                traces_sample_rate=0.1,
                environment=settings.environment,
            )
            logger.info("Sentry initialized (env=%s)", settings.environment)
        except Exception as e:
            logger.warning("Failed to initialize Sentry: %s", e)

    logger.info("Starting Project Gamma backend (env=%s)", settings.environment)
    yield
    logger.info("Shutting down Project Gamma backend")


app = FastAPI(
    title="Project Gamma - Logistics Operations Intelligence",
    description="Claude-powered logistics document extraction, cost allocation, and operational Q&A",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLoggingMiddleware)

app.include_router(api_router, prefix="/api")
