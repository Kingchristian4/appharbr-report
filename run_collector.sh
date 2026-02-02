#!/bin/bash
# AppHarbr Collector - Scheduled Runner
# This script is called by cron every 3 days

cd /Users/tobiassilber/Claude_c

# Run the collector
/usr/bin/python3 main.py --config config.yaml --max 100

# Publish to GitHub Pages
/usr/bin/python3 publish.py

# Log completion
echo "$(date): Collection and publish completed" >> /Users/tobiassilber/Claude_c/logs/cron.log
