"""
TopDev Crawler - Crawl job postings from TopDev.vn

Uses Playwright to scrape TopDev's Next.js website with comprehensive extraction.
Features:
- JSON-LD structured data extraction
- Advanced salary parsing (USD/VND with K/M multipliers)
- Experience years parsing
- Section-based content extraction
- IT job filtering with 70+ keywords
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


def clean_text(text: str) -> str:
    """Clean and normalize text content."""
    if not text:
        return ''
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove leading/trailing whitespace
    text = text.strip()
    return text


def parse_salary_text(salary_str: str) -> Dict[str, Any]:
    """Parse salary text into structured format with USD/VND support.
    
    Examples:
        '$2000 - $3000' -> {min: 2000, max: 3000, currency: 'USD'}
        '20M - 30M VND' -> {min: 20000000, max: 30000000, currency: 'VND'}
        'Up to $5K' -> {min: None, max: 5000, currency: 'USD'}
    """
    result = {
        'salary_min': None,
        'salary_max': None,
        'salary_currency': None,
        'salary_text': salary_str
    }
    
    if not salary_str or salary_str.lower() in ['negotiable', 'competitive', 'attractive']:
        return result
    
    # Detect currency
    if '$' in salary_str or 'usd' in salary_str.lower():
        result['salary_currency'] = 'USD'
    elif 'vnd' in salary_str.lower() or 'vnđ' in salary_str.lower() or 'đ' in salary_str:
        result['salary_currency'] = 'VND'
    
    # Extract numbers with K/M multipliers
    numbers = re.findall(r'\$?([0-9,\.]+)\s*([KkMm]|Million)?', salary_str)
    
    if not numbers:
        return result
    
    def parse_number(num_str: str, multiplier: str = '') -> Optional[float]:
        """Parse number string with multiplier."""
        try:
            num = float(num_str.replace(',', ''))
            multiplier = multiplier.upper() if multiplier else ''
            
            if multiplier in ['K', 'THOUSAND']:
                return num * 1000
            elif multiplier in ['M', 'MILLION']:
                return num * 1000000
            else:
                # Auto-detect: if VND and number < 1000, likely in millions
                if result['salary_currency'] == 'VND' and num < 1000:
                    return num * 1000000
                return num
        except:
            return None
    
    parsed_nums = []
    for num_str, multiplier in numbers:
        parsed = parse_number(num_str, multiplier)
        if parsed:
            parsed_nums.append(parsed)
    
    if len(parsed_nums) >= 2:
        result['salary_min'] = int(min(parsed_nums))
        result['salary_max'] = int(max(parsed_nums))
    elif len(parsed_nums) == 1:
        # Single number - set as max if "up to", else as min
        if 'up to' in salary_str.lower() or 'upto' in salary_str.lower():
            result['salary_max'] = int(parsed_nums[0])
        else:
            result['salary_min'] = int(parsed_nums[0])
    
    return result


def parse_experience_years(exp_str: str) -> Dict[str, Any]:
    """Parse experience requirement text into min/max years.
    
    Examples:
        '5+ years' -> {min: 5, max: None}
        '3-5 years' -> {min: 3, max: 5}
        'No experience' -> {min: 0, max: 0}
    """
    result = {
        'experience_years_min': None,
        'experience_years_max': None
    }
    
    if not exp_str:
        return result
    
    exp_lower = exp_str.lower()
    
    # No experience required
    if any(keyword in exp_lower for keyword in ['no experience', 'fresher', 'entry level', 'intern']):
        result['experience_years_min'] = 0
        result['experience_years_max'] = 0
        return result
    
    # Extract numbers
    numbers = re.findall(r'(\d+)', exp_str)
    
    if not numbers:
        return result
    
    nums = [int(n) for n in numbers]
    
    if len(nums) >= 2:
        result['experience_years_min'] = min(nums)
        result['experience_years_max'] = max(nums)
    elif len(nums) == 1:
        if '+' in exp_str or 'more' in exp_lower or 'above' in exp_lower:
            result['experience_years_min'] = nums[0]
        else:
            result['experience_years_min'] = nums[0]
            result['experience_years_max'] = nums[0]
    
    return result


class TopDevCrawler(BaseCrawler):
    """Crawler for TopDev.vn job postings with comprehensive extraction."""
    
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
    
    # IT-related keywords for filtering (70+ keywords)
    IT_KEYWORDS = [
        # Developer roles
        'developer', 'engineer', 'programmer', 'coder', 'software', 'backend', 'frontend',
        'fullstack', 'full stack', 'full-stack', 'dev', 'coding',
        # Technologies & languages
        'java', 'python', 'javascript', 'js', 'typescript', 'react', 'angular', 'vue',
        'nodejs', 'node.js', '.net', 'dotnet', 'c#', 'c++', 'golang', 'go', 'ruby',
        'php', 'laravel', 'django', 'spring', 'kotlin', 'swift', 'flutter', 'dart',
        # Mobile
        'ios', 'android', 'mobile', 'app', 'react native',
        # DevOps & Infrastructure
        'devops', 'cloud', 'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'k8s',
        'jenkins', 'ci/cd', 'terraform', 'infrastructure', 'sre', 'sysadmin', 'linux',
        # Data & AI/ML
        'data', 'ai', 'ml', 'machine learning', 'data science', 'data engineer',
        'big data', 'analytics', 'bi', 'spark', 'hadoop', 'kafka', 'etl',
        # Database
        'database', 'dba', 'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'nosql',
        # Quality & Testing
        'qa', 'qc', 'tester', 'test', 'automation test', 'selenium',
        # Security
        'security', 'cybersecurity', 'infosec', 'penetration',
        # Architecture
        'architect', 'solution architect', 'tech lead', 'technical lead',
        # Other IT
        'api', 'rest', 'graphql', 'microservices', 'web', 'technical', 'it'
    ]
    
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
        """Run Playwright crawl in sync context with detailed job extraction."""
        from playwright.sync_api import sync_playwright
        
        all_jobs = []
        seen_urls = set()
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()
            
            try:
                # Step 1: Collect job URLs from listing pages
                job_urls = []
                for page_num in range(1, pages + 1):
                    url = self._build_search_url(keywords, location, page_num)
                    logger.info(f"Fetching TopDev listing page {page_num}/{pages}")
                    
                    page.goto(url, wait_until='domcontentloaded', timeout=60000)
                    time.sleep(3)
                    
                    # Extract job links from listing
                    content = page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    job_links = soup.find_all('a', href=re.compile(r'/detail-jobs/'))
                    for link in job_links:
                        href = link.get('href', '')
                        if href and href not in seen_urls:
                            full_url = f"{self.BASE_URL}{href}" if href.startswith('/') else href
                            if full_url not in seen_urls:
                                job_urls.append(full_url)
                                seen_urls.add(full_url)
                    
                    logger.info(f"Found {len(job_links)} job links on page {page_num} (total: {len(job_urls)})")
                    
                    if page_num < pages:
                        time.sleep(random.uniform(2, 4))
                
                # Step 2: Fetch detailed job information
                logger.info(f"\nFetching details for {len(job_urls)} jobs...")
                for idx, job_url in enumerate(job_urls, 1):
                    try:
                        logger.info(f"[{idx}/{len(job_urls)}] Fetching: {job_url}")
                        page.goto(job_url, wait_until='domcontentloaded', timeout=60000)
                        time.sleep(2)
                        
                        html_content = page.content()
                        job_data = self._extract_job_details(html_content, job_url)
                        
                        if job_data:
                            all_jobs.append(job_data)
                            logger.info(f"✓ Extracted: {job_data.get('title', 'Unknown')}")
                        
                        self.log_progress(len(all_jobs))
                        time.sleep(random.uniform(1, 2))
                        
                    except Exception as e:
                        logger.error(f"Error fetching job {job_url}: {e}")
                        continue
                        
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
    
    def _extract_job_details(self, html_content: str, job_url: str) -> Optional[Dict[str, Any]]:
        """Extract comprehensive job details from job detail page.
        
        Extraction methods:
        1. JSON-LD structured data (primary)
        2. Section-based extraction from HTML
        3. Regex fallbacks for missing data
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        job_data = {
            'source': 'topdev',
            'source_url': job_url,
            'crawled_at': datetime.now().isoformat()
        }
        
        # Method 1: Extract from JSON-LD structured data
        json_ld_scripts = soup.find_all('script', {'type': 'application/ld+json'})
        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                if data.get('@type') == 'JobPosting':
                    # Basic info
                    job_data['title'] = data.get('title', '')
                    job_data['company_name'] = data.get('hiringOrganization', {}).get('name', '')
                    job_data['skills'] = data.get('skills', '')
                    job_data['date_posted'] = data.get('datePosted', '')
                    job_data['valid_through'] = data.get('validThrough', '')
                    job_data['industry'] = data.get('industry', '')
                    
                    # Salary information
                    salary_info = data.get('baseSalary', {})
                    if salary_info:
                        value = salary_info.get('value', {})
                        salary_text = value.get('value', '')
                        if salary_text:
                            parsed_salary = parse_salary_text(str(salary_text))
                            job_data.update(parsed_salary)
                    
                    # Location
                    location = data.get('jobLocation', {}).get('address', {})
                    job_data['location'] = {
                        'city': location.get('addressLocality', ''),
                        'region': location.get('addressRegion', ''),
                        'country': location.get('addressCountry', ''),
                        'address': location.get('streetAddress', '')
                    }
                    
                    # Experience requirements
                    exp_req = data.get('experienceRequirements', {})
                    exp_months = exp_req.get('monthsOfExperience', '')
                    if exp_months:
                        try:
                            years = int(exp_months) // 12
                            job_data['experience_years_min'] = years
                        except:
                            pass
                    
                    # Employment type
                    job_data['employment_type'] = data.get('employmentType', [])
                    if isinstance(job_data['employment_type'], list) and job_data['employment_type']:
                        job_data['job_type'] = job_data['employment_type'][0]
                    
                    # Extract sections from description HTML
                    description_html = data.get('description', '')
                    if description_html:
                        desc_soup = BeautifulSoup(description_html, 'html.parser')
                        all_text = desc_soup.get_text()
                        
                        # Company Overview
                        overview_match = re.search(
                            r'1\.?\s*Company Overview\s*(.+?)(?=2\.?\s*Job Summary|\d+\.?\s*Your role|$)',
                            all_text, re.DOTALL | re.IGNORECASE
                        )
                        if overview_match:
                            job_data['company_overview'] = clean_text(overview_match.group(1))
                        
                        # Job Summary
                        summary_match = re.search(
                            r'2\.?\s*Job Summary\s*(.+?)(?=\d+\.?\s*Your role|1\s*Your role|$)',
                            all_text, re.DOTALL | re.IGNORECASE
                        )
                        if summary_match:
                            job_data['job_summary'] = clean_text(summary_match.group(1))
                        
                        # Level
                        level_match = re.search(r'<strong>•\s*Level:</strong>\s*([^<&\n]+)', description_html)
                        if level_match:
                            job_data['level'] = clean_text(level_match.group(1))
                        else:
                            level_match = re.search(r'•\s*Level:\s*([^\n\r•]+)', all_text, re.IGNORECASE)
                            if level_match:
                                job_data['level'] = clean_text(level_match.group(1))
                    
                    # Benefits
                    benefits_html = data.get('jobBenefits', '')
                    if benefits_html:
                        ben_soup = BeautifulSoup(benefits_html, 'html.parser')
                        benefits = []
                        for li in ben_soup.find_all('li'):
                            text = clean_text(li.get_text())
                            if text and len(text) > 10:
                                benefits.append(text)
                        if benefits:
                            job_data['benefits'] = json.dumps(benefits[:20])
                    
                    break
            except Exception as e:
                logger.debug(f"Error parsing JSON-LD: {e}")
                continue
        
        # Method 2: Extract sections from page text
        page_text = soup.get_text(separator='\n')
        
        # Responsibilities
        resp_text = self._extract_section(
            page_text,
            'Your role & responsibilities',
            ['Your skills & qualifications', 'Why you', 'Benefits']
        )
        if resp_text:
            job_data['responsibilities_text'] = resp_text
            resp_lines = [line.strip() for line in resp_text.split('\n') 
                         if line.strip() and len(line.strip()) > 15]
            job_data['responsibilities'] = resp_lines[:20]
        
        # Qualifications
        qual_text = self._extract_section(
            page_text,
            'Your skills & qualifications',
            ['Why you', 'Benefits', 'Apply', 'How to']
        )
        if qual_text:
            job_data['qualifications_text'] = qual_text
            qual_lines = [line.strip() for line in qual_text.split('\n')
                         if line.strip() and len(line.strip()) > 15]
            job_data['qualifications'] = qual_lines[:20]
        
        # Method 3: Regex fallbacks for additional data
        if not job_data.get('responsibilities'):
            resp_match = re.search(
                r'Your role & responsibilities(.+?)(?=Your skills|2\s*Your skills|$)',
                html_content, re.DOTALL | re.IGNORECASE
            )
            if resp_match:
                resp_soup = BeautifulSoup(resp_match.group(1), 'html.parser')
                responsibilities = []
                for elem in resp_soup.find_all(['li', 'p']):
                    text = clean_text(elem.get_text())
                    if text and len(text) > 15:
                        responsibilities.append(text)
                job_data['responsibilities'] = responsibilities[:20]
        
        # Build combined description
        description_parts = []
        if job_data.get('company_overview'):
            description_parts.append("Company Overview:\n" + job_data['company_overview'])
        if job_data.get('job_summary'):
            description_parts.append("Job Summary:\n" + job_data['job_summary'])
        if job_data.get('responsibilities_text'):
            description_parts.append("Your role & responsibilities:\n" + job_data['responsibilities_text'])
        elif job_data.get('responsibilities'):
            description_parts.append("Your role & responsibilities:\n" + 
                                   '\n'.join([f"• {r}" for r in job_data['responsibilities']]))
        
        job_data['description'] = '\n\n'.join(description_parts) if description_parts else None
        
        # Build requirements text
        if job_data.get('qualifications_text'):
            job_data['requirements_text'] = "Your skills & qualifications:\n\n" + job_data['qualifications_text']
        elif job_data.get('qualifications'):
            job_data['requirements_text'] = "Your skills & qualifications:\n\n" + \
                                          '\n'.join([f"• {q}" for q in job_data['qualifications']])
        
        # Format location
        if isinstance(job_data.get('location'), dict):
            loc = job_data['location']
            job_data['location'] = f"{loc.get('city', '')}, {loc.get('region', '')}".strip(', ')
        
        # Extract skills as JSON array
        if job_data.get('skills'):
            if isinstance(job_data['skills'], str):
                skills_list = [s.strip() for s in job_data['skills'].split(',') if s.strip()]
                job_data['required_skills'] = json.dumps(skills_list[:30])
        
        return job_data if job_data.get('title') else None
    
    def _extract_section(self, text: str, start_marker: str, end_markers: List[str]) -> Optional[str]:
        """Extract a section of text between start and end markers."""
        start_idx = text.find(start_marker)
        if start_idx == -1:
            return None
        
        start_idx += len(start_marker)
        end_idx = len(text)
        
        for end_marker in end_markers:
            idx = text.find(end_marker, start_idx)
            if idx != -1 and idx < end_idx:
                end_idx = idx
        
        return text[start_idx:end_idx].strip()
    
    def _extract_jobs_from_html(self, html_content: str, seen_ids: set) -> List[Dict[str, Any]]:
        """Legacy method - Extract job data from Next.js hydration scripts."""
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
                salary_info = parse_salary_text(salary_text)
                job_data.update(salary_info)
            
            jobs.append(job_data)
        
        return jobs
    
    def parse_item(self, raw_data: Any) -> Dict[str, Any]:
        """Parse raw job data into structured format."""
        return raw_data if isinstance(raw_data, dict) else {}
