"""
TopCV Crawler - Crawl job postings from TopCV.vn

Two-phase approach:
1. Download HTML pages to local storage
2. Parse stored HTML and save to database

Supports VPN/host network and handles rate limiting.
"""
import json
import logging
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Set
from bs4 import BeautifulSoup
import requests

from .base_crawler import BaseCrawler

logger = logging.getLogger(__name__)


class TopCVCrawler(BaseCrawler):
    """Crawler for TopCV.vn job postings with two-phase download/parse approach."""
    
    BASE_URL = "https://www.topcv.vn"
    LISTING_URL = "https://www.topcv.vn/viec-lam-it"
    DEFAULT_MAX_PAGES = 40
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    
    def __init__(self, 
                 download_dir: Optional[str] = None,
                 urls_cache_file: Optional[str] = None,
                 **kwargs):
        """
        Initialize TopCV crawler.
        
        Args:
            download_dir: Directory to store downloaded HTML files
            urls_cache_file: JSON file to cache collected URLs
            **kwargs: Additional arguments for BaseCrawler
        """
        super().__init__(source="topcv", use_playwright=False, **kwargs)
        
        # Setup directories
        self.download_dir = Path(download_dir) if download_dir else Path("data/topcv_html")
        self.urls_cache_file = Path(urls_cache_file) if urls_cache_file else Path("data/topcv_urls.json")
        
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.urls_cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        # HTTP session for downloads
        self.session = requests.Session()
        self._update_session_headers()
        
        # Cache
        self._url_cache: Set[str] = set()
        self._load_url_cache()
    
    def _update_session_headers(self):
        """Update session headers with random user agent."""
        self.session.headers.update({
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
    
    def _load_url_cache(self):
        """Load cached URLs from file."""
        if self.urls_cache_file.exists():
            try:
                with open(self.urls_cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._url_cache = set(data.get('urls', []))
                    logger.info(f"Loaded {len(self._url_cache)} URLs from cache")
            except Exception as e:
                logger.warning(f"Could not load URL cache: {e}")
    
    def _save_url_cache(self):
        """Save URL cache to file."""
        try:
            with open(self.urls_cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'urls': list(self._url_cache),
                    'updated': datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Could not save URL cache: {e}")
    
    def _get_file_path_for_url(self, url: str) -> Path:
        """Get local file path for a job URL."""
        match = re.search(r'/(\d+)\.html', url)
        if match:
            job_id = match.group(1)
            return self.download_dir / f"{job_id}.html"
        
        # Fallback: hash the URL
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
        return self.download_dir / f"{url_hash}.html"
    
    def crawl(self, 
              max_pages: int = DEFAULT_MAX_PAGES,
              download_only: bool = False,
              parse_only: bool = False) -> Generator[Dict[str, Any], None, None]:
        """
        Crawl TopCV jobs with two-phase approach.
        
        Args:
            max_pages: Maximum number of listing pages to crawl
            download_only: Only download HTML files, don't parse
            parse_only: Only parse existing HTML files, don't download
            
        Yields:
            Parsed job data dictionaries
        """
        self.start_crawl()
        
        try:
            if not parse_only:
                # Phase 1: Download
                logger.info("=" * 60)
                logger.info("Phase 1: Downloading HTML pages")
                logger.info("=" * 60)
                self._download_phase(max_pages)
                self._save_url_cache()
            
            if not download_only:
                # Phase 2: Parse
                logger.info("=" * 60)
                logger.info("Phase 2: Parsing HTML pages")
                logger.info("=" * 60)
                for job_data in self._parse_phase():
                    yield job_data
                    self.success_count += 1
        
        except Exception as e:
            logger.error(f"Error in TopCV crawl: {e}", exc_info=True)
            self.error_count += 1
        
        finally:
            self.log_completion()
    
    def _download_phase(self, max_pages: int):
        """Phase 1: Collect URLs and download HTML files."""
        # Step 1: Collect all job URLs from listing pages
        logger.info(f"Collecting job URLs from up to {max_pages} pages...")
        new_urls = self._collect_job_urls(max_pages)
        logger.info(f"Total URLs in cache: {len(self._url_cache)}")
        logger.info(f"New URLs to download: {len(new_urls)}")
        
        # Step 2: Download job detail pages
        if new_urls:
            logger.info(f"Downloading {len(new_urls)} job detail pages...")
            self._download_job_pages(new_urls)
        
        # Report
        total_files = len(list(self.download_dir.glob("*.html")))
        logger.info(f"Total HTML files in storage: {total_files}")
    
    def _collect_job_urls(self, max_pages: int) -> Set[str]:
        """Collect job URLs from listing pages."""
        new_urls = set()
        empty_pages = 0
        
        for page_num in range(1, max_pages + 1):
            urls = self._get_jobs_from_listing_page(page_num)
            
            if not urls:
                empty_pages += 1
                if empty_pages >= 2:
                    logger.info(f"No more jobs found after page {page_num}")
                    break
            else:
                empty_pages = 0
                urls_on_page = set(urls) - self._url_cache
                new_urls.update(urls_on_page)
                self._url_cache.update(urls)
                logger.info(f"Page {page_num}: Found {len(urls)} jobs, {len(urls_on_page)} new")
            
            # Save progress
            self._save_url_cache()
            
            # Delay between pages
            if page_num < max_pages:
                self.random_delay()
        
        return new_urls
    
    def _get_jobs_from_listing_page(self, page: int) -> List[str]:
        """Get job URLs from a single listing page."""
        url = f"{self.LISTING_URL}?page={page}" if page > 1 else self.LISTING_URL
        logger.debug(f"Fetching listing page: {url}")
        
        try:
            self._update_session_headers()
            response = self.session.get(url, timeout=30)
            
            # Handle rate limiting
            if response.status_code == 429:
                logger.warning(f"Rate limited on page {page}, waiting 60s...")
                time.sleep(60)
                return self._get_jobs_from_listing_page(page)  # Retry
            
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Error fetching listing page {page}: {e}")
            return []
        
        soup = BeautifulSoup(response.text, "lxml")
        job_cards = soup.select(".job-item-2")
        
        job_urls = []
        for card in job_cards:
            link_tag = card.select_one("a.job-item-2__title") or card.select_one("a[href*='viec-lam']")
            if link_tag:
                href = link_tag.get("href", "")
                if "/viec-lam/" in href:
                    # Clean URL (remove query params)
                    clean_url = href.split("?")[0]
                    if clean_url.endswith(".html"):
                        job_urls.append(clean_url)
        
        self.request_count += 1
        return job_urls
    
    def _download_job_pages(self, urls: Set[str]):
        """Download job detail pages."""
        success = 0
        failed = 0
        
        urls_list = list(urls)
        for i, url in enumerate(urls_list):
            file_path = self._get_file_path_for_url(url)
            
            # Skip if already downloaded
            if file_path.exists():
                continue
            
            logger.info(f"[{i+1}/{len(urls_list)}] Downloading: {url[:60]}...")
            
            if self._download_single_page(url, file_path):
                success += 1
                logger.debug(f"  ✓ Saved to {file_path.name}")
            else:
                failed += 1
                # Retry with longer delay
                wait_time = 30 + random.uniform(10, 30)
                logger.warning(f"  ✗ Failed, waiting {wait_time:.0f}s for retry...")
                time.sleep(wait_time)
                
                if self._download_single_page(url, file_path):
                    success += 1
                    failed -= 1
                    logger.info(f"  ✓ Retry successful")
            
            # Delay between downloads
            self.random_delay()
        
        logger.info(f"Download phase complete: {success} success, {failed} failed")
    
    def _download_single_page(self, url: str, file_path: Path) -> bool:
        """Download a single job detail page."""
        try:
            self._update_session_headers()
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 429:
                return False
            
            response.raise_for_status()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            self.request_count += 1
            return True
            
        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            return False
    
    def _parse_phase(self) -> Generator[Dict[str, Any], None, None]:
        """Phase 2: Parse downloaded HTML files."""
        html_files = list(self.download_dir.glob("*.html"))
        logger.info(f"Found {len(html_files)} HTML files to parse")
        
        for i, file_path in enumerate(html_files):
            # Find corresponding URL
            url = self._find_url_for_file(file_path)
            
            try:
                job_data = self._parse_html_file(file_path, url)
                if job_data:
                    logger.info(f"[{i+1}/{len(html_files)}] ✓ {job_data['title'][:50]}...")
                    yield job_data
                else:
                    logger.warning(f"[{i+1}/{len(html_files)}] ✗ Could not parse {file_path.name}")
            except Exception as e:
                logger.error(f"Error parsing {file_path.name}: {e}")
                self.error_count += 1
    
    def _find_url_for_file(self, file_path: Path) -> Optional[str]:
        """Find the original URL for a downloaded HTML file."""
        # Try to match by job ID in filename
        filename = file_path.stem
        if filename.isdigit():
            for url in self._url_cache:
                if f"/{filename}.html" in url:
                    return url
        
        # Fallback: return None if URL can't be determined
        return None
    
    def _parse_html_file(self, file_path: Path, url: Optional[str]) -> Optional[Dict[str, Any]]:
        """Parse a single HTML file into job data."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html = f.read()
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return None
        
        soup = BeautifulSoup(html, "lxml")
        
        # Extract job data
        job = {
            "source": "topcv",
            "source_url": url,
            "crawled_at": datetime.now(),
        }
        
        # Title
        title_el = soup.select_one("h1.job-detail__info--title")
        job["title"] = title_el.get_text(strip=True) if title_el else None
        
        if not job["title"]:
            return None
        
        # Company
        company_el = soup.select_one(".company-name-label a.name")
        job["company_name"] = company_el.get_text(strip=True) if company_el else None
        
        # Salary
        salary_el = soup.select_one(".section-salary .job-detail__info--section-content-value")
        salary_text = salary_el.get_text(strip=True) if salary_el else None
        job["salary_text"] = salary_text
        job["salary_min"], job["salary_max"] = self.parse_salary_range(salary_text) if salary_text else (None, None)
        
        # Location
        location_el = soup.select_one(".company-address .company-value")
        job["location"] = location_el.get_text(strip=True) if location_el else None
        
        # Experience
        exp_el = soup.select_one(".section-experience .job-detail__info--section-content-value")
        exp_text = exp_el.get_text(strip=True) if exp_el else None
        job["experience_years_min"], job["experience_years_max"] = self._parse_experience(exp_text)
        
        # Description, Requirements, Benefits
        description_parts = []
        requirements_parts = []
        benefits = []
        
        sections = soup.select(".job-description__item")
        for section in sections:
            heading_el = section.select_one("h3") or section.select_one("strong")
            content_el = section.select_one(".job-description__item--content")
            
            if content_el:
                heading_text = heading_el.get_text(strip=True).lower() if heading_el else ""
                content_text = content_el.get_text(strip=True)
                
                if "mô tả" in heading_text or "công việc" in heading_text:
                    description_parts.append(content_text)
                elif "yêu cầu" in heading_text:
                    requirements_parts.append(content_text)
                elif any(kw in heading_text for kw in ["quyền lợi", "phúc lợi", "đãi ngộ"]):
                    # Extract list items
                    li_items = content_el.select("li")
                    if li_items:
                        benefits.extend([li.get_text(strip=True) for li in li_items])
                    else:
                        # Parse line by line
                        for line in content_text.split('\n'):
                            line = line.strip()
                            if line.startswith('-'):
                                line = line[1:].strip()
                            if line and len(line) > 5:
                                benefits.append(line)
        
        # Additional benefits section
        benefit_section = soup.select_one(".job-detail__box--benefit, .box-benefit")
        if benefit_section:
            for li in benefit_section.select("li"):
                text = li.get_text(strip=True)
                if text and text not in benefits:
                    benefits.append(text)
        
        job["description"] = "\n".join(description_parts) if description_parts else None
        job["requirements_text"] = "\n".join(requirements_parts) if requirements_parts else None
        job["benefits"] = benefits
        
        # Skills
        skill_tags = soup.select(".job-tags__group-list-tag a.item")
        job["required_skills"] = [tag.get_text(strip=True) for tag in skill_tags]
        
        # Remote flag
        job["is_remote"] = "remote" in (url or "").lower() or "remote" in job["title"].lower()
        
        return job
    
    def parse_item(self, raw_data: Any) -> Dict[str, Any]:
        """Parse raw HTML into structured job data (required by BaseCrawler)."""
        # This is handled by _parse_html_file in this implementation
        return raw_data
    
    def parse_salary_range(self, salary_text: str) -> tuple:
        """Parse salary text to extract min and max values."""
        if not salary_text or "Thoả thuận" in salary_text or "Thỏa thuận" in salary_text:
            return None, None
        
        # Range: "10 - 20 triệu"
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*-\s*(\d+(?:[.,]\d+)?)', salary_text)
        if match:
            min_val = float(match.group(1).replace(',', '.'))
            max_val = float(match.group(2).replace(',', '.'))
            if "triệu" in salary_text.lower():
                min_val *= 1_000_000
                max_val *= 1_000_000
            return int(min_val), int(max_val)
        
        # From: "Từ 10 triệu"
        from_match = re.search(r'(?:từ|trên)\s*(\d+(?:[.,]\d+)?)', salary_text, re.IGNORECASE)
        if from_match:
            val = float(from_match.group(1).replace(',', '.'))
            if "triệu" in salary_text.lower():
                val *= 1_000_000
            return int(val), None
        
        # Single value: "15 triệu"
        single_match = re.search(r'(\d+(?:[.,]\d+)?)', salary_text)
        if single_match:
            val = float(single_match.group(1).replace(',', '.'))
            if "triệu" in salary_text.lower():
                val *= 1_000_000
            return int(val), int(val)
        
        return None, None
    
    def _parse_experience(self, exp_text: str) -> tuple:
        """Parse experience text to extract min and max years."""
        if not exp_text:
            return None, None
        
        exp_lower = exp_text.lower()
        
        # No experience required
        if "không yêu cầu" in exp_lower or "chưa có" in exp_lower:
            return 0, 0
        
        # Under X years: "Dưới 1 năm"
        if "dưới" in exp_lower:
            match = re.search(r'(\d+)', exp_text)
            if match:
                return 0, int(match.group(1))
            return 0, 1
        
        # Range: "2 - 5 năm"
        match = re.search(r'(\d+)\s*-\s*(\d+)', exp_text)
        if match:
            return int(match.group(1)), int(match.group(2))
        
        # Single value: "3 năm"
        single_match = re.search(r'(\d+)', exp_text)
        if single_match:
            years = int(single_match.group(1))
            return years, years
        
        return None, None
