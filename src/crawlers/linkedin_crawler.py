"""
LinkedIn Crawler - Best implementation using FlareSolverr.

Production-ready LinkedIn crawler with:
- FlareSolverr integration for bypassing Cloudflare
- Comprehensive data extraction (25+ fields)
- Multi-keyword and multi-location support
- Smart pagination and deduplication
- Robust error handling and retry logic
- Progress tracking and auto-save
"""
from typing import List, Dict, Any, Optional, Generator
from datetime import datetime
import logging
import json
import os
import re
import time
import random
from bs4 import BeautifulSoup
from urllib.parse import urlencode
from pathlib import Path
from collections import Counter

from .base_crawler import BaseCrawler

logger = logging.getLogger(__name__)

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.error("requests not available. Install with: pip install requests")


class FlareSolverrClient:
    """FlareSolverr client for bypassing Cloudflare protection."""
    
    def __init__(self, api_url: str, timeout: int = 60000):
        self.api_url = api_url
        self.timeout = timeout
        self.session_id = None
        self.request_count = 0
    
    def test_connection(self) -> bool:
        """Test FlareSolverr connection."""
        try:
            response = requests.post(
                self.api_url,
                json={"cmd": "sessions.list"},
                timeout=10
            )
            data = response.json()
            if data.get("status") == "ok":
                logger.info("✓ FlareSolverr is accessible")
                return True
            return False
        except Exception as e:
            logger.error(f"FlareSolverr not accessible: {e}")
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
                logger.info(f"✓ FlareSolverr session created: {self.session_id}")
                return True
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
            logger.info(f"✓ Session destroyed")
        except Exception as e:
            logger.warning(f"Error destroying session: {e}")
    
    def get(self, url: str, cookies: Optional[List[Dict]] = None, max_retries: int = 3) -> Optional[Dict]:
        """Make a GET request through FlareSolverr."""
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
                
                response = requests.post(
                    self.api_url, 
                    json=payload, 
                    timeout=(self.timeout / 1000) + 10
                )
                data = response.json()
                
                if data.get("status") == "ok":
                    solution = data.get("solution", {})
                    self.request_count += 1
                    
                    return {
                        "html": solution.get("response", ""),
                        "url": solution.get("url", url),
                        "cookies": solution.get("cookies", []),
                        "status": solution.get("status", 200)
                    }
                else:
                    logger.warning(f"FlareSolverr error: {data.get('message', 'Unknown')}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}")
            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}/{max_retries}: {e}")
            
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                time.sleep(wait_time)
        
        return None


class LinkedInCrawler(BaseCrawler):
    """Best LinkedIn crawler with FlareSolverr integration."""
    
    BASE_URL = "https://www.linkedin.com"
    JOBS_SEARCH_URL = "https://www.linkedin.com/jobs/search"
    
    def __init__(self, 
                 cookies_path: Optional[str] = None,
                 flaresolverr_url: Optional[str] = None,
                 **kwargs):
        super().__init__(source="linkedin", **kwargs)
        self.cookies_path = cookies_path
        self.cookies = self._load_cookies()
        self.flaresolverr_url = flaresolverr_url or os.getenv("FLARESOLVERR_URL", "http://localhost:8191/v1")
        self.flare_client = None
        self.seen_urls = set()
    
    def _load_cookies(self) -> List[Dict]:
        """Load cookies from JSON file."""
        if not self.cookies_path:
            return []
        
        try:
            path = Path(self.cookies_path)
            if not path.exists():
                logger.warning(f"Cookie file not found: {self.cookies_path}")
                return []
            
            with open(path, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            
            logger.info(f"Loaded {len(cookies)} cookies")
            return cookies
        except Exception as e:
            logger.error(f"Failed to load cookies: {e}")
            return []
    
    def crawl(self, 
              keywords: Optional[List[str]] = None,
              locations: Optional[List[str]] = None,
              max_jobs: int = 100) -> Generator[Dict[str, Any], None, None]:
        """
        Crawl LinkedIn jobs using FlareSolverr.
        
        Args:
            keywords: List of job search keywords
            locations: List of locations to search
            max_jobs: Maximum number of jobs to crawl
        
        Yields:
            Job dictionaries with comprehensive data
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests not installed. Run: pip install requests")
        
        if not keywords:
            keywords = ["software engineer"]
        if not locations:
            locations = ["Worldwide"]
        
        logger.info(f"Starting LinkedIn crawl: {len(keywords)} keywords, {len(locations)} locations, max={max_jobs}")
        self.start_crawl()
        
        # Initialize FlareSolverr
        self.flare_client = FlareSolverrClient(self.flaresolverr_url)
        
        if not self.flare_client.test_connection():
            logger.error("FlareSolverr not accessible. Make sure it's running.")
            return
        
        if not self.flare_client.create_session():
            logger.error("Failed to create FlareSolverr session")
            return
        
        try:
            job_count = 0
            total_combinations = len(keywords) * len(locations)
            current_combination = 0
            
            for location in locations:
                for keyword in keywords:
                    if job_count >= max_jobs:
                        break
                    
                    current_combination += 1
                    logger.info(f"Search {current_combination}/{total_combinations}: '{keyword}' in '{location}'")
                    
                    # Calculate jobs per search
                    jobs_per_search = max((max_jobs - job_count) // (total_combinations - current_combination + 1), 10)
                    
                    # Crawl this keyword-location combination
                    for job in self._crawl_search(keyword, location, jobs_per_search):
                        yield job
                        job_count += 1
                        self.success_count += 1
                        
                        if job_count >= max_jobs:
                            break
                    
                    # Delay between searches
                    if current_combination < total_combinations and job_count < max_jobs:
                        time.sleep(random.uniform(5, 10))
                
                if job_count >= max_jobs:
                    break
        
        except Exception as e:
            logger.error(f"Error during crawl: {e}", exc_info=True)
            self.error_count += 1
        finally:
            if self.flare_client:
                self.flare_client.destroy_session()
            self.log_completion()
    
    def _crawl_search(self, keyword: str, location: str, max_jobs: int) -> Generator[Dict[str, Any], None, None]:
        """Crawl a single keyword-location search."""
        start_offset = 0
        jobs_from_search = 0
        consecutive_empty = 0
        max_pages = 10
        
        while jobs_from_search < max_jobs and (start_offset // 25) < max_pages:
            params = {
                'keywords': keyword,
                'location': location,
                'start': start_offset
            }
            
            search_url = f"{self.JOBS_SEARCH_URL}?{urlencode(params)}"
            page_num = (start_offset // 25) + 1
            
            logger.info(f"  Page {page_num} (offset={start_offset})")
            
            # Fetch search results
            response = self.flare_client.get(search_url, cookies=self.cookies if self.cookies else None)
            if not response:
                logger.warning("Failed to fetch search page")
                break
            
            # Parse job cards
            soup = BeautifulSoup(response['html'], 'html.parser')
            job_cards = soup.select(
                '.base-card, .base-search-card, .job-search-card, '
                '[data-entity-urn*="jobPosting"], li.jobs-search-results__list-item'
            )
            
            if not job_cards:
                consecutive_empty += 1
                if consecutive_empty >= 3:
                    break
                start_offset += 25
                time.sleep(random.uniform(2, 4))
                continue
            
            consecutive_empty = 0
            logger.info(f"  Found {len(job_cards)} job cards")
            
            # Extract job URLs
            job_urls = []
            for card in job_cards:
                link = card.select_one(
                    'a[href*="/jobs/view/"], '
                    'a.base-card__full-link, '
                    'a[data-tracking-control-name*="public_jobs"]'
                )
                
                if link:
                    job_url = link.get('href', '')
                    if not job_url.startswith('http'):
                        job_url = self.BASE_URL + job_url
                    
                    job_url = job_url.split('?')[0]
                    
                    if job_url and job_url not in self.seen_urls:
                        job_urls.append(job_url)
                        self.seen_urls.add(job_url)
            
            logger.info(f"  Processing {len(job_urls)} unique jobs")
            
            # Fetch and parse each job
            for idx, job_url in enumerate(job_urls, 1):
                if jobs_from_search >= max_jobs:
                    break
                
                job_response = self.flare_client.get(job_url, cookies=self.cookies if self.cookies else None)
                
                if not job_response:
                    continue
                
                try:
                    job_data = self._parse_job_detail(job_response['html'], job_url)
                    
                    if job_data.get('title'):
                        jobs_from_search += 1
                        self.request_count += 1
                        yield job_data
                        
                        time.sleep(random.uniform(3, 6))
                
                except Exception as e:
                    logger.error(f"Error parsing job: {e}")
                    self.error_count += 1
            
            start_offset += 25
            time.sleep(random.uniform(2, 4))
    
    def _parse_job_detail(self, html: str, url: str) -> Dict[str, Any]:
        """Parse comprehensive job information from LinkedIn detail page."""
        soup = BeautifulSoup(html, 'html.parser')
        
        job_data = {
            'source': 'linkedin',
            'source_url': url.split('?')[0],
            'crawled_at': datetime.now().isoformat(),
            'is_active': True
        }
        
        # Title
        title_selectors = [
            'h1.jobs-unified-top-card__job-title',
            'h1.job-details-jobs-unified-top-card__job-title',
            'h1.topcard__title',
        ]
        for selector in title_selectors:
            elem = soup.select_one(selector)
            if elem:
                job_data['title'] = elem.get_text(strip=True)
                break
        
        # Company Name
        company_selectors = [
            '.jobs-unified-top-card__company-name a',
            'a.ember-view.job-details-jobs-unified-top-card__company-name',
        ]
        for selector in company_selectors:
            elem = soup.select_one(selector)
            if elem:
                job_data['company_name'] = elem.get_text(strip=True)
                break
        
        # Location
        location_selectors = [
            'span.jobs-unified-top-card__bullet',
            'span.jobs-unified-top-card__workplace-type',
        ]
        for selector in location_selectors:
            elem = soup.select_one(selector)
            if elem:
                location_text = elem.get_text(strip=True)
                if location_text and len(location_text) > 3 and not any(
                    word in location_text.lower() for word in ['ago', 'posted', 'applicant']
                ):
                    job_data['location'] = location_text
                    break
        
        # Description
        desc_selectors = [
            '.jobs-description__content',
            'div.jobs-description-content__text',
            '.show-more-less-html__markup',
        ]
        description = ""
        for selector in desc_selectors:
            elem = soup.select_one(selector)
            if elem:
                description = elem.get_text(separator='\n', strip=True)
                job_data['description'] = description
                break
        
        # Structured job criteria
        criteria_items = soup.select('.jobs-unified-top-card__job-insight, .description__job-criteria-item')
        
        for criteria in criteria_items:
            text = criteria.get_text(strip=True)
            
            if any(kw in text for kw in ['Full-time', 'Part-time', 'Contract', 'Temporary', 'Internship']):
                if not job_data.get('job_type'):
                    job_data['job_type'] = text.split('\n')[0] if '\n' in text else text
            
            elif any(kw in text for kw in ['Entry level', 'Mid-Senior', 'Director', 'Executive', 'Senior', 'Lead']):
                if not job_data.get('level'):
                    job_data['level'] = text.split('\n')[0] if '\n' in text else text
        
        # Company rating
        rating_elem = soup.select_one('.jobs-unified-top-card__company-rating')
        if rating_elem:
            rating_text = rating_elem.get_text()
            rating_match = re.search(r'(\d+\.?\d*)', rating_text)
            if rating_match:
                try:
                    job_data['company_rating'] = float(rating_match.group(1))
                except ValueError:
                    pass
        
        # Requirements
        requirements_keywords = [
            'requirements', 'qualifications', 'what you need',
            'required qualifications', 'you should have'
        ]
        requirements_text = self._extract_section_text(soup, requirements_keywords)
        
        if not requirements_text and description:
            req_patterns = [
                r'(?:Requirements|Qualifications)[:\n]([\s\S]{100,5000}?)(?:Benefits|Responsibilities|$)',
            ]
            for pattern in req_patterns:
                match = re.search(pattern, description, re.IGNORECASE | re.DOTALL)
                if match:
                    requirements_text = match.group(1).strip()
                    break
        
        if not requirements_text and len(description) > 200:
            requirements_text = description
        
        if requirements_text:
            job_data['requirements_text'] = requirements_text[:10000]
        
        # Benefits
        benefits_keywords = ['benefits', 'perks', 'what we offer', 'why join us']
        benefits_text = self._extract_section_text(soup, benefits_keywords)
        benefits_list = []
        
        if benefits_text:
            benefit_lines = [
                line.strip().lstrip('-•*·').strip() 
                for line in benefits_text.split('\n') 
                if line.strip() and len(line.strip()) > 10
            ]
            benefits_list.extend(benefit_lines[:20])
        
        # Common benefit keywords
        benefit_keywords = [
            'health insurance', 'dental', 'vision', '401k', 'pto',
            'stock options', 'equity', 'bonus', 'flexible hours',
            'remote work', 'gym membership', 'learning budget',
            'parental leave'
        ]
        
        desc_lower = description.lower()
        found_benefits = [kw.title() for kw in benefit_keywords if kw in desc_lower]
        
        all_benefits = list(set(benefits_list + found_benefits))
        if all_benefits:
            job_data['benefits'] = json.dumps(all_benefits[:25])
        
        # Education
        education_patterns = [
            r"bachelor'?s?\s+degree",
            r"master'?s?\s+degree",
            r"phd|doctorate",
        ]
        
        for pattern in education_patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                edu_text = match.group(0).lower()
                if 'master' in edu_text:
                    job_data['education_level'] = "Master's Degree"
                elif 'phd' in edu_text or 'doctorate' in edu_text:
                    job_data['education_level'] = "PhD"
                elif 'bachelor' in edu_text:
                    job_data['education_level'] = "Bachelor's Degree"
                break
        
        # Skills
        full_text = description + "\n" + (requirements_text or "")
        skills = self._extract_skills(full_text)
        
        if skills:
            job_data['required_skills'] = json.dumps(skills[:20])
            if len(skills) > 20:
                job_data['preferred_skills'] = json.dumps(skills[20:35])
        
        # Experience
        exp_min, exp_max = self._extract_experience_years(full_text)
        if exp_min is not None:
            job_data['experience_years_min'] = exp_min
        if exp_max is not None:
            job_data['experience_years_max'] = exp_max
        
        # Salary
        salary_info = self._extract_salary(full_text)
        job_data.update(salary_info)
        
        # Remote detection
        remote_keywords = ['remote', 'work from home', 'wfh', '100% remote', 'fully remote']
        location_text = job_data.get('location', '').lower()
        
        if any(kw in desc_lower or kw in location_text for kw in remote_keywords):
            job_data['is_remote'] = True
        else:
            job_data['is_remote'] = False
        
        return job_data
    
    def _extract_section_text(self, soup: BeautifulSoup, keywords: List[str]) -> Optional[str]:
        """Extract text from a section based on header keywords."""
        for keyword in keywords:
            headers = soup.find_all(['h2', 'h3', 'h4', 'strong', 'b'])
            
            for header in headers:
                if keyword.lower() in header.get_text(strip=True).lower():
                    section = header.find_parent(['div', 'section', 'article'])
                    
                    if section:
                        text_parts = []
                        for elem in section.find_all(['p', 'li', 'span']):
                            text = elem.get_text(strip=True)
                            if text and len(text) > 15:
                                text_parts.append(text)
                        
                        if text_parts:
                            return '\n'.join(text_parts)
        
        return None
    
    def _extract_skills(self, text: str) -> List[str]:
        """Extract technical skills from text."""
        skill_patterns = [
            r'\b(Python|Java|JavaScript|TypeScript|C\+\+|C#|Ruby|PHP|Go|Rust|Swift|Kotlin|Scala)\b',
            r'\b(React|Angular|Vue\.?js|Node\.?js|Django|Flask|FastAPI|Spring|\.NET|Laravel)\b',
            r'\b(AWS|Azure|GCP|Docker|Kubernetes|Jenkins|GitLab|GitHub|CI/CD|DevOps)\b',
            r'\b(MySQL|PostgreSQL|MongoDB|Redis|Elasticsearch|Oracle)\b',
            r'\b(Machine Learning|AI|Data Science|TensorFlow|PyTorch)\b',
            r'\b(REST|GraphQL|Microservices|Agile|Scrum|Git)\b',
        ]
        
        skills = set()
        for pattern in skill_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                skills.add(match.group(0).strip())
        
        return sorted(list(skills))
    
    def _extract_salary(self, text: str) -> Dict[str, Any]:
        """Extract salary information."""
        result = {
            "salary_min": None,
            "salary_max": None,
            "salary_currency": "USD",
            "salary_text": None
        }
        
        patterns = [
            r'\$\s?([\d,]+)k?\s*[-–to]+\s*\$\s?([\d,]+)k?',
            r'([\d,]+)k?\s*[-–to]+\s*([\d,]+)k?\s*(USD|EUR|GBP)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    groups = match.groups()
                    if len(groups) >= 2:
                        salary_min = int(groups[0].replace(',', ''))
                        salary_max = int(groups[1].replace(',', ''))
                        
                        if 'k' in match.group(0).lower() and salary_min < 1000:
                            salary_min *= 1000
                            salary_max *= 1000
                        
                        result["salary_min"] = salary_min
                        result["salary_max"] = salary_max
                        result["salary_text"] = match.group(0).strip()
                        break
                except (ValueError, IndexError):
                    continue
        
        return result
    
    def _extract_experience_years(self, text: str) -> tuple:
        """Extract years of experience."""
        years_min, years_max = None, None
        
        patterns = [
            r'(\d+)\+\s*(?:years?|yrs?)',
            r'(\d+)\s*[-–to]+\s*(\d+)\s*(?:years?|yrs?)',
            r'(?:minimum|at least)\s+(\d+)\s*(?:years?|yrs?)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    groups = match.groups()
                    if len(groups) == 1 or groups[1] is None:
                        years_min = int(groups[0])
                    else:
                        years_min = int(groups[0])
                        years_max = int(groups[1])
                    break
                except (ValueError, IndexError):
                    continue
        
        return years_min, years_max
    
    def parse_item(self, raw_data: Any) -> Dict[str, Any]:
        """Parse raw data into structured format (already structured in this implementation)."""
        return raw_data if isinstance(raw_data, dict) else {}
