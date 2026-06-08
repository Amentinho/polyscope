"""Mock analyst — returns synthetic opportunities without calling Claude."""

import random
from analyst.analyst import Opportunity
from ingester.sources import NewsItem
from polymarket.client import Market


def mock_opportunities(news_items: list[NewsItem], markets: list[Market], min_edge: float = 0.05) -> list[Opportunity]:
    """Generate fake but structurally valid opportunities for pipeline testing."""
    random.seed(42)
    results = []

    sample_markets = [m for m in markets if m.liquidity > 0][:10]
    sample_news = news_items[:5] if news_items else []

    for i, market in enumerate(sample_markets):
        side = random.choice(["YES", "NO"])
        market_price = market.yes_price if side == "YES" else market.no_price
        # Inject a fake edge so opportunities pass the threshold
        analyst_prob = min(market_price + random.uniform(0.06, 0.20), 0.97)
        edge = analyst_prob - market_price

        if edge < min_edge:
            continue

        results.append(Opportunity(
            market=market,
            news=sample_news[:2],
            side=side,
            market_price=market_price,
            analyst_prob=analyst_prob,
            edge=edge,
            confidence=random.choice(["high", "medium", "low"]),
            rationale="[MOCK] Synthetic opportunity generated for pipeline testing. No real analysis performed.",
            risk_flags=["mock data", "do not trade"],
        ))

    return sorted(results, key=lambda o: o.edge, reverse=True)
