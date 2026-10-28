# PULSE — Pop Culture Radar

Minimal dark news aggregator, covering **Games, Anime, Manga, Comics, Film**.

## How it works
- Public RSS feeds are fetched by `scripts/update_news.py` (Python standard library only).
- Github Actions runs `.github/workflows/update-news.yml` every two hours (UTC cron `17 */2 * * *`), and on manual dispatch.
- The static frontend renders `data/news.json`. Content links go to original publishers.
- The categorizer uses conservative headline/summary keyword heuristics; some articles may be misclassified.
- Unavailable feeds are skipped, and recent previously fetched stories are retained. Scheduled Actions are best-effort and may be delayed.
- Data includes headline, source, publication date, original URL, short RSS excerpt, and feed-provided image. No full articles are republished.

## Publish
GitHub repository Settings → Pages → Deploy from branch → `main` → `/ (root)`.
After merging the portal branch, open Actions → Refresh pop culture news → Run workflow to populate initial articles.

## Sources
IGN, GameSpot, PC Gamer, Anime News Network, ComicBook.com. Feeds are best-effort; publishers may change them. Add or remove sources in `FEEDS` inside `scripts/update_news.py`.

Original personal profile was on the repository's main branch before this change. Review the PR before replacing the current homepage.
