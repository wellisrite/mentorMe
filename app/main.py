from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import sys
import os

from app.db import database, init_db
from .services.cache import init_cache, cleanup_cache
from app.routers import (
    main_router,
    health_router,
    profiles_router,
    jobs_router,
    matches_router
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting Career Mirror API")
    try:
        # Initialize database
        await database.connect()
        await init_db()
        logger.info("Database initialized successfully")
        
        # Initialize cache
        await init_cache()
        logger.info("Cache initialized successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise
    finally:
        logger.info("Shutting down Career Mirror API")
        
        # Cleanup resources
        await cleanup_cache()
        await database.disconnect()
        logger.info("Cleanup completed")

app = FastAPI(
    title="Career Mirror API",
    description="Intelligent CV-to-Job matching with explainable AI scoring",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGIN", "*")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(main_router, prefix="/v1")
app.include_router(health_router, prefix="/healthz", tags=["Health"])
app.include_router(profiles_router, prefix="/v1/profiles", tags=["Profiles"])
app.include_router(jobs_router, prefix="/v1/jobs", tags=["Jobs"])
app.include_router(matches_router, prefix="/v1/matches", tags=["Matches"])
