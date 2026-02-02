"""
Data Structures for AppHarbr Collector
======================================
Clean, typed data structures for article collection, storage, and notifications.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


# ==============================================================================
# CORE ARTICLE DATA
# ==============================================================================

class ArticleStatus(Enum):
    """Status of article processing"""
    NEW = "new"
    PARSED = "parsed"
    FAILED = "failed"
    DUPLICATE = "duplicate"


@dataclass
class Article:
    """
    Core article object representing a discovered article.

    This is the main data structure passed between components.
    """
    # Core identifiers
    url: str
    title: str

    # Metadata
    source: str  # e.g., "Google News", "Bing", "RSS"
    discovered_at: datetime

    # Content (populated by parser)
    summary: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[datetime] = None

    # Tags/Categories
    tags: List[str] = field(default_factory=list)
    relevance_score: Optional[float] = None  # 0.0 to 1.0
    matched_keywords: List[str] = field(default_factory=list)  # Keywords that matched

    # Processing state
    status: ArticleStatus = ArticleStatus.NEW
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON/storage"""
        data = asdict(self)
        data['discovered_at'] = self.discovered_at.isoformat()
        if self.published_date:
            data['published_date'] = self.published_date.isoformat()
        data['status'] = self.status.value
        return data

    @property
    def url_hash(self) -> str:
        """Generate unique hash for deduplication"""
        import hashlib
        return hashlib.md5(self.url.encode()).hexdigest()[:12]


# ==============================================================================
# SEARCH & COLLECTION
# ==============================================================================

@dataclass
class SearchQuery:
    """Configuration for a search operation"""
    keywords: List[str]
    date_range: Optional[tuple] = None  # (start_date, end_date)
    max_results: int = 50
    sources: List[str] = field(default_factory=lambda: ["google", "bing"])
    exclude_domains: List[str] = field(default_factory=list)
    language: str = "en"


@dataclass
class SearchResult:
    """Result from search engine"""
    articles: List[Article]
    query: SearchQuery
    search_engine: str
    timestamp: datetime
    total_found: int

    def get_new_articles(self, existing_urls: set) -> List[Article]:
        """Filter out already-seen articles"""
        return [a for a in self.articles if a.url not in existing_urls]


# ==============================================================================
# DEDUPLICATION & STATE
# ==============================================================================

@dataclass
class ArticleCache:
    """
    In-memory cache for deduplication.

    Keeps track of seen URLs to avoid duplicates within a session.
    """
    seen_urls: set = field(default_factory=set)
    seen_hashes: set = field(default_factory=set)
    articles_by_hash: Dict[str, Article] = field(default_factory=dict)

    def add(self, article: Article) -> bool:
        """
        Add article to cache.
        Returns True if new, False if duplicate.
        """
        url_hash = article.url_hash

        if url_hash in self.seen_hashes:
            return False

        self.seen_urls.add(article.url)
        self.seen_hashes.add(url_hash)
        self.articles_by_hash[url_hash] = article
        return True

    def is_duplicate(self, url: str) -> bool:
        """Check if URL already seen"""
        return url in self.seen_urls


# ==============================================================================
# NOTIFICATIONS
# ==============================================================================

@dataclass
class NotificationPayload:
    """Data for Slack/email notifications"""
    total_articles: int
    new_articles: int
    top_articles: List[Article]  # Top 3-5 articles
    dashboard_url: Optional[str] = None  # Optional external dashboard link
    timestamp: datetime = field(default_factory=datetime.now)
    errors: List[str] = field(default_factory=list)

    def to_slack_message(self) -> Dict[str, Any]:
        """Generate Slack message blocks"""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔔 AppHarbr Daily Intelligence"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{self.new_articles} new articles* found ({self.total_articles} total processed)"
                }
            }
        ]

        # Show top 5 articles
        if self.top_articles:
            article_lines = []
            for i, article in enumerate(self.top_articles[:5], 1):
                article_lines.append(f"{i}. <{article.url}|{article.title}>")

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Top Articles:*\n" + "\n".join(article_lines)
                }
            })

        if self.dashboard_url:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Dashboard"
                        },
                        "url": self.dashboard_url
                    }
                ]
            })

        if self.errors:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"⚠️ {len(self.errors)} errors occurred"
                    }
                ]
            })

        return {"blocks": blocks}


# ==============================================================================
# CONFIGURATION
# ==============================================================================

@dataclass
class CollectorConfig:
    """Master configuration object"""
    # Search settings
    search_queries: List[SearchQuery]

    # Target sites (restrict search to these domains)
    target_sites: List[str] = field(default_factory=list)

    # Slack notifications
    slack_webhook_url: Optional[str] = None

    # Processing options
    max_articles_per_run: int = 100
    enable_deduplication: bool = True
    backup_to_json: bool = True

    # Paths
    output_dir: str = "outputs"
    log_dir: str = "logs"

    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'CollectorConfig':
        """Load configuration from YAML file"""
        import os
        import yaml
        from pathlib import Path

        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)

        # Try to load local config with secrets
        yaml_dir = Path(yaml_path).parent
        local_config_path = yaml_dir / 'config.local.yaml'
        if local_config_path.exists():
            with open(local_config_path, 'r') as f:
                local_data = yaml.safe_load(f)
                # Merge local config (secrets) into main config
                if local_data and 'slack' in local_data:
                    if 'slack' not in data:
                        data['slack'] = {}
                    data['slack'].update(local_data['slack'])

        # Parse queries
        queries = [
            SearchQuery(
                keywords=q['keywords'],
                max_results=q.get('max_results', 50),
                sources=q.get('sources', ['google', 'bing'])
            )
            for q in data.get('search_queries', [])
        ]

        # Get webhook URL from config or environment variable
        webhook_url = data.get('slack', {}).get('webhook_url')
        if not webhook_url:
            webhook_url = os.environ.get('SLACK_WEBHOOK_URL')

        return cls(
            search_queries=queries,
            target_sites=data.get('target_sites', []),
            slack_webhook_url=webhook_url,
            max_articles_per_run=data.get('max_articles_per_run', 100),
            output_dir=data.get('output_dir', 'outputs'),
            log_dir=data.get('log_dir', 'logs')
        )


# ==============================================================================
# COLLECTION RUN STATE
# ==============================================================================

@dataclass
class CollectionRun:
    """
    Tracks the state of a single collection run.

    This is the main orchestration object that gets passed through
    the collection pipeline.
    """
    config: CollectorConfig
    start_time: datetime

    # State tracking
    cache: ArticleCache = field(default_factory=ArticleCache)
    articles: List[Article] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    # Results
    search_results: List[SearchResult] = field(default_factory=list)
    notification_sent: bool = False

    @property
    def new_articles(self) -> List[Article]:
        """Get articles that are actually new"""
        return [a for a in self.articles if a.status == ArticleStatus.NEW or a.status == ArticleStatus.PARSED]

    @property
    def duration(self) -> float:
        """Duration of run in seconds"""
        return (datetime.now() - self.start_time).total_seconds()

    def add_article(self, article: Article) -> bool:
        """
        Add article to run, handling deduplication.
        Returns True if added, False if duplicate.
        """
        if self.config.enable_deduplication:
            if not self.cache.add(article):
                article.status = ArticleStatus.DUPLICATE
                return False

        self.articles.append(article)
        return True

    def get_summary(self) -> Dict[str, Any]:
        """Get run summary for logging/reporting"""
        status_counts = {}
        for article in self.articles:
            status = article.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        source_counts = {}
        for article in self.articles:
            source_counts[article.source] = source_counts.get(article.source, 0) + 1

        return {
            "start_time": self.start_time.isoformat(),
            "duration_seconds": round(self.duration, 2),
            "total_articles": len(self.articles),
            "new_articles": len(self.new_articles),
            "duplicates": status_counts.get("duplicate", 0),
            "failed": status_counts.get("failed", 0),
            "status_breakdown": status_counts,
            "source_breakdown": source_counts,
            "searches_performed": len(self.search_results),
            "errors": self.errors,
            "error_count": len(self.errors),
            "notification_sent": self.notification_sent,
        }

    def create_notification_payload(self, dashboard_url: Optional[str] = None) -> NotificationPayload:
        """Create a notification payload from the current run state"""
        # Sort by relevance score to get top articles
        scored_articles = [a for a in self.new_articles if a.relevance_score is not None]
        scored_articles.sort(key=lambda a: a.relevance_score or 0, reverse=True)

        # If no scored articles, just take the first few new ones
        top_articles = scored_articles[:5] if scored_articles else self.new_articles[:5]

        return NotificationPayload(
            total_articles=len(self.articles),
            new_articles=len(self.new_articles),
            top_articles=top_articles,
            dashboard_url=dashboard_url,
            errors=self.errors,
        )
