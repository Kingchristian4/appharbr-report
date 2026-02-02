#!/usr/bin/env python3
"""
Publish reports to GitHub Pages
===============================
Copies reports to docs/ folder and updates index.html
"""

import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


def get_report_files(docs_dir: Path) -> list:
    """Get all report files sorted by date (newest first)"""
    reports = []
    for f in docs_dir.glob("report_*.html"):
        # Extract date from filename
        match = re.search(r'report_(\d{4}-\d{2}-\d{2})\.html', f.name)
        if match:
            date_str = match.group(1)
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            reports.append({
                'file': f.name,
                'date': date_obj.strftime('%B %d, %Y'),
                'sort_key': date_str
            })

    # Sort by date, newest first
    reports.sort(key=lambda x: x['sort_key'], reverse=True)
    return reports


def generate_index(docs_dir: Path, reports: list) -> None:
    """Generate index.html with report links"""

    report_items = ""
    for report in reports:
        report_items += f'''
            <a href="{report['file']}" class="report-link">
                <div class="report-date">📄 {report['date']}</div>
                <div class="report-desc">Daily Intelligence Report</div>
            </a>
'''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AppHarbr Intelligence Reports</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
        }}
        header {{
            text-align: center;
            margin-bottom: 40px;
        }}
        h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .subtitle {{
            color: #94a3b8;
            font-size: 1.1rem;
        }}
        .reports {{
            display: flex;
            flex-direction: column;
            gap: 15px;
        }}
        .report-link {{
            display: block;
            background: #1e293b;
            padding: 20px 25px;
            border-radius: 12px;
            text-decoration: none;
            color: #e2e8f0;
            border: 1px solid #334155;
            transition: all 0.2s;
        }}
        .report-link:hover {{
            background: #253348;
            border-color: #60a5fa;
            transform: translateX(5px);
        }}
        .report-date {{
            font-size: 1.2rem;
            font-weight: 600;
            color: #60a5fa;
        }}
        .report-desc {{
            color: #94a3b8;
            margin-top: 5px;
        }}
        .stats {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin: 30px 0;
        }}
        .stat {{
            text-align: center;
        }}
        .stat-value {{
            font-size: 2rem;
            font-weight: bold;
            color: #60a5fa;
        }}
        .stat-label {{
            color: #94a3b8;
            font-size: 0.9rem;
        }}
        footer {{
            text-align: center;
            margin-top: 60px;
            color: #64748b;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔔 AppHarbr Intelligence</h1>
            <p class="subtitle">Ad Fraud & Scam Advertising Reports</p>
        </header>

        <div class="stats">
            <div class="stat">
                <div class="stat-value">{len(reports)}</div>
                <div class="stat-label">Reports</div>
            </div>
        </div>

        <div class="reports">
            {report_items}
        </div>

        <footer>
            <p>Updated every 3 days • Last update: {datetime.now().strftime('%B %d, %Y at %H:%M')}</p>
        </footer>
    </div>
</body>
</html>'''

    with open(docs_dir / 'index.html', 'w') as f:
        f.write(html)

    print(f"Generated index.html with {len(reports)} reports")


def copy_new_reports(output_dir: Path, docs_dir: Path) -> int:
    """Copy new reports from outputs to docs"""
    copied = 0
    for report in output_dir.glob("report_*.html"):
        dest = docs_dir / report.name
        if not dest.exists():
            shutil.copy(report, dest)
            print(f"Copied: {report.name}")
            copied += 1
    return copied


def git_push(repo_dir: Path) -> bool:
    """Commit and push to GitHub"""
    try:
        os.chdir(repo_dir)

        # Add all docs
        subprocess.run(['git', 'add', 'docs/'], check=True)

        # Check if there are changes
        result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
        if not result.stdout.strip():
            print("No changes to commit")
            return True

        # Commit
        date_str = datetime.now().strftime('%Y-%m-%d')
        subprocess.run([
            'git', 'commit', '-m', f'Update reports - {date_str}'
        ], check=True)

        # Push
        subprocess.run(['git', 'push'], check=True)
        print("Pushed to GitHub successfully")
        return True

    except subprocess.CalledProcessError as e:
        print(f"Git error: {e}")
        return False


def main():
    """Main publish workflow"""
    base_dir = Path(__file__).parent
    output_dir = base_dir / 'outputs'
    docs_dir = base_dir / 'docs'

    # Ensure docs dir exists
    docs_dir.mkdir(exist_ok=True)

    # Copy new reports
    copied = copy_new_reports(output_dir, docs_dir)
    print(f"Copied {copied} new report(s)")

    # Get all reports
    reports = get_report_files(docs_dir)

    # Generate index
    generate_index(docs_dir, reports)

    # Try to push to GitHub
    if (base_dir / '.git').exists():
        git_push(base_dir)
    else:
        print("\nNot a git repo yet. To set up GitHub:")
        print("1. Create repo 'appharbr-reports' on GitHub")
        print("2. Run: git init && git remote add origin git@github.com:Kingchristian4/appharbr-reports.git")
        print("3. Run: git add . && git commit -m 'Initial commit' && git push -u origin main")


if __name__ == '__main__':
    main()
