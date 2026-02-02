"""
Notification Module for AppHarbr Collector
==========================================
Sends notifications via Slack webhooks.
"""

import logging
from typing import Optional

import requests

from data_structures import NotificationPayload

logger = logging.getLogger(__name__)


class SlackNotifier:
    """Sends notifications to Slack via webhooks"""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url

    def send(self, payload: NotificationPayload) -> bool:
        """
        Send notification to Slack.
        Returns True if successful.
        """
        if not self.webhook_url:
            logger.warning("No Slack webhook URL configured, skipping notification")
            return False

        message = payload.to_slack_message()

        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=10
            )
            response.raise_for_status()

            logger.info("Slack notification sent successfully")
            return True

        except requests.RequestException as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False

    def send_with_report(self, payload: NotificationPayload, report_path: Optional[str] = None) -> bool:
        """
        Send notification with relevance scores and report info.
        Returns True if successful.
        """
        if not self.webhook_url:
            logger.warning("No Slack webhook URL configured, skipping notification")
            return False

        # Count by relevance tier
        high = len([a for a in payload.top_articles if (a.relevance_score or 0) >= 0.6])
        medium = len([a for a in payload.top_articles if 0.3 <= (a.relevance_score or 0) < 0.6])

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
                    "text": f"*{payload.new_articles} new articles* found ({payload.total_articles} total processed)\n"
                            f"🟢 High relevance: {high}  |  🟡 Medium: {medium}"
                }
            },
            {
                "type": "divider"
            }
        ]

        # Add top articles with relevance scores
        if payload.top_articles:
            # Sort by relevance
            sorted_articles = sorted(
                payload.top_articles[:10],
                key=lambda a: a.relevance_score or 0,
                reverse=True
            )

            article_lines = []
            for article in sorted_articles:
                score = article.relevance_score or 0
                if score >= 0.6:
                    emoji = "🟢"
                elif score >= 0.3:
                    emoji = "🟡"
                else:
                    emoji = "⚪"

                # Show top 3 matched keywords
                keywords_str = ""
                if article.matched_keywords:
                    top_keywords = article.matched_keywords[:3]
                    keywords_str = f" `{', '.join(top_keywords)}`"

                article_lines.append(
                    f"{emoji} *{score:.0%}* <{article.url}|{article.title[:50]}{'...' if len(article.title) > 50 else ''}>{keywords_str}"
                )

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Top Articles by Relevance:*\n" + "\n".join(article_lines)
                }
            })

        # Add report info
        if report_path:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"📄 Full HTML report saved to: `{report_path}`"
                    }
                ]
            })

        # Add errors if any
        if payload.errors:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"⚠️ {len(payload.errors)} errors occurred during collection"
                    }
                ]
            })

        message = {"blocks": blocks}

        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=10
            )
            response.raise_for_status()

            logger.info("Slack notification with report sent successfully")
            return True

        except requests.RequestException as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False

    def send_simple(self, text: str) -> bool:
        """Send a simple text message"""
        if not self.webhook_url:
            logger.warning("No Slack webhook URL configured")
            return False

        try:
            response = requests.post(
                self.webhook_url,
                json={"text": text},
                timeout=10
            )
            response.raise_for_status()
            return True

        except requests.RequestException as e:
            logger.error(f"Failed to send Slack message: {e}")
            return False

    def send_error_alert(self, errors: list) -> bool:
        """Send an error alert to Slack"""
        if not self.webhook_url or not errors:
            return False

        message = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "⚠️ AppHarbr Collector Errors"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{len(errors)} errors occurred:*\n" +
                                "\n".join(f"• {e[:100]}" for e in errors[:5])
                    }
                }
            ]
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=10
            )
            response.raise_for_status()
            return True

        except requests.RequestException as e:
            logger.error(f"Failed to send error alert: {e}")
            return False


def send_notification(
    webhook_url: str,
    payload: NotificationPayload
) -> bool:
    """Convenience function for one-off notifications"""
    notifier = SlackNotifier(webhook_url)
    return notifier.send(payload)
