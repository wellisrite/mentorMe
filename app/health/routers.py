from fastapi import APIRouter, Depends
from datetime import datetime
import logging

from app.health.models import HealthResponse
from app.db import get_database

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=HealthResponse)
async def health_check(db=Depends(get_database)):
    """Health check endpoint with database connectivity test."""
    database_connected = False
    
    try:
        # Test database connectivity
        await db.execute("SELECT 1")
        database_connected = True
        status = "healthy"
        logger.info("Health check passed")
    except Exception as e:
        status = "unhealthy"
        logger.error(f"Health check failed: {e}")
    
    return HealthResponse(
        status=status,
        timestamp=datetime.utcnow(),
        database_connected=database_connected
    )