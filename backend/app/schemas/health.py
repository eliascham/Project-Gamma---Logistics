from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    timestamp: datetime
    environment: str
    version: str
