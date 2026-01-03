"""
ITViec Crawler - Crawl job postings from ITViec.com

Uses Playwright to bypass Cloudflare protection with cookie-based authentication.
Supports both fast listing crawl and detailed crawl modes.
"""
import json
import logging
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Set

from .base_crawler import BaseCrawler

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not available. Install with: pip install playwright && playwright install chromium")


class ITViecCrawler(BaseCrawler):
    """Crawler for ITViec.com job postings with Playwright and cookie authentication."""
    
    BASE_URL = "https://itviec.com"
    JOBS_URL = "https://itviec.com/it-jobs"
    DEFAULT_MAX_JOBS = 1000
    MAX_SKILLS_PER_JOB = 15
    
    def __init__(self, cookies_path: Optional[str] = None, **kwargs):
        super().__init__(source="itviec", use_playwright=True, **kwargs)
        self.cookies_path = cookies_path
        self.cookies = self._load_cookies()
        self._seen_urls: Set[str] = set()
    
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
                data = json.load(f)
            
            # Handle both {"cookies": [...]} and [...] formats
            cookies = data.get('cookies', data) if isinstance(data, dict) else data
            
            cleaned = []
            allowed_same_site = ["Strict", "Lax", "None"]
            for cookie in cookies:
                if not isinstance(cookie, dict):
                    continue
                cleaned_cookie = {
                    'name': cookie.get('name'),
                    'value': cookie.get('value'),
                    'domain': cookie.get('domain', '.itviec.com'),
                    'path': cookie.get('path', '/'),
                    'secure': cookie.get('secure', True),
                    'httpOnly': cookie.get('httpOnly', False),
                }
                same_site = cookie.get('sameSite', 'Lax')
                cleaned_cookie['sameSite'] = same_site if same_site in allowed_same_site else 'Lax'
                cleaned.append(cleaned_cookie)
            
            logger.info(f"Loaded {len(cleaned)} cookies")
            return cleaned
        except Exception as e:
            logger.error(f"Failed to load cookies: {e}")
            return []
    
    def crawl(
        self,
        keywords: Optional[List[str]] = None,
        location: Optional[str] = None,
        pages: int = 1,
        max_jobs: int = DEFAULT_MAX_JOBS,
        fetch_details: bool = True,
        store_to_db: bool = True,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Crawl job postings from ITViec using Playwright.
        
        Args:
            keywords: Search keywords
            location: Location filter
            pages: Number of pages to crawl
            max_jobs: Maximum number of jobs to collect (default: 1000)
            fetch_details: Whether to fetch detailed info for each job (slower)
            store_to_db: Whether to store directly to database
            
        Yields:
            Job data dictionaries
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright is not installed. Run: pip install playwright && playwright install chromium")
        
        logger.info(f"Starting ITViec crawl: keywords={keywords}, location={location}, pages={pages}, max_jobs={max_jobs}")
        self.start_crawl()
        self._seen_urls.clear()
        
        try:
            jobs = self._run_playwright_crawl(keywords, location, pages, max_jobs, fetch_details, store_to_db)
            for job in jobs:
                yield job
                self.success_count += 1
        except Exception as e:
            logger.error(f"Error crawling ITViec: {e}", exc_info=True)
            self.error_count += 1
        
        self.log_completion()
    
    def _run_playwright_crawl(
        self, 
        keywords: Optional[List[str]], 
        location: Optional[str], 
        pages: int,
        max_jobs: int,
        fetch_details: bool,
        store_to_db: bool,
    ) -> List[Dict[str, Any]]:
        """Run Playwright crawl with direct job card extraction."""
        jobs = []
        logger.info("Starting Playwright browser...")
        
        with sync_playwright() as playwright:
            logger.info("Launching Chromium...")
            browser = playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                ]
            )
            logger.info("Browser launched successfully")
            
            try:
                context = self._create_browser_context(browser)
                page = context.new_page()
                logger.info("Created new browser page")
                
                # Crawl each page
                for page_num in range(1, pages + 1):
                    # Check if we've reached max jobs
                    if len(jobs) >= max_jobs:
                        logger.info(f"Reached max jobs target ({max_jobs})")
                        break
                    
                    # Build URL with page number
                    url = self._build_search_url(keywords, location, page_num)
                    logger.info(f"Fetching page {page_num}/{pages}: {url}")
                    
                    if not self._navigate_and_wait(page, url):
                        logger.warning(f"Failed to load page {page_num}, skipping")
                        continue
                    
                    # Extract jobs from current page using direct selectors
                    page_jobs = self._extract_jobs_from_page(page)
                    
                    # Fallback: try extracting from links if no job cards found
                    if not page_jobs:
                        page_jobs = self._extract_jobs_from_links(page)
                    
                    logger.info(f"Page {page_num}: Found {len(page_jobs)} jobs")
                    
                    if not page_jobs:
                        logger.warning(f"No jobs on page {page_num}, may have reached end")
                        break
                    
                    # Process each job
                    for job_data in page_jobs:
                        source_url = job_data.get('source_url')
                        if not source_url or source_url in self._seen_urls:
                            continue
                        
                        self._seen_urls.add(source_url)
                        
                        # Optionally fetch details (slower but more complete)
                        if fetch_details:
                            try:
                                logger.debug(f"Fetching details: {job_data['title'][:50]}...")
                                detail_data = self._fetch_job_detail(page, source_url)
                                if detail_data:
                                    job_data.update(detail_data)
                                time.sleep(random.uniform(1.5, 3.0))
                            except Exception as e:
                                logger.error(f"Error fetching details: {e}")
                        
                        jobs.append(job_data)
                        self.request_count += 1
                        
                        # Store to DB if enabled
                        if store_to_db:
                            self._store_job(job_data)
                        
                        if len(jobs) >= max_jobs:
                            break
                    
                    logger.info(f"Total unique jobs so far: {len(jobs)}")
                    
                    # Delay between pages
                    if page_num < pages and len(jobs) < max_jobs:
                        time.sleep(random.uniform(1, 2))
                
                context.close()
            finally:
                browser.close()
        
        logger.info(f"Crawl complete: {len(jobs)} jobs collected")
        return jobs
    
    def _create_browser_context(self, browser: Browser):
        """Create a browser context with stealth settings."""
        context = browser.new_context(
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='Asia/Ho_Chi_Minh',
            geolocation={'latitude': 10.8231, 'longitude': 106.6297},
            permissions=['geolocation'],
        )
        
        # Add cookies if available
        if self.cookies:
            context.add_cookies(self.cookies)
            logger.info(f"Added {len(self.cookies)} authentication cookies")
        
        # Add comprehensive stealth scripts
        context.add_init_script("""
            // Hide webdriver
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            
            // Add chrome object
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin' }
                ]
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en', 'vi'] });
            
            // Mock permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
        """)
        
        return context
    
    def _build_search_url(self, keywords: Optional[List[str]], location: Optional[str], page: int = 1) -> str:
        """Build the search URL with parameters."""
        params = []
        if keywords:
            params.append(f"q={'+'.join(keywords)}")
        if location:
            params.append(f"locations={location}")
        if page > 1:
            params.append(f"page={page}")
        
        if params:
            return f"{self.JOBS_URL}?{'&'.join(params)}"
        return self.JOBS_URL
    
    def _navigate_and_wait(self, page: Page, url: str, max_retries: int = 3) -> bool:
        """Navigate to URL and wait for Cloudflare challenge to complete."""
        for attempt in range(max_retries):
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=60000)
                
                # Check title immediately
                title = page.title()
                if "Just a moment" not in title and "Chờ" not in title:
                    logger.info(f"Page loaded immediately: {title[:50]}")
                    time.sleep(0.5)  # Brief wait for dynamic content
                    return True
                
                # Wait for Cloudflare challenge to complete (check every 1 second, up to 20 seconds)
                for wait_count in range(20):
                    time.sleep(1)
                    title = page.title()
                    if "Just a moment" not in title and "Chờ" not in title:
                        logger.info(f"Page loaded after {wait_count+1}s: {title[:50]}")
                        time.sleep(0.5)
                        return True
                
                logger.warning(f"Cloudflare challenge timeout, attempt {attempt + 1}/{max_retries}")
            except Exception as e:
                logger.error(f"Navigation error (attempt {attempt + 1}): {e}")
                time.sleep(2)
        
        return False
    
    def _extract_jobs_from_page(self, page: Page) -> List[Dict[str, Any]]:
        """Extract job data directly from page using Playwright selectors."""
        jobs = []
        
        # Wait for job cards to load
        try:
            page.wait_for_selector('.job-card, .job_content, [class*="job"]', timeout=10000)
        except:
            logger.warning("Job cards selector timeout, trying alternative approach")
        
        # Try multiple selector strategies
        job_cards = page.query_selector_all('.job-card')
        if not job_cards:
            job_cards = page.query_selector_all('[class*="job_content"]')
        if not job_cards:
            job_cards = page.query_selector_all('div[data-job-id]')
        
        logger.info(f"Found {len(job_cards)} job cards")
        
        for card in job_cards:
            try:
                job_data = self._extract_job_from_card(card)
                if job_data:
                    jobs.append(job_data)
            except Exception as e:
                logger.error(f"Error extracting job from card: {e}")
        
        return jobs
    
    def _extract_jobs_from_links(self, page: Page) -> List[Dict[str, Any]]:
        """Fallback: Extract jobs from job links when cards aren't found."""
        jobs = []
        job_links = page.query_selector_all('a[href*="/it-jobs/"][href*="-"]')
        logger.info(f"Fallback: Found {len(job_links)} job links")
        
        for link in job_links:
            try:
                href = link.get_attribute('href')
                if not href or href in self._seen_urls:
                    continue
                
                # Skip non-job links
                if '?page=' in href or href.endswith('/it-jobs') or '/it-jobs?' in href:
                    continue
                
                title = link.inner_text().strip()
                if not title or len(title) < 5:
                    continue
                
                full_url = href if href.startswith('http') else f"{self.BASE_URL}{href}"
                
                jobs.append({
                    'title': title,
                    'source_url': full_url,
                    'source': 'itviec',
                    'is_active': True,
                })
            except Exception as e:
                logger.debug(f"Error extracting link: {e}")
                continue
        
        return jobs
    
    def _extract_job_from_card(self, card) -> Optional[Dict[str, Any]]:
        """Extract job data from a single job card element."""
        try:
            # Get title - it's in h3 directly with data-url attribute
            title_elem = card.query_selector('h3[data-url]')
            if title_elem:
                title = title_elem.inner_text().strip()
                job_url = title_elem.get_attribute('data-url')
            else:
                # Fallback: try link selectors
                link_elem = card.query_selector('a[href*="/it-jobs/"]')
                if not link_elem:
                    return None
                title = link_elem.inner_text().strip()
                job_url = link_elem.get_attribute('href')
            
            if job_url and not job_url.startswith('http'):
                job_url = f"{self.BASE_URL}{job_url}"
            
            if not title or not job_url:
                return None
            
            # Get company name - in span.ims-2 or span.small-text containing company link
            company = "Unknown Company"
            company_elem = card.query_selector('span.ims-2 a, span.small-text a[href*="/companies/"]')
            if company_elem:
                company = company_elem.inner_text().strip()
            if not company:
                # Fallback: get second link to /companies/ (first is logo)
                company_links = card.query_selector_all('a[href*="/companies/"]')
                for link in company_links:
                    text = link.inner_text().strip()
                    if text:
                        company = text
                        break
            if not company:
                company = "Unknown Company"
            
            # Get location - various possible selectors
            location_elem = card.query_selector('[class*="city"], [class*="location"], .address, .job-location')
            location = location_elem.inner_text().strip() if location_elem else "Vietnam"
            if not location:
                location = "Vietnam"
            
            # Get salary - note: may show "Sign in to view salary" if not logged in
            salary_elem = card.query_selector('.salary, [class*="salary"]')
            salary_text = salary_elem.inner_text().strip() if salary_elem else None
            # Skip "sign in" text
            if salary_text and 'sign in' in salary_text.lower():
                salary_text = None
            
            # Get skills/tags (limit to MAX_SKILLS_PER_JOB)
            skills = []
            skill_elems = card.query_selector_all('.itag, .tag, [class*="skill"], .badge')
            for skill in skill_elems:
                skill_text = skill.inner_text().strip()
                if skill_text and len(skill_text) < 50 and skill_text not in skills:
                    skills.append(skill_text.lower())
                if len(skills) >= self.MAX_SKILLS_PER_JOB:
                    break
            
            job_data = {
                'title': title,
                'source_url': job_url,
                'company_name': company,
                'location': location,
                'source': 'itviec',
                'required_skills': skills,
                'is_active': True,
            }
            
            if salary_text:
                job_data['salary_text'] = salary_text
                salary_info = self.parse_salary_range(salary_text)
                job_data.update(salary_info)
            
            return job_data
        except Exception as e:
            logger.error(f"Error extracting job from card: {e}")
            return None
    
    def _fetch_job_detail(self, page: Page, url: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed job information from detail page."""
        try:
            if not self._navigate_and_wait(page, url, max_retries=2):
                return None
            
            detail_data = {}
            
            # Salary
            salary_elem = page.query_selector('span.ips-2.fw-500, [class*="salary"]')
            if salary_elem:
                salary_text = salary_elem.inner_text().strip()
                detail_data['salary_text'] = salary_text
                salary_info = self.parse_salary_range(salary_text)
                detail_data.update(salary_info)
            
            # Description
            desc_sections = page.query_selector_all('div.paragraph, .job-description, [class*="description"]')
            for section in desc_sections:
                h2 = section.query_selector('h2')
                if h2:
                    heading = h2.inner_text().lower()
                    content = section.inner_text()
                    
                    if 'description' in heading or 'about' in heading:
                        detail_data['description'] = content
                    elif any(k in heading for k in ['skill', 'requirement', 'experience']):
                        detail_data['requirements_text'] = content
            
            # Company rating
            rating_elem = page.query_selector('div.h4.ips-2.text-it-black, [class*="rating"] span')
            if rating_elem:
                try:
                    detail_data['company_rating'] = float(rating_elem.inner_text().strip())
                except:
                    pass
            
            # Skills from detail page (limit to MAX_SKILLS_PER_JOB)
            skill_elems = page.query_selector_all('div.d-flex.flex-wrap.igap-2 a.itag, .skill-tag, [class*="skill"] a')
            skills = []
            for elem in skill_elems:
                skill_text = elem.inner_text().strip().lower()
                if skill_text and skill_text not in skills:
                    skills.append(skill_text)
                if len(skills) >= self.MAX_SKILLS_PER_JOB:
                    break
            if skills:
                detail_data['required_skills'] = skills
            
            # Company name (if not already set)
            company_elem = page.query_selector('div.employer-name, .company-name, [class*="employer"] a')
            if company_elem:
                detail_data['company_name'] = company_elem.inner_text().strip()
            
            # Location
            location_elem = page.query_selector('span.normal-text.text-rich-grey, [class*="location"]')
            if location_elem:
                detail_data['location'] = location_elem.inner_text().strip()
            
            # Extract experience and level
            requirements_text = detail_data.get('requirements_text', '')
            exp_info = self.extract_experience_years(requirements_text)
            detail_data['experience_years_min'] = exp_info.get('min')
            detail_data['experience_years_max'] = exp_info.get('max')
            detail_data['level'] = self._infer_level_from_text(requirements_text)
            
            # Job type
            detail_data['job_type'] = self._extract_job_type_from_page(page)
            
            # Benefits
            benefit_elems = page.query_selector_all('section.job-content li, .benefit-item, [class*="benefit"] li')
            benefits = [elem.inner_text().strip() for elem in benefit_elems if elem.inner_text().strip()]
            if benefits:
                detail_data['benefits'] = benefits
            
            # Is remote
            description = detail_data.get('description', '')
            detail_data['is_remote'] = self.detect_remote_work(description, requirements_text)
            
            return detail_data
            
        except Exception as e:
            logger.error(f"Error fetching job detail from {url}: {e}")
            return None
    
    def _extract_job_type_from_page(self, page: Page) -> str:
        """Extract job type from job detail page."""
        # Try to find working time info
        time_elem = page.query_selector('[class*="working"], [class*="time"]')
        if time_elem:
            text = time_elem.inner_text()
            if re.search(r'\d{1,2}:\d{2}', text):
                return text.strip()
        
        # Look for specific labels
        labels = page.query_selector_all('div.d-flex div')
        for label in labels:
            text = label.inner_text().lower()
            if 'full-time' in text or 'full time' in text:
                return 'Full-time'
            if 'part-time' in text or 'part time' in text:
                return 'Part-time'
            if 'contract' in text:
                return 'Contract'
        
        return 'Full-time'
    
    def _infer_level_from_text(self, text: str) -> str:
        """Infer job level from requirements text."""
        if not text:
            return 'Middle'
        
        text_lower = text.lower()
        
        # Senior indicators
        if any(k in text_lower for k in ['senior', 'lead', 'manager', 'principal', 'expert', 'architect']):
            return 'Senior'
        if re.search(r'(\d+)\s*\+?\s*(?:year|năm)', text_lower):
            match = re.search(r'(\d+)\s*\+?\s*(?:year|năm)', text_lower)
            if match and int(match.group(1)) >= 5:
                return 'Senior'
        
        # Junior indicators
        if any(k in text_lower for k in ['junior', 'fresher', 'entry level', 'graduate', 'intern']):
            return 'Junior'
        if re.search(r'\b0-2\s*(?:year|năm)', text_lower):
            return 'Junior'
        
        return 'Middle'
    
    def _store_job(self, job_data: Dict[str, Any]) -> bool:
        """Store job directly to database."""
        try:
            from src.database import get_db_session, job_crud
            from src.schemas.job import JobCreate
            
            with get_db_session() as db:
                # Check for duplicate
                if job_crud.get_by_source_url(db, job_data.get('source_url', '')):
                    logger.debug(f"Job already exists: {job_data.get('title', '')}")
                    return False
                
                job_create = JobCreate(
                    title=job_data.get('title', 'Unknown'),
                    source_url=job_data.get('source_url', ''),
                    company_name=job_data.get('company_name'),
                    location=job_data.get('location'),
                    source='itviec',
                    description=job_data.get('description'),
                    requirements_text=job_data.get('requirements_text'),
                    job_type=job_data.get('job_type'),
                    level=job_data.get('level'),
                    salary_min=job_data.get('salary_min'),
                    salary_max=job_data.get('salary_max'),
                    salary_currency=job_data.get('salary_currency', 'USD'),
                    salary_text=job_data.get('salary_text'),
                    experience_years_min=job_data.get('experience_years_min'),
                    experience_years_max=job_data.get('experience_years_max'),
                    required_skills=job_data.get('required_skills', []),
                    benefits=job_data.get('benefits', []),
                    company_rating=job_data.get('company_rating'),
                    is_remote=job_data.get('is_remote', False),
                    is_active=True,
                )
                job_crud.create(db, job_create)
                logger.info(f"Stored job: {job_data.get('title', '')}")
                return True
        except Exception as e:
            logger.error(f"Error storing job: {e}")
            return False
    
    def parse_item(self, raw_data: Any) -> Dict[str, Any]:
        """Parse raw data into structured format."""
        return raw_data if isinstance(raw_data, dict) else {}
