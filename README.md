# AppHarbr Collector

**Automated intelligence gathering for ad fraud, scam ads, and political advertising.**

This tool collects and analyzes articles from targeted industry websites, scores them by relevance, generates HTML reports, and sends daily Slack notifications with key findings.

---

## Features

- 🔍 **Targeted Search**: Site-restricted searches across industry publications
- 🎯 **Relevance Scoring**: ML-powered scoring to surface the most important articles
- 📊 **HTML Reports**: Beautiful daily reports with article summaries and scores
- 🔔 **Slack Notifications**: Rich notifications with top articles and relevance indicators
- 🌐 **Web Publishing**: Automatic GitHub Pages deployment of reports
- 🔄 **Deduplication**: Smart caching to avoid processing duplicate articles
- 📝 **Comprehensive Logging**: Detailed logs for monitoring and debugging

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Searches

Edit `config.yaml` to customize:
- Target websites to search
- Search keywords and queries
- Maximum articles per run
- Output paths

### 3. Set Up Slack Notifications (Optional)

#### Create a Slack Webhook:

1. Go to https://api.slack.com/apps
2. Create a new app or select existing
3. Navigate to "Incoming Webhooks"
4. Activate and create a new webhook URL
5. Copy the webhook URL

#### Configure the webhook:

**Option A: Environment Variable (Recommended)**
```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

**Option B: Config File**

Create `config.local.yaml`:
```yaml
slack:
  webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

**Option C: Command Line**
```bash
python main.py --slack-webhook "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

### 4. Run Collection

```bash
# Run with default config
python main.py

# Run with custom config
python main.py --config config.yaml

# Quick search with keywords
python main.py --keywords "mobile security" "app threats"

# With Slack notifications
python main.py --slack-webhook "YOUR_WEBHOOK_URL"
```

---

## Slack Notification Features

The Slack integration provides rich, actionable notifications:

### 📊 Article Statistics
- Total articles found (new vs. total processed)
- Relevance breakdown (High 🟢 / Medium 🟡)

### 📑 Top Articles by Relevance
- Up to 10 most relevant articles
- Relevance score percentage (0-100%)
- Matched keywords for each article
- Color-coded relevance indicators:
  - 🟢 High (≥60%): Critical articles requiring attention
  - 🟡 Medium (30-59%): Noteworthy articles
  - ⚪ Low (<30%): General industry news

### 🔗 Web Report Link
- Direct link to full HTML report on GitHub Pages
- Includes all articles with full text and metadata

### ⚠️ Error Reporting
- Automatic alerts if collection errors occur
- Summary of failed searches or parsing issues

### Example Notification

```
🔔 AppHarbr Daily Intelligence
─────────────────────────────
42 new articles found (156 total processed)
🟢 High relevance: 8  |  🟡 Medium: 15

Top Articles by Relevance:
🟢 85% Major Ad Network Caught Serving Malware... `scam ads, malvertising, ad fraud`
🟢 78% New Phishing Campaign Targets Mobile Users... `phishing ads, mobile threats`
🟡 52% Political Ad Transparency Rules Updated... `political advertising, regulations`
🟡 45% Celebrity Deepfake Scams Surge in Q1... `deepfake ads, celebrity scam`

📄 View Full Report
```

---

## Configuration

### `config.yaml` Structure

```yaml
# Target websites for site-restricted searches
target_sites:
  - globalgamesforum.com
  - adexchanger.com
  - digiday.com

# Search queries
search_queries:
  - keywords:
      - "fake ads OR malvertising OR scam ads"
    max_results: 30
    sources:
      - google
      - duckduckgo

# Slack notifications
slack:
  webhook_url: null  # Set via environment or config.local.yaml

# Processing settings
max_articles_per_run: 100
enable_deduplication: true
backup_to_json: true

# Output paths
output_dir: "outputs"
log_dir: "logs"
```

### Configuration Priority

1. Command line arguments (highest)
2. `config.local.yaml` (local overrides, gitignored)
3. Environment variables (`SLACK_WEBHOOK_URL`)
4. `config.yaml` (default config)

---

## Project Structure

```
appharbr-report/
├── config.yaml              # Main configuration
├── config.local.yaml        # Local overrides (gitignored)
├── main.py                  # Entry point and orchestration
├── collector.py             # Search engine integration
├── parser.py                # Article content extraction
├── notifier.py              # Slack notification system
├── report.py                # HTML report generation
├── storage.py               # Data persistence
├── data_structures.py       # Data models
├── requirements.txt         # Python dependencies
├── run_collector.sh         # Shell script for automation
├── outputs/                 # JSON backups and data
│   ├── articles/            # Individual article JSONs
│   ├── reports/             # Daily summary reports
│   └── seen_urls.json       # Deduplication cache
├── docs/                    # HTML reports (published to GitHub Pages)
│   ├── index.html           # Report index
│   └── report_YYYY-MM-DD.html
└── logs/                    # Application logs
    └── collector_YYYY-MM-DD.log
```

---

## Automated Scheduling

### Using Cron (Linux/Mac)

```bash
# Run daily at 9 AM
0 9 * * * cd /path/to/appharbr-report && ./run_collector.sh >> logs/cron.log 2>&1
```

### Using Task Scheduler (Windows)

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., Daily at 9:00 AM)
4. Action: Start a program
   - Program: `python`
   - Arguments: `main.py --config config.yaml`
   - Start in: `C:\path\to\appharbr-report`

### Using GitHub Actions

```yaml
name: Daily Collection
on:
  schedule:
    - cron: '0 9 * * *'  # 9 AM UTC daily
  workflow_dispatch:

jobs:
  collect:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - run: pip install -r requirements.txt
      - run: python main.py
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
      - uses: actions/upload-artifact@v3
        with:
          name: reports
          path: outputs/
```

---

## Command Line Usage

```bash
# Basic usage
python main.py

# Custom config
python main.py --config my-config.yaml

# Quick keyword search
python main.py --keywords "ransomware" "malware"

# Limit article collection
python main.py --max 50

# Specify output directory
python main.py --output my-outputs

# Enable verbose logging
python main.py --verbose

# Skip article parsing (faster)
python main.py --no-parse

# Combine options
python main.py --keywords "phishing" --max 100 --verbose --slack-webhook "URL"
```

---

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_collector.py
```

### Code Style

```bash
# Format code
black .

# Lint
pylint *.py

# Type checking
mypy .
```

---

## Troubleshooting

### Slack Notifications Not Sending

1. **Check webhook URL**: Verify it starts with `https://hooks.slack.com/services/`
2. **Test webhook**:
   ```bash
   curl -X POST -H 'Content-type: application/json' \
     --data '{"text":"Test message"}' \
     YOUR_WEBHOOK_URL
   ```
3. **Check logs**: Look for errors in `logs/collector_*.log`
4. **Verify permissions**: Ensure webhook has permission to post to channel

### No Articles Found

1. **Check search queries**: Verify keywords in `config.yaml`
2. **Review target sites**: Ensure sites are accessible
3. **Check logs**: Look for search errors
4. **Test without site restriction**: Temporarily remove `target_sites` to verify search works

### Articles Not Parsed

1. **Check network connectivity**
2. **Review user agent**: Some sites block bots
3. **Increase timeout**: Adjust parser timeout in code
4. **Check logs**: Look for specific parsing errors

### Deduplication Not Working

1. **Verify `enable_deduplication: true`** in config
2. **Check `seen_urls.json`** exists in output directory
3. **Review logs**: Look for deduplication messages
4. **Delete cache**: Remove `seen_urls.json` to reset

---

## Security & Privacy

- **No credentials stored**: Webhook URL should be in environment variables
- **Rate limiting**: Respects search engine rate limits
- **User agent**: Identifies as legitimate research tool
- **Public data only**: Only collects publicly available articles
- **GDPR compliant**: No personal data collection

---

## License

MIT License - See LICENSE file for details

---

## Support

For issues, questions, or contributions:
- **GitHub Issues**: [Create an issue](https://github.com/Kingchristian4/appharbr-report/issues)
- **Documentation**: Check this README and code comments
- **Logs**: Review logs in `logs/` directory for debugging

---

## Roadmap

- [ ] Email notification support
- [ ] Advanced relevance scoring with ML models
- [ ] Multi-language support
- [ ] API endpoint for webhook integration
- [ ] Real-time monitoring dashboard
- [ ] Custom alert rules and thresholds

---

**Built with ❤️ for the AppHarbr team**
