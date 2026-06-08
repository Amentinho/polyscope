"""Claude-powered market analyst: matches news to markets and scores edge."""

import os
import json
import anthropic
from dataclasses import dataclass
from typing import Optional

from ingester.sources import NewsItem
from polymarket.client import Market
from analyst import cache as analysis_cache


ANALYST_MODEL = os.getenv("ANALYST_MODEL", "claude-opus-4-8")
TRIAGE_MODEL = os.getenv("TRIAGE_MODEL", "claude-haiku-4-5-20251001")

client = anthropic.Anthropic()


@dataclass
class Opportunity:
    market: Market
    news: list[NewsItem]
    side: str            # "YES" or "NO"
    market_price: float  # current market probability for our side
    analyst_prob: float  # Claude's estimated true probability
    edge: float          # analyst_prob - market_price (positive = we have edge)
    confidence: str      # "high" | "medium" | "low"
    rationale: str
    risk_flags: list[str]


def triage_news(items: list[NewsItem], markets: list[Market]) -> list[tuple[NewsItem, Market]]:
    """Fast triage: use Haiku to find news-market pairs worth deep analysis."""
    if not items or not markets:
        return []

    news_block = "\n".join(
        f"[N{i}] ({item.category}) {item.title}" for i, item in enumerate(items[:80])
    )
    market_block = "\n".join(
        f"[M{i}] {m.question} (YES={m.yes_price:.2f}, liq=${m.liquidity:,.0f})"
        for i, m in enumerate(markets[:100])
    )

    prompt = f"""You are a prediction market analyst. Match news items to prediction markets where the news likely changes the probability.

NEWS (recent):
{news_block}

MARKETS (open):
{market_block}

Return a JSON array of matches. Each match: {{"news_idx": int, "market_idx": int, "reason": "one line"}}
Only include high-signal matches where the news clearly informs the market outcome. Max 20 matches.
Return only the JSON array, no other text."""

    msg = client.messages.create(
        model=TRIAGE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        matches = json.loads(msg.content[0].text)
        return [
            (items[m["news_idx"]], markets[m["market_idx"]])
            for m in matches
            if m["news_idx"] < len(items) and m["market_idx"] < len(markets)
        ]
    except Exception:
        return []


def analyze_opportunity(news_items: list[NewsItem], market: Market) -> Optional[Opportunity]:
    """Deep analysis: use Opus to assess edge on a specific market given news."""
    news_ids = [n.id for n in news_items]
    cached = analysis_cache.get(news_ids, market.condition_id)
    if cached:
        result = cached
        side = result.get("side", "YES")
        market_price = market.yes_price if side == "YES" else market.no_price
        return Opportunity(
            market=market,
            news=news_items,
            side=side,
            market_price=market_price,
            analyst_prob=float(result["analyst_prob"]),
            edge=float(result["analyst_prob"]) - market_price,
            confidence=result.get("confidence", "low"),
            rationale="[cached] " + result.get("rationale", ""),
            risk_flags=result.get("risk_flags", []),
        )

    news_block = "\n\n".join(
        f"Source: {n.source}\nTitle: {n.title}\nBody: {n.body[:500]}" for n in news_items
    )

    prompt = f"""You are a professional prediction market analyst. Analyze whether current news creates a mispriced opportunity.

MARKET:
Question: {market.question}
Description: {market.description}
Current YES price: {market.yes_price:.3f} (implies {market.yes_price*100:.1f}% probability)
Current NO price: {market.no_price:.3f}
Liquidity: ${market.liquidity:,.0f}
Volume 24h: ${market.volume_24h:,.0f}
Closes: {market.end_date}

RECENT NEWS:
{news_block}

Assess the true probability of YES resolving, considering:
1. Direct information in the news
2. Base rates and historical precedent
3. Time remaining to resolution
4. Market efficiency (high liquidity = harder to beat)
5. Information gaps and unknowns

Return JSON only:
{{
  "analyst_prob": 0.0-1.0,
  "side": "YES" or "NO",
  "edge": float (your_prob - market_price_for_side, positive means you have edge),
  "confidence": "high" | "medium" | "low",
  "rationale": "2-3 sentence explanation",
  "risk_flags": ["list", "of", "risks"]
}}"""

    msg = client.messages.create(
        model=ANALYST_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        result = json.loads(msg.content[0].text)
        analysis_cache.put(news_ids, market.condition_id, result)
        side = result.get("side", "YES")
        market_price = market.yes_price if side == "YES" else market.no_price
        analyst_prob = float(result["analyst_prob"])
        edge = analyst_prob - market_price

        return Opportunity(
            market=market,
            news=news_items,
            side=side,
            market_price=market_price,
            analyst_prob=analyst_prob,
            edge=edge,
            confidence=result.get("confidence", "low"),
            rationale=result.get("rationale", ""),
            risk_flags=result.get("risk_flags", []),
        )
    except Exception as e:
        print(f"[analyst] parse error: {e}\n{msg.content[0].text[:200]}")
        return None


def find_opportunities(
    news_items: list[NewsItem],
    markets: list[Market],
    min_edge: float = 0.05,
    min_liquidity: float = 5000,
) -> list[Opportunity]:
    """Full pipeline: triage → deep analysis → ranked opportunities."""
    # Filter low-liquidity markets
    liquid_markets = [m for m in markets if m.liquidity >= min_liquidity]

    # Group news by market after triage
    pairs = triage_news(news_items, liquid_markets)
    market_news: dict[str, list[NewsItem]] = {}
    pair_markets: dict[str, Market] = {}
    for news, market in pairs:
        key = market.condition_id
        market_news.setdefault(key, []).append(news)
        pair_markets[key] = market

    opportunities = []
    for condition_id, news in market_news.items():
        market = pair_markets[condition_id]
        opp = analyze_opportunity(news, market)
        if opp and opp.edge >= min_edge:
            opportunities.append(opp)

    return sorted(opportunities, key=lambda o: o.edge, reverse=True)
