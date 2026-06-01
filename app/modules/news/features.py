import re
from typing import Iterable

from app.modules.news.model import NewsArticle


class NewsFeatureEngineer:
    """
    Simple, explainable NLP features based on keyword/event detection.
    No pretrained models.
    """

    KEYWORDS = {
        "settlement": [r"\bsettle(d|ment)?\b", r"\bpayout(s)?\b", r"\bcompensation\b", r"\bclaim(s)? paid\b"],
        "regulatory": [r"\bregulator\b", r"\bfine(d)?\b", r"\bsanction(s)?\b", r"\blicen[sc]e\b", r"\bpenalt(y|ies)\b"],
        "lawsuit": [r"\blawsuit(s)?\b", r"\bsued\b", r"\bcourt\b", r"\blitigation\b"],
        "catastrophe": [r"\bflood(s)?\b", r"\bfire(s)?\b", r"\bcyclone(s)?\b", r"\bstorm(s)?\b", r"\bearthquake(s)?\b"],
    }

    WEIGHTS = {
        "settlement": 2.0,
        "regulatory": 3.0,
        "lawsuit": 2.5,
        "catastrophe": 2.0,
    }

    def __init__(self, articles: list[NewsArticle]):
        self.articles = articles or []

    def _text(self, a: NewsArticle) -> str:
        return f"{a.title} {a.content}".lower()

    def _match_any(self, text: str, patterns: Iterable[str]) -> bool:
        return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)

    def compute(self) -> dict:
        counts = {k: 0 for k in self.KEYWORDS.keys()}

        for a in self.articles:
            t = self._text(a)
            for k, patterns in self.KEYWORDS.items():
                if self._match_any(t, patterns):
                    counts[k] += 1

        adverse_event_count = sum(counts.values())
        news_risk_score = 0.0
        for k, c in counts.items():
            news_risk_score += self.WEIGHTS.get(k, 1.0) * c

        return {
            "adverse_event_count": adverse_event_count,
            "settlement_event_count": counts["settlement"],
            "regulatory_event_count": counts["regulatory"],
            "lawsuit_event_count": counts["lawsuit"],
            "catastrophe_event_count": counts["catastrophe"],
            "news_risk_score": round(news_risk_score, 4),
        }
