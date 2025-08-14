import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.jobs.repositories import JobRepository

pytestmark = pytest.mark.asyncio

class TestJobsAPI:
    """Test jobs API endpoints."""
    
    async def test_create_job_success(self, async_client, mock_job_data):
        """Test successful job creation."""
        with patch('app.jobs.repositories.JobRepository.create_job', new_callable=AsyncMock) as mock_create, \
             patch('app.services.redis.FastAPICache.clear', new_callable=AsyncMock) as mock_cache:
            
            mock_create.return_value = mock_job_data
            
            job_data = {
                "job_description": "We are looking for a Senior Python Developer with extensive experience in Django framework and PostgreSQL database. The ideal candidate should have strong problem-solving skills and experience with agile methodologies.",
                "title": "Senior Python Developer",
                "company": "TechCorp Inc."
            }
            
            response = await async_client.post("/jobs/", json=job_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == mock_job_data["id"]
            assert data["title"] == mock_job_data["title"]
            assert isinstance(data["must_have_skills"], list)
            assert isinstance(data["nice_to_have_skills"], list)
            
            # Verify mocks were called
            mock_create.assert_called_once()
            mock_cache.assert_called_once()
    
    async def test_create_job_validation_error(self, async_client):
        """Test job creation with validation errors."""
        test_cases = [
            # Empty payload
            ({}, 422),
            # Short job description
            ({
                "job_description": "Short description",
                "title": "Developer"
            }, 422),
            # Missing required field
            ({
                "title": "Developer",
                "company": "TechCorp"
            }, 422),
        ]
        
        for payload, expected_status in test_cases:
            response = await async_client.post("/jobs/", json=payload)
            assert response.status_code == expected_status

        job_data = {
            "job_description": "Short description",
            "title": "Developer",
            "company": "TechCorp"
        }
        with patch('app.jobs.repositories.JobRepository.create_job', new_callable=AsyncMock):
            response = await async_client.post("/jobs/", json=job_data)
            assert response.status_code == 422
    
    async def test_list_jobs_pagination(self, async_client, mock_job_data):
        """Test listing jobs with pagination."""
        with patch('app.jobs.repositories.JobRepository.list_jobs', new_callable=AsyncMock) as mock_list:
            # Mock paginated results
            mock_list.return_value = [mock_job_data] * 10
            
            # Test first page
            response = await async_client.get("/jobs/?page=1&page_size=10")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 10
            
            # Test with different page size
            response = await async_client.get("/jobs/?page=1&page_size=5")
            assert response.status_code == 200
            assert len(response.json()) == 10  # Still returns mock data
            
            # Verify repository method was called with correct parameters
            mock_list.assert_called_with(1, 5)
    
    async def test_get_job_by_id(self, async_client, mock_job_data):
        """Test getting a specific job by ID."""
        with patch('app.jobs.repositories.JobRepository.get_job_by_id', new_callable=AsyncMock) as mock_get:
            # Test successful retrieval
            mock_get.return_value = mock_job_data
            response = await async_client.get(f"/jobs/{mock_job_data['id']}")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == mock_job_data["id"]
            assert data["title"] == mock_job_data["title"]
            mock_get.assert_called_once_with(mock_job_data['id'])
            
            # Test job not found
            mock_get.reset_mock()
            mock_get.return_value = None
            response = await async_client.get("/jobs/999")
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
    
    @pytest.mark.parametrize("field,invalid_value", [
        ("job_description", "x" * 99),  # Too short
        ("job_description", None),      # Missing required
        ("title", "x" * 256),          # Too long
        ("company", "x" * 256),        # Too long
    ])
    async def test_invalid_input_validation(self, async_client, field, invalid_value):
        """Test input validation for various invalid cases."""
        job_data = {
            "job_description": "Valid job description that is definitely long enough to pass validation. It includes required skills and nice to have skills.",
            "title": "Senior Developer",
            "company": "TechCorp Inc."
        }
        job_data[field] = invalid_value
        
        response = await async_client.post("/jobs/", json=job_data)
        assert response.status_code == 422
    
    async def test_cache_invalidation(self, async_client, mock_job_data):
        """Test that cache is invalidated after job creation."""
        with patch('app.jobs.repositories.JobRepository.create_job', new_callable=AsyncMock) as mock_create, \
             patch('app.services.redis.FastAPICache.clear', new_callable=AsyncMock) as mock_cache:
            
            mock_create.return_value = mock_job_data
            
            response = await async_client.post("/jobs/", json={
                "job_description": "This is a valid job description that is definitely long enough to pass validation. It includes required skills and nice to have skills.",
                "title": "Developer",
                "company": "TechCorp"
            })
            
            assert response.status_code == 200
            mock_cache.assert_called_once()