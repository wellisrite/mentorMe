from unittest.mock import patch, AsyncMock
import pytest
from datetime import datetime

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

    async def test_get_profile_report_not_found(self, async_client):
        """Test report generation for non-existent profile."""
        with patch('app.services.scoring.get_profile_aggregate_report', new_callable=AsyncMock) as mock_report:
            mock_report.side_effect = Exception("Profile not found")

            response = await async_client.get("/v1/reports/999")
            
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data

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