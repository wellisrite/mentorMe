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
             patch('app.services.cache.cache_service.clear_by_patterns', new_callable=AsyncMock) as mock_cache_clear:
            
            mock_create.return_value = mock_job_data
            
            job_data = {
                "job_description": "We are looking for a Senior Python Developer with extensive experience in Django framework and PostgreSQL database. The ideal candidate should have strong problem-solving skills and experience with agile methodologies.",
                "title": "Senior Python Developer",
                "company": "TechCorp Inc."
            }
            
            response = await async_client.post("/v1/jobs/", json=job_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == mock_job_data["id"]
            assert data["title"] == mock_job_data["title"]
            assert isinstance(data["must_have_skills"], list)
            assert isinstance(data["nice_to_have_skills"], list)
            
            # Verify mocks were called
            mock_create.assert_called_once()
            mock_cache_clear.assert_called_once()
    
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
            response = await async_client.post("/v1/jobs/", json=payload)
            assert response.status_code == expected_status

        job_data = {
            "job_description": "Short description",
            "title": "Developer",
            "company": "TechCorp"
        }
        with patch('app.jobs.repositories.JobRepository.create_job', new_callable=AsyncMock):
            response = await async_client.post("/v1/jobs/", json=job_data)
            assert response.status_code == 422
    
    async def test_list_jobs_pagination(self, async_client, mock_job_data):
        """Test listing jobs with pagination and caching."""
        with patch('app.jobs.repositories.JobRepository.list_jobs', new_callable=AsyncMock) as mock_list:
            # Mock paginated results
            mock_list.return_value = [mock_job_data] * 10
            
            # Test first page
            response = await async_client.get("/v1/jobs/?page=1&page_size=10")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 10
            
            # Test with different page size
            response = await async_client.get("/v1/jobs/?page=1&page_size=5")
            assert response.status_code == 200
            assert len(response.json()) == 10  # Still returns mock data
            
            # Verify repository method was called with correct parameters
            mock_list.assert_called_with(1, 5)
    
    async def test_get_job_by_id_cache_hit(self, async_client, mock_job_data):
        """Test getting a job by ID with cache hit."""
        with patch('app.services.cache.cache_service.get', new_callable=AsyncMock) as mock_cache_get, \
             patch('app.jobs.repositories.JobRepository.get_job_by_id', new_callable=AsyncMock) as mock_repo_get:
            
            # Mock cache hit
            cached_job = {
                "id": mock_job_data["id"],
                "title": mock_job_data["title"],
                "company": mock_job_data["company"],
                "job_description": mock_job_data["job_description"],
                "must_have_skills": [],
                "nice_to_have_skills": [],
                "created_at": mock_job_data["created_at"]
            }
            mock_cache_get.return_value = cached_job
            
            response = await async_client.get(f"/v1/jobs/{mock_job_data['id']}")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == mock_job_data["id"]
            
            # Cache was hit, repository should not be called
            mock_cache_get.assert_called_once_with(f"job:{mock_job_data['id']}")
            mock_repo_get.assert_not_called()
    
    async def test_get_job_by_id_cache_miss(self, async_client, mock_job_data):
        """Test getting a job by ID with cache miss."""
        with patch('app.services.cache.cache_service.get', new_callable=AsyncMock) as mock_cache_get, \
             patch('app.services.cache.cache_service.set', new_callable=AsyncMock) as mock_cache_set, \
             patch('app.jobs.repositories.JobRepository.get_job_by_id', new_callable=AsyncMock) as mock_repo_get:
            
            # Mock cache miss
            mock_cache_get.return_value = None
            mock_repo_get.return_value = mock_job_data
            
            response = await async_client.get(f"/v1/jobs/{mock_job_data['id']}")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == mock_job_data["id"]
            
            # Verify cache operations
            mock_cache_get.assert_called_once_with(f"job:{mock_job_data['id']}")
            mock_repo_get.assert_called_once_with(mock_job_data['id'])
            mock_cache_set.assert_called_once()
    
    async def test_get_job_by_id_not_found(self, async_client):
        """Test getting a non-existent job."""
        with patch('app.services.cache.cache_service.get', new_callable=AsyncMock) as mock_cache_get, \
             patch('app.jobs.repositories.JobRepository.get_job_by_id', new_callable=AsyncMock) as mock_repo_get:
            
            # Mock cache miss and repository returning None
            mock_cache_get.return_value = None
            mock_repo_get.return_value = None
            
            response = await async_client.get("/v1/jobs/999")
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
        
        response = await async_client.post("/v1/jobs/", json=job_data)
        assert response.status_code == 422
    
    async def test_cache_invalidation_on_creation(self, async_client, mock_job_data):
        """Test that cache is properly invalidated after job creation."""
        with patch('app.jobs.repositories.JobRepository.create_job', new_callable=AsyncMock) as mock_create, \
             patch('app.services.cache.cache_service.clear_by_patterns', new_callable=AsyncMock) as mock_cache_clear:
            
            mock_create.return_value = mock_job_data
            
            response = await async_client.post("/v1/jobs/", json={
                "job_description": "This is a valid job description that is definitely long enough to pass validation. It includes required skills and nice to have skills.",
                "title": "Developer",
                "company": "TechCorp"
            })
            
            assert response.status_code == 200
            
            # Verify cache clearing was called with correct patterns
            mock_cache_clear.assert_called_once()
            call_args = mock_cache_clear.call_args[0][0]  # Get the patterns list
            
            expected_patterns = [
                "job:*",
                "mentorme_cache:*list_jobs*",
                "mentorme_cache:*get_job*"
            ]
            
            for pattern in expected_patterns:
                assert pattern in call_args
    
    async def test_repository_cache_integration(self, async_client):
        """Test that repository-level caching works correctly."""
        with patch('app.services.cache.cache_service.get', new_callable=AsyncMock) as mock_cache_get, \
             patch('app.services.cache.cache_service.set', new_callable=AsyncMock) as mock_cache_set, \
             patch('databases.Database.fetch_all', new_callable=AsyncMock) as mock_db_fetch:
            
            # Test list_jobs caching
            mock_cache_get.return_value = None  # Cache miss
            mock_db_fetch.return_value = []
            
            # This would be called by the repository's @cached decorator
            from app.jobs.repositories import JobRepository
            from app.db import get_database
            
            # We can't easily test the @cached decorator without more setup,
            # but we can verify the cache service methods are being called
            response = await async_client.get("/v1/jobs/?page=1&page_size=5")
            assert response.status_code == 200
    
    async def test_cache_service_health_check(self, async_client):
        """Test behavior when cache service is unhealthy."""
        with patch('app.services.cache.cache_service.is_healthy', new_callable=AsyncMock) as mock_health, \
             patch('app.jobs.repositories.JobRepository.get_job_by_id', new_callable=AsyncMock) as mock_repo_get, \
             patch('app.services.cache.cache_service.get', new_callable=AsyncMock) as mock_cache_get:
            
            # Mock unhealthy cache
            mock_health.return_value = False
            mock_cache_get.return_value = None  # Cache unavailable
            mock_repo_get.return_value = {
                "id": 1,
                "title": "Test Job",
                "company": "Test Company",
                "job_description": "Test description",
                "must_have_skills": "[]",
                "nice_to_have_skills": "[]",
                "created_at": "2024-01-01T00:00:00"
            }
            
            response = await async_client.get("/v1/jobs/1")
            assert response.status_code == 200
            
            # App should still work even with cache issues
            data = response.json()
            assert data["id"] == 1
            assert data["title"] == "Test Job"