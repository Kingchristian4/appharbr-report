"""
HTML Report Generator for AppHarbr Collector
=============================================
Generates daily HTML reports with relevance scoring.
"""

import re
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from data_structures import Article

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates HTML reports from collected articles"""

    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # Keywords with weights: higher weight = more important/specific
    # Weight 3: Highly specific, core terms
    # Weight 2: Important but broader terms
    # Weight 1: General/supporting terms
    WEIGHTED_KEYWORDS = {
        # Core ad fraud terms (weight 3)
        "malvertising": 3,
        "ad fraud": 3,
        "scam ads": 3,
        "fake ads": 3,
        "fraudulent advertising": 3,
        "deepfake ads": 3,
        "AI-generated scam ads": 3,

        # Specific scam types (weight 2.5)
        "celebrity scam ads": 2.5,
        "crypto scam ads": 2.5,
        "financial scam ads": 2.5,
        "investment scam ads": 2.5,
        "fake celebrity endorsements": 2.5,
        "phishing ads": 2.5,

        # Important terms (weight 2)
        "deceptive ads": 2,
        "misleading ads": 2,
        "ad scams": 2,
        "gambling ads": 2,
        "betting ads": 2,
        "romance scam ads": 2,
        "lottery scam ads": 2,
        "tech support scam ads": 2,
        "impersonation ads": 2,
        "synthetic media ads": 2,
        "manipulated media ads": 2,
        "counterfeit ads": 2,

        # Political advertising (weight 2)
        "political ad regulations": 2,
        "political ad compliance": 2,
        "political ad transparency": 2,
        "EU political ad regulations": 2,
        "US political ad laws": 2,
        "UK political ad rules": 2,

        # Supporting terms (weight 1.5)
        "political advertising": 1.5,
        "election advertising rules": 1.5,
        "political ad disclosure": 1.5,
        "campaign finance ads": 1.5,
        "political ad verification": 1.5,
        "political ad labeling": 1.5,
        "sponsored political content": 1.5,
        "issue advocacy ads": 1.5,
        "political ad restrictions": 1.5,

        # General terms (weight 1)
        "social engineering": 1,
    }

    # For backwards compatibility
    DEFAULT_KEYWORDS = list(WEIGHTED_KEYWORDS.keys())

    def calculate_relevance(self, article: Article, keywords: List[str] = None) -> tuple:
        """
        Calculate relevance score (0.0 to 1.0) based on weighted keyword matches.
        Returns (score, matched_keywords).

        Scoring factors:
        - Keyword weight (specificity)
        - Title match bonus (2x multiplier)
        - Frequency bonus (diminishing returns)
        - Multi-word phrase bonus
        """
        if keywords is None:
            keyword_weights = self.WEIGHTED_KEYWORDS
        else:
            # If custom keywords provided, give them all weight 2
            keyword_weights = {kw: 2 for kw in keywords}

        score = 0.0
        matched = []

        # Get text content
        title = article.title.lower()
        content = f"{article.summary or ''} {article.content or ''}".lower()
        full_text = f"{title} {content}"

        # Calculate max possible score for normalization
        max_possible = sum(keyword_weights.values()) * 2  # Assume all in title

        for keyword, weight in keyword_weights.items():
            kw_lower = keyword.lower()

            if kw_lower in full_text:
                matched.append(keyword)

                # Base score from weight
                kw_score = weight

                # Title match bonus (2x multiplier)
                if kw_lower in title:
                    kw_score *= 2.0

                # Multi-word phrase bonus (more specific = better)
                word_count = len(keyword.split())
                if word_count >= 3:
                    kw_score *= 1.3  # 30% bonus for 3+ word phrases
                elif word_count == 2:
                    kw_score *= 1.1  # 10% bonus for 2 word phrases

                # Frequency bonus (count occurrences, diminishing returns)
                count = full_text.count(kw_lower)
                if count > 1:
                    kw_score *= (1 + min(count - 1, 5) * 0.1)  # Up to 50% bonus

                score += kw_score

        # Normalize to 0-1 range
        normalized = min(score / max_possible, 1.0) if max_possible > 0 else 0

        # Sort matched keywords by weight (most important first)
        matched.sort(key=lambda k: keyword_weights.get(k, 1), reverse=True)

        return round(normalized, 2), matched

    def score_articles(self, articles: List[Article], keywords: List[str] = None) -> List[Article]:
        """Calculate and assign relevance scores and matched keywords to all articles"""
        for article in articles:
            if article.relevance_score is None:
                score, matched = self.calculate_relevance(article, keywords)
                article.relevance_score = score
                article.matched_keywords = matched
        return articles

    def generate_html_report(
        self,
        articles: List[Article],
        date: Optional[datetime] = None,
        title: str = "AppHarbr Daily Intelligence Report"
    ) -> str:
        """
        Generate HTML report with all articles and relevance scores.
        Returns the filepath to the generated report.
        """
        if date is None:
            date = datetime.now()

        # Score articles if not already scored
        self.score_articles(articles)

        # Sort by relevance score (highest first)
        sorted_articles = sorted(
            articles,
            key=lambda a: a.relevance_score or 0,
            reverse=True
        )

        # Generate HTML
        html = self._build_html(sorted_articles, date, title)

        # Save to file
        filename = f"report_{date.strftime('%Y-%m-%d')}.html"
        filepath = self.output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)

        logger.info(f"Generated HTML report: {filepath}")
        return str(filepath)

    def _build_html(self, articles: List[Article], date: datetime, title: str) -> str:
        """Build the HTML content"""

        # Count by relevance tier
        high_relevance = len([a for a in articles if (a.relevance_score or 0) >= 0.6])
        medium_relevance = len([a for a in articles if 0.3 <= (a.relevance_score or 0) < 0.6])
        low_relevance = len([a for a in articles if (a.relevance_score or 0) < 0.3])

        article_rows = []
        for i, article in enumerate(articles, 1):
            score = article.relevance_score or 0

            # Color based on score
            if score >= 0.6:
                score_class = "high"
                score_color = "#22c55e"
            elif score >= 0.3:
                score_class = "medium"
                score_color = "#f59e0b"
            else:
                score_class = "low"
                score_color = "#94a3b8"

            # Truncate summary
            summary = article.summary or article.content or "No summary available"
            if len(summary) > 200:
                summary = summary[:200] + "..."

            # Source badge
            source = article.source or "Unknown"

            # Matched keywords tags
            keywords_html = ""
            if article.matched_keywords:
                keyword_tags = "".join(
                    f'<span class="keyword">{kw}</span>'
                    for kw in article.matched_keywords[:6]  # Show top 6 keywords
                )
                keywords_html = f'<div class="keywords">{keyword_tags}</div>'

            article_rows.append(f'''
            <tr class="article-row {score_class}">
                <td class="rank">{i}</td>
                <td class="score">
                    <div class="score-bar">
                        <div class="score-fill" style="width: {score * 100}%; background: {score_color};"></div>
                    </div>
                    <span class="score-value">{score:.0%}</span>
                </td>
                <td class="content">
                    <a href="{article.url}" target="_blank" class="title">{article.title}</a>
                    <p class="summary">{summary}</p>
                    {keywords_html}
                    <div class="meta">
                        <span class="source">{source}</span>
                        {f'<span class="author">by {article.author}</span>' if article.author else ''}
                        {f'<span class="date">{article.published_date.strftime("%b %d, %Y")}</span>' if article.published_date else ''}
                    </div>
                </td>
            </tr>
            ''')

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - {date.strftime("%B %d, %Y")}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            line-height: 1.6;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        header {{
            text-align: center;
            padding: 40px 20px;
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border-radius: 16px;
            margin-bottom: 30px;
            border: 1px solid #334155;
        }}
        h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .date {{
            color: #94a3b8;
            font-size: 1.1rem;
        }}
        .stats {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-top: 20px;
            flex-wrap: wrap;
        }}
        .stat {{
            background: #1e293b;
            padding: 15px 25px;
            border-radius: 10px;
            border: 1px solid #334155;
        }}
        .stat-value {{
            font-size: 2rem;
            font-weight: bold;
        }}
        .stat-value.high {{ color: #22c55e; }}
        .stat-value.medium {{ color: #f59e0b; }}
        .stat-value.low {{ color: #94a3b8; }}
        .stat-value.total {{ color: #60a5fa; }}
        .stat-label {{
            color: #94a3b8;
            font-size: 0.9rem;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: #1e293b;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid #334155;
        }}
        th {{
            background: #334155;
            padding: 15px;
            text-align: left;
            font-weight: 600;
            color: #e2e8f0;
        }}
        td {{
            padding: 15px;
            border-bottom: 1px solid #334155;
            vertical-align: top;
        }}
        .rank {{
            width: 50px;
            text-align: center;
            font-weight: bold;
            color: #60a5fa;
        }}
        .score {{
            width: 120px;
        }}
        .score-bar {{
            height: 8px;
            background: #334155;
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 5px;
        }}
        .score-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s ease;
        }}
        .score-value {{
            font-size: 0.9rem;
            font-weight: 600;
        }}
        .title {{
            color: #60a5fa;
            text-decoration: none;
            font-weight: 600;
            font-size: 1.1rem;
            display: block;
            margin-bottom: 8px;
        }}
        .title:hover {{
            color: #93c5fd;
            text-decoration: underline;
        }}
        .summary {{
            color: #94a3b8;
            font-size: 0.95rem;
            margin-bottom: 10px;
        }}
        .keywords {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-bottom: 10px;
        }}
        .keyword {{
            background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 500;
        }}
        .meta {{
            display: flex;
            gap: 15px;
            font-size: 0.85rem;
            color: #64748b;
        }}
        .meta span {{
            background: #0f172a;
            padding: 3px 10px;
            border-radius: 4px;
        }}
        .article-row:hover {{
            background: #253348;
        }}
        .article-row.high .rank {{ color: #22c55e; }}
        .article-row.medium .rank {{ color: #f59e0b; }}
        footer {{
            text-align: center;
            padding: 30px;
            color: #64748b;
            font-size: 0.9rem;
        }}
        @media (max-width: 768px) {{
            h1 {{ font-size: 1.8rem; }}
            .stats {{ gap: 15px; }}
            .stat {{ padding: 10px 15px; }}
            .score {{ width: 80px; }}
            td {{ padding: 10px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔔 {title}</h1>
            <p class="date">{date.strftime("%B %d, %Y")}</p>
            <div class="stats">
                <div class="stat">
                    <div class="stat-value total">{len(articles)}</div>
                    <div class="stat-label">Total Articles</div>
                </div>
                <div class="stat">
                    <div class="stat-value high">{high_relevance}</div>
                    <div class="stat-label">High Relevance</div>
                </div>
                <div class="stat">
                    <div class="stat-value medium">{medium_relevance}</div>
                    <div class="stat-label">Medium Relevance</div>
                </div>
                <div class="stat">
                    <div class="stat-value low">{low_relevance}</div>
                    <div class="stat-label">Low Relevance</div>
                </div>
            </div>
        </header>

        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Relevance</th>
                    <th>Article</th>
                </tr>
            </thead>
            <tbody>
                {"".join(article_rows)}
            </tbody>
        </table>

        <footer>
            Generated by AppHarbr Collector at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </footer>
    </div>
</body>
</html>'''

        return html
