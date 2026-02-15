from app.config import settings
from app.database import get_db
from app.services.claude_service import ClaudeService

# Re-export get_db for use in Depends()
get_db = get_db


def get_claude_service() -> ClaudeService:
    return ClaudeService(settings)
