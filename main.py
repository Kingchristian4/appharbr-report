#!/usr/bin/env python3
"""
AppHarbr Collector - Main Entry Point
=====================================
Orchestrates article collection from search engines.

Usage:
    python main.py                    # Run with default config
    python main.py --config my.yaml   # Run with custom config
    python main.py --keywords "AI security" "mobile threats"  # Quick search
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from data_structures import (
    Article,
    ArticleStatus,
    CollectionRun,
    CollectorConfig,
    SearchQuery,
)
from collector import SearchCollector
from parser import ArticleParser
from storage import ArticleStorage
from notifier import SlackNotifier
from report import ReportGenerator


def setup_logging(log_dir: str = "logs", verbose: bool = False) -> None:
    """Configure logging"""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                log_path / f"collector_{datetime.now().strftime('%Y-%m-%d')}.log"
            )
        ]
    )


def run_collection(config: CollectorConfig) -> CollectionRun:
    """
    Main collection pipeline.

    1. Search for articles
    2. Deduplicate against seen URLs
    3. Parse article content
    4. Save results
    5. Send notification
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting collection run...")

    # Initialize components
    collector = SearchCollector(target_sites=config.target_sites)
    parser = ArticleParser()
    storage = ArticleStorage(config.output_dir)
    notifier = SlackNotifier(config.slack_webhook_url)

    if config.target_sites:
        logger.info(f"Restricting search to sites: {', '.join(config.target_sites)}")

    # Start run
    run = CollectionRun(config=config, start_time=datetime.now())

    # Load previously seen URLs for deduplication
    if config.enable_deduplication:
        seen_urls = storage.get_seen_urls()
        run.cache.seen_urls = seen_urls
        logger.info(f"Loaded {len(seen_urls)} previously seen URLs")

    # Execute searches
    for query in config.search_queries:
        logger.info(f"Searching for: {' '.join(query.keywords)}")

        try:
            results = collector.search(query)
            run.search_results.extend(results)

            for result in results:
                for article in result.articles:
                    # Check against max articles limit
                    if len(run.articles) >= config.max_articles_per_run:
                        logger.info(f"Reached max articles limit ({config.max_articles_per_run})")
                        break

                    # Add to run (handles deduplication)
                    run.add_article(article)

        except Exception as e:
            error_msg = f"Search failed for '{' '.join(query.keywords)}': {str(e)}"
            logger.error(error_msg)
            run.errors.append(error_msg)

    logger.info(f"Found {len(run.articles)} articles ({len(run.new_articles)} new)")

    # Parse article content
    articles_to_parse = [a for a in run.articles if a.status == ArticleStatus.NEW]
    logger.info(f"Parsing {len(articles_to_parse)} articles...")

    for i, article in enumerate(articles_to_parse):
        try:
            parser.parse(article)
            if (i + 1) % 10 == 0:
                logger.info(f"Parsed {i + 1}/{len(articles_to_parse)} articles")
        except Exception as e:
            article.status = ArticleStatus.FAILED
            article.error_message = str(e)
            run.errors.append(f"Parse failed for {article.url}: {str(e)}")

    # Generate HTML report with relevance scoring
    report_generator = ReportGenerator(config.output_dir)
    report_path = None

    if run.new_articles:
        # Score articles by relevance
        report_generator.score_articles(run.new_articles)

        # Sort by relevance for notification
        run.articles.sort(key=lambda a: a.relevance_score or 0, reverse=True)

        # Generate HTML report
        report_path = report_generator.generate_html_report(run.new_articles)
        logger.info(f"Generated HTML report: {report_path}")

    # Save results
    if config.backup_to_json:
        new_articles = run.new_articles
        if new_articles:
            storage.save_articles(new_articles)
            storage.export_daily_report(new_articles)

        # Update seen URLs
        all_urls = {a.url for a in run.articles}
        storage.save_seen_urls(all_urls)

        # Save run summary
        storage.save_run_summary(run)

    # Send notification with report link
    if config.slack_webhook_url and run.new_articles:
        try:
            payload = run.create_notification_payload()
            if notifier.send_with_report(payload, report_path):
                run.notification_sent = True
        except Exception as e:
            run.errors.append(f"Notification failed: {str(e)}")

    # Final summary
    summary = run.get_summary()
    logger.info(f"Collection complete in {summary['duration_seconds']}s")
    logger.info(f"  Total: {summary['total_articles']}, New: {summary['new_articles']}, "
                f"Duplicates: {summary['duplicates']}, Failed: {summary['failed']}")

    if run.errors:
        logger.warning(f"  {len(run.errors)} errors occurred")

    return run


def create_default_config(keywords: list = None) -> CollectorConfig:
    """Create a default configuration"""
    if keywords is None:
        keywords = ["mobile app security", "app store malware"]

    queries = [
        SearchQuery(
            keywords=keywords,
            max_results=20,
            sources=["google", "duckduckgo"],
        )
    ]

    return CollectorConfig(
        search_queries=queries,
        max_articles_per_run=50,
        enable_deduplication=True,
        backup_to_json=True,
        output_dir="outputs",
        log_dir="logs",
    )


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="AppHarbr Article Collector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py
  python main.py --keywords "mobile security" "app threats"
  python main.py --config config.yaml
  python main.py --keywords "ransomware" --max 100 --verbose
        """
    )

    parser.add_argument(
        '--config', '-c',
        help='Path to YAML config file'
    )
    parser.add_argument(
        '--keywords', '-k',
        nargs='+',
        help='Search keywords (space-separated)'
    )
    parser.add_argument(
        '--max', '-m',
        type=int,
        default=50,
        help='Maximum articles to collect (default: 50)'
    )
    parser.add_argument(
        '--output', '-o',
        default='outputs',
        help='Output directory (default: outputs)'
    )
    parser.add_argument(
        '--slack-webhook',
        help='Slack webhook URL for notifications'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--no-parse',
        action='store_true',
        help='Skip article parsing (faster, less data)'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(verbose=args.verbose)
    logger = logging.getLogger(__name__)

    # Load or create config
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            logger.error(f"Config file not found: {args.config}")
            sys.exit(1)
        config = CollectorConfig.from_yaml(args.config)
    else:
        config = create_default_config(args.keywords)

    # Override with CLI args
    config.max_articles_per_run = args.max
    config.output_dir = args.output

    if args.slack_webhook:
        config.slack_webhook_url = args.slack_webhook

    # Run collection
    try:
        run = run_collection(config)

        # Print summary
        print("\n" + "=" * 50)
        print("COLLECTION SUMMARY")
        print("=" * 50)
        summary = run.get_summary()
        print(f"Duration: {summary['duration_seconds']}s")
        print(f"Articles found: {summary['total_articles']}")
        print(f"New articles: {summary['new_articles']}")
        print(f"Duplicates skipped: {summary['duplicates']}")
        print(f"Failed to parse: {summary['failed']}")
        print(f"Errors: {summary['error_count']}")
        print(f"Output: {config.output_dir}/")
        print("=" * 50)

        # Exit with error code if significant failures
        if summary['error_count'] > summary['total_articles'] / 2:
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
