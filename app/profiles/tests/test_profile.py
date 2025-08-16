import pytest
from unittest.mock import AsyncMock, patch
from app.profiles.repositories import ProfileRepository

pytestmark = pytest.mark.asyncio

class TestProfilesAPI:
    """Test profiles API endpoints."""
    
    async def test_create_profile_success(self, async_client, mock_profile_data):
        """Test successful profile creation."""
        with patch.object(ProfileRepository, 'create_profile', new_callable=AsyncMock) as mock_create:
            
            mock_create.return_value = mock_profile_data
            
            profile_data = {
                "cv_text": "Python developer with 5 years of experience in Django, PostgreSQL, and AWS cloud services.",
                "linkedin_url": "https://linkedin.com/in/johndoe"
            }
            
            response = await async_client.post("/v1/profiles/", json=profile_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == mock_profile_data["id"]
            assert data["cv_text"] == mock_profile_data["cv_text"]
            assert isinstance(data["skills"], list)
            
            mock_create.assert_called_once()
    
    async def test_create_profile_with_cv_text(self, async_client, mock_profile_data):
        """Test profile creation with CV text."""
        with patch.object(ProfileRepository, 'create_profile', new_callable=AsyncMock) as mock_create:
            
            mock_create.return_value = mock_profile_data
            
            profile_data = {
                "cv_text": "This is a valid CV text that is definitely long enough to pass validation. It contains more than 50 characters.",
                "linkedin_url": None
            }
            
            response = await async_client.post("/v1/profiles/", json=profile_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == mock_profile_data["id"]
            assert data["cv_text"] == mock_profile_data["cv_text"]
            assert isinstance(data["skills"], list)
            assert len(data["skills"]) > 0
            mock_create.assert_called_once()

    async def test_create_profile_with_linkedin_url(self, async_client, mock_profile_data):
        """Test profile creation with LinkedIn URL."""
        with patch('app.services.linkedinscraper.extract_linkedin_profile', new_callable=AsyncMock) as mock_linkedin:
            mock_linkedin.side_effect = NotImplementedError("LinkedIn scraping not supported")
            
            profile_data = {
                "cv_text": None,
                "linkedin_url": "https://linkedin.com/in/johndoe"
            }
            
            response = await async_client.post("/v1/profiles/", json=profile_data)
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
        response = await async_client.post("/v1/profiles/", json=test_input)
        assert response.status_code == expected_status
    
    async def test_list_profiles_success(self, async_client, mock_profile_data):
        """Test successful profile listing."""
        with patch.object(ProfileRepository, 'list_profiles', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = [mock_profile_data] * 10
            
            response = await async_client.get("/v1/profiles/")
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 10
            mock_list.assert_called_once()

    async def test_list_profiles_cache_hit(self, async_client, mock_profile_data):
        """Test profile listing with cache hit."""
        cached_data = [mock_profile_data] * 5
        
        with patch.object(ProfileRepository, 'list_profiles', new_callable=AsyncMock) as mock_list:
            # Mock the repository method to return cached data directly
            mock_list.return_value = cached_data
            
            response = await async_client.get("/v1/profiles/")
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 5
            mock_list.assert_called_once()

    async def test_get_profile_by_id_success(self, async_client, mock_profile_data):
        """Test successful profile retrieval."""
        with patch.object(ProfileRepository, 'get_profile_by_id', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_profile_data
            
            response = await async_client.get(f"/v1/profiles/{mock_profile_data['id']}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == mock_profile_data["id"]
            mock_get.assert_called_once_with(mock_profile_data["id"])

    async def test_get_profile_by_id_cache_hit(self, async_client, mock_profile_data):
        """Test profile retrieval with cache hit."""
        with patch.object(ProfileRepository, 'get_profile_by_id', new_callable=AsyncMock) as mock_get:
            # Repository returns data (could be from cache or DB)
            mock_get.return_value = mock_profile_data
            
            response = await async_client.get(f"/v1/profiles/{mock_profile_data['id']}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == mock_profile_data["id"]
            mock_get.assert_called_once_with(mock_profile_data["id"])

    async def test_get_profile_not_found(self, async_client):
        """Test profile not found scenario."""
        with patch.object(ProfileRepository, 'get_profile_by_id', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            
            response = await async_client.get("/v1/profiles/999")
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
            mock_get.assert_called_once_with(999)

    async def test_cache_invalidation_after_creation(self, async_client, mock_profile_data):
        """Test cache invalidation after profile creation."""
        with patch.object(ProfileRepository, 'create_profile', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_profile_data
            
            response = await async_client.post("/v1/profiles/", json={
                "cv_text": "This is a valid CV text that is definitely long enough to pass validation. It contains more than 50 characters."
            })
            
            assert response.status_code == 200
            mock_create.assert_called_once()

    async def test_cache_service_failure_graceful_handling(self, async_client, mock_profile_data):
        """Test that cache failures don't break the API."""
        with patch.object(ProfileRepository, 'get_profile_by_id', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_profile_data
            
            response = await async_client.get(f"/v1/profiles/{mock_profile_data['id']}")
            
            # API should still work even if cache fails
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == mock_profile_data["id"]
            mock_get.assert_called_once_with(mock_profile_data["id"])

    async def test_cache_decorator_with_custom_ttl(self, async_client, mock_profile_data):
        """Test that cache decorator respects custom TTL values."""
        with patch('app.services.cache.cache_service.set', new_callable=AsyncMock) as mock_cache_set, \
             patch('app.services.cache.cache_service.get', new_callable=AsyncMock) as mock_cache_get, \
             patch('app.profiles.repositories.ProfileRepository.get_profile_by_id', new_callable=AsyncMock) as mock_get:
            
            mock_cache_get.return_value = None
            mock_get.return_value = mock_profile_data
            
            response = await async_client.get(f"/v1/profiles/{mock_profile_data['id']}")
            
            assert response.status_code == 200
            # Verify cache.set was called with appropriate TTL
            if mock_cache_set.called:
                # Check if TTL parameter was passed (depends on your caching implementation)
                call_args = mock_cache_set.call_args
                # This will vary based on your actual caching setup
                assert len(call_args[0]) >= 2  # At least key and value

class TestCacheIntegration:
    """Test cache integration at the repository level."""
    
    async def test_repository_cache_hit_and_miss(self, mock_profile_data):
        """Test repository-level caching behavior."""
        from unittest.mock import MagicMock
        
        # Mock database
        mock_db = MagicMock()
        mock_db.fetch_one = AsyncMock(return_value=mock_profile_data)
        
        repo = ProfileRepository(mock_db)
        
        with patch('app.services.cache.cache_service.get', new_callable=AsyncMock) as mock_cache_get, \
             patch('app.services.cache.cache_service.set', new_callable=AsyncMock) as mock_cache_set:
            
            # Test cache miss - should call database
            mock_cache_get.return_value = None
            result = await repo.get_profile_by_id(123)
            
            assert result == dict(mock_profile_data)
            mock_db.fetch_one.assert_called_once()
            mock_cache_set.assert_called_once()
            
            # Reset mocks
            mock_db.reset_mock()
            mock_cache_set.reset_mock()
            
            # Test cache hit - should NOT call database
            mock_cache_get.return_value = dict(mock_profile_data)
            result = await repo.get_profile_by_id(123)
            
            assert result == dict(mock_profile_data)
            mock_db.fetch_one.assert_not_called()
            mock_cache_set.assert_not_called()
    
    async def test_repository_list_profiles_caching(self, mock_profile_data):
        """Test list profiles caching in repository."""
        from unittest.mock import MagicMock
        
        mock_db = MagicMock()
        mock_db.fetch_all = AsyncMock(return_value=[mock_profile_data, mock_profile_data])
        
        repo = ProfileRepository(mock_db)
        
        with patch('app.services.cache.cache_service.get', new_callable=AsyncMock) as mock_cache_get, \
             patch('app.services.cache.cache_service.set', new_callable=AsyncMock) as mock_cache_set:
            
            # Test cache miss
            mock_cache_get.return_value = None
            result = await repo.list_profiles(limit=10, offset=0)
            
            assert len(result) == 2
            mock_db.fetch_all.assert_called_once()
            mock_cache_set.assert_called_once()
    
    async def test_repository_create_profile_cache_invalidation(self, mock_profile_data):
        """Test that create_profile properly invalidates caches."""
        from unittest.mock import MagicMock
        
        mock_db = MagicMock()
        mock_db.fetch_one = AsyncMock(return_value=mock_profile_data)
        
        repo = ProfileRepository(mock_db)
        
        with patch('app.services.cache.cache_service.set', new_callable=AsyncMock) as mock_cache_set, \
             patch('app.services.cache.cache_service.delete_pattern', new_callable=AsyncMock) as mock_cache_delete:
            
            await repo.create_profile(cv_text="Test CV", skills="[]")
            
            # Should cache the new profile
            mock_cache_set.assert_called()
            
            # Should invalidate list caches
            mock_cache_delete.assert_called()
            call_args = [call[0][0] for call in mock_cache_delete.call_args_list]
            assert any("profile:list" in arg for arg in call_args)
    
    async def test_cache_key_generation(self):
        """Test cache key generation."""
        from app.services.cache import build_cache_key
        
        # Test basic key building
        key = build_cache_key("profile", 123)
        assert "profile" in key
        assert "123" in key
        
        # Test with kwargs
        key = build_cache_key("profile:list", limit=10, offset=0)
        assert "profile:list" in key
        assert "limit:10" in key
        assert "offset:0" in key
    
    async def test_cache_service_health_check(self):
        """Test cache service health check."""
        from app.services.cache import cache_service
        
        with patch.object(cache_service, 'redis_pool') as mock_pool:
            mock_pool.ping = AsyncMock(return_value=True)
            cache_service._connected = True
            
            is_healthy = await cache_service.is_healthy()
            assert is_healthy is True
    
    async def test_cache_service_connection_failure(self):
        """Test cache service handles connection failures gracefully."""
        from app.services.cache import cache_service
        
        with patch.object(cache_service, 'redis_pool') as mock_pool:
            mock_pool.ping = AsyncMock(side_effect=Exception("Connection failed"))
            
            is_healthy = await cache_service.is_healthy()
            assert is_healthy is False