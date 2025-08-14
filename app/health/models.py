from pydantic import BaseModel
from datetime import datetime

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    database_connected: bool
    version: str = "1.0.0"