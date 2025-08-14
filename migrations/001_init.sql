-- Career Mirror Database Schema
-- Version: 001

-- Enable UUID extension for future use
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Profiles table - stores candidate CV data
CREATE TABLE IF NOT EXISTS profiles (
    id SERIAL PRIMARY KEY,
    cv_text TEXT NOT NULL,
    linkedin_url VARCHAR(255),
    skills JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Jobs table - stores job descriptions and requirements
CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    job_description TEXT NOT NULL,
    title VARCHAR(255),
    company VARCHAR(255),
    must_have_skills JSONB DEFAULT '[]'::jsonb,
    nice_to_have_skills JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Matches table - stores matching results and analysis
CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    match_score DECIMAL(5,2) NOT NULL CHECK (match_score >= 0 AND match_score <= 100),
    reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    suggestions JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(profile_id, job_id)
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_profiles_skills ON profiles USING GIN (skills);
CREATE INDEX IF NOT EXISTS idx_jobs_must_have_skills ON jobs USING GIN (must_have_skills);
CREATE INDEX IF NOT EXISTS idx_jobs_nice_to_have_skills ON jobs USING GIN (nice_to_have_skills);
CREATE INDEX IF NOT EXISTS idx_matches_profile_id ON matches(profile_id);
CREATE INDEX IF NOT EXISTS idx_matches_job_id ON matches(job_id);
CREATE INDEX IF NOT EXISTS idx_matches_score ON matches(match_score);
CREATE INDEX IF NOT EXISTS idx_matches_created_at ON matches(created_at);

-- Add updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE 'plpgsql';

-- Apply updated_at triggers safely
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'update_profiles_updated_at'
    ) THEN
        CREATE TRIGGER update_profiles_updated_at
        BEFORE UPDATE ON profiles
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'update_jobs_updated_at'
    ) THEN
        CREATE TRIGGER update_jobs_updated_at
        BEFORE UPDATE ON jobs
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'update_matches_updated_at'
    ) THEN
        CREATE TRIGGER update_matches_updated_at
        BEFORE UPDATE ON matches
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END;
$$;

-- Insert sample data for testing
INSERT INTO profiles (cv_text, skills) VALUES 
('Senior Python Developer with 5+ years of experience in Django, Flask, PostgreSQL, Redis, and AWS. Strong background in API development, microservices architecture, and agile methodologies. Led teams of 3-5 developers and delivered scalable web applications serving 100K+ users.', 
 '["python", "django", "flask", "postgresql", "redis", "aws", "api development", "microservices", "agile", "team leadership"]'::jsonb)
ON CONFLICT DO NOTHING;

INSERT INTO jobs (job_description, title, company, must_have_skills, nice_to_have_skills) VALUES 
('We are seeking a Senior Backend Engineer with expertise in Python, Django, and PostgreSQL. Must have experience with AWS cloud services, RESTful API design, and agile development. Nice to have: Redis, Docker, Kubernetes, and team leadership experience.',
 'Senior Backend Engineer', 'TechCorp Inc.',
 '["python", "django", "postgresql", "aws", "rest", "agile"]'::jsonb,
 '["redis", "docker", "kubernetes", "team leadership"]'::jsonb)
ON CONFLICT DO NOTHING;
