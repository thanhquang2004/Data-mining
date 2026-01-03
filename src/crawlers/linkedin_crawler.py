"""
LinkedIn Crawler - Crawl job postings from LinkedIn.com

Uses Playwright to scrape LinkedIn job postings with proper authentication.
"""
from typing import List, Dict, Any, Optional, Generator
from datetime import datetime
import logging
import json
import re
import time
import random
from bs4 import BeautifulSoup
from urllib.parse import urlencode, quote_plus
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from .base_crawler import BaseCrawler

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not available. Install with: pip install playwright && playwright install chromium")


class LinkedInCrawler(BaseCrawler):
    """Crawler for LinkedIn.com job postings with Playwright."""
    
    BASE_URL = "https://www.linkedin.com"
    JOBS_SEARCH_URL = "https://www.linkedin.com/jobs/search"
    
    def __init__(self, cookies_path: Optional[str] = None, **kwargs):
        super().__init__(source="linkedin", use_playwright=True, **kwargs)
        self.cookies_path = cookies_path
        self.cookies = self._load_cookies()
    
    def _load_cookies(self) -> List[Dict]:
        """Load cookies from JSON file for authenticated access."""
        if not self.cookies_path:
            return []
        
        try:
            path = Path(self.cookies_path)
            if not path.exists():
                logger.warning(f"Cookie file not found: {self.cookies_path}")
                return []
            
            with open(path, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            
            cleaned = []
            allowed_same_site = ["Strict", "Lax", "None"]
            for cookie in cookies:
                cleaned_cookie = {
                    'name': cookie.get('name'),
                    'value': cookie.get('value'),
                    'domain': cookie.get('domain', '.linkedin.com'),
                    'path': cookie.get('path', '/'),
                    'secure': cookie.get('secure', True),
                    'httpOnly': cookie.get('httpOnly', False),
                }
                same_site = cookie.get('sameSite', 'Lax')
                cleaned_cookie['sameSite'] = same_site if same_site in allowed_same_site else 'Lax'
                
                if 'expires' in cookie and isinstance(cookie['expires'], (int, float)):
                    cleaned_cookie['expires'] = cookie['expires']
                
                cleaned.append(cleaned_cookie)
            
            logger.info(f"Loaded {len(cleaned)} cookies from {self.cookies_path}")
            return cleaned
        except Exception as e:
            logger.error(f"Failed to load cookies: {e}")
            return []
    
    def crawl(self, 
              keywords: Optional[List[str]] = None,
              location: Optional[str] = None,
              pages: int = 1) -> Generator[Dict[str, Any], None, None]:
        """Crawl job postings from LinkedIn using Playwright."""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright is not installed. Run: pip install playwright && playwright install chromium")
        
        logger.info(f"Starting LinkedIn crawl: keywords={keywords}, location={location}, pages={pages}")
        self.start_crawl()
        
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._run_playwright_crawl, keywords, location, pages)
                jobs = future.result(timeout=600)
                
                for job in jobs:
                    yield job
                    self.success_count += 1
        
        except Exception as e:
            logger.error(f"Error crawling LinkedIn: {e}", exc_info=True)
            self.error_count += 1
        
        self.log_completion()
    
    def _run_playwright_crawl(self, keywords, location, pages) -> List[Dict[str, Any]]:
        """Run Playwright crawl with staged approach: listings -> details."""
        from playwright.sync_api import sync_playwright
        
        jobs = []
        
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                ]
            )
            
            try:
                logger.info("Stage 1: Crawling job listings")
                job_listings = self._crawl_job_listings(browser, keywords, location, pages)
                
                logger.info(f"Stage 2: Crawling details for {len(job_listings)} jobs")
                for idx, listing in enumerate(job_listings, 1):
                    try:
                        logger.info(f"Fetching details {idx}/{len(job_listings)}: {listing['title']}")
                        
                        if listing.get('source_url'):
                            detail_data = self._fetch_job_detail(browser, listing['source_url'])
                            if detail_data:
                                listing.update(detail_data)
                        
                        jobs.append(listing)
                        self.request_count += 1
                        time.sleep(random.uniform(2, 4))
                        
                    except Exception as e:
                        logger.error(f"Error fetching detail for job {idx}: {e}")
                        jobs.append(listing)
                
            finally:
                browser.close()
        
        return jobs
    
    def _crawl_job_listings(self, browser, keywords, location, pages) -> List[Dict]:
        """Stage 1: Crawl job listing pages to get basic info and URLs."""
        listings = []
        seen_ids = set()
        
        for page_num in range(pages):
            try:
                params = {}
                if keywords:
                    params['keywords'] = ' '.join(keywords)
                if location:
                    params['location'] = location
                params['start'] = page_num * 25  # LinkedIn uses offset pagination
                
                url = f"{self.JOBS_SEARCH_URL}?{urlencode(params)}"
                logger.info(f"Crawling page {page_num + 1}/{pages}: {url}")
                
                html_content = self._get_page_content(browser, url)
                if not html_content:
                    logger.error(f"Failed to fetch page {page_num + 1}")
                    continue
                
                soup = BeautifulSoup(html_content, 'lxml')
                
                # Find job cards
                job_cards = soup.find_all('div', class_=re.compile(r'base-card'))
                logger.info(f"Found {len(job_cards)} job cards on page {page_num + 1}")
                
                for card in job_cards:
                    try:
                        # Extract job link
                        link_tag = card.find('a', class_=re.compile(r'base-card__full-link'))
                        if not link_tag:
                            continue
                        
                        job_url = link_tag.get('href', '')
                        if not job_url:
                            continue
                        
                        # Extract job ID from URL
                        job_id_match = re.search(r'/view/(\d+)', job_url)
                        job_id = job_id_match.group(1) if job_id_match else None
                        
                        if not job_id or job_id in seen_ids:
                            continue
                        seen_ids.add(job_id)
                        
                        # Extract title
                        title_tag = card.find('h3', class_=re.compile(r'base-search-card__title'))
                        title = title_tag.get_text(strip=True) if title_tag else 'Unknown'
                        
                        # Extract company
                        company_tag = card.find('h4', class_=re.compile(r'base-search-card__subtitle'))
                        company_name = company_tag.get_text(strip=True) if company_tag else 'Unknown'
                        
                        # Extract location
                        location_tag = card.find('span', class_=re.compile(r'job-search-card__location'))
                        job_location = location_tag.get_text(strip=True) if location_tag else None
                        
                        listings.append({
                            'job_id': job_id,
                            'title': title,
                            'company_name': company_name,
                            'location': job_location,
                            'source_url': job_url,
                            'source': 'linkedin'
                        })
                    except Exception as e:
                        logger.error(f"Error parsing job card: {e}")
                
                if page_num < pages - 1:
                    time.sleep(random.uniform(3, 5))
                    
            except Exception as e:
                logger.error(f"Error crawling page {page_num + 1}: {e}")
        
        return listings
    
    def _get_page_content(self, browser, url: str) -> Optional[str]:
        """Fetch page content using Playwright browser."""
        context_options = {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'viewport': {'width': 1920, 'height': 1080}
        }
        
        context = browser.new_context(**context_options)
        
        if self.cookies:
            context.add_cookies(self.cookies)
            logger.debug("Added authentication cookies")
        
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        
        page = context.new_page()
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            time.sleep(3)  # Wait for dynamic content
            return page.content()
        except Exception as e:
            logger.error(f"Playwright error fetching {url}: {e}")
            return None
        finally:
            context.close()
    
    def _fetch_job_detail(self, browser, url: str) -> Optional[Dict[str, Any]]:
        """Stage 2: Fetch detailed job information from detail page."""
        try:
            html_content = self._get_page_content(browser, url)
            if not html_content:
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            detail_data = {}
            
            # Description
            desc_tag = soup.find('div', class_=re.compile(r'show-more-less-html__markup'))
            if desc_tag:
                detail_data['description'] = desc_tag.get_text(separator='\n', strip=True)
            
            # Job criteria (seniority, employment type, etc.)
            criteria_items = soup.find_all('li', class_=re.compile(r'job-criteria__item'))
            for item in criteria_items:
                label_tag = item.find('h3', class_=re.compile(r'job-criteria__subheader'))
                value_tag = item.find('span', class_=re.compile(r'job-criteria__text'))
                
                if label_tag and value_tag:
                    label = label_tag.get_text(strip=True).lower()
                    value = value_tag.get_text(strip=True)
                    
                    if 'seniority' in label:
                        detail_data['level'] = value
                    elif 'employment type' in label:
                        detail_data['job_type'] = value
            
            # Extract skills from description
            description = detail_data.get('description', '')
            if description:
                skills = self._extract_skills_from_text(description)
                detail_data['required_skills'] = skills
                
                # Extract experience requirements
                exp_info = self.extract_experience_years(description)
                detail_data['experience_years_min'] = exp_info.get('min')
                detail_data['experience_years_max'] = exp_info.get('max')
            
            # Salary (often not displayed publicly on LinkedIn)
            salary_tag = soup.find(string=re.compile(r'\$\d+'))
            if salary_tag:
                salary_text = salary_tag.strip()
                detail_data['salary_text'] = salary_text
                salary_info = self.parse_salary_range(salary_text)
                detail_data.update(salary_info)
            
            return detail_data
            
        except Exception as e:
            logger.error(f"Error fetching job detail from {url}: {e}")
            return None
    
    def _extract_skills_from_text(self, text: str) -> List[str]:
        """Extract technical skills from text."""
        if not text:
            return []
        
        text_lower = text.lower()
        found_skills = set()
        
        skill_patterns = [
            r'\b(python|java|javascript|typescript|csharp|c\+\+|golang|go|rust|ruby|php|swift|kotlin|scala)\b',
            r'\b(react|vue|angular|django|flask|fastapi|spring|springboot|rails|laravel|nodejs|express|nestjs|nextjs)\b',
            r'\b(mysql|postgresql|postgres|mongodb|redis|elasticsearch|oracle|sqlserver|sqlite)\b',
            r'\b(aws|azure|gcp|docker|kubernetes|k8s|terraform|jenkins|gitlab|github|cicd|ci/cd)\b',
            r'\b(git|linux|unix|restapi|rest|api|graphql|microservices|agile|scrum)\b',
        ]
        
        for pattern in skill_patterns:
            matches = re.findall(pattern, text_lower)
            found_skills.update(matches)
        
        return sorted(list(found_skills))
    
    def parse_item(self, raw_data: Any) -> Dict[str, Any]:
        """Parse raw data into structured format."""
        return raw_data if isinstance(raw_data, dict) else {}
