import re
import json
from typing import List, Tuple, Dict, Any, Optional, Set
from collections import Counter, defaultdict
from dataclasses import dataclass
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import logging
from datetime import datetime
import asyncio
import statistics
from functools import lru_cache

from app.matches.models import MatchReason, MatchSuggestion
from app.db import database

logger = logging.getLogger(__name__)

@dataclass
class SkillMatch:
    """Enhanced skill matching data structure."""
    skill: str
    category: str  # 'must_have', 'nice_to_have', 'bonus'
    status: str   # 'matched', 'missing', 'partial'
    confidence: float  # 0.0 - 1.0
    weight: float
    context: Optional[str] = None  # Where the skill was found

# Expanded and categorized technical skills
TECHNICAL_SKILLS = {
    # Programming Languages
    'programming': {
        'python', 'java', 'javascript', 'typescript', 'go', 'rust', 'c++', 'c#', 'php', 'ruby',
        'kotlin', 'swift', 'scala', 'r', 'matlab', 'perl', 'lua', 'dart', 'objective-c',
        'assembly', 'cobol', 'fortran', 'haskell', 'clojure', 'erlang', 'elixir'
    },
    # Frontend Technologies
    'frontend': {
        'react', 'vue', 'angular', 'svelte', 'html', 'css', 'sass', 'less', 'stylus',
        'jquery', 'bootstrap', 'tailwind', 'material-ui', 'ant-design', 'webpack',
        'vite', 'parcel', 'rollup', 'babel', 'npm', 'yarn', 'pnpm'
    },
    # Backend Technologies
    'backend': {
        'node.js', 'express', 'django', 'flask', 'fastapi', 'spring', 'spring-boot',
        'laravel', 'symfony', 'rails', 'sinatra', 'asp.net', '.net-core', 'gin',
        'fiber', 'echo', 'koa', 'nestjs', 'next.js', 'nuxt.js', 'gatsby'
    },
    # Databases
    'database': {
        'postgresql', 'mysql', 'mongodb', 'redis', 'elasticsearch', 'cassandra',
        'dynamodb', 'sqlite', 'oracle', 'sql-server', 'mariadb', 'couchdb',
        'neo4j', 'influxdb', 'clickhouse', 'snowflake', 'bigquery'
    },
    # Cloud & Infrastructure
    'cloud': {
        'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform', 'ansible',
        'jenkins', 'gitlab-ci', 'github-actions', 'circleci', 'travis-ci',
        'helm', 'istio', 'prometheus', 'grafana', 'elk-stack', 'datadog'
    },
    # Tools & Methodologies
    'tools': {
        'git', 'github', 'gitlab', 'bitbucket', 'jira', 'confluence', 'slack',
        'teams', 'notion', 'linux', 'bash', 'powershell', 'vim', 'vscode',
        'intellij', 'eclipse', 'postman', 'insomnia'
    },
    # Data & AI
    'data_ai': {
        'tensorflow', 'pytorch', 'scikit-learn', 'pandas', 'numpy', 'matplotlib',
        'seaborn', 'plotly', 'jupyter', 'apache-spark', 'hadoop', 'kafka',
        'airflow', 'dbt', 'looker', 'tableau', 'power-bi'
    },
    # Architecture & Protocols
    'architecture': {
        'rest', 'graphql', 'grpc', 'soap', 'microservices', 'serverless',
        'event-driven', 'cqrs', 'ddd', 'api-gateway', 'load-balancer',
        'oauth', 'jwt', 'ssl', 'tls', 'websockets', 'sse'
    },
    # Methodologies
    'methodology': {
        'agile', 'scrum', 'kanban', 'lean', 'devops', 'ci/cd', 'tdd', 'bdd',
        'pair-programming', 'code-review', 'unit-testing', 'integration-testing',
        'e2e-testing', 'performance-testing', 'security-testing'
    }
}

# Flatten for easier access
ALL_SKILLS = set()
SKILL_CATEGORIES = {}
for category, skills in TECHNICAL_SKILLS.items():
    ALL_SKILLS.update(skills)
    for skill in skills:
        SKILL_CATEGORIES[skill] = category

# Enhanced skill synonyms with confidence scores
SKILL_SYNONYMS = {
    'js': ('javascript', 1.0),
    'ts': ('typescript', 1.0),
    'nodejs': ('node.js', 1.0),
    'reactjs': ('react', 1.0),
    'vuejs': ('vue', 1.0),
    'angularjs': ('angular', 0.9),
    'postgres': ('postgresql', 1.0),
    'mongo': ('mongodb', 1.0),
    'k8s': ('kubernetes', 1.0),
    'tf': ('terraform', 0.8),  # Could also mean TensorFlow
    'ml': ('machine learning', 1.0),
    'ai': ('artificial intelligence', 1.0),
    'dl': ('deep learning', 1.0),
    'c++': ('cpp', 1.0),
    'c#': ('csharp', 1.0),
    'objective-c': ('objc', 1.0),
    'sql': ('database', 0.7),
    'nosql': ('mongodb', 0.6),
    'rdbms': ('postgresql', 0.7),
    'ci/cd': ('continuous integration', 1.0),
    'devops': ('development operations', 1.0),
    'ux': ('user experience', 1.0),
    'ui': ('user interface', 1.0),
    'mvc': ('model-view-controller', 1.0),
    'orm': ('object-relational mapping', 1.0),
    'api': ('application programming interface', 1.0)
}

# Experience level indicators
EXPERIENCE_PATTERNS = {
    r'(\d+)\+?\s*years?\s+(?:of\s+)?experience\s+(?:with\s+|in\s+)?(\w+)': 2,
    r'senior\s+(\w+)\s+(?:developer|engineer)': 1.5,
    r'lead\s+(\w+)\s+(?:developer|engineer)': 1.8,
    r'principal\s+(\w+)\s+(?:developer|engineer)': 2.0,
    r'expert\s+(?:in\s+|with\s+)?(\w+)': 1.7,
    r'proficient\s+(?:in\s+|with\s+)?(\w+)': 1.3,
    r'advanced\s+(\w+)': 1.4,
    r'intermediate\s+(\w+)': 1.1,
    r'basic\s+(\w+)': 0.8
}

@lru_cache(maxsize=1000)
def normalize_skill(skill: str) -> Tuple[str, float]:
    """Normalize skill name with confidence score."""
    skill_lower = skill.lower().strip()
    
    if skill_lower in SKILL_SYNONYMS:
        normalized, confidence = SKILL_SYNONYMS[skill_lower]
        return normalized, confidence
    
    return skill_lower, 1.0

def extract_skills_with_context(text: str) -> List[Tuple[str, str, float]]:
    """Extract skills with context and confidence scores."""
    text_lower = text.lower()
    found_skills = []
    
    # Direct skill matching with context
    for skill in ALL_SKILLS:
        pattern = r'\b' + re.escape(skill) + r'\b'
        matches = re.finditer(pattern, text_lower)
        
        for match in matches:
            start, end = match.span()
            # Get surrounding context (20 chars each side)
            context_start = max(0, start - 20)
            context_end = min(len(text), end + 20)
            context = text[context_start:context_end].strip()
            
            # Calculate confidence based on context
            confidence = 1.0
            
            # Boost confidence for experience indicators
            for exp_pattern, boost in EXPERIENCE_PATTERNS.items():
                if re.search(exp_pattern, context, re.IGNORECASE):
                    confidence = min(2.0, confidence * boost)
                    break
            
            found_skills.append((skill, context, confidence))
    
    # Pattern-based extraction for structured content
    extraction_patterns = [
        (r'(?:skills?|technologies?|tools?)\s*:?\s*([^.!?\n]+)', 1.2),
        (r'(?:experience with|proficient in|skilled in|expert in|knowledge of)\s+([^,.;]+)', 1.3),
        (r'•\s*([^•\n]+?)(?:\n|$)', 1.1),  # Bullet points
        (r'-\s*([^-\n]+?)(?:\n|$)', 1.1),   # Dash points
        (r'(\w+(?:\.\w+)*)\s*(?:\d+\+?\s*years?)', 1.5)  # Years of experience
    ]
    
    for pattern, base_confidence in extraction_patterns:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        for match in matches:
            skills_text = match.strip(' .,;-')
            potential_skills = re.split(r'[,;/&\s]+', skills_text)
            
            for skill in potential_skills:
                skill = skill.strip(' .,;()[]{}')
                normalized_skill, norm_confidence = normalize_skill(skill)
                
                if normalized_skill in ALL_SKILLS:
                    confidence = base_confidence * norm_confidence
                    found_skills.append((normalized_skill, match, confidence))
    
    return found_skills

def extract_skills_from_text(text: str) -> List[str]:
    """Extract technical skills from text (legacy interface)."""
    skills_with_context = extract_skills_with_context(text)
    # Deduplicate and return unique skills
    unique_skills = {}
    for skill, context, confidence in skills_with_context:
        if skill not in unique_skills or confidence > unique_skills[skill][1]:
            unique_skills[skill] = (context, confidence)
    
    return list(unique_skills.keys())

import re
from typing import List, Tuple

def extract_job_requirements_enhanced(job_description: str) -> Tuple[List[str], List[str], List[str]]:
    """Enhanced job requirement extraction with bonus skills category."""
    text_lower = job_description.lower()

    must_have_skills = set()
    nice_to_have_skills = set()
    bonus_skills = set()

    # --- Step 1: Section heading-based extraction ---
    section_patterns = {
        "must": r"(?:required skills?|must have|essential)\s*:([\s\S]*?)(?=\n\s*\n|preferred skills?|nice to have|bonus points?|bonus:|$)",
        "nice": r"(?:preferred skills?|nice to have)\s*:([\s\S]*?)(?=\n\s*\n|bonus points?|bonus:|$)",
        "bonus": r"(?:bonus points?|bonus)\s*:([\s\S]*?)(?=\n\s*\n|$)"
    }

    for category, pattern in section_patterns.items():
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            section_text = match.group(1)
            # Support both bullet points and comma-separated items
            items = re.findall(r"-\s*([^\n]+)", section_text)
            if not items:
                items = [i.strip() for i in section_text.split(",") if i.strip()]
            for skill in items:
                extracted = extract_skills_from_text(skill)
                if category == "must":
                    must_have_skills.update(extracted)
                elif category == "nice":
                    nice_to_have_skills.update(extracted)
                elif category == "bonus":
                    bonus_skills.update(extracted)

    # --- Step 2: Pattern-based extraction (fallback if headings aren't found) ---
    if not any([must_have_skills, nice_to_have_skills, bonus_skills]):
        must_have_patterns = [
            r'(?:required|must have|essential|mandatory|minimum|need|needs)\s*:?\s*([^.!?\n]+)',
            r'(?:you must|candidates must|required to|shall)\s+(?:have\s+)?([^.!?\n]+)',
            r'(?:minimum|at least)\s+(\d+\+?\s*years?\s+[^.!?\n]+)',
            r'(?:bachelor|master|degree|diploma|certification)\s+(?:in\s+)?([^.!?\n]+)',
            r'(?:experience|background)\s+(?:in\s+|with\s+)?([^.!?\n]+?)(?:required|mandatory|essential)',
            r'(?:strong|solid|extensive)\s+(?:experience|knowledge|skills?)\s+(?:in\s+|with\s+)?([^.!?\n]+)',
        ]

        nice_to_have_patterns = [
            r'(?:preferred|nice to have|bonus|plus|advantage|desirable|would be nice|beneficial)\s*:?\s*([^.!?\n]+)',
            r'(?:good to have|asset|helpful|valuable)\s+(?:if\s+)?([^.!?\n]+)',
            r'(?:familiarity with|exposure to|some experience)\s+([^.!?\n]+)',
            r'(?:additional|extra|supplementary)\s+(?:skills?|experience)\s*:?\s*([^.!?\n]+)',
        ]

        bonus_patterns = [
            r'(?:bonus points?|highly desired|strongly preferred|ideal candidate)\s+([^.!?\n]+)',
            r'(?:exceptional|outstanding|excellent)\s+(?:skills?|experience)\s+(?:in\s+|with\s+)?([^.!?\n]+)',
            r'(?:thought leader|expert|guru|ninja|rockstar)\s+(?:in\s+|with\s+)?([^.!?\n]+)',
        ]

        for patterns, skill_set in [
            (must_have_patterns, must_have_skills),
            (nice_to_have_patterns, nice_to_have_skills),
            (bonus_patterns, bonus_skills)
        ]:
            for pattern in patterns:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                for match in matches:
                    skills = extract_skills_from_text(match)
                    skill_set.update(skills)

    # --- Step 3: Remove overlaps (maintain hierarchy: must > nice > bonus) ---
    nice_to_have_skills -= must_have_skills
    bonus_skills -= must_have_skills
    bonus_skills -= nice_to_have_skills

    return list(must_have_skills), list(nice_to_have_skills), list(bonus_skills)

def extract_job_requirements(job_description: str) -> Tuple[List[str], List[str]]:
    """Legacy interface for job requirement extraction."""
    must_have, nice_to_have, bonus = extract_job_requirements_enhanced(job_description)
    # Combine nice_to_have and bonus for legacy compatibility
    return must_have, nice_to_have + bonus

@lru_cache(maxsize=100)
def calculate_text_similarity_cached(text1: str, text2: str) -> float:
    """Cached version of text similarity calculation."""
    return calculate_text_similarity(text1, text2)

def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate TF-IDF cosine similarity with enhanced preprocessing."""
    if not text1.strip() or not text2.strip():
        return 0.0
    
    try:
        # Enhanced preprocessing
        def preprocess_text(text):
            # Convert to lowercase and remove special characters
            text = re.sub(r'[^\w\s]', ' ', text.lower())
            # Remove extra whitespace
            text = ' '.join(text.split())
            return text
        
        text1_clean = preprocess_text(text1)
        text2_clean = preprocess_text(text2)
        
        vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=2000,
            ngram_range=(1, 3),  # Include trigrams for better context
            min_df=1,
            max_df=0.95,
            lowercase=True,
            token_pattern=r'\b\w+\b'
        )
        
        tfidf_matrix = vectorizer.fit_transform([text1_clean, text2_clean])
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        
        return float(similarity)
        
    except Exception as e:
        logger.warning(f"TF-IDF similarity calculation failed: {e}")
        return 0.0

def calculate_skill_importance_weights(skills: List[str], job_description: str) -> Dict[str, float]:
    """Calculate importance weights for skills based on job description context."""
    weights = {}
    job_lower = job_description.lower()
    
    for skill in skills:
        base_weight = 1.0
        
        # Count occurrences
        occurrences = len(re.findall(r'\b' + re.escape(skill) + r'\b', job_lower))
        frequency_weight = min(2.0, 1.0 + (occurrences * 0.2))
        
        # Check for emphasis keywords around skill mentions
        emphasis_patterns = [
            r'(?:critical|crucial|essential|key|important|core|primary|main)\s+.*?\b' + re.escape(skill) + r'\b',
            r'\b' + re.escape(skill) + r'\b.*?(?:critical|crucial|essential|key|important|core|primary|main)',
        ]
        
        emphasis_weight = 1.0
        for pattern in emphasis_patterns:
            if re.search(pattern, job_lower):
                emphasis_weight = 1.5
                break
        
        # Position-based weighting (earlier mention = more important)
        first_mention = job_lower.find(skill)
        if first_mention != -1:
            position_weight = max(0.8, 1.2 - (first_mention / len(job_lower)))
        else:
            position_weight = 1.0
        
        # Skill category weighting
        category = SKILL_CATEGORIES.get(skill, 'tools')
        category_weights = {
            'programming': 1.3,
            'backend': 1.2,
            'frontend': 1.2,
            'database': 1.1,
            'cloud': 1.1,
            'data_ai': 1.2,
            'architecture': 1.1,
            'methodology': 0.9,
            'tools': 0.8
        }
        category_weight = category_weights.get(category, 1.0)
        
        final_weight = base_weight * frequency_weight * emphasis_weight * position_weight * category_weight
        weights[skill] = min(3.0, final_weight)  # Cap at 3.0
    
    return weights

def calculate_match_score_enhanced(
    profile_skills: List[str],
    profile_text: str,
    must_have_skills: List[str],
    nice_to_have_skills: List[str],
    job_description: str,
    bonus_skills: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Enhanced match score calculation with weighted importance."""
    
    if bonus_skills is None:
        bonus_skills = []
    
    # Normalize skills for comparison
    profile_skills_norm = {normalize_skill(skill)[0] for skill in profile_skills}
    must_have_norm = {normalize_skill(skill)[0] for skill in must_have_skills}
    nice_to_have_norm = {normalize_skill(skill)[0] for skill in nice_to_have_skills}
    bonus_norm = {normalize_skill(skill)[0] for skill in bonus_skills}
    
    # Calculate importance weights
    all_job_skills = must_have_skills + nice_to_have_skills + bonus_skills
    importance_weights = calculate_skill_importance_weights(all_job_skills, job_description)
    
    reasons = []
    total_weight = 0.0
    achieved_weight = 0.0
    
    # Process must-have skills (70% of total weight)
    must_have_matched = must_have_norm.intersection(profile_skills_norm)
    must_have_missing = must_have_norm - profile_skills_norm
    
    for skill in must_have_matched:
        weight = importance_weights.get(skill, 1.0) * 0.7 / max(len(must_have_norm), 1)
        total_weight += weight
        achieved_weight += weight
        
        reasons.append(MatchReason(
            skill=skill,
            category="must_have",
            status="matched",
            weight=weight
        ))
    
    for skill in must_have_missing:
        weight = importance_weights.get(skill, 1.0) * 0.7 / max(len(must_have_norm), 1)
        total_weight += weight
        
        reasons.append(MatchReason(
            skill=skill,
            category="must_have",
            status="missing",
            weight=0.0
        ))
    
    # Process nice-to-have skills (25% of total weight)
    nice_to_have_matched = nice_to_have_norm.intersection(profile_skills_norm)
    nice_to_have_missing = nice_to_have_norm - profile_skills_norm
    
    for skill in nice_to_have_matched:
        weight = importance_weights.get(skill, 1.0) * 0.25 / max(len(nice_to_have_norm), 1)
        total_weight += weight
        achieved_weight += weight
        
        reasons.append(MatchReason(
            skill=skill,
            category="nice_to_have",
            status="matched",
            weight=weight
        ))
    
    for skill in nice_to_have_missing:
        weight = importance_weights.get(skill, 1.0) * 0.25 / max(len(nice_to_have_norm), 1)
        total_weight += weight
        
        reasons.append(MatchReason(
            skill=skill,
            category="nice_to_have",
            status="missing",
            weight=0.0
        ))
    
    # Process bonus skills (5% of total weight)
    bonus_matched = bonus_norm.intersection(profile_skills_norm)
    
    for skill in bonus_matched:
        weight = importance_weights.get(skill, 1.0) * 0.05 / max(len(bonus_norm), 1)
        total_weight += weight
        achieved_weight += weight
        
        reasons.append(MatchReason(
            skill=skill,
            category="bonus",
            status="matched",
            weight=weight
        ))
    
    # Calculate base score from weighted skills
    skill_score = achieved_weight / max(total_weight, 1.0) if total_weight > 0 else 0.0
    
    # Add text similarity component (up to 15% boost)
    text_similarity = calculate_text_similarity_cached(profile_text, job_description)
    similarity_bonus = text_similarity * 0.15
    
    # Experience level bonus based on profile analysis
    experience_bonus = calculate_experience_bonus(profile_text, job_description)
    
    # Final score calculation
    final_score = min(100.0, (skill_score + similarity_bonus + experience_bonus) * 100)
    
    # Generate enhanced suggestions
    suggestions = generate_suggestions_enhanced(
        must_have_missing=list(must_have_missing),
        nice_to_have_missing=list(nice_to_have_missing),
        profile_skills=profile_skills,
        job_description=job_description,
        importance_weights=importance_weights,
        profile_text=profile_text
    )
    
    logger.info(f"Enhanced match score: {final_score:.2f} (skill: {skill_score:.2f}, "
               f"similarity: {similarity_bonus:.2f}, experience: {experience_bonus:.2f})")
    
    return {
        "match_score": round(final_score, 2),
        "reasons": reasons,
        "suggestions": suggestions,
        "breakdown": {
            "skill_match": round(skill_score * 100, 2),
            "text_similarity": round(similarity_bonus * 100, 2),
            "experience_bonus": round(experience_bonus * 100, 2)
        }
    }

def calculate_experience_bonus(profile_text: str, job_description: str) -> float:
    """Calculate experience-based bonus score."""
    profile_lower = profile_text.lower()
    job_lower = job_description.lower()
    
    # Flexible patterns for profile text
    profile_years = []
    year_patterns = [
        # Allow optional 'of', and up to 2 extra words before 'experience'
        r'(\d+)\+?\s*years?(?:\s+of)?(?:\s+\w+){0,2}\s+experience',
        r'over\s+(\d+)\s+years?',
        r'more than\s+(\d+)\s+years?'
    ]
    
    for pattern in year_patterns:
        matches = re.findall(pattern, profile_lower)
        profile_years.extend([int(match) for match in matches])
    
    # Flexible patterns for job description
    job_years = []
    job_year_patterns = [
        r'(\d+)\+?\s*years?(?:\s+of)?(?:\s+\w+){0,2}\s+(?:experience|background)',
        r'minimum\s+(\d+)\s+years?',
        r'at least\s+(\d+)\s+years?'
    ]
    
    for pattern in job_year_patterns:
        matches = re.findall(pattern, job_lower)
        job_years.extend([int(match) for match in matches])
    
    if not profile_years or not job_years:
        return 0.0
    
    max_profile_years = max(profile_years)
    min_required_years = min(job_years)
    
    if max_profile_years >= min_required_years * 1.5:
        return 0.05  # Bonus for significantly exceeding requirements
    elif max_profile_years >= min_required_years:
        return 0.02  # Bonus for meeting requirements
    else:
        return -0.05  # Penalty for not meeting requirements


def calculate_match_score(
    profile_skills: List[str],
    profile_text: str,
    must_have_skills: List[str],
    nice_to_have_skills: List[str],
    job_description: str
) -> Dict[str, Any]:
    """Legacy interface for match score calculation."""
    return calculate_match_score_enhanced(
        profile_skills=profile_skills,
        profile_text=profile_text,
        must_have_skills=must_have_skills,
        nice_to_have_skills=nice_to_have_skills,
        job_description=job_description
    )

def generate_suggestions_enhanced(
    must_have_missing: List[str],
    nice_to_have_missing: List[str],
    profile_skills: List[str],
    job_description: str,
    importance_weights: Dict[str, float],
    profile_text: str = ""  # <-- add this default
) -> List[MatchSuggestion]:
    """Generate enhanced actionable improvement suggestions."""
    suggestions = []
    
    # Sort missing skills by importance
    must_have_sorted = sorted(must_have_missing, 
                            key=lambda x: importance_weights.get(x, 1.0), 
                            reverse=True)
    nice_to_have_sorted = sorted(nice_to_have_missing,
                                key=lambda x: importance_weights.get(x, 1.0),
                                reverse=True)
    
    # High-priority suggestions for critical missing skills
    if must_have_sorted:
        top_critical = must_have_sorted[:2]
        
        suggestions.append(MatchSuggestion(
            type="cv_improvement",
            suggestion=f"Prioritize gaining experience with {', '.join(top_critical)}",
            rationale=f"These are the highest-weighted must-have requirements missing from your profile",
            priority="critical"
        ))
        
        # Specific learning path suggestions
        for skill in top_critical[:3]:
            category = SKILL_CATEGORIES.get(skill, 'general')
            learning_suggestions = get_learning_suggestions(skill, category)
            
            suggestions.append(MatchSuggestion(
                type="skill_development",
                suggestion=learning_suggestions,
                rationale=f"Developing {skill} expertise will significantly improve your match score",
                priority="high"
            ))
    
    # Project-based suggestions
    if must_have_missing or nice_to_have_missing:
        all_missing = must_have_sorted[:2] + nice_to_have_sorted[:2]
        
        suggestions.append(MatchSuggestion(
            type="cv_improvement",
            suggestion=f"Create a portfolio project showcasing {', '.join(all_missing[:3])} integration",
            rationale="Hands-on projects demonstrate practical application of missing skills",
            priority="high"
        ))
    
    # Keyword optimization suggestions
    job_keywords = extract_high_value_keywords(job_description)
    profile_keywords = extract_high_value_keywords(profile_text if profile_text else "")
    missing_keywords = set(job_keywords) - set(profile_keywords)
    
    if missing_keywords:
        top_keywords = list(missing_keywords)[:3]
        suggestions.append(MatchSuggestion(
            type="keyword",
            suggestion=f"Include these high-value terms: {', '.join(top_keywords)}",
            rationale="These keywords appear prominently in the job description and will improve ATS matching",
            priority="medium"
        ))
    
    # Optimization suggestions for strong profiles
    if not must_have_missing and len(nice_to_have_missing) <= 2:
        suggestions.extend([
            MatchSuggestion(
                type="cv_improvement",
                suggestion="Quantify your achievements with specific metrics and business impact",
                rationale="Strong technical alignment - focus on demonstrating results and value delivered",
                priority="medium"
            ),
            MatchSuggestion(
                type="cv_improvement",
                suggestion="Highlight leadership, mentoring, or cross-functional collaboration experience",
                rationale="Senior roles value both technical skills and leadership capabilities",
                priority="medium"
            ),
            MatchSuggestion(
                type="optimization",
                suggestion="Consider applying to senior or specialized roles that match your strong skill set",
                rationale="Your profile shows strong alignment - you may be qualified for higher-level positions",
                priority="low"
            )
        ])
    
    # Industry-specific suggestions
    industry_context = detect_industry_context(job_description)
    if industry_context:
        industry_suggestions = get_industry_specific_suggestions(industry_context, profile_skills)
        suggestions.extend(industry_suggestions[:2])
    
    return suggestions[:8]  # Return top 8 suggestions

def get_learning_suggestions(skill: str, category: str) -> str:
    """Generate specific learning path suggestions for skills."""
    learning_paths = {
        'python': "Complete a Python certification course and build REST API projects",
        'react': "Build 2-3 React applications with modern hooks and state management",
        'aws': "Pursue AWS Cloud Practitioner certification and practice with free tier services",
        'kubernetes': "Set up a local k8s cluster and deploy containerized applications",
        'postgresql': "Practice database design and optimization with real datasets",
        'docker': "Containerize existing projects and learn Docker Compose for multi-service apps",
        'tensorflow': "Complete machine learning courses and implement neural network projects",
        'django': "Build a full-stack web application with authentication and database integration"
    }
    
    category_defaults = {
        'programming': f"Take online courses and build projects demonstrating {skill} proficiency",
        'frontend': f"Create modern web applications showcasing {skill} best practices",
        'backend': f"Develop API services and server-side applications using {skill}",
        'database': f"Practice data modeling and query optimization with {skill}",
        'cloud': f"Gain hands-on experience with {skill} through tutorials and free tier usage",
        'data_ai': f"Complete data science projects and courses focused on {skill}",
        'tools': f"Integrate {skill} into your development workflow and document the process"
    }
    
    return learning_paths.get(skill, category_defaults.get(category, f"Develop expertise in {skill} through courses and practical projects"))

def extract_high_value_keywords(text: str) -> List[str]:
    """Extract high-value keywords from text using TF-IDF analysis."""
    if not text.strip():
        return []
    
    try:
        # Focus on technical and business terms
        technical_pattern = r'\b(?:' + '|'.join(ALL_SKILLS) + r')\b'
        business_pattern = r'\b(?:scale|growth|performance|optimization|architecture|leadership|team|agile|innovation|digital transformation|user experience|data-driven|cloud-native|microservices|automation|security|compliance|integration|analytics|machine learning|artificial intelligence)\b'
        
        combined_pattern = f'(?:{technical_pattern})|(?:{business_pattern})'
        
        keywords = re.findall(combined_pattern, text.lower())
        
        # Count frequency and return top keywords
        keyword_counts = Counter(keywords)
        return [kw for kw, count in keyword_counts.most_common(10)]
        
    except Exception as e:
        logger.warning(f"Keyword extraction failed: {e}")
        return []

def detect_industry_context(job_description: str) -> Optional[str]:
    """Detect industry context from job description."""
    industry_keywords = {
        'fintech': ['financial', 'banking', 'payment', 'trading', 'blockchain', 'cryptocurrency', 'investment'],
        'healthcare': ['healthcare', 'medical', 'patient', 'clinical', 'hipaa', 'fda', 'pharma'],
        'ecommerce': ['ecommerce', 'retail', 'shopping', 'marketplace', 'inventory', 'logistics'],
        'saas': ['saas', 'platform', 'subscription', 'tenant', 'multi-tenant', 'api'],
        'gaming': ['game', 'gaming', 'unity', 'unreal', 'mobile game', 'multiplayer'],
        'iot': ['iot', 'sensor', 'embedded', 'device', 'hardware', 'firmware'],
        'ai_ml': ['artificial intelligence', 'machine learning', 'deep learning', 'nlp', 'computer vision']
    }
    
    text_lower = job_description.lower()
    
    for industry, keywords in industry_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            return industry
    
    return None

def get_industry_specific_suggestions(industry: str, profile_skills: List[str]) -> List[MatchSuggestion]:
    """Generate industry-specific suggestions."""
    suggestions = []
    
    industry_requirements = {
        'fintech': {
            'compliance': "Highlight experience with financial regulations (PCI DSS, SOX, etc.)",
            'security': "Emphasize security practices and data protection expertise",
            'scale': "Mention experience with high-volume transaction processing"
        },
        'healthcare': {
            'compliance': "Add HIPAA compliance and healthcare data handling experience",
            'security': "Highlight security certifications and data privacy expertise",
            'integration': "Mention experience with healthcare systems integration"
        },
        'saas': {
            'scalability': "Emphasize experience building scalable, multi-tenant systems",
            'apis': "Highlight API design and integration expertise",
            'monitoring': "Add experience with application monitoring and analytics"
        }
    }
    
    if industry in industry_requirements:
        for key, suggestion_text in industry_requirements[industry].items():
            suggestions.append(MatchSuggestion(
                type="industry_specific",
                suggestion=suggestion_text,
                rationale=f"Industry-specific requirement for {industry} roles",
                priority="medium"
            ))
    
    return suggestions

def generate_suggestions(
    must_have_missing: List[str],
    nice_to_have_missing: List[str],
    profile_skills: List[str],
    job_description: str
) -> List[MatchSuggestion]:
    """Legacy interface for suggestion generation."""
    importance_weights = calculate_skill_importance_weights(
        must_have_missing + nice_to_have_missing, job_description
    )
    
    return generate_suggestions_enhanced(
        must_have_missing=must_have_missing,
        nice_to_have_missing=nice_to_have_missing,
        profile_skills=profile_skills,
        job_description=job_description,
        importance_weights=importance_weights
    )

# Enhanced batch processing for multiple job matches
async def batch_calculate_match_scores(
    profile_data: Dict[str, Any],
    job_listings: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Calculate match scores for multiple jobs efficiently."""
    profile_skills = extract_skills_from_text(profile_data.get('text', ''))
    profile_text = profile_data.get('text', '')
    
    results = []
    
    # Process in batches to avoid memory issues
    batch_size = 10
    for i in 0, len(job_listings), batch_size:
        batch = job_listings[i:i + batch_size]
        batch_results = []
        
        for job in batch:
            must_have, nice_to_have, bonus = extract_job_requirements_enhanced(job['description'])
            
            result = calculate_match_score_enhanced(
                profile_skills=profile_skills,
                profile_text=profile_text,
                must_have_skills=must_have,
                nice_to_have_skills=nice_to_have,
                job_description=job['description'],
                bonus_skills=bonus
            )
            
            result['job_id'] = job['id']
            result['job_title'] = job.get('title', 'Unknown')
            result['company'] = job.get('company', 'Unknown')
            
            batch_results.append(result)
        
        results.extend(batch_results)
        
        # Small delay to prevent overwhelming the system
        await asyncio.sleep(0.01)
    
    return results

# Enhanced reporting with trend analysis
async def get_profile_aggregate_report_enhanced(profile_id: int) -> Dict[str, Any]:
    """Generate comprehensive profile matching report with trends."""
    try:
        # Get all matches for this profile with more detail
        matches_query = """
            SELECT m.*, j.title, j.company, j.job_description, j.created_at as job_posted_at
            FROM matches m 
            JOIN jobs j ON m.job_id = j.id 
            WHERE m.profile_id = :profile_id 
            ORDER BY m.created_at DESC
            LIMIT 100
        """
        matches = await database.fetch_all(query=matches_query, values={"profile_id": profile_id})
        
        if not matches:
            return {
                "profile_id": profile_id,
                "total_jobs_analyzed": 0,
                "average_match_score": 0.0,
                "median_match_score": 0.0,
                "match_distribution": {},
                "top_skills": [],
                "skill_gaps": [],
                "trending_skills": [],
                "recommendations": ["No job matches found. Start by matching your profile against job descriptions."],
                "last_updated": datetime.utcnow()
            }
        
        # Calculate comprehensive statistics
        scores = [match["match_score"] for match in matches]
        avg_score = sum(scores) / len(scores)
        median_score = statistics.median(scores)  # FIXED: correct median calculation
        
        # Match score distribution
        distribution = {
            "excellent": len([s for s in scores if s >= 90]),
            "good": len([s for s in scores if 60 <= s < 90]),  # expanded range
            "fair": 0,
            "poor": len([s for s in scores if s < 60])
        }

        
        # Analyze skill trends over time
        skill_frequency = Counter()
        missing_skills = Counter()
        
        for match in matches:
            reasons = json.loads(match["reasons"])
            for reason in reasons:
                skill = reason["skill"]
                if reason["status"] == "matched":
                    skill_frequency[skill] += 1
                elif reason["status"] == "missing" and reason["category"] == "must_have":
                    missing_skills[skill] += 1
        
        # Top skills (most frequently matched)
        top_skills = [
            {"skill": skill, "match_frequency": count, "match_rate": count / len(matches)}
            for skill, count in skill_frequency.most_common(10)
        ]
        
        # Skill gaps (most frequently missing must-have skills)
        skill_gaps = [
            {
                "skill": skill, 
                "gap_frequency": count, 
                "impact": "critical" if count > len(matches) * 0.7 else "high" if count > len(matches) * 0.4 else "medium",
                "priority": 1 if count > len(matches) * 0.5 else 2 if count > len(matches) * 0.3 else 3
            }
            for skill, count in missing_skills.most_common(10)
        ]
        
        # Trending skills analysis (skills appearing in recent jobs)
        recent_matches = [m for m in matches if (datetime.utcnow() - m["created_at"]).days <= 30]
        if recent_matches:
            recent_skill_mentions = Counter()
            for match in recent_matches:
                job_skills = extract_skills_from_text(match["description"])
                for skill in job_skills:
                    recent_skill_mentions[skill] += 1
            
            trending_skills = [
                {"skill": skill, "trend_score": count / len(recent_matches)}
                for skill, count in recent_skill_mentions.most_common(5)
                if count >= len(recent_matches) * 0.3  # Appears in at least 30% of recent jobs
            ]
        else:
            trending_skills = []
        
        # Generate enhanced recommendations
        recommendations = generate_profile_recommendations(
            avg_score, skill_gaps, trending_skills, top_skills
        )
        
        return {
            "profile_id": profile_id,
            "total_jobs_analyzed": len(matches),
            "average_match_score": round(avg_score, 2),
            "median_match_score": round(median_score, 2),
            "match_distribution": distribution,
            "top_skills": top_skills,
            "skill_gaps": skill_gaps,
            "trending_skills": trending_skills,
            "recommendations": recommendations,
            "match_trend": calculate_match_trend(matches),
            "last_updated": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Error generating enhanced profile report: {e}")
        raise

def generate_profile_recommendations(
    avg_score: float,
    skill_gaps: List[Dict],
    trending_skills: List[Dict],
    top_skills: List[Dict]
) -> List[str]:
    """Generate comprehensive profile recommendations."""
    recommendations = []
    
    # Score-based recommendations
    if avg_score < 50:
        recommendations.append("🚨 Focus on fundamental skill development - consider career pivot or intensive upskilling")
        recommendations.append("📚 Prioritize learning the most in-demand skills in your target roles")
    elif avg_score < 70:
        recommendations.append("📈 Good foundation - focus on closing critical skill gaps")
        recommendations.append("🎯 Target roles that better align with your current skill set")
    elif avg_score < 85:
        recommendations.append("⭐ Strong profile - fine-tune missing skills and showcase achievements")
        recommendations.append("🏆 Consider senior or specialized roles that match your expertise")
    else:
        recommendations.append("🚀 Excellent profile! Focus on leadership skills and cutting-edge technologies")
        recommendations.append("💡 Consider thought leadership through blogging, speaking, or open source contributions")
    
    # Gap-based recommendations
    if skill_gaps:
        critical_gaps = [gap for gap in skill_gaps[:3] if gap["impact"] == "critical"]
        if critical_gaps:
            gap_skills = [gap["skill"] for gap in critical_gaps]
            recommendations.append(f"🔧 Critical: Immediately focus on {', '.join(gap_skills)}")
    
    # Trend-based recommendations
    if trending_skills:
        trending_list = [skill["skill"] for skill in trending_skills[:3]]
        recommendations.append(f"📊 Emerging opportunities: Consider learning {', '.join(trending_list)}")
    
    # Strengths-based recommendations
    if top_skills:
        strength_skills = [skill["skill"] for skill in top_skills[:3]]
        recommendations.append(f"💪 Leverage your strengths in {', '.join(strength_skills)} when applying")
    
    return recommendations

def calculate_match_trend(matches: List[Dict]) -> Dict[str, Any]:
    """Calculate match score trend over time."""
    if len(matches) < 3:
        return {"trend": "insufficient_data", "direction": "neutral", "change": 0.0}
    
    # Sort by creation date
    sorted_matches = sorted(matches, key=lambda x: x["created_at"])
    
    # Calculate trend using simple linear regression on recent matches
    recent_matches = sorted_matches[-10:]  # Last 10 matches
    
    if len(recent_matches) < 3:
        return {"trend": "insufficient_data", "direction": "neutral", "change": 0.0}
    
    # Simple trend calculation
    early_avg = sum(match["match_score"] for match in recent_matches[:len(recent_matches)//2]) / (len(recent_matches)//2)
    late_avg = sum(match["match_score"] for match in recent_matches[len(recent_matches)//2:]) / (len(recent_matches) - len(recent_matches)//2)
    
    change = late_avg - early_avg
    
    if abs(change) < 2:
        direction = "stable"
    elif change > 0:
        direction = "improving"
    else:
        direction = "declining"
    
    return {
        "trend": direction,
        "direction": direction,
        "change": round(change, 2),
        "early_average": round(early_avg, 2),
        "recent_average": round(late_avg, 2)
    }

# Legacy function for backward compatibility
async def get_profile_aggregate_report(profile_id: int) -> Dict[str, Any]:
    """Legacy interface for profile aggregate report."""
    enhanced_report = await get_profile_aggregate_report_enhanced(profile_id)
    
    # Convert to legacy format
    return {
        "profile_id": enhanced_report["profile_id"],
        "total_jobs_analyzed": enhanced_report["total_jobs_analyzed"],
        "average_match_score": enhanced_report["average_match_score"],
        "top_skills": [skill["skill"] for skill in enhanced_report["top_skills"][:5]],
        "common_gaps": [
            {"skill": gap["skill"], "frequency": gap["gap_frequency"], "impact": gap["impact"]}
            for gap in enhanced_report["skill_gaps"][:5]
        ],
        "recommendations": enhanced_report["recommendations"],
        "last_updated": enhanced_report["last_updated"]
    }