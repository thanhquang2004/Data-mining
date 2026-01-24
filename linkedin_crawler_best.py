#!/usr/bin/env python3
"""
Best LinkedIn Job Crawler Implementation

A production-ready LinkedIn crawler with:
- FlareSolverr integration for bypassing Cloudflare
- Comprehensive data extraction with all fields
- Robust error handling and retry logic
- Progress tracking and auto-save
- Database integration with upsert logic
- Multi-keyword and multi-location support
- Smart pagination and deduplication

Usage:
    # Basic usage
    python linkedin_crawler_best.py --keywords "software engineer" --max-jobs 100
    
    # Multiple keywords and locations
    python linkedin_crawler_best.py \
        --keywords "python developer,java developer,devops" \
        --locations "San Francisco,New York,London" \
        --max-jobs 1000
    
    # With authentication
    python linkedin_crawler_best.py \
        --keywords "backend engineer" \
        --cookies data/linkedin-cookies.json \
        --max-jobs 500
"""

import argparse
import json
import logging
import os
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# ============================================================================
# CONFIGURATION
# ============================================================================

# FlareSolverr Configuration
FLARESOLVERR_URL = os.getenv("FLARESOLVERR_URL", "http://localhost:8191/v1")
FLARESOLVERR_TIMEOUT = 60000  # 60 seconds

# LinkedIn URLs
LINKEDIN_BASE_URL = "https://www.linkedin.com"
LINKEDIN_JOBS_SEARCH_URL = "https://www.linkedin.com/jobs/search"

# Crawler settings
REQUEST_DELAY_RANGE = (3, 6)  # Random delay between job detail requests (seconds)
PAGE_DELAY_RANGE = (2, 4)     # Delay between search pages (seconds)
KEYWORD_DELAY_RANGE = (5, 10) # Delay between keywords (seconds)
MAX_RETRIES = 3
SAVE_INTERVAL = 50  # Save progress every N jobs
MAX_PAGINATION = 40  # LinkedIn allows ~40 pages (25 jobs per page = 1000)
JOBS_PER_PAGE = 25   # LinkedIn pagination increment

# Database settings (from environment or defaults)
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USER", "crawler_user"),
    "password": os.getenv("MYSQL_PASSWORD", "crawler_pass"),
    "database": os.getenv("MYSQL_DATABASE", "job_crawler"),
    "charset": "utf8mb4"
}

# Output directory
OUTPUT_DIR = Path(__file__).parent / "data" / "raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(OUTPUT_DIR / 'linkedin_crawler.log')
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# FLARESOLVERR CLIENT
# ============================================================================

class FlareSolverrClient:
    """Enhanced FlareSolverr client with session management and retry logic."""
    
    def __init__(self, api_url: str = FLARESOLVERR_URL, timeout: int = FLARESOLVERR_TIMEOUT):
        self.api_url = api_url
        self.timeout = timeout
        self.session_id = None
        self.request_count = 0
        logger.info(f"🔧 FlareSolverr client initialized: {api_url}")
    
    def test_connection(self) -> bool:
        """Test FlareSolverr connection and availability."""
        try:
            response = requests.post(
                self.api_url,
                json={"cmd": "sessions.list"},
                timeout=10
            )
            data = response.json()
            if data.get("status") == "ok":
                logger.info("✓ FlareSolverr is running and accessible")
                return True
            else:
                logger.error(f"FlareSolverr returned error: {data}")
                return False
        except Exception as e:
            logger.error(f"Cannot connect to FlareSolverr at {self.api_url}: {e}")
            logger.error("Make sure FlareSolverr is running: docker ps | grep flaresolverr")
            return False
    
    def create_session(self) -> bool:
        """Create a new FlareSolverr session."""
        try:
            response = requests.post(
                self.api_url,
                json={"cmd": "sessions.create"},
                timeout=30
            )
            data = response.json()
            
            if data.get("status") == "ok":
                self.session_id = data.get("session")
                logger.info(f"✓ Session created: {self.session_id}")
                return True
            else:
                logger.error(f"Failed to create session: {data}")
                return False
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return False
    
    def destroy_session(self):
        """Destroy the FlareSolverr session."""
        if not self.session_id:
            return
        
        try:
            requests.post(
                self.api_url,
                json={"cmd": "sessions.destroy", "session": self.session_id},
                timeout=10
            )
            logger.info(f"✓ Session destroyed: {self.session_id}")
        except Exception as e:
            logger.warning(f"Error destroying session: {e}")
    
    def get(self, url: str, cookies: Optional[List[Dict]] = None, max_retries: int = MAX_RETRIES) -> Optional[Dict]:
        """
        Make a GET request through FlareSolverr with retry logic.
        
        Returns:
            dict with 'html', 'url', 'cookies', 'status' if successful, None otherwise
        """
        if not self.session_id:
            if not self.create_session():
                return None
        
        for attempt in range(max_retries):
            try:
                payload = {
                    "cmd": "request.get",
                    "url": url,
                    "session": self.session_id,
                    "maxTimeout": self.timeout
                }
                
                if cookies:
                    payload["cookies"] = cookies
                
                logger.debug(f"→ Fetching: {url[:80]}... (attempt {attempt + 1}/{max_retries})")
                
                response = requests.post(
                    self.api_url, 
                    json=payload, 
                    timeout=(self.timeout / 1000) + 10
                )
                data = response.json()
                
                if data.get("status") == "ok":
                    solution = data.get("solution", {})
                    html_length = len(solution.get("response", ""))
                    self.request_count += 1
                    
                    logger.debug(f"✓ Response: status={solution.get('status')}, size={html_length} bytes")
                    
                    return {
                        "html": solution.get("response", ""),
                        "url": solution.get("url", url),
                        "cookies": solution.get("cookies", []),
                        "status": solution.get("status", 200)
                    }
                else:
                    error_msg = data.get("message", "Unknown error")
                    logger.warning(f"FlareSolverr error: {error_msg}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}")
            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}/{max_retries}: {e}")
            
            # Exponential backoff
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                logger.info(f"⏳ Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
        
        logger.error(f"❌ Failed to fetch after {max_retries} attempts: {url[:80]}...")
        return None


# ============================================================================
# DATA EXTRACTION FUNCTIONS
# ============================================================================

def extract_skills_from_text(text: str) -> List[str]:
    """Extract programming languages, frameworks, and tools from text."""
    
    # Comprehensive skill patterns
    skill_patterns = [
        # Programming Languages
        r'\b(Python|Java|JavaScript|TypeScript|C\+\+|C#|Ruby|PHP|Go|Rust|Swift|Kotlin|Scala|R|MATLAB|Perl|Dart|Elixir|Haskell)\b',
        
        # Web Frameworks & Libraries
        r'\b(React|Angular|Vue\.?js|Svelte|Next\.?js|Nuxt\.?js|Node\.?js|Express|Django|Flask|FastAPI|Spring|Spring Boot|\.NET|ASP\.NET|Laravel|Rails|Ruby on Rails)\b',
        
        # Cloud & DevOps
        r'\b(AWS|Azure|GCP|Google Cloud|Docker|Kubernetes|K8s|Jenkins|GitLab CI|GitHub Actions|CircleCI|Travis CI|Terraform|Ansible|Chef|Puppet|CI/CD|DevOps)\b',
        
        # Databases
        r'\b(MySQL|PostgreSQL|MongoDB|Redis|Elasticsearch|Cassandra|DynamoDB|Oracle|SQL Server|MariaDB|SQLite|Neo4j|CouchDB|InfluxDB)\b',
        
        # Data & ML
        r'\b(Machine Learning|Deep Learning|AI|Artificial Intelligence|Data Science|Big Data|Hadoop|Spark|Kafka|TensorFlow|PyTorch|Keras|scikit-learn|Pandas|NumPy)\b',
        
        # APIs & Architecture
        r'\b(REST|RESTful|GraphQL|gRPC|SOAP|Microservices|Monolith|Serverless|Lambda|API Gateway|Message Queue|RabbitMQ|Event Driven)\b',
        
        # Development Practices
        r'\b(Agile|Scrum|Kanban|TDD|BDD|Test Driven Development|Continuous Integration|Continuous Deployment|Git|GitHub|GitLab|Bitbucket|JIRA|Confluence)\b',
        
        # Mobile
        r'\b(iOS|Android|React Native|Flutter|Xamarin|Swift UI|Jetpack Compose|Mobile Development)\b',
        
        # Testing
        r'\b(Jest|Mocha|Pytest|JUnit|Selenium|Cypress|Playwright|TestNG|Postman|Unit Testing|Integration Testing)\b',
        
        # Other Tools
        r'\b(Linux|Unix|Bash|Shell|Docker Compose|Nginx|Apache|Redis|Memcached|Celery|Airflow)\b'
    ]
    
    skills = set()
    text_upper = text  # Keep original case for matching
    
    for pattern in skill_patterns:
        matches = re.finditer(pattern, text_upper, re.IGNORECASE)
        for match in matches:
            skill = match.group(0).strip()
            # Normalize common variations
            skill_normalized = skill.replace('Node.js', 'Node.js').replace('Vue.js', 'Vue.js').replace('Next.js', 'Next.js')
            skills.add(skill_normalized)
    
    return sorted(list(skills))


def extract_salary_info(text: str) -> Dict[str, Any]:
    """Extract comprehensive salary information from text."""
    result = {
        "salary_min": None,
        "salary_max": None,
        "salary_currency": "USD",
        "salary_text": None
    }
    
    # Enhanced salary patterns
    patterns = [
        # $100,000 - $150,000 per year
        r'\$\s?([\d,]+)k?\s*[-–to]+\s*\$\s?([\d,]+)k?\s*(?:per|/|a)?\s*(?:year|yr|annum|annually)?',
        
        # 100k-150k USD
        r'([\d,]+)k?\s*[-–to]+\s*([\d,]+)k?\s*(USD|EUR|GBP|CAD|AUD|SGD)?',
        
        # $80-100K
        r'\$\s?([\d,]+)\s*[-–]\s*([\d,]+)K',
        
        # 50000-70000 EUR
        r'([\d,]+)\s*(USD|EUR|GBP|CAD|AUD|SGD)\s*[-–to]+\s*([\d,]+)',
        
        # Salary: $120,000
        r'salary[:\s]+\$?\s?([\d,]+)k?',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                groups = match.groups()
                
                # Extract min and max
                if len(groups) >= 2 and groups[0] and groups[1]:
                    salary_min = int(groups[0].replace(',', '').replace('k', '').replace('K', ''))
                    salary_max = int(groups[1].replace(',', '').replace('k', '').replace('K', ''))
                    
                    # Handle 'k' notation (e.g., 100k = 100000)
                    match_text = match.group(0).lower()
                    if 'k' in match_text and salary_min < 1000:
                        salary_min *= 1000
                        salary_max *= 1000
                    
                    result["salary_min"] = salary_min
                    result["salary_max"] = salary_max
                    
                    # Extract currency
                    currency_match = re.search(r'\b(USD|EUR|GBP|CAD|AUD|SGD|INR|CNY)\b', match.group(0), re.IGNORECASE)
                    if currency_match:
                        result["salary_currency"] = currency_match.group(1).upper()
                    
                    result["salary_text"] = match.group(0).strip()
                    break
                    
            except (ValueError, IndexError, AttributeError) as e:
                logger.debug(f"Error parsing salary: {e}")
                continue
    
    return result


def extract_experience_years(text: str) -> Tuple[Optional[int], Optional[int]]:
    """Extract years of experience required from text."""
    years_min, years_max = None, None
    
    patterns = [
        # 3+ years, 5+ years of experience
        r'(\d+)\+\s*(?:years?|yrs?)(?:\s+of\s+(?:experience|exp))?',
        
        # 3-5 years, 2 to 4 years
        r'(\d+)\s*[-–to]+\s*(\d+)\s*(?:years?|yrs?)',
        
        # minimum 3 years, at least 5 years
        r'(?:minimum|min|at least)\s+(\d+)\s*(?:years?|yrs?)',
        
        # 3 years experience required
        r'(\d+)\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp)(?:\s+required)?',
        
        # experience: 3-5 years
        r'experience[:\s]+(\d+)\s*[-–to]+\s*(\d+)\s*(?:years?|yrs?)?',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                groups = match.groups()
                if len(groups) == 1 or groups[1] is None:
                    # Single number (e.g., "3+ years")
                    years_min = int(groups[0])
                    years_max = None
                else:
                    # Range (e.g., "3-5 years")
                    years_min = int(groups[0])
                    years_max = int(groups[1])
                break
            except (ValueError, IndexError) as e:
                logger.debug(f"Error parsing experience: {e}")
                continue
    
    return years_min, years_max


def extract_section_text(soup: BeautifulSoup, section_keywords: List[str]) -> Optional[str]:
    """Extract text from a section based on header keywords."""
    
    for keyword in section_keywords:
        # Find headers containing the keyword
        headers = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'strong', 'b', 'div'])
        
        for header in headers:
            header_text = header.get_text(strip=True).lower()
            
            if keyword.lower() in header_text:
                # Get the parent container
                section = header.find_parent(['div', 'section', 'article'])
                
                if section:
                    # Extract text from this section
                    text_parts = []
                    
                    # Get all text elements
                    for elem in section.find_all(['p', 'li', 'span', 'div']):
                        text = elem.get_text(strip=True)
                        # Filter out short/meaningless text
                        if text and len(text) > 15 and text not in text_parts:
                            text_parts.append(text)
                    
                    if text_parts:
                        return '\n'.join(text_parts)
                
                # If no parent section, try getting siblings
                text_parts = []
                for sibling in header.find_next_siblings():
                    text = sibling.get_text(strip=True)
                    if text and len(text) > 15:
                        text_parts.append(text)
                    # Stop at next header
                    if sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5']:
                        break
                
                if text_parts:
                    return '\n'.join(text_parts)
    
    return None


def parse_linkedin_job(html: str, url: str) -> Dict[str, Any]:
    """
    Extract comprehensive job information from LinkedIn job detail page.
    
    Returns:
        Dictionary with all job fields mapped to database schema
    """
    
    soup = BeautifulSoup(html, 'html.parser')
    
    job_data = {
        'source': 'linkedin',
        'source_url': url.split('?')[0],  # Remove query params for clean URL
        'crawled_at': datetime.now().isoformat(),
        'is_active': True
    }
    
    # ========================================================================
    # BASIC INFORMATION
    # ========================================================================
    
    # Extract Job Title
    title_selectors = [
        'h1.jobs-unified-top-card__job-title',
        'h1.job-details-jobs-unified-top-card__job-title',
        'h1.topcard__title',
        '.job-details-jobs-unified-top-card__job-title h1',
        'h1[class*="job-title"]',
    ]
    for selector in title_selectors:
        elem = soup.select_one(selector)
        if elem:
            job_data['title'] = elem.get_text(strip=True)
            break
    
    # Extract Company Name
    company_selectors = [
        '.jobs-unified-top-card__company-name a',
        'a.ember-view.job-details-jobs-unified-top-card__company-name',
        '.job-details-jobs-unified-top-card__company-name a',
        '.topcard__org-name-link',
        '.topcard__flavor--black-link',
        'a[data-tracking-control-name="public_jobs_topcard-org-name"]',
    ]
    for selector in company_selectors:
        elem = soup.select_one(selector)
        if elem:
            job_data['company_name'] = elem.get_text(strip=True)
            break
    
    # Extract Location
    location_selectors = [
        'span.jobs-unified-top-card__bullet',
        'span.jobs-unified-top-card__workplace-type',
        '.job-details-jobs-unified-top-card__bullet',
        '.topcard__flavor--bullet',
        'span[class*="workplace-type"]',
    ]
    for selector in location_selectors:
        elem = soup.select_one(selector)
        if elem:
            location_text = elem.get_text(strip=True)
            # Filter out non-location text (like "Posted X ago")
            if location_text and len(location_text) > 3 and not any(
                word in location_text.lower() for word in ['ago', 'posted', 'applicant', 'reposted']
            ):
                job_data['location'] = location_text
                break
    
    # ========================================================================
    # JOB DESCRIPTION
    # ========================================================================
    
    # Extract Full Description
    desc_selectors = [
        '.jobs-description__content',
        'div.jobs-description-content__text',
        '.show-more-less-html__markup',
        'div.jobs-description',
        '.description__text',
        'article.jobs-description',
    ]
    description = ""
    for selector in desc_selectors:
        elem = soup.select_one(selector)
        if elem:
            description = elem.get_text(separator='\n', strip=True)
            job_data['description'] = description
            break
    
    # ========================================================================
    # STRUCTURED JOB CRITERIA
    # ========================================================================
    
    # Extract criteria from LinkedIn's structured sections
    criteria_items = soup.select('.jobs-unified-top-card__job-insight, .description__job-criteria-item, li.description__job-criteria-item')
    
    for criteria in criteria_items:
        text = criteria.get_text(strip=True)
        text_lower = text.lower()
        
        # Job Type
        if any(keyword in text for keyword in ['Full-time', 'Part-time', 'Contract', 'Temporary', 'Internship', 'Freelance', 'Volunteer']):
            if not job_data.get('job_type'):
                job_data['job_type'] = text.split('\n')[0] if '\n' in text else text
        
        # Seniority Level
        elif any(keyword in text for keyword in ['Entry level', 'Mid-Senior', 'Director', 'Executive', 'Internship', 'Associate', 'Senior', 'Lead', 'Principal']):
            if not job_data.get('level'):
                job_data['level'] = text.split('\n')[0] if '\n' in text else text
        
        # Industry
        elif 'industries' in text_lower or 'industry' in text_lower:
            if not job_data.get('industry'):
                industry_text = text.split('\n')[-1] if '\n' in text else text
                if len(industry_text) > 50:
                    industry_text = text.split('\n')[1] if '\n' in text else text
                job_data['industry'] = industry_text
    
    # ========================================================================
    # COMPANY RATING
    # ========================================================================
    
    rating_selectors = [
        '.jobs-unified-top-card__company-rating',
        '[data-test-app-aware-link] .artdeco-entity-lockup__subtitle',
        'span[class*="rating"]',
    ]
    for selector in rating_selectors:
        rating_elem = soup.select_one(selector)
        if rating_elem:
            rating_text = rating_elem.get_text()
            rating_match = re.search(r'(\d+\.?\d*)\s*(?:stars?|★|rating)', rating_text, re.IGNORECASE)
            if rating_match:
                try:
                    job_data['company_rating'] = float(rating_match.group(1))
                    break
                except ValueError:
                    pass
    
    # ========================================================================
    # REQUIREMENTS & QUALIFICATIONS
    # ========================================================================
    
    requirements_keywords = [
        'requirements', 'qualifications', 'what you need', "what you'll need",
        'required qualifications', 'minimum qualifications', 'basic qualifications',
        'you should have', 'you must have', "what we're looking for",
        'required skills', 'required experience', 'must have'
    ]
    
    requirements_text = extract_section_text(soup, requirements_keywords)
    
    # Fallback: extract from description using regex
    if not requirements_text and description:
        req_patterns = [
            r'(?:Requirements|Qualifications|What [Yy]ou [Nn]eed|What [Yy]ou\'ll [Nn]eed)[:\n]([\s\S]{100,5000}?)(?:Benefits|Responsibilities|What [Ww]e [Oo]ffer|About|Company|Apply|$)',
            r'(?:Required|Minimum)[:\s]+([\s\S]{100,3000}?)(?:Preferred|Benefits|Responsibilities|$)',
            r'(?:Must [Hh]ave|Required [Ss]kills)[:\n]([\s\S]{100,2000}?)(?:Nice to [Hh]ave|Benefits|$)',
        ]
        for pattern in req_patterns:
            match = re.search(pattern, description, re.IGNORECASE | re.DOTALL)
            if match:
                requirements_text = match.group(1).strip()
                break
    
    # LinkedIn often doesn't separate sections clearly, use full description as fallback
    if not requirements_text and len(description) > 200:
        requirements_text = description
    
    if requirements_text:
        job_data['requirements_text'] = requirements_text[:10000]  # Limit length
    
    # ========================================================================
    # BENEFITS & PERKS
    # ========================================================================
    
    benefits_keywords = [
        'benefits', 'perks', 'what we offer', 'why join us', 'why work with us',
        "what you'll get", 'compensation and benefits', 'our benefits',
        'employee benefits', 'perks and benefits'
    ]
    
    benefits_text = extract_section_text(soup, benefits_keywords)
    benefits_list = []
    
    if benefits_text:
        # Parse benefits from structured text
        benefit_lines = [
            line.strip().lstrip('-•*·➤►▪').strip() 
            for line in benefits_text.split('\n') 
            if line.strip() and len(line.strip()) > 10
        ]
        benefits_list.extend(benefit_lines[:20])
    
    # Search for common benefits in description
    benefit_keywords = [
        'health insurance', 'medical insurance', 'dental insurance', 'vision insurance',
        'life insurance', '401k', '401(k)', 'retirement plan', 'pension',
        'pto', 'paid time off', 'vacation days', 'sick leave', 'paid leave',
        'stock options', 'equity', 'rsu', 'stock grants', 'espp',
        'bonus', 'performance bonus', 'signing bonus', 'annual bonus',
        'flexible hours', 'flexible schedule', 'work from home', 'remote work',
        'gym membership', 'wellness program', 'fitness', 'mental health',
        'learning budget', 'professional development', 'tuition reimbursement',
        'parental leave', 'maternity leave', 'paternity leave',
        'commuter benefits', 'transportation', 'parking',
        'meal allowance', 'free lunch', 'snacks', 'catered meals'
    ]
    
    desc_lower = description.lower()
    found_benefits = [kw.title() for kw in benefit_keywords if kw in desc_lower]
    
    # Combine and deduplicate
    all_benefits = list(set(benefits_list + found_benefits))
    if all_benefits:
        job_data['benefits'] = json.dumps(all_benefits[:25])  # Max 25 benefits
    
    # ========================================================================
    # EDUCATION REQUIREMENTS
    # ========================================================================
    
    education_patterns = [
        r"(?:bachelor'?s?|b\.?s\.?|b\.?a\.?)\s+degree",
        r"(?:master'?s?|m\.?s\.?|m\.?a\.?|mba)\s+degree",
        r"(?:phd|ph\.d\.|doctorate|doctoral)\s+(?:degree)?",
        r"associate'?s?\s+degree",
        r"high school diploma|ged",
    ]
    
    for pattern in education_patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            edu_text = match.group(0).lower()
            if 'master' in edu_text or 'm.s' in edu_text or 'mba' in edu_text:
                job_data['education_level'] = "Master's Degree"
            elif 'phd' in edu_text or 'ph.d' in edu_text or 'doctorate' in edu_text:
                job_data['education_level'] = "PhD"
            elif 'bachelor' in edu_text or 'b.s' in edu_text or 'b.a' in edu_text:
                job_data['education_level'] = "Bachelor's Degree"
            elif 'associate' in edu_text:
                job_data['education_level'] = "Associate's Degree"
            elif 'high school' in edu_text or 'ged' in edu_text:
                job_data['education_level'] = "High School"
            break
    
    # ========================================================================
    # CERTIFICATIONS
    # ========================================================================
    
    cert_patterns = [
        r'\b([A-Z]{2,10})\s+(?:certified|certification)\b',
        r'\bcertification[s]?\s+(?:in|for)?\s+([A-Z][A-Za-z\s]{3,40})',
        r'\b(AWS|Azure|GCP|PMP|CISSP|CCNA|CCNP|CKA|CKAD|CFA|CPA|CEH|CISM|CompTIA|ITIL)\s+(?:certification|certified)?',
        r'certified\s+([A-Za-z\s]{3,40}?)\s*(?:professional|specialist|expert|engineer|developer)',
    ]
    
    certifications = set()
    for pattern in cert_patterns:
        matches = re.finditer(pattern, description, re.IGNORECASE)
        for match in matches:
            cert = match.group(1).strip() if match.lastindex >= 1 else match.group(0).strip()
            # Filter out noise
            if 2 < len(cert) < 60 and not any(word in cert.lower() for word in ['required', 'preferred', 'degree', 'diploma']):
                certifications.add(cert)
    
    if certifications:
        job_data['certifications'] = json.dumps(list(certifications)[:15])
    
    # ========================================================================
    # SKILLS EXTRACTION
    # ========================================================================
    
    # Extract from description + requirements
    full_text = description + "\n" + (requirements_text or "")
    skills = extract_skills_from_text(full_text)
    
    if skills:
        # Split into required and preferred (first 15 as required, rest as preferred)
        job_data['required_skills'] = json.dumps(skills[:20])
        if len(skills) > 20:
            job_data['preferred_skills'] = json.dumps(skills[20:35])
    
    # ========================================================================
    # EXPERIENCE REQUIREMENTS
    # ========================================================================
    
    if not job_data.get('experience_years_min'):
        exp_min, exp_max = extract_experience_years(full_text)
        if exp_min is not None:
            job_data['experience_years_min'] = exp_min
        if exp_max is not None:
            job_data['experience_years_max'] = exp_max
    
    # ========================================================================
    # SALARY INFORMATION
    # ========================================================================
    
    salary_info = extract_salary_info(full_text)
    job_data.update(salary_info)
    
    # ========================================================================
    # JOB TYPE & LEVEL (from description if not in criteria)
    # ========================================================================
    
    # Job Type
    if not job_data.get('job_type'):
        job_type_patterns = [
            r'(?:position|role|employment|job)\s+type[:\s]+([\w\s-]+?)(?:\.|,|\n|$)',
            r'(?:this is a|seeking a|looking for a)\s+(full[\s-]?time|part[\s-]?time|contract|temporary|internship|freelance)',
            r'(full[\s-]?time|part[\s-]?time|contract|temporary|internship)\s+(?:position|role|employment|opportunity)',
        ]
        for pattern in job_type_patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                job_type = match.group(1).strip().title()
                # Normalize
                if 'full' in job_type.lower():
                    job_data['job_type'] = 'Full-time'
                elif 'part' in job_type.lower():
                    job_data['job_type'] = 'Part-time'
                elif 'contract' in job_type.lower():
                    job_data['job_type'] = 'Contract'
                elif 'intern' in job_type.lower():
                    job_data['job_type'] = 'Internship'
                elif 'temp' in job_type.lower():
                    job_data['job_type'] = 'Temporary'
                elif 'freelance' in job_type.lower():
                    job_data['job_type'] = 'Freelance'
                break
    
    # Seniority Level
    if not job_data.get('level'):
        level_patterns = [
            r'(?:seniority|experience)\s+level[:\s]+([\w\s-]+?)(?:\.|,|\n|$)',
            r'(?:seeking|looking for|hiring)\s+(?:a|an)?\s*(senior|junior|mid[\s-]?level|entry[\s-]?level|lead|principal|staff|architect)\s+',
            r'(senior|junior|mid[\s-]?level|entry[\s-]?level|lead|principal|staff|architect)\s+(?:software|developer|engineer|position)',
        ]
        for pattern in level_patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                level = match.group(1).strip().lower()
                # Normalize
                if 'senior' in level or 'sr' in level:
                    job_data['level'] = 'Senior level'
                elif 'junior' in level or 'jr' in level:
                    job_data['level'] = 'Junior level'
                elif 'mid' in level:
                    job_data['level'] = 'Mid-Senior level'
                elif 'entry' in level:
                    job_data['level'] = 'Entry level'
                elif 'lead' in level:
                    job_data['level'] = 'Lead'
                elif 'principal' in level:
                    job_data['level'] = 'Principal'
                elif 'staff' in level:
                    job_data['level'] = 'Staff'
                elif 'architect' in level:
                    job_data['level'] = 'Architect'
                break
    
    # ========================================================================
    # REMOTE/HYBRID/ONSITE
    # ========================================================================
    
    remote_keywords = [
        'remote', 'work from home', 'wfh', 'telecommute', 'work remotely',
        'remote work', '100% remote', 'fully remote', 'remote first',
        'distributed team', 'work from anywhere'
    ]
    hybrid_keywords = [
        'hybrid', 'flexible work', 'remote/office', 'office/remote',
        'mix of remote', 'partially remote', 'flexible location'
    ]
    
    location_text = job_data.get('location', '').lower()
    desc_lower = description.lower()
    
    # Check for explicit remote indicators
    if any(keyword in desc_lower or keyword in location_text for keyword in remote_keywords):
        job_data['is_remote'] = True
    elif any(keyword in desc_lower or keyword in location_text for keyword in hybrid_keywords):
        job_data['is_remote'] = False  # Hybrid is not fully remote
    else:
        job_data['is_remote'] = False
    
    return job_data


# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

def create_database_engine():
    """Create SQLAlchemy engine with proper configuration."""
    try:
        database_url = (
            f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
            f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
            f"?charset={DB_CONFIG['charset']}"
        )
        
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=5,
            max_overflow=10,
            echo=False
        )
        
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        logger.info(f"✓ Database connected: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
        return engine
    
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        logger.warning("Continuing without database (will save to JSON only)")
        return None


def upsert_jobs_to_database(jobs: List[Dict[str, Any]], engine) -> Tuple[int, int, int]:
    """
    Upsert jobs to database using efficient batch operations.
    
    Returns:
        Tuple of (inserted, updated, failed) counts
    """
    if engine is None:
        return 0, 0, len(jobs)
    
    inserted = 0
    updated = 0
    failed = 0
    
    try:
        with engine.begin() as conn:  # Auto-commit transaction
            for job_data in jobs:
                try:
                    # Check if job exists by source_url
                    check_query = text("SELECT id, updated_at FROM jobs WHERE source_url = :url LIMIT 1")
                    result = conn.execute(check_query, {"url": job_data['source_url']})
                    existing = result.fetchone()
                    
                    if existing:
                        # Update existing job
                        job_id = existing[0]
                        
                        # Build dynamic update query
                        update_fields = []
                        params = {"job_id": job_id}
                        
                        for key, value in job_data.items():
                            if key not in ['source_url', 'created_at']:  # Don't update these
                                update_fields.append(f"{key} = :{key}")
                                params[key] = value
                        
                        if update_fields:
                            update_query = text(
                                f"UPDATE jobs SET {', '.join(update_fields)}, updated_at = NOW() WHERE id = :job_id"
                            )
                            conn.execute(update_query, params)
                            updated += 1
                        
                    else:
                        # Insert new job
                        columns = list(job_data.keys())
                        placeholders = [f":{col}" for col in columns]
                        
                        insert_query = text(
                            f"INSERT INTO jobs ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                        )
                        conn.execute(insert_query, job_data)
                        inserted += 1
                
                except Exception as e:
                    failed += 1
                    logger.debug(f"Error upserting job {job_data.get('source_url', 'unknown')}: {e}")
    
    except Exception as e:
        logger.error(f"❌ Database transaction error: {e}")
        failed = len(jobs)
    
    if inserted > 0 or updated > 0:
        logger.info(f"💾 Database: ✓ {inserted} inserted, 🔄 {updated} updated, ❌ {failed} failed")
    
    return inserted, updated, failed


# ============================================================================
# MAIN CRAWLER
# ============================================================================

def crawl_linkedin_jobs(
    keywords: List[str],
    locations: List[str] = ["Worldwide"],
    max_jobs: int = 100,
    cookies_path: Optional[str] = None,
    save_to_db: bool = True,
    flaresolverr_url: str = FLARESOLVERR_URL
) -> List[Dict[str, Any]]:
    """
    Main LinkedIn job crawler with multi-keyword and multi-location support.
    
    Args:
        keywords: List of job search keywords
        locations: List of locations to search
        max_jobs: Maximum number of jobs to crawl
        cookies_path: Path to LinkedIn cookies JSON file (optional)
        save_to_db: Whether to save results to database
        flaresolverr_url: FlareSolverr API URL
    
    Returns:
        List of extracted job dictionaries
    """
    
    logger.info("=" * 80)
    logger.info("🚀 LINKEDIN JOB CRAWLER - BEST VERSION")
    logger.info("=" * 80)
    logger.info(f"📋 Keywords: {', '.join(keywords)}")
    logger.info(f"📍 Locations: {', '.join(locations)}")
    logger.info(f"🎯 Target jobs: {max_jobs}")
    logger.info(f"💾 Save to DB: {save_to_db}")
    logger.info("=" * 80)
    
    # Initialize FlareSolverr client
    flare = FlareSolverrClient(api_url=flaresolverr_url)
    
    # Test connection first
    if not flare.test_connection():
        logger.error("❌ FlareSolverr is not accessible. Please start it:")
        logger.error("   docker run -d --name flaresolverr -p 8191:8191 flaresolverr/flaresolverr:latest")
        return []
    
    if not flare.create_session():
        logger.error("❌ Failed to create FlareSolverr session")
        return []
    
    # Load cookies if provided
    cookies = []
    if cookies_path:
        cookie_file = Path(cookies_path)
        if cookie_file.exists():
            try:
                with open(cookie_file, 'r') as f:
                    cookies = json.load(f)
                logger.info(f"✓ Loaded {len(cookies)} cookies from {cookie_file.name}")
            except Exception as e:
                logger.warning(f"Failed to load cookies: {e}")
        else:
            logger.warning(f"Cookie file not found: {cookies_path}")
    
    # Initialize database
    engine = None
    if save_to_db:
        engine = create_database_engine()
    
    # Storage
    all_jobs = []
    seen_urls = set()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Statistics
    stats = {
        'total_searches': 0,
        'total_pages': 0,
        'jobs_found': 0,
        'jobs_parsed': 0,
        'jobs_failed': 0,
    }
    
    try:
        # Iterate over all keyword × location combinations
        total_combinations = len(keywords) * len(locations)
        current_combination = 0
        
        for location in locations:
            for keyword in keywords:
                current_combination += 1
                
                # Stop if we've reached the target
                if len(all_jobs) >= max_jobs:
                    logger.info(f"🎯 Target reached: {len(all_jobs)}/{max_jobs} jobs")
                    break
                
                logger.info(f"\n{'='*80}")
                logger.info(f"🔍 Search {current_combination}/{total_combinations}: '{keyword}' in '{location}'")
                logger.info(f"{'='*80}")
                
                stats['total_searches'] += 1
                
                # Build search URL
                # Rotate through different time filters for diversity
                time_filters = ['r86400', 'r604800', 'r2592000', '']  # 1 day, 1 week, 1 month, all
                time_filter = time_filters[current_combination % len(time_filters)]
                
                params = {
                    'keywords': keyword,
                    'location': location,
                }
                
                if time_filter:
                    params['f_TPR'] = time_filter
                
                # Add full-time filter (optional, comment out for all types)
                # params['f_JT'] = 'F'
                
                # Calculate jobs needed from this search
                jobs_per_search = max((max_jobs - len(all_jobs)) // (total_combinations - current_combination + 1), 10)
                
                # Pagination
                start_offset = 0
                jobs_from_search = 0
                consecutive_empty = 0
                max_pages_per_search = min(10, (jobs_per_search // 7) + 2)  # ~7 jobs per page
                
                while jobs_from_search < jobs_per_search and len(all_jobs) < max_jobs:
                    params['start'] = start_offset
                    search_url = f"{LINKEDIN_JOBS_SEARCH_URL}?{urlencode(params)}"
                    
                    page_num = (start_offset // JOBS_PER_PAGE) + 1
                    
                    # Stop if too many pages
                    if page_num > max_pages_per_search:
                        logger.info(f"⏭️  Reached page limit ({max_pages_per_search}) for this search")
                        break
                    
                    logger.info(f"\n📄 Page {page_num} (offset={start_offset})")
                    stats['total_pages'] += 1
                    
                    # Fetch search results
                    response = flare.get(search_url, cookies=cookies if cookies else None)
                    if not response:
                        logger.warning("⚠️  Failed to fetch search page, moving to next search")
                        break
                    
                    # Parse job cards
                    soup = BeautifulSoup(response['html'], 'html.parser')
                    
                    # LinkedIn job card selectors (they change frequently)
                    job_cards = soup.select(
                        '.base-card, .base-search-card, .job-search-card, '
                        '[data-entity-urn*="jobPosting"], li.jobs-search-results__list-item'
                    )
                    
                    if not job_cards:
                        logger.info("ℹ️  No job cards found on this page")
                        consecutive_empty += 1
                        if consecutive_empty >= 3:
                            logger.info("⏭️  No jobs found in 3 consecutive pages, moving to next search")
                            break
                        
                        # Try next page anyway (sometimes pagination is off)
                        start_offset += JOBS_PER_PAGE
                        time.sleep(random.uniform(*PAGE_DELAY_RANGE))
                        continue
                    
                    consecutive_empty = 0
                    logger.info(f"✓ Found {len(job_cards)} job cards")
                    
                    # Extract job URLs
                    job_urls = []
                    for card in job_cards:
                        # Multiple selector strategies
                        link = card.select_one(
                            'a[href*="/jobs/view/"], '
                            'a.base-card__full-link, '
                            'a[data-tracking-control-name*="public_jobs"]'
                        )
                        
                        if link:
                            job_url = link.get('href', '')
                            if not job_url.startswith('http'):
                                job_url = LINKEDIN_BASE_URL + job_url
                            
                            # Clean URL
                            job_url = job_url.split('?')[0]
                            
                            if job_url and job_url not in seen_urls:
                                job_urls.append(job_url)
                                seen_urls.add(job_url)
                    
                    new_jobs = len(job_urls)
                    stats['jobs_found'] += new_jobs
                    logger.info(f"📝 Processing {new_jobs} new jobs from this page")
                    
                    if new_jobs == 0:
                        consecutive_empty += 1
                        if consecutive_empty >= 3:
                            break
                    
                    # Fetch and parse each job
                    for idx, job_url in enumerate(job_urls, 1):
                        if len(all_jobs) >= max_jobs:
                            logger.info(f"🎯 Reached max jobs limit: {max_jobs}")
                            break
                        
                        logger.info(f"  [{idx}/{len(job_urls)}] {job_url[:70]}...")
                        
                        # Fetch job detail page
                        job_response = flare.get(job_url, cookies=cookies if cookies else None)
                        
                        if not job_response:
                            logger.warning(f"  ❌ Failed to fetch job")
                            stats['jobs_failed'] += 1
                            continue
                        
                        # Parse job data
                        try:
                            job_data = parse_linkedin_job(job_response['html'], job_url)
                            
                            # Validate essential fields
                            if not job_data.get('title'):
                                logger.warning(f"  ⚠️  No title found, skipping")
                                stats['jobs_failed'] += 1
                                continue
                            
                            all_jobs.append(job_data)
                            jobs_from_search += 1
                            stats['jobs_parsed'] += 1
                            
                            # Log job info
                            title = job_data.get('title', 'N/A')[:50]
                            company = job_data.get('company_name', 'N/A')[:30]
                            logger.info(f"  ✓ {title} @ {company}")
                            logger.info(f"    Progress: {len(all_jobs)}/{max_jobs}")
                            
                            # Auto-save progress
                            if len(all_jobs) % SAVE_INTERVAL == 0:
                                save_progress(all_jobs, timestamp)
                                if engine:
                                    batch = all_jobs[-SAVE_INTERVAL:]
                                    upsert_jobs_to_database(batch, engine)
                            
                        except Exception as e:
                            logger.error(f"  ❌ Error parsing job: {e}")
                            stats['jobs_failed'] += 1
                        
                        # Delay between jobs
                        time.sleep(random.uniform(*REQUEST_DELAY_RANGE))
                    
                    # Move to next page
                    start_offset += JOBS_PER_PAGE
                    
                    # Delay between pages
                    time.sleep(random.uniform(*PAGE_DELAY_RANGE))
                
                logger.info(f"✓ Search complete: {jobs_from_search} jobs extracted")
                
                # Delay between keywords
                if current_combination < total_combinations:
                    delay = random.uniform(*KEYWORD_DELAY_RANGE)
                    logger.info(f"⏳ Waiting {delay:.1f}s before next search...")
                    time.sleep(delay)
            
            # Stop if target reached
            if len(all_jobs) >= max_jobs:
                break
    
    except KeyboardInterrupt:
        logger.info("\n⚠️  Crawl interrupted by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"\n❌ Fatal error: {e}", exc_info=True)
    finally:
        # Cleanup
        flare.destroy_session()
    
    # ========================================================================
    # FINAL RESULTS
    # ========================================================================
    
    logger.info(f"\n{'='*80}")
    logger.info("🏁 CRAWL COMPLETE")
    logger.info(f"{'='*80}")
    logger.info(f"📊 Statistics:")
    logger.info(f"   Total searches: {stats['total_searches']}")
    logger.info(f"   Total pages crawled: {stats['total_pages']}")
    logger.info(f"   Jobs found: {stats['jobs_found']}")
    logger.info(f"   Jobs successfully parsed: {stats['jobs_parsed']}")
    logger.info(f"   Jobs failed: {stats['jobs_failed']}")
    logger.info(f"   FlareSolverr requests: {flare.request_count}")
    logger.info(f"{'='*80}")
    
    if all_jobs:
        # Save final results
        save_final(all_jobs, timestamp)
        
        # Save to database
        if engine:
            logger.info("💾 Saving all jobs to database...")
            upsert_jobs_to_database(all_jobs, engine)
        
        # Print summary statistics
        print_summary(all_jobs)
    else:
        logger.warning("⚠️  No jobs were extracted")
    
    return all_jobs


def save_progress(jobs: List[Dict], timestamp: str):
    """Save progress to JSON file."""
    progress_file = OUTPUT_DIR / f"linkedin_jobs_progress_{timestamp}.json"
    try:
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Progress saved: {len(jobs)} jobs → {progress_file.name}")
    except Exception as e:
        logger.error(f"Failed to save progress: {e}")


def save_final(jobs: List[Dict], timestamp: str):
    """Save final results to JSON file."""
    final_file = OUTPUT_DIR / f"linkedin_jobs_complete_{timestamp}.json"
    try:
        with open(final_file, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Final results saved:")
        logger.info(f"   📁 {final_file.name}")
        logger.info(f"   📂 {final_file.parent.absolute()}")
        logger.info(f"   📊 {len(jobs)} jobs, {final_file.stat().st_size / 1024:.1f} KB")
    except Exception as e:
        logger.error(f"Failed to save final data: {e}")


def print_summary(jobs: List[Dict]):
    """Print summary statistics about collected jobs."""
    logger.info(f"\n{'='*80}")
    logger.info("📈 JOB COLLECTION SUMMARY")
    logger.info(f"{'='*80}")
    
    # Total
    logger.info(f"Total jobs: {len(jobs)}")
    
    # By company
    companies = [j.get('company_name') for j in jobs if j.get('company_name')]
    if companies:
        top_companies = Counter(companies).most_common(5)
        logger.info(f"\nTop 5 companies:")
        for company, count in top_companies:
            logger.info(f"  • {company}: {count} jobs")
    
    # By location
    locations = [j.get('location') for j in jobs if j.get('location')]
    if locations:
        top_locations = Counter(locations).most_common(5)
        logger.info(f"\nTop 5 locations:")
        for location, count in top_locations:
            logger.info(f"  • {location}: {count} jobs")
    
    # By job type
    job_types = [j.get('job_type') for j in jobs if j.get('job_type')]
    if job_types:
        logger.info(f"\nJob types:")
        for jtype, count in Counter(job_types).most_common():
            logger.info(f"  • {jtype}: {count} jobs")
    
    # By level
    levels = [j.get('level') for j in jobs if j.get('level')]
    if levels:
        logger.info(f"\nSeniority levels:")
        for level, count in Counter(levels).most_common():
            logger.info(f"  • {level}: {count} jobs")
    
    # Remote stats
    remote_count = sum(1 for j in jobs if j.get('is_remote'))
    logger.info(f"\nRemote jobs: {remote_count} ({remote_count/len(jobs)*100:.1f}%)")
    
    # Salary info
    with_salary = sum(1 for j in jobs if j.get('salary_min'))
    logger.info(f"Jobs with salary: {with_salary} ({with_salary/len(jobs)*100:.1f}%)")
    
    logger.info(f"{'='*80}\n")


# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Best LinkedIn Job Crawler with FlareSolverr",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage - single keyword
  python linkedin_crawler_best.py --keywords "software engineer" --max-jobs 100
  
  # Multiple keywords (comma-separated)
  python linkedin_crawler_best.py \\
      --keywords "python developer,java developer,devops engineer" \\
      --max-jobs 500
  
  # Multiple locations
  python linkedin_crawler_best.py \\
      --keywords "data scientist" \\
      --locations "San Francisco,New York,London,Singapore" \\
      --max-jobs 1000
  
  # With authentication cookies
  python linkedin_crawler_best.py \\
      --keywords "backend engineer" \\
      --cookies data/linkedin-cookies.json \\
      --max-jobs 300
  
  # JSON output only (skip database)
  python linkedin_crawler_best.py \\
      --keywords "frontend developer" \\
      --no-db \\
      --max-jobs 200

  # Custom FlareSolverr URL (e.g., in Docker)
  python linkedin_crawler_best.py \\
      --keywords "machine learning" \\
      --flaresolverr-url http://flaresolverr:8191/v1 \\
      --max-jobs 500
        """
    )
    
    parser.add_argument(
        '--keywords',
        type=str,
        required=True,
        help='Job search keywords (comma-separated for multiple)'
    )
    
    parser.add_argument(
        '--locations',
        type=str,
        default='Worldwide',
        help='Job locations (comma-separated for multiple, default: Worldwide)'
    )
    
    parser.add_argument(
        '--max-jobs',
        type=int,
        default=100,
        help='Maximum number of jobs to crawl (default: 100)'
    )
    
    parser.add_argument(
        '--cookies',
        type=str,
        help='Path to LinkedIn cookies JSON file for authenticated access (optional)'
    )
    
    parser.add_argument(
        '--no-db',
        action='store_true',
        help='Skip database save, only save to JSON files'
    )
    
    parser.add_argument(
        '--flaresolverr-url',
        type=str,
        default=FLARESOLVERR_URL,
        help=f'FlareSolverr API URL (default: {FLARESOLVERR_URL})'
    )
    
    args = parser.parse_args()
    
    # Parse keywords and locations
    keywords = [k.strip() for k in args.keywords.split(',') if k.strip()]
    locations = [l.strip() for l in args.locations.split(',') if l.strip()]
    
    if not keywords:
        logger.error("❌ No keywords provided")
        sys.exit(1)
    
    # Run crawler
    jobs = crawl_linkedin_jobs(
        keywords=keywords,
        locations=locations,
        max_jobs=args.max_jobs,
        cookies_path=args.cookies,
        save_to_db=not args.no_db,
        flaresolverr_url=args.flaresolverr_url
    )
    
    if jobs:
        logger.info(f"\n✅ SUCCESS! Extracted {len(jobs)} jobs")
        logger.info(f"📁 Check data/raw/ folder for output files")
    else:
        logger.warning("\n⚠️  No jobs extracted. Check the logs for errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
