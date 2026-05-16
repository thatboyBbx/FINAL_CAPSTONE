"""
News Scraper — scrapes 4 Zimbabwean news sources for insurance-related articles,
performs VADER sentiment analysis, and inserts into the news_articles table.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, date, timedelta
from typing import Optional
from urllib.parse import urljoin, urlparse

from sqlalchemy.orm import Session

from app.infrastructure.scrapers.base_scraper import BaseScraper, ScraperResult
from app.infrastructure.scrapers.scraper_utils import (
    extract_text_from_html,
    find_insurer_mentions,
)

logger = logging.getLogger(__name__)

# ── Insurance keyword weights (used to boost/dampen VADER scores) ─────────────
_NEGATIVE_KEYWORDS = [
    "complaint", "instalment", "default", "curatorship", "liquidation",
    "fine", "suspended", "penalty", "fraud", "scandal", "dispute", "lawsuit",
    "crisis", "insolvent", "collapse", "failed", "unpaid",
]
_POSITIVE_KEYWORDS = [
    "profit", "dividend", "growth", "stability", "award", "rating",
    "expand", "launch", "innovation", "surplus", "record", "milestone",
    "increase", "improvement", "strong", "premium",
]
_INSURANCE_TERMS = [
    "insurance", "insurer", "reinsurance", "policy", "premium", "claim",
    "underwriting", "actuary", "ipec", "assurance", "life insurance",
    "short-term", "funeral",
]

# News sources: (name, url, article_selector_hint)
_SOURCES = [
    ("Zimbabwe Independent",  "https://www.theindependent.co.zw",          "/category/18/business"),
    ("The Herald",            "https://www.herald.co.zw",                    "/business"),
    ("NewsDay Zimbabwe",      "https://www.newsday.co.zw",                   "/business"),
    ("AllAfrica Zimbabwe",    "https://allafrica.com/zimbabwe/economy.html",  ""),
]


class NewsScraper(BaseScraper):
    scraper_name = "news"

    def __init__(self, lookback_days: int = 30):
        self.lookback_days = lookback_days
        self._vader = None

    def run(self, db: Session) -> ScraperResult:
        run_id = self.log_run_start(db)
        result = ScraperResult(run_id=run_id)

        insurer_names = self._get_insurer_names(db)
        cutoff_date = date.today() - timedelta(days=self.lookback_days)

        for source_name, base_url, path in _SOURCES:
            url = base_url + path if path else base_url
            try:
                articles = self._scrape_source(url, source_name, base_url, cutoff_date)
                for art in articles:
                    try:
                        ins, upd = self._process_article(db, art, insurer_names)
                        result.records_inserted += ins
                        result.records_updated  += upd
                    except Exception as exc:
                        msg = f"Article {art.get('url', '?')}: {exc}"
                        logger.debug("[news] %s", msg)
            except Exception as exc:
                msg = f"{source_name}: {exc}"
                logger.warning("[news] %s", msg)
                result.errors.append(msg)

        db.commit()
        status = "partial" if result.errors else "success"
        result.status = status
        self.log_run_complete(db, run_id, status, result.records_inserted, result.records_updated,
                              "; ".join(result.errors) if result.errors else None)
        return result

    # ── Source scraping ───────────────────────────────────────────────────────

    def _scrape_source(
        self, url: str, source_name: str, base_url: str, cutoff_date: date
    ) -> list[dict]:
        """Fetch source index page and extract article metadata."""
        try:
            resp = self._fetch_with_retry(url)
        except Exception as exc:
            logger.warning("[news] failed to fetch %s: %s", url, exc)
            return []

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        articles: list[dict] = []

        # Find article links — look for <a> tags within common article containers
        seen_urls: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full_url = urljoin(base_url, href)
            if full_url in seen_urls:
                continue
            # Skip non-article links (images, pages, anchors)
            if any(ext in href for ext in [".jpg", ".png", ".gif", "#", "mailto:"]):
                continue
            # Require same domain
            if urlparse(full_url).netloc != urlparse(base_url).netloc:
                continue

            title_text = a.get_text(strip=True)
            if len(title_text) < 20:
                continue

            # Quick relevance filter — must mention insurance terms
            if not self._is_relevant(title_text):
                continue

            seen_urls.add(full_url)
            articles.append({
                "url":    full_url,
                "title":  title_text,
                "source": source_name,
                "published_date": date.today(),  # will be refined when fetching article
            })

            if len(articles) >= 50:  # cap per source
                break

        # Fetch each article for full content + precise date
        enriched: list[dict] = []
        for art in articles[:20]:  # limit full fetches to 20 per source
            try:
                full = self._fetch_article(art["url"], art, base_url, cutoff_date)
                if full:
                    enriched.append(full)
            except Exception:
                pass

        return enriched

    def _fetch_article(self, url: str, meta: dict, base_url: str, cutoff_date: date) -> dict | None:
        """Fetch and parse a single article page."""
        try:
            resp = self._fetch_with_retry(url, timeout=10)
        except Exception:
            return None

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract date
        pub_date = self._extract_date(soup, resp.text)
        if pub_date and pub_date < cutoff_date:
            return None  # Too old

        # Extract main content
        content = self._extract_article_content(soup)
        if not content or len(content) < 100:
            return None

        return {
            "url":            url,
            "title":          meta["title"],
            "source":         meta["source"],
            "published_date": pub_date or date.today(),
            "content":        content,
            "snippet":        content[:500],
        }

    def _extract_date(self, soup, raw_html: str) -> date | None:
        """Try to extract publication date from article page."""
        # Try <time> tag
        time_tag = soup.find("time")
        if time_tag:
            dt_str = time_tag.get("datetime") or time_tag.get_text(strip=True)
            parsed = self._parse_date_str(dt_str)
            if parsed:
                return parsed

        # Try meta tags
        for meta in soup.find_all("meta"):
            prop = meta.get("property", "") + meta.get("name", "")
            if "date" in prop.lower() or "published" in prop.lower():
                dt_str = meta.get("content", "")
                parsed = self._parse_date_str(dt_str)
                if parsed:
                    return parsed

        # Regex fallback in raw HTML
        m = re.search(r"(\d{4}-\d{2}-\d{2})", raw_html)
        if m:
            parsed = self._parse_date_str(m.group(1))
            if parsed:
                return parsed

        return None

    def _parse_date_str(self, s: str) -> date | None:
        if not s:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d %B %Y", "%B %d, %Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(s[:len(fmt) + 4], fmt).date()
            except ValueError:
                pass
        return None

    def _extract_article_content(self, soup) -> str:
        """Extract article body text, stripping nav/ads."""
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            tag.decompose()
        # Try common article content containers
        for selector in ["article", ".article-body", ".post-content", ".entry-content", "main"]:
            el = soup.select_one(selector)
            if el:
                return el.get_text(separator=" ", strip=True)
        return soup.get_text(separator=" ", strip=True)

    # ── Article processing ────────────────────────────────────────────────────

    def _process_article(self, db: Session, art: dict, insurer_names: list[str]) -> tuple[int, int]:
        """Match article to insurers, score sentiment, and upsert into news_articles."""
        from app.modules.news.model import NewsArticle

        # Dedup check
        existing = db.query(NewsArticle).filter(NewsArticle.url == art["url"]).first()

        content = art.get("content", art.get("title", ""))
        mentions = find_insurer_mentions(content, insurer_names, threshold=85)
        if not mentions:
            return 0, 0

        # Use top mention
        insurer_name = mentions[0][0]
        insurer_id = self._resolve_insurer_id(db, insurer_name)
        if not insurer_id:
            return 0, 0

        score, label = self._score_sentiment(content)
        keywords = self._extract_keywords(content)

        if existing:
            # Update sentiment if not already scored
            if existing.sentiment_score is None:
                existing.sentiment_score = score
                existing.sentiment_label = label
                existing.keywords = keywords
            return 0, 1

        article = NewsArticle(
            insurer_id=insurer_id,
            published_date=art["published_date"],
            source=art.get("source"),
            title=art["title"],
            content=content,
            url=art.get("url"),
            snippet=art.get("snippet", content[:500]),
            sentiment_score=score,
            sentiment_label=label,
            keywords=keywords,
        )
        db.add(article)
        return 1, 0

    # ── Sentiment ─────────────────────────────────────────────────────────────

    def _load_vader(self):
        if self._vader is None:
            try:
                import nltk
                try:
                    from nltk.sentiment.vader import SentimentIntensityAnalyzer
                    self._vader = SentimentIntensityAnalyzer()
                except LookupError:
                    nltk.download("vader_lexicon", quiet=True)
                    from nltk.sentiment.vader import SentimentIntensityAnalyzer
                    self._vader = SentimentIntensityAnalyzer()
            except Exception as exc:
                logger.warning("[news] VADER unavailable: %s", exc)
        return self._vader

    def _score_sentiment(self, text: str) -> tuple[float, str]:
        """Return (compound_score, label) using VADER with insurance keyword boosting."""
        vader = self._load_vader()
        if vader is None:
            return 0.0, "neutral"

        scores = vader.polarity_scores(text)
        compound = scores["compound"]

        # Keyword boosting
        text_lower = text.lower()
        neg_hits = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in text_lower)
        pos_hits = sum(1 for kw in _POSITIVE_KEYWORDS if kw in text_lower)
        compound = max(-1.0, min(1.0, compound - neg_hits * 0.03 + pos_hits * 0.02))

        if compound >= 0.05:
            label = "positive"
        elif compound <= -0.05:
            label = "negative"
        else:
            label = "neutral"

        return round(compound, 4), label

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract matched insurance keywords from article text."""
        text_lower = text.lower()
        found = []
        for kw in _NEGATIVE_KEYWORDS + _POSITIVE_KEYWORDS + _INSURANCE_TERMS:
            if kw in text_lower and kw not in found:
                found.append(kw)
        return found[:20]  # cap at 20

    def _is_relevant(self, text: str) -> bool:
        """Quick check: does text contain any insurance-related term?"""
        text_lower = text.lower()
        return any(term in text_lower for term in _INSURANCE_TERMS)

    # ── DB helpers ────────────────────────────────────────────────────────────

    def _get_insurer_names(self, db: Session) -> list[str]:
        from app.infrastructure.scrapers.scraper_utils import get_insurer_names
        return get_insurer_names(db)

    def _resolve_insurer_id(self, db: Session, name: str) -> int | None:
        from app.infrastructure.scrapers.scraper_utils import resolve_insurer_id
        return resolve_insurer_id(db, name, fuzzy=False)

    def parse_financial_data(self, raw_text: str) -> list[dict]:
        # Not used in news scraper but required by ABC
        return []
