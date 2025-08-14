from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import sys
import os

from app.db import database, init_db
from app.services.redis import init_cache
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
    logger.info("Starting Career Mirror API")
    try:
        await database.connect()
        await init_db()
        await init_cache()
        logger.info("Database initialized successfully")
        yield
    finally:
        logger.info("Shutting down Career Mirror API")
        await database.disconnect()

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
app.include_router(main_router)
app.include_router(health_router, prefix="/healthz", tags=["Health"])
app.include_router(profiles_router, prefix="/profiles", tags=["Profiles"])
app.include_router(jobs_router, prefix="/jobs", tags=["Jobs"])
app.include_router(matches_router, prefix="/matches", tags=["Matches"])
