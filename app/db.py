import os
import asyncpg
from databases import Database
import logging

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:password@localhost:5432/career_mirror"
)

database = Database(DATABASE_URL)


async def init_db():
    """Initialize database with migrations."""
    try:
        # Connect directly with asyncpg for DDL operations
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Read and execute migration
        with open("migrations/001_init.sql", "r") as f:
            migration_sql = f.read()
        
        await conn.execute(migration_sql)
        await conn.close()
        
        logger.info("Database migrations completed successfully")
        
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        raise


async def get_database():
    """Dependency to get database connection."""
    return database