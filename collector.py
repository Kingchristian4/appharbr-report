"""
Search Collector for AppHarbr Collector
=======================================
Collects articles from various search sources.
"""

import logging
import time
from datetime import datetime
from typing import List, Optional
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup

from data_structures import Article, SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class SearchCollector:
    """Collects articles from search engines"""

    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }

    def __init__(self, delay_between_requests: float = 3.0, target_sites: List[str] = None):
        self.delay = delay_between_requests
        self.target_sites = target_sites or []
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)

    def search(self, query: SearchQuery) -> List[SearchResult]:
        """
        Execute search across configured sources.
        Returns list of SearchResults (one per source).
        """
        results = []

        for source in query.sources:
            try:
                if source.lower() == "google":
                    result = self._search_google(query)
                elif source.lower() == "bing":
                    result = self._search_bing(query)
                elif source.lower() == "duckduckgo":
                    result = self._search_duckduckgo(query)
                else:
                    logger.warning(f"Unknown source: {source}")
                    continue

                if result:
                    results.append(result)

                # Rate limiting
                time.sleep(self.delay)

            except Exception as e:
                logger.error(f"Search failed for {source}: {e}")

        return results

    def _build_site_query(self, keywords: str) -> str:
        """Build search query with site restrictions if configured"""
        if not self.target_sites:
            return keywords

        # Build site:x OR site:y query
        site_query = " OR ".join(f"site:{site}" for site in self.target_sites)
        return f"({keywords}) ({site_query})"

    def _search_google(self, query: SearchQuery) -> Optional[SearchResult]:
        """Search Google News"""
        keywords = ' '.join(query.keywords)
        full_query = self._build_site_query(keywords)
        encoded_query = quote_plus(full_query)

        # Use Google News search
        url = f"https://www.google.com/search?q={encoded_query}&tbm=nws&num={query.max_results}"

        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            articles = []

            # Google News results structure
            for item in soup.select('div.SoaBEf'):
                try:
                    link = item.select_one('a')
                    title_elem = item.select_one('div.MBeuO')

                    if link and title_elem:
                        article_url = link.get('href', '')
                        title = title_elem.get_text(strip=True)

                        # Skip if URL is excluded
                        if self._is_excluded(article_url, query.exclude_domains):
                            continue

                        articles.append(Article(
                            url=article_url,
                            title=title,
                            source="Google News",
                            discovered_at=datetime.now(),
                        ))
                except Exception as e:
                    logger.debug(f"Failed to parse Google result: {e}")
                    continue

            # Fallback: try alternative selectors
            if not articles:
                for item in soup.select('div.g'):
                    try:
                        link = item.select_one('a')
                        title_elem = item.select_one('h3')

                        if link and title_elem:
                            article_url = link.get('href', '')
                            if not article_url.startswith('http'):
                                continue

                            title = title_elem.get_text(strip=True)

                            if self._is_excluded(article_url, query.exclude_domains):
                                continue

                            articles.append(Article(
                                url=article_url,
                                title=title,
                                source="Google",
                                discovered_at=datetime.now(),
                            ))
                    except Exception:
                        continue

            logger.info(f"Google: found {len(articles)} articles for '{keywords}'")

            return SearchResult(
                articles=articles[:query.max_results],
                query=query,
                search_engine="google",
                timestamp=datetime.now(),
                total_found=len(articles),
            )

        except requests.RequestException as e:
            logger.error(f"Google search failed: {e}")
            return None

    def _search_bing(self, query: SearchQuery) -> Optional[SearchResult]:
        """Search Bing News"""
        keywords = ' '.join(query.keywords)
        full_query = self._build_site_query(keywords)
        encoded_query = quote_plus(full_query)

        url = f"https://www.bing.com/news/search?q={encoded_query}&count={query.max_results}"

        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            articles = []

            for item in soup.select('.news-card'):
                try:
                    link = item.select_one('a.title')
                    if not link:
                        link = item.select_one('a')

                    if link:
                        article_url = link.get('href', '')
                        title = link.get_text(strip=True)

                        if not article_url.startswith('http'):
                            continue

                        if self._is_excluded(article_url, query.exclude_domains):
                            continue

                        articles.append(Article(
                            url=article_url,
                            title=title,
                            source="Bing News",
                            discovered_at=datetime.now(),
                        ))
                except Exception:
                    continue

            # Fallback selector
            if not articles:
                for item in soup.select('a[href*="http"]'):
                    title = item.get_text(strip=True)
                    url = item.get('href', '')

                    if title and len(title) > 20 and url.startswith('http'):
                        if 'bing.com' not in url and 'microsoft.com' not in url:
                            if not self._is_excluded(url, query.exclude_domains):
                                articles.append(Article(
                                    url=url,
                                    title=title[:200],
                                    source="Bing",
                                    discovered_at=datetime.now(),
                                ))

            # Deduplicate by URL
            seen = set()
            unique_articles = []
            for a in articles:
                if a.url not in seen:
                    seen.add(a.url)
                    unique_articles.append(a)

            logger.info(f"Bing: found {len(unique_articles)} articles for '{keywords}'")

            return SearchResult(
                articles=unique_articles[:query.max_results],
                query=query,
                search_engine="bing",
                timestamp=datetime.now(),
                total_found=len(unique_articles),
            )

        except requests.RequestException as e:
            logger.error(f"Bing search failed: {e}")
            return None

    def _search_duckduckgo(self, query: SearchQuery) -> Optional[SearchResult]:
        """Search DuckDuckGo"""
        keywords = ' '.join(query.keywords)
        full_query = self._build_site_query(keywords)
        encoded_query = quote_plus(full_query)

        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            articles = []

            for item in soup.select('.result'):
                try:
                    link = item.select_one('.result__a')
                    if link:
                        article_url = link.get('href', '')
                        title = link.get_text(strip=True)

                        # DuckDuckGo uses redirect URLs, extract actual URL
                        if 'uddg=' in article_url:
                            from urllib.parse import parse_qs, urlparse
                            parsed = urlparse(article_url)
                            params = parse_qs(parsed.query)
                            if 'uddg' in params:
                                article_url = params['uddg'][0]

                        if not article_url.startswith('http'):
                            continue

                        if self._is_excluded(article_url, query.exclude_domains):
                            continue

                        articles.append(Article(
                            url=article_url,
                            title=title,
                            source="DuckDuckGo",
                            discovered_at=datetime.now(),
                        ))
                except Exception:
                    continue

            logger.info(f"DuckDuckGo: found {len(articles)} articles for '{keywords}'")

            return SearchResult(
                articles=articles[:query.max_results],
                query=query,
                search_engine="duckduckgo",
                timestamp=datetime.now(),
                total_found=len(articles),
            )

        except requests.RequestException as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            return None

    def _is_excluded(self, url: str, exclude_domains: List[str]) -> bool:
        """Check if URL domain is in exclude list"""
        if not exclude_domains:
            return False

        try:
            domain = urlparse(url).netloc.lower()
            for excluded in exclude_domains:
                if excluded.lower() in domain:
                    return True
        except Exception:
            pass

        return False
