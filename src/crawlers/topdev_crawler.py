"""
TopDev Crawler - Crawl job postings from TopDev.vn

Uses Playwright to scrape TopDev's Next.js website.
"""
from typing import List, Dict, Any, Optional, Generator
from datetime import datetime
import logging
import json
import re
import time
import random
from bs4 import BeautifulSoup
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor

from .base_crawler import BaseCrawler

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not available. Install with: pip install playwright && playwright install chromium")


class TopDevCrawler(BaseCrawler):
    """Crawler for TopDev.vn job postings."""
    
    BASE_URL = "https://topdev.vn"
    SEARCH_URL = "https://topdev.vn/jobs/search"
    
    LOCATION_MAP = {
        'ho chi minh': '79',
        'hcm': '79',
        'ha noi': '01',
        'hanoi': '01',
        'da nang': '048',
        'danang': '048',
    }
    
    def __init__(self, **kwargs):
        super().__init__(source="topdev", use_playwright=True, **kwargs)
    
    def crawl(self,
              keywords: Optional[List[str]] = None,
              location: Optional[str] = None,
              pages: int = 1) -> Generator[Dict[str, Any], None, None]:
        """Crawl job postings from TopDev using Playwright."""
        logger.info(f"Starting TopDev crawl: keywords={keywords}, location={location}, pages={pages}")
        self.start_crawl()
        
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._run_playwright_crawl, keywords, location, pages)
                jobs_data = future.result(timeout=600)
            
            for job_data in jobs_data:
                yield job_data
                self.success_count += 1
                self.request_count += 1
        
        except Exception as e:
            logger.error(f"Error crawling TopDev: {e}", exc_info=True)
            self.error_count += 1
        
        self.log_completion()
    
    def _run_playwright_crawl(self,
                               keywords: Optional[List[str]],
                               location: Optional[str],
                               pages: int) -> List[Dict[str, Any]]:
        """Run Playwright crawl in sync context."""
        from playwright.sync_api import sync_playwright
        
        all_jobs = []
        seen_ids = set()
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()
            
            try:
                for page_num in range(1, pages + 1):
                    # Build URL with parameters
                    url = self._build_search_url(keywords, location, page_num)
                    
                    logger.info(f"Fetching TopDev page {page_num}/{pages}: {url}")
                    
                    # Load page with longer timeout for JS hydration
                    page.goto(url, wait_until='networkidle', timeout=60000)
                    time.sleep(3)  # Wait for JS hydration
                    
                    # Extract job data from Next.js script tags
                    content = page.content()
                    jobs_on_page = self._extract_jobs_from_html(content, seen_ids)
                    
                    if not jobs_on_page:
                        logger.warning(f"No jobs found on page {page_num} from JSON extraction")
                        # Try extracting from visible cards as fallback
                        jobs_on_page = self._extract_jobs_from_cards(page, seen_ids)
                    
                    logger.info(f"Found {len(jobs_on_page)} jobs on page {page_num}")
                    all_jobs.extend(jobs_on_page)
                    
                    self.log_progress(len(all_jobs))
                    
                    # Delay between pages
                    if page_num < pages:
                        time.sleep(random.uniform(2, 4))
                        
            except Exception as e:
                logger.error(f"Error in Playwright crawl: {e}", exc_info=True)
            finally:
                browser.close()
        
        return all_jobs
    
    def _build_search_url(self, keywords: Optional[List[str]], location: Optional[str], page_num: int) -> str:
        """Build search URL with parameters."""
        params = []
        
        if keywords:
            params.append(f"keyword={'+'.join(keywords)}")
        
        if location:
            region_id = self.LOCATION_MAP.get(location.lower().replace(' ', ''), '')
            if region_id:
                params.append(f"region_ids={region_id}")
        
        if page_num > 1:
            params.append(f"page={page_num}")
        
        return f"{self.SEARCH_URL}?{'&'.join(params)}" if params else self.SEARCH_URL
    
    def _extract_jobs_from_html(self, html_content: str, seen_ids: set) -> List[Dict[str, Any]]:
        """Extract job data from Next.js hydration scripts."""
        jobs = []
        
        for match in re.finditer(r'\\"id\\":(\d{7}),\\"title\\":\\"([^\\]+)\\"', html_content):
            job_id = match.group(1)
            title = match.group(2)
            
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)
            
            start = max(0, match.start() - 50)
            end = min(len(html_content), match.end() + 2000)
            context = html_content[start:end]
            
            company_match = re.search(r'\\"display_name\\":\\"([^\\]+)\\"', context)
            company_name = company_match.group(1) if company_match else 'Unknown'
            
            skills_match = re.search(r'\\"skills_str\\":\\"([^\\]*)\\"', context)
            skills_str = skills_match.group(1) if skills_match else ''
            skills = [s.strip().lower() for s in skills_str.split(',') if s.strip()]
            
            location_match = re.search(r'\\"address_region_list\\":\\"([^\\]*)\\"', context)
            location = location_match.group(1) if location_match else None
            
            url_match = re.search(r'\\"detail_url\\":\\"([^\\]*)\\"', context)
            source_url = url_match.group(1).replace('\\/', '/') if url_match else None
            if source_url and not source_url.startswith('http'):
                source_url = f"{self.BASE_URL}{source_url}"
            
            salary_match = re.search(r'\\"value\\":\\"([^\\]+)\\"', context)
            salary_text = salary_match.group(1) if salary_match else None
            if salary_text == 'Negotiable':
                salary_text = None
            
            job_data = {
                'job_id': job_id,
                'title': title,
                'company_name': company_name,
                'location': location,
                'required_skills': skills,
                'source_url': source_url,
                'salary_text': salary_text,
                'source': 'topdev',
            }
            
            if salary_text:
                salary_info = self.parse_salary_range(salary_text)
                job_data.update(salary_info)
            
            jobs.append(job_data)
        
        return jobs
    
    def _extract_jobs_from_cards(self, page, seen_ids: set) -> List[Dict[str, Any]]:
        """Fallback: Extract jobs from visible job cards."""
        from bs4 import BeautifulSoup
        
        jobs = []
        content = page.content()
        soup = BeautifulSoup(content, 'lxml')
        
        job_cards = soup.find_all('a', href=re.compile(r'/detail-jobs/'))
        
        for card in job_cards:
            try:
                href = card.get('href', '')
                if not href or 'detail-jobs' not in href:
                    continue
                
                id_match = re.search(r'-(\d{7})$', href)
                if not id_match:
                    continue
                job_id = id_match.group(1)
                
                if job_id in seen_ids:
                    continue
                seen_ids.add(job_id)
                
                title_elem = card.find(['h3', 'h4', 'span'], 
                                      class_=lambda x: x and 'title' in x.lower() if x else False)
                title = title_elem.get_text(strip=True) if title_elem else card.get_text(strip=True)[:100]
                
                source_url = f"{self.BASE_URL}{href}" if href.startswith('/') else href
                
                jobs.append({
                    'job_id': job_id,
                    'title': title,
                    'company_name': 'Unknown',
                    'source_url': source_url,
                    'source': 'topdev',
                })
            except Exception as e:
                logger.error(f"Error parsing job card: {e}")
                continue
        
        return jobs
    
    def parse_item(self, raw_data: Any) -> Dict[str, Any]:
        """Parse raw job data into structured format."""
        return raw_data if isinstance(raw_data, dict) else {}
