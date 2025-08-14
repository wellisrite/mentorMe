import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.asyncio

class TestHealthEndpoint:
    """Test health check functionality."""
    
    async def test_health_check_success(self, async_client):
        """Test successful health check."""
        with patch('app.db.database.execute', new_callable=AsyncMock) as mock_db:
            mock_db.return_value = None
            response = await async_client.get("/healthz/")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["database_connected"] is True
            assert "timestamp" in data
    
    async def test_health_check_db_failure(self, async_client):
        """Test health check with database failure."""
        with patch('app.db.database.execute', new_callable=AsyncMock) as mock_db:
            mock_db.side_effect = Exception("Database connection failed")
            response = await async_client.get("/healthz/")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["database_connected"] is False