import pytest
from unittest.mock import AsyncMock, patch
from app.profiles.repositories import ProfileRepository

pytestmark = pytest.mark.asyncio

class TestProfilesAPI:
    """Test profiles API endpoints."""
    
    async def test_create_profile_success(self, async_client, mock_profile_data):
        """Test successful profile creation."""
        with patch('app.profiles.repositories.ProfileRepository.create_profile', new_callable=AsyncMock) as mock_create, \
             patch('app.services.redis.FastAPICache.clear', new_callable=AsyncMock) as mock_cache:
            
            mock_create.return_value = mock_profile_data
            
            profile_data = {
                "cv_text": "Python developer with 5 years of experience in Django, PostgreSQL, and AWS cloud services.",
                "linkedin_url": "https://linkedin.com/in/johndoe"
            }
            
            response = await async_client.post("/profiles/", json=profile_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == mock_profile_data["id"]
            assert data["cv_text"] == mock_profile_data["cv_text"]
            assert isinstance(data["skills"], list)
            
            mock_create.assert_called_once()
            mock_cache.assert_called_once()
    
    async def test_create_profile_with_cv_text(self, async_client, mock_profile_data):
        """Test profile creation with CV text."""
        with patch('app.profiles.repositories.ProfileRepository.create_profile', new_callable=AsyncMock) as mock_create, \
             patch('app.services.redis.FastAPICache.clear', new_callable=AsyncMock) as mock_cache:
            
            mock_create.return_value = mock_profile_data
            
            profile_data = {
                "cv_text": "This is a valid CV text that is definitely long enough to pass validation. It contains more than 50 characters.",
                "linkedin_url": None
            }
            
            response = await async_client.post("/profiles/", json=profile_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == mock_profile_data["id"]
            assert data["cv_text"] == mock_profile_data["cv_text"]
            assert isinstance(data["skills"], list)
            assert len(data["skills"]) > 0
            mock_create.assert_called_once()
            mock_cache.assert_called_once()

    async def test_create_profile_with_linkedin_url(self, async_client, mock_profile_data):
        """Test profile creation with LinkedIn URL."""
        with patch('app.services.linkedinscraper.extract_linkedin_profile', new_callable=AsyncMock) as mock_linkedin:
            mock_linkedin.side_effect = NotImplementedError("LinkedIn scraping not supported")
            
            profile_data = {
                "cv_text": None,
                "linkedin_url": "https://linkedin.com/in/johndoe"
            }
            
            response = await async_client.post("/profiles/", json=profile_data)
            assert response.status_code == 422

    @pytest.mark.parametrize("test_input,expected_status", [
        ({}, 400),  # Empty payload
        ({"cv_text": "Short CV"}, 422),  # Short CV text
        ({"linkedin_url": "https://invalid-url.com"}, 422),  # Invalid LinkedIn URL
        ({"cv_text": None, "linkedin_url": None}, 422),  # Neither CV nor LinkedIn
        ({"cv_text": "x" * 49}, 422),  # CV text too short
        ({"linkedin_url": "not-a-url"}, 422),  # Invalid URL format
        ({"linkedin_url": "https://notlinkedin.com"}, 422),  # Wrong domain
    ])
    async def test_create_profile_validation_error(self, async_client, test_input, expected_status):
        """Test profile creation validation errors."""
        response = await async_client.post("/profiles/", json=test_input)
        assert response.status_code == expected_status
    
    async def test_list_profiles_success(self, async_client, mock_profile_data):
        """Test successful profile listing."""
        with patch('app.profiles.repositories.ProfileRepository.list_profiles', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = [mock_profile_data] * 10
            
            response = await async_client.get("/profiles/")
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 10
            mock_list.assert_called_once()

    async def test_get_profile_by_id_success(self, async_client, mock_profile_data):
        """Test successful profile retrieval."""
        with patch('app.profiles.repositories.ProfileRepository.get_profile_by_id', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_profile_data
            
            response = await async_client.get(f"/profiles/{mock_profile_data['id']}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == mock_profile_data["id"]
            mock_get.assert_called_once_with(mock_profile_data["id"])

    async def test_get_profile_not_found(self, async_client):
        """Test profile not found scenario."""
        with patch('app.profiles.repositories.ProfileRepository.get_profile_by_id', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            
            response = await async_client.get("/profiles/999")
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
            mock_get.assert_called_once_with(999)

    async def test_cache_invalidation(self, async_client, mock_profile_data):
        """Test cache invalidation after profile creation."""
        with patch('app.profiles.repositories.ProfileRepository.create_profile', new_callable=AsyncMock) as mock_create, \
             patch('app.services.redis.FastAPICache.clear', new_callable=AsyncMock) as mock_cache:
            
            mock_create.return_value = mock_profile_data
            
            response = await async_client.post("/profiles/", json={
                "cv_text": "This is a valid CV text that is definitely long enough to pass validation. It contains more than 50 characters."
            })
            
            assert response.status_code == 200
            mock_cache.assert_called_once()

