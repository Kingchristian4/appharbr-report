"""
Article Parser for AppHarbr Collector
=====================================
Fetches and parses article content from URLs.
"""

import re
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from data_structures import Article, ArticleStatus

logger = logging.getLogger(__name__)


class ArticleParser:
    """Parses article content from URLs"""

    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)

    def parse(self, article: Article) -> Article:
        """
        Fetch and parse article content.
        Updates the article in-place and returns it.
        """
        try:
            response = self.session.get(article.url, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract content
            article.content = self._extract_content(soup)
            article.summary = self._extract_summary(soup, article.content)
            article.author = self._extract_author(soup)
            article.published_date = self._extract_date(soup)

            # Update title if we got a better one
            page_title = self._extract_title(soup)
            if page_title and len(page_title) > len(article.title):
                article.title = page_title

            article.status = ArticleStatus.PARSED
            logger.info(f"Parsed: {article.title[:50]}...")

        except requests.RequestException as e:
            article.status = ArticleStatus.FAILED
            article.error_message = str(e)
            logger.warning(f"Failed to parse {article.url}: {e}")
        except Exception as e:
            article.status = ArticleStatus.FAILED
            article.error_message = f"Parse error: {str(e)}"
            logger.warning(f"Parse error for {article.url}: {e}")

        return article

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract article title"""
        # Try og:title first
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return og_title['content'].strip()

        # Try <title> tag
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text().strip()

        # Try h1
        h1 = soup.find('h1')
        if h1:
            return h1.get_text().strip()

        return None

    def _extract_content(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract main article content"""
        # Remove unwanted elements
        for tag in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'noscript']):
            tag.decompose()

        # Try article tag first
        article_tag = soup.find('article')
        if article_tag:
            return self._clean_text(article_tag.get_text())

        # Try common content containers
        for selector in ['[role="main"]', '.article-content', '.post-content', '.entry-content', '#content', 'main']:
            content = soup.select_one(selector)
            if content:
                return self._clean_text(content.get_text())

        # Fallback: find the div with the most <p> tags
        divs = soup.find_all('div')
        best_div = None
        max_paragraphs = 0

        for div in divs:
            p_count = len(div.find_all('p', recursive=False))
            if p_count > max_paragraphs:
                max_paragraphs = p_count
                best_div = div

        if best_div and max_paragraphs >= 2:
            return self._clean_text(best_div.get_text())

        # Last resort: just get body text
        body = soup.find('body')
        if body:
            return self._clean_text(body.get_text())[:5000]

        return None

    def _extract_summary(self, soup: BeautifulSoup, content: Optional[str]) -> Optional[str]:
        """Extract or generate article summary"""
        # Try meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc['content'].strip()

        # Try og:description
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            return og_desc['content'].strip()

        # Generate from content
        if content:
            # Take first ~200 chars, ending at a sentence
            summary = content[:300]
            last_period = summary.rfind('.')
            if last_period > 100:
                summary = summary[:last_period + 1]
            return summary.strip()

        return None

    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract article author"""
        # Try meta author
        meta_author = soup.find('meta', attrs={'name': 'author'})
        if meta_author and meta_author.get('content'):
            return meta_author['content'].strip()

        # Try schema.org author
        author_link = soup.find('a', rel='author')
        if author_link:
            return author_link.get_text().strip()

        # Try common author classes
        for selector in ['.author', '.byline', '[rel="author"]', '.post-author']:
            author = soup.select_one(selector)
            if author:
                text = author.get_text().strip()
                # Clean up "By Author Name" format
                text = re.sub(r'^by\s+', '', text, flags=re.IGNORECASE)
                if text and len(text) < 100:
                    return text

        return None

    def _extract_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Extract publication date"""
        # Try meta tags
        for attr in ['article:published_time', 'datePublished', 'pubdate']:
            meta = soup.find('meta', property=attr) or soup.find('meta', attrs={'name': attr})
            if meta and meta.get('content'):
                parsed = self._parse_date(meta['content'])
                if parsed:
                    return parsed

        # Try time tag
        time_tag = soup.find('time')
        if time_tag:
            datetime_attr = time_tag.get('datetime')
            if datetime_attr:
                parsed = self._parse_date(datetime_attr)
                if parsed:
                    return parsed

        return None

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats"""
        formats = [
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d',
            '%B %d, %Y',
            '%b %d, %Y',
        ]

        # Remove timezone info for simpler parsing
        date_str = re.sub(r'\+\d{2}:\d{2}$', '', date_str)
        date_str = date_str.replace('Z', '')

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        return None

    def _clean_text(self, text: str) -> str:
        """Clean extracted text"""
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove leading/trailing whitespace
        text = text.strip()
        return text
