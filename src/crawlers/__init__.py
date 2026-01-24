"""
Web Crawlers Package

Provides crawlers for various job posting websites.
Each crawler inherits from BaseCrawler and implements site-specific logic.

Available Crawlers:
- ITViecCrawler: For ITViec.com
- TopDevCrawler: For TopDev.vn
- TopCVCrawler: For TopCV.vn
- LinkedInCrawler: For LinkedIn.com
"""

from .base_crawler import BaseCrawler
from .itviec_crawler import ITViecCrawler
from .topdev_crawler import TopDevCrawler
from .topcv_crawler import TopCVCrawler
from .linkedin_crawler import LinkedInCrawler

__all__ = [
    'BaseCrawler',
    'ITViecCrawler',
    'TopDevCrawler',
    'TopCVCrawler',
    'LinkedInCrawler',
    'create_crawler',
]


def create_crawler(source: str, **kwargs):
    """
    Factory function to create a crawler based on source name.
    
    Args:
        source: Source name ('itviec', 'topdev', 'topcv', 'linkedin')
        **kwargs: Additional arguments passed to the crawler
        
    Returns:
        Crawler instance
        
    Raises:
        ValueError: If source is not recognized
        
    Example:
        >>> crawler = create_crawler('topcv', download_dir='data/topcv_html')
        >>> for job in crawler.crawl(max_pages=10):
        >>>     print(job)
    """
    crawlers = {
        'itviec': ITViecCrawler,
        'topdev': TopDevCrawler,
        'topcv': TopCVCrawler,
        'linkedin': LinkedInCrawler,
    }
    
    source_lower = source.lower()
    if source_lower not in crawlers:
        raise ValueError(
            f"Unknown source: {source}. "
            f"Available sources: {', '.join(crawlers.keys())}"
        )
    
    return crawlers[source_lower](**kwargs)
