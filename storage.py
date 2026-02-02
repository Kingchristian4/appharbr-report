"""
Storage Module for AppHarbr Collector
=====================================
Handles saving and loading articles to/from JSON files.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

from data_structures import Article, ArticleStatus, CollectionRun

logger = logging.getLogger(__name__)


class ArticleStorage:
    """Handles article persistence to JSON files"""

    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # File paths
        self.articles_file = self.output_dir / "articles.json"
        self.seen_urls_file = self.output_dir / "seen_urls.json"
        self.runs_file = self.output_dir / "runs.json"

    def save_articles(self, articles: List[Article], append: bool = True) -> str:
        """
        Save articles to JSON file.
        Returns the filepath.
        """
        existing = []
        if append and self.articles_file.exists():
            try:
                with open(self.articles_file, 'r') as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, IOError):
                existing = []

        # Convert new articles to dicts
        new_data = [a.to_dict() for a in articles]

        # Combine and save
        all_articles = existing + new_data

        with open(self.articles_file, 'w') as f:
            json.dump(all_articles, f, indent=2, default=str)

        logger.info(f"Saved {len(new_data)} articles to {self.articles_file}")
        return str(self.articles_file)

    def load_articles(self) -> List[dict]:
        """Load all saved articles"""
        if not self.articles_file.exists():
            return []

        try:
            with open(self.articles_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load articles: {e}")
            return []

    def get_seen_urls(self) -> Set[str]:
        """Load set of previously seen URLs for deduplication"""
        if not self.seen_urls_file.exists():
            return set()

        try:
            with open(self.seen_urls_file, 'r') as f:
                data = json.load(f)
                return set(data.get('urls', []))
        except (json.JSONDecodeError, IOError):
            return set()

    def save_seen_urls(self, urls: Set[str]) -> None:
        """Save seen URLs for future deduplication"""
        # Load existing and merge
        existing = self.get_seen_urls()
        all_urls = existing.union(urls)

        with open(self.seen_urls_file, 'w') as f:
            json.dump({
                'urls': list(all_urls),
                'count': len(all_urls),
                'updated_at': datetime.now().isoformat()
            }, f, indent=2)

        logger.info(f"Saved {len(all_urls)} seen URLs")

    def save_run_summary(self, run: CollectionRun) -> None:
        """Append run summary to runs log"""
        existing_runs = []
        if self.runs_file.exists():
            try:
                with open(self.runs_file, 'r') as f:
                    existing_runs = json.load(f)
            except (json.JSONDecodeError, IOError):
                existing_runs = []

        existing_runs.append(run.get_summary())

        with open(self.runs_file, 'w') as f:
            json.dump(existing_runs, f, indent=2, default=str)

        logger.info(f"Saved run summary to {self.runs_file}")

    def export_daily_report(self, articles: List[Article], date: Optional[datetime] = None) -> str:
        """
        Export articles to a dated JSON file.
        Useful for daily snapshots.
        """
        if date is None:
            date = datetime.now()

        filename = f"articles_{date.strftime('%Y-%m-%d')}.json"
        filepath = self.output_dir / filename

        data = {
            'date': date.isoformat(),
            'count': len(articles),
            'articles': [a.to_dict() for a in articles]
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"Exported daily report: {filepath}")
        return str(filepath)

    def get_article_count(self) -> int:
        """Get total number of stored articles"""
        articles = self.load_articles()
        return len(articles)

    def clear_all(self) -> None:
        """Clear all stored data (use with caution)"""
        for filepath in [self.articles_file, self.seen_urls_file]:
            if filepath.exists():
                filepath.unlink()
        logger.warning("Cleared all stored data")
