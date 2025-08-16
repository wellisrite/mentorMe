from app.services.cache import cache_service
import logging


logger = logging.getLogger(__name__)

async def clear_job_caches():
    """Clear all job-related caches."""
    try:
        patterns = [
            "job:*",                        # Individual job caches
            "mentorme_cache:*list_jobs*",   # FastAPI-Cache list jobs patterns
            "mentorme_cache:*get_job*"      # FastAPI-Cache get job patterns
        ]
        await cache_service.clear_by_patterns(patterns)
        logger.info("Cleared job-related caches")
    except Exception as e:
        logger.error(f"Error clearing job caches: {e}")