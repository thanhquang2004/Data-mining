"""
Base Crawler - Abstract base class for web crawlers.

Provides foundation for web crawlers with rate limiting, error handling, 
browser automation support (Playwright), and utility methods.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Generator
import time
import random
import logging
import re
from datetime import datetime, timedelta

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger(__name__)


class BaseCrawler(ABC):
    """Abstract base class for web crawlers with common functionality."""
    
    def __init__(self,
                 source: str,
                 delay_min: float = 2.0,
                 delay_max: float = 5.0,
                 max_retries: int = 3,
                 use_playwright: bool = False,
                 headless: bool = True):
        """
        Initialize base crawler.
        
        Args:
            source: Source name identifier
            delay_min: Minimum delay between requests (seconds)
            delay_max: Maximum delay between requests (seconds)
            max_retries: Maximum retry attempts
            use_playwright: Whether to use Playwright
            headless: Whether to run browser in headless mode
        """
        self.source = source
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_retries = max_retries
        self.request_count = 0
        self.error_count = 0
        self.success_count = 0
        self.use_playwright = use_playwright
        self.headless = headless
        self.start_time = None
    
    @abstractmethod
    def crawl(self, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """Crawl and yield items. Implement in subclasses."""
        pass
    
    @abstractmethod
    def parse_item(self, raw_data: Any) -> Dict[str, Any]:
        """Parse raw data into structured format. Implement in subclasses."""
        pass
    
    def random_delay(self):
        """Apply random delay between requests."""
        delay = random.uniform(self.delay_min, self.delay_max)
        time.sleep(delay)
    
    def get_headers(self) -> Dict[str, str]:
        """Get request headers with random User-Agent."""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
        
        return {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
    
    def handle_error(self, error: Exception, url: str) -> bool:
        """Handle errors with exponential backoff."""
        self.error_count += 1
        logger.error(f"Error crawling {url}: {error}")
        
        if self.error_count <= self.max_retries:
            wait_time = (2 ** self.error_count) * 10
            logger.info(f"Retrying in {wait_time}s...")
            time.sleep(wait_time)
            return True
        
        logger.error(f"Max retries exceeded for {url}")
        return False
    
    def parse_salary_range(self, salary_text: str) -> Dict[str, Any]:
        """Parse salary text to extract min, max, currency."""
        result = {'salary_min': None, 'salary_max': None, 'salary_currency': None}
        
        if not salary_text or salary_text.lower() in ['negotiable', 'thỏa thuận', 'n/a', 'competitive']:
            return result
        
        if '$' in salary_text or 'usd' in salary_text.lower():
            result['salary_currency'] = 'USD'
        elif 'vnd' in salary_text.lower() or 'vnđ' in salary_text.lower() or 'triệu' in salary_text.lower():
            result['salary_currency'] = 'VND'
        
        numbers = re.findall(r'[\d,.]+', salary_text)
        nums = [float(n.replace(',', '').replace('.', '')) for n in numbers if n]
        
        if not nums:
            return result
        
        if len(nums) == 1:
            result['salary_max'] = int(nums[0])
        elif len(nums) >= 2:
            result['salary_min'] = int(nums[0])
            result['salary_max'] = int(nums[1])
        
        if 'triệu' in salary_text.lower() or 'million' in salary_text.lower():
            if result['salary_min']:
                result['salary_min'] *= 1_000_000
            if result['salary_max']:
                result['salary_max'] *= 1_000_000
        
        return result
    
    def extract_experience_years(self, text: str) -> Dict[str, Optional[int]]:
        """Extract minimum and maximum experience years from text."""
        if not text:
            return {'min': None, 'max': None}
        
        text_lower = text.lower()
        
        range_match = re.search(r'(\d+)\s*(?:-|to|đến)\s*(\d+)\s*(?:năm|year)', text_lower)
        if range_match:
            return {'min': int(range_match.group(1)), 'max': int(range_match.group(2))}
        
        min_match = re.search(r'(?:at least|tối thiểu|ít nhất|over|trên)\s*(\d+)\s*(?:năm|year)', text_lower)
        if min_match:
            return {'min': int(min_match.group(1)), 'max': None}
        
        num_match = re.search(r'(\d+)\s*\+?\s*(?:năm|year)', text_lower)
        if num_match:
            return {'min': int(num_match.group(1)), 'max': None}
        
        return {'min': None, 'max': None}
    
    def start_crawl(self):
        """Mark the start of a crawl session."""
        self.start_time = datetime.now()
        logger.info(f"Starting {self.source} crawler")
    
    def log_progress(self, items_count: int):
        """Log crawling progress."""
        logger.info(f"Progress: {items_count} items | Errors: {self.error_count}")
    
    def log_completion(self):
        """Log crawling completion statistics."""
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
            logger.info(f"Crawl completed in {duration:.1f}s | Success: {self.success_count} | Errors: {self.error_count}")
