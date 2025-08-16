# app/tests/test_cache.py
import pytest
import asyncio
import logging
from unittest.mock import patch, AsyncMock
from app.conftest import patch_cache_service

# Enable debug logging to see what's happening
logging.basicConfig(level=logging.DEBUG)

class TestCacheDebugging:
    @pytest.mark.asyncio
    async def test_cache_service_directly(self, patch_cache_service):
        """Test the cache service directly to ensure it works."""
        from app.services.cache import build_cache_key
        
        # Use the mocked cache service from conftest
        cache_service = patch_cache_service
        
        cache_key = build_cache_key("test", 1)
        test_data = {"test": "data"}
        
        # Test set
        result = await cache_service.set(cache_key, test_data, 60)
        assert result == True
        
        # Test get
        result = await cache_service.get(cache_key)
        assert result == test_data

    @pytest.mark.asyncio
    async def test_get_profile_report_with_debugging(self, async_client, patch_cache_service):
        """Test with extensive debugging to see what's happening."""
        
        with patch('app.routers.cache_service', patch_cache_service), \
            patch('app.services.scoring.get_profile_aggregate_report', new_callable=AsyncMock) as mock_report:
            mock_report.return_value = {
                "profile_id": 1,
                "total_jobs_analyzed": 2,
                "average_match_score": 80.0,
                "top_skills": [{"skill": "python", "match_rate": 0.9}],
                "common_gaps": [],
                "recommendations": ["Test recommendation"],
                "last_updated": "2024-01-15T10:00:00"
            }

            # First request
            print("Making first request...")
            response1 = await async_client.get("/v1/reports/1")
            assert response1.status_code == 200
            print(f"Mock call count after first request: {mock_report.call_count}")
            
            # Second request
            print("Making second request...")
            response2 = await async_client.get("/v1/reports/1")
            assert response2.status_code == 200
            print(f"Mock call count after second request: {mock_report.call_count}")
            
            # Verify responses are identical
            assert response1.json() == response2.json()
            
            # Print actual calls for debugging
            print(f"Actual calls: {mock_report.call_args_list}")
            
            # This should pass if caching works
            if mock_report.call_count == 1:
                print("✅ Cache is working correctly!")
            else:
                print(f"❌ Cache failed - function called {mock_report.call_count} times")
                
            mock_report.assert_called_once_with(1)

    @pytest.mark.asyncio 
    async def test_cache_keys_are_unique(self, patch_cache_service):
        """Test that different cache keys work correctly."""
        cache_service = patch_cache_service
        
        # Set different values for different keys
        await cache_service.set("key1", {"data": "value1"}, 60)
        await cache_service.set("key2", {"data": "value2"}, 60)
        
        # Verify they're stored separately
        result1 = await cache_service.get("key1")
        result2 = await cache_service.get("key2")
        
        assert result1 == {"data": "value1"}
        assert result2 == {"data": "value2"}
        assert result1 != result2