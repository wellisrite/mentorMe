import asyncio
from unittest.mock import patch, AsyncMock
import pytest
import time
from datetime import datetime
from app.conftest import patch_cache_service

class TestReportsAPI:
    """Test reports API endpoints."""

    @pytest.mark.asyncio
    async def test_get_profile_report_success(self, async_client):
        """Test successful profile report generation."""
        with patch('app.services.scoring.get_profile_aggregate_report', new_callable=AsyncMock) as mock_report:
            mock_report.return_value = {
                "profile_id": 1,
                "total_jobs_analyzed": 2,
                "average_match_score": 80.0,
                "top_skills": [{"skill": "python", "match_rate": 0.9}],
                "common_gaps": [{"skill": "java", "frequency": 0.5, "impact": "medium"}],
                "recommendations": ["Add Java to your skillset"],
                "last_updated": "2024-01-15T10:00:00"
            }

            response = await async_client.get("/v1/reports/1")

            assert response.status_code == 200
            data = response.json()
            assert data["profile_id"] == 1
            assert data["total_jobs_analyzed"] == 2
            assert data["average_match_score"] == 80.0
            assert isinstance(data["top_skills"], list)
            assert data["top_skills"][0]["skill"] == "python"
            assert "match_rate" in data["top_skills"][0]
            assert isinstance(data["common_gaps"], list)
            assert data["common_gaps"][0]["skill"] == "java"
            assert data["common_gaps"][0]["impact"] == "medium"
            assert isinstance(data["recommendations"], list)
            assert "last_updated" in data
            mock_report.assert_called_once_with(1)
            
    @pytest.mark.asyncio
    async def test_get_profile_report_cache_hit(self, async_client, patch_cache_service):
        with patch("app.routers.cache_service", patch_cache_service), \
            patch("app.services.scoring.get_profile_aggregate_report", new_callable=AsyncMock) as mock_report:

            report_data = {
                "profile_id": 1,
                "total_jobs_analyzed": 2,
                "average_match_score": 80.0,
                "top_skills": [{"skill": "python", "match_rate": 0.9}],
                "common_gaps": [],
                "recommendations": ["Test recommendation"],
                "last_updated": "2024-01-15T10:00:00"
            }
            mock_report.return_value = report_data

            # First request (cache miss)
            response1 = await async_client.get("/v1/reports/1")
            assert response1.status_code == 200
            assert response1.json() == report_data

            # Second request (cache hit)
            response2 = await async_client.get("/v1/reports/1")
            assert response2.status_code == 200
            assert response2.json() == report_data

            # Ensure scoring function called only once
            mock_report.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_get_profile_report_different_profiles_different_cache(self, async_client):
        """Test that different profiles have separate cache entries."""
        with patch("app.routers.cache_service", patch_cache_service), \
         patch("app.services.scoring.get_profile_aggregate_report", new_callable=AsyncMock) as mock_report:            # Setup different responses for different profiles
            def side_effect(profile_id):
                return {
                    "profile_id": profile_id,
                    "total_jobs_analyzed": profile_id,  # Different data per profile
                    "average_match_score": 80.0 + profile_id,
                    "top_skills": [],
                    "common_gaps": [],
                    "recommendations": [f"Recommendation for profile {profile_id}"],
                    "last_updated": "2024-01-15T10:00:00"
                }
            
            mock_report.side_effect = side_effect
            
            # Request reports for different profiles
            response1 = await async_client.get("/v1/reports/1")
            response2 = await async_client.get("/v1/reports/2")
            
            assert response1.status_code == 200
            assert response2.status_code == 200
            
            # Verify different data returned
            data1 = response1.json()
            data2 = response2.json()
            
            assert data1["profile_id"] == 1
            assert data2["profile_id"] == 2
            assert data1["average_match_score"] == 81.0
            assert data2["average_match_score"] == 82.0
            
            # Both profiles should have been called (no cross-contamination)
            assert mock_report.call_count == 2
            
    @pytest.mark.asyncio
    async def test_get_profile_report_cache_key_uniqueness(self, async_client, patch_cache_service):
        """Test cache key uniqueness for different profile IDs."""
        # Cache is already mocked globally - this test verifies cache behavior
        with patch("app.routers.cache_service", patch_cache_service), \
         patch("app.services.scoring.get_profile_aggregate_report", new_callable=AsyncMock) as mock_report:
            
            report_data = {
                "profile_id": 123,
                "total_jobs_analyzed": 1,
                "average_match_score": 75.0,
                "top_skills": [{"skill": "javascript", "match_rate": 0.8}],
                "common_gaps": [],
                "recommendations": ["Test recommendation"],
                "last_updated": "2024-01-15T10:00:00"
            }
            
            mock_report.return_value = report_data
            
            # Two requests to the same endpoint should use cache
            response1 = await async_client.get("/v1/reports/123")
            assert response1.status_code == 200
            
            response2 = await async_client.get("/v1/reports/123")
            assert response2.status_code == 200
            
            # Should only call the scoring function once
            mock_report.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_get_profile_report_not_found(self, async_client):
        """Test report generation for non-existent profile."""
        with patch('app.services.scoring.get_profile_aggregate_report', new_callable=AsyncMock) as mock_report:
            mock_report.side_effect = Exception("Profile not found")

            response = await async_client.get("/v1/reports/999")
            
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data

    @pytest.mark.asyncio
    async def test_get_profile_report_no_jobs(self, async_client):
        """Test report for profile with no job matches."""
        with patch('app.services.scoring.get_profile_aggregate_report', new_callable=AsyncMock) as mock_report:
            mock_report.return_value = {
                "profile_id": 2,
                "total_jobs_analyzed": 0,
                "average_match_score": 0.0,
                "top_skills": [],
                "common_gaps": [],
                "recommendations": ["No job matches found."],
                "last_updated": datetime.utcnow().isoformat()
            }

            response = await async_client.get("/v1/reports/2")
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_jobs_analyzed"] == 0
            assert data["average_match_score"] == 0.0
            assert data["top_skills"] == []
            assert data["common_gaps"] == []
            assert "No job matches found." in data["recommendations"]

    @pytest.mark.asyncio
    async def test_get_profile_report_cache_miss_fallback(self, async_client):
        """Test behavior when cache operations fail."""
        # Create a failing cache mock
        failing_cache = AsyncMock()
        failing_cache.get.side_effect = Exception("Cache unavailable")
        failing_cache.set.side_effect = Exception("Cache unavailable")
        
        with patch('app.routers.cache_service', failing_cache), \
             patch('app.services.scoring.get_profile_aggregate_report', new_callable=AsyncMock) as mock_report:
            
            report_data = {
                "profile_id": 1,
                "total_jobs_analyzed": 2,
                "average_match_score": 80.0,
                "top_skills": [{"skill": "python", "match_rate": 0.9}],
                "common_gaps": [],
                "recommendations": ["Test recommendation"],
                "last_updated": "2024-01-15T10:00:00"
            }
            
            mock_report.return_value = report_data
            
            # Should still work even with cache failures (graceful degradation)
            response = await async_client.get("/v1/reports/1")
            assert response.status_code == 200
            assert response.json() == report_data
            
            # Function should be called since cache failed
            mock_report.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_get_profile_report_performance_with_cache(self, async_client, patch_cache_service):
        """Test that cached responses are faster than uncached ones."""
        
        with patch("app.routers.cache_service", patch_cache_service), \
            patch("app.services.scoring.get_profile_aggregate_report", new_callable=AsyncMock) as mock_report:
            
            # Simulate slow report generation
            async def slow_report_generation(profile_id):
                await asyncio.sleep(0.1)  # 100ms delay
                return {
                    "profile_id": profile_id,
                    "total_jobs_analyzed": 5,
                    "average_match_score": 85.0,
                    "top_skills": [],
                    "common_gaps": [],
                    "recommendations": ["Performance test"],
                    "last_updated": "2024-01-15T10:00:00"
                }
            
            mock_report.side_effect = slow_report_generation
            
            # First request (cache miss) - should be slower
            start_time = time.time()
            response1 = await async_client.get("/v1/reports/1")
            first_request_time = time.time() - start_time
            
            assert response1.status_code == 200
            
            # Second request (cache hit) - should be faster
            start_time = time.time()
            response2 = await async_client.get("/v1/reports/1")
            second_request_time = time.time() - start_time
            
            assert response2.status_code == 200
            assert response1.json() == response2.json()
            
            # Second request should be significantly faster
            assert second_request_time < first_request_time * 0.5  # At least 50% faster
            
            # Function should only be called once
            mock_report.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_cache_isolation_between_tests(self, async_client, patch_cache_service):
        """Test that cache is properly isolated between tests."""
        # This test verifies that the cache doesn't leak data between tests
        
        with patch('app.routers.cache_service', patch_cache_service), \
            patch('app.services.scoring.get_profile_aggregate_report', new_callable=AsyncMock) as mock_report:
            mock_report.return_value = {
                "profile_id": 999,
                "total_jobs_analyzed": 1,
                "average_match_score": 99.0,
                "top_skills": [],
                "common_gaps": [],
                "recommendations": ["Isolation test"],
                "last_updated": "2024-01-15T10:00:00"
            }
            
            # Make request
            response = await async_client.get("/v1/reports/999")
            assert response.status_code == 200
            
            # Verify function was called (cache was empty)
            mock_report.assert_called_once_with(999)
            
            # Verify cache has the data
            cache_key = "profile_report:999"  # This should match your cache key format
            cached_data = await patch_cache_service.get(cache_key)
            assert cached_data is not None