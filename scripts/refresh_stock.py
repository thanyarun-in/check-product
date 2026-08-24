name: Refresh SRM Stock data

on:
  schedule:
    # 07:30 Bangkok time (UTC+7) every day = 21:00 UTC the previous day
    - cron: '0 21 * * *'
  workflow_dispatch: {}   # lets you also trigger it manually from the Actions tab

permissions:
  contents: write

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Refresh product stock data from Google Sheet
        run: python3 scripts/refresh_stock.py

      - name: Commit and push if anything changed
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add index.html
          if git diff --staged --quiet; then
            echo "No changes to commit."
          else
            git commit -m "Auto-refresh SRM stock data"
            git push
          fi
