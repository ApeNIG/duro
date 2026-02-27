# Skill: Web Scraper

## Description
Build and run web scrapers for data extraction from websites.

## When to Use
- User needs data from websites
- Monitoring for changes/updates
- Price tracking, property hunting, job searching

## Required Tools
- Python with Playwright (for JS-rendered sites)
- BeautifulSoup/lxml for parsing
- SQLite for deduplication
- Email/webhook for notifications

## Pattern
1. Identify target site structure
2. Choose rendering method (requests vs Playwright)
3. Build selectors for data extraction
4. Add deduplication layer (SQLite)
5. Set up notification (email, webhook)
6. Schedule for recurring runs

## Example Implementation
Reference: `C:\Users\sibag\property-scraper`

Key files:
- `scraper.py` - Main orchestration
- `sites/rightmove.py` - Site-specific scraper
- `storage.py` - SQLite deduplication
- `emailer.py` - Notification

## Guardrails
- Respect robots.txt
- Add delays between requests (2-5 seconds)
- Rotate user agents
- Handle rate limits gracefully
- Never scrape login-protected content without permission
- Store credentials in .env, never in code
