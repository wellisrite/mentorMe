import pytest
from unittest.mock import AsyncMock, patch
from app.matches.repositories import MatchRepository

pytestmark = pytest.mark.asyncio

class TestMatchAPI:
    """Test match API endpoints."""
    
    async def test_create_match_success(self, async_client, mock_profile_data, mock_job_data, mock_match_data):
        """Test successful match creation."""
        with patch('app.matches.repositories.MatchRepository.get_existing_match', new_callable=AsyncMock) as mock_existing, \
             patch('app.matches.repositories.MatchRepository.get_profile', new_callable=AsyncMock) as mock_profile, \
             patch('app.matches.repositories.MatchRepository.get_job', new_callable=AsyncMock) as mock_job, \
             patch('app.matches.repositories.MatchRepository.create_match', new_callable=AsyncMock) as mock_create:
            
            # Setup mock returns
            mock_existing.return_value = None
            mock_profile.return_value = mock_profile_data
            mock_job.return_value = mock_job_data
            mock_create.return_value = mock_match_data
            
            # Make request
            match_request = {
                "profile_id": 1,
                "job_id": 1
            }
            
            response = await async_client.post("/matches/", json=match_request)
            
            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert data["profile_id"] == mock_match_data["profile_id"]
            assert data["job_id"] == mock_match_data["job_id"]
            assert data["match_score"] == mock_match_data["match_score"]
            assert isinstance(data["reasons"], list)
            assert isinstance(data["suggestions"], list)
            
            # Verify repository calls
            mock_existing.assert_called_once_with(1, 1)
            mock_profile.assert_called_once_with(1)
            mock_job.assert_called_once_with(1)
            mock_create.assert_called_once()
    
    async def test_create_match_existing_result(self, async_client, mock_match_data):
        """Test match creation when result already exists."""
        with patch('app.matches.repositories.MatchRepository.get_existing_match', new_callable=AsyncMock) as mock_existing:
            mock_existing.return_value = mock_match_data
            
            match_request = {
                "profile_id": 1,
                "job_id": 1
            }
            
            response = await async_client.post("/matches/", json=match_request)
            
            assert response.status_code == 200
            data = response.json()
            assert data["match_score"] == mock_match_data["match_score"]
            mock_existing.assert_called_once_with(1, 1)
    
    async def test_create_match_profile_not_found(self, async_client):
        """Test match creation when profile doesn't exist."""
        with patch('app.matches.repositories.MatchRepository.get_existing_match', new_callable=AsyncMock) as mock_existing, \
             patch('app.matches.repositories.MatchRepository.get_profile', new_callable=AsyncMock) as mock_profile:
            
            mock_existing.return_value = None
            mock_profile.return_value = None
            
            match_request = {
                "profile_id": 999,
                "job_id": 1
            }
            
            response = await async_client.post("/matches/", json=match_request)
            
            assert response.status_code == 404
            assert "Profile not found" in response.json()["detail"]
    
    async def test_create_match_job_not_found(self, async_client, mock_profile_data):
        """Test match creation when job doesn't exist."""
        with patch('app.matches.repositories.MatchRepository.get_existing_match', new_callable=AsyncMock) as mock_existing, \
             patch('app.matches.repositories.MatchRepository.get_profile', new_callable=AsyncMock) as mock_profile, \
             patch('app.matches.repositories.MatchRepository.get_job', new_callable=AsyncMock) as mock_job:
            
            mock_existing.return_value = None
            mock_profile.return_value = mock_profile_data
            mock_job.return_value = None
            
            match_request = {
                "profile_id": 1,
                "job_id": 999
            }
            
            response = await async_client.post("/matches/", json=match_request)
            
            assert response.status_code == 404
            assert "Job not found" in response.json()["detail"]

    @pytest.mark.parametrize("match_request,expected_status", [
        ({}, 422),  # Empty request
        ({"profile_id": "abc"}, 422),  # Invalid profile_id type
        ({"job_id": -1}, 422),  # Invalid job_id
        ({"profile_id": 1}, 422),  # Missing job_id
        ({"job_id": 1}, 422),  # Missing profile_id
    ])
    async def test_create_match_validation(self, async_client, match_request, expected_status):
        """Test match creation input validation."""
        response = await async_client.post("/matches/", json=match_request)
        assert response.status_code == expected_status

class TestReportsAPI:
    """Test reports API endpoints."""
    
    async def test_get_profile_report_success(self, async_client):
        """Test successful profile report generation."""
        with patch('app.services.scoring.get_profile_aggregate_report', new_callable=AsyncMock) as mock_report:
            mock_report.return_value = {
                "profile_id": 1,
                "total_jobs_analyzed": 2,
                "average_match_score": 80.0,
                "top_skills": [{"skill": "python", "match_rate": 0.9}],
                "common_gaps": [{"skill": "java", "frequency": 0.5}],
                "recommendations": ["Add Java to your skillset"],
                "last_updated": "2024-01-15T10:00:00"
            }
            
            response = await async_client.get("/reports/1")
            
            assert response.status_code == 200
            data = response.json()
            assert data["profile_id"] == 1
            assert data["total_jobs_analyzed"] == 2
            assert data["average_match_score"] == 80.0
            assert len(data["recommendations"]) > 0
            mock_report.assert_called_once_with(1)