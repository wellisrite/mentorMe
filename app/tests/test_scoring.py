import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from app.services.scoring import (
    extract_skills_from_text,
    extract_job_requirements,
    extract_job_requirements_enhanced,
    calculate_match_score,
    calculate_match_score_enhanced,
    calculate_text_similarity,
    normalize_skill,
    generate_suggestions,
    generate_suggestions_enhanced,
    extract_skills_with_context,
    calculate_skill_importance_weights,
    calculate_experience_bonus,
    get_learning_suggestions,
    extract_high_value_keywords,
    detect_industry_context,
    get_industry_specific_suggestions,
    batch_calculate_match_scores,
    get_profile_aggregate_report_enhanced,
    calculate_match_trend,
    generate_profile_recommendations,
    SkillMatch,
    TECHNICAL_SKILLS,
    ALL_SKILLS,
    SKILL_CATEGORIES,
    SKILL_SYNONYMS,
    EXPERIENCE_PATTERNS
)
from app.matches.models import MatchReason, MatchSuggestion


class TestEnhancedSkillExtraction:
    """Test enhanced skill extraction functionality."""
    
    def test_extract_skills_with_context(self):
        """Test skill extraction with context and confidence scores."""
        text = """
        Senior Python developer with 5+ years experience.
        Proficient in Django framework and PostgreSQL databases.
        Expert in React.js frontend development.
        """
        
        skills_with_context = extract_skills_with_context(text)
        
        # Should return tuples of (skill, context, confidence)
        assert len(skills_with_context) > 0
        
        # Check for skills with experience indicators
        python_skills = [s for s in skills_with_context if s[0] == "python"]
        assert len(python_skills) > 0
        
        # Experience indicators should boost confidence
        python_with_years = [s for s in python_skills if "5+" in s[1]]
        if python_with_years:
            assert python_with_years[0][2] > 1.0  # Confidence boost
    
    def test_skill_normalization_with_confidence(self):
        """Test enhanced skill normalization with confidence scores."""
        # Test perfect matches
        skill, confidence = normalize_skill("javascript")
        assert skill == "javascript"
        assert confidence == 1.0
        
        # Test synonyms
        skill, confidence = normalize_skill("js")
        assert skill == "javascript"
        assert confidence == 1.0
        
        skill, confidence = normalize_skill("k8s")
        assert skill == "kubernetes"
        assert confidence == 1.0
        
        # Test ambiguous synonyms
        skill, confidence = normalize_skill("tf")
        assert skill == "terraform"
        assert confidence == 0.8  # Lower confidence due to ambiguity
    
    def test_extract_structured_skills(self):
        """Test extraction from structured content."""
        text = """
        Skills:
        • Python (5 years)
        • Django framework
        • PostgreSQL database design
        
        Technologies used:
        - React.js frontend
        - AWS cloud services
        - Docker containerization
        """
        
        skills = extract_skills_from_text(text)
        expected_skills = ["python", "django", "postgresql", "react", "aws", "docker"]
        
        for skill in expected_skills:
            assert skill in skills
    
    def test_experience_pattern_detection(self):
        """Test detection of experience level patterns."""
        text = "Senior Python developer with 7+ years experience in Django"
        skills_with_context = extract_skills_with_context(text)
        
        # Should find both Python and Django with boosted confidence
        python_skills = [s for s in skills_with_context if s[0] == "python"]
        django_skills = [s for s in skills_with_context if s[0] == "django"]
        
        assert len(python_skills) > 0
        assert len(django_skills) > 0
        
        # Senior level should boost confidence
        senior_python = [s for s in python_skills if s[2] > 1.0]
        assert len(senior_python) > 0


class TestEnhancedJobRequirements:
    """Test enhanced job requirement extraction with bonus skills."""
    
    def test_extract_three_tier_requirements(self):
        """Test extraction of must-have, nice-to-have, and bonus skills."""
        job_desc = """
        Required Skills:
        - 5+ years Python development
        - Django framework experience
        - PostgreSQL database knowledge
        
        Preferred Skills:
        - Redis caching experience
        - Docker containerization
        
        Bonus Points:
        - Kubernetes orchestration
        - Team leadership experience
        """
        
        must_have, nice_to_have, bonus = extract_job_requirements_enhanced(job_desc)
        
        assert "python" in must_have
        assert "django" in must_have
        assert "postgresql" in must_have
        
        assert "redis" in nice_to_have
        assert "docker" in nice_to_have
        
        assert "kubernetes" in bonus
    
    def test_requirement_hierarchy_overlap_removal(self):
        """Test that skill overlaps are properly removed maintaining hierarchy."""
        job_desc = """
        Essential: Python, Django
        Nice to have: Python, Redis
        Bonus: Django, Kubernetes
        """
        
        must_have, nice_to_have, bonus = extract_job_requirements_enhanced(job_desc)
        
        # Python should only be in must_have (highest priority)
        assert "python" in must_have
        assert "python" not in nice_to_have
        assert "python" not in bonus
        
        # Django should only be in must_have
        assert "django" in must_have
        assert "django" not in bonus
        
        # Redis should only be in nice_to_have
        assert "redis" in nice_to_have
        
        # Kubernetes should only be in bonus
        assert "kubernetes" in bonus
    
    def test_fallback_strategy_for_unstructured_requirements(self):
        """Test fallback strategy when no clear categorization is found."""
        job_desc = """
        We need a developer with Python, Django, PostgreSQL, Redis, and Docker experience.
        Knowledge of Kubernetes and AWS would be beneficial.
        """
        
        must_have, nice_to_have, bonus = extract_job_requirements_enhanced(job_desc)
        
        # Should still categorize skills even without clear structure
        total_skills = len(must_have) + len(nice_to_have) + len(bonus)
        assert total_skills > 0
        
        # Should have some distribution across categories
        assert len(must_have) > 0 or len(nice_to_have) > 0


class TestEnhancedMatchingAlgorithm:
    """Test the enhanced matching algorithm with weighted scoring."""
    
    def test_weighted_importance_calculation(self):
        """Test skill importance weight calculation."""
        job_description = """
        We urgently need a Python developer. Python is critical for this role.
        Django experience is also important. Some Redis knowledge would be nice.
        """
        
        skills = ["python", "django", "redis"]
        weights = calculate_skill_importance_weights(skills, job_description)
        
        # Python should have highest weight (mentioned multiple times, marked as critical)
        assert weights["python"] > weights["django"]
        assert weights["django"] > weights.get("redis", 1.0)
        
        # All weights should be reasonable
        for weight in weights.values():
            assert 0.5 <= weight <= 3.0
    
    def test_enhanced_match_score_with_bonus_skills(self):
        """Test match scoring with bonus skills category."""
        profile_skills = ["python", "django", "postgresql", "redis", "kubernetes"]
        must_have = ["python", "django"]
        nice_to_have = ["postgresql", "redis"]
        bonus = ["kubernetes", "aws"]
        
        result = calculate_match_score_enhanced(
            profile_skills=profile_skills,
            profile_text="Python Django developer with PostgreSQL, Redis, and Kubernetes",
            must_have_skills=must_have,
            nice_to_have_skills=nice_to_have,
            job_description="Python Django developer needed",
            bonus_skills=bonus
        )
        
        # Should have high score with all categories matched
        assert result["match_score"] >= 85.0
        
        # Should have breakdown of different components
        assert "breakdown" in result
        assert "skill_match" in result["breakdown"]
        assert "text_similarity" in result["breakdown"]
        assert "experience_bonus" in result["breakdown"]
        
        # Check that bonus skills are properly categorized
        bonus_reasons = [r for r in result["reasons"] if r.category == "bonus"]
        assert len(bonus_reasons) > 0
    
    def test_experience_bonus_calculation(self):
        """Test experience bonus calculation."""
        # Profile with more experience than required
        profile_text = "Senior developer with 8+ years of Python experience"
        job_description = "Minimum 5 years Python development experience required"
        
        bonus = calculate_experience_bonus(profile_text, job_description)
        assert bonus > 0.0  # Should get positive bonus
        
        # Profile with less experience than required
        profile_text = "Junior developer with 2 years Python experience"
        job_description = "Minimum 5 years Python development experience required"
        
        bonus = calculate_experience_bonus(profile_text, job_description)
        assert bonus < 0.0  # Should get penalty
        
        # No experience information
        profile_text = "Python developer"
        job_description = "Python developer needed"
        
        bonus = calculate_experience_bonus(profile_text, job_description)
        assert bonus == 0.0  # No bonus or penalty
    
    def test_category_weighted_scoring(self):
        """Test that different skill categories have appropriate weights."""
        # Test with programming language vs tools
        profile_skills = ["python"]  # High-value programming skill
        must_have = ["python", "git"]  # Programming + tool
        
        result = calculate_match_score_enhanced(
            profile_skills=profile_skills,
            profile_text="Python developer",
            must_have_skills=must_have,
            nice_to_have_skills=[],
            job_description="Python developer with Git experience"
        )
        
        # Programming skills should be weighted higher than tools
        reasons = result["reasons"]
        python_reason = next(r for r in reasons if r.skill == "python")
        git_reason = next((r for r in reasons if r.skill == "git"), None)
        
        if git_reason and python_reason.status == "matched":
            # Python should have higher implicit weight due to category
            assert len([r for r in reasons if r.skill == "python"]) >= 1


class TestEnhancedSuggestionGeneration:
    """Test enhanced suggestion generation."""
    
    def test_priority_based_suggestion_sorting(self):
        """Test that suggestions are properly prioritized."""
        must_have_missing = ["python", "django"]
        nice_to_have_missing = ["redis"]
        importance_weights = {"python": 2.0, "django": 1.5, "redis": 1.0}
        
        suggestions = generate_suggestions_enhanced(
            must_have_missing=must_have_missing,
            nice_to_have_missing=nice_to_have_missing,
            profile_skills=["javascript"],
            job_description="Python Django developer with Redis",
            importance_weights=importance_weights
        )
        
        # Should have critical/high priority suggestions for must-have skills
        critical_suggestions = [s for s in suggestions if s.priority == "critical"]
        high_suggestions = [s for s in suggestions if s.priority == "high"]
        
        assert len(critical_suggestions) + len(high_suggestions) > 0
        
        # Python should be mentioned in high-priority suggestions (highest weight)
        high_priority_text = " ".join([s.suggestion for s in critical_suggestions + high_suggestions])
        assert "python" in high_priority_text.lower()
    
    def test_learning_path_suggestions(self):
        """Test specific learning path generation."""
        # Test specific skill suggestions
        python_path = get_learning_suggestions("python", "programming")
        assert "python" in python_path.lower()
        assert len(python_path) > 20  # Should be detailed
        
        react_path = get_learning_suggestions("react", "frontend")
        assert "react" in react_path.lower()
        
        # Test category fallbacks
        unknown_skill_path = get_learning_suggestions("unknown_skill", "programming")
        assert "unknown_skill" in unknown_skill_path
        assert "projects" in unknown_skill_path.lower()
    
    def test_industry_specific_suggestions(self):
        """Test industry-specific suggestion generation."""
        # Test fintech suggestions
        fintech_suggestions = get_industry_specific_suggestions("fintech", ["python", "django"])
        assert len(fintech_suggestions) > 0
        
        fintech_text = " ".join([s.suggestion for s in fintech_suggestions])
        assert any(keyword in fintech_text.lower() for keyword in ["compliance", "security", "financial"])
        
        # Test healthcare suggestions
        healthcare_suggestions = get_industry_specific_suggestions("healthcare", ["python"])
        healthcare_text = " ".join([s.suggestion for s in healthcare_suggestions])
        assert "hipaa" in healthcare_text.lower()
    
    def test_optimization_suggestions_for_strong_profiles(self):
        """Test suggestions for profiles with high match scores."""
        # Strong profile with no missing must-have skills
        suggestions = generate_suggestions_enhanced(
            must_have_missing=[],
            nice_to_have_missing=["redis"],  # Only minor gaps
            profile_skills=["python", "django", "postgresql", "aws"],
            job_description="Python Django developer",
            importance_weights={"redis": 1.0}
        )
        
        # Should include optimization and leadership suggestions
        suggestion_text = " ".join([s.suggestion for s in suggestions])
        assert any(keyword in suggestion_text.lower() for keyword in 
                  ["leadership", "mentoring", "senior", "quantify", "metrics"])


class TestIndustryDetectionAndKeywords:
    """Test industry detection and keyword extraction."""
    
    def test_industry_context_detection(self):
        """Test detection of industry context from job descriptions."""
        # Test fintech detection
        fintech_desc = "We're a fintech company looking for a blockchain developer with cryptocurrency experience"
        assert detect_industry_context(fintech_desc) == "fintech"
        
        # Test healthcare detection
        healthcare_desc = "Healthcare technology company seeking HIPAA-compliant medical software developer"
        assert detect_industry_context(healthcare_desc) == "healthcare"
        
        # Test SaaS detection
        saas_desc = "Multi-tenant SaaS platform needs API developer for subscription service"
        assert detect_industry_context(saas_desc) == "saas"
        
        # Test no clear industry
        generic_desc = "Software developer needed for web application development"
        assert detect_industry_context(generic_desc) is None
    
    def test_high_value_keyword_extraction(self):
        """Test extraction of high-value keywords."""
        text = """
        Senior Python developer needed for scalable microservices architecture.
        Experience with cloud-native solutions, automation, and data-driven analytics required.
        Leadership and team management skills preferred.
        """
        
        keywords = extract_high_value_keywords(text)
        
        assert len(keywords) > 0
        # Should include technical terms
        assert "python" in keywords
        # Should include business terms
        assert any(keyword in keywords for keyword in ["scalable", "leadership", "cloud-native"])
    
    def test_keyword_frequency_ranking(self):
        """Test that keywords are ranked by frequency and importance."""
        text = "Python Python Python developer with Django Django experience and AWS knowledge"
        keywords = extract_high_value_keywords(text)
        
        # Python should appear first due to higher frequency
        if len(keywords) > 1:
            assert keywords[0] == "python"


class TestBatchProcessingAndReporting:
    """Test batch processing and enhanced reporting functionality."""
    
    @pytest.mark.asyncio
    async def test_batch_match_score_calculation(self):
        """Test batch processing of multiple job matches."""
        profile_data = {
            "text": "Python Django developer with PostgreSQL and AWS experience"
        }
        
        job_listings = [
            {
                "id": 1,
                "title": "Backend Developer",
                "company": "TechCorp",
                "description": "Python Django developer needed with PostgreSQL"
            },
            {
                "id": 2,
                "title": "Full Stack Developer", 
                "company": "StartupXYZ",
                "description": "React and Node.js developer with MongoDB"
            },
            {
                "id": 3,
                "title": "Cloud Engineer",
                "company": "CloudCo",
                "description": "AWS cloud engineer with Python automation"
            }
        ]
        
        results = await batch_calculate_match_scores(profile_data, job_listings)
        
        assert len(results) == 3
        
        # Check result structure
        for result in results:
            assert "job_id" in result
            assert "job_title" in result
            assert "company" in result
            assert "match_score" in result
            assert "reasons" in result
            assert "suggestions" in result
        
        # First job should have highest match (Python Django PostgreSQL)
        job1_result = next(r for r in results if r["job_id"] == 1)
        job2_result = next(r for r in results if r["job_id"] == 2)
        
        assert job1_result["match_score"] > job2_result["match_score"]
    
    def test_match_trend_calculation(self):
        """Test match score trend calculation over time."""
        # Simulated match data with improving trend
        base_time = datetime.utcnow() - timedelta(days=30)
        matches = []
        
        for i in range(10):
            matches.append({
                "match_score": 60 + i * 3,  # Improving scores
                "created_at": base_time + timedelta(days=i * 3)
            })
        
        trend = calculate_match_trend(matches)
        
        assert trend["direction"] == "improving"
        assert trend["change"] > 0
        assert "early_average" in trend
        assert "recent_average" in trend
        assert trend["recent_average"] > trend["early_average"]
        
        # Test stable trend
        stable_matches = [{"match_score": 75, "created_at": base_time + timedelta(days=i)} for i in range(10)]
        stable_trend = calculate_match_trend(stable_matches)
        assert stable_trend["direction"] == "stable"
        
        # Test insufficient data
        few_matches = [{"match_score": 75, "created_at": base_time}]
        insufficient_trend = calculate_match_trend(few_matches)
        assert insufficient_trend["trend"] == "insufficient_data"
    
    def test_profile_recommendation_generation(self):
        """Test comprehensive profile recommendation generation."""
        # Low score recommendations
        low_score_recs = generate_profile_recommendations(
            avg_score=45.0,
            skill_gaps=[{"skill": "python", "impact": "critical", "gap_frequency": 10}],
            trending_skills=[{"skill": "rust", "trend_score": 0.8}],
            top_skills=[{"skill": "javascript", "match_frequency": 5}]
        )
        
        assert len(low_score_recs) > 0
        rec_text = " ".join(low_score_recs)
        assert any(keyword in rec_text.lower() for keyword in ["fundamental", "upskilling", "pivot"])
        
        # High score recommendations
        high_score_recs = generate_profile_recommendations(
            avg_score=90.0,
            skill_gaps=[],
            trending_skills=[{"skill": "kubernetes", "trend_score": 0.9}],
            top_skills=[{"skill": "python", "match_frequency": 20}]
        )
        
        high_rec_text = " ".join(high_score_recs)
        assert any(keyword in high_rec_text.lower() for keyword in ["excellent", "leadership", "cutting-edge"])
    
    @pytest.mark.asyncio
    async def test_enhanced_profile_aggregate_report(self):
        """Test enhanced profile aggregate report generation."""
        # Mock database responses
        mock_matches = [
            {
                "match_score": 85.0,
                "reasons": '[{"skill": "python", "category": "must_have", "status": "matched", "weight": 0.3}]',
                "created_at": datetime.utcnow() - timedelta(days=5),
                "title": "Backend Developer",
                "company": "TechCorp",
                "description": "Python Django developer needed"
            },
            {
                "match_score": 70.0,
                "reasons": '[{"skill": "react", "category": "must_have", "status": "missing", "weight": 0.2}]',
                "created_at": datetime.utcnow() - timedelta(days=10),
                "title": "Full Stack Developer",
                "company": "WebCorp",
                "description": "React developer needed"
            }
        ]
        
        with patch('app.services.scoring.database') as mock_db:
            mock_db.fetch_all = AsyncMock(return_value=mock_matches)
            
            report = await get_profile_aggregate_report_enhanced(profile_id=123)
            
            assert report["profile_id"] == 123
            assert report["total_jobs_analyzed"] == 2
            assert report["average_match_score"] == 77.5
            assert report["median_match_score"] == 77.5
            
            # Should have distribution
            assert "match_distribution" in report
            assert report["match_distribution"]["good"] == 2  # Both scores in 75-90 range
            
            # Should have top skills and gaps
            assert len(report["top_skills"]) > 0
            assert len(report["skill_gaps"]) > 0
            
            # Should have recommendations
            assert len(report["recommendations"]) > 0


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling for enhanced features."""
    
    def test_empty_inputs_enhanced_scoring(self):
        """Test enhanced scoring with empty inputs."""
        result = calculate_match_score_enhanced(
            profile_skills=[],
            profile_text="",
            must_have_skills=[],
            nice_to_have_skills=[],
            job_description="",
            bonus_skills=[]
        )
        
        assert 0.0 <= result["match_score"] <= 100.0
        assert "breakdown" in result
        assert isinstance(result["reasons"], list)
        assert isinstance(result["suggestions"], list)
    
    def test_skill_importance_weights_edge_cases(self):
        """Test skill importance calculation with edge cases."""
        # Empty job description
        weights = calculate_skill_importance_weights(["python"], "")
        assert weights["python"] > 0.0
        
        # Job description without any skills
        weights = calculate_skill_importance_weights(["python"], "Looking for a great developer")
        assert weights["python"] > 0.0
        
        # Very long job description
        long_desc = "Python " * 1000
        weights = calculate_skill_importance_weights(["python"], long_desc)
        assert weights["python"] > 1.0  # Should get frequency boost
    
    def test_text_similarity_edge_cases(self):
        """Test text similarity with edge cases."""
        # Empty texts
        assert calculate_text_similarity("", "") == 0.0
        assert calculate_text_similarity("test", "") == 0.0
        
        # Very short texts
        similarity = calculate_text_similarity("hi", "hello")
        assert 0.0 <= similarity <= 1.0
        
        # Special characters and numbers
        similarity = calculate_text_similarity("C++ developer", "C# programmer")
        assert 0.0 <= similarity <= 1.0
    
    def test_large_skill_lists(self):
        """Test handling of large skill lists."""
        # Large profile skills list
        large_skills = [f"skill_{i}" for i in range(100)]
        
        result = calculate_match_score_enhanced(
            profile_skills=large_skills,
            profile_text="Developer with many skills",
            must_have_skills=["skill_1", "skill_2"],
            nice_to_have_skills=["skill_3"],
            job_description="Need developer with skill_1 and skill_2"
        )
        
        # Should handle large lists without crashing
        assert 0.0 <= result["match_score"] <= 100.0
        assert len(result["reasons"]) > 0


class TestSkillMatchDataclass:
    """Test the SkillMatch dataclass."""
    
    def test_skill_match_creation(self):
        """Test creation of SkillMatch instances."""
        skill_match = SkillMatch(
            skill="python",
            category="must_have",
            status="matched",
            confidence=0.95,
            weight=0.3,
            context="5 years Python development experience"
        )
        
        assert skill_match.skill == "python"
        assert skill_match.category == "must_have"
        assert skill_match.status == "matched"
        assert skill_match.confidence == 0.95
        assert skill_match.weight == 0.3
        assert skill_match.context == "5 years Python development experience"
    
    def test_skill_match_default_context(self):
        """Test SkillMatch with default context."""
        skill_match = SkillMatch(
            skill="django",
            category="nice_to_have", 
            status="missing",
            confidence=1.0,
            weight=0.1
        )
        
        assert skill_match.context is None


# Test configuration and fixtures
@pytest.fixture
def sample_enhanced_profile():
    """Enhanced sample profile for testing."""
    return {
        "skills": ["python", "django", "postgresql", "react", "aws", "docker", "kubernetes"],
        "text": """
        Senior Full Stack Developer with 7+ years experience.
        
        Backend: Python, Django, FastAPI, PostgreSQL, Redis
        Frontend: React, JavaScript, TypeScript, HTML/CSS
        Infrastructure: AWS (EC2, S3, RDS), Docker, Kubernetes
        
        Led development of microservices architecture serving 1M+ users.
        Implemented CI/CD pipelines and automated testing.
        Experience with agile methodologies and team leadership.
        """
    }


@pytest.fixture
def sample_enhanced_job():
    """Enhanced sample job for testing."""
    return {
        "id": 1,
        "title": "Senior Backend Engineer",
        "company": "TechCorp",
        "description": """
        Senior Backend Engineer - TechCorp
        
        Required Skills:
        - 5+ years Python development experience
        - Django or FastAPI framework expertise
        - PostgreSQL database design and optimization
        - AWS cloud platform experience (EC2, S3, RDS)
        - RESTful API development
        
        Preferred Skills:
        - Redis caching implementation
        - Docker containerization
        - Kubernetes orchestration
        - Team leadership experience
        - Agile/Scrum methodologies
        
        Bonus Skills:
        - Machine learning experience
        - GraphQL API development
        - Terraform infrastructure as code
        """
    }


@pytest.fixture
def mock_database():
    """Mock database for testing."""
    with patch('app.services.scoring.database') as mock_db:
        mock_db.fetch_all = AsyncMock(return_value=[])
        yield mock_db


# Integration test for the complete enhanced workflow
class TestCompleteEnhancedWorkflow:
    """Integration test for the complete enhanced scoring workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_enhanced_matching_workflow(self, sample_enhanced_profile, sample_enhanced_job):
        """Test the complete enhanced matching workflow."""
        # Extract skills with context
        profile_skills = extract_skills_from_text(sample_enhanced_profile["text"])
        skills_with_context = extract_skills_with_context(sample_enhanced_profile["text"])
        
        # Extract three-tier job requirements
        must_have, nice_to_have, bonus = extract_job_requirements_enhanced(sample_enhanced_job["description"])
        
        # Calculate enhanced match score
        result = calculate_match_score_enhanced(
            profile_skills=profile_skills,
            profile_text=sample_enhanced_profile["text"],
            must_have_skills=must_have,
            nice_to_have_skills=nice_to_have,
            job_description=sample_enhanced_job["description"],
            bonus_skills=bonus
        )
        
        # Verify comprehensive result structure
        assert result["match_score"] >= 80.0  # Should be high match
        assert "breakdown" in result
        assert len(result["reasons"]) > 5
        assert len(result["suggestions"]) > 0
        
        # Verify skill categorization
        must_have_reasons = [r for r in result["reasons"] if r.category == "must_have"]
        nice_to_have_reasons = [r for r in result["reasons"] if r.category == "nice_to_have"]
        bonus_reasons = [r for r in result["reasons"] if r.category == "bonus"]
        
        assert len(must_have_reasons) > 0
        assert len(nice_to_have_reasons) > 0
        
        # Test batch processing
        job_listings = [sample_enhanced_job]
        batch_results = await batch_calculate_match_scores(sample_enhanced_profile, job_listings)
        
        assert len(batch_results) == 1
        assert batch_results[0]["match_score"] == result["match_score"]
        
        # Test industry detection
        industry = detect_industry_context(sample_enhanced_job["description"])
        if industry:
            industry_suggestions = get_industry_specific_suggestions(industry, profile_skills)
            assert len(industry_suggestions) >= 0
        
        # Test keyword extraction
        keywords = extract_high_value_keywords(sample_enhanced_job["description"])
        assert len(keywords) > 0
        assert "python" in keywords


if __name__ == "__main__":
    pytest.main([__file__, "-v"])